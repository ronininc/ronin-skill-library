---
name: parametric-3d-model-builder
description: >-
  Synthesize a detailed, recolorable 3D product mesh AT RUNTIME from a compact JSON "shape" schema — zero
  downloaded assets, instant, fully self-authored — by extruding a profile silhouette across a width in one
  coordinate space and bolting on feature-flagged add-ons. Use WHENEVER a build needs 3D models but has no
  asset budget, no licensed meshes, or many variants to show: "we can't afford/find 3D models", "generate
  the models in code", "show a whole lineup in 3D without downloads", "procedural / parametric model", "let
  data drive the geometry", or a catalog where each item differs by a few numbers (dimensions, features).
  Reference domain is vehicles, but the technique fits any profile-extrudable product (furniture, tools,
  bottles, boats, buildings). COMPLEMENTS webgl-product-turntable-studio (this supplies its
  `render:'procedural'` path) and gltf-draco-model-normalizer (the upgrade path: swap a synthesized item
  for a real .glb later with no UI change).
---
# Parametric 3D Model Builder

## What it is / when to use / what it composes with
A pure builder: `build(product) -> { group, setPaint, wheels }`. Instead of loading a mesh, it constructs
one in code from `product.shape` — a flat object of ~20 numbers plus a handful of feature flags. Every
item in a catalog is a different set of numbers, so N products cost N tiny data objects and ZERO bytes of
downloaded geometry, and load instantly even offline. The key discipline is **one coordinate space**: a
side silhouette is built as a 2D profile, extruded across the width, and translated (never re-centered) so
that every add-on lands exactly where its maths says relative to the same origin.

Composes with: **webgl-product-turntable-studio** (renders + repaints + spins whatever this returns),
**gltf-draco-model-normalizer** (per-item upgrade to a real mesh), **single-source-data-embed** (the shape
schema lives in the one source module that feeds both the app and the DB).

## Reference implementation — exact source
Repo: `~/Projects/clients/supercar-garage`, `public/js/carBuilder.js` (whole file, `window.CarBuilder`).
- **One coordinate convention** documented up top, with a front-relative `X(f)` helper —
  `carBuilder.js:6-8`, `:60,62`. `+X` = front, `Y` = height above floor (0 = ground), `Z` = width.
- **Extrude-a-profile helper** — `extrudeZ(shape, width, bevel)` extrudes a `THREE.Shape` across the width
  then `geo.translate(0,0,-width/2)` to center in Z **without** `.center()` — `carBuilder.js:27-35`.
- **Body silhouette** as a single `THREE.Shape` of line/quadratic segments driven by shape params
  (nose/hood/cowl/roof/deck/tail heights, roofStart/roofEnd) — `carBuilder.js:71-88`.
- **Shared material palette** (tire/rim/chrome/carbon/trim/caliper) defined once — `carBuilder.js:18-25`.
- **Feature flags → optional add-ons**, each positioned in the same space:
  side intakes `:120-126`, front splitter `:139-142`, finned rear diffuser `:145-152`, rear wing
  (`gt`/`active`/`lip`) `:155-170`, exhausts (`quad`/`center`/dual, skipped when `ev`) `:173-181`,
  mirrors `:184-187`, head/tail lights (emissive) `:129-136`, wheels + body-colored fender arches
  `:106-117`.
- **Detailed sub-assembly from primitives** — `makeWheel` composes tire/rim/spokes/hub/caliper from
  cylinders + torus + boxes — `carBuilder.js:37-56`.
- **Live repaint hook** — the body uses one `MeshPhysicalMaterial` (metallic base + `clearcoat:1.0`) and
  `setPaint(hex)` just sets its color — `carBuilder.js:67-69,189`.
- **The schema that drives it** (copy the shape, not the data): an example `shape:{...}` object —
  `db/cars.mjs:32-36`; 16 items each vary only the numbers + flags (`db/cars.mjs`).

## How to reapply
1. **Fix ONE coordinate convention** and write it in a comment; add a helper (like `X(f)`) that expresses
   positions relative to the product's own dimensions, so the same shape scales.
2. **Model the dominant profile as a `THREE.Shape`** and `extrudeZ` it; translate to center on the minor
   axis — never `.center()` (that desyncs the add-ons).
3. **Define materials once**, reuse everywhere; make the one recolorable surface a `MeshPhysicalMaterial`
   and return a `setPaint` closure over it.
4. **Add features as flags** (`if (shape.wing === 'gt') …`), positioned against the same origin, so one
   builder covers the whole product family.
5. **Return `{ group, setPaint, wheels }`** (or your moving parts) so the turntable studio can spin and
   repaint it with no special-casing.

## Gotchas (from the code)
- **`.center()` is the trap.** Once you center the extruded body, every hand-placed add-on is off by half
  the width/length. Translate the geometry instead and keep a single origin (`carBuilder.js:9,32-34`).
- **Bevel the extrude** (`bevelEnabled`, small `bevelThickness/Size`) or edges look like folded cardboard;
  `computeVertexNormals()` after (`carBuilder.js:27-34`).
- **Lights that should glow need `emissive` + `emissiveIntensity`**, not just a bright color
  (`carBuilder.js:129-136`).
- **Feature flags must be exhaustive per family** — an unhandled `wing`/`exhaust` value silently renders
  nothing; default the `else` branch (`carBuilder.js:166,180`).
- This is the **interactive** ceiling, not photoreal — a live, orbitable procedural mesh is deliberately
  stylized; for photoreal go to a real .glb via gltf-draco-model-normalizer (README `:16-20`).
