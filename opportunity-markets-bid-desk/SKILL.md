---
name: opportunity-markets-bid-desk
description: >-
  An INBOUND opportunity desk for a services/agency CRM: aggregate posted RFPs, gigs, and
  procurement notices from many sources into one normalized D1 queue, deterministically fit-score
  each one, run a qualify→shortlist→draft→ready→submitted lifecycle, and generate human-reviewable
  proposal drafts that NEVER auto-submit. Each source carries an HONEST connector-status model
  (needs_key | needs_authorization | needs_api_approval | connected — connected only when a real
  API key/OAuth is present) so the operator always knows which lanes actually ingest vs. which are
  compliant "open the portal + import a matched listing" tracks. Use WHENEVER a CRM must WIN work by
  RESPONDING to opportunities buyers already posted — "bid desk", "RFP/procurement pipeline",
  "SAM.gov / government-bid intake", "gig/marketplace aggregator", "respond to posted jobs",
  "proposal drafting queue", "where buyers already look". This is the INVERSE of outbound lead-gen
  (geo-directory-prospecting / custom-lead-generator generate prospects to cold-approach; this
  ingests inbound demand) — do not conflate them. COMPLEMENTS crm-build-standard (the CRM + its ML
  lead scoring; this adds a lighter transparent keyword fit-score for opportunities) and
  governed-email-outreach (the compliant send rail for an assisted submission). The bearer/role-
  scoped MCP transport that exposes these tools to an AI operator is a SEPARATE concern — build it
  with crm-mcp-server / scoped-bearer-token, do NOT re-implement token auth here.
---

# Opportunity Markets Bid Desk

## What it is / when to use
A normalized intake + bid desk for **inbound** opportunities. It turns many marketplaces and
procurement portals into one D1 queue where every listing is fit-scored, moved through a
qualification lifecycle, and answered with a draft proposal a human reviews before anything leaves
the building. Reach for it on any agency/services CRM that competes for posted work (federal/state
procurement, agency directories, freelance marketplaces).

**Composes with:** `crm-build-standard` (the CRM shell + its ML lead scoring — this desk adds a
transparent keyword fit-score for opportunities, a different job); `governed-email-outreach` (send
rail when a source's compliant track is "email the buyer"); `crm-mcp-server` + `scoped-bearer-token`
(the AI-operator transport — the bid tools are designed to be exposed there, but that layer is not
this skill). It is the mirror image of outbound prospecting (`geo-directory-prospecting`,
`custom-lead-generator`): keep the two pipelines separate.

## Reference implementation (ronininc CRM — OPEN before lifting)
Cloudflare Worker + D1. Start at `CRM_SKILLS_CATALOG.md`, then read:
- **`worker/opportunity-markets.ts`**
  - `scoreOpportunity` L29-48 — deterministic weighted-keyword fit: a `[RegExp, weight, reason][]`
    signals table over `title+description`, base 0.34, budget nudges, clamped 0.05–0.99, returns
    `{score, reason}`. Transparent (not ML) — verticalize by editing the signals array.
  - `upsertOpportunity` L50-80 — score-on-write; dedupe by `(source_id, external_id)` (UPDATE if the
    pair exists, else INSERT with status `new`).
  - `sourceRuntime` L88-107 — the HONEST connector-status model: per-source computes
    `needs_key` / `needs_authorization` / `needs_api_approval` / `connected` from whether the secret
    or stored OAuth token is actually present, plus a human `setup` string.
  - `opportunityDashboard` L109-136 — one parallel read: sources (with runtime status), a ranked
    opportunity+bid join, recent bids, status counts.
  - `importOpportunity` L138-156 / `updateOpportunity` L158-167 — manual capture (HTTPS-validated,
    bounded ints) + status transitions against an allow-set.
  - `proposalCopy` L169-183 + `draftOpportunityBid` L185-203 — build a subject/scope/body draft
    (branch on detected need), store it (body+scope encrypted at rest via `encField`), flip the
    opportunity to `drafting`. **Never submits externally.**
  - `syncSamGov` L221-253 — the one real API adapter: date-window query, 2 MB response cap,
    `AbortSignal.timeout(20000)`, upsert each notice.
  - `syncOpportunitySources` L262-287 — per-source dispatch; non-API sources return their compliant
    assisted-track status rather than pretending to ingest.
  - `searchOpportunityRecords` L371-386 — filtered read (source/status/min-fit/query), ranked by
    `fit_score DESC, deadline ASC`.
  - `runScheduledOpportunitySync` L393-396 — cron entry: sync only `mode='api'` sources whose
    `next_sync_at` is due.
- **`worker/opportunity-mcp.ts`** L18-113 — the bid-desk tools as MCP tools (`list_market_sources`,
  `search_opportunities`, `sync_market_source`, `import_opportunity`, `set_opportunity_status`,
  `draft_opportunity_bid`) with `readOnlyHint`/`idempotentHint` annotations. Reuse the tool SHAPES;
  the transport/auth is crm-mcp-server's.
- **`migrations/0016_opportunity_markets.sql`** — `opportunity_sources` (mode api|monitor|manual|
  partner, status enum, seed rows L95-107), `market_opportunities` (status CHECK, `fit_score`,
  `submission_mode`, UNIQUE partial index on `(source_id, external_id)` L46-47, queue index L48-49),
  `opportunity_bids` (UNIQUE `opportunity_id`, status CHECK). (`mcp_api_tokens` here belongs to
  crm-mcp-server, not this skill.)
- **`worker/admin.ts`** L288-292 — dispatch: GET `opportunities`, POST `opportunities/import`, PATCH
  `opportunities/item`, POST `opportunities/draft`, POST `opportunities/sync`.
- **`worker/index.ts`** L190 — `runScheduledOpportunitySync(env)` inside `scheduled()`.
- **`public/admin/admin.js`** L1229-1314 — the panel: metric cards, source cards with the runtime
  state + "Run track", an import form, the ranked qualification table with inline status selects and
  a "Draft response" button that alerts "nothing was submitted externally".

## How to reapply it
1. **Migration.** Copy the three tables. Keep the partial UNIQUE index `(source_id, external_id)
   WHERE external_id IS NOT NULL` — it is what makes API re-syncs idempotent. Reseed
   `opportunity_sources` for THIS client's verticals (each row: id, mode, base_url, docs_url,
   submission_mode). `opportunity_bids.opportunity_id` is UNIQUE → one live draft per opportunity.
