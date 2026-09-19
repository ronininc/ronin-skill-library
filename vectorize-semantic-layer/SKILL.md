---
name: vectorize-semantic-layer
description: >-
  Meaning-aware search, dedup, and recommendations for a Cloudflare Worker + D1 CRM using Cloudflare's
  OWN edge AI — Workers AI embeddings (`@cf/baai/bge-base-en-v1.5`, 768-dim) + a Vectorize index — with
  NO third-party egress (vectors never leave Cloudflare's network). One tiny module: embed text, upsert
  entities with tenant/source metadata, then semantic search (top-K by cosine), duplicate detection
  (best match over a threshold, e.g. before creating a lead/customer), and "entities like this one"
  recommendations (nearest neighbours minus the seed). Because the AI + Vectorize bindings are injected
  via `env`, the ranking/threshold/dedup logic is unit-testable with a local embedder while embedding
  QUALITY needs a deploy. Use WHENEVER a build needs "search by meaning not keywords", "find similar
  products/customers/cases", "recommend related items", "detect duplicate leads/contacts semantically",
  "customers who bought X might want Y", "embeddings / vector search", or "semantic dedup". It
  COMPLEMENTS contact-enrichment-deliverability (that dedups/validates by MX + normalized identity —
  this dedups by MEANING), pluggable-draft-brain (that is the LLM text-DRAFT seam — this is the
  embeddings/retrieval seam; different Workers AI capability), and any catalog/CRM spine (commerce-spine,
  crm-build-standard) whose records it indexes. Bilingual-friendly: collapse name_en/name_es into one
  text so translations cluster. Guardrail: this is the ONLY intelligence layer that calls a Cloudflare
  edge model — it is capability-GATED and ships INERT (needs the `ai` + `vectorize` bindings provisioned);
  for a fully-offline build use sovereign-edge-scorer / ledger-demand-forecast instead.
---
# vectorize-semantic-layer — embeddings + Vectorize for semantic search / dedup / recommend

## What it is / when to use
The retrieval half of a CRM's intelligence, kept sovereign by staying on Cloudflare's own network.
Reach for it when string matching isn't enough: a customer types a need in their own words, you want
"similar to this," or you want to catch a near-duplicate lead before it's created. It is distinct
from LLM drafting (pluggable-draft-brain) and from deterministic contact dedup
(contact-enrichment-deliverability) — this is embeddings + vector nearest-neighbour.

## Reference implementation (patterns only, no client data)
- **`worker/lib/crm-intelligence/semantic.mjs`** — the engine:
  - `embed(env, texts)` L16–21 — `env.AI.run('@cf/baai/bge-base-en-v1.5', {text:list})` → vectors.
  - `cosine(a,b)` L24–28 — the local, testable similarity.
  - `indexEntity(env, {id, text, metadata})` L32–36 — embed + `env.VECTORIZE.upsert`; metadata carries
    `tenant_id` + source table/id for filter + join-back.
  - `findSimilar(env, query, {topK, filter})` L39–43 — embed query → `VECTORIZE.query` with
    `returnMetadata`.
  - `findDuplicate(env, text, {threshold=0.92, filter})` L50–54 — best match over threshold, else null.
  - `recommend(env, seedText, {topK, filter, excludeId})` L58–61 — neighbours minus the seed.
- **`worker/lib/crm-intelligence/features.mjs`** L177–216 — the adapter: `productText` collapses
  name/category/description (incl. `name_es`/`web_category_es`) into one embedding string;
  `indexProductCatalog`, `recommendProducts`, `searchProducts` wrap the engine with a tenant filter.
- Proof: `worker/lib/crm-intelligence/_proof/features-semantic-assist.test.mjs`.

## How to reapply (this capability ships INERT — here are the bindings)
1. `wrangler.jsonc`: add `"ai": { "binding": "AI" }` and
   `"vectorize": [{ "binding": "VECTORIZE", "index_name": "<name>" }]`.
2. Create the index at the model's dimensions:
   `wrangler vectorize create <name> --dimensions=768 --metric=cosine` (768 = bge-base output dims).
3. Backfill: iterate your catalog/contacts through `indexEntity` (stamp `tenant_id`, `kind`, source id).
4. Query paths: search box → `findSimilar`; pre-create lead → `findDuplicate`; "related" → `recommend`.

## Gotchas + wiring status (from the code)
- **UNWIRED in the source repo:** `semantic.mjs` (and its `assist.mjs` sibling) are NOT imported by
  `worker/index.js`, and the `ai`/`vectorize` blocks are COMMENTED in `wrangler.jsonc` — it is a proven
  but dormant capability. Say so when lifting; the code is ready, the bindings are the missing step.
- The index dims MUST equal the embedding model's output (768 here); a mismatch is a silent upsert fail.
- `findDuplicate` threshold is model-specific — 0.92 is a starting point; tune on real pairs.
- Keep `metadata` small and filterable (`tenant_id`, `kind`, source id) — it's your only join back to D1.
