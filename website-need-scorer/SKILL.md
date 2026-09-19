---
name: website-need-scorer
description: >-
  Compute how badly a BUSINESS needs a web/CRM/automation upgrade — a 0..1 need score plus
  human-readable reasons — by probing its live site: fingerprint the builder (Wix/Squarespace/Weebly/
  GoDaddy) and legacy stack (old jQuery, Flash, table layout), detect missing commerce/booking/forms,
  run Google PageSpeed, and check domain age via RDAP. SSRF-guarded, byte-capped, and KV-cached by
  domain so the outreach hot path never re-probes. Use WHENEVER prospecting must be PRIORITIZED by
  digital gap: "which prospects need us most", "score their website", "rank leads by how bad their
  site is", "find outdated / slow / no-booking sites", "who to pitch first", or "digital-gap score."
  It scores a BUSINESS's site, not a person — so it COMPLEMENTS lead-qualifier (person/deal fit +
  win-rate-by-signal) and geo-directory-prospecting (which sources the businesses and does a lightweight
  inline need heuristic); this is the heavier evidence-based probe you run to rank a batch. Do NOT
  duplicate lead-qualifier's fit model. CRITICAL CAVEAT — like the rest of the discovery Phase 1-3
  spine it ships COMPLETE but DISCONNECTED from cron/router (index.ts:183-185); the body includes the
  KV/PageSpeed bindings, admin route and cron tick it needs. Never invent signals — every point added
  carries a stored reason string.
---
# Website Need Scorer

