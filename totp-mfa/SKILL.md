---
name: totp-mfa
description: >-
  Self-contained authenticator-app 2FA (RFC 6238 TOTP) for a Cloudflare Worker + D1 app, on Web Crypto ONLY
  with zero npm deps: a single dependency-free library (base32 encode/decode, HOTP, TOTP, otpauth:// URL,
  and a constant-time verify with a ±1 step window) plus the enroll → confirm → login-gate → disable flow —
  where a wrong OR absent code at login counts as a failed attempt toward account lockout so MFA can't be
  brute-forced, and disabling MFA also requires a current code. EXTENDS cf-identity (adds a second factor to
  its login) and pairs with cf-abuse-guard (a bad code feeds the same lockout ledger). Use WHENEVER a build
  needs "two-factor", "2FA", "MFA", "authenticator app", "TOTP", "Google Authenticator / Authy support",
  "one-time code", "step-up auth", "protect the admin account", or "require a code at login". The library
  file (`totp.mjs`) lifts UNCHANGED into any Worker or Node ≥20 project. Guardrails: enrollment is a
  two-step commit (secret stored but INACTIVE until one correct code confirms it) so a mis-scanned QR can't
  lock the user out; a wrong/absent code at login is a lockout-counted failure, never a free retry oracle;
  the compare is constant-time; store the base32 secret server-side and never return it after enrollment.
---

# totp-mfa — authenticator-app 2FA with no dependencies

## What it is / when to use
Adds a real second factor (the 6-digit code from Google Authenticator / Authy / 1Password / any RFC-6238 app)
to a cf-identity login, using nothing but Web Crypto — no `otplib`, no `speakeasy`, no npm. Ships as one small
library file you can drop into any Worker or Node project, plus the four-endpoint flow (setup, enable,
disable, and the login-time gate). Reach for it whenever an account is worth protecting past a password —
especially the admin/owner account.

**Extends `cf-identity`.** It hooks into cf-identity's `handleLogin` (the code is required in the SAME login
request once enabled) and adds two columns to its `users` table. Pairs with `cf-abuse-guard`: a wrong code is
recorded as a login failure, so the lockout ledger also throttles code-guessing. Build cf-identity first.

## Reference implementation (lift the proven code)
All paths under `~/Projects/clients/wavelygth/`:
- **The library (lift the whole file unchanged):** `worker/lib/totp.mjs` — `base32Encode`/`base32Decode`
  (RFC 4648, tolerant decode), `counterToBytes` (8-byte BE, safe past 2^32), `hmacSha1` via
  `crypto.subtle`, `hotp` (RFC 4226 dynamic truncation), and the public API: `generateSecret(bytes=20)`,
  `otpauthUrl(secret,{label,issuer})`, `currentCode(secret,{t,step,digits})`,
  `verifyTotp(secret,code,{t,step,digits,window=1})` (loops the window, `timingSafeEqualStr`, no early break).
- **Server flow:** `worker/index.js`
  - `handleMfaSetup(env, me)` — generates a secret, stores it with `mfa_enabled=0`, returns the base32 secret
    + an `otpauth://` URL (for a QR) — **L342–348**
  - `handleMfaEnable(req, env, me)` — requires ONE correct code to flip `mfa_enabled=1` — **L349–358**
  - `handleMfaDisable(req, env, me)` — requires a current code to clear the secret + flag — **L359–368**
  - **Login-time gate:** **L312–324** inside `handleLogin` — only after the password succeeds; a missing code
    returns `{mfa_required:true} 401`; a wrong code ALSO calls `recordLoginFailure(...)` (lockout) before the
    401.
  - Import + `publicUser` exposing `mfa_enabled`: L36, L136.
  - Routes: L3117–3119 (`/api/mfa/setup|enable|disable`).
- **Migration:** `worker/migrations/0005_hardening.sql` — `ALTER TABLE users ADD COLUMN mfa_secret TEXT` and
  `ADD COLUMN mfa_enabled INTEGER NOT NULL DEFAULT 0`.
