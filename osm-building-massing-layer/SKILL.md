---
name: osm-building-massing-layer
description: >-
  Turn a bounded map area into REAL 3D building massing — footprint polygons with per-building
  heights — pulled from OpenStreetMap via one bounded Overpass query, parsed to plain GeoJSON, with
  an HONEST per-building height-provenance ladder (measured tag → est tag → levels×storey → per-type
  default → flat default) so a render can legend which heights are measured vs estimated. Renderer-
  AGNOSTIC: the output is GeoJSON you point at ANY 3D globe/map (deck.gl, Three.js, MapLibre,
  Cesium, a canvas fallback). Use WHENEVER a client build needs to show a place in 3D or draw real
  buildings on a map — a real-estate / neighborhood / venue / city / "explore this area" dashboard,
  a site whose hero is the town's own skyline, or any "put real buildings on the map / show the
  massing / 3D footprints for this address" request. It is the 3D-HEIGHT layer specifically: it
  COMPLEMENTS overpass-query-hardening (that hardens the raw Overpass CALL — reuse it, do not restate
  its four lessons here), offline-osm-basemap-map (that renders a FLAT branded basemap with 2D
  footprints — this adds real height/extrusion on top), and geo-directory-prospecting (business POIs,
  "who is here" — this is "what the built form looks like"). Reuses ssrf-safe-egress-transport /
  connector-egress-circuit-breaker for the fetch and hands its GeoJSON to media-generation-dispatch or
  any WebGL renderer for the actual 3D. Guardrails: bounded bbox + response cap, PURE parse (Overpass
  JSON in → GeoJSON out, no network/clock in the parser), hostile-tag height clamp, drop-don't-invent
  geometry, ODbL attribution on every feature.
---
# OSM Building-Massing Layer

## What it is / when to use / composes with
A **pure data-extraction seam** that converts a bounding box into a governed GeoJSON layer of building
footprints, each carrying a height and the *provenance* of that height. It exists because a place only
looks like a place when you have its **buildings** — footprints with heights — and OSM has that data for
free (ODbL, commercial-clean with attribution) if you query it in a bounded, honest way.

Use it when a client build must render a real location in 3D or draw real buildings on a map. It is the
**data** half of a geo dashboard; the **render** half is whatever 3D engine the client already uses. Keep
those two halves separate — this skill never owns the renderer.

- **Composes with `overpass-query-hardening`** — that atom owns the raw-call battle scars (coordinate
  rounding to 5dp so an egress firewall doesn't flag the digits, quoting QL keys/regex, one query in
  flight, injectable transport). Reuse it for the *fetch*; do NOT restate those lessons here. This skill
  is only the parse-and-derive-height layer that sits on top.
- **Complements `offline-osm-basemap-map`** — that renders a branded FLAT basemap (canvas/svg or
  maplibre-gl) and draws buildings as 2D footprint fills. This skill adds the third dimension: the same
  footprints carry a `heightMeters` so a 3D renderer can extrude them. Flat surface from that skill,
  real height from this one.
- **Complements `geo-directory-prospecting`** — that runs a vertical Overpass NWR query for business POIs
  (lead sourcing: name/address/website). This runs a `building=*` query for the built form. Same public
  source, orthogonal purpose; a dashboard often uses both (pins for businesses, massing for the skyline).
- **Reuses `ssrf-safe-egress-transport` / `connector-egress-circuit-breaker`** for the outbound Overpass
  call — resolve-then-pin the address, reject redirects to a new origin/private range, byte-cap the read.
  Do **not** invent a second fetch path.
- **Hands off to `media-generation-dispatch`** (or any WebGL turntable / globe) as the render engine seam.
  The parser output is renderer-agnostic GeoJSON; a client points deck.gl `PolygonLayer` (extruded by
  `heightMeters`), a Three.js extrude, or a MapLibre `fill-extrusion` at it with zero parser changes.

## Reference implementation (TSS-own)
- `server/src/runtime/gods-eye-osm-buildings.ts:120` — `buildingsOverpassQuery(bbox, limit, date?)`: one
  bounded query for `way["building"]`, `relation["building"]["type"="multipolygon"]`, and
  `way["building:part"]` (Simple-3D-Buildings tower/podium heights), `out geom <limit>;` so geometry is
  inline (no second round-trip) and the response is size-capped. An optional validated `[date:"…"]` attic
  setting turns it into a **4D / time-travel** query ("this block as of 2015").
