---
name: county-records-comps-arv
description: >-
  A comparable-sales valuation engine that turns a FREE county assessor's public GIS parcel service into a
  proposed As-Is value and ARV (after-repair value) for a real-estate deal — the piece that unblocks
  wholesale underwriting when deals pile up at "sourced" because nobody produced a defensible ARV. Given a
  parcel (APN), it pulls same-property-use sales in the SAME subdivision (else a small lat/lon box),
  filters to arm's-length sales in the last 12 months (18 if thin), within ±30% living area, trims $/sq-ft
  outliers, then: As-Is = median $/sq-ft × subject sq-ft, ARV = 75th-percentile $/sq-ft × sq-ft (renovated
  homes sell at the top of the comp set), with a confidence grade from comp count + spread and the comp set
  attached as evidence. It PROPOSES only — it never writes the deal's confirmed numbers; a separate operator
  confirm (who also picks a light/medium/heavy repair preset) turns the estimate into the numbers
  underwriting may use. Use WHENEVER a build must "estimate ARV / as-is value from comps", "pull comparable
  sales for a property", "underwrite a wholesale deal", "value a house from public records", "what's this
  parcel worth", or "propose a repair budget" — anywhere free county data can replace a paid comps API.
  It COMPLEMENTS valuation-pof-engine (both are READ-ONLY, evidence-graded value engines that move no money
  — that one values a securities book from live quotes, this values real property from public comps),
  buy-box-matcher / az-cash-buyer-finder (which decide FIT and find the exit — this supplies the value they
  need), and confirmed-inputs-decision-gate (the operator confirm this rides on). Guardrails: it never
  writes the confirmed ARV/repair fields on its own; every estimate carries its comps so it can be checked;
  non-arm's-length transfers ($10 quitclaims, sub-threshold sales) and $/sq-ft outliers are dropped, never
  averaged in.
---
# County-Records Comps → ARV — free public comps become a propose-only valuation

## What it is / when to use / what it composes with
A backend engine for a Cloudflare Worker + D1 real-estate CRM that computes a defensible As-Is value and
ARV from a public county assessor's parcel/sales GIS layer — no paid comps subscription. It exists because
underwriting stalls without a confirmed ARV + repair budget, and the public assessor already carries living
area, sale price, sale month, property-use code, subdivision, and lat/lon — enough for real comparable
selection. Reach for it whenever a deal needs a value backed by actual nearby sales, and the honest posture
is "here is a proposed number and the exact comps behind it," not an opaque estimate.

**Composes with:** **valuation-pof-engine** (its READ-ONLY, never-overstated, evidence-graded sibling for a
different asset class — reuse its posture: display value, move nothing, grade honestly), **buy-box-matcher**
/ **az-cash-buyer-finder** (fit + exit; this feeds them the value), and **confirmed-inputs-decision-gate**
(the human confirm that promotes an estimate to a usable number). The county fetch should ride your
SSRF/egress transport; the cron pass registers as one daemon in daemon-fleet-switchboard.

## Reference implementation — EXACT source
`ronininc-site/worker/arv-comps.ts` (reference county: Maricopa County, AZ assessor ArcGIS service):
- The assessor endpoint + fields pulled — `worker/arv-comps.ts:21-22` (`ASSESSOR_URL`, `FIELDS`:
  `APN,PUC,LIVING_SPACE,SALE_DATE,SALE_PRICE,…,LATITUDE,LONGITUDE`).
