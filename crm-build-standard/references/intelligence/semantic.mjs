// CRM Intelligence — semantic layer (Cloudflare Workers AI embeddings + Vectorize).
//
// Gives the CRM meaning-aware search, dedup, and recommendations. Embeddings come
// from Workers AI (`env.AI.run('@cf/baai/bge-base-en-v1.5', …)`), vectors live in
// Vectorize (`env.VECTORIZE`). Both are Cloudflare bindings passed in `env`, so
// the RANKING / DEDUP / THRESHOLD logic here is testable with a local embedder,
// while embedding QUALITY requires a deploy (the real model runs at the edge).
//
// Sovereign note: these two are the only intelligence modules that touch a
// Cloudflare edge model. They stay on Cloudflare's network (no third-party
// egress). If a build must be fully offline, use score.mjs/forecast.mjs only.

const EMBED_MODEL = '@cf/baai/bge-base-en-v1.5';

/** Embed one or many strings. Returns an array of vectors. */
export async function embed(env, texts) {
  const list = Array.isArray(texts) ? texts : [texts];
  const res = await env.AI.run(EMBED_MODEL, { text: list });
  // Workers AI returns { data: number[][] }
  return res?.data ?? [];
}

const l2 = (v) => Math.sqrt(v.reduce((s, x) => s + x * x, 0)) || 1;
export function cosine(a, b) {
  let dot = 0;
  for (let i = 0; i < a.length; i++) dot += a[i] * b[i];
  return dot / (l2(a) * l2(b));
}

/** Upsert an entity into the vector index. `metadata` should carry tenant_id and
 *  the source table/id so results can be filtered and joined back. */
export async function indexEntity(env, { id, text, metadata = {} }) {
  const [values] = await embed(env, text);
  await env.VECTORIZE.upsert([{ id, values, metadata }]);
  return { id, dims: values.length };
}

/** Semantic search: embed the query, return the top-K nearest with scores. */
export async function findSimilar(env, query, { topK = 5, filter } = {}) {
  const [vector] = await embed(env, query);
  const res = await env.VECTORIZE.query(vector, { topK, filter, returnMetadata: true });
  return (res?.matches ?? []).map((m) => ({ id: m.id, score: m.score, metadata: m.metadata }));
}

/**
 * Duplicate detection: is there an existing entity semantically ~identical to
 * this text? Returns the best match above `threshold`, else null. Use before
 * creating a new lead/customer to avoid duplicates.
 */
export async function findDuplicate(env, text, { threshold = 0.92, filter } = {}) {
  const hits = await findSimilar(env, text, { topK: 1, filter });
  const best = hits[0];
  return best && best.score >= threshold ? best : null;
}

/** Recommend entities related to a seed (e.g. "members like this one",
 *  "attorneys who handled similar cases") — nearest neighbours minus the seed. */
export async function recommend(env, seedText, { topK = 5, filter, excludeId } = {}) {
  const hits = await findSimilar(env, seedText, { topK: topK + 1, filter });
  return hits.filter((h) => h.id !== excludeId).slice(0, topK);
}
