---
name: last-usable-owner-guard
description: >-
  A DATABASE-LEVEL invariant that makes a multi-seat Cloudflare Worker + D1 app impossible to lock
  yourself out of: there is ALWAYS at least one account that can BOTH administer AND sign in. Two SQLite
  BEFORE UPDATE / BEFORE DELETE triggers re-check "count of usable owners" (role owner/admin AND active
  AND approved) with CURRENT row state INSIDE the write transaction and `RAISE(ABORT)` if the statement
  would take the last one out of that set; the app catches the abort and returns a clean "hand ownership
  off first" message instead of silently bricking. This closes a TOCTOU race that application guards
  structurally cannot: an app that reads "is this the last owner?" then writes can be raced by a
  concurrent demote/deactivate/reject/transfer and strand the portal with zero usable admins. Use
  WHENEVER an app has admin roles that can be demoted, deactivated, deleted, rejected, or transferred —
  "don't let the last admin be removed", "can't lock yourself out", "always keep one owner", "protect
  the last owner", "who can demote the owner", or productizing a self-serve team/RBAC portal. It
  COMPLEMENTS clearance-rbac (whose "owner-always-all" governs permission GRANTS — this governs roster
  INTEGRITY, that a usable owner always EXISTS) and cf-identity (its login already requires
  active+approved — this guard uses the exact same predicate). Guardrail: the DB trigger is the real
  enforcement; the app-level guards + abort-catch are the friendly UX on top, never the sole line.
---
# Last Usable Owner Guard

## What it is / when to use / what it composes with
A "you can never brick your own app" safety invariant enforced in the database. It is the roster-integrity
counterpart to **clearance-rbac**'s permission model (that skill guarantees the owner HOLDS every
permission; this guarantees a usable owner still EXISTS after any write), and it reuses **cf-identity**'s
login predicate (a session is valid only for an `active` + `approved` owner/admin — so "usable" is
defined the same way).

## Reference implementation — exact source
- **DB triggers:** `worker/migrations/0013_keep_one_usable_owner.sql` — `trg_keep_one_usable_owner_update`
  (BEFORE UPDATE) and `trg_keep_one_usable_owner_delete` (BEFORE DELETE) on `users`.
- **App side** (`worker/index.js`): `isLastOwnerAbort` (`:1206`), caught in `handleAccept` (`:635`),
  `rejectUser` (`:807`), `setRole` (`:1273`), `transferOwnership` (`:1346`), `setActive` (`:1480`);
  `ownerCount` (`:1209`) is the optimistic pre-check.

## How to reapply
- **Define "usable owner" once** = `role IN ('owner','admin') AND active = 1 AND approval = 'approved'`
  (whatever your session-validation requires). Use the IDENTICAL predicate in the triggers and in login.
- **UPDATE trigger:** fire only when the row WAS usable and the NEW values make it NOT usable, AND the
  current usable count is `<= 1`; then `SELECT RAISE(ABORT, 'last_usable_owner')`. This covers demotion,
  deactivation, and un-approval in one rule. Editing an owner's name/password keeps them usable, so it
  never fires on benign edits.
- **DELETE trigger:** fire when the row being deleted is usable and the count is `<= 1`.
- **App-level UX:** wrap each ownership-affecting mutation in try/catch; `isLastOwnerAbort(e)` =
  `/last_usable_owner/.test(e.message)`; return a 409 with "hand ownership off first" (or, on
  accept-invite, treat it as idempotent success). Keep `ownerCount` as a friendly early check, but do
  NOT rely on it — the trigger is the real guard.
- **Transfer safely:** promote the incoming owner BEFORE stepping the outgoing one down, so at the
  step-down there are momentarily two usable owners and the trigger stays silent (`transferOwnership`).
- **Migration note:** D1 rejects a non-constant column default, so the `approval` column (`0011`) is
  `NOT NULL DEFAULT 'approved'` — every legacy account is usable, nobody is locked out by adding this.

## Gotchas
- **Application guards alone are insufficient** — this is the whole point. A guard reads a row, decides
  "not the last owner," then writes; a concurrent transaction can make it the last owner before the
  write lands. Only a check with CURRENT state inside the write transaction (a trigger) closes it. Don't
  try to close it path-by-path.
- The trigger's subquery counts `users` on every qualifying write — negligible at team scale, but it is
  a per-row BEFORE trigger, so keep the predicate cheap and indexed (`0011` indexes `approval`).
- Match the trigger predicate to login EXACTLY. If login also required, say, `email_verified`, the guard
  must too — otherwise you can strand the app with an owner who satisfies the trigger but can't sign in.
- This protects the OWNER tier's existence; it is not a general RBAC layer — compose clearance-rbac for
  who-can-do-what.