- **The pure comp selection + math** (lift this — it's deterministic and unit-testable): `worker/arv-comps.ts:54-78`
  (`computeArv`): same-APN excluded, same `PUC` (property use), 12→18-month recency window, ±30% sq-ft,
  ≥ $60k arm's-length floor, `ppsf` outlier trim around the median (0.5×–1.8×), then median → As-Is and
  p75 → ARV, with a `confidence` from comp count + interquartile spread.
- Quantile + month-index helpers — `worker/arv-comps.ts:32-41`.
- The ArcGIS POST query (form-encoded, 25s timeout, error-shape check) — `worker/arv-comps.ts:43-50`.
- Orchestration `estimateArv` (subject lookup by APN → same-subdivision comps → lat/lon-box FALLBACK →
  store the estimate + basis) — `worker/arv-comps.ts:85-108`; the estimates table DDL at `:80-82`.
- Cron pass, bounded per tick, best-deal-score first — `worker/arv-comps.ts:111-124` (`runArvCompsPass`).
- **The operator confirm** (propose→confirm boundary): repair presets `REPAIR_PER_SQFT` (`worker/arv-comps.ts:127`)
  and `confirmArv` (`:131-139`) — this is the ONLY place `re_deals.arv_cents`/`repair_cents` are written,
  from the stored comps ARV + the operator-picked repair level.
- Estimates for a deal list (admin table) — `worker/arv-comps.ts:142-151` (`estimatesFor`).
- Wiring: admin action + Solomon MCP tool call `estimate-arv`/confirm — `worker/acquisitions.ts:14,250,254`,
  `worker/solomon-mcp.ts:21,449,460`; list join `worker/deal-finder.ts:23`; cron `worker/index.ts:21,370`.

## How to reapply — the schema + THE INVARIANT
1. Split estimation from confirmation across TWO tables: `re_arv_estimates` (the machine's proposal — comps
   JSON, median/p75 ppsf, as-is/arv cents, confidence, basis, status) and the deal's own confirmed
   `arv_cents`/`repair_cents` (written only by the operator confirm).
2. Selection is a pure function of (subject, candidates, nowMonth): exclude the subject, require same
   property-use, filter recency/size/arm's-length, trim $/sq-ft outliers around the median. As-Is = median
   ppsf × sqft; ARV = p75 ppsf × sqft. Widen the recency window (12→18mo) and fall back subdivision→radius
   box ONLY when comps are thin; if still < 3 arm's-length comps, return "not enough comps" — never invent
   a number.
3. Store the comp set (APN, month, price, sqft) with every estimate so any figure can be audited.
4. **THE INVARIANT:** this engine PROPOSES; it never writes the deal's confirmed ARV/repair. Underwriting
   runs only on operator-confirmed numbers — the confirm step (which also records the repair level the
   operator chose) is the single writer of those fields. No auto-underwrite from an unconfirmed estimate.

## Gotchas — real pitfalls from the code + how it's validated
- **Non-arm's-length sales poison a median.** $10 quitclaims and sub-$60k transfers are dropped
  (`worker/arv-comps.ts:60`), and $/sq-ft outliers are trimmed to 0.5×–1.8× of the pre-trim median
  (`:66-67`) — never averaged in. Skipping this makes comps look absurdly cheap or dear.
- **Sale dates are month-precision.** `monthIndex` parses `MM/DD/YYYY` to a month ordinal (`:33-36`); do
  recency math in months, not days, and don't assume a real day-of-month.
- **The subject may lack a subdivision or an APN.** `estimateArv` falls back to a lat/lon box when
  `SUBNAME` is missing (`:99-104`) and stores an explicit `no-apn`/`no-parcel`/`thin` status
  (`:92,94,105`) so the admin sees WHY a deal has no value, instead of a silent blank.
- **Confidence must degrade honestly.** `high` needs ≥6 comps AND spread ≤0.35; otherwise `medium`/`low`
  (`:72`). A 3-comp estimate is `low` and should be shown as such, never as a firm number.
- **Bound the cron.** `runArvCompsPass` does a few deals per tick, highest deal-score first, re-checking
  only deals older than a cooldown (`:111-124`) — a Worker can't comp thousands of parcels in one
  invocation. Validated by the operator seeing an estimate + its comps in the deal dossier before any
  confirm; the pure `computeArv` is the seam a proof harness drives with fixture parcels.
