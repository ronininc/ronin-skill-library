---
name: geo-directory-prospecting
description: >-
  Daily lead SOURCING from OpenStreetMap: geocode a market (Nominatim), run a vertical-specific
  Overpass NWR query, dedupe, then cold-start fit-rank each candidate on need/capacity/budget-fit and
  route partner vs direct — a durable Cloudflare Workflow that GENERATES a fresh prospect list from a
  city + vertical, with no purchased data. Use WHENEVER a build needs to "find businesses to reach
  out to", "generate leads for [city/vertical]", "source prospects", "fill the pipeline", "cold lead
  list from a map", "who should we pitch in [market]", or a self-running prospecting engine for a
  local-business CRM. COMPLEMENTS crm-build-standard (which stores the contact/deal and SCORES fit
  once a lead exists) and lead-qualifier (win-rate-by-signal) — this skill is the SOURCE that feeds
  them; do NOT reimplement their scoring/dialer. Pairs with contact-enrichment-deliverability (verify
  the emails it finds) and rotating-leadgen-scheduler (run it on a cadence across markets). Guardrails:
  public OSM/website data only, SSRF-guarded fetches, byte-capped reads, honest under-delivery (returns
  fewer than target rather than padding with weak matches), one active run at a time.
---
# Geo-Directory Prospecting

## What it is / when to use
A durable Workflow that turns **a market + a vertical** into a ranked list of real prospect businesses,
written straight into the CRM's campaign queue. It geocodes the market to a bounding box, queries a
public business directory (OpenStreetMap via Overpass) for that vertical, enriches each hit from its
own public website (decision-maker, emails, socials, text signals), then **cold-start ranks** on
need × budget-fit × data-quality and keeps only high-value matches. Use it as the front of a lead-gen
CRM when you have no purchased list and want a sovereign, repeatable source.

**Composes with:** `crm-build-standard` (the contact/deal store + fit-scoring ML + dialer this feeds),
`lead-qualifier` (signal→win-rate once outcomes accrue), `contact-enrichment-deliverability` (upgrade
the emails it discovers to verified/deliverable), `decision-maker-email-extractor` (the owner-finding
atom, extracted from this file), `rotating-leadgen-scheduler` (run it daily across a market rotation),
`governed-email-outreach` (send to what it queues). This is the SOURCE stage — it does not send, score
fit long-term, or dial; those belong to the skills above.

## Reference implementation (ronininc)
`worker/lead-generation.ts` (whole file, ~646 lines) — confirmed read. Live and WIRED: workflow class
exported at `index.ts:42`, launched from admin route `outreach/generate` (`admin.ts:389`), binding
`LEAD_GENERATION` in `wrangler.jsonc`. Schema: `migrations/0007_lead_generation_workflow.sql`
(+`0022_lead_tracks.sql` for the partner/direct column).

Key spans:
- **Geocode → bbox** `discover()` L128-151: Nominatim `format=jsonv2&limit=1`, then **clamp** the bbox
  to ±0.18 lat / ±0.22 lon around center so a large municipal boundary can't make Overpass enumerate a
  whole county.
- **Vertical → OSM selectors** `selectors()` L77-94 (data-driven map) and `overpassQuery()` L96-106
  (`nwr[...](bbox);out center tags N;`). The `~` in a selector becomes a regex clause.
- **Overpass failover** L159-176: three endpoints tried in order, 25s `AbortSignal.timeout`, honest
  "temporarily unavailable" if all fail.
- **Dedup** L182-193: `Set` keyed on email || website || `name|address`.
- **Website enrichment** `enrich()` L354-385 → follows ≤2 `/about|/team|/leadership` pages
  (`likelyTeamPages` L308-321), harvests emails (`emailsFromHtml` L244-249), finds the decision-maker
  (`decisionMakerFromPage` L272-306, see decision-maker-email-extractor skill).
- **Cold-start ranking** `rank()` L387-428: `need` (missing social/conversion/automation/legacy-stack
  signals), `capacity` (scale/category/credibility words), `budgetFit` from `targetDealCents` via a
  log10 required-capacity curve, `matchScore = need*.42 + budgetFit*.43 + dataQuality*.15`.
