---
name: mystery-box-balancer
description: >-
  A server-side composer for curated/blind bundles ("mystery boxes"): the customer pays one fixed box
  price and the CRM assembles the real contents from live catalog SKUs, balancing a HARD margin ceiling
  (never violated — protects the cut) against a SOFT value promise (maximized — the hook), with a
  quality FLOOR that drops low-grade items at any price and a weighted quality/reputation/value ranking.
  The box line carries the revenue; the composed component lines carry the COGS — so per-order P&L books
  correctly. Use WHENEVER a commerce build needs "mystery box", "blind box", "surprise bundle", "grab
  bag", "curated bundle at one price", "loot box", "pack it live so it's worth more than they paid but
  we keep margin", or "compose the contents server-side". COMPLEMENTS commerce-spine (which owns the
  catalog, cart, and server-side re-pricing this plugs into) and order-pnl-fund-gate-fulfillment (which
  books the P&L from the component COGS lines this emits) — do NOT re-implement the catalog, order
  insert, or P&L here; this is only the balancer delta. Guardrails: margin is the hard constraint (only
  SKUs whose unit cost fits the ceiling are drawn), composition is ALWAYS server-side (never trust a
  client-supplied box), and near-cost anchor SKUs are excluded from boxes via box_eligible=0.
---
# Mystery-Box Balancer

## What it is / when to use
A pure, unit-testable function plus a thin catalog loader that turns "buy this $99 sealed box" into a
real set of catalog items chosen to maximize delivered retail value while never breaking a protected
net-margin floor. The margin floor is a **hard** constraint; the value promise is a **soft** target
maximized underneath it. It exists so a store can sell surprise/curated bundles that feel generous to
the buyer and stay profitable to the operator, with the composition done on the server where the client
can't tamper with it.

**Composes with:** `commerce-spine` (the per-site D1 catalog + cart + `publicCreateOrder` that re-prices
server-side — this balancer is invoked from inside that order path), `order-pnl-fund-gate-fulfillment`
(the box emits one revenue-bearing box line + N cost-bearing component lines, which that skill's
`reconcileOrderFinance` sums into COGS), and `capital-leak-breaker` (which watches the resulting margins).
This skill owns **contents composition + the margin/value/quality balance only** — nothing else.

## Reference implementation (ronininc)
Confirmed read:
- `worker/mystery.ts` L1-79 — the whole engine.
  - `feeOf()` L22 — the card fee subtracted from the ceiling: `round(price·290/10000)+30` (2.90% + $0.30),
    matching the store's default fee model so the ceiling reflects true take-home.
  - `balanceBox()` L30-61 — the **pure** balancer (no I/O; takes `rng` for deterministic tests):
    - `value_target = round(price·valueBps/10000)` — soft promise (e.g. 17000 bps = 170% of price).
    - `cost_ceiling = max(0, round(price·(10000−marginFloorBps)/10000) − feeOf(price))` — HARD margin gate.
    - Pool filter L37-38: `cost>0 AND cost<=cost_ceiling AND quality>=minQuality` (margin gate + quality floor).
    - Ranking key L40-46: value stays the reachable base (so the promise always clears the price), and a
      `qr` blend of quality+reputation nudges ordering; `weights.v` sets value emphasis; light jitter
      `(0.9+0.2·rng())` for genuine surprise. Sorted highest-key-first.
    - Fill loop L51-59: add items highest-first, **skip any that would push cost over the ceiling**
      (`continue`, never break the floor), stop once `min_items` reached AND `value >= value_target`,
      capped at `max_items`.
  - `composeBox()` L64-79 — loads box-eligible candidates for the box's theme
    (`status='active' AND sales_halted=0 AND is_box=0 AND box_eligible=1`, optional `category=theme`),
    reads the tunable floor+weights from `store_settings`, and calls `balanceBox`.
