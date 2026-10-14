---
name: local-media-generation-stack
description: >-
  Stand up and run FREE, commercially-licensed image and video generation on a client's OWN hardware
  (an Apple-silicon Mac for images via stable-diffusion.cpp Metal, an NVIDIA box such as a DGX Spark
  for video via ComfyUI CUDA). No cloud credits, no per-image cost, nothing leaves the building. Use
  WHENEVER a build or client asks to "generate images locally", "stop paying for image gen", "run
  Qwen/FLUX/Z-Image/Wan on the Mac/Spark", "pick an open model we can sell output from", "set up
  video generation on the NVIDIA box", or "why is the local image/video lane down". It gives you a
  licence-verified model lineup, the hash-pinning rule, the per-machine install shape, the "run
  light" reliability contract, and a troubleshooting table. COMPLEMENTS media-generation-dispatch
  (that skill is the router and the cloud-engine seam; THIS is the local engine behind it on real
  hardware), local-first-inference-ladder (text LLMs; this is pixels), and worker-media-headers
  (serve the output). Guardrails: verify the LICENCE OF THE EXACT WEIGHT FILE before it loads,
  because new releases often change licence (Qwen-Image-2.1 is research-only; FLUX.2-klein-9B is
  non-commercial). "Uncensored" repacks are not a feature: check what the file actually is first.
---

# Local Media Generation Stack (licence-clear models · pinned weights · run light)

## What it is / when to use

A deployment pattern for **owned-hardware generative media**:

- An **Apple-silicon Mac** runs images through `stable-diffusion.cpp` on Metal. Each job is its own process, so memory comes back when it exits.
- An **NVIDIA box** (DGX Spark, RTX workstation) runs video through ComfyUI on CUDA.

The client pays once for hardware and nothing per image.

Use it when:

- the client is spending on Midjourney, OpenAI Images or Replicate for content-pillar media;
- media must stay private;
- you're asked to evaluate a "free/uncensored local model" from a reel or a post.

Don't use it for:

- an 8 GB laptop: images only, FLUX.2-klein-4B Q4, and no video;
- a client who needs a model only available as an API (e.g. Wan 3.x, Veo).

## Model lineup: licences verified 2026-10-14 (`cardData.license` on Hugging Face)

| Lane | Default (light) | Quality tier | Edit | Fallback |
|---|---|---|---|---|
| Image (Mac) | `Tongyi-MAI/Z-Image-Turbo` 6B, 8 steps | `Qwen/Qwen-Image-2512` 20B (best text in image) | `Qwen/Qwen-Image-Edit-2511` | `black-forest-labs/FLUX.2-klein-4B` |
| Video (NVIDIA) | `Wan-AI/Wan2.2-TI2V-5B` 720p | `Wan-AI/Wan2.2-T2V-A14B` / `I2V-A14B` | — | — |

All of the above are **Apache-2.0**.

Conditional: `Lightricks/LTX-2.3` (native audio) is under the LTX-2 Community License. It's reported free under $10M annual revenue; read `LICENSE-2` and get sign-off.

**Refuse for commercial output:**

| Model | Licence |
|---|---|
| Qwen-Image-2.1 / 2.1-Turbo (and every repack) | Qwen Research License, §2(b): no commercial use |
| FLUX.2-klein-**9B**, FLUX.2-dev, FLUX.1-dev | Non-commercial |
| HunyuanVideo-1.5 | Tencent community licence: MAU and territory terms |
| SD 1.5 | OpenRAIL-M; excluded by Ronin policy |

**Re-verify every time.** These lists drift. Newer releases in the same family often carry a *more* restrictive licence than older ones (Qwen-Image Apache → Qwen-Image-2.1 research-only). One API call answers it:

```bash
curl -s https://huggingface.co/api/models/<org>/<repo> | python3 -c 'import sys,json;d=json.load(sys.stdin)["cardData"];print(d.get("license"),d.get("license_name",""),d.get("license_link",""))'
```

`other` means read the linked LICENSE. A quant or repack inherits the licence of its **base_model**, whatever its own card says.

## Reference implementation (Kingmaker / Solomon: read, don't copy the moat)

- **Licence gate:** `Kingmaker/solomon/server/src/runtime/media-weights-licence-gate.ts`
  - An ordered regex registry; first match wins. Put derivative and variant rules *before* the family rule.
  - Unknown is refused.
  - Policy exclusions are kept separate from the licence verdict.
- **Hash-pinned manifest:** `Kingmaker/solomon/server/src/runtime/media-weights-manifest.ts`
  - Entries are `{id, source, licence, sha256, bytes, filenames}`; the seed is `PENDING_PIN`.
  - The operator pins by hashing the exact reviewed file.
  - The gate order is manifest → pin → streamed sha256 → licence, so the verdict is about *these bytes*, not a filename.
