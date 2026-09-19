---
name: overpass-query-hardening
description: >-
  The battle-scars atom for talking to a public OpenStreetMap Overpass endpoint from a client
  build WITHOUT tripping the failure modes that make the feed silently come back empty. Four hard
  lessons, extracted as reusable plumbing: (1) ROUND bbox/point coordinates to ~5 decimals before
  they enter the query — raw float math emits 14-decimal digit runs that a Luhn/"CARD_LIKE" egress
  firewall flags as a card number and fail-closes the whole call; (2) QUOTE every Overpass-QL key
  and regex value (`"amenity"~"cafe|bar"`) — an unquoted regex selector yields HTTP 400; (3) keep
  exactly ONE query in flight (a client-side ref guard for React StrictMode double-mounts + rapid
  taps, and server-side SEQUENTIAL fetches) — the free Overpass tier rate-limits parallel calls
  from one origin and returns empty; (4) fetch through an INJECTABLE JSON transport so the parse is
  hermetically testable and so egress can be SSRF-guarded/pinned by the host build. Use WHENEVER a
  build issues Overpass QL directly — a "businesses near here" POI feed, a surveillance/camera
  layer, a buildings/roads pull, or a basemap bake. COMPLEMENTS geo-directory-prospecting (the
  lead-SOURCING workflow that USES Overpass): that skill owns geocode→query→dedupe→rank; THIS skill
  is the reusable query-client hardening any Overpass call needs, and pairs with
  offline-osm-basemap-map (which renders what the query returns) and ssrf-safe-egress-transport
  (the pinned fetch lane this injects). Public OSM/ODbL data only; honest-empty on failure, never
  fabricate features.
---
# Overpass Query Hardening

## What it is / when to use
A small set of **defensive conventions for issuing OpenStreetMap Overpass-QL queries** that turn a
flaky, silently-empty integration into a reliable one. It is NOT a workflow and NOT a renderer — it
is the query-client layer that sits under any feature that reads OSM: a nearby-POI feed, a
public-infrastructure layer (ALPR cameras, hydrants), a road/building pull, or a one-shot basemap
bake. Reach for it the moment a build writes `data=` + Overpass QL and POSTs it to
`overpass-api.de/api/interpreter` (or a self-hosted mirror).

The four hardening rules, each a real bug that cost a debugging session:

1. **5-decimal coordinate rounding** — a firewall false-positive guard, not cosmetics.
2. **Quoted keys + regex values** — unquoted regex = `HTTP 400`.
3. **One query in flight** — free-tier rate-limit protection, client and server side.
4. **Injectable JSON transport** — testability + SSRF-guarded egress owned by the host.

**Composes with:** `geo-directory-prospecting` (the lead-sourcing engine that calls Overpass — it
references these gotchas in prose; this skill is the extracted, reusable client so a NON-sourcing
feature gets the same hardening), `offline-osm-basemap-map` (renders Overpass results as a dark
map), `ssrf-safe-egress-transport` / `connector-egress-circuit-breaker` (the governed, pinned fetch
lane you inject as the transport). Do NOT reimplement geo-directory-prospecting's geocode/dedupe/
rank here — this skill stops at "get clean bytes back from Overpass".

## Reference implementation (TSS-own)
- **5-decimal coord rounding + the WHY** — `server/src/runtime/map-opportunity-feed.ts:46-57`
  (`bboxAround()`): computes a metre-radius bbox then rounds every corner with
  `Math.round(n * 1e5) / 1e5`. The comment (L46-51) is the load-bearing lesson: raw
  `radiusM / 111320` yields tails like `33.41754222062522`, whose bare 14-digit run can be
  Luhn-valid and trip an egress firewall's `CARD_LIKE` guard, fail-closing the whole feed; a
  5-decimal coord (~1.1 m, far finer than a POI scan needs) cannot form a 13+ digit run, so the
  query stays clean while the firewall stays strict.
- **Quoted key + quoted regex value** — `server/src/apps/leadengine/discovery.ts:44-63`
  (`normSelector()` + `overpassQuery()`): `normSelector` turns `amenity~cafe|bar` into
  `"amenity"~cafe|bar` and a bare `shop` into `"shop"`; the query builder wraps each selector as
  `node[<norm>](bbox); way[<norm>](bbox);`. The convention that regex VALUES are also quoted
  (`amenity~"restaurant|cafe|bar"`) is stated at `server/src/runtime/map-opportunity-feed.ts:16-25`
  (`MAP_FEED_SELECTORS`) — an unquoted regex value emits invalid QL and Overpass returns 400.
