---
name: webgl-product-turntable-studio
description: >-
  A self-contained Three.js "studio" that shows ONE 3D product on a lit turntable and lets the visitor
  spin it, orbit it, and repaint it live in real physically-based clearcoat — the reusable centerpiece for
  any single-product showcase or configurator (cars, furniture, sneakers, jewelry, appliances, a device).
  Use WHENEVER a build needs "let them spin it around", "change the color live", "a 3D configurator",
  "show the product in 3D and let them customize it", "turntable / rotating hero", "pick a finish and see
  it", or an interactive product hero that is one item (not a gallery). COMPLEMENTS
  immersive-evidence-workspace: that skill is the MULTI-product AR gallery you walk through and select from;
  THIS is the single-item studio you drop a selected product into — repaint, orbit, cinematic camera. Pair
  it with gltf-draco-model-normalizer (to load a real .glb) or parametric-3d-model-builder (to synthesize
  the mesh from data), and with website-build-standard for the page around it.
---
# WebGL Product Turntable Studio

## What it is / when to use / what it composes with
A ~290-line vanilla IIFE (`window.Studio`) that owns one WebGL canvas and gives any 3D product the same
premium treatment: environment-lit reflections, a per-item tinted backdrop + floor glow, an idle turntable
that yields to orbit-drag, a cinematic fly-in camera, and **live repaint** of the body material. It is
render-source-agnostic — it drives both a procedurally-built mesh and a loaded glTF through one code path,
so you can start with synthesized models and upgrade individual items to real meshes with no UI change.

Public API: `Studio.init(canvas)`, `.loadCar(obj)`, `.setPaint(hex)`, `.setAutoRotate(bool)`,
`.resetView()`, `.frontView()`, `.resize()`. (Rename `car`→`product` when you lift it.)

Composes with: **gltf-draco-model-normalizer** (supplies `loadModel`), **parametric-3d-model-builder**
(supplies `loadProcedural`), **immersive-evidence-workspace** (the gallery that hands a product to this
studio), **website-build-standard** (the host page), **web-effects-catalog** (page-level motion around it).

## Reference implementation — exact source
Repo: `~/Projects/clients/supercar-garage`.
- Scene + renderer setup — `public/js/studio.js:48-104`
  - PBR-correct renderer: sRGB encoding + ACES Filmic tone mapping + exposure — `studio.js:51-53`
  - **Free reflections with no HDR file**: PMREM-bake a `RoomEnvironment` into `scene.environment` —
    `studio.js:65-66` (this is what makes clearcoat paint look wet without shipping an .hdr)
  - Floor disc + cylindrical backdrop wall (BackSide) — `studio.js:68-77`
  - Key directional (shadow-casting) + hemisphere fill + tinted rim spotlight — `studio.js:79-88`
  - OrbitControls with damping + distance/polar clamps; `start` event kills auto-rotate — `studio.js:90-94`
- Per-item tinted backdrop + floor glow, generated on a 2D canvas — `studio.js:26-46`, applied in
  `setGlow` — `studio.js:118-122`
- Cinematic fly-in / reframe camera tween — `frameHero` `studio.js:124-133`, eased in
  `frame()` `studio.js:261-278` (idle turntable + wheel spin + tween all live in `frame`)
- **Live repaint** — `setPaint` `studio.js:249`; the body material is a `MeshPhysicalMaterial` with
  `clearcoat:1.0` over a metallic base — see `carBuilder.js:67-69` (procedural) and `studio.js:202-203`
  (model). Recolor is a single `material.color.set(hex)`.
- Clean teardown on product swap — `clearCurrent` disposes geometry + materials + textures —
  `studio.js:106-116`
- App wiring (the pattern to copy): open studio + build swatches + load — `public/js/app.js:77-99`;
  swatch dock builds from a `paints:[{name,hex}]` array — `app.js:105-123`; button/keyboard wiring +
  `Studio.init` in boot — `app.js:205-225`.

## How to reapply
1. **Drop in** `studio.js` + the bundled `vendor/` (three.min.js, OrbitControls, RoomEnvironment; add
   GLTFLoader/DRACOLoader only if you also use the normalizer). Rename `car`→`product`, `glow`→`accent`.
2. **Feed it a product object** shaped `{ accent, default_paint, paints:[{name,hex}], render, ... }`.
   `render:'procedural'` → parametric builder; `render:'model'` → normalizer. Everything else (turntable,
   repaint, camera) is identical.
3. **UI**: a canvas `#stage`, a swatch dock built from `product.paints` (each swatch calls
   `Studio.setPaint`), and Spin/Reset/Front buttons wired to `setAutoRotate/resetView/frontView`
   (`app.js:211-221`).
4. **Resize contract**: call `Studio.resize()` on a `requestAnimationFrame` AND again on a short timeout
   after you reveal the canvas (`app.js:96-97`) — the container has no size until layout settles.

## Gotchas (from the code)
- **Dispose or you leak GPU memory.** Every product swap must traverse-and-dispose geometry, materials,
  and every `material.map` (`studio.js:106-116`); WebGL does not garbage-collect these.
- **PBR needs the two renderer settings.** Without sRGB encoding + ACES tone mapping (`studio.js:51-53`)
  clearcoat paint and reflections look flat/washed. RoomEnvironment PMREM (`:65-66`) is what supplies the
  reflections — you do NOT need to ship an HDR.
- **Canvas is 0×0 until its container is laid out.** Size it after a rAF + a delayed second call, or the
  first frame renders into a zero viewport (`app.js:96-97`, `studio.js:280-287` reads `clientWidth`).
- **Orbit must cancel the turntable**, or the model fights the user; hook `controls` `start`
  (`studio.js:94`) to clear `autoRotate` and any running tween.
- **Some baked single-texture meshes can't cleanly recolor** — gate the paint dock behind a per-product
  `noPaint` flag and hide it rather than shipping a broken configurator (`app.js:87-89`).