- `server/src/runtime/gods-eye-osm-buildings.ts:172` — `resolveHeight(...)`: the honest height ladder,
  best data first: measured `height`/`building:height` → `est_height` → `building:levels`(+`roof:levels`)
  × `METERS_PER_LEVEL` (line 37) → per-`building`-class default (`TYPE_DEFAULT_HEIGHT_M`, line 51) → flat
  default. Only the first branch is `'measured'`; every other tags a distinct `heightSource`.
- `server/src/runtime/gods-eye-osm-buildings.ts:154` — `parseMeters(...)`: reads "18", "18 m", "18.5m";
  **rejects** feet ("59'", "ft") rather than mis-reading as metres (falls through to an estimate).
- `...:163` — `clampHeight(...)`: floor/ceiling (2 m … 900 m) so a hostile/malformed tag (a 5000 m
  "building", a 0, a negative) can never produce absurd or invisible massing.
- `...:202` `closedRing` / `...:229` `outerRingOf`: build a closed footprint ring from a way, or from a
  multipolygon relation's `outer` members; **drop** geometry too thin to be a footprint — never pad with
  invented points.
- `server/src/runtime/gods-eye-osm-buildings.ts:262` — `parseOverpassBuildingsToGeoJson(response)`: the
  PURE transform (Overpass JSON in → GeoJSON `FeatureCollection` out, no I/O, no clock — unit-testable
  against a captured fixture). `metadata` carries `license`, `attribution`, `measuredHeights` /
  `estimatedHeights` counts for the legend, and `commercialOutputOk`.
- Sibling layers on the *same* bounded-Overpass→GeoJSON pattern, if a build needs more than massing:
  `gods-eye-osm-roads.ts` (road centerlines), `gods-eye-terrain.ts` (USGS heightfield),
  `gods-eye-submarine-cables.ts` (the base line/point layer the others were modeled on).

## How to reapply in a CLIENT build
1. **Geocode → bbox.** Turn the client's address/market into a `[south, west, north, east]` box (Nominatim,
   or reuse the geocode step in `geo-directory-prospecting`). Keep it city-block-to-district scale — Overpass
   is bbox-limited for a reason.
2. **Query + fetch through the governed lane.** Build the query with `buildingsOverpassQuery(bbox, limit)`,
   POST it to an Overpass endpoint through your SSRF-safe transport, byte-capped. Pass a `date` only if you
   want time-travel.
3. **Parse purely.** `parseOverpassBuildingsToGeoJson(json)` → GeoJSON. Ship the two counts to the UI as an
   honest legend: *"N buildings — M measured, K estimated."*
4. **Extrude in whatever renderer the site already has.** deck.gl `PolygonLayer({extruded:true, getElevation:
   f => f.properties.heightMeters})`, MapLibre `fill-extrusion` (`fill-extrusion-height` bound to the same
   field), or a Three.js `ExtrudeGeometry`. **Color by `heightSource`** so measured footprints read solid and
   estimates read tinted — the whole point is that the render never *claims* a height it didn't measure.
5. **Print the cite-line.** Every feature carries OSM/ODbL attribution; surface it (`© OpenStreetMap
   contributors, ODbL`) — required by the licence and the honesty contract.
6. **Cache a fixture for the demo.** For a repeatable client demo, commit ONE bounded Overpass response as a
   fixture and read it locally (see `single-source-data-embed`); the parser is pure, so the committed bytes
   render identically offline with no live pull.

## Gotchas
- **Bound the bbox and cap the response.** An unbounded `building=*` query will time out or return tens of MB.
  The `limit` on `out geom <limit>` and a byte-cap on the fetch are both load-bearing.
- **`building:part` without a real height is noise.** A pure part exists only to carry a tower/podium height;
  the reference parser drops a part whose height is only a default (it would just stack an overlapping slab).
- **Round coordinates you log/query for POIs to ~5 decimals.** Over-precise lon/lat has bitten adjacent geo
  code with false "looks like a card number" egress flags — a real gotcha when the same bbox drives an
  outbound scan. Massing geometry itself is fine at full precision; the caution is for anything you put on a
  URL or run through a data-leak scanner.
- **Height is metres by OSM convention; feet is dropped, not converted.** Don't add a guessed ft→m conversion —
  the estimate ladder is more honest than a wrong unit read.
- **Keep the renderer out of this skill.** The temptation is to bundle a specific globe. Don't — the value is a
  clean GeoJSON contract many renderers can consume; a bundled renderer makes it un-reusable.
