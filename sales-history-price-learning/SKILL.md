---
name: sales-history-price-learning
description: >-
  Learn a suggested price for each SKU / pack-level from a merchant's OWN sales history and surface it
  as human-gated GUIDANCE — never an automatic price change, and (critically) NEVER written back to the
  POS that owns prices. A scheduled pass reads real sold prices from `order_lines` over a rolling
  window (default 90 days, min sample count), takes the MEDIAN sold price per level (robust to a few
  odd rings), and when it differs from the current price writes a `pending` price_suggestion — first
  SUPERSEDING any older pending suggestion for the same level so the queue never stacks stale advice.
  An operator approves or rejects; approval just marks the number as active kiosk-discount guidance the
  staff apply per-order — the POS item price is left untouched. Use WHENEVER a build should "suggest
  prices from what actually sold", "learn our pricing from history", "recommend a discount / price
  point", "price optimization but let a human decide", "median sale price per item", or "pending price
  suggestions to approve". It COMPLEMENTS commerce-spine / clover-connector (which hold that POS OWNS
  prices — this reads sale history and only advises, honoring that boundary) and
  confirmed-inputs-decision-gate (the human approve/reject gate this rides on). Guardrails: money is
  integer cents; nothing is auto-applied and nothing is pushed to the POS; a learned price is advisory
  input to a per-order manual discount; below the minimum sample count a level is skipped (no guessing).
---
# sales-history-price-learning — median-of-sold-prices → pending suggestion → human-gated guidance

## What it is / when to use
A tiny, honest price-learning loop: it mines the merchant's own rings for what a thing actually sold
for, proposes a number, and stops. It exists to give staff a data-backed discount to reach for without
ever letting software silently move a price or reach into the POS. Reach for it when "suggest prices"
or "learn our pricing" comes up on a build where the POS is the price authority.

## Reference implementation (patterns only, no client data)
All in `worker/lib/pricing_learn.js`:
- `median(nums)` L6–11 — the robust central estimate (not mean — one odd ring can't skew it).
- `deriveSuggestions(db, {windowDays=90, minSamples=3})` L19–44 — per active pack level: pull sold
  `unit_price_cents` from `order_lines` in the window; skip if under `minSamples`; if the learned
  median differs from the current price, mark older `pending` rows `superseded` then INSERT a new
  `pending` `price_suggestion` (`method='median'`, `source='local_orders'`).
- `listSuggestions(db, status)` L46–55 — joins suggestions → pack_levels → products for the review UI.
- `approveSuggestion(db, env, id, userId)` L62–69 — marks `approved`; returns
  `guidance_price_cents` with the note "kept as kiosk discount guidance — Clover price unchanged."
  **Nothing is written to the POS.**
- `rejectSuggestion(db, id, userId)` L71–76.
- **Schema:** `price_suggestions` + `pack_levels` in `worker/migrations/0003_pack_tiers.sql`.

## How to reapply
1. Migration: `pack_levels` (SKU × size, with a current `price_cents`) and `price_suggestions`
   (`pack_level_id`, `suggested_price_cents`, `current_price_cents`, `method`, `sample_count`,
   `window_days`, `source`, `status`, `decided_at`, `decided_by`).
2. Cron: schedule `deriveSuggestions` (see `worker/index.js` L95 — runs it via `ctx.waitUntil` on the
   cron tick) plus an admin-triggered route (L716).
3. UI: an admin queue listing `pending` suggestions with approve/reject; consume approved guidance at
   the kiosk (source repo reads it at `worker/index.js` L1599 to prefill a per-order discount).

## Gotchas (from the code)
- The POS OWNS prices — this loop is guidance ONLY. Do not add a "push to POS" step; that breaks the
  source-of-truth boundary commerce-spine/clover-connector rely on.
- Always supersede older `pending` rows before inserting (done here) or the queue accumulates stale
  advice for the same level.
- Median needs a minimum sample (default 3) to mean anything — below it, skip the level rather than
  suggest off one or two rings.
