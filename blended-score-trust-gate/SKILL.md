---
name: blended-score-trust-gate
description: >-
  The ranking DELTA for a live CRM: blend a LEARNED propensity (win-rate-by-signal, learned online from
  operator good/bad feedback inside the request path) with an INDEPENDENT deterministic score into ONE
  priority number — but only let the learned half count once it has enough labeled signal, otherwise fall
  back cleanly to the deterministic score. It carries the numerical-safety engineering that makes an ONLINE
  learner survive sparse/one-class live data: finite log-odds via a clamp so all-good / all-bad / tiny-sample
  never yield NaN/Infinity, a both-classes gate that returns a safe null (no false confidence) until it has
  seen a win AND a loss, a per-feature minimum-count before a signal is trusted, and a controlled outcome
  vocabulary so an unknown label is ignored (never silently scored as a failure). Use WHENEVER a build must
  "rank leads by what actually converts", "blend a model score with our own score", "don't let the ranker
  overreact to two data points", "learn from good/bad feedback in production", "show why it ranked this
  high", or "degrade to the base score until the model is trustworthy". It does NOT re-teach the transparent
  win-rate learner — that lives in lead-qualifier (the OFFLINE, one-lead-at-a-time CSV enricher); this is the
  IN-WORKER, blended, trust-gated, numerically-hardened delta. It COMPLEMENTS lead-qualifier (reuse its
  learner concept) and attack-list-priority-queue (deterministic urgency×gain ranking — this blends a learned
  half into that kind of score). Guardrail: the learned score is advisory until proven; the blend weights and
  trust threshold are business-specific — parameterize them.
---
# Blended Score Trust Gate

## What it is / when to use / what it composes with
Two scores rank the same list: a **deterministic** score (domain rules — e.g. an intel match or an
urgency×gain figure) and a **learned** propensity (win-rate-by-signal trained on real outcomes). Naively
trusting the learned score is dangerous on live data — with two labels it will happily output 0 or 100. This
atom makes the blend safe: it **only** admits the learned score once the model has real signal, and keeps
every intermediate number finite.

- **Do NOT duplicate `lead-qualifier`** — that skill owns the transparent win-rate learner and the offline
  CSV enrichment flow. This is the delta it does not detail: the *online* safety gates + the *blend* with a
  second score + the *trust threshold*.
- **`attack-list-priority-queue`** ranks by a deterministic urgency×gain. This skill is how you fold a learned
  half into a score like that without letting sparse data wreck the order.

## Reference implementation — exact source
`~/Projects/ronin-jv-lead-engine/src/learn.js` and `src/index.js`:
- **Finite log-odds guard (the NaN fix):** `EPS`/`clamp01`/`logit` — `learn.js:43-45`. Every probability is
  clamped to `(0,1)` so `logit` is always finite; this is what stops all-good/all-bad from producing
  `Infinity - Infinity = NaN`.
- **Train (smoothed Naive-Bayes):** `trainModel(labeled)` — `learn.js:48-73`. Per-feature win-rate with a
  smoothed prior expressed as a finite log-odds weight; `both_classes = goods>0 && goods<total`
  (`learn.js:53`) is the gate.
- **Score with the trust gate:** `learnedScore(features, model)` — `learn.js:77-91`. Returns
  `{score:null}` until `model.n && model.both_classes`; only counts a feature when `w.total >= 2`; returns
  the top contributors so the ranking is explainable.
- **Insights (why it learned):** `insights(model)` — `learn.js:94-105`. Ranks signals by `lift` (log-odds),
  filtered to `total >= 2`.
- **Outcome vocabulary gate:** `GOOD_OUTCOMES` / `BAD_OUTCOMES` / `isKnownOutcome` — `learn.js:33-39`; the
  feedback endpoint REJECTS an unknown label rather than counting it (`index.js:251-252`).
- **The blend + n-threshold trust:** `index.js:277-291` — `const trusted = model.n >= 5;` then
  `priority = trusted && ls.score != null ? Math.round(0.65*ls.score + 0.35*r.score) : r.score;` Ranking
  sorts by this blended `priority`.
- **Proof:** `~/Projects/ronin-jv-lead-engine/test/learn.test.mjs` — regression tests that all-good, all-bad,
  empty, mixed, unseen-feature, and unknown-label cases never produce a non-finite score/lift.

## How to reapply
- **Features:** derive a small list of categorical signals you can ACT on (source/utm/campaign/tier/
  message-keywords/business-vs-freemail email) — `extractFeatures` `learn.js:6-23` — and store them as
  `features_json` on each row.
- **Feedback → learning signal:** an operator writes a real `outcome` per row (schema: `outcome`,
  `outcome_at`, `outcome_note` — `schema.sql:20`). Retrain from `WHERE outcome IS NOT NULL` on each read
  (`index.js:10-15`); cheap at CRM scale.
- **On read:** load the model, compute `learnedScore`, blend with the deterministic score under the trust
  gate, sort by the blend, and surface `using_learned` + the contributors so the operator sees when the
  learned half kicked in (`index.js:280-290`, UI play-line `index.js:182-187`).

## Gotchas (from the code)
- **Never trust one class.** With only wins (or only losses) the model must return null, not a confident
  number — that is the `both_classes` gate. Skipping it is the classic "100% because we only have good ones"
  bug.
- **Clamp before logit, always.** The NaN comes from `log(0)`/`log(1)`; the clamp is not optional.
- **Unknown labels are ignored, not failures.** Counting a typo status as a loss silently poisons targeting —
  gate the vocabulary at both train and the feedback endpoint (`learn.js:49`, `index.js:251`).
- **The weights are business-specific.** `0.65/0.35` and `n >= 5` and `w.total >= 2` are tunable dials, not
  laws — parameterize them per deployment.
- **Blend, don't replace.** The deterministic score is the safe floor; the learned score only *adjusts* the
  ranking once earned.
