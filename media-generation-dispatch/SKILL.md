---
name: media-generation-dispatch
description: >-
  Pluggable media-generation dispatch: parse ONE free-text creation request ("make an image of X",
  "a 15s reel of the patio", "render a 3D bracket", "design a poster") into a typed media intent
  (subject + format image|video|3d|design + params), then route that format to a SWAPPABLE engine
  adapter that returns a real produced asset — or an honest "engine not available" with remediation,
  never a fabricated success. The engine is a SEAM: a client build points it at a cloud generation
  API (Replicate, fal.ai, OpenAI Images, Google Veo, Stability) behind one typed contract. Use
  WHENEVER a build needs a single natural-language box or voice command to produce media on demand,
  a "generate/make/render this" endpoint, or a provider-agnostic media layer you can re-point without
  touching callers. COMPLEMENTS website-build-standard and commerce-spine (on-demand product/marketing
  media), parametric-3d-model-builder and webgl-product-turntable-studio (they are engines this can
  dispatch to for the 3d format), and worker-media-headers (serve the produced asset). Do NOT use it
  to build a specific generator — use it to route between several.
---

# Media Generation Dispatch (parse intent → route to a swappable engine → return the asset)

## What it is / when to use

A three-part spine that turns one free-text (typed or spoken) creation request into a produced media file:

1. **Parse** the request into ONE typed `MediaIntent` — `{ subject, format, treatment, params }` — where `format ∈ {image, video, 3d, design}`. Media is media: there is no privileged "product-reel lane" and "scene lane", just one intent with variants.
2. **Route** by `format` (plus cheap cues) to the right **engine adapter**.
3. **Produce**: the adapter runs and returns a uniform outcome carrying the real asset path, or fails **closed and honestly** with a reason + remediation — the `executed` flag is *never* set optimistically.

The engine is a **seam**. The reference wires local engines, but the whole point is that a client build swaps in a cloud API (or a mix — Replicate for image, Veo for video, a WebGL/parametric builder for 3d) behind the same `resolveCapability()` / `run()` contract, and no caller changes.

Use it when a build wants:
- a single "describe it and I'll make it" box or `/generate` endpoint;
- a provider-agnostic media layer you can re-point (swap providers, add a format) in one file;
- honest degradation — a request the current provider can't serve says exactly that, instead of returning a placeholder as if real.

Do **not** use it as a *generator* — it is the router *between* generators. The actual image/video/3d engine is a separate concern behind the seam.

## Reference implementation (TSS-own)

Genericize from these files — take the **spine**, drop anything product-specific (see Gotchas):

- **Intent parser (pure, portable as-is):** `server/src/runtime/media-intent.ts:52` — `parseMediaIntent(transcript)`. First-match format detection `server/src/runtime/media-intent.ts:46` (`detect()` walks an ordered `[RegExp, value][]` table, first hit wins, else a fallback). Typed intent shape `server/src/runtime/media-intent.ts:13`. Subject extraction: prefer the clause after a preposition ("scene **of** …"), else peel the leading "make a movie of" shape, else the whole utterance (`media-intent.ts:60-65`). Never emits a placeholder subject.
- **Capability-gated engine adapter (the seam):** `server/src/runtime/media/image-generation.ts:43` — `resolveImageCapability()` returns `{ state, ok, endpoint, reason, remediation }` by checking config **and** live reachability; `server/src/runtime/media/image-generation.ts:150` — `runImageGeneration()` is the governed end-to-end: gate → run → return `{ executed, state, spoken, assetPath, detail }`, honest closed failure when `!ok`. Same contract for video at `server/src/runtime/media/video-generation.ts:48` (`resolveVideoCapability`) and `:106` (`runVideoGeneration`).
- **Format → engine dispatch:** `server/src/runtime/route-dispatch.ts:1191` (`planCreativeDesign` — photoreal-image cue routes to the image engine, else the vector/design engine, and an unavailable image engine *offers* the vector fallback instead of silently substituting) and `server/src/runtime/route-dispatch.ts:1322` (`planRenderMesh` — an explicit motion noun with a subject and no upstream geometry routes text→video, else a geometry render). The uniform produced-outcome contract is `RouteExecution` at `server/src/runtime/route-dispatch.ts:140` — note `executed: boolean` ("True only when the engine genuinely did the thing. Never set optimistically") and the structured `output` carrying the servable asset.

