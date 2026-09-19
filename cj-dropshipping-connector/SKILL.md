---
name: cj-dropshipping-connector
description: >-
  A supplier-SIDE dropship fulfillment + catalog connector for CJ Dropshipping's open API — the
  outbound leg that turns a paid store order into a real supplier purchase with tracking, and pulls
  supplier catalog/cost for publishing. It is the concrete "connector" that order-pnl-fund-gate-
  fulfillment records as `awaiting_connector`: authenticate (cache the ~15-day/24h access token,
  never re-auth per call), obey a HARD QPS=1 rate budget (serialize every call through one queue),
  query products for landed cost, and on a FUNDED order create the supplier order + subscribe to the
  fulfillment/tracking webhook so the tracking number flows back to the customer. Use WHENEVER a
  dropship/commerce build needs "connect CJ Dropshipping", "auto-fulfill orders through a supplier",
  "supplier create-order + tracking", "pull supplier catalog/cost", "wire the dropship supplier", or
  "the fulfillment connector the fund-gate is waiting for". COMPLEMENTS order-pnl-fund-gate-fulfillment
  (buyer-side P&L + fund-gate + money-never-auto — this is the supplier connector it drives, NOT the
  gate itself), commerce-spine (the sovereign catalog/orders the supplier ref links into), and
  shopify-order-bridge (INBOUND sale from a card rail — this is the OPPOSITE, OUTBOUND leg to the
  supplier). Do NOT re-implement the P&L, fund gate, or catalog here — this is only the supplier
  API delta. STATUS: design/spec-stage in the source repo (blueprint, not yet built) — bindings below.
---
# CJ Dropshipping Supplier Connector

## What it is / when to use / what it composes with
The **outbound supplier leg** of a sovereign dropship CRM. The house stack already owns the
buyer side: `commerce-spine` (catalog, cart, orders), `order-pnl-fund-gate-fulfillment` (per-order
P&L + the FUND GATE that forbids buying stock before the customer's money settles, and
`money-never-auto` which parks armed-but-unconnected fulfillment as `awaiting_connector`). This skill
is the **connector that satisfies that `awaiting_connector` state** for one real supplier network:
CJ Dropshipping. Two directions of data:

- **Catalog/cost IN** — query CJ for a product's landed cost (item + shipping) so the publish step
  can price at `cost × markup` and the P&L books a real COGS, not a guess.
- **Order OUT** — when an order is `PAID + funded=1`, create the CJ supplier order, then receive the
  CJ webhook and push the tracking number back onto the store order for the customer.

Reach for it only when the operator has an approved CJ account and the fund gate is armed. It does
NOT decide whether to fulfill (that is `order-pnl-fund-gate-fulfillment`); it only executes the
purchase once told to.

## Reference (design source — no implementation exists yet; this captures the verified design + bindings)
- `drop-shipping-store/BUILD_AND_GTM.md:27` — "**CJ open API** (CJ = the vetted agent) · $0 (pay per
  order) · QPS = 1 (queue/cache 24h token)" — the auth+rate discipline that defines this connector.
- `drop-shipping-store/BUILD_AND_GTM.md:30` — "Auto-fulfill · **CJ create-order + webhooks** (tracking)
  · pay per order · QPS = 1" — the outbound order + tracking-webhook flow.
- `drop-shipping-store/BUILD_AND_GTM.md:26` — "Margin · **computed**: retail − (CJ cost + shipping)" —
  landed-cost is item cost PLUS shipping, both from CJ.
- `drop-shipping-store/BUILD_AND_GTM.md:29,38` — "Auto-publish → our CF Workers + D1 store (POST→INSERT
  we own)" and "Fulfillment worker: on order → CJ create-order → webhook → tracking to customer".
- `drop-shipping-store/FEASIBILITY.md:36-37` — the honest gate: "do NOT promise 'automatic
  dropshipping' until a distributor/supplier account is approved and blind-ship is proven end-to-end
  … 'order → supplier **routing**' (auto-formatted PO), not 'the dropship part runs itself.'"
- `drop-shipping-store/FEASIBILITY.md:29` — seller-of-record / blind-ship compliance (see Gotchas).

CJ API docs: https://developers.cjdropshipping.com/en/api/start/

## How to reapply

