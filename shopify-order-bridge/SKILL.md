---
name: shopify-order-bridge
description: >-
  An HMAC-verified Shopify `orders/create` webhook that lands each live Shopify sale in a sovereign
  Worker+D1 CRM: it verifies Shopify's signature (constant-time), maps each line item to the CRM catalog
  by SKU (so REAL cost + margin book, not just the sale price), is idempotent on `supplier_order_ref`
  = `shopify:<id>` (survives Shopify redelivery), records the order PAID + funded=1, reconciles the
  per-order P&L, and flags any CRM-pack/digital line so a companion can raise a "start working" alert.
  Use WHENEVER a build needs "import Shopify orders", "Shopify webhook into the CRM", "sync sales from
  Shopify", "use Shopify as the card rail but own the data", "book margin on Shopify orders", or "land
  live sales in D1". COMPLEMENTS commerce-spine (the sovereign catalog + orders it writes into; Shopify is
  only the payment rail while D1 stays the source of truth), order-pnl-fund-gate-fulfillment (whose
  `reconcileOrderFinance` it calls to book the P&L — and note it lands orders funded=1 but does NOT itself
  fulfill), and signed-webhook-intake (the generic HMAC/idempotency primitive this specializes). Do NOT
  re-implement the catalog, P&L, or the generic webhook primitive here — this is the Shopify-mapping
  delta only. Guardrails: no secret → 503 (never trust an unsigned body), bad signature → 401,
  idempotent on redelivery, SKU-map for real cost, and Shopify money is a dollar STRING (coerce to cents).
---
# Shopify Order Bridge

## What it is / when to use
A single inbound endpoint that turns "a sale happened on Shopify" into a fully-booked CRM order with real
cost and margin. It exists for the pattern where the merchant wants Shopify's checkout/card rail but wants
to OWN the customer + order + margin data in their own D1 (Shopify closed as a data silo, D1 as the source
of truth). It verifies the webhook, maps SKUs to the local catalog for true COGS, dedupes redelivery, and
books the P&L.

**Composes with:** `commerce-spine` (writes `store_orders` + `store_order_items`; the local catalog's
SKUs are what make the mapping meaningful), `order-pnl-fund-gate-fulfillment` (calls its
`reconcileOrderFinance`; the imported order is `paid,funded=1` so it's fund-gate-clear to fulfill —
but this bridge does NOT call `fulfillOrder`), `signed-webhook-intake` (the constant-time HMAC + idempotency
primitives, here specialized to Shopify's header + money format), and `digital-product-kit` /
`money-feed-health-monitor` (the `crm_pack` flag feeds the "start working" queue). This skill owns
**Shopify signature + line→catalog mapping + idempotent order landing only**.

## Reference implementation (ronininc)
Confirmed read — `worker/shopify-ingest.ts` L1-86:
- `verifyHmac()` L22-32 — `crypto.subtle` HMAC-SHA256 over the raw body, base64-compared **constant-time**
  (length check + XOR-accumulate) against the `X-Shopify-Hmac-Sha256` header. Any error → false.
- `cents()` L20 — **Shopify money is a dollar string** (`"48.70"`); `round(Number(v)·100)`. Using `str()`
  would drop a numeric — the code coerces explicitly (see the `id` note below).
- `shopifyWebhook()` L34-86:
  - Config gate L35-36: no `env.SHOPIFY_WEBHOOK_SECRET` → **503** (never trust an unsigned body).
  - Read raw text L37, verify L38-39 → bad signature **401**.
  - **Idempotency** L44-50: `shopId = String(o.id)` (Shopify sends `id` as a NUMBER — coerced explicitly,
    falls back to `admin_graphql_api_id`); if a `store_orders` row already has `supplier_order_ref =
    'shopify:'+shopId`, return `{ok:true, duplicate:true}` — survives redelivery.
  - **SKU mapping** L57-71: for each `line_item`, look up `products WHERE sku=?` to get `id`, `cost_cents`,
    and the kit flag (`is_digital=1 OR category='KITS'` → `crmPack=true`). Subtotal from line price·qty,
    falling back to `o.total_price`/`o.current_total_price` if empty.
  - **Land the order** L74-83: insert `store_orders` with `status='paid'`, `funded=1`, `paid_at=now`,
    `supplier_order_ref='shopify:'+shopId`; batch-insert `store_order_items` (with `product_id`, real
    `cost_cents`, `sku`).
  - **Book P&L** L84: `reconcileOrderFinance(env, id)`. Returns `{ok, order_no, crm_pack}`.
- Migration `0045_store_shopify_seam.sql` — adds `store_settings.shopify_domain` and
  `products.shopify_variant_id` (for `/cart` permalinks). (The order landing reuses commerce-spine's
  `store_orders`/`store_order_items` + the finance columns from `0046`; `supplier_order_ref` is the
  idempotency key.)
- Route: `worker/index.ts` L68 — `POST /api/store/shopify/webhook → shopifyWebhook` (HMAC-gated, **not**
  behind admin auth — the signature IS the auth).

## How to reapply it
1. **Schema.** Apply `0045` (adds `shopify_domain` + `shopify_variant_id`). You also need commerce-spine's
   `store_orders`/`store_order_items` and the `0046` finance columns (`funded`, `cogs_cents`, etc.) for
   `reconcileOrderFinance` to write.
2. **Drop in `shopify-ingest.ts`.** Set the secret: `wrangler secret put SHOPIFY_WEBHOOK_SECRET` = the
   webhook's signing secret from the Shopify admin.
3. **Route it public + unauthenticated.** `POST /api/store/shopify/webhook` must be reachable without a
   session (the HMAC is the credential). Point the Shopify `orders/create` webhook at it.
4. **Populate SKUs.** The mapping only books real cost when the CRM's `products.sku` matches Shopify's
   line-item `sku`. Keep them in sync (a line with no matching SKU lands with `cost=0` → 100%-looking margin).
5. **Decide fulfillment.** This bridge books finance but does NOT fulfill (see gotcha). If you want the
   imported order to flow, call `fulfillOrder(env, id)` after `reconcileOrderFinance` — it's already
   `funded=1` so the fund gate passes — or leave it for the operator/cron.

## Gotchas (from the code + comments)
- **It books P&L but does NOT fulfill.** `shopifyWebhook` calls `reconcileOrderFinance`, not `fulfillOrder`.
  An imported order sits `paid,funded=1,fulfillment_status='unfulfilled'` until something fulfills it. If
  you expect auto-fulfillment, wire it in step 5 — don't assume the webhook does it.
- **Shopify `id` is a number, money is a string.** Two opposite coercion traps in one payload: `String(o.id)`
  for the idempotency key (a bare `str()` drops the numeric), `Number(v)·100` for money (it's `"48.70"`,
  not cents). Keep both explicit.
- **Idempotency depends on `supplier_order_ref`.** The dedupe check reads `store_orders.supplier_order_ref
  = 'shopify:'+id`. If another code path overwrites that column, redelivered webhooks will double-insert.
  Reserve the `shopify:` prefix for this.
- **No secret = 503, bad sig = 401 — never process an unverified body.** Don't add a "dev mode" that skips
  verification; the endpoint is public and the signature is the only auth.
- **Unmapped SKUs book zero cost.** A Shopify line whose SKU isn't in the catalog lands `cost=0`, inflating
  margin and hiding a real loss (capital-leak-breaker won't catch it — it only scans catalog `products`).
  Alert on unmapped lines or require SKU parity.
- **`crm_pack` is a flag, not delivery.** It only marks the order for the "start working" queue; the actual
  digital hand-off is digital-product-kit's job.