- **UI:** `portal/index.html` — setup card (paste-the-key + confirm-code, disable-with-code) L629–641; the JS
  (`renderMfa`, start/enable/disable) L1850–1883; the login card reveals a code field on a
  `{mfa_required:true}` 401 and re-submits (L764–775).
- **Proof:** `worker/lib/_proof/totp.test.mjs` — asserts `currentCode` matches the RFC 6238 Appendix-B SHA-1
  reference vectors (8-digit and 6-digit), verify accepts/rejects, the ±1 window accepts the previous step,
  `generateSecret` shape, and the exact `otpauthUrl` format. Run: `node --test worker/lib/_proof/totp.test.mjs`.

## How to reapply it
1. **Drop in the library.** Copy `worker/lib/totp.mjs` verbatim. It needs only Web Crypto globals — works in a
   Worker and in Node ≥20 unchanged.
2. **Migration.** Add `mfa_secret TEXT` and `mfa_enabled INTEGER NOT NULL DEFAULT 0` to your users table.
3. **Enroll (two-step).** `POST /mfa/setup`: `const secret = generateSecret();` store it with
   `mfa_enabled=0`; return the secret + `otpauthUrl(secret,{label: user.email, issuer:'<Your App>'})` so the
   UI can show a QR and/or the key. `POST /mfa/enable`: verify ONE `verifyTotp(secret, code, {window:1})`
   before setting `mfa_enabled=1` — this proves the authenticator is correctly synced before you start
   requiring it.
4. **Login gate.** In your login handler, AFTER the password check passes and account-state checks:
   `if (u.mfa_enabled) { const code = body.code; if (!code) return {mfa_required:true} 401;
   if (!(await verifyTotp(u.mfa_secret, code, {window:1}))) { await recordLoginFailure(env, ip, email);
   return {mfa_required:true, error:'…'} 401; } }` then issue the session.
5. **Disable.** `POST /mfa/disable`: require a current code, then null the secret + clear the flag.
6. **UI.** Reveal a one-time-code input on a `{mfa_required:true}` response and resubmit the login with `code`;
   an enrollment card that shows the secret/QR and confirms a code; a disable control that asks for a code.

## Gotchas (from the code + proof)
- **Enrollment is a commit, not a flip.** The secret is stored with `mfa_enabled=0` at setup and only turns on
  after `enable` verifies a live code. If you set the flag at setup time, a user who mis-scans the QR is
  instantly locked out of their own account with no valid code.
- **A wrong/absent code at login MUST count toward lockout.** The gate calls `recordLoginFailure` on a bad
  code. Skip that and the 6-digit space becomes a free brute-force oracle behind a known-good password.
- **Constant-time compare + no early break.** `verifyTotp` runs the full window and uses `timingSafeEqualStr`;
  don't "optimize" it to `return true` on first match or a `===` compare — that reintroduces a timing side
  channel.
- **`window:1` is the right default** — it accepts the code from the adjacent 30s step to tolerate clock skew
  and a user typing as the code rolls. `window:0` will reject valid codes near the boundary; larger windows
  widen the guess surface.
- **HMAC is SHA-1 by RFC 6238** — that's correct for TOTP interop (every authenticator app expects it), NOT a
  security weakness here. The `otpauth://` URL hard-codes `algorithm=SHA1&digits=6&period=30`; keep them in
  sync with the verify defaults or apps will show non-matching codes.
- **Never return the secret after enrollment.** `handleMfaSetup` returns it once so it can be scanned; no other
  endpoint should echo `mfa_secret`. `publicUser` exposes only the boolean `mfa_enabled`.
- **`counterToBytes` uses division, not `>>>`** — bit-shifting the counter would corrupt the high 32 bits and
  break codes far in the future; keep the `Math.floor(n/256)` form.
