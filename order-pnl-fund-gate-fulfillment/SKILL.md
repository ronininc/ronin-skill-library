---
name: order-pnl-fund-gate-fulfillment
description: >-
  The money-discipline layer for a dropship/commerce CRM: book a full per-order P&L on every order
  (revenue − COGS − payment fee − shipping − overhead = net profit) and govern auto-fulfillment with two
  ENFORCED rules — a FUND GATE (never place a supplier purchase before the customer's funds settle, so
  COGS is always paid with the customer's money, never fronted) and money-never-auto (auto-buy is OFF by
  default; armed-but-no-connector records 'awaiting_connector' and NEVER fakes a purchase). Use WHENEVER
  a commerce build needs "track profit per order", "per-order P&L / margins", "don't buy stock until the
  customer pays", "fund gate", "auto-fulfill safely", "supplier purchase orders", "gross vs net margin",
  or "book COGS/fees/overhead per sale". COMPLEMENTS commerce-spine (which owns catalog, orders, and
  order items — this books finance onto its `store_orders` and drives the supplier-purchase leg) and is
  watched by capital-leak-breaker (halts leaking SKUs) and surfaced by money-feed-health-monitor (the
  ledger read-model); mystery-box-balancer and digital-product-kit feed it their line items. Do NOT
  re-implement the catalog or order insert here — this is the P&L + fund-gate + governed-fulfillment
  delta only. Guardrail: the two rules are enforced in code, not merely documented; keep them that way.
---
# Order P&L + Fund Gate + Governed Fulfillment

## What it is / when to use
Two things bolted onto commerce-spine's orders: (1) a pure P&L calculator that, on every order, computes
and persists revenue/COGS/fee/shipping/overhead/net; and (2) a governed fulfillment step that will only
buy supplier materials once the customer's payment has settled, and only auto-buys when explicitly armed
AND a live supplier connector exists — otherwise it queues for a human or records an honest
`awaiting_connector`. Use it for any store where spending ahead of settled revenue would be fatal
(dropship, made-to-order, thin-margin resale).

**Composes with:** `commerce-spine` (orders + order items live there; this adds the finance columns and
the fulfillment leg), `mystery-box-balancer` (emits the revenue/COGS lines this sums), `digital-product-kit`
(the no-COGS delivery branch lives inside `fulfillOrder`), `capital-leak-breaker` (reads the `net_profit_cents`
this books to detect losses), `money-feed-health-monitor` (aggregates these columns). This skill owns
**per-order finance + the fund gate + governed supplier purchase** — nothing upstream of the order.

## Reference implementation (ronininc)
Confirmed read — `worker/fulfillment.ts` L1-281:
- `computeFinance()` L44-58 — **pure**, no I/O. `payment_fee = revenue>0 ? round(revenue·fee_bps/10000)+fee_flat : 0`;
  `overhead = round(revenue·overhead_bps/10000)+overhead_flat`; `full_overhead = cogs+fee+shipping+overhead`;
  `gross_profit = revenue−cogs`; `net_profit = revenue−full_overhead`; margins as ratios. All cents, all clamped ≥0.
- `financeSettings()` L66-71 — reads the fee/overhead/gate model from `store_settings` with safe defaults
  (`require_paid:1`, `auto_fulfill:0`, `payment_fee_bps:290`, `payment_fee_flat_cents:30`).
- `reconcileOrderFinance()` L74-90 — recompute from `subtotal_cents` + `SUM(cost_cents·qty)` over the
  order items, then persist `cogs/payment_fee/shipping/overhead/net_profit` back onto `store_orders`.
- `payOrder()` L96-108 — marks `status='paid'`, `paid_at`, and **`funded`** (default 1 = funds settled).
  `funded=1` is the ONLY thing that unlocks buying. In production this is driven by the payment-settled webhook.
- `fulfillOrder()` L114-165 — the governed loop:
  - **RULE 1 — FUND GATE** L120-124: if `require_paid && funded!==1` → set `fulfillment_status='awaiting_funds'`,
    place ZERO purchases, return early. Never fronts COGS.
  - Digital branch L126-136: any `is_digital=1` line → a `'(digital)'` fulfillment leg, delivered on payment.
  - Supplier grouping L138-142: one purchase per distinct supplier over **physical** items
    (`is_box=0 AND is_digital=0`, `HAVING cost>0`) — box lines and digital kits excluded.
  - **RULE 2 — GOVERNED AUTONOMY** L144-160: `target = !auto_fulfill ? 'queued' : (connector ? 'purchasing' : 'awaiting_connector')`.
    `connector = Boolean(env.CJ_API_KEY)`. Each supplier PO row is written with `funded_by_order=1` proof.
    The live supplier API call goes where the comment marks it (L157-158) once `target==='purchasing'`.
