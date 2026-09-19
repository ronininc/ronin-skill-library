---
name: dropship-opportunity-scorer
description: >-
  A composed-signal ranker that answers the question NO single API answers — "which PRODUCTS are
  rising, high-margin, and not yet saturated for this sub-niche?" — by fusing supplier catalog
  popularity (CJ open API) + optional external validation (Keepa, paid) + trend velocity (Google
  Trends alpha), computing margin as retail − (landed cost + shipping), and ranking a seeded sub-niche
  by `velocity × margin ÷ competition` into a curated shortlist to publish. Use WHENEVER a dropship /
  ecommerce build needs "find winning products", "which products should we sell", "rising high-margin
  products", "score products by opportunity", "product research engine", "beat the saturated hero SKU",
  or "pick SKUs to publish". It scores PRODUCTS, so it COMPLEMENTS — and must not be confused with —
  open-data-signal-discovery (which surfaces fresh BUSINESS buying signals like permits/licenses),
  website-need-scorer + lead-qualifier (which score prospect sites / people), and commerce-spine +
  cj-dropshipping-connector (where the winners it shortlists get their real landed cost and then get
  published/fulfilled). Do NOT re-implement catalog/publish/fulfill here — this is only the
  scoring/selection delta upstream of them. STATUS: design/spec-stage in the source repo (blueprint,
  not yet built) — bindings + the honest data-cost caveats are below.
---
# Dropship Opportunity Scorer

## What it is / when to use / what it composes with
The **selection brain** that sits upstream of the store. Its core insight (and the reason it's a
skill, not a call): **no API returns "top high-margin products."** That signal has to be *composed*
from several weaker ones and a computed margin, then ranked. This skill encodes that composition and
the ranking formula so a build doesn't re-derive it — and so the honest limits (paid data, computed
margin, saturation risk) are stated up front instead of oversold.

Inputs → shortlist:
- A **seed sub-niche** (the operator picks it; the engine does not invent demand).
- **Popularity / velocity** signals per candidate product.
- A **computed margin** per candidate.
- A **competition** proxy (saturation).
- Output: a ranked shortlist to hand to `cj-dropshipping-connector` (real landed cost) and
  `commerce-spine` (publish).

Use it the moment a build asks "what do we sell?" for a dropship/ecommerce venture. It is the
anti-commoditization move: catch a rising sub-niche product *pre-saturation* rather than chasing the
crowded, already-dead hero SKU.

## Reference (design source — no implementation exists yet; this captures the verified design + bindings)
- `drop-shipping-store/BUILD_AND_GTM.md:18` — the ranking formula: score
  `velocity × margin ÷ competition`, seeded on the chosen sub-niche, "to catch emerging products
  *pre-saturation*, not the crowded … hero."
- `drop-shipping-store/BUILD_AND_GTM.md:25` — the composed signal stack: "**CJ open API** catalog
  popularity + optional **Keepa API** external validation + **Google Trends API** (alpha, gated) …
  no API returns 'top high-margin products' — **composed**."
- `drop-shipping-store/BUILD_AND_GTM.md:26` — "Margin · **computed**: retail − (CJ cost + shipping)
  · estimate; excludes ad/return cost."
- `drop-shipping-store/BUILD_AND_GTM.md:35` — the endpoint shape: "`GET /research?niche=` → CJ
  category query → compute margin → rank by velocity × margin ÷ competition → shortlist."
- `drop-shipping-store/BUILD_AND_GTM.md:32` — the hard "don't": "**Do NOT** build research on scraping
  Amazon / AliExpress / TikTok (ToS / copyright / PII)."
- `drop-shipping-store/FEASIBILITY.md:31` — product-finder data reality: PA-API deprecating May 15
  2026 / no new signups → use **Keepa** (paid; compressed-array responses need parsing); this is a
  **paid data dependency**, not free.
- `drop-shipping-store/BUILD_AND_GTM.md:42-44` — the named honest risks (research-with-margin is the
  hardest part; hero SKUs are saturated; still must pass a live test).

Sources: CJ https://developers.cjdropshipping.com/en/api/start/ · Keepa https://keepa.com/api-docs/
· Google Trends alpha https://developers.google.com/search/blog/2025/07/trends-api

## How to reapply