### 1. Token cache (the rate/auth discipline is the whole point)
CJ issues an access token from `POST /authentication/getAccessToken` (email + api key). The token is
long-lived (do NOT re-auth per request — CJ rate-limits auth hard). Cache it:
```sql
-- migration: supplier auth + order link (add to the commerce-spine D1 node)
CREATE TABLE IF NOT EXISTS supplier_auth (
  supplier      TEXT PRIMARY KEY,        -- 'cj'
  access_token  TEXT NOT NULL,
  expires_at    INTEGER NOT NULL         -- unix seconds; refresh a few hours early
);
CREATE TABLE IF NOT EXISTS supplier_order_link (
  store_order_id     TEXT PRIMARY KEY REFERENCES store_orders(id),
  supplier           TEXT NOT NULL,       -- 'cj'
  supplier_order_ref TEXT UNIQUE,         -- CJ order id → idempotency key
  status             TEXT NOT NULL,       -- 'created'|'shipped'|'delivered'|'failed'
  tracking_number    TEXT,
  tracking_carrier   TEXT,
  last_error         TEXT,
  created_at         INTEGER NOT NULL
);
```
Prefer KV or a single D1 row for the token; refresh on a scheduled tick or lazily when `expires_at`
is within a safety window.

### 2. One serialized call path — enforce QPS=1
Every CJ call (catalog, order, tracking) goes through ONE function that guarantees at most one
in-flight request per second. Two safe shapes:
- **Cron-drained work queue** (preferred, composes with `d1-work-queue`): handlers enqueue a
  `cj_task`; a scheduled Worker drains ONE task per invocation (or sleeps ≥1s between). This makes
  QPS=1 structural, not hopeful, and survives bursts of orders.
- **In-Worker mutex** for read paths: a module-level promise chain that spaces calls ≥1000ms.
Never fan out CJ calls in `Promise.all` — QPS=1 means concurrency 1.

### 3. Handlers
- `getCjToken(env)` → returns cached token, refreshing via `getAccessToken` when expired.
- `cjProductLandedCost(env, pid, variantOrSku, destCountry)` → CJ product query + freight-calculate;
  returns `{ itemCost, shipping, landed }`. Feed `landed` to the publish price = `landed × markup`
  and to the P&L COGS.
- `cjCreateOrder(env, storeOrder)` → called by `order-pnl-fund-gate-fulfillment` ONLY after
  `PAID + funded=1`. Idempotent on `supplier_order_ref` (never double-buy on retry): if a link row
  exists, return it; else create the CJ order, then INSERT the link row with the CJ order id.
- `cjWebhook(request, env)` → verify the payload is from CJ (shared secret / signature — treat like
  `signed-webhook-intake`), map CJ order id → `supplier_order_link`, write `status` + tracking, then
  push tracking onto `store_orders` for the customer (email/SMS via the house comms path).

### 4. Routes / cron wiring
- `POST /webhooks/cj` → `cjWebhook` (public, signature-verified).
- Scheduled trigger (wrangler `[triggers] crons`) → drain the `cj_task` queue at QPS=1; also poll
  tracking for any `created` link older than N hours as a webhook-miss backstop.
- Internal: `order-pnl-fund-gate-fulfillment`'s supplier-purchase leg calls `cjCreateOrder` — this
  skill supplies that function; the gate decides when.

### 5. UI (operator console delta)
On the order row show supplier ref + tracking + `status`, and a manual "Retry supplier order"
(re-invokes the idempotent `cjCreateOrder`) for `failed` rows. Surfaces cleanly in `ops-console` /
`governed-operator-console` — do not build a new console.

## Gotchas (from the source, real)
- **QPS = 1 is a hard ceiling, not a suggestion** (`BUILD_AND_GTM.md:27,30`). Concurrency 1, one
  queue. A burst of paid orders that each fire an immediate CJ call WILL get throttled — enqueue.
- **Token is cached, not per-call.** Re-authing on every request is the classic CJ failure; cache
  and refresh early.
- **Landed cost = item + shipping**, and shipping is destination-dependent (`BUILD_AND_GTM.md:26`).
  Publishing off item cost alone under-prices and eats the margin the P&L thinks it has.
- **Never front COGS.** This connector must only be invoked after the fund gate confirms
  `funded=1` — that rule lives in `order-pnl-fund-gate-fulfillment`, not here; do not add an "auto-buy
  on order created" shortcut.
- **Idempotency on `supplier_order_ref`** — CJ webhooks and your own retries both redeliver; a
  create without the unique link row will double-purchase.
- **Compliance honesty** (`FEASIBILITY.md:36-37,29`): market it as "order → supplier **routing**,"
  not "it runs itself," until blind-ship is proven end-to-end. If you ever resell onto a marketplace
  that enforces **seller-of-record** (e.g. Amazon), only a distributor **blind-ship** (your branding
  on the slip, other branding removed, you own returns) complies — buying-from-a-retailer-to-ship is
  banned. The safe default in the source design is to **publish to your OWN store** and sidestep the
  marketplace rule entirely (`BUILD_AND_GTM.md:32`).
- **Off-network / private-label sourcing has no API** (`BUILD_AND_GTM.md:28`) — that is a human deal
  (Alibaba). Do not model it as a connector; this skill is CJ only.
- **CJ is one supplier, not the abstraction.** If a second supplier is added later, keep this as the
  `cj` adapter behind a thin `supplier` interface; don't overfit the P&L/fund-gate to CJ.
