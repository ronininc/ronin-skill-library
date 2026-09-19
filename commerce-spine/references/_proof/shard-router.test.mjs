// Proof: the D1 10 GB bypass works. Runs the REAL router + R2 offload modules
// against three local SQLite files standing in for DB / DB_1 / DB_2.
// Run:  node references/_proof/shard-router.test.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { openD1, fakeR2 } from './d1-node-sqlite-shim.mjs';
import { createShardRouter } from '../crm-shard-router.mjs';
import { putMedia, listMedia } from '../r2-offload.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const schema = readFileSync(join(here, '..', 'schema.sql'), 'utf8');
const sharding = readFileSync(join(here, '..', 'schema-sharding.sql'), 'utf8');

let pass = 0, fail = 0;
const ok = (name, cond, extra = '') => {
  if (cond) { pass++; console.log(`  ✓ ${name}`); }
  else { fail++; console.log(`  ✗ ${name} ${extra}`); }
};
const T = 'primary'; // tenant

// ── set up three shards. schema.sql on all; the registry only on shard 0. ──
const DB = openD1(); DB.exec(schema); DB.exec(sharding);
const DB_1 = openD1(); DB_1.exec(schema);
const DB_2 = openD1(); DB_2.exec(schema);
const MEDIA = fakeR2();
const env = { DB, DB_1, DB_2, MEDIA };

// low watermark so overflow is exercisable in a test (1 KB instead of 9 GB)
const WATER = 1024;
const router = () => createShardRouter(env, { watermark: WATER });

const cust = (key) => ({ customer_id: `${T}:customer:${key}`, tenant_id: T });
async function createCustomer(r, key, name = key) {
  const c = cust(key);
  const db = await r.dbFor('customers', c); // routes + sticky-assigns
  await db.prepare(
    `INSERT INTO customers (customer_id, tenant_id, display_name, source, first_seen, last_seen, lifetime_cents)
     VALUES (?, ?, ?, 'web', ?, ?, 0)`
  ).bind(c.customer_id, T, name, Date.now(), Date.now()).run();
  return c;
}
const routeIx = async (r, c) => (await r._primaryDb
  .prepare('SELECT shard_ix FROM shard_routes WHERE route_key = ?')
  .bind(`customer:${c.customer_id}`).first())?.shard_ix;

