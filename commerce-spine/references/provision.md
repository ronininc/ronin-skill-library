# Provisioning a per-site commerce node

The static site (from `website-build-standard`) stays a static site. Commerce-spine adds a **companion
Worker + D1 node** it talks to over `/api/*`. Ships on every business site — empty-ready even for a
brochure, so there's never a retrofit. Template: `slik-team-board/worker` + `pineapple-disposables/worker`.

## 1. Layout (per site)

```
<site>/
├── index.html            # base static site (unchanged)
├── assets/
└── worker/
    ├── index.js          # Worker: serves /api/*, run_worker_first for security headers
    ├── wrangler.jsonc    # D1 binding + PINNED account_id + observability
    ├── migrations/       # 0001_init.sql (references/schema.sql) → additive, numbered
    └── lib/              # clover.js, stripe.js, orders.js, refunds.js, crm.js, money.js, db.js
```

## 2. wrangler.jsonc (generalize the slik shape)

```jsonc
{
  "name": "<merchant>-commerce",
  "account_id": "<PINNED — comment why: an account switch must not deploy to the wrong place>",
  "main": "worker/index.js",
  "compatibility_date": "2025-01-01",
  "assets": { "directory": "./", "run_worker_first": ["/api/*"] },
  "d1_databases": [{
    "binding": "DB",
    "database_name": "<merchant>-commerce",
    "database_id": "<from `wrangler d1 create`>",
    "migrations_dir": "worker/migrations"
  }],
  "r2_buckets": [{ "binding": "MEDIA", "bucket_name": "<merchant>-media" }],
  "observability": { "enabled": true }
}
```

`MEDIA` (R2) holds any bytes too big for a D1 row (2 MB cap) — recordings, attachments,
images, long email HTML — via `references/r2-offload.mjs`; D1 keeps only the pointer.

### Overflow shards (the D1 10 GB bypass — only when a single node gets fat)

A normal node lives in one `DB` forever. When the active shard nears the **9 GB
watermark**, the node spreads NEW customers across additional D1 databases — see
`references/sharding.md` for the full runbook. In short: `wrangler d1 create
<merchant>-commerce-1`, add a second binding, apply `schema.sql` (entities only, **not**
the registry) to it, and register it with the router:

```jsonc
  "d1_databases": [
    { "binding": "DB",   "database_name": "<merchant>-commerce",   "database_id": "…", "migrations_dir": "worker/migrations" },
    { "binding": "DB_1", "database_name": "<merchant>-commerce-1", "database_id": "…" }
  ],
```

The router (`references/crm-shard-router.mjs`) reads/writes through `.dbFor(kind, row)`
and keeps each customer's whole footprint co-located on one shard; the sticky
`shard_routes` map (shard 0) means adding a shard never moves existing data.

Secrets (never in the file): `ENCRYPTION_KEY` (AES-GCM at rest), gateway keys (`STRIPE_SECRET_KEY` /
`CLOVER_API_TOKEN` / …), `*_WEBHOOK_AUTH`. Set via `wrangler secret put`.

## 3. Commands (operator approves every real one)

```bash
wrangler d1 create <merchant>-commerce
wrangler d1 migrations apply <merchant>-commerce --local     # dev
wrangler d1 migrations apply <merchant>-commerce --remote    # PROD — explicit go-ahead only
wrangler deploy                                              # PROD — explicit go-ahead only
```

## 4. Namespacing

- D1 database name, Worker name, and `integration_bindings.binding_id` all key on the merchant as
  `provider__tenant__merchant`, laid out to mirror that merchant's **OCSF Drive folder**. One merchant
  = one node = one Drive folder, same key across all three.
- `tenant_id` is in every row identity; default tenant `'primary'` for a single-merchant site.

## 5. Bring-up checklist

- [ ] D1 created, `0001_init.sql` (schema.sql) + `0002_sharding.sql` (schema-sharding.sql) applied, Worker bound, `account_id` pinned.
- [ ] `MEDIA` R2 bucket bound; a >2 MB media put round-trips through `r2-offload.mjs` (bytes in R2, pointer in D1).
- [ ] All customer-scoped reads/writes go through `crm-shard-router.mjs` `.dbFor()` (never a bare `env.DB` for CRM/orders), so overflow is a config change, not a code change.
- [ ] `ENCRYPTION_KEY` set; a write of a customer note round-trips through `encField`/`decField`.
- [ ] Auth seeded (`cf-identity` PBKDF2): first account bootstraps `owner`.
- [ ] Processor probed with `capability-readiness`; `integration_bindings.readiness` reflects the real state.
- [ ] If over POS cap: `catalog_source='db'`, hot-set syncer wired (DB→POS), reconciliation wired (POS→ledger).
- [ ] One order → `AWAITING_PAYMENT`; webhook → `PAID`; one partial refund → `succeeded`; over-refund rejected.
- [ ] PCI boundary scanner clean on every stored row (no PAN/CVV/track/PIN anywhere).
- [ ] README lists: D1 name, each integration's mode + readiness, tender capabilities, pending pieces.
