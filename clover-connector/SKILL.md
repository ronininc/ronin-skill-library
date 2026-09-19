---
name: clover-connector
description: >-
  The turnkey Worker+D1 CLOVER CONNECTOR class — one isolated `CloverService` that is the ONLY
  place a build talks to Clover, so everything else stays processor-agnostic. It bundles the four
  things a Clover integration actually needs and gets wrong: (1) a DUAL-TOKEN split — the REST/OAuth
  token (inventory/orders/customers sync) and the Ecommerce PRIVATE token (Hosted Checkout) are
  separate secrets on separate hosts that fail independently; (2) PER_UNIT-vs-FIXED item modeling
  where `unitQty` is in THOUSANDTHS (1.5 cases → unitQty 1500, one line item; FIXED splits into
  repeated ≤100-per-request line items); (3) APPLICATION-SIDE idempotency because the v3 Orders API
  has no idempotency-key header (an order with a `clover_order_id` is never re-pushed); (4) DUAL
  ingestion — a signed webhook (constant-time X-Clover-Auth, verification-code echo handshake,
  dedup via a `webhook_events` table, INGEST-ONLY so it never calls back out = no sync loops) AND a
  `modifiedTime>=` poll bridge (ASC backfill, DESC go-forward). Use WHENEVER a build must "connect
  Clover", "sync Clover inventory/orders/customers", "push an order to Clover", "wire the Clover
  webhook", "poll Clover for recent orders", "Clover Hosted Checkout / online card payment", or
  "the Clover connector". This is the CONCRETE connector implementation that COMPLEMENTS
  commerce-spine (the DB-is-source-of-truth doctrine + agnostic-tender seam — Clover is one driver
  behind it; do NOT re-document that here) and clover-operations-command / cloudflare-ordering-worker
  (operator surface + ordering UI — this is the low-level API client beneath them). Guardrails:
  Clover OWNS prices/inventory — the connector READS them to mirror, NEVER writes an item price back;
  Clover requires a User-Agent header; Hosted Checkout is capability-gated (needs the ecommerce token
  AND Clover Ecommerce enabled) and degrades honestly to atomic-order + invoice when off.
---
# clover-connector — the isolated Clover API client (REST sync + Hosted Checkout + webhook/poll)

## What it is / when to use
One class, `CloverService`, that quarantines every Clover call so the rest of the app is
Clover-agnostic. Reach for it the moment a build needs to talk to Clover at all: mirror the catalog,
push an order, take an online card payment, or hear back about paid sales. It is the concrete driver
that plugs into **commerce-spine**'s agnostic-tender seam — build commerce-spine's DB-source-of-truth
node first, then drop this in as the Clover driver. It does NOT own the catalog, the checkout UI, or
the operator console (those are commerce-spine / cloudflare-ordering-worker / clover-operations-command).

## Reference implementation (patterns only, no merchant data)
All in `worker/lib/clover.js`:
- **Dual capability gates** — `get configured` L46 (REST: mId+token) vs `get hostedCheckoutConfigured`
  L48 (ecommerce private token). Two independent secrets so register-sync and online-payment fail apart.
- **`_fetch`** L50–68 — Bearer REST client; sets the required `User-Agent`; throws with status+body.
- **`_lineItems`** L71–90 — the modeling core: PER_UNIT emits ONE line item with `unitQty = qty_mu`
  (thousandths); FIXED splits whole units into repeated line items. This is the item-cap bypass math.
- **`syncOrder`** L98–125 — pushes ONE atomic order (`POST /v3/merchants/{mId}/atomic_order/orders`);
  **application-side idempotency** (skip if `clover_order_id` already set); never throws to the caller,
  records `clover_sync_status` and leaves the local order authoritative + retryable.
- **`createHostedCheckout`** L147–173 — `POST {base}/invoicingcheckoutservice/v1/checkouts` with the
  **ecommerce private token** + `X-Clover-Merchant-Id`; returns `{href, checkoutSessionId, expirationTime}`
  (session expires ~15 min). Tax is deliberately NOT sent per-line — Clover applies the store's own tax.
- **Bulk pagination** — `listItems` L221–233 and `listItemStocks` L191–201 page (limit 500/1000, hard
  stop ~30k) so mirroring scales past the register's ~15k-item ceiling.
- **Poll bridge** — `listRecentOrders(sinceMs, …)` L252–261: `filter=modifiedTime>={ms}`, expands
  lineItems/customers/payments; **ASC for backfill** (new orders append, offsets don't shift),
  **DESC for go-forward** polling.
- **`upsertCustomer`** L268–282 — the ONE thing pushed to Clover besides orders.
- **Webhook** — `verifyWebhook` L286–289 (constant-time `X-Clover-Auth` compare via `timingSafeEqualStr`
  L24–31); `handleWebhook` L296–330: echoes the `verificationCode` handshake, dedups every event on a
  stable key `mId:objectId:type:ts` into `webhook_events` (UNIQUE → dedup), and is **INGEST-ONLY** —
  it hands `orderRefs`/`itemRefs` back to the caller (`O:` = order, `I:` = inventory item) and never
  calls Clover back, so there are no sync loops.

## How to reapply
1. **Secrets:** `CLOVER_API_TOKEN` (REST), `CLOVER_ECOMM_PRIVATE_TOKEN` (Hosted Checkout — different
   token), `CLOVER_WEBHOOK_AUTH` (the dashboard "Auth Code"). Non-secret vars: `CLOVER_BASE_URL`
   (`https://api.clover.com` prod / `apisandbox.dev.clover.com` sandbox), `CLOVER_MERCHANT_ID` (13-char),
   `CLOVER_ITEM_PRICE_TYPE` (`PER_UNIT` default / `FIXED`).
2. **Routes** (see `worker/index.js`): `POST /api/shop/order` L199 (reprice server-side → `createHostedCheckout`
   L249, else `syncOrder` L277 degrade), `POST /api/clover/webhook` L446 (verify → `handleWebhook` → caller
   accrues + invoices `orderRefs`, re-pulls images for `itemRefs`), `GET /api/clover/webhook/status` L480
   (health: auth_secret_set, last_event_at), `POST /api/clover/poll` L539 (cron/manual fallback).
3. **Item mapping:** store the Clover item id in `products.clover_item_id`; leave prices in Clover.

## Gotchas (from the code)
- The webhook **fails closed**: until `CLOVER_WEBHOOK_AUTH` is set, real events return 401 (it captures
  the header for setup). Don't "temporarily" accept unsigned events.
- `setStock` L207–211 tries PUT then falls back to POST on 405 — Clover's docs and tutorials disagree.
- Provider throw ≠ rejection: `syncOrder` records failure and keeps the local order authoritative;
  a Hosted Checkout `expirationTime` is ~15 min, so don't cache the `href`.
- PER_UNIT is the right choice for fractional/large wholesale quantities; FIXED forces whole-unit
  line-item splitting (batch ≤100 per bulk request, ≤2,500 per order).
