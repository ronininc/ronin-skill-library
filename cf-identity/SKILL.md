---
name: cf-identity
description: >
  Add real user login/signup/sessions to any site or app WITHOUT a third-party
  auth service — a from-scratch clone of Netlify Identity / Supabase Auth built
  on a Cloudflare Worker + D1 (SQLite). Use whenever a build needs "let people
  log in", "create an account", "members-only area", "staff/crew portal",
  "password login", "who is signed in", or a secure gate in front of pages or
  APIs, and you want to own the whole thing (no Auth0/Clerk/Supabase/Netlify
  Identity). Covers PBKDF2 password hashing with Web Crypto, a users + sessions
  schema, HttpOnly session cookies, an auth middleware, roles (admin/worker),
  and an optional shared sign-up code. Working reference:
  ~/Projects/clients/slik-team-board (standalone repo).
---

# cf-identity — own your login (Netlify Identity, cloned onto Cloudflare)

Netlify Identity / Supabase Auth / Auth0 are hosted login services. This skill
reproduces the useful 90% of them with code you own: a Worker + a D1 table.
Nothing leaves your Cloudflare account, there is no per-user billing, and there
is no SDK to break.

**Reference implementation (copy from here):** `~/Projects/clients/slik-team-board/src/index.js`
and `~/Projects/clients/slik-team-board/migrations/0001_init.sql`. It is a live, verified build.

## What you get
- `users` (id, name, email UNIQUE, role, pass_hash, pass_salt)
- `sessions` (token, user_id, expires_at)
- Register → Login → `/api/me` → Logout
- Passwords hashed with **PBKDF2-SHA256** via `crypto.subtle` (no npm deps)
- Session token in an **HttpOnly, SameSite=Lax** cookie; `Secure` auto-on over https
- An `currentUser(req, env)` middleware every protected route calls first
- Roles: first account bootstraps as `admin`; others default `worker`
- Optional `TEAM_CODE` env var to gate sign-up to people who know a shared word

## The 6 pieces (all in the reference file)
1. **hashPassword(password, saltHex)** — `deriveBits({name:'PBKDF2', salt, iterations:100000, hash:'SHA-256'}, key, 256)`. Store hex hash + hex salt. Never store the password. ⚠️ The Cloudflare Workers runtime hard-caps PBKDF2 at **100000** iterations ("iteration counts above 100000 are not supported"). Miniflare (local `wrangler dev`) does NOT enforce this, so a higher value like 120000 passes every local test and then throws on EVERY password hash in production — surfacing as a 500 on register/login only after deploy. Never exceed 100000.
2. **startSession(user)** — `crypto.getRandomValues(32)` → hex token, insert into `sessions` with an expiry, `Set-Cookie`.
3. **currentUser(req, env)** — read cookie, `JOIN sessions→users WHERE token=? AND expires_at > now`.
4. **register** — validate, check team code with a constant-time compare, reject duplicate email, insert, start session.
5. **login** — look up by email, re-hash with the stored salt, constant-time compare, start session.
6. **logout** — delete the session row, clear the cookie (Max-Age=0).

## Rules that keep it safe
- Same generic message for "no such email" and "wrong password" (don't reveal which).
- Enforce a minimum password length; hash with a per-user random salt.
- Cookies are `HttpOnly` (JS can't read them) + `SameSite=Lax`; add `Secure` on https.
- Constant-time compare for the team code and password hash (see `safeEqual`).
- Protected routes call `currentUser` and return 401 before doing anything.

## Adapt it to a new project
1. Copy the `users` + `sessions` tables into your migration.
2. Copy the helpers (`hashPassword`, `randomHex`, `parseCookies`, `sessionCookie`, `currentUser`).
3. Wire `POST /api/auth/{register,login,logout}` and `GET /api/me`.
4. Gate every private route: `const me = await currentUser(req, env); if (!me) return bad('Please log in.', 401);`
5. For email verification or password reset, add a `tokens` table + the
   `cloudflare-email-service` skill to send the link.

Pairs with **cf-functions** (the routing), **cf-deploy** (going live), and the
`durable-objects` skill if you later want real-time presence.
