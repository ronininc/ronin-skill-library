---
name: money-feed-health-monitor
description: >-
  A read-only "money feed" over a commerce CRM's order ledger, built for a companion phone/oversight app:
  one endpoint returns money in / money out / net, a 14-day daily series for graphs, recent orders, a
  "start working" queue (paid digital/kit sales not yet delivered), fulfillment-health counts with
  stuck-order detection (paid > 30 min but never fulfilled), surfaced capital-leaks, and ONE rolled-up
  condition color (white/yellow/orange/red). It reads the real per-order P&L tables — no separate metrics
  store to drift. Use WHENEVER a build needs "money dashboard", "cash/P&L health at a glance", "companion
  app feed", "how's the store doing right now", "what needs my attention", "is fulfillment stuck", "daily
  revenue/net chart", or "a single status light for the business". COMPLEMENTS order-pnl-fund-gate-
  fulfillment (it AGGREGATES the `net_profit_cents`/`cogs_cents`/etc. that skill books — it does not
  compute finance itself), capital-leak-breaker (it TRIGGERS the leak scan on each poll and renders active
  breakers as the RED condition), and governance-diode (this PII-free aggregate feed is the natural
  read-model an oversight/companion role pulls). Do NOT re-implement the P&L, fulfillment, or breaker
  logic here — this is the aggregate read-model + condition-code delta only. Guardrail: read-only surface,
  margins/aggregates only (no write path), and the feed poll is what keeps the dead-man's switch scanning.
---
# Money-Feed Health Monitor

## What it is / when to use
A single GET that a phone/companion or oversight brain polls to see the whole store's money state without
touching business logic: totals, a two-week trend, what's paid-but-undelivered, whether autonomy is
stuck, any capital leaks, and one traffic-light condition. It computes everything from the live order
tables at request time, so there's no metrics table to seed or keep in sync. It exists so an operator can
glance at a phone and know "green / needs attention / bleeding" — and so an oversight role can watch
without write access or PII.

**Composes with:** `order-pnl-fund-gate-fulfillment` (source of the `subtotal/cogs/payment_fee/shipping/
overhead/net_profit` columns it sums, and the `fulfillment_status` states it counts), `capital-leak-breaker`
(it calls `scanAndTrip` first and lists `activeBreakers` as leaks), `digital-product-kit` (the "start
working" queue is digital/kit sales), and `governance-diode` (the PII-free aggregate is what an oversight
role safely reads). This skill owns **the aggregate read-model + condition color only**.

## Reference implementation (ronininc)
Confirmed read — `worker/fulfillment.ts` L182-263, `storeFeed()`:
- L183 — **calls `scanAndTrip(env)` first** ("halt any leaking SKU before we report"): the feed poll is
  what keeps capital-leak-breaker live.
- `realized` filter L184 — `status IN ('paid','fulfilled','shipped','delivered')`.
- **Rollup** L185-196 — one query summing `subtotal_cents` (revenue), `cogs`, `payment_fee`, `shipping`,
  `overhead`, `net_profit`; `money_out = cogs+fees+shipping+overhead`.
- **14-day series** L197-204 — grouped by `date(created_at,'unixepoch')`, `money_in` / `money_out` / `net`
  per day, `created_at >= unixepoch()-14·86400`.
- **Recent orders** L205-208 (last 10), **pending count** L209.
- **"Start working" queue** L211-218 — DISTINCT paid orders with a digital/kit line (`p.is_digital=1 OR
  p.category='KITS'`) whose `fulfillment_status NOT IN ('delivered','shipped')`.
- **Fulfillment health** L220-230 — count by `fulfillment_status`; **stuck** = `status='paid' AND
  fulfillment_status='unfulfilled' AND paid_at < unixepoch()-1800` (paid >30 min, autonomy never acted).
- **Capital leaks** L233-238 — `activeBreakers(env)` mapped to `{breaker_id, scope, label, reason,
  amount_cents, proposed_price_cents, status}`; `leaking = breakers.length>0`.
- **Cooper's color code** L240-246 — `white` (no activity) → `yellow` (activity) → `orange` (attention:
  start-working items, stuck orders, awaiting_funds/queued/awaiting_connector, or pending) → `red` (leaking).
- Returns L248-262 `{ok, condition, leaking, money_in, money_out, net, ledger, pending_orders,
  capital_leaks, crm_pack_alerts, fulfillment_health, series, recent}`.
- `storeLedger()` L265-281 — the lighter totals-only sibling (`GET store/ledger`), no scan/series.
- Route: `worker/admin.ts` L333 — `GET store/feed → storeFeed` (and L332 `GET store/ledger → storeLedger`).

## How to reapply it
1. **No new schema.** It reads commerce-spine + order-pnl-fund-gate-fulfillment's existing columns
   (`store_orders` finance columns, `products.is_digital/category`) and capital-leak-breaker's `store_breakers`.
   If those skills are in, this just works.
2. **Drop in `storeFeed`** (and `storeLedger`). Keep the `scanAndTrip(env)` call at the top — it's the
   store's protection heartbeat (see gotcha). Adjust the stuck threshold (1800s) and series window (14d)
   to taste.
3. **Route.** `GET /api/admin/store/feed` (rich) and `GET /api/admin/store/ledger` (light). For an oversight/
   companion role, expose the feed through governance-diode so it's read-only + PII-scoped (the feed's
   aggregates are already PII-free; `recent`/`crm_pack_alerts` include `customer_email` — strip those for
   an untrusted oversight role).
4. **Companion UI.** Render the condition color as the app's status light, the series as a sparkline, the
   "start working" queue and stuck count as action items, and capital-leaks as red alerts with the staged fix.
5. **Poll cadence.** Have the companion poll the feed on open + on an interval; each poll also runs the leak
   scan. If you want protection independent of the app, ALSO add `scanAndTrip` to a cron (see gotcha).

## Gotchas (from the code + comments)
- **The feed poll IS the breaker's heartbeat.** `storeFeed` calls `scanAndTrip` (L183) — in the source
  that's the ONLY caller. If nobody polls the feed, leaking SKUs are never halted. For hands-off
  protection, add `scanAndTrip` to the `scheduled()` cron too; don't rely on the app being open.
- **It's a read model — keep it read-only.** No write path belongs here. The only side effect is the leak
  scan, which is itself idempotent (INSERT OR IGNORE). Don't add mutations to the feed endpoint.
- **`recent` and `crm_pack_alerts` carry `customer_email`** — PII. The rollup/series/health/leaks are
  PII-free and safe for an oversight role; the recent-orders and start-working lists are not. Split them
  when the consumer is a governance-diode oversight pull, not the operator.
- **Condition precedence matters.** `orange` (attention) is overwritten by `red` (leaking) last (L245-246)
  — a leaking store is always red even if it also has attention items. Keep that order; red is the ceiling.
- **Aggregates are only as honest as the P&L.** `net`/`money_out` are sums of what order-pnl-fund-gate-
  fulfillment booked. An unmapped Shopify SKU (cost=0) or a stale reconcile shows inflated net here — fix
  it upstream, not by patching the feed.
- **"Stuck" is a 30-minute heuristic** for paid-but-unfulfilled. If your fulfillment is legitimately slow
  (manual confirm), tune the threshold or it'll cry orange constantly.
