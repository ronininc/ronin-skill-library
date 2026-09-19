---
name: reference-intel-matcher
description: >-
  Resolve an inbound record (a lead, a contact, a form submission) against a CURATED REFERENCE DATASET of
  known high-value entities and assign a PRECISION-GATED confidence tier — where only high-precision signals
  (a suffix-tolerant exact person-name match against a named principal, or an email domain equal to a
  reference entity's verified website domain) can earn the top tier, and a weak signal (a generic company
  word) can NEVER produce a false top-tier flag. It bundles the reusable matching primitives: name
  normalization, suffix-tolerant first+last person matching (ignoring middle names / Jr / II), registrable
  email-domain extraction with a freemail blocklist, whole-word brand-token matching, and a generic-stopword
  exclusion — then ranks matches strong-first and by an attached magnitude (e.g. capital-to-deploy). Use
  WHENEVER a build must "match a lead against our known list", "flag the whales / VIPs in this inbound",
  "is this person one of our target accounts", "score inbound against curated intel", "identity-resolve to a
  reference set", or "attach proof (filing/socials) when a lead matches someone we know". It COMPLEMENTS
  buy-box-matcher (which matches an item against saved FILTER CRITERIA — this matches an entity against a
  curated ROSTER of known entities), decision-maker-email-extractor / lead-qualifier (person verification and
  fit — this adds reference-set precision TIERING they don't do), and az-cash-buyer-finder (which SOURCES/
  BUILDS the reference intel this matches against — do NOT re-implement the sourcing). Guardrail: a false
  top-tier flag is the one thing this refuses to ship — weak signals are capped at a "possible" tier by
  construction, and the reference data holds no fabricated fields.
---
# Reference Intel Matcher

## What it is / when to use / what it composes with
Given an inbound record and a curated reference set of known entities (people + organizations, with verified
attributes), decide *which known entity, if any, this is* and *how confident we are* — expressed as a tier
where the confidence is governed by the **precision of the signal that matched**, not by how many weak
signals piled up.

- **Not `buy-box-matcher`:** that matches an item to a subscriber's saved *criteria* (cities, price, type).
  This matches an inbound *identity* to a *roster of known entities* and tiers by signal precision.
- **Not `lead-qualifier` / `decision-maker-email-extractor`:** those verify a person's real presence / find
  the owner. This is the reference-set resolution + precision-gated tiering layer on top.
- **Fed by `az-cash-buyer-finder`:** that builds the verified reference intel (named principals, org domains,
  socials, magnitude). This skill only *matches against* it — it does not source or rank the roster.

## Reference implementation — exact source
`~/Projects/ronin-jv-lead-engine/src/score.js`:
- **Normalization:** `norm(s)` — `score.js:4-6` (lowercase, strip punctuation, collapse spaces).
- **Suffix-tolerant person match:** `SUFFIX` set + `core(nrm)` + `nameMatch(leadName, principalNorm)` —
  `score.js:14-23`. Requires first+last on both sides; matches on FIRST and LAST token only, ignoring middle
  names and Jr/Sr/II/III. This is the high-precision human signal.
- **Domain signals:** `domainOf(url)` / `emailDomain(email)` — `score.js:26-35` (strip scheme/www, take host);
  `FREEMAIL` blocklist — `score.js:37-38` so a gmail address never counts as an org-domain match.
- **Whole-word brand token:** `wholeWord(hay, needle)` — `score.js:9-12` (regex word-boundary), used only for
  the WEAK company-mention signal.
- **The tiering (the precision gate):** `scoreLead(lead, ref)` — `score.js:45-108`. Signal 1 (STRONG) principal
  name; Signal 2 (STRONG) email-domain == a reference entity's website domain; Signal 3 (WEAK) distinctive
  non-generic brand token. `strong.length` decides whale/likely; a weak-only match is capped at
  `possible-match` and `isWhale` stays false (`score.js:98-108`). Matches are ranked strong-first then by
  magnitude (`score.js:92`).
- **Generic-word exclusion:** `GENERIC` set + `isGenericWord` — `score.js:111-113` (fund/llc/capital/group/…)
  so "Capital Partners" can't match everyone.
- **Reference tables:** `schema.sql:2-11` — a `sponsors` (org: brand PK, website, socials, verification,
  magnitude) and a `principals` (name, name_norm, brand) table, loaded from D1 via `loadRef` (`index.js:17-23`).

## How to reapply
- **Two reference tables:** one for organizations (unique brand/name key, a verified `website`, a
  `verification` status, a numeric magnitude, optional socials/citation) and one for named people
  (`name`, `name_norm`, foreign key to the org). Index the normalized name (`schema.sql:11`).
- **Match order = precision order:** try the strong signals first (exact suffix-tolerant name; domain equality
  against a non-freemail email domain), THEN the weak signal (whole-word non-generic brand token). Track per
  match whether ANY strong signal fired.
- **Tier from precision:** top tier requires a strong signal AND a "verified" reference; a strong signal with
  an unverified reference is one tier down; weak-only is "possible"; no match is "unmatched" (still a real
  inbound, just not enriched). Attach the matched entity's proof (citation, socials, magnitude) to the result.

## Gotchas (from the code)
- **A false top-tier is the failure you refuse to ship.** Never let a stack of weak signals promote to the top
  tier — the tier is a function of the STRONGEST signal, not the count (`score.js:98-108`).
- **Freemail is not an org signal.** Always exclude generic mail hosts before treating an email domain as an
  identity signal (`score.js:61`, `FREEMAIL` `score.js:37`).
- **Generic words match everyone.** Exclude business stopwords from the token signal or "Group"/"Capital" will
  match the whole roster (`score.js:71`, `GENERIC` `score.js:111`).
- **Names need first AND last on both sides.** A single-token name is not a confident match — require ≥2 core
  tokens (`score.js:21`), and match only first+last so middle names / suffixes don't cause misses.
- **Patterns only.** The reference dataset must hold verified, cited fields — never fabricate a domain, phone,
  or magnitude to force a match. (Do not carry any real roster contents into a build; source them per
  `az-cash-buyer-finder`.)