- `runFulfillment()` L167-175 — the admin POST wrapper.
- Migration `0046_store_fulfillment_finance.sql` — adds the governance/fee columns to `store_settings`,
  the P&L + `funded` + `fulfillment_status` columns to `store_orders`, and the `store_fulfillments` table
  (supplier POs) with a CHECK on `status IN ('queued','awaiting_funds','awaiting_connector','purchasing','purchased','failed','cancelled')`.
- Routes: `worker/admin.ts` L330-332 — `POST store/order/pay → payOrder`, `POST store/fulfill → runFulfillment`,
  `GET store/ledger → storeLedger`.
- **Proof:** `worker/lib/_proof/store-fulfillment.test.ts` L1-90 — P&L math cross-checks a live order
  ($256.58 net); FUND GATE places 0 purchases while unfunded; funded+auto-off queues one PO per supplier;
  armed-without-connector records `awaiting_connector` (never a fake buy).

## How to reapply it
1. **Schema.** Apply `0046` on top of commerce-spine's `store_settings`/`store_orders` and add the
   `store_fulfillments` table. Confirm the CHECK-constraint status vocabulary matches the code.
2. **Drop in `fulfillment.ts`** (`computeFinance`, `reconcileOrderFinance`, `payOrder`, `fulfillOrder`,
   `runFulfillment`, `storeLedger`). Tune the default fee/overhead in `financeSettings` to the client's rail.
3. **Book P&L at every mutation point.** Call `reconcileOrderFinance(env, orderId)` on order create
   (commerce-spine's `publicCreateOrder` does this L234), on `payOrder`, and inside `fulfillOrder` — so
   the ledger is always current.
4. **Wire routes.** `POST /api/admin/store/order/pay`, `POST /api/admin/store/fulfill`,
   `GET /api/admin/store/ledger` behind admin auth.
5. **Connector gate.** The auto-buy connector is detected via `env.CJ_API_KEY` (CJdropshipping). Rename/
   generalize `hasSupplierConnector` (L112) to your supplier API secret. **Until a connector exists,
   leave `auto_fulfill=0`** — armed-without-connector is intentionally inert (records intent, buys nothing).
6. **Payment webhook drives `funded`.** In production, the Stripe/Shopify "payment settled" webhook calls
   `payOrder` (or sets `funded=1`); see shopify-order-bridge, which lands orders `paid,funded=1`.

## Gotchas (from the code + comments)
- **`funded` — not `paid` — unlocks buying.** An order can be `status='paid'` yet `funded=0` (authorized
  but not settled). The gate checks `funded`. Don't collapse the two states.
- **Auto-fulfill OFF is the safe default and should stay off until proven.** Flipping `auto_fulfill=1`
  without a real connector doesn't buy anything (records `awaiting_connector`); flipping it on WITH a
  connector wired at L157-158 starts spending money — treat that as a money-moving change (operator gate).
- **Box + digital lines are excluded from supplier purchase** (L141: `is_box=0 AND is_digital=0`). If you
  add a new non-purchasable line type, exclude it here too or fulfillment will try to buy a phantom.
- **`fulfillOrder` reconciles finance first** (L117) so the PO cost reflects current settings — but it
  does NOT verify the customer actually paid beyond the `funded` flag. Whatever sets `funded=1` is your
  real fund gate; make sure it's the settlement signal, not a hopeful default.
- **Overhead is blended, per-order.** `overhead_bps` is meant for blended ad-spend/CAC; it's a modeling
  estimate, not a booked expense. Net profit is only as honest as that input.
- **Fulfillment is demand-driven in the source** — `fulfillOrder` runs on the admin POST, not a cron.
  If you want hands-off fulfillment of funded orders, add a cron that walks `funded=1, fulfillment_status
  IN ('unfulfilled','awaiting_funds')` and calls `fulfillOrder` (still governed by the two rules).
