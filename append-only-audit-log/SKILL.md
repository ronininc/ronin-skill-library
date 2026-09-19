---
name: append-only-audit-log
description: >-
  One failure-tolerant `audit(env, userId, action, detail)` helper that writes an
  immutable audit_log row (id, ts, user_id, action, detail), wrapped in a
  try/catch that only console.errors so a logging failure can NEVER break the
  request it records — then called after every privileged action across the app
  (login, logout, lockout, invite, accept-invite, password change/reset, MFA
  enable/disable, role/clearance change, signup approval/rejection, token
  mint/revoke, settings change, connector connect/disconnect, record
  create/update). The result is a single immutable compliance trail on plain D1,
  no external logging service. Use WHENEVER a build needs "an audit trail",
  "activity log", "who did what and when", "compliance log", "log every
  privileged action", "immutable record of changes", "security event log", or
  "track admin actions". Backend on a Cloudflare Worker + D1. EXTENDS cf-identity
  (logs its auth events) and pairs with feature-activation-gate (log every flip),
  google-oauth-connector (log connect/disconnect), and any admin mutation.
  Guardrails: the write is fire-and-forget-safe (awaited for ordering, but its
  error is swallowed) so auditing never fails a request; append-only by
  DISCIPLINE — never add an UPDATE/DELETE route to audit_log; detail is bounded
  (~500 chars) and must NEVER contain secrets/passwords/tokens (mask them);
  user_id is a plain nullable TEXT column (not a FK) so a deleted user still
  leaves a trail; use 'system' for cron/webhook actors and null for pre-identity
  events (a failed login of an unknown email); log FAILURES too, not just successes.
---
# append-only-audit-log — one helper, wired everywhere

## What it is / when to use
A single tiny helper that appends an immutable row to an `audit_log` table for
every privileged action, and the discipline of calling it consistently. It gives
any Cloudflare Worker + D1 app a compliance/security trail with no third-party
logging service and no way for a log write to take down a real request. Use it on
any build with auth, admin actions, money-adjacent operations, or a regulatory
need to answer "who did what, when."

## Reference implementation (Wavelygth — patterns only, no client data)
- `~/Projects/clients/wavelygth/worker/index.js`
  - **L138–143** the `audit()` helper (the whole thing).
  - **L58–60** the id/time helpers it uses (`uid = crypto.randomUUID()`, `iso = new Date().toISOString()`).
  - Call sites across auth + admin (illustrating the conventions): **L280** `bootstrap_admin`, **L294** `login_locked`, **L303** `login_failed`, **L321** `login_mfa_failed`, **L327** `login`, **L356/366** `mfa_enabled`/`mfa_disabled`, **L410** `password_changed`, **L491** `invite_accepted`, **L510** `password_reset_requested`, **L530** `password_reset`, **L800/833** `agent_created`/`agent_activated`|`agent_suspended`, **L894–912** `clearance_created`/`clearance_updated`/`clearance_deleted`, **L977–1000** `signup_pending`/`signup_approved`/`signup_rejected`, **L1311/1321** `google_connected`/`google_disconnect`, **L2653/2661** `companion_token_revoked`/`companion_token_minted`, **L2704** `email_config_set` (masked).
- `~/Projects/clients/wavelygth/worker/migrations/0001_init.sql` **L75–81** — the `audit_log` table (note `user_id TEXT` is a plain nullable column, NOT a foreign key).

## How to reapply it
**1. Schema** — append-only by shape; `user_id` deliberately not a FK:
```sql
CREATE TABLE audit_log (
  id      TEXT PRIMARY KEY,
  ts      TEXT NOT NULL,
  user_id TEXT,            -- nullable, NOT REFERENCES users(id): a deleted actor still leaves a trail
  action  TEXT NOT NULL,   -- snake_case verb_noun
  detail  TEXT             -- short human string, NEVER a secret
);
```

**2. The helper** — next to `currentUser`; wrapped so it can never break a request:
```js
async function audit(env, userId, action, detail) {
  try {
    await env.DB.prepare('INSERT INTO audit_log (id, ts, user_id, action, detail) VALUES (?,?,?,?,?)')
      .bind(uid(), iso(), userId || null, action, detail ? String(detail).slice(0, 500) : null).run();
  } catch (e) { console.error('audit failed', String(e)); }   // swallow — auditing never fails the caller
}
```

**3. Call it after every privileged action:**
```js
await audit(env, me.id, 'position_created', `${label} → ${pf.id}`);   // actor = the admin
await audit(env, row.id, 'invite_accepted', null);                    // actor = the affected user (self-serve)
await audit(env, 'system', 'google_connected', email);               // automated / callback actor
await audit(env, null, 'login_locked', email);                       // pre-identity: unknown/anonymous
await audit(env, u.id, 'login_failed', email);                       // log FAILURES, not just successes
await audit(env, me.id, 'email_config_set', maskFrom(from));         // mask anything sensitive in detail
```

**4. Read it back** in an admin view (`SELECT … FROM audit_log ORDER BY ts DESC LIMIT n`) —
read-only. Never expose an edit or delete endpoint for this table.

## Conventions (from the call sites)
- **`action` = `snake_case` `verb_noun`**: `login`, `login_failed`, `login_locked`,
  `password_reset`, `mfa_enabled`, `clearance_created`, `signup_approved`,
  `google_connected`, `companion_token_minted`, `position_updated`, `settings_updated`.
  Stable strings you can filter/aggregate on later.
- **`userId` = the ACTOR.** The admin who did it (`me.id`); the affected user for
  self-serve events (`invite_accepted` → the new user's id); the string `'system'`
  for cron/webhook-driven actions; `null` for pre-identity events (a failed login
  of an email that may not exist — you can't and shouldn't resolve a user there).
- **`detail` = a short, safe human string.** Enough to reconstruct what happened
  (`${leadId}=${outcome}`, `${sent}/${total} via ${trigger}`), never a secret. Mask
  emails/phones/keys (`maskFrom(email)`, `'…' + phone.slice(-4)`). The helper hard-caps it at 500 chars.
- **Log both sides of a toggle** (`agent_activated`/`agent_suspended`,
  `signup_approved`/`signup_rejected`) and **log failures** (`login_failed`,
  `login_mfa_failed`, `login_locked`) — the failures are the security signal.

## Gotchas
- **Auditing must never break the request.** The whole body is a try/catch that
  only `console.error`s. It's `await`ed so ordering is deterministic, but a D1 hiccup
  on the log write can't 500 the operation being logged.
- **Append-only is a DISCIPLINE, not a constraint.** There is no `UPDATE`/`DELETE`
  path to `audit_log` in the app — don't add one. For true immutability, never grant
  the Worker a delete route on this table (and don't let it get swept by a "reset/backup"
  wipe unless that wipe is itself audited/out-of-band).
- **Place the call AFTER the successful mutation** so you never log an action that
  then failed — EXCEPT attempt-logging (failed/locked login), where recording the
  attempt is the entire point, so those fire on the failure path.
- **`user_id` is a plain nullable TEXT column, not `REFERENCES users(id)`.** The
  referenced user may later be deleted and you still want the historical trail; a FK
  would also risk blocking/cascading a user deletion.
- **`detail` is bounded** (`slice(0,500)`) so a large payload can't bloat a row — and
  it's the field most likely to accidentally carry a secret; keep it a short summary.
- **`ts` is an ISO string** here (human-sortable in the admin view); if you prefer
  epoch for range queries, be consistent with the rest of your schema.
