# CRM Intelligence Layer

A **sovereign, explainable** ML layer that drops into the CRM nodes (the
commerce-spine per-site Workers and the mobile-backend). Four capabilities, two
of which run with **zero egress and zero external service**, and two that use
**Cloudflare's own edge models** (no third-party). It sits on top of the D1
sharding layer — the append-only tables we shard (orders, events, ledgers, call
attempts) are exactly the feature store these models read.

| Module | What it does | Runtime | Proven offline? |
|---|---|---|---|
| `score.mjs` | Learned, explainable scoring (lead-conversion, churn, reorder-propensity). Train offline → ship a tiny weights.json → score in the Worker. | **Pure JS, no egress** | ✅ held-out AUC 0.818 |
| `forecast.mjs` | Demand/reorder forecasting + POS hot-set velocity ranking off the ledgers. | **Pure JS, no egress** | ✅ recovers rate, stockout, reorder |
| `semantic.mjs` | Embeddings + Vectorize: semantic search, dedup, recommendations. | Cloudflare Workers AI + Vectorize | ◑ logic/ranking proven; embedding quality needs deploy |
| `assist.mjs` | Governed LLM copilot: summarize, draft, classify, extract. | Cloudflare Workers AI (Llama) | ◑ wiring + governance proven; answer quality needs deploy |

`npm test` runs all three proof suites (**37 assertions**).

## Non-negotiables

- **Explainable, not black-box.** `score.mjs` returns the signed per-feature
  factors behind every score; `forecast.mjs` and the hot-set ranker expose their
  bases. An agent always sees *why*.
- **Governed.** `assist.mjs` NEVER sends, posts, or writes. Drafts/extractions
  come back `requiresApproval: true`; sending is a separate human-approved action
  (Solomon propose→confirm→act). The proof pins this.
- **Sovereign-first.** Prefer `score`/`forecast` (no egress). The two edge-model
  modules stay on Cloudflare's network; for a fully-offline build, skip them.
- **Honest weakness.** `train.mjs` warns when held-out AUC < 0.65 — a weak signal
  is reported, never dressed up. Retrain on a cadence as outcomes accrue.

## Per-client fit (and the two hard guardrails)

| Client | Fit | Guardrail |
|---|---|---|
| **case-plug** (PI leads) | lead-conversion **score** + attorney-match **semantic** + inbound **classify** | scoring PRIORITIZES; it must not be the sole basis for denying anyone service |
| **pineapple** (wholesale/retail) | reorder **forecast** + hot-set ranker + member-churn **score** + product **recommend** | — |
| **slik** (crew portal) | job-cost/duration **forecast** + note **summarize/extract** | — |
| **wavelygth** (investor portal) | **assist** summaries + anomaly flags on valuations only | ⛔ **NO personalized investment predictions/advice** — non-advisory analytics only |
| **oro-talent** (minors) | at most **safety** classification, consented | ⛔ **No ML on children's message content** without an explicit, separate safeguarding + consent review; message bodies are E2E-encrypted at rest |

## Wiring (Worker)

```js
import { Scorer, extractFeatures } from './lib/crm-intelligence/score.mjs';
const scorer = new Scorer(WEIGHTS);           // WEIGHTS = shipped weights.json
const features = extractFeatures(lead, {      // extractors read YOUR schema
  days_old:   (l) => (Date.now() - l.created_at) / 86400000,
  touches:    (l) => l.attempt_count,
  has_phone:  (l) => !!l.phone,
  high_intent:(l) => l.source === 'web_form',
});
const { p, topFactors } = scorer.score(features);   // p = 0..1 + the reasons

// semantic + assist need bindings in wrangler.jsonc:
//   "ai": { "binding": "AI" }
//   "vectorize": [{ "binding": "VECTORIZE", "index_name": "<merchant>-crm" }]
```

## Training loop

1. Export labeled samples from the CRM: `[{ features:{…}, label:0|1 }]` where the
   label is the realized outcome (converted / churned / reordered).
2. `node train.mjs samples.json weights.json` → prints held-out AUC/precision/recall,
   writes `weights.json`.
3. Ship `weights.json` with the Worker. Re-run on a cadence; the model improves as
   real outcomes accumulate (this is the "learns from what converts" loop).
