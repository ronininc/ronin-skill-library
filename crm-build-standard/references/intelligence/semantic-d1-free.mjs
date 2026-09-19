// CRM Intelligence — FREE-TIER semantic (no Vectorize).
//
// Vectorize is Workers-Paid-only. This is the free-plan path: generate the embedding with Workers AI
// (within the 10k-neuron/day budget), STORE the vector as JSON in a D1 column, and rank with cosine
// IN THE WORKER. Ideal for the hundreds-to-low-thousands of records a single CRM holds. When you move
// to Paid and N is large, switch to semantic.mjs (Vectorize) — same call shape.
//
// D1 table (add as a migration):
//   CREATE TABLE embeddings (
//     id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, owner_kind TEXT NOT NULL,
//     vector_json TEXT NOT NULL, dims INTEGER NOT NULL, meta_json TEXT, updated_at INTEGER NOT NULL);
//   CREATE INDEX ix_embeddings_tenant ON embeddings(tenant_id, owner_kind);
//
// Cache discipline (free-tier): only (re)embed when the text changed — store a hash and skip if equal.
// Never re-embed on a read; that burns neurons. Scoring/forecasting need none of this (pure JS).

const EMBED_MODEL = '@cf/baai/bge-base-en-v1.5';

export async function embed(env, texts) {
  const list = Array.isArray(texts) ? texts : [texts];
  const res = await env.AI.run(EMBED_MODEL, { text: list });
  return res?.data ?? [];
}

function l2(v) { let s = 0; for (const x of v) s += x * x; return Math.sqrt(s) || 1; }
export function cosine(a, b) { let d = 0; for (let i = 0; i < a.length; i++) d += a[i] * b[i]; return d / (l2(a) * l2(b)); }

/** Embed + upsert a record's vector into the D1 `embeddings` table (neuron-budgeted: caller should
 *  skip when the text is unchanged). */
export async function indexEntityD1(env, db, { id, tenantId, ownerKind = 'contact', text, metadata = {} }) {
  const [vector] = await embed(env, text);
  await db.prepare(
    `INSERT OR REPLACE INTO embeddings (id, tenant_id, owner_kind, vector_json, dims, meta_json, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  ).bind(id, tenantId, ownerKind, JSON.stringify(vector), vector.length, JSON.stringify(metadata), Date.now()).run();
  return { id, dims: vector.length };
}

/** Semantic search without Vectorize: embed the query, pull the tenant's stored vectors from D1,
 *  rank by cosine in the Worker. topK small; candidate set is one tenant's records. */
export async function findSimilarD1(env, db, query, { tenantId, ownerKind = 'contact', topK = 5 } = {}) {
  const [q] = await embed(env, query);
  const { results } = await db
    .prepare(`SELECT id, vector_json, meta_json FROM embeddings WHERE tenant_id = ? AND owner_kind = ?`)
    .bind(tenantId, ownerKind).all();
  return (results ?? [])
    .map((r) => ({ id: r.id, score: cosine(q, JSON.parse(r.vector_json)), metadata: r.meta_json ? JSON.parse(r.meta_json) : {} }))
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);
}

export async function findDuplicateD1(env, db, text, { tenantId, ownerKind = 'contact', threshold = 0.92 } = {}) {
  const [best] = await findSimilarD1(env, db, text, { tenantId, ownerKind, topK: 1 });
  return best && best.score >= threshold ? best : null;
}

export async function recommendD1(env, db, seedText, { tenantId, ownerKind = 'contact', topK = 5, excludeId } = {}) {
  const hits = await findSimilarD1(env, db, seedText, { tenantId, ownerKind, topK: topK + 1 });
  return hits.filter((h) => h.id !== excludeId).slice(0, topK);
}