- **sd.cpp lane:** `Kingmaker/solomon/server/src/runtime/open-gen/flux-sdcpp-lane.ts`
  - Every component file (diffusion, text encoder(s), VAE) is gated separately.
  - Spawned through the heavy-job admission door with a RAM estimate from the pinned sizes, so a set that can't fit is refused `CONFIG_HOLD` instead of swapping the box.
- **Build order for the Mac + Spark rollout:** `Kingmaker/docs/BUILD-ORDER-local-media-gen.md`

## How to reapply on a client box

1. **Inventory the hardware.** RAM or VRAM per machine, free disk (budget ≥ 150 GB for a full image + video set), and the network link between the machines.
2. **Pick from the lineup** by tier. Ship the *light* default and enable the quality tier only on request.
3. **Install the engines at pinned commits.**
   - Mac: build `stable-diffusion.cpp` with Metal.
   - NVIDIA: ComfyUI. On a DGX Spark use NVIDIA's ComfyUI playbook so NGC PyTorch is kept.
   - Pin custom-node commits too. Never `git pull` in production.
4. **Download the full component set** (diffusion + text encoder(s) + VAE) with `hf download`, then hash each file:

   ```bash
   shasum -a 256 <file>; stat -f%z <file>
   ```

   Record each file's hash and size in the manifest. Set `HF_HUB_OFFLINE=1` afterwards.
5. **Take sd.cpp / ComfyUI flags from the engine's own docs at the pinned commit.** For example, sd.cpp passes Qwen-family encoders as `--llm`, and turbo models need their exact steps / cfg / sigmas. Blog posts go stale.
6. **Connect the machines over loopback.** ComfyUI has **no auth**: bind it to `127.0.0.1` on the NVIDIA box and reach it from the Mac through an SSH or Tailscale tunnel kept alive by a LaunchAgent. Never expose `:8188` on the LAN.
7. **Supervise.** ComfyUI under `systemd Restart=always`; the tunnel under a LaunchAgent with `KeepAlive`. Add a disk-floor alarm and rotation for generated media.
8. **Smoke test and record evidence.** One image per model and one short video, with measured times, memory back at baseline afterwards, and zero outbound calls.

## "Run light" contract (what keeps the owner from calling)

- **One heavy job per machine.** Video never runs beside a model load.
- **Load on demand, unload after.**
  - sd.cpp: one process per job.
  - ComfyUI: `POST /free {"unload_models":true,"free_memory":true}` after every job.
- **Admission before spawn.** A job that won't fit is refused with a reason. It never starts and swaps.
- **Plain-words status for every failure:**
  - "The video machine is offline."
  - "Model X isn't installed. Run `… install`."
  - "Disk is nearly full."
  - Never a placeholder image, never `executed:true` without a real file.
- **No silent updates.** Models, engines and nodes change only by a deliberate update command, followed by the smoke test again.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Video lane says "ComfyUI not installed" while it's running on the NVIDIA box | Capability probe reads a *local* models dir | Use a remote-mode probe (ComfyUI `/object_info`, `/models/<folder>`) plus a pin report from the remote box |
| Wan 2.2 on a Spark takes 15–30+ min or OOMs | Native Diffusers pipeline, or wrong precision / offload settings | Run it through ComfyUI with the playbook's settings; start with TI2V-5B; measure before promising |
| A weight is refused with `PENDING_PIN` / `HASH_MISMATCH` | Not pinned, or the file changed or is a different variant | Re-review the file, re-hash, update the manifest. Never edit the pin to match an unreviewed file |
| A gate clears a model whose card says non-commercial | A broad family regex (e.g. `flux2-klein` matching 9B) | Add the restrictive variant rule *above* the family rule, plus a test |
| Image looks wrong or noisy on a turbo model | Wrong steps / cfg / sigmas | Use the model card's exact sampling contract |
| The box "just stopped" | Disk full, tunnel down, or service crashed | Check `doctor`: disk floor, LaunchAgent / systemd status |

## Gotchas

- **Read what the file *is* before evaluating it.** A popular "uncensored Qwen-Image GGUF" turned out to be only an abliterated **text encoder**. It needed a research-licensed denoiser to draw anything, and its own card showed the abliteration flipped none of its 45 test prompts. Check `base_model`, `tags` and the sibling files first.
- **The licence follows the base model**, not the repacker's card or a social post. "Users keep rights to outputs" in a tweet does not override §2(b) of a licence file.
- **One pinned file does not vouch for the set.** Pin the diffusion file, every text encoder and the VAE separately.
- **Memory profiles written for 8 GB will throttle a 128 GB box** (low-res floors, forced upscales, tiny max side). Add a high-memory tier instead of hand-editing constants.
- **Abliterated or uncensored weights on a client system are a policy decision**, not a licence one. Document the client's acceptable-use policy. Prohibited uses still apply: sexual content involving minors, and intimate images of real people without consent.
