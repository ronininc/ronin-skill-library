---
name: send-once-idempotent-email
description: >-
  An AT-MOST-ONCE transactional-email outbox for a Cloudflare Worker + D1 build: send exactly one
  message per (kind, ref) even when a webhook and a poll both fire for the same event and race. The
  trick is CLAIM-BEFORE-SEND — a single `INSERT … ON CONFLICT(kind,ref) DO UPDATE SET 'pending' WHERE
  status='error'` serialized by the unique index, so exactly one caller comes away with changes≥1 and
  is allowed to send; everyone else sees changes=0 and skips. It FAILS CLOSED (if the claim write
  throws, it does NOT send — better a missed mail than a double), and it models delivery CERTAINTY
  honestly with a three-state finalize: `sent` (provider accepted, terminal), `error` (known
  pre-acceptance failure, re-claimable/retryable), and `uncertain` (the provider call threw AFTER it
  may have already accepted — TERMINAL, never auto-resent, surfaced for operator reconciliation). Runs
  over Cloudflare's NATIVE `send_email` binding (`env.EMAIL.send`, no third-party provider) but the
  dedup wraps any send fn. Use WHENEVER a build emails on an event that can replay — "don't double-send
  the receipt", "idempotent email", "send once per invoice/order", "webhook + cron both email",
  "exactly-once email (honestly at-most-once)", "email outbox with a send log", or "reconcile stuck
  sends". It COMPLEMENTS email-provider-honest-degrade (that is the PROVIDER-resolution seam that skips
  cleanly when unconfigured — THIS is the idempotency/dedup + delivery-state ledger layered on top; use
  both) and append-only-audit-log. Guardrail: `uncertain` is terminal by design — auto-resending an
  ambiguous acceptance is how you double-deliver; only `error` rows re-claim.
---
# send-once-idempotent-email — claim-before-send, at-most-once, honest delivery state

## What it is / when to use
The dedup + delivery-state layer that makes event-driven email safe to fire from more than one path.
Any time a receipt/alert can be triggered by both a webhook and a poll (or a retry), reach for this so
the customer gets exactly one. It is not a provider — pair it with email-provider-honest-degrade (or a
native binding) for the actual send; this owns "have we already sent this, and did it land."

## Reference implementation (patterns only, no client data)
All in `worker/lib/email.js`:
- `sendEmail(env, msg)` L43–67 — the low-level send over the **native `env.EMAIL.send`** Cloudflare
  binding; never throws; returns `{ok}` / `{ok:false, skipped, retryable}` / `{ok:false, uncertain}`
  (a throw AFTER possible acceptance ≠ rejection).
- `sendOnce(env, db, {kind, ref, to, subject, html, text})` L87–136 — the core: the claim `INSERT …
  ON CONFLICT DO UPDATE … WHERE email_log.status='error'` L94–100 (only `error` rows re-claim);
  changes≥1 gate L105–108; three-state finalize L121–128 (`sent`/`uncertain`/`error`); fail-closed on
  a claim-write throw L101–104; degrades to a plain send when no ledger (db/kind/ref) is present.
- Two-lane cost model — `emailFrom`/`storeInbox`/`customerEmailEnabled`/`emailAvailable` L23–32:
  a FREE "store alert" lane to a verified destination address vs a PAID "customer" lane (arbitrary
  recipient, needs an onboarded sending domain), gated by an `EMAIL_CUSTOMER='1'` var.
- `notifyStore` L139–143 and `emailInvoiceIfEnabled` L197–205 — the two lanes calling `sendOnce`.
- **Schema:** `worker/migrations/0016_email_log.sql` — `email_log(kind, ref, recipient, subject,
  status, error, created_at, sent_at)` with `CREATE UNIQUE INDEX ux_email_log_kind_ref ON
  email_log(kind, ref)` (the index that serializes the claim). Status lifecycle documented in the file.
- Proof: `worker/lib/_proof/send-once.test.mjs`.

## How to reapply
1. Migration: the `email_log` table + the `(kind, ref)` UNIQUE index above.
2. Pick a stable `ref` per event class (`kind='invoice'`, `ref=invoice_number`; `kind='online_paid'`,
   `ref=order_id`; …) so replays collapse to one row.
3. Call `sendOnce` from every path that could fire the same event (webhook AND poll), from
   `ctx.waitUntil()` in a background path — the ledger makes concurrency safe.
4. Admin surface: list `email_log` where `status IN ('pending','uncertain')` — that's your reconcile queue.

## Gotchas (from the code)
- `uncertain` and `sent` can NEVER be re-claimed (the `WHERE status='error'` guard) — that is what makes
  an ambiguous acceptance deliver at most once.
- Residual crash window (honest, not exactly-once): if the provider accepts but the finalize write is
  lost, the row stays `pending` and is never retried — it becomes a reconciliation item, not a resend.
- No ledger context ⇒ it silently degrades to a plain (un-deduped) send; always pass db+kind+ref for
  anything replayable.
