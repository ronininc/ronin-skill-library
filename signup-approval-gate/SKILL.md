---
name: signup-approval-gate
description: >-
  Public self-serve account creation behind a moderation gate for a Cloudflare Worker + D1 app: anyone can
  create an account, but it lands PENDING (active=0, approval_status='pending') and cannot sign in until an
  admin approves it — OR, with an operator "auto-approve" toggle on, it goes straight to active + signed-in.
  Admin approves (→ active + optional "you're approved" email) or rejects (→ inactive + kills any sessions);
  crucially the "your account is awaiting approval" message is revealed ONLY AFTER the correct password, so a
  prober still gets a generic wrong-credentials error and cannot enumerate accounts. EXTENDS cf-identity
  (the users/sessions/login core) and DEPENDS on cf-abuse-guard (signup is rate-limited) + optionally an
  email provider (email-provider-honest-degrade). Use WHENEVER a build needs "let people request an
  account", "signup with admin approval", "waitlist / moderated registration", "approve new members",
  "gate signups", "invite-only but self-serve request", "pending accounts", or a toggle between open and
  moderated signup. Guardrails: signup NEVER creates an admin or a privileged role (always the lowest role);
  pending/rejected state is disclosed only post-password (anti-enumeration); reject also deletes sessions;
  the auto-approve switch is an operator setting, off by default; existing users default to 'approved' so a
  migration onto a live DB locks nobody out.
---

# signup-approval-gate — moderated self-serve accounts

## What it is / when to use
Between "sign-up is closed, invite-only" (cf-identity's default) and "anyone can just sign in" sits the
common real case: **let people request an account, but a human lets them in.** This skill is that gate — a
public signup that parks the account as pending, an admin approve/reject queue, and an operator toggle to flip
the whole thing to instant-on when moderation isn't wanted. Reach for it for waitlists, member portals,
investor/client portals, any "request access" flow.

**Extends `cf-identity`** (users, sessions, login, password hashing) and **depends on `cf-abuse-guard`**
(the signup endpoint is rate-limited). The "you're approved" email uses an honest-degrade email provider
(see `email-provider-honest-degrade`) — with no provider it simply records a skip. Build cf-identity +
cf-abuse-guard first.

## Reference implementation (lift the proven code)
All paths under `~/Projects/clients/wavelygth/`:
- **Signup + approval handlers:** `worker/index.js` **L939–1011**
  - `autoApprove(env)` — reads the `auto_approve` app-setting ('1'/'0') — L944–947
  - `sendApprovedEmail(env, to, name)` — honest-degrade notify — L950–958
  - `handleSignup(req, env, url)` — rate-limited; validates; refuses duplicate email; inserts role=lowest,
    `active = auto ? 1 : 0`, `approval_status = auto ? 'approved' : 'pending'`; auto ⇒ start a session, else
    return `{ pending:true }` — L961–980
  - `handleListApprovals(env)` — the admin queue (pending, lowest-role only) + current toggle — L982–985
  - `handleApprovalDecide(req, env, me)` — approve ⇒ `approved`+`active=1`+email; reject ⇒ `rejected`+
    `active=0`+`DELETE FROM sessions WHERE user_id=?` — L987–1002
  - `handleAutoApprove(req, env, me, method)` — GET reads / POST sets the toggle in `app_settings` — L1004–1011
- **The post-password pending gate:** `worker/index.js` **L307–310** — inside `handleLogin`, AFTER the
  password compare succeeds: `if (u.approval_status === 'pending') return {pending:true} 403;` then
  `if (!u.active) return 403;`. A wrong password on a pending account still returns the generic 401 above.
- **Routes:** `worker/index.js` L3093 (`POST /api/auth/signup`, public), L3197–3199 (admin: list approvals,
  decide, auto-approve).
- **Migration:** `worker/migrations/0016_signup_approval.sql` — `ALTER TABLE users ADD COLUMN
  approval_status TEXT NOT NULL DEFAULT 'approved'` (existing rows default approved) + an index.
- **UI:** `portal/index.html` — signup toggle on the auth card + `POST /api/auth/signup` (L748–750, L799–818,
  shows the pending message on `r.pending`); admin approvals panel with the auto-approve checkbox (L975+).
- **Proof:** `worker/lib/_proof/signup-approval.test.mjs` — pending can't sign in (403), a WRONG password on a
  pending account is a generic 401 (anti-enumeration), admin approve → can sign in, reject → 403 not-active,
  duplicate → 409, short password → 400, auto-approve ON → immediate session. Run: `npm run proof:signup`.

## How to reapply it
1. **Migration.** `ALTER TABLE users ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'approved'` (plus an
   index). The `'approved'` default is what keeps existing accounts working. You'll also rely on an `active`
   column (cf-identity) and an `app_settings` key/value table for the toggle.
2. **Signup handler.** Copy `handleSignup`: rate-limit via cf-abuse-guard, validate name/email/password,
   refuse a duplicate email, read `autoApprove(env)`, insert the user at your LOWEST role with
   `active = auto ? 1 : 0` and `approval_status = auto ? 'approved' : 'pending'`. If auto, start a session;
   else return `{ ok:true, pending:true, message:'...pending approval...' }` with no cookie.
3. **Login gate.** In your login handler, put the pending/active checks AFTER the password compare (see
   Gotchas). Pending ⇒ 403 `{pending:true}`; not-active ⇒ 403.
4. **Admin queue.** Copy `handleListApprovals` (pending + lowest-role only) and `handleApprovalDecide`
   (approve sets `approved`+`active=1` and emails; reject sets `rejected`+`active=0` AND deletes the user's
   sessions). Register both behind the admin gate.
5. **Toggle.** Copy `handleAutoApprove` storing `auto_approve` in `app_settings`.
6. **UI.** Add a "Create an account" mode to the auth card that POSTs to `/api/auth/signup` and shows the
   pending message; add an admin approvals panel with an auto-approve checkbox.

## Gotchas (from the code + proof)
- **Disclose account-state only AFTER the password.** The pending/active branches sit *below* the
  wrong-credentials return. If you check `approval_status` before verifying the password, "awaiting approval"
  leaks that the email is registered — an enumeration oracle. The proof explicitly asserts a wrong password on
  a pending account is a plain 401.
- **Signup never mints privilege.** `handleSignup` hard-codes the lowest role; it can't create an admin or an
  operator seat. Privileged accounts still come by invite (cf-identity). Don't parameterize the role from the
  request body.
- **Reject must kill sessions.** If an auto-approved (or previously active) account is later rejected, delete
  its `sessions` rows or it stays logged in until expiry. The decide handler does this.
- **Migration default is `'approved'`.** Applying this to a live DB must not lock out everyone already in —
  the column default handles that. New signups explicitly set `'pending'`.
- **Auto-approve is an operator setting, off by default**, stored as the string `'1'`/`'0'` and compared
  `=== '1'`. It's the switch between a moderated portal and an open one without a redeploy.
- **List only pending + the signup role.** The approvals queue filters to `approval_status='pending' AND
  role=<lowest>` so admin/operator rows never appear there.
