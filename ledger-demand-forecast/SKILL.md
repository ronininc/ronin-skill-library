---
name: ledger-demand-forecast
description: >-
  Turn an append-only inventory/consumption ledger into a forward view — expected daily demand,
  days-to-stockout, a reorder-now signal + recommended reorder quantity, and a learned VELOCITY rank
  for the POS "hot-set" — as pure, explainable JS inside a Cloudflare Worker, no external service.
  The method is EWMA (exponentially-weighted moving average) of recent per-day consumption plus a
  light trend term: the right default for CRM/retail demand because it is robust on short, spiky
  series, needs no seasonality assumption, and is trivially explainable ("recent days weighted
  heaviest"). Consumption is read as negative ledger deltas; gaps within the observed span fill as
  genuine zero-sale days, and today's partial day is deliberately excluded so demand isn't biased
  down. Use WHENEVER a build needs "when do we reorder / how much", "days until we run out",
  "forecast demand from sales history", "which SKUs are moving fastest", "rank products for the
  register / featured shelf", "reorder point", or "velocity ranking". It COMPLEMENTS commerce-spine
  (which SYNCS a hot-set to the POS but doesn't decide its contents — THIS computes the learned
  ranking that chooses it), money-feed-health-monitor (a different read-model — money in/out vs
  demand), and sovereign-edge-scorer (the same sovereign-edge doctrine, applied to a logistic
  propensity instead of demand). Guardrails: it reads an append-only ledger, never mutates; deltas
  are signed (sale = negative, restock = positive) and only outflow counts as consumption; the output
  is a recommendation a human/gate acts on, and margin only breaks velocity ties (never overrides it).
---
# ledger-demand-forecast — EWMA reorder forecast + velocity hot-set ranking

## What it is / when to use
The demand-side sibling of sovereign-edge-scorer. Given an entity's append-only ledger, it answers
"how fast is this moving, when will it run out, and how much should we reorder," and it ranks a set of
items by learned velocity for a POS hot-set / featured shelf. Reach for it whenever reorder timing or
"what's hot" needs to come from real history instead of a hand-tuned constant.

## Reference implementation (patterns only, no client data)
- **`worker/lib/crm-intelligence/forecast.mjs`** — the engine:
  - `dailyConsumption(entries, …)` L13–32 — buckets signed deltas into per-day outflow; fills interior
    zero-sale days; excludes the current incomplete day (the down-bias guard).
  - `ewma(series, alpha)` L35–45 — level + smoothed trend; `alpha` weights recency.
  - `forecastReorder(ledgerEntries, opts)` L51–71 — returns `{dailyDemandMu, daysToStockout, reorderNow,
    recommendedQtyMu, basis}`; reorder point = demand × (leadTime + safety), target cover adds the review
    cycle. All quantities in milli-units ("mu" = thousandths).
  - `rankHotSet(items, opts)` L79–94 — transparent weighted score over velocity + recency + margin
    (`weights` are tunable data); returns each item's score + `factors`.
- **`worker/lib/crm-intelligence/features.mjs`** L37–90 — the schema adapter: `ledgerRowsToDeltas`
  maps a `{change_mu, created_at, reason}` ledger row onto the engine's `{delta_mu, at}`;
  `forecastProductReorder`/`rankProductHotSet` wrap the engine for `products` rows; `loadProductLedger`
  is the exact D1 query (last N days, ASC).
- Proof: `worker/lib/crm-intelligence/_proof/features-forecast.test.mjs`.

## How to reapply
1. Have an append-only ledger with a signed quantity delta + a timestamp per row (outflow negative).
2. Write a tiny adapter mapping your row → `{delta_mu, at}` (keep all schema knowledge in the adapter).
3. Per SKU: `forecastReorder(loadLedger(id), {onHandMu, leadTimeDays, reviewDays, safetyDays, alpha})`.
4. For the hot-set: feed each item its ledger to `rankHotSet(items, {topN})`, then hand the ranked ids
   to commerce-spine's POS hot-set sync.

## Wiring status + gotchas (from the code)
- **WIRED** in the source repo: `worker/index.js` L811 (`forecastProductReorder`) and L815
  (`rankProductHotSet`, topN 20) drive a live route.
- EWMA `alpha` (default 0.3) is the one knob: higher = twitchier/more recent, lower = smoother.
- `daysToStockout` is `Infinity` when demand is 0 — render it as "no recent sales", not a number.
- Margin only nudges ties in `rankHotSet` (via `log1p`); it can't float a dead SKU to the top.
