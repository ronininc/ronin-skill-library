// commerce-spine — CRM/commerce shard router (the D1 10 GB bypass)
//
// Framework-agnostic. Depends only on the Cloudflare D1 binding shape:
//   env[binding].prepare(sql).bind(...args).{first,all,run}()
// so the SAME module runs in a Worker and against the node:sqlite proof shim
// in references/_proof/. No imports, no build step — drop into worker/lib/.
//
// What it does: routes every read/write to the correct physical D1 shard so a
// single merchant node can grow past D1's 10 GB per-database limit by spreading
// customers (and everything co-located with them) across DB, DB_1, DB_2, ….
//
// Doctrine (see references/sharding.md):
//   * Aggregate root = customer (crm/orders/tenders/refunds/media) or product
//     (catalog/prices/ledger). The root id IS the shard key.
//   * Assignment is STICKY (shard_routes, in shard 0) — a root maps to one shard
//     for life; adding a shard only changes where NEW roots land.
//   * A root's whole footprint co-locates on one shard → "show this customer" is
//     a single-DB read. Cross-shard reads fan out + merge (rare, bounded).

// ── entity → aggregate-root map (the agnostic seam) ─────────────────────────
// For a custom CRM, extend this: give each new table the root it co-locates with.
// `domain` picks the shard set; `root` extracts the shard key from a row/params.
export const DEFAULT_ROOTS = {
  // customer domain — the CRM + transaction bulk
  customers:       { domain: 'customer', root: (r) => r.customer_id },
  customer_events: { domain: 'customer', root: (r) => r.customer_id },
  orders:          { domain: 'customer', root: (r) => r.customer_id },
  order_lines:     { domain: 'customer', root: (r) => r.customer_id }, // pass customer_id alongside order_id
  tenders:         { domain: 'customer', root: (r) => r.customer_id },
  refunds:         { domain: 'customer', root: (r) => r.customer_id },
  refund_events:   { domain: 'customer', root: (r) => r.customer_id },
  // product domain — the unlimited catalog
  products:        { domain: 'product',  root: (r) => r.product_id },
  product_prices:  { domain: 'product',  root: (r) => r.product_id },
  inventory_ledger:{ domain: 'product',  root: (r) => r.product_id },
  // media co-locates with whatever it belongs to (owner_id is already a root id)
  media_objects:   { domain: (r) => r.owner_domain || 'customer', root: (r) => r.owner_id },
};

const now = () => Date.now();

export class ShardRouter {
  /**
   * @param {object} env    Worker env holding D1 bindings (env.DB, env.DB_1, …)
   * @param {object} [opts]
   * @param {object} [opts.roots]        entity→root map (defaults to DEFAULT_ROOTS)
   * @param {string} [opts.primary]      binding name of shard 0 (holds the registry). default 'DB'
   * @param {number} [opts.watermark]    approx_bytes at which a shard stops taking new roots. default 9 GB
   */
  constructor(env, opts = {}) {
    this.env = env;
    this.roots = opts.roots || DEFAULT_ROOTS;
    this.primary = opts.primary || 'DB';
    this.watermark = opts.watermark ?? 9 * 1024 * 1024 * 1024; // 9 GB: split before the 10 GB wall
    this._catalog = null;                 // shard_ix -> {binding, domain, state, approx_bytes}
    this._routeCache = new Map();         // route_key -> shard_ix
  }

  get _primaryDb() { return this.env[this.primary]; }

  // Load the physical shard list once per request (cache in memory).
  async _loadCatalog() {
    if (this._catalog) return this._catalog;
    const { results } = await this._primaryDb
      .prepare('SELECT shard_ix, binding, domain, state, approx_bytes FROM shard_catalog')
      .all();
    const map = new Map();
    for (const row of results) map.set(row.shard_ix, row);
    if (!map.has(0)) map.set(0, { shard_ix: 0, binding: this.primary, domain: 'customer', state: 'active', approx_bytes: 0 });
    this._catalog = map;
    return map;
  }

  _domainFor(entityKind, row) {
    const spec = this.roots[entityKind];
    if (!spec) throw new Error(`shard-router: no root mapping for entity '${entityKind}'`);
    const domain = typeof spec.domain === 'function' ? spec.domain(row) : spec.domain;
    const rootId = spec.root(row);
    if (!rootId) throw new Error(`shard-router: entity '${entityKind}' row is missing its root id (${JSON.stringify(row)})`);
    return { domain, rootId };
  }

