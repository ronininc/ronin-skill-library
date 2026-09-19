---
name: webgpu-image-finish-pass
description: >-
  A sovereign, client-side WebGPU image-finish / filter lane: give any image in the browser a
  cinematic "finish" by running a STACK of hand-authored WGSL fragment effects over it — vignette,
  soft glow, teal–orange grade, film grain, chromatic aberration, gaussian blur, radial depth-of-field,
  ACES filmic tonemap, exposure/contrast/saturation, unsharp mask — each dialable via tunable uniforms,
  composed in order, rendered on the GPU with NO server, NO diffusion weights, and NO external shader
  library. Use WHENEVER a build needs to post-process or grade an image/photo/canvas in-page: "make the
  hero photo look cinematic", "add a filter / grade / vignette / glow / grain", "clean up / sharpen an
  uploaded photo", "tilt-shift / depth-of-field a product shot", "let visitors tune a look with sliders",
  "finish this frame before we show it". COMPLEMENTS website-build-standard (finish a hero/gallery image),
  webgl-product-turntable-studio and immersive-evidence-workspace (a post pass over the rendered canvas),
  svg-marketing-asset-generator (grade a rasterized promo), and media-generation-dispatch (a finishing
  stage after an engine returns a raster). Do NOT use it to GENERATE an image (that is a diffusion engine),
  to route between engines (that is media-generation-dispatch), or for CSS/JS motion (that is
  web-effects-catalog) — this is the pixel-level GPU finish only.
---

# Client-Side WebGPU Image-Finish / Filter Pass

## What it is / when to use / composes with
A pure browser graphics technique: load an image into a GPU texture, then run one or more **fullscreen
fragment shader passes** over it and either **overlay** the result (blended over the frame) or **replace**
the frame (a source-sampling "post" effect that reads neighbouring pixels). Effects are small, self-contained
WGSL modules with a `struct P { … }` uniform so every look is **dialable** (sane defaults + a documented
min/max range), and they compose as an ordered **stack** — a richer finish costs a shader pass, not a
round-trip to a server or a generative model. Everything runs on `navigator.gpu` in the visitor's browser:
no backend, no weights, no CDN shader library, CSP-clean.

Two effect kinds share one stack:
- **overlay** — the shader draws a fullscreen layer (vignette darkening, glow, a grade tint, grain) that is
  **blended** over the accumulated frame (`over` / `screen` / `multiply` / `add`).
- **post** — the shader is bound the current frame as a sampleable texture and `textureSample`s it with an
  offset (blur, chromatic aberration, DOF, tonemap, sharpen, colour-correct); its output **replaces** the
  frame.

Composes with: **website-build-standard** (finish a hero/gallery image before it ships),
**webgl-product-turntable-studio** / **immersive-evidence-workspace** (run a post pass over the rendered
product canvas for glow + grade), **svg-marketing-asset-generator** (grade a rasterized promo),
**media-generation-dispatch** (a finishing stage after a routed engine returns a raster), **worker-media-headers**
(serve the exported PNG). It is a *finish*, never a generator.

## Reference implementation — exact source
The effect library and the overlay/post + blend + stack architecture (server-side reference; port the
same WGSL and the same pass model to the browser — see below):

- **Hand-authored WGSL effect library** — `server/src/runtime/shader-asset-seed.ts`
  - `fx()` — fullscreen OVERLAY builder: emits `struct P {…}` at `@group(0)@binding(0)` + a `@fragment fn main`
    that computes `uv = pos.xy / vec2f(W, H)` — `shader-asset-seed.ts:9-10`.
  - `pfx()` — SOURCE-SAMPLING POST builder: binds `src: texture_2d<f32>` + `samp: sampler` at
    `@group(0)@binding(0/1)` and the uniform struct at `@binding(2)`; body gets `uv` and `texel = 1/W,1/H`
    so it can `textureSample(src, samp, uv ± off)` — `shader-asset-seed.ts:14-15`.
  - Overlay effects: vignette `:18-26`, soft glow `:33-41`, teal–orange grade `:42-47`, film grain (hash
    noise) `:48-54`, scanlines `:27-32`.
  - Post effects: chromatic aberration (edge-growing RGB split) `:56-62`, gaussian blur (5×5 weighted taps)
    `:63-72`, radial depth-of-field (sharp focus disc → ramped blur) `:73-85`, ACES filmic tonemap
    (Narkowicz closed-form fit) `:86-97`, exposure/contrast/saturation `:98-108`, unsharp mask `:109-115`.
  - Each entry ships `params: [{ name, purpose, default, min, max }]` — the dial contract.
- **Pass model + blend + stack runner** — `server/src/runtime/vgpu-shader-render.ts`
  - Overlay pass (render one effect to an RGBA layer) — `renderShaderLayer` `:27-46`.
  - Post pass (upload frame → sampleable texture, sample+replace) — `renderPostEffect` `:53-80`.
  - CPU blend math (`over`/`screen`/`multiply`/`add`, base alpha preserved) — `compositeLayer` `:83-98`.
  - Ordered stack runner with per-effect uniform overrides merged onto defaults — `applyShaderStack` +
    `ShaderStackEntry` `:118-162`.