2. **Fit model.** Rewrite the `scoreOpportunity` signals array for the client's capabilities
   (keyword → weight → reason). This is deliberately transparent so the operator can see WHY a
   listing scored high; if you want ML instead, use `crm-build-standard`'s scorer and drop this.
3. **Handlers.** Port `upsertOpportunity` (score-on-write + dedupe), `opportunityDashboard`,
   `importOpportunity`, `updateOpportunity`, `draftOpportunityBid` (+ `proposalCopy` templated to
   the client), and one `sync<Source>` per API source modeled on `syncSamGov` (response cap +
   timeout + upsert loop). Keep drafts encrypted at rest (`encField`).
4. **Connector status.** Implement `sourceRuntime` so `connected` is returned ONLY when the API
   key/OAuth actually exists; everything else returns its honest `needs_*` state + a setup string.
5. **Routes + cron.** Add the five admin routes behind the CRM's admin gate; call
   `runScheduledOpportunitySync(env)` from the Worker `scheduled()` handler (it self-selects due
   `api` sources, so it is safe on a 5-min cron).
6. **UI.** Port the panel: source cards, import form, ranked table with inline status + "Draft
   response". The draft button must state plainly that nothing is submitted externally.

## Gotchas
- **Honest connector status is the whole point.** Never let a source read `connected` unless a real
  credential is present — the model distinguishes `needs_key` (add secret) vs `needs_authorization`
  (finish OAuth) vs `needs_api_approval` (apply for API access) on purpose. A faked "connected" is
  the exact dishonesty this pattern exists to prevent.
- **Assisted submission never auto-submits.** `submission_mode='assisted'` and the draft flow stop
  at a human-reviewable record. Marketplaces have ToS against automated bidding; keep the human in
  the loop and say so in the UI.
- **Fit score is deterministic keyword weighting, NOT ML** — clamp it (0.05–0.99), keep the
  `reason` string, and treat it as triage, not truth. It complements (does not replace) any ML lead
  scoring already in the CRM.
- **API adapters must be bounded:** `AbortSignal.timeout(...)` + a response byte cap (SAM.gov uses
  2 MB) or one bad upstream response can blow the CPU/memory budget on a Worker.
- **Dedupe is `(source_id, external_id)`** — a source with no stable external id will insert
  duplicates on every sync; require an external id for API sources.
- **Do not build token auth here.** Exposing the desk to an AI operator = crm-mcp-server +
  scoped-bearer-token (bearer hash-store, role→scope bundles, host/Origin allowlist). This skill is
  the desk; that skill is the door.
