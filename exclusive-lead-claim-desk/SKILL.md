---
name: exclusive-lead-claim-desk
description: >-
  The PULL side of a lead marketplace: a self-serve BUYER portal where partners log in, browse the leads
  inside THEIR coverage as masked teasers, and CLAIM one exclusively — with the contact details being the
  PRODUCT, so they stay hidden until the claim is recorded. A claim records what is OWED and reveals the
  full contact atomically; it NEVER charges a card. Exclusivity is enforced at the DB layer (a partial
  UNIQUE index allows at most one non-released claim per lead), coverage is re-verified on the claim (not
  trusted from the browse list), and a release frees the lead back to the pool. Use WHENEVER buyers should
  SHOP and CLAIM leads/opportunities themselves rather than have them auto-pushed — "let partners browse and
  claim leads", "exclusive lead claim", "buyer self-serve portal", "first-come-first-served lead pool",
  "reveal contact after purchase", "mask the lead until they buy", "release/return a lead", or a two-sided
  marketplace's demand side. It COMPLEMENTS lead-marketplace-auto-match (the PUSH model against the same
  tables — offer this as the alternative distribution mode), cf-identity (the login pattern it mirrors),
  prepaid-wallet-ledger (the separate money path a claim's OWED balance later settles through), and
  crm-build-standard. Do NOT charge inside the claim — recording OWED and moving money are different steps.
---
# Exclusive Lead-Claim Desk (buyer-pull marketplace + PII-gated reveal)

## What it is / when to use / what it composes with
A demand-side portal: buyers see only leads their coverage covers, shown as **masked teasers** (initial +
type + region + price), and buy one by **claiming it exclusively**. The reveal-on-purchase + exclusivity +
release loop is the reusable core. Any marketplace where "the contact is the product" (lead resale, listing
allocation, territory/opportunity claiming) needs this exact shape.

- **Composes with**: `lead-marketplace-auto-match` (the PUSH twin — same `leads`/`matches` tables, different
  distribution model; a build can run either or both), `cf-identity` (PBKDF2 + HMAC-cookie session pattern
  mirrored here), `tcpa-consent-capture` (only consented, non-conflicted leads are ever surfaced),
  `prepaid-wallet-ledger` (the OWED balance is settled later by the real money path), `append-only-audit-log`.

## Reference implementation (exact source)
- Whole module: `/Users/robbiebrown/Projects/case-plug/src/attorney-portal.js` (437 lines).
  - Masked teaser (contact hidden until claim): `maskLead` `attorney-portal.js:113-122`; full-contact reveal `fullContact` `:123-126`.
  - Coverage-scoped available leads (state IN / case_type IN + consent EXISTS + no active claim): `availableLeads` `:131-148`.
  - **Claim** (re-verifies stage/consent/coverage/eligibility, refuses if already claimed, then an atomic
    `batch`: insert `lead_claims` OWED + lead→matched + insert accepted match + audit): `claim` `:181-220`.
  - **Release** back to the pool (claim→released, lead→qualified, audit): `release` `:223-239`.
  - Invoice/owed summary for the buyer dashboard: `invoiceSummary` `:164-178`.
  - Session (HMAC over `SESSION_SECRET`, fail-closed if unset): `:42-57`; PBKDF2 hashing (100k cap): `:71-92`;
    admin-provisions-login (Bearer): `adminCreateLogin` `:242-262`.
  - Router mounting the whole `/attorney*` space, gating itself: `handleAttorneyPortal` `:278-331`; mounted before
    the generic admin gate in `src/index.js:301-303`.
- Schema: `lead_claims` `schema.sql:298-305` and the **exclusivity lock** —
  `CREATE UNIQUE INDEX ... ON lead_claims(lead_id) WHERE status != 'released'` `schema.sql:306`;
  `attorney_users` (PBKDF2 columns) `schema.sql:292-297`.

## How to reapply
1. **Schema**: `lead_claims(lead_id, buyer_id, price_cents, status IN ('claimed','released','invoiced','paid'),
   invoice_status IN ('owed','invoiced','paid','void'))` + a `buyer_users(buyer_id, email UNIQUE, pass_hash,
   pass_salt, iterations)` login table. **Add the partial unique index** so the DB itself refuses a second
   active claim: `CREATE UNIQUE INDEX ... ON lead_claims(lead_id) WHERE status != 'released'`.
2. **Browse** returns masked teasers only — never phone/email — scoped by the buyer's coverage arrays and
   filtered to consented, non-conflicted, unclaimed, still-qualified leads.
3. **Claim** re-checks EVERYTHING server-side (stage still qualified, consent present, inside coverage,
   eligibility flag set, no active claim), then commits the claim + lead-state + match + audit in ONE batch,
   and only then returns the full contact.
4. **Release** flips the claim to `released` (which the partial index now ignores) and the lead back to
   `qualified` so it re-enters the pool.
5. **Session/login**: mirror `cf-identity` — HMAC-signed cookie over `SESSION_SECRET` (fail closed if unset),
   PBKDF2-SHA256 at **100000 iterations max** (Workers throttles above that), admin provisions logins by Bearer.

## Gotchas (from the code)
- **The exclusivity lock lives in the schema, not the handler.** The `WHERE status != 'released'` partial
  unique index is the real guarantee against a double-claim race; the app's "already claimed?" check is a nice
  409 message, but the index is what actually holds under concurrency.
- **Reveal only after the claim row exists.** Return `fullContact` in the same response that records the claim
  — never in the browse list. The masked teaser is deliberately un-actionable (initial only).
- **Re-verify coverage on the claim.** A buyer can POST any `lead_id`; don't trust that it came from their
  browse list. `claim` recomputes coverage + all gates before touching anything (`:191-206`).
- **A claim records OWED; it does not charge.** Money movement is a separate, explicit path
  (`prepaid-wallet-ledger`). Keeping "owe" and "charge" separate is what lets legal/finance reconcile later.
- **Fail closed on the session secret.** An unset `SESSION_SECRET` yields *no* valid session — never sign with
  a dev fallback key (`:44`, `:49`).
- **Use a distinct cookie name per portal** (`cp_atty` vs staff `cp_sess` vs ambassador `cp_amb`) so sessions
  for different roles on the same origin never collide.
