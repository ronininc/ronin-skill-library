---
name: single-source-data-embed
description: >-
  Author a dataset ONCE in a single source module, then a build step generates BOTH an embedded browser
  bundle AND the SQL seed for the backend — so the frontend and database can never drift, and the embedded
  copy doubles as a zero-backend offline fallback so the app still works with the DB down or opened as a
  plain file. Use WHENEVER a build has a curated dataset that must appear in both the client and a database
  (a catalog, a lineup, a menu, a directory, a set of records), or needs to "work even if the API/DB is
  down", "run as a static file", "keep the seed and the frontend in sync", "one source of truth for the
  data", or "degrade gracefully to embedded data". COMPLEMENTS d1-migration-recipes (schema/migrations —
  this generates the SEED + the client copy from one source), commerce-spine (its DB-is-source-of-truth
  catalog), and agnostic-import-parser (that INGESTS foreign data; this EMITS your own curated data to two
  targets). Not for user-generated/large data — this is for a hand-curated set that ships with the app.
---
# Single-Source Data Embed (+ zero-backend fallback)

## What it is / when to use / what it composes with
A tiny build discipline that removes a whole class of "the app shows different data than the database" bugs
and makes the backend optional. You write the dataset in one `.mjs` (or `.ts`) module — the ONLY place the
data lives — and a build script emits two derived, never-hand-edited artifacts: (1) a browser file that
assigns the array to a global (`window.DATA`), embedded in the page; (2) a `seed.sql` of `INSERT`s for the
Worker/DB. The frontend fetches the API first and **falls back to the embedded global** if the API is
missing or errors, so the toy/site always renders — the database is a pure enhancement, never a single
point of failure. Because the DB stores the record as JSON in one column, swapping D1↔Postgres is a
two-function change with no schema or frontend churn.

Composes with: **d1-migration-recipes** (owns the schema/migrations; this owns the seed + the embed),
**commerce-spine** / **crm-build-standard** (the DB brain that serves the API), **website-build-standard**
(the static host), and any studio/gallery skill that reads the dataset.

## Reference implementation — exact source
Repo: `~/Projects/clients/supercar-garage`.
- **The build step** — `db/build.mjs` (34 lines): imports the source array (`db/build.mjs:6`); writes the
  browser bundle `window.DATA = ${JSON.stringify(...)}` to `public/js/…js` (`:15-18`); generates the seed
  by mapping each record to an `INSERT`, with SQL-safe single-quote escaping via `q()` (`:21-25`), wrapped
  in a leading `DELETE FROM` so re-seeding is idempotent (`:27-30`).
- **The source of truth** — one module exports the array; the app and DB are always generated from it, so
  they can't drift (`db/cars.mjs:1-16`; header states the rule).
- **The schema** — JSON-in-a-column + a few scalar columns for cheap listing/ordering — `db/schema.sql`
  (`data TEXT` holds the full record; `id/name/…/sort` are the scalars). Same DDL is Postgres-valid.
- **The Worker read path** — `readCars`/`readCar` `SELECT data` then `JSON.parse` — `src/worker.js:21-32`;
  routes at `:39-49`; on any DB error it returns 503 **so the frontend can fall back** rather than 500ing
  the page (`:50-53`). The D1→Postgres swap is those two function bodies only (`:8-9`).
- **The frontend fallback** — fetch `/api/…`, and on non-OK/throw/empty return `window.DATA` —
  `public/js/app.js:15-21`.
- **The wiring that prevents drift** — npm scripts chain `build:data` before both `dev` and `deploy`, so
  you can't ship a stale embed/seed — `package.json:8-12`.

## How to reapply
1. **Put the dataset in one module** and export it; add a header banner marking it the sole source of
   truth. Nothing else edits the data.
2. **Write the build script** (`build.mjs`): emit `public/js/<name>.js` (`window.DATA = …`) and
   `db/seed.sql` (`DELETE FROM <t>;` + one `INSERT` per record, escaping quotes). ~30 lines.
3. **Schema**: `id` + a few scalar columns for listing + a `data TEXT` column holding `JSON.stringify`
   of the whole record. Worker reads `data` and `JSON.parse`s it.
4. **Frontend**: `fetch(api)` → on failure/empty use `window.DATA`. Include the generated `<script>` embed
   in the page.
5. **Wire the build into `dev`/`deploy` scripts** so the two artifacts regenerate every run — never commit
   a hand-edited `cars.js`/`seed.sql`.

## Gotchas (from the code)
- **Escape SQL strings** — double every single quote before interpolating into `INSERT` values, or one
  apostrophe in the data breaks the whole seed (`build.mjs:21`).
- **Regenerate or you drift** — the generated files are AUTO-GENERATED; edit the source module and re-run
  `build:data`. The npm-script chaining (`package.json:8-12`) is what enforces this — replicate it.
- **`DELETE FROM` before the `INSERT`s** so re-seeding is idempotent and never duplicates rows
  (`build.mjs:29`).
- **Return 503 (not 500) when the DB is missing/empty** so the frontend's fallback path triggers cleanly
  instead of surfacing an error (`worker.js:50-53`).
- **This is for hand-curated, small datasets** (a catalog/lineup/menu) — embedding the whole set in the
  page is the point (offline/static), but it does NOT scale to user-generated or large tables; use a real
  API-only path there.