- `worker/commerce.ts` L213-227 — the call site inside `publicCreateOrder`: for an `is_box=1` line it
  composes **once per unit** (capped 10), pushes the box line as revenue (`price_cents` set, `cost_cents=0`)
  then each component as a cost line (`title` prefixed `'↳ '`, `price_cents=0`, `cost_cents` set).
- Migrations: `0047_store_mystery_box.sql` — adds `is_box, box_eligible, box_theme, box_value_bps,
  box_margin_floor_bps, box_min_items, box_max_items` to `products`; `0051_store_quality_reputation.sql`
  — adds `quality_score, supplier_rep, rating, review_count` to `products` and
  `pick_min_quality, pick_w_quality, pick_w_rep, pick_w_value` to `store_settings`.
- **Proof:** `worker/lib/_proof/store-fulfillment.test.ts` L92-106 — asserts the quality floor drops a
  cheap low-grade item, `cost <= cost_ceiling` (margin held), and `value >= value_target` (promise cleared).

## How to reapply it
1. **Schema (delta on commerce-spine's `products`/`store_settings`).** Apply the two migrations' column
   sets: box config columns on `products` and the balance weights + `pick_min_quality` on `store_settings`.
   `quality_score`/`supplier_rep` are YOUR curation grades (0-100, legitimately yours); `rating`/
   `review_count` are customer reviews — keep them 0 until real ones exist, never fabricate.
2. **Drop in `mystery.ts`.** Lift `balanceBox` (pure) and `composeBox` (the loader). Adjust `feeOf` to
   match the client's real processor fee if it differs from 2.90%+$0.30, or the ceiling will be wrong.
3. **Seed box products.** Create box SKUs with `is_box=1`, `cost_cents=0` (cost comes from contents at
   order time), and per-box `box_value_bps` / `box_margin_floor_bps` / `box_min_items` / `box_max_items`
   / `box_theme`. **Mark near-cost anchor SKUs `box_eligible=0`** so you never pack a thin-margin item
   into a "value" box.
4. **Wire the order path.** In commerce-spine's `publicCreateOrder`, branch on `is_box=1` and inline the
   L215-227 pattern: compose per unit, emit the box revenue line + component COGS lines. Then let
   `order-pnl-fund-gate-fulfillment.reconcileOrderFinance` book the P&L from those cost lines.
5. **Tune / prove.** Adjust `pick_min_quality` and the weights in `store_settings`; run the balancer
   proof (`npx tsx .../store-fulfillment.test.ts`) with your candidate set to confirm floor + margin + value.

## Gotchas (from the code)
- **The ceiling subtracts the card fee — get `feeOf` right.** If the client's real processor fee is
  higher than the hard-coded 2.90%+$0.30, an unadjusted `feeOf` overstates the ceiling and boxes can ship
  below the true margin floor. Match it to the actual rail.
- **Value is the base retail, quality only reorders.** L44-45 keep the sort key anchored to `retail` so
  the value promise always clears; weights shift *which* qualifying items get picked, not whether the
  promise is met. Don't rewrite the key to let quality dominate value or the promise can under-deliver.
- **Compose server-side, per unit, every time.** The client sends only the box product id; contents are
  drawn on the server (L215-227). Never accept client-supplied contents, and note the 10-units-per-line
  cap (L219) exists to bound compute — raise it deliberately.
- **A thin pool silently under-fills.** If too few SKUs pass `cost<=ceiling AND quality>=floor`, the box
  can end below `value_target` or below `min_items` (the loop just runs out). Keep enough box-eligible,
  in-margin inventory, or the "worth more than you paid" promise breaks.
- **`box_eligible=0` is load-bearing.** Anchors sold at/near cost must be excluded, or the balancer will
  happily pack them and evaporate the margin. Seed data marks anchors explicitly — do the same per client.
- **Component lines are `is_box=0` physical SKUs** — fulfillment groups them by supplier and buys them;
  the box line itself is excluded from supplier purchase (see order-pnl-fund-gate-fulfillment L138-141).
