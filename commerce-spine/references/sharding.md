# The D1 10 GB bypass — customer-sharded overflow

Cloudflare D1 caps a **single database at 10 GB**. It does **not** cap you at one
database: a Workers Paid account gets **50,000 D1 databases**, and Cloudflare's own
documented remedy for the `Exceeded maximum DB size` error is literally *"shard your
data into multiple databases."* So the real ceiling is 10 GB × 50,000 ≈ **500 TB per
node** — the 10 GB wall just becomes a routing problem.

This is the SECOND bypass in commerce-spine, and it rhymes with the first:

| Bypass | Cap it removes | How |
|---|---|---|
| 15k-item (existing) | Clover's register-sync limit | DB is master, hot-set syncs to POS |
| **10 GB (this doc)** | D1's per-database size limit | one node spreads customers across DB, DB_1, DB_2, … |

Nothing here fires until a node approaches the wall. A normal merchant lives in one D1
(`DB`) forever. The machinery below only engages when a **single merchant** gets fat —
matching the house shard model: **per-merchant first, then hash the big one.**

## The one rule: co-locate by aggregate root

D1 **cannot join across databases.** The whole design exists to make that never matter:

- Every row belongs to an **aggregate root** — a **customer** (crm / orders / order_lines
  / tenders / refunds / refund_events / media) or a **product** (products / prices /
  inventory_ledger). The root's id is the **shard key**.
- A root's *entire footprint* lives on **one shard**. "Show me this customer and their
  whole history" stays a **single-database read**. Only cross-root *aggregates*
  ("all hot leads") fan out.
- Assignment is **sticky** (`shard_routes`, in shard 0): a root maps to one shard for
  life. Adding a shard changes only where **new** roots land — never a mass remap. This
  is the difference between growth costing O(new rows) and O(all rows). Never route with
  a live `hash(id) % shardCount`; that reshuffles everyone the moment `shardCount` changes.

## Pieces (all in `references/`)

- **`schema-sharding.sql`** — apply as the next numbered migration (`0002_sharding.sql`).
  Adds, in **shard 0 only**, `shard_catalog` (the physical shard list), `shard_routes`
  (sticky root→shard map), and `media_objects` (R2 pointers, which every shard carries).
- **`crm-shard-router.mjs`** — `worker/lib/` module. `createShardRouter(env)` →
  `.dbFor(entityKind, row)` returns the right D1 handle for a read or write;
  `.fanout(domain, run)` for cross-shard aggregates; `.addShard()`, `.recordShardBytes()`,
  `.sealShard()` for ops. Entity→root mapping is the `DEFAULT_ROOTS` table — **extend it
  for a custom CRM's own tables** (give each new table the root it co-locates with).
- **`r2-offload.mjs`** — `putMedia()` / `listMedia()` / `getMediaBytes()`. Big bytes go to
  R2 (forced anyway by D1's **2 MB row cap**); D1 keeps only the co-located pointer.
- **`_proof/`** — a D1-shaped shim over `node:sqlite` and `shard-router.test.mjs`, which
  runs the real modules across three local SQLite shards and proves sticky routing,
  co-location, overflow, fan-out, and R2 offload. `node references/_proof/shard-router.test.mjs`.

## Wiring a worker to it

```js
import { createShardRouter } from './lib/crm-shard-router.mjs';
// reads AND writes for a customer-scoped entity go through the router:
const router = createShardRouter(env);                 // env.DB, env.DB_1, … + registry in DB
const db = await router.dbFor('customers', { customer_id, tenant_id });
await db.prepare('INSERT INTO customers (...) VALUES (...)').bind(...).run();
// a cross-shard list:
const leads = await router.fanout('customer', async (shardDb) =>
  (await shardDb.prepare("SELECT * FROM customers WHERE ... ").all()).results);
```

**Ordering invariant:** creating a new root writes its `shard_routes` row (shard 0)
**before** the entity row (target shard) — `dbFor()` does this for you. There are no
cross-database transactions in D1; a crash between the two leaves at worst an idempotent
orphan route that the next create reuses. Keep a customer and everything you write in the
same request on the shard `dbFor` hands you — don't re-derive the handle per table.

## Growing a node past 10 GB (operator runbook)

Watch `shard_catalog.approx_bytes` (feed it from `wrangler d1 info <db> --json` →
`database_size`, or the GraphQL analytics `databaseSizeBytes`). When the active shard
crosses the **9 GB watermark** (default in the router — split *before* the 10 GB wall):

```bash
# 1. provision the next physical shard (operator approves every real command)
wrangler d1 create <merchant>-commerce-1
# 2. add the binding to wrangler.jsonc:  { "binding": "DB_1", "database_name": "<merchant>-commerce-1", "database_id": "…" }
# 3. apply the ENTITY schema (schema.sql) to it — NOT schema-sharding.sql (registry stays in shard 0)
wrangler d1 migrations apply <merchant>-commerce-1 --remote
# 4. register it so the router starts placing new roots there:
#    await router.addShard({ shardIx: 1, binding: 'DB_1', databaseName: '<merchant>-commerce-1', domain: 'customer' })
```

New customers now flow to `DB_1`; existing customers stay on `DB`. No data moves. To
retire a shard from *new* writes without moving its data, `sealShard(ix)` (state →
`readonly`) — existing roots keep reading and writing it.

**Rebalancing (rare):** to move a specific customer to another shard, copy their rows
(customers + their orders/events/tenders/refunds/media) to the target shard inside one
export/import, then `UPDATE shard_routes SET shard_ix = ? WHERE route_key = ?`. Because
routing is sticky and by-root, only the chosen roots move — never the whole node.

## The tunable policy

`ShardRouter._pickWriteShard(domain)` decides which active shard a **new** root lands in.
Default = **least-full active shard under the watermark** (bin-packing: fill a shard,
then move on — keeps hot data dense and shard count minimal). Swap its body to bias by
region/locality, spread evenly, or hash — it's the one place placement policy lives, and
changing it never touches already-placed roots.
