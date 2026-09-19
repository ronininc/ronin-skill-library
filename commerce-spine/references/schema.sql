-- commerce-spine — per-site master-node schema (Cloudflare D1 / SQLite)
-- House invariants: money = integer cents; quantity = milli-units (qty_mu, thousandths);
-- tenant_id in every identity; append-only ledgers/event logs; sensitive text AES-GCM at rest
-- (marked "-- ENC"); PAID / refund succeeded only from a verified gateway webhook.
--
-- Apply as numbered migrations (0001_init.sql, 0002_..., additive) exactly like
-- slik-team-board/worker/migrations and pineapple-disposables/worker/migrations.
-- SQLite PRAGMAs (set by the Worker, not here): WAL, synchronous=FULL, foreign_keys=ON.
--
-- D1 10 GB PER-DATABASE LIMIT: a node grows past it by spreading customers across
-- multiple D1 databases (DB, DB_1, DB_2, …). The ENTITY tables below are identical
-- on every shard; the routing registry (shard_catalog / shard_routes / media_objects)
-- lives ONLY on shard 0 and ships in schema-sharding.sql (apply as 0002_sharding.sql).
-- See references/sharding.md + crm-shard-router.mjs. Big blobs never go in a row
-- (2 MB row cap) — they go to R2 via r2-offload.mjs with a media_objects pointer.

------------------------------------------------------------------------------- tenancy + integrations
CREATE TABLE integration_bindings (
  binding_id     TEXT PRIMARY KEY,        -- ${provider}__${tenant_id}__${account}
  tenant_id      TEXT NOT NULL,
  provider       TEXT NOT NULL,           -- clover | stripe | square | authnet | toast
  mode           TEXT NOT NULL,           -- driver | peer
  account        TEXT NOT NULL DEFAULT 'default',
  catalog_source TEXT NOT NULL DEFAULT 'db',   -- db (spine master, 15k bypass) | processor
  readiness      TEXT NOT NULL DEFAULT 'NOT_CONFIGURED', -- capability-readiness state
  config_json    TEXT,                    -- ENC (host, ids; NEVER card data / raw secrets)
  created_at     INTEGER NOT NULL,
  updated_at     INTEGER NOT NULL
);
CREATE UNIQUE INDEX ix_binding_unique ON integration_bindings(tenant_id, provider, account);

------------------------------------------------------------------------------- catalog (unlimited — the bypass)
CREATE TABLE products (
  product_id     TEXT PRIMARY KEY,        -- ${tenant_id}:product:${sku}
  tenant_id      TEXT NOT NULL,
  sku            TEXT NOT NULL,
  name           TEXT NOT NULL,
  category       TEXT,
  active         INTEGER NOT NULL DEFAULT 1,
  hot_set        INTEGER NOT NULL DEFAULT 0,   -- 1 = currently synced into the POS working window
  clover_item_id TEXT,                    -- POS id when mirrored; NULL when DB-only long tail
  stock_qty_mu   INTEGER NOT NULL DEFAULT 0,   -- CACHE ONLY; inventory_ledger is the truth
  reorder_at_mu  INTEGER,
  supplier_id    TEXT,
  notes          TEXT,                    -- ENC
  created_at     INTEGER NOT NULL,
  updated_at     INTEGER NOT NULL
);
CREATE UNIQUE INDEX ix_products_sku ON products(tenant_id, sku);
CREATE INDEX ix_products_hotset ON products(tenant_id, hot_set) WHERE hot_set = 1;

CREATE TABLE product_prices (            -- tiered / multi-currency
  price_id     TEXT PRIMARY KEY,
  tenant_id    TEXT NOT NULL,
  product_id   TEXT NOT NULL REFERENCES products(product_id),
  currency     TEXT NOT NULL DEFAULT 'USD',
  price_type   TEXT NOT NULL DEFAULT 'FIXED',  -- FIXED | PER_UNIT
  amount_cents INTEGER NOT NULL,
  min_qty_mu   INTEGER NOT NULL DEFAULT 1000,
  created_at   INTEGER NOT NULL
);
CREATE INDEX ix_prices_product ON product_prices(product_id, currency);

-- append-only truth of every stock movement
CREATE TABLE inventory_ledger (
  entry_id    TEXT PRIMARY KEY,
  tenant_id   TEXT NOT NULL,
  product_id  TEXT NOT NULL REFERENCES products(product_id),
  delta_mu    INTEGER NOT NULL,           -- signed; negative = sold/consumed
  reason      TEXT NOT NULL,              -- sale | restock | adjust | peer_sync | recipe_deduct
  ref_kind    TEXT,                       -- order | refund | webhook | manual
  ref_id      TEXT,
  at          INTEGER NOT NULL
);
CREATE INDEX ix_ledger_product ON inventory_ledger(product_id, at);