  // THE tunable policy — which active shard a NEW root is placed in.
  // Default: the least-full active shard in the domain (bin-packing toward the
  // watermark). Swap the body to bias by locality, region, hash, etc.
  async _pickWriteShard(domain) {
    const catalog = await this._loadCatalog();
    let best = null;
    for (const s of catalog.values()) {
      if (s.domain !== domain || s.state !== 'active') continue;
      if (s.approx_bytes >= this.watermark) continue; // full → skip
      if (!best || s.approx_bytes < best.approx_bytes) best = s;
    }
    if (best) return best.shard_ix;
    // Every active shard in this domain is at/over the watermark (or none exists):
    // fall back to shard 0 and let the operator provision + addShard() the next one.
    return 0;
  }

  /**
   * Resolve the shard index for an aggregate root, assigning + recording it
   * stickily on first sight. Registry write lands in shard 0 BEFORE any entity
   * write (see sharding.md ordering invariant), and is idempotent.
   */
  async shardIxForRoot(domain, rootId, tenantId) {
    const key = `${domain}:${rootId}`;
    if (this._routeCache.has(key)) return this._routeCache.get(key);

    const hit = await this._primaryDb
      .prepare('SELECT shard_ix FROM shard_routes WHERE route_key = ?')
      .bind(key).first();
    if (hit) { this._routeCache.set(key, hit.shard_ix); return hit.shard_ix; }

    const ix = await this._pickWriteShard(domain);
    await this._primaryDb
      .prepare(`INSERT OR IGNORE INTO shard_routes (route_key, tenant_id, domain, root_id, shard_ix, created_at)
                VALUES (?, ?, ?, ?, ?, ?)`)
      .bind(key, tenantId || rootId.split(':')[0] || 'primary', domain, rootId, ix, now()).run();
    // Re-read in case a concurrent request won the INSERT OR IGNORE race.
    const settled = await this._primaryDb
      .prepare('SELECT shard_ix FROM shard_routes WHERE route_key = ?')
      .bind(key).first();
    const finalIx = settled ? settled.shard_ix : ix;
    this._routeCache.set(key, finalIx);
    return finalIx;
  }

  async _dbForIx(ix) {
    const catalog = await this._loadCatalog();
    const s = catalog.get(ix) || catalog.get(0);
    const db = this.env[s.binding];
    if (!db) throw new Error(`shard-router: env has no binding '${s.binding}' for shard ${ix} — add it to wrangler.jsonc`);
    return db;
  }

  /**
   * The main entry point. Given an entity kind and a row/params object that
   * carries the root id (customer_id / product_id / owner_id), return the D1
   * handle that entity lives in. Use it for BOTH reads and writes of that entity.
   */
  async dbFor(entityKind, row) {
    const { domain, rootId } = this._domainFor(entityKind, row);
    const tenantId = row.tenant_id;
    const ix = await this.shardIxForRoot(domain, rootId, tenantId);
    return this._dbForIx(ix);
  }

  /**
   * Fan-out read across every shard in a domain, then merge. Use ONLY for
   * cross-root aggregates (e.g. "all hot leads for this merchant") — never for a
   * single-customer read, which dbFor() keeps to one database.
   * @param {string} domain
   * @param {(db, shardIx) => Promise<any[]>} run  runs the query on one shard
   * @returns {Promise<any[]>} concatenated results
   */
  async fanout(domain, run) {
    const catalog = await this._loadCatalog();
    const shards = [...catalog.values()].filter((s) => s.domain === domain);
    const parts = await Promise.all(shards.map((s) => run(this.env[s.binding], s.shard_ix)));
    return parts.flat();
  }

  // ── operations: grow the shard set ────────────────────────────────────────
  /** Register a freshly-provisioned D1 as the next active shard in a domain. */
  async addShard({ shardIx, binding, databaseName, domain = 'customer' }) {
    await this._primaryDb
      .prepare(`INSERT OR REPLACE INTO shard_catalog
                (shard_ix, binding, database_name, domain, state, approx_bytes, created_at)
                VALUES (?, ?, ?, ?, 'active', 0, ?)`)
      .bind(shardIx, binding, databaseName, domain, now()).run();
    this._catalog = null; // invalidate cache
  }

  /** Record the last-observed size of a shard (feeds the watermark / write-shard picker). */
  async recordShardBytes(shardIx, approxBytes) {
    await this._primaryDb
      .prepare('UPDATE shard_catalog SET approx_bytes = ? WHERE shard_ix = ?')
      .bind(approxBytes, shardIx).run();
    this._catalog = null;
  }

  /** Stop a shard from taking new roots (existing roots keep reading/writing it). */
  async sealShard(shardIx) {
    await this._primaryDb
      .prepare("UPDATE shard_catalog SET state = 'readonly' WHERE shard_ix = ?")
      .bind(shardIx).run();
    this._catalog = null;
  }
}

export function createShardRouter(env, opts) {
  return new ShardRouter(env, opts);
}
