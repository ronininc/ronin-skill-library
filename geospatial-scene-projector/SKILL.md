---
name: geospatial-scene-projector
description: >-
  The seam that turns georeferenced building/road GeoJSON (lon/lat footprints + heights) into an
  engine-AGNOSTIC 3D SCENE: a local equirectangular projection onto a flat metric ground plane
  (bbox-centered, cos-latitude scaled, antimeridian-safe), a single fit-to-view (or real-metre)
  units-per-metre so the whole place auto-frames with faithful proportions, footprints EXTRUDED to
  grounded massing (full-ring prisms or one box per building), a PBR façade material chosen from the OSM
  class + height (glass/concrete/brick/metal/stone, with estimated heights honestly desaturated), roads as
  ground ribbons under the same projection, and a camera dolly PATH resampled along the longest street.
  Output is plain scene data (positions/scales/footprints/materials/camera path) you hand to ANY offline or
  scene renderer — Three.js, Blender, Godot, or a cloud render/gen API. Use WHENEVER a build must take map
  data the final step into a rendered 3D scene, flythrough, or hero render of a real place — "make a 3D
  scene / flythrough of this neighborhood", "render the town skyline", "put the block in Blender/Godot",
  "a camera move down the main street". It is the STEP AFTER osm-building-massing-layer (which SOURCES the
  GeoJSON + height provenance) and is for SCENE/offline renderers that need a flat centered metric space +
  a camera — NOT for web-mercator map libs (deck.gl/MapLibre extrude lon/lat GeoJSON directly; use
  osm-building-massing-layer + offline-osm-basemap-map there). COMPLEMENTS media-generation-dispatch (this
  produces the scene an engine renders), parametric-3d-model-builder (per-building mesh detail),
  webgl-product-turntable-studio (single-object studio), and webgpu-image-finish-pass (grade the rendered
  frame). Pure: GeoJSON in, scene out — no network, no clock, no renderer bundled.
---

# Geospatial Scene Projector

## What it is / when to use / composes with
`osm-building-massing-layer` gives you GeoJSON footprints with heights and a measured/estimated `heightSource`
— but still in **lon/lat**, still a **2D footprint + a number**. A web-mercator map library (deck.gl,
MapLibre, Cesium) extrudes that directly and needs nothing more. But a **scene renderer** — Three.js, a
headless Blender/Godot lane, or a cloud render/gen API — needs the data taken the last step: lon/lat
flattened onto a **centered metric ground plane**, one **units-per-metre** so the place fits the view with
faithful proportions, footprints **extruded to grounded massing**, façades given a **material**, and a
**camera path** to move through it. This skill is that step — a pure `GeoJSON → scene` transform with the
renderer kept out, so the same scene feeds Three.js, Blender, Godot, or a cloud engine unchanged.

Composes with: **osm-building-massing-layer** (its GeoJSON + `heightSource` is this skill's input — do not
re-source here), **media-generation-dispatch** (this builds the scene an engine renders to video/stills),
**parametric-3d-model-builder** (swap a prism for a real per-building mesh on the same footprint),
**webgpu-image-finish-pass** (grade the rendered frame), **offline-osm-basemap-map** (the flat 2D map
alternative when no 3D scene is wanted).