### 1. Normalize every signal to 0..1, then combine (don't add raw units)
```
velocity   = trend + catalog-popularity momentum for the product     (0..1)
margin     = clamp( (retail − (landedCost + shipping)) / retail , 0, 1 )   -- gross margin %
competition= saturation proxy: listing count / recency / "everyone already sells it" (0..1, 0 = open)
score      = velocity * margin / max(competition, ε)      -- ε avoids divide-by-zero on a fresh niche
```
Guard the divide (`ε`, e.g. 0.05) so a brand-new sub-niche with ~0 competition doesn't produce
Infinity. Keep `margin` as a FRACTION so the product is comparable across price points.

### 2. Signal adapters (each isolated + individually skippable)
- `cjPopularity(niche)` → CJ category/product query (via `cj-dropshipping-connector`'s serialized
  QPS=1 path — reuse it, don't open a second CJ client) → popularity/listing counts. Also yields
  landed cost for the margin term. **This is the always-on, $0 signal.**
- `keepaValidate(candidate)` → OPTIONAL external validation; PAID. Parse Keepa's compressed arrays.
  Gate behind a config flag so the engine runs $0 on CJ alone and only spends when armed.
- `trendVelocity(term)` → Google Trends alpha (gated) OR a stored trend series. OPTIONAL; degrade to
  catalog momentum only when absent.
Each adapter returns a partial signal; a missing optional adapter drops its term to a neutral value
(don't zero the whole score because Keepa is off).

### 3. Schema (cache candidates so `/research` is cheap and QPS=1 is respected)
```sql
CREATE TABLE IF NOT EXISTS product_candidates (
  id            TEXT PRIMARY KEY,        -- supplier product id
  niche         TEXT NOT NULL,
  title         TEXT,
  landed_cost   REAL,                    -- item + shipping (from the supplier connector)
  suggested_retail REAL,
  velocity      REAL,                    -- 0..1
  margin        REAL,                    -- 0..1 fraction
  competition   REAL,                    -- 0..1
  score         REAL,                    -- computed
  signals_json  TEXT,                    -- provenance: which adapters contributed + raw values
  scored_at     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cand_niche_score ON product_candidates(niche, score DESC);
```
Persist `signals_json` so every score is explainable ("why is this ranked #1") — never a black-box
number. This mirrors `website-need-scorer`'s "score + human-readable reasons" contract.

### 4. Route / cron wiring
- `GET /research?niche=<seed>` → return the cached shortlist for that niche ordered by `score DESC`.
- Scheduled refresh (cron) → re-score active niches on the CJ QPS=1 queue (reuse
  `cj-dropshipping-connector` + `d1-work-queue`); do NOT re-score synchronously inside the GET.
- Winners flow OUT: operator curates the shortlist → publish via `commerce-spine`
  (`cost × markup`) → optionally bundle via `mystery-box-balancer`.

### 5. UI
An operator "research" view: seed a sub-niche, see the ranked shortlist with the three sub-scores and
the provenance chips, select candidates to publish. Fits `governed-operator-console` / `ops-console`.

## Gotchas (from the source, real)
- **Margin is an ESTIMATE and excludes ad + return cost** (`BUILD_AND_GTM.md:26`). A "high-margin"
  score is gross; a product can still lose money after CAC and returns. Label it as gross margin, and
  gate the real go/no-go on a live ad test, not on this score (`FEASIBILITY.md`/`BUILD_AND_GTM.md:47`).
- **"Top high-margin products" is composed, never fetched** (`BUILD_AND_GTM.md:25`). Anyone expecting
  one API call is wrong — the value of this skill is the composition + the divide-guarded formula.
- **Keepa is a PAID data dependency** (`FEASIBILITY.md:31`) and returns compressed arrays that need
  parsing; keep it optional and behind a flag so the engine runs free on CJ alone.
- **Never scrape Amazon / AliExpress / TikTok for signals** (`BUILD_AND_GTM.md:32`) — ToS / copyright
  / PII. Use the sanctioned APIs (CJ, Keepa, Google Trends) only. This is a hard boundary, not a perf
  choice.
- **Saturation is the real enemy** (`BUILD_AND_GTM.md:18,43`). The whole point of the `÷ competition`
  term and the sub-niche seed is to avoid the crowded hero SKU; if you ignore competition you just
  re-rank the same dead winners everyone sells.
- **This scores; it does not decide.** The final decision is a cheap live test on ONE product
  (`BUILD_AND_GTM.md:47`), because a good score is "odds-improving, not a guarantee"
  (`BUILD_AND_GTM.md:44`). Don't let the score auto-publish at scale.
- **Reuse the supplier connector's rate discipline.** CJ is QPS=1; drive every CJ read through
  `cj-dropshipping-connector`'s serialized queue, not a parallel fetch here.
