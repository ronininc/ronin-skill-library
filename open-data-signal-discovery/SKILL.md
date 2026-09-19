---
name: open-data-signal-discovery
description: >-
  A government/open-data ingestion spine that surfaces FRESH buying signals — a new business license, a
  pulled building permit, a just-formed entity — before anyone cold-calls the business. A reviewed
  Socrata source catalog drives a cursored, keyset-paginated SoQL puller (every identifier in the query
  comes ONLY from the allowlist, never from a request — injection-safe), plus an R2 NDJSON bulk path
  for datasets a Worker can't fetch directly (Overture/Foursquare/ROC), all upserting into a
  businesses + time-stamped signals model deduped by a SHA-256 place-key. Use WHENEVER a lead-gen CRM
  should "find new/just-opened businesses", "watch permits/licenses/entity formations", "ingest city
  open data", "Socrata / data.gov feeds", "surface buying-signal leads", or "who just got a permit".
  COMPLEMENTS crm-build-standard (the CRM the signals feed) and data-feed-intake (generic feed
  plumbing) — this is the open-data-specific catalog + SoQL cursor + place-key dedup on top; and it
  pairs with geo-directory-prospecting (map-sourced prospects) as a second, event-driven source lane.
  CRITICAL CAVEAT — this ships COMPLETE and migration-backed but DISCONNECTED from cron/router in the
  source (index.ts:183-185); the skill body includes the exact bindings, routes and cron wiring it
  needs. Injection-safety (allowlist-only identifiers) is the load-bearing guardrail — never relax it.
---
# Open-Data Signal Discovery

## What it is / when to use
An event-driven lead source. Instead of scanning a map for who exists, it watches public government
datasets for **something that just changed** — a license issued, a permit pulled, an LLC formed — and
lands each as a timestamped `signal` attached to a deduped `business`. Those fresh signals are the
highest-intent leads a local-services CRM can get. Use it as a second sourcing lane alongside
map-based prospecting.

**Composes with:** `crm-build-standard` (stores/scores what this surfaces), `data-feed-intake` (generic
intake patterns — this is the open-data specialization), `geo-directory-prospecting` (complementary
map lane), `contact-enrichment-deliverability` + `website-need-scorer` (the downstream stages that turn
a raw `business` row into a contactable, prioritized lead — the whole Phase 1-3 spine chains). This
skill owns **catalog + cursored ingestion + place-key dedup only**; it does not enrich, score, or send.

## Reference implementation (ronininc)
All confirmed read. Files under `worker/discovery/`:
- `catalog.ts` (~222 lines) — `DiscoverySource`/`SourceFields` types + `DISCOVERY_SOURCES` array. Each
  entry is deliberately explicit: `domain/datasetId/dateField/idField/where/fields`. **The comment at
  L39-40 is the whole security model:** "identifiers used in generated SoQL come only from this reviewed
  list, never from an API request." Kinds: `socrata` (live pull), `bulk-download` (disabled; origin
  blocks Workers), `r2-ndjson` (off-edge-prepared).
- `socrata.ts` (~196 lines) — `ingestSocrataSource()` L124-195: reads the saved cursor, builds the SoQL
  URL (`queryUrl()` L94-114), pages ≤1000 rows, normalizes each (`normalize()` L43-67 via `readPath`
  dotted-path resolver), stores, advances the cursor. `quote()` L18 is the ONLY value that gets
  interpolated and it's single-quote-escaped; field/dataset identifiers are never interpolated from
  input. Keyset pagination: `(dateField > D OR (dateField = D AND idField > tiebreak))` ordered
  `dateField ASC, idField ASC` — stable across pages, no OFFSET drift.
- `store.ts` (~111 lines) — `storeBusinessSignal()` L54-110: computes a `placeKey` =
  `SHA-256(normalizedName | lat,lon@4dp || address|city|state)` (`placeKey()` L40-52), upserts
  `businesses ON CONFLICT(tenant,place_key)` with COALESCE-keep-existing on every field, and
  `INSERT OR IGNORE` into `signals` (UNIQUE tenant/source/external_id/event_date). Returns true only
  when a NEW signal row was written — so replays are idempotent.
- `service.ts` (~87 lines) — `runSocrataDiscovery()` (wraps one source in a `discovery_runs` row),
  `runDiscoveryTick()` L36-51 (the cron entry: runs ONE due source per tick, cadence-gated), and
  `discoveryStatus()` / `triggerSocrataDiscovery()` (admin surfaces). Strips `fields` from the status
  payload so the reviewed catalog internals aren't exposed.