------------------------------------------------------------------------------- CRM
CREATE TABLE customers (
  customer_id  TEXT PRIMARY KEY,          -- ${tenant_id}:customer:${key}
  tenant_id    TEXT NOT NULL,
  display_name TEXT,                      -- ENC
  email        TEXT,                      -- ENC
  phone        TEXT,                      -- ENC
  source       TEXT,                      -- web | pos | toast_peer | import
  first_seen   INTEGER NOT NULL,
  last_seen    INTEGER NOT NULL,
  lifetime_cents INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_customers_tenant ON customers(tenant_id, last_seen);

CREATE TABLE customer_events (           -- append-only CRM history
  event_id    TEXT PRIMARY KEY,
  tenant_id   TEXT NOT NULL,
  customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  kind        TEXT NOT NULL,             -- order | visit | message | note | loyalty
  detail_json TEXT,                      -- ENC
  at          INTEGER NOT NULL
);
CREATE INDEX ix_custevents ON customer_events(customer_id, at);

------------------------------------------------------------------------------- orders + tenders
CREATE TABLE orders (
  order_id     TEXT PRIMARY KEY,          -- ${tenant_id}:order:${key}
  tenant_id    TEXT NOT NULL,
  customer_id  TEXT REFERENCES customers(customer_id),
  status       TEXT NOT NULL DEFAULT 'DRAFT', -- DRAFT|AWAITING_PAYMENT|PAID|FULFILLING|FULFILLED|CANCELLED
  currency     TEXT NOT NULL DEFAULT 'USD',
  subtotal_cents   INTEGER NOT NULL DEFAULT 0,
  surcharge_cents  INTEGER NOT NULL DEFAULT 0,  -- surcharge / cash-discount delta
  tip_cents        INTEGER NOT NULL DEFAULT 0,
  tax_cents        INTEGER NOT NULL DEFAULT 0,
  total_cents      INTEGER NOT NULL DEFAULT 0,
  captured_cents   INTEGER NOT NULL DEFAULT 0,  -- what actually settled (bounds refunds)
  clover_order_id  TEXT,
  created_at   INTEGER NOT NULL,
  updated_at   INTEGER NOT NULL
);
CREATE INDEX ix_orders_status ON orders(tenant_id, status, updated_at);

CREATE TABLE order_lines (
  line_id     TEXT PRIMARY KEY,
  tenant_id   TEXT NOT NULL,
  order_id    TEXT NOT NULL REFERENCES orders(order_id),
  product_id  TEXT REFERENCES products(product_id),
  name_snap   TEXT NOT NULL,             -- snapshot at sale time
  qty_mu      INTEGER NOT NULL,
  unit_cents  INTEGER NOT NULL,
  line_cents  INTEGER NOT NULL
);
CREATE INDEX ix_lines_order ON order_lines(order_id);

CREATE TABLE tenders (                   -- the CHARGE side (one order may have >1 attempt)
  tender_id        TEXT PRIMARY KEY,
  tenant_id        TEXT NOT NULL,
  order_id         TEXT NOT NULL REFERENCES orders(order_id),
  gateway          TEXT NOT NULL,        -- stripe | square | authnet | clover
  gateway_ref      TEXT,                 -- session / paymentIntent / transaction id
  amount_cents     INTEGER NOT NULL,
  currency         TEXT NOT NULL DEFAULT 'USD',
  status           TEXT NOT NULL DEFAULT 'PENDING', -- PENDING|AUTHORIZED|CAPTURED|VOIDED|FAILED
  captured_cents   INTEGER NOT NULL DEFAULT 0,     -- supports partial capture
  vault_token      TEXT,                 -- gateway saved-card token (NOT a PAN) — ENC
  created_at       INTEGER NOT NULL,
  updated_at       INTEGER NOT NULL
);
CREATE INDEX ix_tenders_order ON tenders(order_id);

------------------------------------------------------------------------------- REFUND SCHEMA (standard)
CREATE TABLE refunds (
  refund_id       TEXT PRIMARY KEY,       -- ${tenant_id}:refund:${key}
  tenant_id       TEXT NOT NULL,
  order_id        TEXT NOT NULL REFERENCES orders(order_id),
  tender_id       TEXT NOT NULL REFERENCES tenders(tender_id),
  gateway         TEXT NOT NULL,
  gateway_refund_id TEXT,                 -- id returned by the processor
  kind            TEXT NOT NULL,          -- full | partial
  amount_cents    INTEGER NOT NULL CHECK (amount_cents > 0),
  currency        TEXT NOT NULL DEFAULT 'USD',
  reason_code     TEXT NOT NULL DEFAULT 'other',
    -- requested_by_customer | duplicate | fraudulent | item_returned | not_as_described
    -- | price_adjustment | canceled_order | goodwill | other
  reason_note     TEXT,                   -- ENC
  status          TEXT NOT NULL DEFAULT 'requested',
    -- requested | approved | processing | succeeded | failed | canceled
  requested_by    TEXT,                   -- actor (user id)
  approved_by     TEXT,
  failure_reason  TEXT,
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL,
  processed_at    INTEGER
);
CREATE INDEX ix_refunds_order ON refunds(order_id, status);
CREATE INDEX ix_refunds_tender ON refunds(tender_id);

-- append-only refund lifecycle log (status transitions come through here)
CREATE TABLE refund_events (
  event_id    TEXT PRIMARY KEY,
  tenant_id   TEXT NOT NULL,
  refund_id   TEXT NOT NULL REFERENCES refunds(refund_id),
  from_status TEXT,
  to_status   TEXT NOT NULL,
  actor       TEXT,                       -- user id | 'webhook'
  detail_json TEXT,                       -- ENC
  at          INTEGER NOT NULL
);
CREATE INDEX ix_refund_events ON refund_events(refund_id, at);

-- REFUND INVARIANTS (enforced in the Worker, same transaction):
--  1. status='succeeded' is written ONLY from a verified gateway webhook (actor='webhook').
--  2. SUM(succeeded refunds for an order) <= orders.captured_cents  (over-refund guard).
--  3. every status change appends a refund_events row; refunds is never updated silently.
--  4. a succeeded refund that returned stock writes a matching inventory_ledger row (reason='restock').

------------------------------------------------------------------------------- webhooks (idempotent + loop-safe)
CREATE TABLE webhook_events (
  dedupe_key  TEXT PRIMARY KEY,           -- ${mId}:${objectId}:${type}:${ts}
  tenant_id   TEXT NOT NULL,
  provider    TEXT NOT NULL,
  origin      TEXT,                       -- 'external' | 'self' (guards self-inflicted sync loops)
  payload_json TEXT,
  received_at INTEGER NOT NULL
);
