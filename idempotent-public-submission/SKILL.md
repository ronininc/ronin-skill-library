---
name: idempotent-public-submission
description: >-
  Durable idempotency for UNAUTHENTICATED public form POSTs that drive a side effect (create a lead, fire a
  charge, send a match) — so a dropped connection, a double-tap, or a retry can never create a duplicate record
  or a double-charge. A client-supplied `idempotency_key` is CLAIMED before any write via `INSERT OR IGNORE`
  into a submissions ledger: the first caller (changes === 1) OWNS the write; a replay or concurrent retry
  reads back and returns the ORIGINAL stored JSON receipt (or a safe "still processing" ack if the first call
  hasn't finalized) — one submit = one lead = one consent = at most one charge. Crucially it NEVER dedupes by
  phone/email, so a genuine repeat submitter can always come back. Use WHENEVER a public endpoint that isn't a
  signed webhook performs a non-idempotent action — "make the intake form idempotent", "stop double
  submissions", "the form double-charged / created two leads", "retry-safe POST", "return the same receipt on
  replay", "idempotency key for the public API". It COMPLEMENTS cf-forms (the public form + honeypot it guards)
  and signed-webhook-intake (which gives idempotency to SIGNED provider webhooks — this is the public-browser-form,
  client-key, receipt-REPLAY variant), and it is the claim that wraps tcpa-consent-capture + lead-marketplace-auto-match
  so the whole capture→match→charge chain runs at most once per key.
---
# Idempotent Public Submission (claim-before-write + receipt replay)

## What it is / when to use / what it composes with
A tiny, durable state machine that makes a public non-idempotent POST safe to retry. The key is claimed
*before* any side effect, and the exact JSON receipt of the first success is stored and replayed — so the
client that retries gets the same answer, not a second lead or a second charge. It's the outer wrapper around
any capture-that-does-something flow.

- **Composes with**: `cf-forms` (the public form + honeypot), `signed-webhook-intake` (the SIGNED-webhook
  idempotency sibling — this is the unauthenticated-form, receipt-replay variant), `tcpa-consent-capture` +
  `lead-marketplace-auto-match` (the capture→match→charge chain it makes exactly-once).

## Reference implementation (exact source)
- Claim + finalize: `/Users/robbiebrown/Projects/case-plug/src/index.js:77-91`.
  - `claimKey` — `INSERT OR IGNORE ... status='processing'`; `meta.changes === 1` ⇒ owner, else read back the
    stored receipt: `index.js:78-85`.
  - `finalize` — on success stamp `status='done'`, `lead_id`, and the exact `response` JSON: `index.js:86-91`.
- Used by intake (claim before any write; replay/in-flight returns the original or a safe ack): `index.js:117-125`
  and every terminal branch returns `finalize(env, key, lead_id, receipt)` (`:156,175,190,203`).
- Used by the ambassador form too (same pattern, different `kind`): `index.js:219-223,232`.
- Schema: `submissions(key PRIMARY KEY, kind, status IN processing|done, lead_id, response /*the exact JSON
  receipt*/, created_at)` — with the explicit "never dedupes by phone/email" note: `schema.sql:98-108`.

## How to reapply
1. **Schema**: `submissions(key TEXT PRIMARY KEY, kind TEXT, status TEXT DEFAULT 'processing', ref_id INTEGER,
   response TEXT, created_at)`. The PRIMARY KEY on `key` is what makes the claim atomic.
2. **Claim first**: `INSERT OR IGNORE INTO submissions (key, kind, status) VALUES (?,?, 'processing')`. If
   `meta.changes === 1` you own the write; otherwise `SELECT response` — return the stored receipt with an
   `idempotent:true` flag, or if it's still `processing` (no response yet) return a safe `{status:'received',
   idempotent:true}` ack. Do this BEFORE any lead insert / charge.
3. **Finalize on every terminal path**: whatever the outcome (matched, unmatched, disqualified), stamp
   `status='done'`, the created id, and the EXACT JSON you returned, so a later replay is byte-identical.
4. **Bound the key** (slice to 64 chars) and treat a missing key as "not idempotent" (still works, just no
   replay protection) rather than rejecting — public clients may not send one.
5. Client sends a durable, self-generated key (e.g. a UUID persisted in the form so a double-tap reuses it).

## Gotchas (from the code)
- **Claim before the work, not after.** If you do the work then record the key, a crash between the two lets a
  retry redo the whole side effect. `INSERT OR IGNORE` is the atomic gate.
- **NEVER dedupe by phone/email** (`schema.sql:100`, `index.js:14-15`). A real person can legitimately submit
  twice (a second accident, a second inquiry); idempotency is per-submission-key ONLY.
- **In-flight replay must not create a second lead.** A concurrent retry that arrives before `finalize` gets a
  safe "received" ack — never a fresh insert. That's why the claim precedes the write and `finalize` fills the
  response later.
- **Store the exact receipt**, not a regenerated one — the replay should return what the first call actually
  returned (same ids, same status), so the client's two attempts are indistinguishable.
- **This is NOT signature verification.** A public form key is client-chosen and unauthenticated — for provider
  webhooks you also need HMAC/timing-safe verification (`signed-webhook-intake`); idempotency alone isn't auth.
