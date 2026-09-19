---
name: segment-shrinkage-estimator
description: >-
  A learned, EXPLAINABLE numeric-target regressor for a Cloudflare Worker + D1 CRM — "jobs/deals/items
  like this one have historically cost / taken / been worth X" — using hierarchical empirical-Bayes
  shrinkage over segment means. For each row it takes the mean of the target in its MOST-SPECIFIC segment
  (e.g. type×size), shrunk toward the coarser parent segment (type), shrunk toward the global mean, in
  proportion to how FEW samples the fine segment has — so a 40-sample segment trusts itself, a 2-sample
  segment leans on its parent, and an unseen segment falls back to the global mean. Pure JS, zero egress,
  and every prediction NAMES its basis (which segment, sample count, segment mean, delta-vs-global) plus
  the naive-baseline MAE it must beat ("just quote the average"). Use WHENEVER a build must ESTIMATE a
  continuous value from history with explainability — "estimate the job cost / duration", "quote based on
  similar past jobs", "predict the price/hours for this type", "average-by-segment with small-sample
  smoothing", "beat quoting the flat average", or "an explainable estimate, not a black box". It
  COMPLEMENTS the sovereign-edge intelligence kit as a THIRD model type beside sovereign-edge-scorer
  (logistic propensity — a 0/1 label) and ledger-demand-forecast (EWMA time-series demand): this is the
  numeric-target REGRESSOR neither provides. Feeds crm-build-standard's records. Guardrail: the shrinkage
  math is schema-agnostic and belongs in the SKILL; the feature EXTRACTORS + the segment HIERARCHY read
  your schema and live in the app, never hard-coded here — and never ship an estimate that can't beat the
  naive baseline on held-out data.
---
# Segment Shrinkage Estimator

## What it is / when to use / what it composes with
An explainable average-by-segment regressor: predict a continuous target (cost, duration, value) by
blending segment means with empirical-Bayes shrinkage, so small segments don't over-fit and unseen ones
degrade gracefully to the global mean. It is the numeric-target sibling of **sovereign-edge-scorer**
(logistic 0/1 propensity) and **ledger-demand-forecast** (EWMA demand) — same sovereign-first,
explainable, model-is-data-you-own doctrine — filling the "estimate a number" gap those two don't. The
records it estimates over are **crm-build-standard**'s.

## Reference implementation — exact source
`worker/lib/crm-intelligence/features.mjs:109-198`:
- `HIERARCHY` (`:120`) — segment levels finest→coarsest, e.g. `[['job_type','size_bucket'], ['job_type']]`
  (global mean is the implicit coarsest).
- `trainEstimator(samples, {priorWeight})` (`:132`) — accumulates `{sum,count}` per segment per level.
- `SegmentEstimator.predict(features)` (`:160`) — walks COARSE→FINE, `shrink()`-ing each present segment
  toward the running parent estimate.
- `shrink(sum, count, parentEstimate, priorWeight)` (`:149`) = `(sum + priorWeight*parentEstimate) / (count + priorWeight)`.
- `estimatorMAE` (`:182`) and `naiveBaselineMAE` (`:192`) — the "must beat the flat average" evaluators.
Proof: `worker/lib/crm-intelligence/_proof/estimator.test.mjs`.

## How to reapply
- **The model (schema-agnostic — copy this into the skill's shipped module):** `trainEstimator` builds,
  for each hierarchy level, a `Map<segmentKey, {sum,count}>` over `{features, target}` samples (filter
  non-finite targets). `SegmentEstimator.predict` starts `estimate = globalMean`, then for each level
  from coarsest→finest that HAS a matching segment, `estimate = shrink(stat.sum, stat.count, estimate, priorWeight)`.
  `priorWeight` is the pseudo-count of shrinkage toward the parent (default 8 → a segment needs ~8+
  samples before it trusts its own mean more than its parent's). Serialize the fitted `{levels, globalMean,
  priorWeight, hierarchy}` as JSON — it is small and it is data the operator owns.
- **The app layer (schema-aware — stays in your app, NOT the skill):** write pure feature extractors that
  bucket a row into categorical segments (in this repo `jobType`/`seasonOf`/`sizeBucket`, `features.mjs:35-64`)
  and define the `HIERARCHY` for your domain. Train offline on exported historical rows whose target is
  the realized value (`total_cents`, `duration_hours`, …), ship the JSON, and at request time build the
  feature vector for the NEW row (target absent) and call `predict`.
- **Always show the basis:** `predict` returns `{ value, basis: { segment, level, count, segmentMean,
  globalMean, deltaVsGlobal, matched } }` — surface it so the operator sees "based on N similar past jobs,
  $X above the all-jobs average," never a bare number.
- **Wiring (this ships DISCONNECTED in the source):** `worker/index.js` does NOT import
  `lib/crm-intelligence/*` — the estimator is complete but unreached. To activate: add an authed route
  (e.g. `POST /api/estimate {job}`) that joins the shift + line items + invoice into the feature shape,
  loads the fitted JSON (a bundled asset or a `settings` row), and returns `predict()`. It is pure JS and
  needs NO binding (unlike the assist path, which needs Workers AI). Keep it ADVISORY — an estimate
  informs a human quote; it never sets a price or moves money on its own.

## Gotchas
- **Prove it beats the baseline before you trust it.** `naiveBaselineMAE` (predict the flat all-jobs mean)
  is the bar; if `estimatorMAE` on a held-out split isn't clearly lower, you don't have enough labeled
  history yet — say so rather than shipping a confident wrong number.
- **`priorWeight` is the whole tuning knob:** larger = more shrinkage toward the parent (safer on sparse
  data, blander); smaller = trusts fine segments sooner (sharper, risk of over-fit). Tune on held-out MAE.
- Unseen fine segments are handled by design (fall back to the parent/global) — but a segment key must be
  stable; `keyOf` uses `features[col] ?? 'other'`, so keep your bucketers total (never return `undefined`).
- Do NOT bake your domain's `HIERARCHY`/extractors into the shipped model — that's what makes it reusable;
  they read a schema and belong in the app, exactly as `score.mjs`/`features.mjs` are split here.
