---
name: cf-abuse-guard
description: >-
  Pure Cloudflare Worker + D1 abuse defense with NO KV, Durable Object, Redis, or external rate-limit
  binding: a failed-login ledger giving simultaneous per-IP AND per-account lockout that is checked BEFORE
  the password is ever touched (so it also throttles unknown/guessed emails and can't be used to enumerate
  accounts), a generic fixed-window rate limiter for register / signup / public form-capture endpoints, and
  a cron reaper that trims both ledgers so they never grow without bound. EXTENDS cf-identity (hardens its
  login + register routes). Use WHENEVER a build has a login, a signup, a password-reset, or any public
  POST that an anonymous script could hammer — "rate limit the login", "stop brute force / credential
  stuffing", "lock out after N failures", "throttle signups", "protect the public form", "someone's
  hammering the API", "prevent account enumeration". Guardrails: the lockout gate runs before the password
  compare and returns the SAME generic message for locked/unknown/wrong so it leaks nothing; a successful
  login clears the account's failures; fail-open (never block a real user because the ledger write errored).
---

# cf-abuse-guard — brute-force + flood defense on plain D1

## What it is / when to use
Two D1-backed defenses that need no extra Cloudflare product:
1. **Login lockout** — a `login_failures` ledger (one row per failed attempt, tagged `ip:<addr>` or
   `email:<addr>`) giving *simultaneous* per-IP and per-account limits within a rolling window.
2. **Generic fixed-window rate limiter** — a `rate_counters` table (`INSERT … ON CONFLICT DO UPDATE`) for any
   keyed endpoint: register, signup, forgot-password, public lead/contact capture.

Plus a `scheduled()` cron reaper so neither table grows forever. Use it in every build with a login or a
public form.

**Extends `cf-identity`.** It wires directly into cf-identity's `handleLogin` / `handleRegister`. Build
cf-identity first; this hardens it.

## Reference implementation (lift the proven code)
All paths under `~/Projects/clients/wavelygth/`:
- **Helpers:** `worker/index.js` **L145–197**
  - `clientIp(req)` — `cf-connecting-ip` → `x-forwarded-for` → `'unknown'` — L153–155
  - Tunable constants `LOGIN_WINDOW_SEC` / `LOGIN_MAX_IP` / `LOGIN_MAX_ACCOUNT` — L157–159
  - `loginLockState(env, ip, email)` — read-only; one query SUM-CASEs both scopes; locked if either over budget — L163–175
  - `recordLoginFailure(env, ip, email)` — a `env.DB.batch([...])` inserting both an ip: and an email: row — L176–181
  - `clearLoginFailures(env, email)` — delete the account's rows on success — L182–184
  - `rateLimit(env, key, limit, windowSec)` — fixed window; returns true when ALLOWED — L188–197
- **Login wiring:** `worker/index.js` **L289–328** — lock gate BEFORE the password (L292–296), record on wrong
  password (L302), record on a wrong MFA code too (L320), clear on success (L326).
- **Rate-limit call sites:** register L261, signup L963, forgot L501, public capture L2115.
- **Cron reaper:** `reapRateLimits(env)` L3055–3064, invoked from `scheduled()` L3292–3301 via
  `ctx.waitUntil(...)`; `wrangler.jsonc` cron triggers L73–76.
- **Migration:** `worker/migrations/0005_hardening.sql` — `login_failures` (+ `ix_login_failures_scope`) and
  `rate_counters` (composite PK `(rkey, window_start)`).

## How to reapply it
1. **Migration.** Copy the `login_failures` table (`id`, `scope` TEXT, `ts` INTEGER seconds) with an index on
   `(scope, ts)`, and `rate_counters` (`rkey`, `window_start`, `hits`, PRIMARY KEY `(rkey, window_start)`).
2. **Helpers.** Copy `clientIp`, `loginLockState`, `recordLoginFailure`, `clearLoginFailures`, `rateLimit`
   and the three tunable constants. They depend only on `env.DB` and a `now()` returning unix seconds.
3. **Wire the login.** In `handleLogin`, FIRST resolve `ip = clientIp(req)`, then
   `const lock = await loginLockState(env, ip, email); if (lock.locked) return 429` with a `retry-after`
   header — *before* looking the user up or hashing. On a wrong password (or wrong MFA code) call
   `recordLoginFailure(env, ip, email)`; on success call `clearLoginFailures(env, email)`.
4. **Wire the public endpoints.** At the top of register/signup/forgot/capture:
   `if (!(await rateLimit(env, \`signup:${clientIp(req)}\`, 10, 3600))) return 429;`
5. **Cron reaper.** Add `reapRateLimits(env)` (delete `login_failures` older than the login window,
   `rate_counters` older than a day) and call it from `scheduled()` under `ctx.waitUntil(...)`. Add a cron
   trigger in `wrangler.jsonc`.

## Gotchas (from the code + comments)
- **Check the lockout BEFORE the password.** Doing it first means an attacker gets the same "too many
  attempts" whether the email exists or not — the per-IP scope throttles email guessing and prevents
  enumeration. Checking after a user lookup would leak existence via timing/branching.
- **Per-IP AND per-account, together.** One query returns both counts (`LOGIN_MAX_IP` ~20, `LOGIN_MAX_ACCOUNT`
  ~8). Per-account alone lets a botnet spread across IPs; per-IP alone punishes a shared NAT. Keep both.
- **A wrong MFA code counts as a failure too** (see totp-mfa) — otherwise 2FA is a free brute-force oracle.
- **Fail-open on ledger errors.** `recordLoginFailure` / `rateLimit` swallow DB errors (`.catch(console.error)`)
  so a transient D1 hiccup never bricks real logins. Security posture: degrade to *not blocking*, never to a
  500 on the auth path.
- **`rateLimit` returns true = ALLOWED.** Easy to invert. It increments first, then reads, and allows while
  `hits <= limit`.
- **The reaper is mandatory.** Without the cron these tables grow unbounded on a busy or attacked site.
  `login_failures` is trimmed to the lockout window; `rate_counters` to ~a day.
- **`clientIp` trusts Cloudflare's header.** `cf-connecting-ip` is set by the edge and safe; only fall back to
  `x-forwarded-for` when not fronted by CF. Don't trust a raw client-set `x-forwarded-for` as the primary.