- **Effect asset shape** (blend mode, overlay-vs-post `mode`, tunable `params`) —
  `server/src/runtime/shader-asset-store.ts:16-38`.
- **Headless-capture GPU note** (only if a client renders headless in CI): `--disable-gpu` under new
  headless Chrome removes WebGL2/WebGPU *entirely* rather than falling back to software — leave the GPU on —
  `server/src/runtime/headless-chrome-gpu.ts:40-66`.

## How to reapply in a CLIENT build (browser, no server, no weights)
1. **Get a device.** `const adapter = await navigator.gpu.requestAdapter(); const device = await
   adapter.requestDevice();` Feature-detect first (`if (!navigator.gpu) …` → fall back to the untouched
   image); WebGPU is stable in Chrome/Edge and Safari 18+.
2. **Fullscreen pass rig.** One vertex shader emits a full-screen triangle
   (`@vertex fn vs(@builtin(vertex_index) i:u32) -> @builtin(position) vec4f` from `array(vec2f(-1,-1),
   vec2f(3,-1),vec2f(-1,3))`). Reuse it for every effect; only the `@fragment` swaps.
3. **Resolution.** Drop the build-time `__W__/__H__` tokens — pass width/height as **uniform** fields (or a
   `resolution: vec2f`) instead of string-substituting the source, so one compiled module handles any size.
4. **Overlay effect** → render the fragment to an RGBA texture, then composite over the accumulated frame.
   In the browser prefer a **GPU blend state** on the pipeline (`blend: { color: { srcFactor, dstFactor,
   operation } }`) — `screen`/`multiply`/`add`/`over` map to standard blend factors — instead of the CPU
   `compositeLayer` loop. Keep `compositeLayer`'s formulas as the spec of what each mode must produce.
5. **Post effect** → upload the current frame to a `texture_2d<f32>` (`device.queue.copyExternalImageToTexture`
   from an `<img>`/`ImageBitmap`/canvas, or ping-pong between two textures for later passes), bind a
   `clamp-to-edge` linear sampler, run the `pfx` fragment, and treat its output as the new frame.
6. **Uniforms = the dial.** Pack each effect's `P` struct into a uniform buffer; expose `params` (name +
   min/max) as sliders so a visitor or builder tunes the look live. Merge caller overrides onto defaults
   exactly like `applyShaderStack` (`overrides?.[name] ?? param.default`).
7. **Stack.** Run effects in order into a ping-pong pair of textures; the last write is the finish.
   Present to a `<canvas>` context (`context.configure({ device, format, alphaMode:'premultiplied' })`) for
   display, or `copyTextureToBuffer` → read back → encode a PNG for export/download.
8. **Curate a small library.** Ship the WGSL as static strings (or a tiny JSON manifest of
   `{id, mode, blend, wgsl, params}`) alongside the page — that is your reusable "look" catalog; add
   client-specific grades by writing one more `fx`/`pfx` module.

A good default cinematic finish (order matters): `color-correct` → `grade-teal-orange` → `glow` →
`vignette` → `film-grain` (grade before glow so glow picks up the graded highlights; grain last so it isn't
blurred).

## Gotchas
- **Colour space.** The grade/tonemap effects assume roughly linear-ish RGB; a canvas configured
  `rgba8unorm` is sRGB-encoded. For a faithful ACES/exposure result, work in `rgba16float` intermediate
  textures or linearize on read and re-encode on present. For a quick web finish, `rgba8unorm` throughout is
  usually fine — just know the tonemap will be approximate.
- **Post effects need clamp-to-edge.** A `repeat` sampler makes blur/DOF/aberration wrap the opposite edge
  into the frame; always `addressModeU/V: 'clamp-to-edge'`.
- **Alpha.** `compositeLayer` deliberately preserves the *base* alpha; overlay effects tint colour only. If
  you present to a canvas, match `alphaMode` to whether you want the page background to show through.
- **Blur/DOF are fixed 5×5.** They soften but won't do a heavy bokeh; for a wider blur, raise the tap
  offset (`radius`/`amt`) rather than the loop bounds, or run the blur pass twice.
- **`__W__/__H__` tokens are a server artifact.** They exist because the server runner string-substitutes
  dims before compile. In the browser, a resolution uniform is cleaner and lets one module serve every size.
- **This is the finish, not the source.** It cannot invent content; feed it a real image (photo, rendered
  canvas, generated raster). Feature-detect and degrade to the untouched image where WebGPU is absent.

## Deliberately EXCLUDED (do not port)
- The `vgpu`/`vgpu/node` runner (a vendored third-party MIT package, Dawn headless) — not owned IP; the
  browser uses `navigator.gpu` directly.
- The capacity/tier ladder (`vgpu-shader-tier.ts`: preview/standard/realtime/cinematic gated on local RAM +
  GPU detection) — that is a local-hardware-runtime concern, not a client-graphics one. A client build has
  one target: the visitor's browser.
- The SQLite `shader_asset` catalog + licence-gated registration and the CodeGen↔shader conductor bridge —
  those are private server-side library/orchestration infrastructure; a client ships the WGSL as static
  assets.
