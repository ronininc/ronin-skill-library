---
name: multi-source-identity-resolver
description: >-
  Turn one weak handle (a username, an email, a domain) into a normalized identity dossier built
  from MULTIPLE public OSINT sources at once (cross-platform account discovery + email-registration
  probes), then RESOLVE the fields with authority-aware discipline: an API-EXTRACTED value outranks
  a scraped display string, a value is only asserted when an authoritative source backs it, and a
  cross-platform username COLLISION (the same handle owned by different people) is surfaced as a
  conflict flag instead of being silently collapsed into one person. Every output is stamped
  CANDIDATE, not verified identity, and nothing is fabricated. Use WHENEVER a build must "enrich
  this lead from public sources", "what accounts does this handle have", "build a dossier from a
  username/email", "resolve who this is across platforms", "cross-reference their profiles", or feed
  a grounded-truth packet to an outreach/decision step. COMPLEMENTS decision-maker-email-extractor
  (which finds WHO runs a business from its own site) and contact-enrichment-deliverability (which
  grades whether an address is DELIVERABLE) — this skill answers "which cross-platform profiles
  plausibly belong to this handle, and how sure are we," a layer neither does; and it feeds
  reference-intel-matcher (roster match) and public-relationship-graph (who-can-help). Guardrails:
  PUBLIC sources only; a matched profile is a CANDIDATE to confirm before any outreach; authoritative
  (API) values outrank scraped ones; name conflicts across platforms are surfaced, never merged;
  the domain-recon layer is explicitly a stub until wired — never present it as done.
---
# Multi-Source Identity Resolver

## What it is / when to use / what it composes with
Given a single lead signal, run several PUBLIC enrichment tools and fold their outputs into one
dossier where each derived field carries **how it was learned**. The value of the pattern is not the
scraping — it is the **resolution discipline**: multiple sources disagree constantly (a username
collides across platforms, a scraped "name" is a page title, one API says one thing and a bio says
another), and this decides what may be asserted and what must be flagged.

- **Not `decision-maker-email-extractor`:** that reads a business's OWN website to name its owner.
  This takes a handle/email and discovers cross-platform accounts, then resolves identity across them.
- **Not `contact-enrichment-deliverability`:** that proves an address accepts mail. This decides
  whether the person behind the accounts is even one person, and which name/photo may be trusted.
- **Feeds `reference-intel-matcher`** (match the resolved identity to a curated roster) and
  **`public-relationship-graph`** (map the resolved person's warm ties). Run behind
  `residential-edge-relay` when the CRM is on the edge (see `runner.py`).

## Reference implementation — exact source (lift the proven code)
`~/ronin-osint/enrich.py`:
- **Source adapters, normalized to a common profile shape:** `run_maigret()` (cross-platform account
  discovery) — `enrich.py:20-63`; the authority flag is set from whether the source API actually
  extracted structured ids: `"authoritative": bool(ids.get("_extractor"))` at `enrich.py:51`.
  `run_holehe()` (email → registered services) — `enrich.py:65-81`.
- **THE CORE — authority-aware field derivation:** `derive_field(profiles, key)` —
  `enrich.py:83-103`. Authoritative values and scraped values are counted separately
  (`enrich.py:91-97`); ranked authoritative-first then by count (`enrich.py:100`); `best` is set
  ONLY if the top-ranked value is authoritative — a purely scraped value never gets asserted
  (`enrich.py:102`); `conflict = (distinct values > 1)` (`enrich.py:103`).
- **Dossier derivation + honest identity note:** `_derive()` — `enrich.py:105-126`. Photo is taken
  from an authoritative profile if any, else best-effort and flagged (`enrich.py:110`,`115-116`);
  `fullname_conflict` + a plain-English `identity_note` warn when the same handle maps to different
  display names (`enrich.py:117-125`).
- **Dossier envelope:** `enrich.py:150-166` — `confidence: "candidate"` (`:162`), a note that a match
  is a candidate not verified identity (`:163-164`), and `warnings[]` carrying any source failure.
- **The stub to respect:** `domain_recon` returns `{status: "pending"}` — the domain layer is NOT
  wired (`enrich.py:159-160`). See Gotchas.

## How to reapply — the schema + THE INVARIANT
1. **One profile shape per source.** Every adapter emits `{site, url, username, image, fullname,
   location, company, …, authoritative: bool, extractor}` so `derive_field` can treat them uniformly
   (`enrich.py:40-56`). Add a source by writing one adapter to this shape — the resolver is untouched.
2. **Derive, don't merge.** For each identity field, call `derive_field`; store `{value, conflict,
   candidates[]}`. Assert `value` only when it came from an authoritative source; always keep the
   full `candidates` list for the human review step.
3. **Ship the dossier as `…/dossier@1`** with `confidence:"candidate"`, per-field candidates, the
   `identity_note`, and `warnings`. Map onto a `lead_dossiers.profile_json` column; the review→import
   path lets an operator promote confirmed fields (README integration plan).

**THE INVARIANT:** a value is asserted only when an authoritative source backs it; every conflict is
surfaced, never silently resolved; the whole dossier is a CANDIDATE for a human to confirm. A
username colliding across platforms means the same handle can belong to DIFFERENT people, so the
resolver refuses to collapse them into one asserted identity.

## Gotchas — real pitfalls from the code + how it's validated
- **Username collisions are the #1 trap.** Two people can hold the same handle; naive enrichment
  fabricates a Frankenstein person. The conflict flag + "confirm the person before trusting any
  single name" note exist precisely for this (`enrich.py:122-125`). Never drop the candidates list.
- **Scraped ≠ authoritative.** A display name in a page title outranks nothing; only an API-extracted
  value earns assertion (`enrich.py:102`). Keep the `_extractor` signal when you add a source.
- **Never fabricate.** No source, no value — the field stays null and a warning is recorded
  (`enrich.py:144`,`148`). The dossier states "no fabricated data" (`enrich.py:164`).
- **UNWIRED layer — flag it.** `--domain` produces only a `pending` stub; theHarvester/GHunt/
  SpiderFoot are "next" per the repo README, not built. Presenting domain recon as complete would be
  dishonest — treat it as a gap to fill, and say so.
- **Governed egress + host-bound.** The heavy scan needs the local OSINT tools installed and (per the
  operator's doctrine) an authorized run; the CRM Worker never runs Python — it enqueues, the
  residential relay fulfills (`runner.py`).
- **Business-contact enrichment only.** The source repo deliberately excludes face-search / dark-web
  / individual-tracking. Keep new sources on the public-business-contact side of that line.
