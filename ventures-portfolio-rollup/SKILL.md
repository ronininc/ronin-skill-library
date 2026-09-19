---
name: ventures-portfolio-rollup
description: >-
  A read-only, single-query PORTFOLIO ROLLUP for a Cloudflare Worker + D1 CRM that runs several
  automated verticals at once: one SQL statement of correlated sub-counts + sub-sums rolls up every
  vertical (blog network, outreach campaigns, store, sales reps, content studio, acquisitions/deals,
  cash buyers, contacts, wire revenue) into ONE business-pulse object, plus a portfolio dashboard of
  per-vertical cards with deep-links into each app tab. It computes over the REAL per-vertical tables
  at request time — there is NO registry table to seed, drift, or keep in sync (add a vertical → it
  appears the moment its table exists). Use WHENEVER a multi-line business needs "one screen for the
  whole machine", "business pulse / factory overview", "roll up all my verticals", "portfolio
  dashboard", "how many blogs/campaigns/orders/deals/reps do I have and how much revenue", or "give
  the oversight brain a PII-free snapshot of everything". This is the specific MULTI-VERTICAL rollup —
  it COMPLEMENTS ops-console (the general KPI command-center shell / ops-card grid; use THAT for a
  single business's operational KPIs, use THIS to aggregate ACROSS independent verticals) and sits on
  top of the per-vertical skills it counts (auto-blog-network, sales-force-roster-distribution,
  commerce-spine, content-studio-publisher, the wholesale-RE atoms, wire-payment-collect-reconcile) —
  do NOT re-implement any of those; this only READS their tables. Because its output is PII-free
  aggregates, it is the natural read-model for governance-diode / crm-mcp-server to expose to an
  oversight role. Guardrails: the single query FAILS if any referenced table is absent (include only
  the verticals that exist), it is read-only (no migration, no cron, no writes), and revenue is two
  distinct streams (store-order totals vs received wire payments) — never conflate them.
---

# Ventures Portfolio Rollup

## What it is / when to use
A "whole factory at a glance" read model. One correlated-subquery statement returns counts and
revenue for every automated vertical the CRM runs, and a dashboard renders one card per vertical with
an "Open →" deep-link into that app. Reach for it when an operator runs MANY independent verticals on
one Worker + D1 and wants a single pulse screen (and a single MCP snapshot) instead of clicking
through each app — a factory overview, not a per-business KPI board.

**Composes with:** `ops-console` (the general command-center shell / ops-card grid — that is the
right tool for ONE business's operational KPIs; this rolls up ACROSS verticals, a different job — do
not duplicate it); the per-vertical skills whose tables it counts — `auto-blog-network`,
`sales-force-roster-distribution`, `commerce-spine`, `content-studio-publisher`,
`wholesale-real-estate` / `buy-box-matcher` (deals + cash buyers), `wire-payment-collect-reconcile`
(received revenue); and `governance-diode` + `crm-mcp-server` (its PII-free aggregate is exactly the
snapshot an oversight role should be able to pull — expose it as a read-only MCP tool). It OWNS none
of those — it is a pure derived view, like `attack-list-priority-queue`.

## Reference implementation (ronininc CRM — OPEN before lifting)
Cloudflare Worker + D1. Start at `CRM_SKILLS_CATALOG.md`, then read:
- **`worker/ventures.ts` L12-40** — the whole skill, two functions, no migration:
  - `venturesSummary` L12-36 — ONE `env.DB.prepare(...).first()` whose columns are correlated
    sub-selects, one (or a few) per vertical:
    - blogs: `COUNT(*)`, `COALESCE(SUM(enabled),0)` as active, published-post count, `SUM(views)` L15-18.
    - campaigns: counts split by `campaign_kind` (`client` / `recruit`) and `status='active'` L19-21.
    - store: active `products`, all `store_orders`, and `SUM(total_cents)` gated to the paid-ish order
      statuses `('paid','fulfilled','shipped','delivered')` L22-24.
    - reps: total + `status='active'` L25-26; `content_items` not cancelled L27.
    - acquisitions: `re_deals` open + `stage='assigned'`, `cash_buyers` active L28-30.
    - `contacts` total L31; `wire_payments` `SUM(amount_cents) WHERE status='received'` L32 — the
      SECOND, distinct revenue stream (settled bank transfers), separate from store-order revenue.
    Then a second small read for the blog list (`SELECT id,slug,title,enabled … LIMIT 100`, L34) is
    spread into the result L35. Everything is `COALESCE(...,0)` so an empty vertical returns 0, not
    null.
  - `venturesDashboard` L38-40 — thin `json(await venturesSummary(env))` wrapper for the admin route.
- **`worker/admin.ts` L55** (import) **L340** — `GET ventures` → `venturesDashboard(env)`, behind the
  admin gate; clearance is mapped in `worker/auth.ts` L183 (`ventures: 'acquisitions'` — the tab
  reuses an existing clearance rather than minting a new one).
- **`worker/solomon-mcp.ts` L17** (import) **L190-195** — the SAME `venturesSummary` re-exposed as a
  read-only MCP tool (`list_ventures`) so an oversight brain gets the identical PII-free snapshot. One
  source of truth, two surfaces (admin JSON + MCP).
- **`public/admin/admin.js` L1702-1730** — `loadVentures`: fetches `/api/admin/ventures`, renders a
  top "factory" pulse card (contacts, received revenue, active reps, active campaigns) then one
  `card(eyebrow, title, metrics, tab)` per vertical (blogs, campaigns, sales force, store, content,
  acquisitions), each with an `Open →` button that calls `activateTab(...)` to jump into that app.
  Money via a `money2()` cents-formatter; metrics via an `apMetric()` helper.

## How to reapply it
1. **No migration, no cron, no writes.** It derives entirely from tables the per-vertical skills
   already created. There is nothing to seed and nothing to schedule — that "no registry to drift" is
   the point (contrast a stored `ventures` table you'd have to keep in sync).
2. **Build the rollup query FROM the verticals this client actually has.** Copy `venturesSummary` and
   DELETE the sub-selects for tables that don't exist in this build (a single missing table makes the
   whole statement throw — see gotchas). Add a sub-select per new vertical the same way. Keep every
   aggregate wrapped in `COALESCE(...,0)`.
3. **Handler + route.** Port `venturesSummary` + `venturesDashboard`; register one `GET ventures`
   route behind the admin/staff gate. Map its clearance to an existing role (as the reference reuses
   the `acquisitions` clearance) rather than inventing one, unless the portfolio view deserves its own.
4. **MCP (optional but cheap).** Register the same `venturesSummary` as a read-only/idempotent MCP
   tool via `crm-mcp-server` so an operator/oversight brain can pull the pulse; because the output is
   counts + revenue only (no PII), it is safe to hand to an oversight role through `governance-diode`.
5. **UI.** Port `loadVentures`: a top pulse card + one deep-linking card per vertical. Only render a
   card for a vertical whose app tab exists. Recompute on load (no stored state to invalidate).

## Gotchas
- **The single query FAILS CLOSED if any referenced table is missing.** `SELECT (SELECT COUNT(*) FROM
  blogs) …` throws "no such table: blogs" for the WHOLE statement if `blogs` isn't in this build — so
  the rollup must be assembled to match the verticals actually present. When you add a vertical later,
  add its sub-select at the same time you add its migration.
- **`COALESCE(SUM(enabled),0)` as "active" is coupled to the schema.** It assumes `blogs.enabled` is a
  0/1 integer flag; if your equivalent uses a text status, switch to `SUM(CASE WHEN status='active'
  THEN 1 ELSE 0 END)`. Same pattern anywhere you sum a boolean.
- **Two DISTINCT revenue streams — do not add them blindly.** `store_revenue_cents` is
  `SUM(store_orders.total_cents)` for paid-ish orders; `revenue_received_cents` is
  `SUM(wire_payments.amount_cents)` for settled wires. They measure different rails (card/store vs
  bank transfer) and can double-count if a wire also books a store order. Show them separately (the
  reference does) unless you deliberately reconcile them.
- **The store-revenue status set must match the commerce lifecycle.** The gate is the literal set
  `('paid','fulfilled','shipped','delivered')`; if `commerce-spine`/`order-pnl` uses different order
  statuses in this build, revenue silently under- or over-counts. Keep the set in sync with the
  order-status CHECK.
- **Correlated sub-selects are cheap but not free.** Each is its own aggregate scan; it's fine for a
  handful of verticals with indexed tables, but a dozen `COUNT(*)`/`SUM()` over large unindexed tables
  on every dashboard load adds up. It's read-only, so cache briefly or move to cron only if it
  actually gets slow — don't pre-optimize away the freshness.
- **The blog list is capped `LIMIT 100`.** The spread `blogs` array is a convenience sample, not a
  full inventory — don't drive counts off `blogs.length`; use the `blogs_total` aggregate.
- **Keep it PII-free.** Its value as an oversight/MCP snapshot depends on it emitting only counts and
  revenue — never widen it to return contact names, emails, or deal notes, or it can no longer be
  handed across the governance diode.
