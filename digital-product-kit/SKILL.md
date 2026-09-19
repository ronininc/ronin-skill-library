---
name: digital-product-kit
description: >-
  A near-100%-margin DIGITAL product class alongside physical dropship in a commerce CRM: a product
  flagged `is_digital=1` with a `delivery` mode (download | repo | license) has no supplier and no
  shipping, so its only cost is the payment fee — but the FUND GATE still holds (the paid file is handed
  over only after payment settles). Fulfillment records a distinct `'(digital)'` leg and marks the order
  delivered without ever grouping the line into a supplier purchase. Use WHENEVER a commerce build sells
  "digital products", "downloads", "a kit/template/course/license", "software or a repo as a product",
  "self-serve digital tier", or "sell a file, not a shipped item". COMPLEMENTS commerce-spine (which owns
  the catalog + product CRUD this flag lives on) and order-pnl-fund-gate-fulfillment (whose `fulfillOrder`
  contains the digital-delivery branch and whose fund gate still governs when the file is released) — do
  NOT re-implement the catalog or the P&L/fulfillment engine here; this is only the digital-line delta.
  Guardrails: digital lines are excluded from supplier grouping (nothing is "bought"), the fund gate is
  NOT bypassed (deliver on settled funds), and margin honesty means cost_cents stays 0 (fee still books).
---
# Digital Product Kit

## What it is / when to use
A small schema + fulfillment delta that lets the same store sell files/licenses next to physical goods.
A digital SKU has `is_digital=1`, `cost_cents=0`, and a `delivery` mode; when its order is funded,
fulfillment delivers it (a `'(digital)'` fulfillment leg) instead of placing a supplier purchase. It
exists so a store can offer a self-serve, near-100%-margin tier (kits, templates, licenses) without
inventing a second checkout or bypassing the money rules.

**Composes with:** `commerce-spine` (the catalog + product CRUD where `is_digital`/`delivery` are stored
and shown), `order-pnl-fund-gate-fulfillment` (the digital branch lives inside its `fulfillOrder`; the
fund gate still decides *when* the file is released), and `money-feed-health-monitor` (whose "start
working" queue surfaces paid-but-undelivered digital/kit sales). This skill owns **the digital line type
+ its fulfillment branch only**.

## Reference implementation (ronininc)
Confirmed read:
- Migration `0049_store_digital_kits.sql` — adds `products.is_digital INTEGER NOT NULL DEFAULT 0` and
  `products.delivery TEXT` (`'download' | 'repo' | 'license'`). Digital SKUs are seeded with
  `cost_cents=0`, `dropship=0`, `box_eligible=0`. (Header comment states the rule outright: "no supplier,
  no shipping, ~100% margin; delivered by download once payment settles — the fund gate still holds.")
- `worker/fulfillment.ts` L126-136 — the delivery branch inside `fulfillOrder`, **after** the fund gate
  (L120-124), so a digital line is delivered only when the order is funded:
  - counts order items joined to `products` where `is_digital=1` (L127-129);
  - if any, inserts a `store_fulfillments` row `supplier='(digital)'`, `cost_cents=0`, `status='purchased'`,
    `auto=1`, `funded_by_order=1`, note "Digital kit — delivered by download on payment." (L132-135).
  - Physical supplier grouping L138-142 excludes digital: `COALESCE(p.is_digital,0)=0` (and boxes).
  - Final status L162: if there are no physical lines but a digital line, the order is `'delivered'`.
- `worker/commerce.ts` L186 — `publicProduct` selects `is_digital,delivery` (plus quality/rating) so the
  storefront detail page can render "instant download / license" instead of shipping.
- Cross-refs: shopify-order-bridge (`worker/shopify-ingest.ts` L67) flags a line `crmPack` when
  `is_digital=1 OR category='KITS'`; money-feed-health-monitor (`fulfillment.ts` L211-218) builds the
  "start working" queue from `is_digital=1 OR category='KITS'` sales not yet delivered.

## How to reapply it
1. **Schema.** Apply `0049`: add `is_digital` + `delivery` to commerce-spine's `products`. Seed digital
   SKUs with `cost_cents=0`, `dropship=0`, and `box_eligible=0` (a digital item never goes in a physical box).
2. **Product CRUD.** Extend the admin `saveProduct` form/handler to set `is_digital` and pick a `delivery`
   mode. Show the digital badge on the storefront by selecting `is_digital,delivery` in the product read.
3. **Fulfillment branch.** Ensure `order-pnl-fund-gate-fulfillment`'s `fulfillOrder` includes the L126-136
   digital branch AND the `is_digital=0` exclusion in the physical supplier grouping (L141). Without both,
   a digital line would either be skipped or wrongly sent to a supplier.
4. **Actual delivery.** The source records the delivery leg but the file hand-off itself (a signed R2
   download URL, a repo invite, a license key issue) is the integration you add where the `'(digital)'`
   row is written — gate it on `funded=1` (the branch already runs post-gate).
5. **Surface undelivered.** Wire money-feed-health-monitor's "start working" queue so paid digital/kit
   sales that aren't delivered yet show up for the operator.

## Gotchas (from the code + comments)
- **The fund gate is NOT bypassed for digital.** The branch runs *after* the L120-124 gate, so a digital
  file is released only once `funded=1`. Cheap to deliver ≠ free to give away pre-payment — keep the
  actual download/license issue behind the funded check.
- **`cost_cents=0` is a margin claim, not zero cost.** The payment fee still books in `computeFinance`,
  so net margin is ~ (100% − fee), not literally 100%. Don't let the "~100% margin" label leak into the
  P&L as zero fees.
- **Exclude digital from supplier grouping AND from boxes.** `is_digital=0` in the physical group query
  and `box_eligible=0` on the SKU — miss either and you'll try to "buy" a file from a supplier or pack it
  into a value box.
- **`delivery` is a mode, not a mechanism.** `'download'|'repo'|'license'` only labels how it ships; you
  still implement each hand-off. An order can be marked `'delivered'` (L162) before you've wired real
  delivery — don't ship that half-built.
- **Mixed orders resolve to the physical target.** If an order has both physical and digital lines, the
  final `fulfillment_status` follows the physical `target` (L162), and the digital leg is delivered
  alongside — verify your delivery still fires for the digital line in a mixed cart.