## What it is / when to use
An evidence-based probe that answers "how much does this business need what we sell?" It fetches the
site once, accumulates penalty points for real deficiencies, caps at 100 (→ 0..1 score), and records
the top reasons so every rank is explainable. Use it to sort a fresh batch of `businesses` so outreach
hits the highest-gap prospects first — not to decide person/deal fit (that's lead-qualifier).

**Composes with:** `geo-directory-prospecting` (sources the businesses; it also does a *cheap inline*
need heuristic in `rank()` — this skill is the *heavy, cached, evidence-backed* version you run on the
short list), `open-data-signal-discovery` (the other source lane feeding `businesses`),
`contact-enrichment-deliverability` (the sibling Phase-2 stage), `lead-qualifier` (fit + win-rate —
different axis), `crm-build-standard` (stores the score/reason on the lead). This skill owns
**site-condition scoring only**.

## Reference implementation (ronininc)
- `worker/discovery/need-probe.ts` (~251 lines) — confirmed read.
- `worker/discovery/fingerprints.json` (16 lines) — the pattern lists (data, not code).
- Schema: `migrations/0010_need_probes.sql`.

Key spans:
- **Fetch + measure** `fetchSite()` L52-73: `redirect:'manual'` loop (≤4), 18s timeout, records
  `finalUrl`, `status`, and `elapsedMs`. `limitedText()` L33-50 caps the body at 500 KB.
- **Scoring** `computeProbe()` L115-168 — the whole rubric, each with a reason string:
  no HTML/unreachable +55; not HTTPS +20; no `<meta viewport>` +15; homepage >4s +12; a known
  builder +12; a legacy/outdated footprint +18; no commerce AND no booking +18; no `<form>` +8;
  PageSpeed <0.5 +20 (or <0.75 +10); domain registered ≤1yr ago +8. Score = `min(100,points)/100`,
  reasons sliced to the top 4.
- **Fingerprinting** `firstFingerprint()`/`hasAny()` L105-113 over `fingerprints.json`
  (`builders`, `outdated` [{name,patterns}], flat `commerce`/`booking` string lists).
- **PageSpeed** `pageSpeed()` L89-103: Google PSI v5, mobile+performance; returns
  `{score:null,status:'not-configured'}` gracefully when `PAGESPEED_API_KEY` is unset — the probe
  still works without it, just without the perf signal.
- **Domain age** `registrationYear()` L75-87: RDAP (`rdap.org/domain/<d>`), reads the `registration`
  event year. Best-effort; null on failure.
- **Caching** `probeBusinessNeed()` L170-188: KV `DOMAIN_PROBES` keyed `need:<tenant>:<domain>`, 7-day
  TTL, then copies `need_score`/`need_reason`/`need_probe_status` onto the `businesses` row so the
  outreach path reads D1, never re-probes.
- **Workflow + cron entry** `NeedProbeWorkflow` L190-215, `runNeedProbeTick()` L226-240 (5 pending
  businesses/tick), `triggerNeedProbe()` L242-250 (admin, ≤10 ids), `startWorkflow()` L217-224.

⚠️ **DISCONNECTED in source.** Same Phase 1-3 spine as open-data/enrichment. `NEED_PROBE` (Workflow),
`DOMAIN_PROBES` (KV) and `PAGESPEED_API_KEY` are typed in `Env` (`types.ts:69,76,67`) but the workflow
is absent from `wrangler.jsonc`, no cron calls `runNeedProbeTick`, and no admin route reaches
`triggerNeedProbe` (verified by grep). Wire it yourself (step 4).

## How to reapply it
1. **Schema.** Apply `0010`: adds `need_score` (default 0.5), `need_reason`, `need_probe_status`
   (default 'pending'), `need_probed_at` to `businesses` + a queue index
   `(tenant, need_probe_status, latest_event_date DESC)`. Requires the `businesses` table from `0008`
   (open-data-signal-discovery) or your equivalent.
2. **Fingerprints are data.** Edit `fingerprints.json` for the client's market — add the site builders
   and legacy tells you actually see. No code change needed to extend detection.
3. **Tune the rubric.** The point weights in `computeProbe()` encode "what a web/CRM/automation seller
   cares about." If the client sells something else (e.g. only SEO), reweight — keep the reason string
   next to every `points +=` so scores stay explainable.
4. **WIRE IT (the missing half):**
   - `wrangler.jsonc`: KV `{ binding:"DOMAIN_PROBES", id:... }`, Workflow `{ binding:"NEED_PROBE",
     class_name:"NeedProbeWorkflow" }`, `export { NeedProbeWorkflow }`; optional secret
     `PAGESPEED_API_KEY`.
   - Cron: add `runNeedProbeTick(env)` to `scheduled()` (5 pending/tick — cheap).
   - Admin route: `POST need-probe/trigger → triggerNeedProbe` (accepts `business_ids[]`, ≤10).
5. **Rank with it.** Sort the outreach batch by `need_score DESC` and show `need_reason` in the CRM so
   the operator sees *why* a prospect ranks high.

## Gotchas (from the code)
- **Unreachable dominates the score (+55).** A site that fails TLS or returns non-HTML scores very high
  "need" — which is often right (they need a working site) but sometimes a transient fetch error. The
  probe stores `fetch_error`/`http_status` in `details` so you can tell a real gap from a blip;
  consider a re-probe before acting on a 55-from-unreachable.
- **PageSpeed is optional and rate-limited.** Without a key it's simply skipped (no perf points). With
  a key, PSI is slow (45s timeout here) and quota-limited — it's why probing runs in a Workflow off the
  hot path and results are KV-cached for 7 days. Don't call it inline on outreach.
- **RDAP is flaky.** `rdap.org` doesn't cover every TLD; `registrationYear` returns null a lot. The
  "new domain" signal is a bonus, never a requirement.
- **Cache key is by domain, not business.** Two `businesses` rows sharing a domain share a score — fine
  (it's the *site* being scored), but a franchise with many locations on one site all rank identically.
- **SSRF guard is mandatory** (`safeWebsite()` L20-31 rejects localhost/`.local`/`.internal`/private
  IP ranges/odd ports) — the URL comes from untrusted ingested data.
- **Inert until wired** — same as the rest of the discovery spine; the reference repo never runs it in
  production.
