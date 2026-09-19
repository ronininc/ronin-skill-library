---
name: installment-financing-intent
description: >-
  A thin, store-settings-driven financing-INTENT layer for a commerce CRM: on eligible storefront orders
  (total ≥ a configured minimum, split over up to a configured max number of months) it records a
  `payment_plan='installments'` with an installment count and per-installment cents on the order —
  delegating the ACTUAL charging to the payment rail (Shop Pay Installments / Klarna via Shopify). It
  records intent + schedule only; it does not move money. Use WHENEVER a build needs "pay in installments",
  "buy now pay later / BNPL intent", "0% financing on orders over $X", "split payment into N months",
  "offer a payment plan", or "record an installment schedule on the order". COMPLEMENTS commerce-spine
  (the storefront order path where the plan is attached during `publicCreateOrder`) and shopify-order-bridge
  / the payment rail (which performs the real installment charging) — do NOT implement a charging engine
  here; this is the schedule-recording delta only. Guardrails: this NEVER charges a card (the rail does),
  the fund gate still holds for physical goods (materials bought only once collected funds cover COGS —
  a digital kit's carries no COGS so a first installment funds it safely), and eligibility is gated on a
  store-settings minimum + max-months clamp.
---
# Installment / Financing Intent

## What it is / when to use
A few columns and a dozen lines that let a storefront offer "pay in N months" without building a lender.
When the buyer opts into installments and the order qualifies, the CRM stamps the plan and a per-payment
amount onto the order; the real charging is the payment rail's job (Shop Pay Installments, Klarna, etc.).
It exists so the store can surface and record a financing option honestly — schedule and intent captured
in D1, money movement left to the licensed rail.

**Composes with:** `commerce-spine` (the `publicCreateOrder` path attaches the plan right after the order
is created and P&L booked), `order-pnl-fund-gate-fulfillment` (the fund gate is unchanged — a plan doesn't
let you buy materials before collected funds cover COGS), and `shopify-order-bridge` / the payment rail
(which actually charges the installments). This skill owns **eligibility + schedule recording only** — no
charging, no ledger of collected installments.

## Reference implementation (ronininc)
Confirmed read:
- Migration `0050_store_financing.sql`:
  - `store_settings.financing_enabled` (default 1), `financing_max_months` (default 2 — "0% up to 2 months"),
    `financing_min_cents` (default 15000 — offer plans on $150+).
  - `store_orders.payment_plan` (`'full' | 'installments'`, default `'full'`), `installments` (default 1),
    `installment_cents` (default 0).
  - Header comment states the boundaries: "Actual installment CHARGING runs on the payment rail … this
    records intent + schedule. The fund gate still holds."
- `worker/commerce.ts` L235-245 — inside `publicCreateOrder`, after `reconcileOrderFinance`:
  - only if the request opted in (`payment_plan === 'installments'`);
  - read `financing_enabled/financing_max_months/financing_min_cents` from `store_settings`;
  - eligibility: `financing_enabled && total_cents >= financing_min_cents`;
  - `months = clamp(round(requested), 2 .. financing_max_months)`; `per = ceil(total_cents / months)`;
  - `UPDATE store_orders SET payment_plan='installments', installments=?, installment_cents=?`;
  - return `plan = { months, installment_cents: per }` (or `null` when ineligible / not requested).
- Surfaced read-only in `worker/fulfillment.ts` L206 — `storeFeed`'s recent-orders select includes
  `payment_plan` so the money feed shows which orders are on a plan.

## How to reapply it
1. **Schema.** Apply `0050`: the three `store_settings` financing columns + the three `store_orders` plan
   columns. Set `financing_min_cents` / `financing_max_months` to the client's policy.
2. **Storefront opt-in.** The checkout sends `payment_plan:'installments'` and an `installments` count.
   Inline the L235-245 block into commerce-spine's `publicCreateOrder` (after the P&L reconcile).
3. **Clamp + compute server-side.** Never trust the client's month count or per-payment amount: clamp
   `months` to `2..financing_max_months`, and compute `per = ceil(total/months)` on the server.
4. **Connect the rail for real charging.** The plan is intent only. Wire Shop Pay Installments / Klarna
   (via Shopify or the gateway) to actually collect. This CRM records the schedule; the rail moves money.
5. **Keep the fund gate.** For physical goods, don't fulfill/buy materials until collected funds cover
   COGS (order-pnl-fund-gate-fulfillment's `funded` gate). Digital kits carry no COGS, so a first
   installment funds them safely.

## Gotchas (from the code + comments)
- **This charges nothing.** It writes `payment_plan/installments/installment_cents` and returns a schedule.
  If you ship it without wiring a real installment rail, you've promised a plan you can't collect. The
  charging integration is required, not optional.
- **`per = ceil(total/months)`** means the sum of installments can slightly exceed the total (rounding up).
  Reconcile the last payment against the real total on the rail, or the customer overpays by a few cents.
- **Eligibility is store-settings-gated, both ways.** `financing_enabled=0` or `total < financing_min_cents`
  → no plan (returns `null`), and `months` is clamped to `financing_max_months`. Don't let the client widen
  either bound by request.
- **The fund gate is not relaxed by a plan.** A financed physical order is still `funded`-gated for COGS.
  Only digital (no-COGS) lines are safe to deliver on a first installment. Don't buy materials against a
  promise of future installments.
- **It's intent, so the P&L books full revenue on the order.** `computeFinance` uses `subtotal_cents`, not
  collected-to-date — a financed order shows full revenue immediately. If you need cash-basis accounting,
  that's a separate collected-installments ledger this layer intentionally does not build.
