-- commerce-spine — D1 10 GB bypass: customer-sharded overflow (additive migration)
-- Apply as the next numbered migration on an existing node, e.g. 0002_sharding.sql.
-- Cloudflare D1 caps a SINGLE database at 10 GB, but allows 50,000 databases per
-- account and its OWN documented remedy for "Exceeded maximum DB size" is
-- "shard your data into multiple databases". This schema is the routing brain
-- for that shard set. It lives in shard 0 (the node's primary `DB`) ONLY — the
-- overflow shards (DB_1, DB_2, …) carry the SAME entity tables from schema.sql
-- and none of these three registry tables.
--
-- Model (matches the house doctrine `${tenant_id}:${kind}:${key}`):
--   * Every row belongs to an AGGREGATE ROOT — a customer (crm/orders/tenders/
--     refunds) or a product (catalog/prices/ledger). The root's id IS the shard key.
--   * A root is assigned to a physical shard ONCE, stickily (shard_routes). Adding
--     a shard never remaps existing roots — only NEW roots flow to the new shard.
--   * A root's whole footprint (a customer + their orders + events + tenders) lives
--     in the SAME shard, so "show me this customer" is a single-DB read. D1 cannot
--     join across databases; co-location is what keeps that never necessary.
--   * Tenant-level singletons (integration_bindings, webhook_events) stay in shard 0.

------------------------------------------------------------------------------- physical shards for this node
CREATE TABLE IF NOT EXISTS shard_catalog (
  shard_ix      INTEGER PRIMARY KEY,        -- 0 = primary DB; 1 = DB_1; 2 = DB_2; …
  binding       TEXT NOT NULL,              -- the wrangler env binding name ('DB' | 'DB_1' | …)
  database_name TEXT NOT NULL,              -- '<merchant>-commerce' | '<merchant>-commerce-1' | …
  domain        TEXT NOT NULL DEFAULT 'customer', -- shard-key domain this DB serves (customer | product)
  state         TEXT NOT NULL DEFAULT 'active',   -- active (takes new roots) | readonly (full/draining)
  approx_bytes  INTEGER NOT NULL DEFAULT 0,       -- last observed size; watermark source for auto-split
  created_at    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_shard_catalog_domain ON shard_catalog(domain, state);

------------------------------------------------------------------------------- sticky root -> shard map
CREATE TABLE IF NOT EXISTS shard_routes (
  route_key   TEXT PRIMARY KEY,             -- '${domain}:${root_id}'  (globally unique)
  tenant_id   TEXT NOT NULL,
  domain      TEXT NOT NULL,                -- customer | product | <your custom root kind>
  root_id     TEXT NOT NULL,                -- customer_id | product_id | …
  shard_ix    INTEGER NOT NULL REFERENCES shard_catalog(shard_ix),
  created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_shard_routes_shard ON shard_routes(shard_ix);
CREATE INDEX IF NOT EXISTS ix_shard_routes_tenant ON shard_routes(tenant_id, domain);

------------------------------------------------------------------------------- R2 offload pointers (2 MB row-cap escape)
-- Big bytes (call recordings, attachments, email HTML, images) NEVER live in a D1
-- row — D1 caps a string/BLOB/row at 2 MB and they would burn shard budget fast.
-- They live in R2; D1 stores only this pointer. One row per stored object.
-- This table lives in the SAME shard as its owning root (so a customer's media
-- travels with the customer), NOT only in shard 0.
CREATE TABLE IF NOT EXISTS media_objects (
  media_id    TEXT PRIMARY KEY,             -- ${tenant_id}:media:${key}
  tenant_id   TEXT NOT NULL,
  owner_kind  TEXT NOT NULL,                -- customer | order | customer_event | product | …
  owner_id    TEXT NOT NULL,                -- the aggregate-root id it co-locates with
  r2_key      TEXT NOT NULL,                -- object key in the node's R2 bucket
  content_type TEXT,
  byte_len    INTEGER NOT NULL DEFAULT 0,
  sha256      TEXT,                         -- integrity + dedupe
  meta_json   TEXT,                         -- ENC (caption, source, etc.)
  created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_media_owner ON media_objects(owner_kind, owner_id, created_at);

-- Seed: shard 0 is always the primary DB, always active, customer domain by default.
INSERT OR IGNORE INTO shard_catalog (shard_ix, binding, database_name, domain, state, approx_bytes, created_at)
VALUES (0, 'DB', 'primary', 'customer', 'active', 0, 0);
