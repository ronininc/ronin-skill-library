---
name: d1-tenancy-wall
description: >-
  Row-level multi-tenant isolation for a Cloudflare Worker + D1 app, reduced to two functions and one
  ironclad discipline: a `visibility()` query that returns ONLY the rows a given user is allowed to see
  (their own + any explicitly shared/"firm" rows + everything for an admin), and a `require(id)` guard that
  rejects any client-supplied resource id not already in that visible set (404, not 403 — never confirm the
  row exists) — with the rule that NO route EVER binds a caller-supplied id into a query without first
  passing it through `require()`. EXTENDS cf-identity (uses its user/role model). Use WHENEVER one user must
  not see another's data — "multi-tenant", "each customer sees only their own records", "row-level
  security", "tenant isolation", "scope data to the logged-in user", "an investor/client can't reach
  another's account", "don't leak other users' rows", "IDOR", "authorization on the object, not just the
  endpoint". Its value is as much the PROOF TEMPLATE as the code: a cross-tenant leak is a reportable
  privacy/security incident, so the pattern ships with a test that proves user A cannot address user B's id.
  Guardrails: check ownership on the OBJECT every time (not just "are you logged in"); an unauthorized id
  returns 404 so existence isn't confirmed; admins are the only all-rows role; the check is centralized so
  it can't be forgotten route-by-route.
---

# d1-tenancy-wall — the two-function data-isolation spine

## What it is / when to use
The single most security-critical pattern in any multi-user product, kept deliberately tiny so it's obviously
correct and impossible to route-around:
- **`visiblePortfolios(env, user)`** (rename `portfolios` to your owned resource) — the ONE query that
  computes the set of rows this user may touch: admin → all; otherwise `own OR shared/'firm'`.
- **`requirePortfolio(env, user, id)`** — takes a client-supplied id, and returns the row only if it's in the
  visible set, else `null` (the caller turns that into a 404).

The discipline: **every** route that accepts a resource id resolves it through `require()` before using it.
No exceptions, no "this one's internal." Reach for this the moment two users share a database.

**Extends `cf-identity`.** It reads `user.role` and `user.id` from the cf-identity user. Build cf-identity first.

## Reference implementation (lift the proven code)
All paths under `~/Projects/clients/wavelygth/`:
- **The two functions:** `worker/index.js` **L534–550**
  - `visiblePortfolios(env, user)` — admin returns all rows; otherwise
    `WHERE kind='firm' OR user_id = ?` bound to `user.id` — L539–546
  - `requirePortfolio(env, user, portfolioId)` — `list.find(p => p.id === portfolioId) || null` — L547–550
- **Every call site binds through it** — e.g. `worker/index.js` L684 (portfolio list), L693 (history),
  L1454 (proof-of-funds), L1497 (monthly report). Note there is no code path that binds a caller id to a
  query without this hop.
- **Proof (the real deliverable):** `worker/lib/_proof/tenancy.test.mjs` — boots a fresh local D1, creates two
  users, and asserts: A sees an own row, A does NOT see B's row in its list, A GET-ing B's id → 404 on every
  read route, a non-admin → 403 on admin routes, and anonymous → 401. Run: `npm run proof:tenancy`.

## How to reapply it
1. **Model.** Give the owned resource a `user_id` column, and (optionally) a `kind`/`shared` marker for rows
   everyone in the tenant may see (the "firm" book). No new migration is unique to this skill — it's a
   discipline over your existing tables.
2. **The two functions.** Copy `visibility(env, user)` and `require(env, user, id)`, renaming `portfolios` to
   your resource. Keep the admin branch as the ONLY all-rows path.
3. **Route discipline.** Grep your router for every place a query binds a URL/body id
   (`url.searchParams.get('...')`, `b.id`). For each, insert
   `const row = await require(env, me, id); if (!row) return bad('Not found.', 404);` and use `row` — never
   re-query by the raw id afterward.
4. **Return 404, not 403, for an id outside the set.** A 403 confirms the row exists (just not for you); a 404
   reveals nothing.
5. **Write the proof.** Copy `tenancy.test.mjs` and rename the resource. Two users, cross-address every read,
   assert 404. This test is the artifact you show a security reviewer.

## Gotchas (from the code + proof)
- **Endpoint auth is NOT object auth.** "Is the caller logged in / an admin?" (the router gate) is a
  different question from "may THIS user touch THIS row?" (the tenancy wall). Both are required. The classic
  leak (IDOR) is a correctly-authenticated user passing someone else's id to an endpoint they're allowed to
  call.
- **Centralize so it can't be forgotten.** The whole point is one chokepoint. If you inline "own-vs-shared"
  logic per route, one route will eventually skip it. Route everything through the same two functions.
- **404 over 403 for a foreign id.** See step 4 — don't confirm existence.
- **Admin is the only all-rows role.** Everyone else is `own OR shared`. Don't add a second all-rows path
  without adding it to the proof.
- **Small on purpose.** Resist "optimizing" `require()` into a direct `SELECT … WHERE id=? AND user_id=?` per
  route — the two-function shape keeps a single visible-set definition that the proof pins. (If you do fold it
  into a query for hot paths, keep the shared visible-set predicate and re-run the proof.)
- **A leak here is reportable.** Treat a failing tenancy proof as a release blocker, not a nice-to-have.
