---
name: gltf-draco-model-normalizer
description: >-
  Load ANY .glb/.gltf from anywhere (a marketplace download, a client upload, a Draco-compressed export)
  and make it "just work" on screen — auto-scaled to a target size, centered and dropped onto the floor,
  its meshes mapped to material roles (body/chrome/glass/wheels), given a real contact shadow, and falling
  back gracefully if it fails to load. Use WHENEVER a build ingests a 3D model whose exact size, origin,
  orientation, or mesh names you do NOT control: "add a real 3D model", "let the client upload a .glb",
  "load this model from Sketchfab/TurboSquid/CGTrader", "drop-in glTF viewer", "why is my model huge / off
  the floor / invisible", or a Draco-compressed asset that needs a bundled decoder (no CDN). COMPLEMENTS
  webgl-product-turntable-studio (this is the loader that studio's `render:'model'` path calls) and
  immersive-evidence-workspace (use it wherever those load a real mesh into a pedestal/slot).
---
# glTF + Draco Model Normalizer

## What it is / when to use / what it composes with
The "drop any model in and it looks right" loader. Arbitrary glTF assets come in every scale (millimetres
to hundreds of units), every origin (centered, or offset so they float or sink), and with artist-chosen
mesh names — so a naive `GLTFLoader.load` gives you a giant, off-floor, wrongly-lit blob. This subsystem
normalizes all of that deterministically and applies studio-quality materials, with a hard rule that the
viewer is **never left empty** on failure.

Composes with: **webgl-product-turntable-studio** (calls this as `loadModel`; the normalizer returns the
`{root, wheels, setBody}` the studio's turntable + repaint expect), **parametric-3d-model-builder** (the
fallback when a model fails to load), **immersive-evidence-workspace** (real meshes in gallery slots).

## Reference implementation — exact source
Repo: `~/Projects/clients/supercar-garage`, `public/js/studio.js`.
- **Bundled Draco decoder, no CDN** — `DRACOLoader.setDecoderPath('vendor/draco/')` wired into GLTFLoader
  — `studio.js:97-99`; the decoder (`draco_decoder.js/.wasm/.wasm_wrapper`) ships in
  `public/vendor/draco/` (README `:33-34`). Draco-compressed models then load with zero extra work.
- **Auto-fit ANY model** — `loadModel` `studio.js:175-247`:
  - measure with `Box3.getSize`, scale so the longest horizontal axis hits a target length —
    `studio.js:181-185` (`scale = targetLength / longest`, or an explicit `scale`)
  - re-measure, then center in X/Z and drop so `box.min.y` sits on the floor — `studio.js:186-188`
  - optional explicit `rotationY` — `studio.js:189`
- **Mesh-name → material role mapping** — `apply(names, mat)` resolves by `getObjectByName` —
  `studio.js:197-204`; roles: body = physical clearcoat paint, chrome = metal, glass = `transmission:1.0`
  physical. Auto fallback when there is no mapping: find the largest mesh by bbox volume
  (`largestMesh` `studio.js:164-173`) and recolor only that, preserving the artist's other materials
  (`studio.js:205-216`).
- **Contact shadow** — baked-AO plane with `MultiplyBlending` when the asset ships an AO texture
  (`studio.js:219-225`), else a generated soft radial "blob" shadow (`blobShadow` `studio.js:150-162`).
- **Camera framing derived from the FITTED size** (or an explicit `camera` block) — `studio.js:233-236`.
- **Never leave the stage empty** — on load error, fall back to the procedural build —
  `studio.js:242-246`.
- Config shape a model carries (`model:{ file, body, chrome, glass, wheels, wheelAxis, ao, aoSize,
  camera, scale/targetLength/rotationY, noPaint }`) — documented in README `:80-99`.

## How to reapply
1. **Ship the decoder locally** under `vendor/draco/` and point `DRACOLoader` at it — never a CDN (CSP +
   offline). Set it on the GLTFLoader before any `.load` (`studio.js:97-99`).
2. **Always normalize**: measure → scale to target → recenter → floor-drop (`studio.js:181-188`). Do this
   for every asset; never assume a model's export units/origin.
3. **Map roles if you know the mesh names** (best result); otherwise recolor the largest mesh and keep the
   rest (`studio.js:205-216`). Expose a `noPaint` flag for baked single-texture models.
4. **Give it a shadow** (baked AO plane, or the blob generator) — a floating car with no contact shadow
   reads as fake.
5. **Wire the fallback** so a 404/parse error swaps to a synthesized model instead of a black canvas.

## Gotchas (from the code)
- **Bundle Draco or compressed models silently fail** — the decoder is separate from three.js; a missing
  `vendor/draco/` path yields an empty scene with only a console warning.
- **Don't `.center()` a loaded root** — you want X/Z centered but Y grounded (`min.y`→0), not the bounding
  box centered (which buries half the model under the floor) — `studio.js:186-188`.
- **AO plane must be `MeshBasicMaterial` + `MultiplyBlending` + `toneMapped:false`** or the shadow tints
  wrong / gets tone-mapped into grey (`studio.js:223`); set `renderOrder` and a tiny `y` offset to avoid
  z-fighting with the floor (`:225`).
- **Glass needs `MeshPhysicalMaterial` with `transmission:1.0`**, not a transparent standard material
  (`studio.js:195`).
- **Clear the model's separate contact-shadow mesh on swap** — it's added to the scene independently of
  the model root, so track it (`current_extra`) and remove it in teardown (`studio.js:107`).