async function main() {
  console.log('\n[1] sticky routing + co-location (single shard, no overflow yet)');
  {
    const r = router();
    const a = await createCustomer(r, 'alice');
    const ixA = await routeIx(r, a);
    ok('new customer recorded in shard_routes', ixA === 0, `got ${ixA}`);

    // co-locate an order + an event with the customer
    const orderDb = await r.dbFor('orders', { customer_id: a.customer_id, tenant_id: T });
    await orderDb.prepare(
      `INSERT INTO orders (order_id, tenant_id, customer_id, status, created_at, updated_at)
       VALUES (?, ?, ?, 'PAID', ?, ?)`
    ).bind(`${T}:order:o1`, T, a.customer_id, Date.now(), Date.now()).run();
    const evDb = await r.dbFor('customer_events', { customer_id: a.customer_id, tenant_id: T });
    await evDb.prepare(
      `INSERT INTO customer_events (event_id, tenant_id, customer_id, kind, at) VALUES (?, ?, ?, 'order', ?)`
    ).bind(`${T}:evt:e1`, T, a.customer_id, Date.now()).run();

    const onDB   = (DB.prepare('SELECT COUNT(*) n FROM orders WHERE customer_id=?').bind(a.customer_id).first()).n;
    const onDB_1 = (DB_1.prepare('SELECT COUNT(*) n FROM orders WHERE customer_id=?').bind(a.customer_id).first()).n;
    ok('order co-located on the customer\'s shard (DB)', onDB === 1 && onDB_1 === 0, `DB=${onDB} DB_1=${onDB_1}`);

    // sticky across a FRESH router instance (cold cache re-reads registry)
    const r2 = router();
    const dbAgain = await r2.dbFor('orders', { customer_id: a.customer_id, tenant_id: T });
    ok('sticky: cold-cache resolve returns same shard', dbAgain === DB);

    // idempotent: resolving the same root twice makes exactly one route row
    await r2.dbFor('customers', a); await r2.dbFor('customers', a);
    const routeRows = DB.prepare('SELECT COUNT(*) n FROM shard_routes WHERE route_key=?')
      .bind(`customer:${a.customer_id}`).first().n;
    ok('sticky assignment is idempotent (one route row)', routeRows === 1, `rows=${routeRows}`);
  }

  console.log('\n[2] overflow: shard 0 fills → new customers move to DB_1/DB_2, old stay put');
  {
    const r = router();
    // mark shard 0 as over the watermark, then provision two more shards
    await r.recordShardBytes(0, WATER + 1);
    await r.addShard({ shardIx: 1, binding: 'DB_1', databaseName: 'm-commerce-1', domain: 'customer' });
    await r.addShard({ shardIx: 2, binding: 'DB_2', databaseName: 'm-commerce-2', domain: 'customer' });

    const bob = await createCustomer(r, 'bob');
    ok('new customer skips full shard 0 → lands on an overflow shard', (await routeIx(r, bob)) !== 0, `ix=${await routeIx(r, bob)}`);
    const bobIx = await routeIx(r, bob);
    ok('overflow shard picked is active + under watermark', bobIx === 1 || bobIx === 2, `ix=${bobIx}`);

    // fill the shard bob landed on; next customer must move to the OTHER overflow shard
    await r.recordShardBytes(bobIx, WATER + 1);
    const carol = await createCustomer(r, 'carol');
    const carolIx = await routeIx(r, carol);
    ok('second overflow customer moves to the remaining under-watermark shard', carolIx !== bobIx && carolIx !== 0, `bob=${bobIx} carol=${carolIx}`);

    // existing customer (alice) is STICKY on shard 0 even though it is "full"
    const r3 = router();
    const aliceDb = await r3.dbFor('customers', cust('alice'));
    ok('pre-overflow customer stays on shard 0 (sticky, ignores watermark)', aliceDb === DB);

    // all overflow shards full → graceful fallback to shard 0 (operator\'s cue to add a shard)
    await r.recordShardBytes(carolIx, WATER + 1);
    const dave = await createCustomer(r, 'dave');
    ok('all shards full → graceful fallback to shard 0', (await routeIx(r, dave)) === 0, `ix=${await routeIx(r, dave)}`);
  }

  console.log('\n[3] fan-out read merges every shard');
  {
    const r = router();
    const all = await r.fanout('customer', async (db) =>
      (await db.prepare('SELECT customer_id FROM customers').all()).results);
    const names = new Set(all.map((x) => x.customer_id.split(':').pop()));
    // alice+dave on DB, bob on one overflow, carol on the other
    ok('fan-out returns all customers across shards', ['alice', 'bob', 'carol', 'dave'].every((n) => names.has(n)), `got ${[...names].join(',')}`);
    const distinctShards = DB.prepare('SELECT COUNT(DISTINCT shard_ix) n FROM shard_routes').first().n;
    ok('customers really span >1 physical shard', distinctShards >= 2, `distinctShards=${distinctShards}`);
  }

  console.log('\n[4] R2 offload: >2 MB blob → R2, tiny pointer co-located in the customer shard');
  {
    const r = router();
    const a = cust('alice'); // alice is on shard 0
    const big = new Uint8Array(3 * 1024 * 1024); big.fill(7); // 3 MB — illegal as a D1 row
    const ptr = await putMedia({ env, router: r }, {
      tenantId: T, ownerKind: 'customer', ownerId: a.customer_id, bytes: big, contentType: 'audio/mp4',
    });
    ok('blob bytes stored in R2', MEDIA._store.has(ptr.r2_key) && MEDIA._store.get(ptr.r2_key).byteLength === 3 * 1024 * 1024);
    ok('pointer records true byte length', ptr.byte_len === 3 * 1024 * 1024);

    const row = DB.prepare('SELECT * FROM media_objects WHERE media_id=?').bind(ptr.media_id).first();
    const rowInlineBytes = Object.values(row).reduce((s, v) => s + (v == null ? 0 : String(v).length), 0);
    ok('D1 pointer row is tiny (no inline blob)', row && rowInlineBytes < 2048, `rowBytes=${rowInlineBytes}`);
    ok('pointer co-located on the owner\'s shard (DB)', !!row);
    const listed = await listMedia({ router: r }, { tenantId: T, ownerKind: 'customer', ownerId: a.customer_id });
    ok('media list reads back from the owner shard', listed.length === 1 && listed[0].r2_key === ptr.r2_key);
  }

  console.log(`\n${fail === 0 ? 'PASS' : 'FAIL'} — ${pass} passed, ${fail} failed\n`);
  process.exit(fail === 0 ? 0 : 1);
}
main().catch((e) => { console.error(e); process.exit(1); });