- `r2-import.ts` (~185 lines) — `OpenDataImportWorkflow`: streams an NDJSON object from R2 in 512 KB
  ranges, carries the partial trailing line between chunks (base64), enforces the object is under its
  source's reviewed `r2Prefix` (L88, L162), and stores each line via the same `storeBusinessSignal`.
- Schema: `migrations/0008_discovery_catalog.sql` — `lead_tenants`, `businesses`, `signals`,
  `source_cursors`, `discovery_runs`.

⚠️ **DISCONNECTED in source.** `index.ts:183-185` states it outright: "The unfinished catalog/R2/KV
discovery spine remains disconnected until its bindings and D1 migrations are explicitly provisioned."
Verified: `OPEN_DATA` (R2) and `OPEN_DATA_IMPORT` (Workflow) are typed in `Env` (`types.ts:68,75`) but
absent from `wrangler.jsonc`; no cron calls `runDiscoveryTick`; no admin route reaches
`triggerSocrataDiscovery`/`discoveryStatus`/`triggerR2Import`. The code is done; the wiring is not.

## How to reapply it
1. **Schema.** Apply `0008` (creates the tenant/businesses/signals/cursors/runs tables + indexes). This
   is the shared substrate for contact-enrichment-deliverability (`0009`) and website-need-scorer
   (`0010`) — apply all three if you want the full lead-refinement chain.
2. **Curate the catalog.** Replace `DISCOVERY_SOURCES` with the client's jurisdictions. For each Socrata
   dataset, open its Socrata page, copy the real column API names into `fields`, set `domain/datasetId/
   dateField/idField`, an optional `where` (e.g. `record_status='Active'`), and `initialLookbackDays`.
   **Only add identifiers you've reviewed** — they go straight into SoQL.
3. **WIRE IT (the missing half):**
   - `wrangler.jsonc`: add R2 `{ binding:"OPEN_DATA", bucket_name:... }`, the Workflow
     `{ binding:"OPEN_DATA_IMPORT", class_name:"OpenDataImportWorkflow" }`, and `export {
     OpenDataImportWorkflow }` from the entry.
   - Cron: add `runDiscoveryTick(env)` to the `scheduled()` batch (it self-limits to one due source per
     tick, so it's cheap and stays inside CPU limits).
   - Admin routes: `POST discovery/socrata → triggerSocrataDiscovery`, `GET discovery/status →
     discoveryStatus`, `POST discovery/r2-import → triggerR2Import`.
   - Optional secret `SOCRATA_APP_TOKEN` (raises Socrata rate limits; the code sends it as `X-App-Token`
     when present, works without).
4. **Bulk / R2 lane.** For datasets a Worker can't fetch (Cloudflare-challenged origins, huge dumps),
   prepare NDJSON off-edge (DuckDB for Overture/Foursquare, a browser download for ROC), upload under
   the source's `r2Prefix`, then POST `discovery/r2-import`. Credentials for those sources never enter
   the Worker repo.
5. **Chain downstream.** New `businesses` land with `enrichment_status='pending'` /
   `need_probe_status='pending'` — wire contact-enrichment-deliverability and website-need-scorer to
   pick them up and refine them into contactable, ranked leads.

## Gotchas (from the code + comments)
- **Injection safety is the whole design.** Field, dataset, date and id identifiers come ONLY from the
  reviewed catalog — never from a request body. `triggerSocrataDiscovery` accepts only a `source_id`
  that must match an enabled catalog entry. Never let a caller pass raw SoQL, a column name, or a
  dataset id. `quote()` escapes the one interpolated *value* (the cursor). Don't add a code path that
  interpolates anything else.
- **Keyset cursor, not OFFSET.** The `(date > D OR (date = D AND id > tiebreak))` pattern needs a stable
  `dateField ASC, idField ASC` order; if a dataset has no reliable monotonic id, pagination can loop or
  skip. Pick `idField` carefully.
- **Place-key collisions/misses.** Dedup rounds lat/lon to 4 decimals (~11 m) and strips corporate
  suffixes from the name; two distinct suites at one address without coords can merge, and a renamed
  business gets a new key. It's a heuristic, tuned to avoid duplicate outreach, not a legal identity.
- **R2 chunk boundary bug class:** `r2-import` splits on the last `\n` in each range and carries the
  remainder; a single NDJSON row larger than ~2×512 KB throws by design (L115) rather than silently
  truncating. Keep rows small.
- **Business facts only.** The schema intentionally stores no protected-person attributes (comment in
  `0008`). Keep it that way — this is a lawful-open-data spine, not a people database.
- **It does nothing until wired.** The single most common mistake is assuming this runs because the code
  is present. It is inert until step 3.
