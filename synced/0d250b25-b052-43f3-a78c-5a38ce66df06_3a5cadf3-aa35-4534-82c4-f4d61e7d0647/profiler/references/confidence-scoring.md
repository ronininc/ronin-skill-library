# Confidence Scoring — deterministic tiers, same evidence → same tier

A match verdict is only useful if it's honest about *how sure* it is and if two people
scoring the same evidence land on the same tier. This rubric makes the tier
re-derivable from the evidence grid in the dossier — never a vibe.

## The four tiers

| Tier | Meaning | Safe to act on? |
|------|---------|-----------------|
| `Confirmed` | Multiple independent, operator-controlled signals tie the fragment to one entity. | Yes — pitch/build/dial. |
| `Likely` | One strong signal + one corroborating; no conflicts. | Yes, but note residual risk in the dossier. |
| `Possible` | A single suggestive signal, uncorroborated. | No — confirm before any outreach. |
| `Unknown` | Nothing ties the fragment to an entity, or evidence conflicts unresolved. | No — fragment stays unresolved. |

## Scoring the five tests

Weight each test by how forgeable it is. Operator-controlled, mutually-linked signals
are heaviest; single-source and aggregator signals are lightest.

**Strong signals (any one is a real tie):**
- Test 4 **two-way** account↔website linkage (both operator-controlled).
- Test 2 **logo match** (exact wordmark + icon + palette) on an operator surface.
- Test 5 NAP agreement across **≥2 independent operator-controlled** sources.
- Test 3 distinctive media provably on the business's **own** multiple surfaces.

**Corroborating signals (support a strong one, don't stand alone):**
- Test 1 link-in-bio → own domain (one-way).
- Test 4 **one-way** linkage.
- Test 3 media matches known-good but only seen once.
- Test 5 NAP agreement including aggregators.
- Test 1 bio/category/tagged-location consistency.

**Disqualifiers / downgraders:**
- Logo mismatch, media reverse-searches to stock/another business, or a UGC flag on
  the account → the account is not the operator's (downgrade to `Unknown` for
  "is this their account", even if the business itself is real).
- Unresolved NAP conflict → cap at `Possible` and flag; never `Confirmed` over a
  conflict.

## The rule (apply top-down, stop at the first that fits)

1. **Any two strong signals, no unresolved conflict → `Confirmed`.**
2. **One strong + one corroborating, no conflict → `Confirmed`** *(this is the common
   "logo match + NAP agreement" or "two-way link + one more" case)*.
3. **Exactly one strong signal, nothing else → `Likely`.**
4. **Only corroborating signals (no strong), ≥2 of them agreeing → `Likely`.**
5. **A single corroborating signal → `Possible`.**
6. **Nothing ties, or a disqualifier fires, or a conflict is unresolved → `Unknown`.**

Write the firing rule number into the dossier ("tier: Confirmed — rule 2: two-way link
+ logo match") so the tier is auditable.

## Ambiguity is not a low tier — it's a separate state

If Test 1 surfaced **two entities** sharing the name and the later tests didn't
separate them, the verdict is `ambiguous → unresolved`, listing both candidates and
what would break the tie. Do **not** pick one to report a tier. Forcing a choice here
is the single most expensive error in the pipeline.

## Contact tiers use the same spine

For each phone/email (see `contact-enrichment.md`): `Confirmed` = on ≥2 operator
surfaces; `Likely` = one operator surface or two aggregators agreeing; `Possible` =
one aggregator; `PATTERN-GUESS` = derived from a pattern, never presented as found;
`Unknown` = not located. The entity tier and the contact tier are recorded separately
— you can be `Confirmed` on the entity and `Unknown` on its email.

## Determinism check before you present

Re-read your evidence grid and re-run the rule. If the tier you wrote doesn't fall out
of the rule mechanically, the tier is wrong (or the evidence is thinner than you
thought) — fix one or the other. That self-check is what keeps "Confirmed" meaning the
same thing every run.
