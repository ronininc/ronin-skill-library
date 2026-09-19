---
name: notion-intake-crm-cloner
description: Clone a client-owned Leads + Intake + Marketing-ROI CRM into a client's OWN Notion workspace via the Notion API — built for personal-injury / accident law firms but reusable for any lead-driven service business. Use WHENEVER the task is "build a CRM in Notion for a client", "set up their intake pipeline", "clone the intake CRM", "give the attorney/firm a lead+marketing CRM they own", or productizing lead-gen as a per-client node. Scope is leads / intake / marketing ROI — NOT case management, so NO PHI and no HIPAA wall (injury data is severity buckets, never medical records). The client owns every database; the recurring value is the intake automation + monthly ROI tuning, not the tables.
---

# Notion Intake-CRM Cloner

Stamps a complete **client-owned** intake + marketing-ROI CRM into a client's Notion workspace, so they own
it outright and can never be held hostage by a vendor. Same skill clones the next client / vertical.

## When to use
"Build a Notion CRM for [client]", "set up their intake pipeline", "clone the intake CRM", "PI/accident
attorney needs a CRM", or packaging lead-gen as a per-client owned node. Full design: the blueprint doc
(`PI Intake CRM — Blueprint`).

## What it builds (two shapes, one script)
- **`--shape marketplace`** (default) — a two-sided case-matching marketplace (e.g. **Case Plug**):
  **Consumer Leads → Matches → Attorney Partners** + Billing/Invoices + Marketing Channels + Tasks + Staff.
  Compliance fields baked in: Sourcing (Inbound/Purchased/Unknown), Consent/TCPA, Already-Represented
  (auto-disqualify), Partner Payment Model (default Flat-per-lead) + Fee-agreement-on-file.
- **`--shape firm`** — single-firm intake CRM: Leads · Marketing Channels · Referral Network · Signed Cases.

Then the human finishes the pipeline status + formulas + the Kanban / Speed-to-lead / Matching-queue /
Marketing-ROI / **Compliance** views in Notion (the API can't set status groups or formulas).

## Run it (the clone)
```
NOTION_TOKEN=secret_xxx  python3 scripts/setup_notion_crm.py --parent <PARENT_PAGE_ID> [--shape marketplace|firm]
```
Token = a Notion **internal integration** secret (notion.so -> Settings -> Connections -> integrations);
share the parent page with that integration first. It creates every DB IN THAT WORKSPACE = the client owns it.

## STATUS / honesty
- The cloner is authored against the Notion API but **not yet run against a live workspace** — verify on the
  first token (build into a throwaway page, confirm, then the client's page). Do NOT claim it's proven until
  a real run succeeds. (Contrast: the az-cash-buyer-finder was verified against the live county API.)
- **Credentials:** never paste a raw token into chat. The operator runs the cloner with the client's token,
  or it's supplied through the governed vault.

## Honesty invariants (design-defining)
- **No PHI in Notion** — injury = severity buckets, never medical records. Keeps it out of HIPAA scope.
- **Solicitation law governs how leads are WORKED** (DPPA / AZ Bar Rule 7.3 30-day / TCPA / DNC): this CRM
  organizes INBOUND leads; it must never become a tool to cold-solicit accident victims.
- **National scale:** archive closed leads (Notion slows past ~10-20k rows, API ~3 req/s). If raw volume is
  huge, an owned ingest worker becomes source-of-truth and Notion shows the working set.

## The recurring-value loop (why this is a product, not a one-off)
Intake ingestion (forms / LSA / call-tracking → Leads via API) + missed-call-text-back + auto-assign, then
a **monthly tuning pass**: which sources/creatives produce SIGNED cases → reallocate spend. That measurable
"consistently making their lead gen better" is the retainer.
