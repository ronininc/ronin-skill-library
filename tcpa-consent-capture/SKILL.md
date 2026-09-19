---
name: tcpa-consent-capture
description: >-
  The INBOUND consent-proof capture kernel for any US lead/inquiry form that will later be called,
  texted, or sold: no consent -> 422 and NOTHING is stored; the lead row and its consent proof commit
  ATOMICALLY (a lead can never exist without consent, nor consent without a lead); the consent record
  captures the exact displayed language + a version tag + IP + user-agent + source_url; the phone is
  DNC-scrubbed BEFORE any write; and an "already represented / conflicted" flag disqualifies the lead so
  it is stored but never routed. Use WHENEVER a build captures a consented contact that will be contacted
  or resold — "TCPA consent on the form", "store consent proof", "prove they opted in", "consent-or-nothing
  capture", "DNC scrub on intake", "one-to-one consent", "TrustedForm/Jornaya cert", or any personal-injury
  / insurance / mortgage / debt lead form. This is the CAPTURE (inbound) side and COMPLEMENTS
  outbound-compliance-gate (which owns the SEND-side consent/DNC/hours predicate — do not duplicate it),
  append-only-audit-log (the trail every state change appends to), and cf-forms (the public form). It is the
  consent basis that lead-marketplace-auto-match and predictive-dialer-pacing both read before they act.
---
# TCPA Consent Capture (inbound consent-proof kernel)

## What it is / when to use / what it composes with
The server-side gate that makes a captured lead legally defensible the moment it lands, enforced in **code +
schema, not policy**. Every US product that calls/texts/sells a lead needs a *provable* record that the
person consented, in the exact words shown, at a real IP/time — this is that record and the gates around it.

- **Composes with** `outbound-compliance-gate` (send-side predicate — this is the capture-side that fills the
  `consents`/`dnc` tables it later reads), `append-only-audit-log` (writes a row on created/qualified/
  disqualified), `cf-forms` (the public POST), and `idempotent-public-submission` (the key claimed before
  these writes). It is the precondition for `lead-marketplace-auto-match` and `predictive-dialer-pacing`.
- **Use it** on any consent-gated intake: PI/accident, insurance, mortgage, debt-relief, home-services leads.

## Reference implementation (exact source)
- Gate + atomic commit: `/Users/robbiebrown/Projects/case-plug/src/index.js:93-160` (`handleIntake`).
  - Consent gate (no consent -> 422, nothing stored): `index.js:109-110`.
  - DNC scrub before any write: `index.js:111-115`.
  - Matching-key sanitization (state/case_type constrained to safe values so no `%` wildcard match): `index.js:105-108`.
  - **Atomic** lead + consent proof via `env.DB.batch([leadStmt, consentStmt])` with the consent bound to
    `last_insert_rowid()`: `index.js:135-149`.
  - Conflict disqualification (already-represented -> stored but `stage='disqualified'`, never matched): `index.js:152-157`.
- Schema: `consents` (with `consent_text`, `consent_version`, `ip`, `user_agent`, `source_url`) `schema.sql:84-96`;
  `dnc` `schema.sql:110-115`; `leads.already_represented` + stage CHECK `schema.sql:69-74`.
- Certified-consent seam (TrustedForm/Jornaya): `consent_certs` table `schema.sql:249-253`; the dialer accepts
  an intake consent **OR** a `status='claimed'` cert as the consent basis `dialer.js:48-52`.

## How to reapply
1. **Schema** — three tables. `consents(lead_id, consented, consent_text, consent_version, ip, user_agent,
   source_url, created_at)` indexed on `lead_id`; `dnc(phone PRIMARY KEY, reason, created_at)`;
   optional `consent_certs(lead_id, provider, cert_id, status IN ('unclaimed','claimed','failed'))`. Put a
   `CONSENT_VERSION` constant in code and bump it when the displayed language changes.
2. **Handler order (do not reorder)** — parse/limit body → honeypot drop → validate contact + required keys →
   **sanitize matching keys** → **consent gate (422 if absent, before ANY write)** → **DNC scrub (403)** →
   claim idempotency key → `batch([insert lead, insert consent bound to last_insert_rowid()])` → audit →
   conflict check (`already_represented` → set `disqualified`, audit, return) → mark `qualified`.
3. **Capture the proof from the request**, not the body alone: `ip` from `cf-connecting-ip`, `user_agent`
   from the header, plus the client-sent `consent_text`/`consent_version`/`source_url`.
4. **UI**: the form sends `consent:true` + the literal checkbox text as `consent_text`. Keep the displayed
   language and the stored `consent_version` in lockstep.

## Gotchas (from the code)
- **Consent gate must precede every write.** If you insert the lead first "and clean up later", a crash
  leaves a stored-but-unconsented lead — exactly the record you can't defend. The batch is the whole point.
- **Never dedupe a repeat caller by phone/email.** A real person can be in an accident twice; idempotency is
  by submission key only (see `idempotent-public-submission`).
- **Sanitize state/case_type before they touch a LIKE/IN.** `index.js:105-108` strips to `[A-Z]{2}` / `[a-z_]`
  so a crafted `case_type:"%"` can't wildcard-match (and bill) a partner downstream.
- **Disqualified ≠ deleted.** A represented/conflicted lead is stored (you may owe a source ROI record) but
  its `stage='disqualified'` must exclude it from every match/dial query — enforce that in the WHERE, not by trust.
- **A cert is only a consent basis once CLAIMED.** Never dial on an `unclaimed` `consent_certs` row.
- **Public responses never leak internal error detail** (`index.js:336-340`) — a 500 is `{error:"server_error"}`.
