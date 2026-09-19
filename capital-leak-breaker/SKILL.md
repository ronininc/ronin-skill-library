---
name: capital-leak-breaker
description: >-
  A self-restoring circuit breaker (dead-man's switch) for a commerce CRM: on every feed poll it scans
  for capital leaks — an active SKU priced at or below its cost (every sale loses money) or an order that
  already booked a NEGATIVE net — HALTS only the bleeding SKU (traffic to the rest of the store keeps
  flowing), stages a concrete reprice fix, and raises RED; because re-going-live moves money it requires
  explicit operator approval (money-never-auto): approve → apply the staged fix → un-halt → resolved. Use
  WHENEVER a commerce build needs "stop selling something at a loss", "auto-halt below-cost items",
  "circuit breaker on margins", "detect a capital/money leak", "kill switch for a bad SKU", "alert me if
  an order sold at a loss", or "don't let a mispriced product keep bleeding". COMPLEMENTS
  order-pnl-fund-gate-fulfillment (it reads the `net_profit_cents` that skill books to detect realized
  losses) and commerce-spine (whose `products.sales_halted` flag it flips), and it is surfaced by
  money-feed-health-monitor (whose feed poll is what triggers the scan, and which renders the leaks as
  the RED condition). Do NOT re-implement the P&L or the catalog here — this is the detect→halt→stage→
  approve breaker delta only. Guardrails: halt is per-SKU (never the whole store), re-going-live is
  operator-gated (moves money), and a unique partial index guarantees one active breaker per scope.
---
# Capital-Leak Breaker

## What it is / when to use
A protection loop that treats a mispriced or loss-making SKU like a burst pipe: shut the one valve, keep
the house running, stage the repair, and require a human to turn it back on. Two leak classes:
**structural** (an active physical SKU priced ≤ cost — auto-halted with a staged reprice) and
**realized** (an order that already netted negative — flagged for review, no auto-reprice). It exists so
a store can run semi-autonomously without a single bad price quietly draining cash.

**Composes with:** `order-pnl-fund-gate-fulfillment` (source of `net_profit_cents` for the realized-loss
class), `commerce-spine` (owns `products`; this adds/flips `sales_halted`), `money-feed-health-monitor`
(calls the scan on every poll and paints the store RED when breakers are active). This skill owns
**leak detection + per-SKU halt + staged fix + operator-gated restore** — nothing else.

## Reference implementation (ronininc)
Confirmed read — `worker/breakers.ts` L1-71:
- `scanAndTrip()` L14-36 — the dead-man's switch, run on every feed poll:
  - **Structural** L16-26: select active, non-halted, physical (`is_box=0 AND is_digital=0`) SKUs with
    `cost_cents>0 AND price_cents<=cost_cents`. For each: `UPDATE products SET sales_halted=1` (stop the
    bleeding), then `INSERT OR IGNORE INTO store_breakers` a `fix_staged` row with `proposed_price_cents
    = max(round(cost·1.4), cost+500)` (40% over cost, min +$5) and a human-readable `fix_note`.
  - **Realized** L28-35: select `status IN ('paid','fulfilled','shipped','delivered') AND net_profit_cents<0`;
    `INSERT OR IGNORE` a `tripped` breaker (`amount_cents` = the negative net) for review — no auto-reprice.
- `activeBreakers()` L38-43 — `status IN ('tripped','fix_staged')`, newest first, LIMIT 30.
- `listBreakers()` L45-47 — admin GET.
- `resolveBreaker()` L50-71 — operator review:
  - `approve` L57-65: for a product breaker, reprice to `b.price_cents || proposed_price_cents`, set
    `sales_halted=0, status='active'`; mark breaker `resolved` with `approved_by`.
  - `dismiss` L66-69: mark `dismissed` — the **SKU stays halted** (dismiss ≠ un-halt).
- Migration `0053_store_breakers.sql` — adds `products.sales_halted`; creates `store_breakers`
  (scope_type product|order|store, reason, amount_cents, status CHECK, fix_note, proposed_price_cents,
  timestamps, approved_by) with `idx_store_breakers_status` and, critically, a **UNIQUE partial index**
  `idx_store_breakers_active ON (scope_type, scope_id) WHERE status IN ('tripped','fix_staged')` — one
  active breaker per scope, so a repeated scan can't double-trip.
- Trigger point: `worker/fulfillment.ts` L183 — `storeFeed` calls `scanAndTrip(env)` first, "before we
  report", so protection runs whenever the companion checks in.
- Routes: `worker/admin.ts` L338-339 — `GET breakers → listBreakers`, `POST breaker/resolve → resolveBreaker`.
- **Proof:** `worker/lib/_proof/store-breaker.test.ts` — below-cost SKU auto-halted + fix staged
  (reprice to $40.60 = max(2900·1.4, 2900+500)); operator approve → repriced/un-halted/resolved; a
  healthy SKU is left alone (no false re-trip).

## How to reapply it
1. **Schema.** Apply `0053`: add `products.sales_halted` and create `store_breakers`. **Keep the unique
   partial index** — it's what prevents duplicate active breakers under repeated scans.
2. **Drop in `breakers.ts`** (`scanAndTrip`, `activeBreakers`, `listBreakers`, `resolveBreaker`). Tune the
   reprice heuristic (L21, `cost·1.4` / min +$5) to the client's target margin.
3. **Honor `sales_halted` everywhere a SKU is sold.** The public catalog and product endpoints must
   filter `sales_halted=0` (commerce-spine already does in `publicProducts`/`publicProduct`), and the
   mystery-box loader excludes halted SKUs — otherwise a halted item can still be bought or boxed.
4. **Wire the scan to run.** The source calls `scanAndTrip` only from `storeFeed` (L183). If the companion
   feed isn't polled regularly, **the switch never scans** — see gotchas. Add `scanAndTrip(env)` to the
   `scheduled()` cron batch (it's cheap, INSERT-OR-IGNORE idempotent) so protection is time-driven, not
   only poll-driven.
5. **Routes + UI.** `GET breakers`, `POST breaker/resolve`. Approve moves money (un-halts a SKU to sell
   again) → put it behind the operator confirm, and pass the reviewed `price_cents` if overriding the
   staged proposal.

## Gotchas (from the code + comments)
- **It only scans when something calls it.** In the source that's the feed poll (`storeFeed`), not a
  cron. A store nobody is watching gets no protection. Add the cron in step 4 for hands-off coverage.
- **`dismiss` does NOT un-halt.** Dismissing a breaker leaves `sales_halted=1` — the SKU stays stopped
  until an `approve` (with a valid price) restores it. This is deliberate: dismiss = "I've seen it, keep
  it off." Don't confuse dismiss with resume.
- **Only physical SKUs trip the structural class.** `is_box=0 AND is_digital=0` — a box's price legitimately
  exceeds its per-line cost (box line cost=0), and digital kits carry no cost, so both are excluded. Don't
  relax that filter or every box/digital line will false-trip.
- **Realized-loss breakers are advisory** (`tripped`, no proposed price). They flag an order that already
  lost money — you can't un-sell it; the fix is on pricing/overhead going forward. Approving one just
  clears the flag.
- **The unique partial index is the anti-double-trip.** `INSERT OR IGNORE` relies on it; without the
  index every scan of the same leak inserts a new row. Keep it.
- **Re-going-live is the only money-moving action here** — repricing + un-halting resumes sales. Keep it
  operator-gated (money-never-auto); never auto-approve breakers.
