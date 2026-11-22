# Scoring Rubric — deterministic, reproducible, fail-closed

Scoring runs during a **prospecting scan** to qualify and rank shops, and on a
**targeted** shop to assign its priority tier. The score is a formula: same
evidence + same buy-box version → same number and tier. No dimension is scored on
feel. Missing evidence is `Unknown`, handled by the gates, never silently zeroed.

## Step 1 — score each dimension 0–5 from evidence

Anchors for the default `orosolu-restaurant` buy-box (`Unknown` = no source read
this run; not the same as 0):

**1. Third-party dependence** — win-back potential
- 5: on 3+ delivery marketplaces, prominently.  3–4: on 1–2.  1–2: minimal.  0: none.

**2. Direct-ordering gap** — the fix we sell
- 5: no first-party ordering at all (brochure/menu-only or no site).
- 3–4: ordering only via embedded marketplace widget / phone; no owned checkout.
- 1–2: has some direct ordering but poor/hidden/broken.  0: strong first-party ordering.

**3. Discoverability gap** — SEO/website upside
- 5: no real website (social-only) or no GBP.  3–4: stale/template site, thin GBP.
- 1–2: decent site, minor gaps.  0: already strong site + SEO + GBP.

**4. Demand proof** — traffic worth converting (review volume × rating)
- 5: 500+ reviews, ≥4.3★.  3–4: 100–500, ≥4.0★.  1–2: <100 or middling.  0: almost none/poor.

**5. Reachability** — can outreach land
- 5: decision-maker name + direct business email.  3–4: business email or direct phone.
- 1–2: only a form / social DM.  0: no reachable channel.

**6. Fit** — right target shape
- 5: independent, right size, clearly takeout-friendly.  3–4: mostly fits.
- 1–2: marginal.  0: poor fit (a chain/franchise is a DROP, not a 0).

## Step 2 — weighted sum

`score = Σ (dimension_raw × weight)`. For `orosolu-restaurant v1` (weights 4,4,3,4,3,2
= 20) the score is 0–100. Put the trace in the dossier / Build Brief:

```
dim1 third-party dependence : 5 × 4 = 20
dim2 direct-ordering gap     : 5 × 4 = 20
dim3 discoverability gap     : 2 × 3 =  6
dim4 demand proof            : 5 × 4 = 20
dim5 reachability            : 4 × 3 = 12
dim6 fit                     : 5 × 2 = 10
                               TOTAL = 88
```

## Step 3 — apply the gates (in order)

1. **Disqualifier check first.** Any buy-box disqualifier → **DROP** (record reason),
   no tier, **no deep dive** (don't harvest a shop you'd never build for).
2. **Completeness check.** Count `Unknown` among **core** dimensions (1–5). **≥2
   Unknown → INCOMPLETE**; name which dimensions lack evidence. No qualifying tier.
   (One core Unknown is allowed but noted.)
3. **Tier by score band** (only if it passed 1 and 2):
   - **Tier A** — ≥ 75 → highest need + reachable; deep-dive + build-chain ready.
   - **Tier B** — 55–74 → real prospect; deep-dive, worth outreach.
   - **Tier C** — 40–54 → marginal; deep-dive optional, nurture/revisit.
   - **< 40** → **DROP (low fit/need)**, score recorded, no deep dive.

## Determinism & audit

- Never zero-fill an `Unknown` to cross a band; it flows through the completeness
  gate, not the sum.
- The score trace + gate outcome + buy-box version + sources travel with the lead,
  so any tier is re-derivable from the row.
- Weights and bands are policy in the buy-box/this file. Change between runs and bump
  the version; never nudge them mid-run to move one lead across a line.
