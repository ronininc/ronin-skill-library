// Proof: free-tier semantic (embeddings-in-D1 + in-Worker cosine) ranks correctly, isolates by
// tenant, and detects duplicates — no Vectorize. Mock env.AI (local deterministic embedder) + a
// tiny in-memory D1 shim. Proves OUR logic; real embedding quality needs Workers AI at deploy.
import assert from 'node:assert/strict';
import { indexEntityD1, findSimilarD1, findDuplicateD1, recommendD1 } from '../semantic-d1-free.mjs';

let passed = 0;
const ok = (n, c, x = '') => { assert.ok(c, `FAIL: ${n} ${x}`); passed++; console.log(`  ✓ ${n}${x ? ' — ' + x : ''}`); };

function localEmbed(s) {
  const v = new Array(64).fill(0);
  const t = ` ${String(s).toLowerCase().replace(/[^a-z0-9]+/g, ' ')} `;
  for (let i = 0; i < t.length - 2; i++) { let h = 0; for (let k = 0; k < 3; k++) h = (h * 31 + t.charCodeAt(i + k)) >>> 0; v[h % 64] += 1; }
  return v;
}
const env = { AI: { async run(_m, input) { return { data: input.text.map(localEmbed) }; } } };

// in-memory D1 shim (prepare/bind/run/all) over a plain array
function makeDb() {
  const rows = [];
  return {
    prepare(sql) {
      return {
        _a: [], bind(...a) { this._a = a; return this; },
        async run() {
          if (/INSERT OR REPLACE INTO embeddings/.test(sql)) {
            const [id, tenant_id, owner_kind, vector_json, dims, meta_json, updated_at] = this._a;
            const i = rows.findIndex((r) => r.id === id);
            const row = { id, tenant_id, owner_kind, vector_json, dims, meta_json, updated_at };
            if (i >= 0) rows[i] = row; else rows.push(row);
          }
          return {};
        },
        async all() {
          const [tenant_id, owner_kind] = this._a;
          return { results: rows.filter((r) => r.tenant_id === tenant_id && r.owner_kind === owner_kind) };
        },
      };
    },
  };
}

async function main() {
  const db = makeDb();
  await indexEntityD1(env, db, { id: 'c1', tenantId: 't1', text: 'Ana Ruiz rear-end car accident on I-10', metadata: { name: 'Ana' } });
  await indexEntityD1(env, db, { id: 'c2', tenantId: 't1', text: 'slip and fall wet floor grocery store' });
  await indexEntityD1(env, db, { id: 'c3', tenantId: 't2', text: 'other tenant rear-end accident' });

  console.log('\n[1] ranking + tenant isolation (no Vectorize)');
  const hits = await findSimilarD1(env, db, 'freeway rear-end collision, Ana', { tenantId: 't1', topK: 2 });
  ok('most similar record ranks first', hits[0].id === 'c1', `order: ${hits.map((h) => h.id).join(',')}`);
  ok('tenant filter excludes other tenants', hits.every((h) => h.id !== 'c3'));

  console.log('\n[2] duplicate detection by threshold');
  const dup = await findDuplicateD1(env, db, 'Ana Ruiz car accident rear-ended I-10', { tenantId: 't1', threshold: 0.6 });
  ok('near-duplicate detected', dup && dup.id === 'c1', `score=${dup?.score?.toFixed(2)}`);
  const none = await findDuplicateD1(env, db, 'unrelated plumbing invoice', { tenantId: 't1', threshold: 0.9 });
  ok('no false-positive duplicate', none === null);

  console.log('\n[3] recommend excludes the seed');
  const recs = await recommendD1(env, db, 'car accident freeway', { tenantId: 't1', topK: 5, excludeId: 'c1' });
  ok('recommendations exclude the seed id', recs.every((r) => r.id !== 'c1'));

  console.log(`\nPASS — ${passed} assertions passed (free-tier semantic; no Vectorize)\n`);
}
main().catch((e) => { console.error('FAIL:', e.message); process.exit(1); });