## How to reapply in a CLIENT build

**1. Define the typed intent + a pure parser.** Copy the `MediaIntent` shape and `parseMediaIntent`/`detect` almost verbatim — they have zero runtime dependencies. Trim `treatment`/`archetype`/`merchant`/`products` to whatever the client actually branches on; keep `subject` + `format` always.

```ts
export type MediaFormat = 'image' | 'video' | '3d' | 'design';
export interface MediaIntent { subject: string; format: MediaFormat; params: Record<string, unknown>; }
// ordered table, first match wins, sensible fallback — see media-intent.ts:46
```

**2. Define ONE engine-adapter interface (the seam).** Every engine — local *or* cloud — implements the same two methods:

```ts
export interface MediaEngine {
  resolveCapability(): Promise<{ ok: boolean; reason: string; remediation: string }>;
  run(intent: MediaIntent): Promise<{ executed: boolean; assetPath: string | null; detail: string | null; spoken: string }>;
}
```

**3. Point each format at a cloud engine.** A `ReplicateImageEngine` / `FalVideoEngine` / `OpenAiImageEngine` implements `resolveCapability` as "is the API key set and does a `HEAD`/models ping succeed?" and `run` as "POST the prompt, poll the prediction, download the result URL to a served path." This is the *drop-in replacement* for the reference's local ComfyUI internals — same interface, different body. For `3d`, dispatch to `parametric-3d-model-builder` or `webgl-product-turntable-studio`; for `design`, an SVG/template engine.

**4. Dispatch.** `const engine = registry[intent.format]; const cap = await engine.resolveCapability(); if (!cap.ok) return honestUnavailable(cap); return engine.run(intent);` — mirror `planCreativeDesign`'s "offer a fallback, never silently substitute" (route-dispatch.ts:1222).

**5. Serve the asset.** Hand `assetPath` to `worker-media-headers` (or any static/CDN serve) and return a URL; persist a record if the build has one.

## Gotchas

- **Honest `executed`, always.** The single most important discipline: `executed:true` only when a real file was produced. A down provider, an empty result, or a timeout returns `executed:false` with the real `detail` (image-generation.ts:168-171). Callers/UI trust this flag; faking it is worse than failing.
- **Capability check = config AND liveness.** "API key present" is not "ready." The reference probes the live endpoint (`resolveImageCapability` at :48) — a cloud port does the equivalent models/health ping so you fail before spending a slow generation call.
- **Ordered first-match table, most specific first.** `3d model` and `poster` must be tested before the generic `video`/`image` cues, exactly like the format table (media-intent.ts:54) and its scene ordering — otherwise a "3d model reel" mis-parses.
- **Never leak a placeholder as real.** When the chosen engine is off, *offer* the cheaper alternative ("say 'design it as a poster'"), don't silently return it (route-dispatch.ts:1222-1229).
- **Strip the product-specific wrapper.** In the reference, dispatch lives inside a governed voice router with proposal/approval gates, an artifact substrate, and an on-screen evidence surface (`showOnEvidenceSquare`, `openEngineReporter`). Those are **not** part of this pattern — keep only parse → route-by-format → adapter → produced-outcome. Add your own auth/persistence around it.
- **Do NOT copy the local render pipeline.** The reference's deterministic Blender/Godot/heavy-slot plan and the ComfyUI workflow graphs (`buildDiffusionWorkflow`/`buildVideoWorkflow`) are one specific local engine's internals for constrained hardware. A client build replaces the whole engine body with a cloud API call; only the *seam contract* transfers.
- **Path safety on the way out.** Resolve produced files relative to a single media dir and reject anything escaping it before turning it into a URL (see `servedMediaUrl` at route-dispatch.ts:706) so an engine can never hand back an arbitrary filesystem path.
