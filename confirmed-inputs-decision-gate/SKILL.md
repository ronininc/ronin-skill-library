---
name: confirmed-inputs-decision-gate
description: >-
  A reusable governance ATOM — "AI proposes, operator confirms, deterministic math decides" — for any
  CRM where a money/irreversible calculation must never run on a value a model invented. Three moving
  parts: (1) an enrichment call whose prompt FORBIDS inventing numbers (unsupported → null at "low"
  confidence, with citations/sources stored, never a fabricated figure); (2) an explicit operator
  CONFIRM action that writes the real value and promotes confidence to "high"; (3) a pure-math
  calculator that RETURNS NULL and PARKS the record when a required confirmed input is missing, rather
  than computing on a guess. Use WHENEVER a build has an "AI-assisted number that drives a decision":
  "don't let the AI make up the ARV/valuation/quote", "operator must confirm before we calculate",
  "gate the math on confirmed inputs", "low-confidence until a human verifies", "park the deal if we
  don't have real numbers", "citations required". This is the confirm-gate EXTRACTED from a wholesale
  real-estate pipeline; it COMPLEMENTS wholesale-real-estate + az-cash-buyer-finder (the RE vertical
  that USES it) and buy-box-matcher, and it is ORTHOGONAL to graduated-autonomy-tiers (that dials
  off/draft/auto per STAGE; this gates the TRUST of an INPUT before any stage math runs) and to
  governed-operator-console (which gates ACTIONS). Capture only the confirm-gate delta — do NOT
  re-implement the underlying vertical pipeline. Guardrail: the model's suggested value is advisory
  only; the deterministic function is the sole decider, and it refuses to decide on unconfirmed data.
---

# Confirmed-Inputs Decision Gate

## What it is / when to use
A small, vertical-agnostic trust boundary that sits between an LLM enrichment step and a
deterministic calculation. The model may SUGGEST (with citations, at low confidence); a human must
CONFIRM before the number is trusted; and the calculator REFUSES to produce an offer/quote/valuation
until a confirmed input exists. Reach for it anywhere a wrong-but-confident number would cost money:
real-estate ARV/MAO, a valuation, a bid amount, an insurance quote, a pricing decision.

**Composes with:** `wholesale-real-estate` + `az-cash-buyer-finder` (the RE vertical this atom was
lifted from — they own the pipeline, this owns the input-trust gate) and `buy-box-matcher` (the
disposition step downstream). It is a different axis from `graduated-autonomy-tiers`
(off/draft/auto per stage) and `governed-operator-console` (propose→confirm→execute for ACTIONS) —
you can and often should use all three together.

## Reference implementation (ronininc CRM — OPEN before lifting)
Cloudflare Worker + D1, `worker/acquisitions.ts` (a wholesaling pipeline). The atom is three spots —
read them, ignore the surrounding RE-specific stages:
- **Enrichment that never fabricates** — `enrichDeal` L73-106. The prompt (L86-91) states: "From
  ONLY the facts below … DO NOT invent numbers, comps, or an ARV. If a value is not supported by the
  facts, use null and set confidence 'low'." The system message (L93) repeats "You never fabricate …
  Unknown means null + low confidence." Output is parsed defensively (slice `{...}` out of the
  response L95, validate the confidence enum L97) and stored as `enrichment_json` + `sources_json`
  (citations) with `confidence` — the SUGGESTED value is recorded, not applied.
- **The pure-math decider** — `computeMao` L112-115: `if (arvCents == null || repairCents == null)
  return null;` then the formula. It returns **null**, not 0, on a missing input. `underwriteDeal`
  L117-128: when `computeMao` returns null it PARKS the record (advances the stage marker but writes
  no numbers, returns `reason: 'Needs a confirmed ARV and repair estimate…'`); only with real inputs
  does it write the computed value.
- **The operator confirm action** — `advanceDeal` action `'set'` L226-230: writes the operator's
  ARV/repair via `COALESCE(?, existing)` and sets `confidence='high'`. This is the ONLY path that
  promotes a value to trusted; the LLM can never write `high`.
- **Schema** — `migrations/0028_acquisitions.sql` L37: `confidence TEXT DEFAULT 'low' CHECK
  (confidence IN ('low','medium','high'))`; L38 `enrichment_json`, `sources_json` (the synthesis
  output + citations); the value columns (`arv_cents`, `repair_cents`) are nullable so "not yet
  confirmed" is representable as NULL.

## How to reapply it
1. **Schema.** On the record that carries the decision inputs: make each gated value column
   NULLABLE (NULL = not confirmed), add `confidence TEXT DEFAULT 'low' CHECK IN ('low','medium',
   'high')`, and add `enrichment_json` + `sources_json` (or equivalents) to store the model's
   suggestion + citations WITHOUT applying them.
2. **Enrichment step.** Call the model with a prompt that (a) supplies only real facts, (b) forbids
   inventing values, (c) mandates `null` + `"low"` when unsupported, (d) demands a `sources[]`.
   Parse defensively (extract the JSON substring, validate the confidence enum). Store the result;
   do NOT copy suggested values into the trusted columns.
3. **Confirm action.** Add an operator-only endpoint that writes the real value (`COALESCE(?,
   existing)`) and sets `confidence='high'`. This is the only writer of the trusted value.
4. **Deterministic decider.** Write the calculation as a pure function that returns `null` when any
   required input is null, and a caller that PARKS the record (surface a "needs confirmed X" reason)
   instead of computing. Never coerce a missing input to 0 or a default that reads as a real answer.
5. **Wire.** The enrich + confirm + compute actions hang off the record's action endpoint (see
   `advanceDeal`); the compute step can also run from cron once inputs are confirmed.

## Gotchas
- **Return `null`, never `0`, on a missing input.** `0` is a real offer/quote; `null` is "I refuse
  to answer." Parking on null is the entire safety property.
- **The LLM can never write the trusted value or `confidence='high'`.** Only the operator confirm
  action promotes. If the model's `suggested_*` ever flows into the math, the gate is defeated.
- **Model output is untrusted text.** Slice the JSON object out of the response and validate every
  enum/number — a model that ignores "return only JSON" must not crash the handler or smuggle a
  string where a number belongs.
- **Store citations, surface them.** `sources_json` is what lets the operator confirm quickly and
  is the honesty trail; don't drop it.
- **This gates INPUT trust, not stage autonomy.** It stacks with `graduated-autonomy-tiers`: even a
  stage set to `auto` must still park on unconfirmed inputs (see `runAcquisitions` only auto-
  underwriting deals where `arv_cents IS NOT NULL AND repair_cents IS NOT NULL`). Keep both gates.
- **"low/medium/high" is a promotion ladder, not a score.** Low = AI-suggested/unconfirmed, high =
  operator-confirmed. Don't let a model emit "high" to skip the human.