## Reference implementation (TSS-own)
All in `server/src/runtime/geospatial-scene-adapter.ts` — a pure module (GeoJSON in, scene data out, no I/O,
no clock; the whole point is that it's deterministically testable with fixtures):

- **Local equirectangular projection to a metric scene ground** — the load-bearing seam:
  - `referenceOrigin(pairs)` `:144-156` — the projection reference is the collection's own bbox CENTER
    (scene centered on the evidence, not the globe origin); longitude is resolved in circular space so a
    collection straddling the antimeridian measures as its true narrow span.
  - `wrappedLonDelta(lon, ref)` `:130-135` — shortest signed angular delta, wrapped to (-180,180], so
    ±179°-adjacent features don't balloon to a ~358° span (bit-identical to plain subtraction elsewhere).
  - `projectToSceneGround(lon, lat, origin)` `:164-169` — `[lon,lat] → [x,y]` with longitude scaled by
    `cos(reference latitude)` so scene units-per-real-distance match on both axes near the reference. No
    projection library, no network — a pure function of the input, accurate at sub-continental bbox scale.
  - `flattenLonLatPairs(coords)` `:108-112` — recursively pulls `[lon,lat]` pairs out of ANY GeoJSON
    geometry (Point/Line/Polygon/Multi*), dropping malformed/out-of-range pairs (never guessed).
- **Fit-to-view (or real-metre) scaling** — `cityFromLayers(layers, opts)` `:541-625`: projects the UNION of
  building + road coords, finds the real half-extent, and picks ONE `unitsPerMeter =
  TARGET_HALF_FOOTPRINT / halfExtent` (or `1` in `realMetres` mode for co-registration with real-metre
  tiles) that governs footprint size, height, AND road width together — so proportions stay faithful and
  the scene auto-frames. Keeps every footprint ring and road vertex (fit-to-view bounds the VIEW, not the
  data). `originLonLat` forces a shared origin so several layers co-register.
- **Extrude to grounded massing**:
  - `sceneObjectsFromBuildings(collection)` `:380-432` — one axis-aligned BOX per building (bbox +
    height), `position.z = halfHeight` so the base sits on `z=0` even after a clamped height (a clamped
    tower stays grounded, never floats/sinks). Fit-to-view scale + `WORKER_MIN/MAX` clamps bound the output.
  - `cityFromLayers` (above) keeps the **full footprint polygon** per building for a true-silhouette
    extrude, plus roads as ground ribbons `widthUnits` by class, under the one shared projection.
- **Honest PBR façade material** — `buildingMaterial(class, heightM, measured)` `:464-481`: OSM building
  class + height → glass/concrete/brick/metal/stone (`color`+`metallic`+`roughness`); a tall building reads
  as glass regardless of tag; an ESTIMATED height is pulled 18% toward neutral grey + slightly more matte —
  an honest "we inferred this one" cue that keeps the material family recognisable. Class regexes `:456-459`.
- **Camera dolly path** — `cameraPathFromCity(city, samples)` `:779-792`: pick the LONGEST road polyline and
  arc-length-resample it to N points — a ready camera track down the main street.
- **Budget guards** (bound one scene) — `subsampleVertices` `:173-178` (even subsample of a long route,
  keeping endpoints), `normalizeMaxVerticesPerLine` `:79-84` (clamps a hostile per-line cap; the NaN/Infinity
  fix), `MAX_OBJECTS_PER_COLLECTION` `:67`.
- **Deterministic library-asset placement (optional upgrade)** — `server/src/runtime/render-asset-placement.ts`:
  `assignBuildingAssets(city)` `:82` stamps a real `.glb` onto each footprint chosen by a stable FNV-1a hash
  of the building identity (`hashString` `:19-24`), with an HONEST fallback to the prism when the library is
  empty — same city always maps to the same meshes (reproducible), never invents a mesh it doesn't have.

## How to reapply in a CLIENT build
1. **Source the GeoJSON.** Use `osm-building-massing-layer` (bounded Overpass → footprints + `heightMeters` +
   `heightSource`) for the buildings, and its road-centerline sibling for streets. Do not re-source here.
2. **Project once.** Compute `referenceOrigin` over the union of all coords, then map every vertex with
   `projectToSceneGround` (or `cityFromLayers`' `toMeters`). Now you are in a flat, centered metric plane a
   scene renderer understands (Z-up in the reference; use Y-up and swap axes for Three.js/glTF).
3. **Pick one units-per-metre.** Fit-to-view for a framed hero (`TARGET_HALF_FOOTPRINT / halfExtent`), or
   `realMetres:true` (=1) when you must co-register with real-metre 3D-Tiles/photogrammetry — then pass that
   same `originLonLat` to both.
4. **Extrude.** Full footprint rings → `THREE.ExtrudeGeometry` / a Blender/Godot mesh per building, height =
   `heightMeters × unitsPerMeter` (clamped, base on the ground). Or one box per building for a fast schematic.
5. **Material + honesty.** Apply `buildingMaterial`; color/tint estimated buildings distinctly and surface the
   measured/estimated counts as a legend — carry the ODbL attribution from the source layer through.
6. **Camera.** `cameraPathFromCity` → a dolly track; point the camera along the tangent, lift it a few units,
   and you have a main-street flythrough with zero manual keyframing.
7. **Hand to the renderer.** The output is plain data — feed Three.js in the browser, a headless
   Blender/Godot lane, or a cloud render/gen engine via `media-generation-dispatch`. The skill bundles no
   renderer, so it never locks the build to one.

## Gotchas
- **This is NOT for web-mercator map libs.** deck.gl `PolygonLayer{extruded}` / MapLibre `fill-extrusion`
  already project lon/lat and extrude by a height field — projecting to a flat metric plane first would fight
  their coordinate system. Use this only for SCENE renderers (Three.js scene, Blender, Godot, cloud) that
  want a centered metric space + a camera. For a flat branded map use `offline-osm-basemap-map`.
- **The projection is local and bounded.** Equirectangular-about-a-point is accurate at city-block-to-district
  bbox scale (what these scenes draw); it is NOT a global projection — do not feed it a continent-spanning
  collection and expect true distances.
- **Antimeridian + poles.** `wrappedLonDelta` handles the ±180° seam; the `cos(lat)` scale degenerates near
  the poles (guarded to `1`). Fine for populated places, not for polar scenes.
- **Height provenance must survive to the render.** The whole honesty contract is that the render can show
  which heights were measured vs estimated — keep `heightSource`/`measured` on the building through extrusion
  and color by it (`buildingMaterial` already does).
- **Clamp hostile geometry.** Keep the height floor/ceiling and the per-line + per-collection vertex budgets;
  one bad OSM tag or a giant multipolygon must not spear the sky or blow the object budget.
- **Axis convention.** The reference is Z-up worker space (`position[2]` = height). Three.js/glTF are Y-up —
  swap when you emit, or you get a city lying on its side.

## Deliberately EXCLUDED (do not extract)
- The **OSM sourcing / governed egress** (bounded Overpass, SSRF-pinned fetch) — already owned by
  `osm-building-massing-layer` + `overpass-query-hardening` + `ssrf-safe-egress-transport`; this skill starts
  from GeoJSON.
- The **headless Blender/Godot render + export runtime** (`godot-render-lane.ts`, `godot-export-lane.ts`,
  `godot-city-flythrough.ts`, the Blender worker + Titan media production) — that is a local
  8GB/Metal hardware runtime tuned to one machine, not a portable client pattern. Point the scene at a
  pluggable renderer or a cloud engine instead.
- The **voice-request → SceneSpec provenance loop** (`codegen-scene-spec.ts`) — coupled to the private
  spoken-media pipeline, not client scene assembly.