- **Prepare + queue** `prepareLead()` L430-457 (upsert `contacts` ON CONFLICT(email), blend with the
  learned email score from `lead-learning`), `queueLead()` L459-477 (INSERT OR IGNORE into
  `campaign_recipients`, honor `outreach_suppressions`, store the score components + `match_reason` for
  auditability).
- **Workflow orchestration** `LeadGenerationWorkflow.run()` L487-582: `step.do` per phase, per-batch
  enrich-and-rank (`ENRICHMENT_BATCH_SIZE=1`), a `skip-unreadable-*` step so one bad site never fails
  the run, final `queue-best-learned-matches` slice to `targetCount`.
- **Public entry** `startLeadGeneration()` L608-646: validates location/count(1-100)/deal($500-$1M),
  refuses a second concurrent run, creates the campaign, launches.

## How to reapply it
1. **Schema.** Copy `0007` (the `lead_generation_runs` audit table + the `campaign_recipients`
   score/provenance columns: `generation_run_id, source_url, match_score, need_score, capacity_score,
   match_reason`). If dual-track, copy `0022` (`lead_type` on campaigns/contacts/runs). Your CRM must
   already have `contacts` (UNIQUE email), `campaigns`, `campaign_recipients`, `outreach_suppressions`.
2. **Workflow binding.** Add to `wrangler.jsonc` `workflows`: `{ name, binding: "LEAD_GENERATION",
   class_name: "LeadGenerationWorkflow" }`, and `export { LeadGenerationWorkflow }` from the entry.
3. **Selectors = data.** Rewrite `selectors()` for the client's target verticals using real OSM keys
   (`shop`, `amenity`, `office`, `craft`, `healthcare`, `tourism`). This is the one client-specific
   edit; everything else is reusable.
4. **Offer profile drives need.** Pass the client's actual offer string; `rank()` tokenizes it and
   scores "fit for <offer>" when the site lacks those tokens.
5. **Route.** Wire an admin POST (e.g. `outreach/generate`) to `startLeadGeneration`. Optionally add
   the rotating-leadgen-scheduler skill to run it unattended.
6. **User-Agent + contact email.** Set a real UA and contact email on the Nominatim/Overpass fetches
   (L14, L133) per each service's usage policy.

## Gotchas (from the code + memory)
- **Nominatim/Overpass etiquette:** one geocode per run, a descriptive User-Agent, a contact email in
  the query, and bbox clamping — public instances rate-limit or 429 heavy callers. Memory
  (osm-overpass-egress-gotchas): round precise coords to ~5 decimals or a false CARD_LIKE filter can
  trip; an unquoted regex value yields Overpass **400**; concurrent Overpass calls get rate-limited, so
  keep it one-in-flight.
- **Under-deliver on purpose:** the run returns fewer than `targetCount` rather than padding the queue
  with weak matches (thresholds `MIN_HIGH_VALUE_MATCH=65 / NEED=55 / CAPACITY=40`, L19-21). Don't
  "fix" this by lowering thresholds to hit a volume number.
- **Free-plan CPU:** enrichment keeps a raw 9 KB HTML prefix instead of full DOM cleanup (L376-378) and
  batches one candidate per durable step; heavy regex on a rendered page will blow the CPU limit.
- **SSRF:** `isPublicWebsite()` L212-224 rejects localhost/`.local`/`.internal`/IP-literal/non-80-443
  ports before any fetch — keep it; candidate websites are attacker-influenced input.
- **One run at a time:** L621 refuses to start if a `queued`/`running` run exists; the scheduler relies
  on this. A stuck run blocks the schedule until it completes or is marked failed.
- **Email is the identity key:** `contacts` upsert is `ON CONFLICT(email)`; a candidate with no public
  email is dropped at `prepareLead` (L432). Sourcing volume is gated by email discovery — pair with
  contact-enrichment-deliverability / decision-maker-email-extractor to lift it.
