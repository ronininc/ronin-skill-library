---
name: scoped-bearer-token
description: >-
  A scoped, revocable API key for headless / companion / non-browser clients of a Cloudflare Worker + D1
  app: mint a prefixed token whose PLAINTEXT is shown exactly once (only its SHA-256 hash is stored),
  authenticate a request by hashing the `Authorization: Bearer` header and matching the stored hash,
  track last-used, revoke on demand, treat the Bearer path as CSRF-exempt (no cookie ⇒ no browser can
  auto-send it ⇒ no same-origin check needed), and HARD-SCOPE it at the router to a single API surface —
  never its own token-management endpoints, never admin. EXTENDS cf-identity (the token resolves to a
  cf-identity user with least privilege). Use WHENEVER a build needs a machine/agent/CLI/companion to call
  the API without a login session — "personal access token", "API key", "let my script/bot/worker call
  it", "headless client", "service credential", "a token for the companion app / Raspberry Pi", "give the
  integration a key". Guardrails: store ONLY the hash (plaintext is unrecoverable after mint), show it once,
  make it revocable, path-scope it so a leaked token can't escalate, and keep the CSRF exemption EXPLICIT
  and narrow (Bearer only, never a cookie).
---

# scoped-bearer-token — a least-privilege API key for headless clients

## What it is / when to use
Browsers get a session cookie (cf-identity). A companion app, CLI, cron box, or agent has no browser, so it
carries a **Bearer token** instead. This skill is the safe way to issue one: prefixed, hash-only-stored,
shown once, revocable, last-used-tracked, and — critically — **scoped at the router to exactly one API
surface** so a leak can't reach admin or its own re-mint. Reach for it whenever something non-interactive
must call your Worker.

**Extends `cf-identity`.** The token maps to a cf-identity `users` row (`companion_tokens.user_id`), inheriting
that user's identity but *not* their full session privileges — the router narrows it. Build cf-identity first.

## Reference implementation (lift the proven code)
All paths under `~/Projects/clients/wavelygth/`:
- **Hash helper + resolver:** `worker/index.js` **L210–225**
  - `sha256hex(s)` — L210–213
  - `companionUser(req, env)` — regex-extracts a `Bearer <prefix>_<hex>` token, hashes it, joins
    `companion_tokens → users` on `token_hash` where `revoked=0 AND u.active=1`, and best-effort updates
    `last_used_at` — L216–225
- **Mint / list / revoke handler:** `worker/index.js` **L2645–2663** (`handleCompanionToken`): GET lists
  (metadata only — never the token), DELETE sets `revoked=1` scoped to the caller's `user_id`, POST mints a
  fresh `<prefix>_<32-byte-hex>`, stores only `sha256hex(token)`, returns the plaintext **once**.
- **Router: Bearer auth + CSRF exemption + path-scope:** `worker/index.js` **L3079–3113**
  - resolve `companion` from the Bearer BEFORE the same-origin/CSRF check, and skip that check for a companion
    request (L3082–3084) — the exemption is explicit and commented
  - `const me = companion || await currentUser(...)` (L3109)
  - the scope wall (L3113): a companion token is refused on anything outside its allowed prefix, **and**
    refused on its own management path — `if (companion && (!path.startsWith('/api/<surface>/') || path.startsWith('/api/<surface>/companion'))) return 403;`
- **Migration:** `worker/migrations/0011_companion_token.sql` — `companion_tokens` (`id` PK, `user_id`,
  `label`, `token_hash` UNIQUE, `created_at`, `last_used_at`, `revoked`) + an index on `user_id`.
- **UI:** `portal/index.html` **L1600–1616** — generate button, "copy this now, it's shown once" box, list
  with a Revoke button.
- **Proof:** `worker/lib/_proof/companion-token.test.mjs` — mints, uses the Bearer to hit the scoped surface
  with NO Origin header (proving CSRF exemption), asserts 403 on a non-scoped route AND on token management,
  401 on a bogus token, and 401 after revoke. Run: `npm run proof:companion`.

## How to reapply it
1. **Migration.** Copy the `companion_tokens` table. `token_hash` is UNIQUE and is the ONLY representation of
   the secret stored.
2. **Helpers.** Copy `sha256hex` and `companionUser`. Pick a short distinctive prefix for your app (so a
   leaked token is greppable/identifiable) and put it in the resolver's regex, e.g. `^Bearer\s+(myapp_[A-Za-z0-9]+)$`.
3. **Mint/list/revoke handler.** Copy `handleCompanionToken`. Mint = `prefix + randomHex(32)`, store
   `sha256hex(token)`, return the plaintext once in the POST response and never again. Scope list/revoke to
   `WHERE user_id = ?`.
4. **Router wiring (the security-critical part).**
   - Resolve `const companion = await companionUser(req, env)` early.
   - Compute `mutating = method !== 'GET'`; only bypass the same-origin/CSRF check
     `if (mutating && !companion && !sameOrigin(...))` — i.e. cookies still need CSRF, Bearers don't.
   - `const me = companion || await currentUser(req, env); if (!me) return 401;`
   - Immediately after, the scope wall: reject a companion request that isn't under its one allowed path
     prefix, and reject it on the token-management endpoint itself.
5. **UI.** Copy the generate/copy-once/revoke widget.

## Gotchas (from the code + proof)
- **Hash-only storage, shown once.** Only `sha256hex(token)` is stored; the plaintext exists solely in the
  mint response. If the operator loses it they must revoke and re-mint — there is no "show me the token
  again." This is the reusable security contract; don't add a "reveal" endpoint.
- **The CSRF exemption is deliberate and must stay narrow.** It's safe *because* a browser can't auto-attach a
  Bearer header the way it auto-attaches cookies, so there's nothing to forge. Exempt ONLY the Bearer path,
  never loosen the cookie path's same-origin check.
- **Scope the token, not just authenticate it.** Authentication (who) and authorization (what) are separate:
  the token proves identity, the router `path.startsWith(...)` wall limits what it can touch. The proof
  asserts a valid token still gets 403 outside its surface AND on token management (so a leaked dialer token
  can't mint more tokens or reach admin).
- **Two hashers can coexist — pick one per feature and be consistent.** This repo has `sha256hex` (Bearer
  tokens) and a separately-named `sha256Hex` (magic-link auth tokens). They're the same algorithm; just don't
  mismatch the mint and the verify.
- **`last_used_at` update is best-effort** (`.catch(() => {})`) so telemetry never blocks auth.
- **Revoke = a flag, not a delete.** `revoked=1` keeps the row for audit/last-used history; the resolver's
  `WHERE revoked=0` is what actually turns it off.
