---
name: offline-osm-basemap-map
description: >-
  Build a dark, game-styled OpenStreetMap ops/status map for a CRM or dashboard WITHOUT a paid map
  SDK or per-tile bill — pins that carry a state color, a tap-to-filter legend, a click-to-open
  detail card, and license attribution drawn on the map. Two interchangeable rendering paths under
  one look: (A) LIVE-TILE — maplibre-gl (open-source) over the free OSM raster tiles, recolored to
  a dark/neon theme with a single CSS `filter:` "vanta" pass plus horizon/tint/grain/vignette
  overlays and custom HTML-element markers (drag/zoom/roam, needs network for tiles); (B)
  OFFLINE-BAKED — commit a size-budgeted OSM GeoJSON asset ONCE (roads/water/boundaries/building
  footprints simplified with Douglas-Peucker + coordinate quantize + same-class chain-joining),
  paint it on a `<canvas>` and overlay pins/labels on an `<svg>` that SHARE ONE lon/lat→x/y
  projection, and never fetch tiles at runtime (fully offline, refresh is an explicit operator
  command with a staleness line). Use WHENEVER a build needs a branded map surface: a "map of our
  customers/sites/leads", an ops/status wall, a store locator, a territory/coverage view, or a
  location answer that must look designed rather than default-Google. COMPLEMENTS
  geo-directory-prospecting + overpass-query-hardening (they SOURCE and HARDEN the OSM query; this
  RENDERS the result), crm-build-standard / commerce-spine (the records whose locations become
  pins), and portal-design-system / white-label-branding (swap the palette to the client's brand).
  Public OSM data, ODbL — attribution is a license condition and is rendered on the map. NOT a
  3D globe (that is a separate Cesium/WebGL concern) and NOT a paid provider (Mapbox/Google) wrapper.
---
# Offline OSM Basemap Map

## What it is / when to use
A recipe for a **designed, dark map surface** driven by OpenStreetMap data, with zero dependency on
a metered map provider. It gives you: a themed basemap, markers whose color encodes a per-record
state (with a pulse for alert states), a legend that doubles as a filter, a detail card on click,
and on-map license attribution. Use it for any "put our things on a map" surface in a client CRM,
ops dashboard, store locator, or territory view.

Pick the rendering path by whether runtime network is acceptable:

- **Path A — LIVE-TILE (maplibre + OSM raster + CSS vanta).** Fastest to stand up, supports
  drag/rotate/zoom/roam over the whole planet, but fetches raster tiles at runtime from
  `tile.openstreetmap.org`. Recolor the default OSM tiles to your dark/neon theme with a single CSS
  `filter:` on the canvas — no custom tile server, no style JSON beyond the raster source.
- **Path B — OFFLINE-BAKED (committed GeoJSON + canvas/SVG).** No SDK at all and no runtime tile
  fetch: a build step bakes a small OSM GeoJSON asset for your frame, you commit it, and the client
  paints it with plain `<canvas>` (geometry) + `<svg>` (pins/labels) sharing one projection. Choose
  this for an "offline-first", fixed-metro, or size/privacy-sensitive surface where you don't want
  every viewer hitting a tile CDN.

Both paths use the SAME palette-token + legend + pin conventions, so a build can start on Path A
and migrate the geography to Path B later without redesigning the chrome.

**Composes with:** `overpass-query-hardening` (harden the query that feeds either path),
`geo-directory-prospecting` (source the businesses that become pins), `crm-build-standard` /
`commerce-spine` (the location records), `portal-design-system` / `white-label-branding` (retheme
the palette tokens per client), `worker-media-headers` (serve the committed `.geojson` asset with
correct headers/caching).

## Reference implementation (TSS-own)
### Path A — live-tile maplibre + vanta filter
`app/src/dashboard/components/OpportunityMapView.tsx`:
- **Raster OSM style, no provider key** — L78-84: a maplibre `Map` with an inline style v8 whose
  only source is `{ type:'raster', tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
  tileSize:256, attribution:'© OpenStreetMap contributors' }`. `attributionControl:false` because
  attribution is rendered by the parent chrome.
- **The "vanta" recolor** — the CSS at L185 (`.sol-maplibre`):
  `filter: invert(0.92) hue-rotate(175deg) saturate(0.55) sepia(0.35) brightness(0.82) contrast(1.06);`
  turns the default light OSM raster into the dark gold-black theme with ONE line. Overlaid FX
  (L186-190): a `screen`-blend horizon gradient, a `multiply` tint, an SVG `feTurbulence` grain, and
  an inset box-shadow vignette — all `pointer-events:none`.
- **Custom HTML-element pins** — L99-107: build a `document.createElement('button')`, className by
  state (`sol-pin money|recharge` + `prime`), and add it as a maplibre `Marker` with
  `anchor:'bottom'`; a "you are here" pin at L95-97. Click flies to the pin and selects it.
- **Imperative flyTo handle** — L68-70 (`useImperativeHandle`), so a rail/list elsewhere can drive
  the map.
- **Legend as filter + detail popup** — the tap-to-filter legend rows live in the parent
  `app/src/dashboard/components/SolomonOpportunityMap.tsx:178-205`; the click-to-open detail popup is
  `OpportunityMapView.tsx:122-175`.

### Path B — offline-baked GeoJSON + canvas/SVG
Server bake — `server/src/runtime/crm-wall-basemap.ts`:
- **Overpass queries for the frame** — `basemapOverpassQueries()` L111-121 (roads by highway class,
  water + waterways, admin-level-8 boundaries, and building footprints only inside small declared
  "cluster" boxes so the asset stays under budget).
- **Geometry thinning** — `simplifyChain()` L158-179 (iterative, stack-based Douglas-Peucker),
  `quantizeChain()` L135-144 (round to 4 decimals ≈ 10 m; 5 for footprints), `joinRoadChains()`
  L206-242 (join contiguous same-class ways through degree-2 endpoints so a long arterial collapses
  to a few vertices), `stitchRings()` L379-403 (stitch boundary member-ways into closed rings, drop
  un-closable leftovers rather than lie about a border). Stated tolerances at L124-133.
- **Bake + IO + refresh seam** — `buildBasemapFromOverpass()` L247-374 emits a typed
  `FeatureCollection` with `metadata.attribution/license/refreshedAt/counts`;
  `readCrmWallBasemap()`/`writeCrmWallBasemap()` L418-439 (named `BASEMAP_ASSET_MISSING/CORRUPT`
  failures, not a throw); `refreshCrmWallBasemap()` L448-478 re-fetches sequentially and REFUSES to
  overwrite with an empty result (L472-475).
Client render — `app/src/dashboard/components/CrmCommandWall.tsx`:
- **One shared projection** — `toXY()` L112-116 maps lon/lat→x/y against a fixed `FRAME` and a
  `VIEW` viewBox; BOTH the canvas and the SVG use it so pins sit exactly on the geography.
- **Canvas painter, painted once** — `paintBasemap()` L135-226: DPR-aware sizing, `xMidYMid meet`
  letterboxing math (L143-149) mirrored by the SVG viewBox, then layers drawn in order
  boundaries→water→roads(casing then fill, minor classes first)→buildings. Repaint only on
  `ResizeObserver` (L300-308), never on data poll.
- **SVG overlay** — pins + city labels at L354-375; the `Marker` component L231-251 (circle for a
  record, diamond for an "active" one, a pulsing `<animate>` ring for alert states, white text halo
  via `stroke`+`paintOrder`).
- **Legend, attribution, staleness/refresh** — legend L378-395; on-map ODbL attribution + "Nd old —
  say refresh" line + refresh button L397-411; poll-only-when-visible so a hidden tab burns nothing
  L262-281.

## How to reapply it in a CLIENT build
1. **Define palette tokens once**, on the map root (CSS custom properties: ground/panel/line/ink +
   an accent per marker state). Both paths read the same tokens, so retheming = swap the tokens
   (pull them from `white-label-branding` for a client's brand).
2. **Path A (fastest):** add `maplibre-gl` (open-source), build a `Map` with the inline raster-OSM
   style above, set `attributionControl:false`, and add the CSS `filter:` vanta line on the map
   container — tune the `hue-rotate`/`sepia`/`brightness` for your accent. Add markers as HTML
   elements via `new Marker({element}).setLngLat([lng,lat])`. Draw the "© OpenStreetMap
   contributors" credit yourself in your chrome (license condition).
3. **Path B (offline):** write a build/refresh script that runs the four Overpass queries for your
   bounding box (harden them with `overpass-query-hardening`), thin the geometry with
   Douglas-Peucker + quantize + chain-join, and commit the resulting `FeatureCollection` (aim for a
   few MB — cap building footprints to downtown "cluster" boxes). At runtime read it ONCE, paint the
   geometry on a `<canvas>` and the markers/labels on an `<svg>` using ONE `toXY` projection against
   a fixed frame + viewBox. Never fetch at runtime; expose refresh as an explicit command and show a
   staleness line past N days.
4. **Markers encode state.** Map each record's status to an accent color; give alert states a pulse
   (CSS `@keyframes` on Path A, `<animate>` on Path B) and consider a second SHAPE (circle vs
   diamond) for a second dimension. Keep the legend and the pins using the exact same shapes/colors.
5. **Legend = filter.** Render legend rows as buttons that toggle a `{stateA:boolean,…}` filter;
   re-run the marker build on filter change (Path A) or conditionally render pins (Path B).
6. **Detail on click.** Selection is controlled by the parent so the same map can be driven from a
   list/rail; open a card/popup with the record's fields on marker click, close on map-background
   click.

## Gotchas
- **Attribution is not optional.** OSM tiles and derived geometry are ODbL — "© OpenStreetMap
  contributors" (plus your license line for baked data) must be visible ON the map, not buried in a
  footer. The baked asset carries it in `metadata` so the renderer can draw it.
- **Canvas and SVG must share ONE projection or pins drift.** Compute the same letterboxing offset/
  scale for the canvas that the SVG's `xMidYMid meet` viewBox uses (see `paintBasemap` L143-149);
  a mismatch puts every pin a few pixels off the road it belongs to, worst at non-16:9 panes.
- **Paint the basemap ONCE.** Repaint only on resize (ResizeObserver), never on the data poll —
  re-tracing thousands of vertices every 30 s tanks a low-power machine. Poll data only while the
  tab is visible.
- **The vanta `filter:` also inverts your overlays if you nest them.** Put FX layers and pins as
  SIBLINGS of the filtered tile canvas, not children, or they get recolored too.
- **Keep the baked asset small.** Full-metro building footprints blow a multi-MB budget instantly —
  restrict footprints to a handful of downtown cluster boxes where the eye lands; quantize roads/
  water to 4 decimals and boundaries harder (~120 m); drop ponds/sheds under an area threshold.
- **maplibre-gl is BSD/open-source (not Mapbox GL JS ≥ 2, which is proprietary).** Pin maplibre and
  the free OSM raster; do NOT pull a Mapbox/Google style or key — that reintroduces the metered
  provider this skill exists to avoid.
- **Free OSM tile usage policy.** The public `tile.openstreetmap.org` raster is fine for light/
  internal use; a high-traffic client surface should point Path A at its own/thirdparty tile host
  or move to Path B — don't hammer the free tiles in production.
