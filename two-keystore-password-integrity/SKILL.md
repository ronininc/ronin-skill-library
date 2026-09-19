---
name: two-keystore-password-integrity
description: >-
  A tamper-detection hardening for a Cloudflare Worker + D1 login: store each admin/staff password hash
  in TWO independent keystores — D1 (`users.password_hash`) AND Cloudflare KV (`pw:<email>`) — and
  require a login to clear BOTH, so if one store is tampered with (a doctored D1 row, a swapped KV
  value) the two disagree and the login is DENIED rather than silently trusting the altered one. It is
  migration-safe: a missing KV key is HEALED from the verified D1 hash on the next good login (the
  existing DB admin is never locked out), and if KV isn't bound it degrades to db-only (can't enforce
  the second key, but never fabricates a pass). Ships with a co-located companion: stateless SESSION
  INVALIDATION via a KV "epoch" — a password change bumps `epoch:<userId>`, the epoch is baked into the
  signed session token as a 4th segment, and any token minted before the bump is rejected on its next
  request (all prior sessions die on a password change, with no server-side session table to sweep).
  Use WHENEVER an auth build needs "make the password store tamper-evident", "verify against two
  stores", "don't trust a single hash column", "invalidate all sessions when the password changes",
  "log everyone out on reset", or "defense-in-depth on admin credentials". It EXTENDS cf-identity
  (which owns the single-store PBKDF2 hash, HMAC sessions, roles — build that first; this hardens it)
  and pairs with append-only-audit-log (log every password change / mismatch). It is DISTINCT from
  cf-abuse-guard (rate-limit / lockout — that owns throttling; keep it there) and from
  last-usable-owner-guard (roster integrity). Guardrails: PBKDF2 on Workers caps at 100,000 iterations
  (the platform max — do not request more); both stores hold the SAME hash (compare with a timing-safe
  check); a mismatch is a security event, not a silent retry.
---
# two-keystore-password-integrity — a login that must clear D1 AND KV, + epoch session kill

## What it is / when to use
Defense-in-depth for the credential of the one account that matters most: the admin. A single
`password_hash` column is one tampering away from a backdoor; mirroring it into KV and requiring both
to agree turns any single-store edit into a denied login instead of a silent compromise. Reach for it
when hardening an admin/staff surface built on cf-identity, or whenever "verify against two stores" or
"log everyone out on password change" comes up.

## Reference implementation (patterns only, no client data)
All in `worker/lib/auth.js`:
- `verifyTwoKey(env, user, password)` L135–145 — the core: D1 hash must verify FIRST; then the KV hash
  (`pw:<email>`) — absent ⇒ **healed** from D1 (migration-safe), present ⇒ must also clear; returns
  `{ok, mode:'two-key'|'healed'|'db-only'}`; a mismatch ⇒ `{ok:false, reason:'stores out of sync'}`.
- `setUserPassword(env, db, email, pw)` L148–153 — writes the new hash to BOTH stores.
- `syncHashToKV(env, email, hash)` L156–158 — mirror on bootstrap.
- PBKDF2 helpers L14–33 — `hashPassword`/`verifyPassword`, `PBKDF2_ITERS = 100_000` (L9, the Workers
  Web Crypto MAX — requesting more throws), timing-safe compare L35–40.
- **Companion — epoch session invalidation:** `createSession` L46–54 bakes `getEpoch(env,userId)` into
  the signed payload as a 4th segment; `verifySession` L56–72 rejects a token whose epoch ≠ the current
  `epoch:<userId>` (old 3-part tokens → `'0'`); `getEpoch`/`bumpEpoch` L187–192 store it in KV. Bump on
  every password change ⇒ all prior sessions die, no session table to sweep.

## How to reapply
1. Bind KV (e.g. `AUTH_KEYS`) alongside cf-identity's D1 users/sessions.
2. On bootstrap / password set: write the hash to D1 and `syncHashToKV`. On login: `verifyTwoKey`.
3. On any password change/reset: `setUserPassword` (writes both) + `bumpEpoch(env, userId)`.
4. Bake the epoch into the session token (4th segment) and check it in `verifySession`.
5. Audit-log the mode returned + any `stores out of sync` mismatch (append-only-audit-log).

## Gotchas (from the code)
- Do NOT raise PBKDF2 iterations above 100,000 on Workers — it throws; 100k is the platform cap.
- `db-only` mode (KV unbound) is a real, honest fallback — it can't enforce the 2nd key, but it never
  fakes a pass; treat a build that intends the protection as mis-bound if it stays in db-only.
- A `two-key` mismatch means the two stores disagree — that is a tamper/incident signal, not a "try
  again"; surface it, don't silently retry.
- Keep rate-limiting / lockout in cf-abuse-guard (the KV limiter + login-lockout in this same file are
  that concern) — this skill is only the two-store integrity + epoch invalidation delta.