- **Client-side single-in-flight guard** — `app/src/dashboard/components/SolomonOpportunityMap.tsx:34-65`:
  a `useRef(false)` gate (`inFlight`) at the top of the async loader — `if (inFlight.current) return;`
  then `inFlight.current = true;` … `finally { inFlight.current = false; }`. The comment (L34-36)
  names the two triggers it defends against: React StrictMode's double-mount and rapid re-taps,
  either of which fires two Overpass POSTs at once → rate-limited → empty.
- **Server-side sequential fetches** — `server/src/runtime/crm-wall-basemap.ts:465-469`: four
  Overpass queries run with `await` one after another, with the comment
  `// Sequential on purpose — Overpass rate-limits parallel queries from one origin.`
- **Injectable transport + honest-empty** — `server/src/apps/leadengine/discovery.ts:19-33`
  (`JsonFetcher` type + `governedJsonFetch` default) and
  `server/src/runtime/deflock-alpr-map.ts:38-85` (a second, independent client: injectable
  `AlprFetcher`, a bounded `out body <CAP>` query, and a failed/blocked fetch → `null` → an honest
  "none mapped here" rather than a thrown error or faked rows).

## How to reapply it in a CLIENT build
1. **Never let raw float coords into the query.** Add one rounding helper and call it on every
   bbox corner and point before it becomes query text:
   ```ts
   const r5 = (n: number) => Math.round(n * 1e5) / 1e5;
   function bboxAround(lat: number, lng: number, radiusM: number): [number, number, number, number] {
     const dLat = radiusM / 111_320;
     const dLng = radiusM / ((111_320 * Math.cos((lat * Math.PI) / 180)) || 1);
     return [r5(lat - dLat), r5(lng - dLng), r5(lat + dLat), r5(lng + dLng)];
   }
   ```
   Do this even if the build has no egress firewall today — it also keeps the query short and
   cache-friendly, and the firewall may be added later.
2. **Normalize every selector through a quoter.** Copy `normSelector` verbatim; author selectors as
   `key` or `key~"a|b|c"` (regex value in quotes) and build clauses as
   `node[<norm>](bbox); way[<norm>](bbox);`. If you also need relations, add `relation[<norm>](bbox);`.
   Prefer `out center tags <limit>;` for POIs (gives a single centroid per way) and `out geom;` when
   you need full geometry (roads, footprints).
3. **Gate to one call in flight.** In a browser/React caller, use the `useRef(false)` guard pattern.
   On a server that fires several queries for one result, `await` them sequentially — do NOT
   `Promise.all` Overpass. Bound every query's output with a cap (`out ... <N>;`).
4. **Inject the transport.** Type the fetch as
   `(req: {url; method?; body?; headers?; reason?}) => Promise<{ok; status; json?; error?}>` and take
   it as a parameter defaulting to your governed lane. This makes the parse unit-testable with a
   canned Overpass JSON blob (zero network) AND lets the host enforce SSRF pinning / online-mode on
   the real path. POST the query as `data=` + `encodeURIComponent(query)` with
   `content-type: application/x-www-form-urlencoded`.
5. **Set etiquette headers.** A descriptive `User-Agent` and a contact `email=` (Nominatim) or in
   the query per each public instance's usage policy; treat 429/timeouts as an honest coverage note,
   not an exception — return what you have and say the feed was partial.

## Gotchas
- **The CARD_LIKE trap is invisible.** When it fires, the query never leaves the machine and the
  endpoint is blameless — you see an empty feed with a 200-ish transport but no elements. If a
  location feed is mysteriously empty only for *some* coordinates, suspect an un-rounded coord
  before you suspect Overpass. Rounding to 5 decimals is the fix; do not "fix" it by loosening the
  firewall.
- **400 from Overpass is almost always quoting.** `key~a|b` (unquoted) 400s; `key~"a|b"` works.
  `key=value` needs quotes too (`"amenity"="cafe"`). One bad selector fails the whole compound query.
- **StrictMode will double-fire in dev.** Without the in-flight ref you will chase a "works in prod,
  empty in dev" ghost; it is the double-mount issuing two POSTs the free tier rate-limits.
- **Parallel = rate-limited.** `Promise.all` of several Overpass queries from one origin gets one or
  more rejected; the result looks like partial data, not an error. Sequential `await` is the trade
  you make for a free endpoint.
- **Nominatim boundingbox order differs.** Nominatim returns `[south, north, west, east]`; Overpass
  bbox filters want `(south, west, north, east)` — reorder (see `discovery.ts:88-90`).
- **Honest-empty, never fabricate.** Absence in OSM is not proof of absence in the world; a
  blocked/failed fetch must yield an empty result + a coverage note, never invented features to hit
  a target count.
