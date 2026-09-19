---
name: sovereign-edge-scorer
description: >-
  A learned, EXPLAINABLE propensity score that runs as pure JS inside a Cloudflare Worker (or any
  edge/mobile backend) with ZERO network calls and NO external ML service: train logistic regression
  OFFLINE on exported CRM rows, ship the fitted coefficients as a tiny `weights.json`, and score live
  entities at the edge — and every score returns the ranked signed factors that produced it, so the
  CRM can SHOW an operator WHY, never a black-box number. The model is data the operator owns; the
  feature EXTRACTORS (entity → numbers) live in the app because they read your schema, and the model
  is just the coefficients. Ships with the honest engineering: z-score standardization baked into the
  model, gradient descent + L2, a Mann–Whitney (rank-based) AUC + precision/recall evaluator, and an
  offline trainer that does an 80/20 held-out split and WARNS when AUC < 0.65 (weak signal — get more
  labeled outcomes before relying on it). Use WHENEVER a build needs "score/rank leads or members by
  likelihood to convert / churn / reorder", "a propensity model that runs offline / with no API",
  "explainable scoring", "which accounts are about to lapse", "train on our own outcomes and ship the
  model", or "learn from what actually converted." It COMPLEMENTS crm-build-standard (the records it
  scores) and lead-qualifier (that is an OFFLINE, one-lead CSV verifier with a win-rate heuristic —
  this is an in-worker LEARNED logistic model with shipped weights); it pairs with
  ledger-demand-forecast (the same sovereign-edge doctrine for demand) and feeds
  attack-list-priority-queue / a call list. Guardrails: extractors must be pure + cheap (they run per
  score); a zero-variance feature is guarded (std→1); retrain on a cadence as outcomes accrue; the
  score is ADVISORY input to a human/gate, never an automatic money or send decision.
---
# sovereign-edge-scorer — train offline, ship weights.json, score explainably at the edge

## What it is / when to use
The propensity-scoring spine for a CRM that must not phone home. You export labeled rows (features +
the realized outcome), fit a logistic model on your own machine, commit a small JSON blob, and the
Worker scores entities inline. It fits the sovereignty doctrine: the model is owned data, inference
is local math, and each score is auditable. Reach for it any time "rank by likelihood to X" comes up
and you want it explainable and dependency-free.

## Reference implementation (patterns only, no client data)
- **`worker/lib/crm-intelligence/score.mjs`** — the whole engine:
  - `extractFeatures(entity, extractors, ctx)` L21–28 — declarative extractor map → flat `{name:number}`
    vector (booleans→0/1, missing→0).
  - `trainLogistic(samples, featureNames, opts)` L49–76 — z-score standardizer L31–41 folded into the
    returned model, GD + L2; the model shape is `{kind:'logreg', featureNames, mean, std, weights, bias, meta}`.
  - `Scorer.score(features, threshold)` L91–110 — returns `p`, `label`, and `topFactors`/`factors`
    (each `{feature, value, z, contribution}`, sorted by |contribution|) — the explainability.
  - `evaluate(model, samples)` L114–133 — accuracy + **AUC via Mann–Whitney U** + precision/recall.
- **`worker/lib/crm-intelligence/train.mjs`** L1–41 — the offline trainer: reads `samples.json`,
  deterministic shuffle + 80/20 held-out split, prints metrics, **warns when AUC < 0.65**, writes
  `weights.json` you ship to the Worker.
- **`worker/lib/crm-intelligence/features.mjs`** L101–167 — the *adapter* pattern: `MEMBER_FEATURE_NAMES`
  + `computeMemberFeatures` (days_since_last_order, order_count, avg_order_cents, spend_trend, tier) and
  `loadMemberContext` (the exact D1 queries a route runs). This is how you map YOUR schema onto the model.
- Proof: `worker/lib/crm-intelligence/_proof/features-score.test.mjs`.

## How to reapply
1. Write feature extractors for your entity (pure functions of a row + context). Keep the names stable.
2. Export `[{features:{…}, label:0|1}, …]` from realized outcomes (converted? churned? reordered?).
3. `node worker/lib/crm-intelligence/train.mjs samples.json weights.json` → commit `weights.json`.
4. In the Worker: `new Scorer(model).score(extractFeatures(row, extractors))`; render `topFactors`.
5. Retrain weekly/monthly as outcomes accrue; watch the AUC warning.

## Gotchas + wiring status (from the code)
- **UNWIRED delta in the source repo:** the raw feature vector (`computeMemberFeatures`) IS called
  from a route (`worker/index.js` L825), but **no `weights.json` is shipped**, so `Scorer.score()`
  is proven-but-dormant there. To go live you must train + commit the weights and call `Scorer`. Flag
  this whenever lifting: the engine is real, the trained model is the missing artifact.
- Standardization lives IN the model (mean/std), so score-time and train-time must use the same
  featureNames — a renamed extractor silently scores 0 for that feature.
- AUC < 0.65 means the signal is weak; add features or more labels before trusting the rank.
