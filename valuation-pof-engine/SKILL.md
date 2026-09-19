---
name: valuation-pof-engine
description: >-
  A READ-ONLY, evidence-graded valuation + proof-of-funds engine for a Cloudflare Worker + D1 book
  of holdings: dual-source live quotes (Finnhub when a key is set → keyless Yahoo chart fallback),
  cross-source symbol de-dup so N positions in one ticker cost ONE fetch, an append-only valuations
  snapshot table, evidence tiers that are NEVER overstated (market / verified / modeled / pending —
  a live quote is "market", never "verified"), no-silent-freeze refresh telemetry (one row per run
  so the operator sees stale/failed pricing), a whole-book time series, and proof-of-funds +
  monthly statements that EMBED a "representation, not a bank/custodian attestation" disclaimer in
  the payload so no render can drop it. Use WHENEVER a build must DISPLAY the value of a portfolio /
  holdings / assets and prove balances without touching money: "portfolio value", "net worth
  dashboard", "proof of funds", "monthly statement", "live stock/crypto prices", "mark-to-market",
  "asset tracker", "show what they're worth". EXTENDS commerce-spine (uses its D1 shard router for
  cross-shard fanout + co-location) and pairs with vanilla-svg-charts. Guardrails: it DISPLAYS
  value, it never moves, trades, sends, or custodies money (that is prohibited); evidence grades
  are honest and never inflated; quotes are cron-refreshed with telemetry, never silently frozen;
  every POF/statement carries its disclaimer in the data, not just the UI.
---
# valuation-pof-engine — show the value, prove the funds, move nothing

## What it is / when to use
An engine that prices a book of positions from live market data, snapshots every value append-only,
grades each value's evidence honestly, and renders proof-of-funds + monthly statements that are
explicitly *representations* (not custodial attestations). Use it for any "what is this portfolio
worth / prove the balance" surface. It is strictly read-only over money.

## Reference implementation (Wavelygth — lift from here)
- **Quotes + refresh** — `~/Projects/clients/wavelygth/worker/index.js`
  - `quoteFinnhub(symbol, key)` L556-563, `quoteYahoo(symbol)` L565-576 (keyless; needs a
    browser-ish UA), `fetchQuote(env, symbol)` L577-582 — Finnhub when `env.FINNHUB_KEY` is set,
    else Yahoo; each throws on empty/non-finite so a bad quote never writes a zero.
  - `refreshPrices(env, trigger)` L586-645 — fans out over shards, **de-dupes symbols across
    shards** (`bySymbol`) so ten AAPL positions = one fetch; writes a `valuations` row per position
    with `evidence='market'` for a live quote; snapshots manual-valued positions (real estate /
    private / cash) too; writes ONE `refresh_runs` telemetry row per run (`ok`, priced, failed,
    failed_symbols) — **no silent NAV freeze**.
  - `latestValuation` L649-653, `portfolioPayload(env, portfolio)` L655-681 (per-position value +
    `value_source`/`value_evidence`/`value_ts`), `handleHistory` L692-716 (bucket per day, carry
    forward, sum).
  - `handlePof(env, user, url)` L1453-1477 — evidence counts + verified/market subtotals + a
    hard-coded **disclaimer string in the payload** ("a representation … not a bank or custodian
    attestation … not certified proof of funds").
  - `monthBounds(month)` L1486-1494 + `handleMonthlyReport` L1496-1543 — opening (last snapshot
    BEFORE the month) vs closing (last AT/BEFORE month end) per position, with its own disclaimer.
  - Routes: L3126 `/api/history`, L3127 `/api/pof`, L3128 `/api/report/monthly`; manual refresh
    L3216-3220 (`/api/admin/refresh`).
- **Schema** — `~/Projects/clients/wavelygth/worker/migrations/0001_init.sql`: `positions`
  (kind ∈ equity|crypto|real_estate|private|cash, qty, cost_basis, manual_value, `evidence` ∈
  verified|modeled|pending), append-only `valuations` (price, value, source, evidence, ts).
  `0005_hardening.sql`: `refresh_runs` (ts, trigger, priced, failed, symbols JSON, ok).

## How to reapply it
1. **Migration:** copy `positions` + `valuations` (append-only snapshots) + `refresh_runs`
   (telemetry). Keep the `evidence` CHECK so a bad grade can't be inserted.
2. **Quotes:** copy `quoteFinnhub`/`quoteYahoo`/`fetchQuote` — provider-first-with-keyless-fallback,
   each throwing on empty. Add `FINNHUB_KEY` as an optional secret; Yahoo needs a UA header.
3. **Refresh:** copy `refreshPrices` (de-dupe symbols before fetching; write the telemetry row).
   Wire it into `scheduled()` (cron) AND an admin "refresh now" button. Read telemetry to badge
   "prices fresh/stale" in the UI.
4. **Reads:** copy `portfolioPayload` (carry each value's source + evidence + timestamp through to
   the client) and `handleHistory`. Feed the payload to `vanilla-svg-charts`.
5. **POF / statement:** copy `handlePof` + `handleMonthlyReport` — **put the disclaimer in the JSON
   payload**, so a PDF/print/export can't render the numbers without the caveat.

## Gotchas (from the code + comments)
- **A live quote is `market`, NOT `verified`.** `verified` is reserved for an independently-attested
  value (a custodian/broker statement). Never label a keyless Yahoo quote as attested — that is the
  whole honesty contract of the POF.
- **De-dupe symbols across the whole book before fetching**, or you pay one API call per position
  and blow rate limits.
- **Throw on empty/non-finite quotes.** A `0` written as a value silently zeroes someone's net
  worth — `fetchQuote` and both providers reject empties so the position stays at its last snapshot.
- **No silent freeze.** Every refresh writes a `refresh_runs` row (even on partial failure) so the
  operator can see "last successful refresh" + which symbols failed. Surface it.
- **Disclaimer lives in the payload, not the template.** So no rendering path (print, export, a new
  screen) can accidentally drop it.
- **Positions and their valuations co-locate** on the same shard by design (the commerce-spine
  router) — history JOINs are single-shard; refresh writes each shard's valuations back to that
  same shard.
- **This engine displays value; it never moves money.** No trades, transfers, buys, sells, or
  withdrawals — those are prohibited actions. Keep it strictly read-only.
