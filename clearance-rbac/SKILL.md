---
name: clearance-rbac
description: >-
  Admin-editable role-based access control for any multi-seat Cloudflare Worker + D1 app: named
  "clearance" bundles (a grouped permission catalog defined in code, custom levels created and
  re-permissioned at runtime by the operator, assignable per user), owner-always-all so nobody can
  lock themselves out, locked built-in levels, legacy-role fallback so existing seats keep working,
  create-user-directly-at-a-clearance, and a LIVE view-vs-mutate endpoint gate. Read-only / viewer
  seats are just a clearance. EXTENDS cf-identity (adds an operator-editable permission layer on top of
  its flat admin/worker/investor roles). Use WHENEVER a build needs "custom permissions", "roles I can
  edit myself", "read-only seats", "view but not edit", "permission levels", "who can do what",
  "staff tiers", "granular access", "a viewer account", or productizing RBAC as a standalone module for
  a multi-user portal/CRM/admin. Guardrails: the owner (role='admin') always holds every permission;
  built-in levels are locked from edit/delete; deleting a level falls its users back to legacy defaults,
  never to more access; enforcement is checked server-side on the request, never trusted from the client.
---

# clearance-rbac — operator-editable permissions (RBAC on Cloudflare)

## What it is / when to use
A permissions product the operator can run themselves: they define named **clearance levels** (bundles of
permission keys from a catalog you ship in code), assign one to each user, and every protected route checks
the caller's resolved permission set. A "read-only" or "viewer" seat is not a special code path — it's just a
clearance with the `.view` keys but not the `.run`/`.manage` keys. Reach for it any time flat roles aren't
enough and the customer needs to shape access without a redeploy.

**Extends `cf-identity`.** cf-identity gives you `users`, `sessions`, `currentUser()`, and coarse roles
(admin / worker). This skill adds a `clearances` table + a `clearance_id` on `users` + a permission resolver,
turning those flat roles into an operator-editable system. Build cf-identity first.

## Reference implementation (lift the proven code)
All paths under `~/Projects/clients/wavelygth/`:
- **Catalog + resolver + CRUD + create-user-at-clearance:** `worker/index.js` **L837–937**
  - `CLEARANCE_CATALOG` (the code-defined permission schema, grouped) + `ALL_PERM_KEYS` — L844–858
  - `loadPerms(env, user)` — the resolver: owner→all, clearance→its perms, else legacy-role default — L862–871
  - `handlePermissionCatalog` / `handleListClearances` — expose the catalog + levels to the UI — L873–880
  - `handleSaveClearance` (create or rename/re-permission; blocks editing built-ins) — L882–901
  - `handleDeleteClearance` (blocks deleting built-ins; nulls `clearance_id` on affected users) — L903–914
  - `handleCreateUser` (create an operator user AT a clearance, returns an invite link) — L916–937
- **Live enforcement gate:** `worker/index.js` **L3140–3159** — `dperms = await loadPerms(env, me)`;
  `.view` to read, `.run` to mutate; admin-only sub-routes still layered on top.
- **Router registration (admin-only):** `worker/index.js` **L3186–3190**.
- **Migrations:** `worker/migrations/0020_clearances.sql` (the `clearances` table + `clearance_id` column +
  two locked built-ins seeded) and `worker/migrations/0019_readonly_seats.sql` (the `readonly` flag used by the
  legacy-role fallback — the "viewer seat is just a clearance" precursor).
- **UI (admin tick-grid editor):** `portal/index.html` **L926–973** — `loadClearances`, `renderPermPicker`
  (grouped checkbox grid), `openClearanceEditor`, save/edit/delete handlers + a clearance `<select>` on the
  create-user form (L935).
- **Proofs:** `worker/lib/_proof/clearances.test.mjs` (end-to-end: catalog exposed, built-ins seeded+locked,
  custom level created, user created on it, view-only blocked from run, editing a level re-permissions its
  users, delete works on custom only, no-clearance user gets nothing, owner never blocked) and
  `readonly-seat.test.mjs`. Run: `npm run proof:clearances`.

## How to reapply it
1. **Migration.** Create a `clearances` table (`id` TEXT PK, `name`, `perms` TEXT = JSON array of keys,
   `is_system` INTEGER for locked built-ins, `created_at`) and `ALTER TABLE users ADD COLUMN clearance_id TEXT`.
   Use plain `CREATE TABLE IF NOT EXISTS` + `ADD COLUMN` (no CHECK, no rebuild) so it applies on a live remote
   D1. Seed 1–2 built-ins with `is_system=1` as examples. Copy `0020_clearances.sql` and rename the seeded
   perm keys.
2. **Define your catalog in code.** Write a `CLEARANCE_CATALOG` array of `{key, label, group}` for YOUR
   domain (e.g. `orders.view` / `orders.manage` / `customers.view` / `billing.manage`). Derive
   `ALL_PERM_KEYS`. This is the whole "rename the catalog and go" step.
3. **Resolver.** Copy `loadPerms(env, user)`: `role==='admin'` → `new Set(ALL_PERM_KEYS)`; a `clearance_id` →
   parse that clearance's `perms` JSON into a Set; otherwise return a legacy-role default Set so pre-existing
   seats keep the access they had.
4. **CRUD handlers.** Copy `handleListClearances` (returns levels + the catalog so the UI can render the
   picker), `handleSaveClearance` (filters incoming perms to `ALL_PERM_KEYS`; on edit refuse when
   `is_system`), `handleDeleteClearance` (refuse `is_system`; `UPDATE users SET clearance_id=NULL` before the
   DELETE), and `handleCreateUser` (insert a user with the chosen `clearance_id` + mint a cf-identity invite
   link). Register them all behind the admin gate.
5. **Enforce on every protected route.** At the top of a gated surface: `const perms = await loadPerms(env, me);`
   then `if (!perms.has('x.view')) return 403;` and `if (method !== 'GET' && !perms.has('x.run')) return 403;`.
   Keep truly destructive/shared-state routes as an extra `requireAdmin(me)` layer on top of the perm check.
6. **UI.** Copy the grouped-checkbox permission picker (`renderPermPicker`) and the levels table; add a
   clearance `<select>` (default option = "full / legacy") to your create-user form.

## Gotchas (from the code + proofs)
- **Owner immunity is non-negotiable.** `loadPerms` returns ALL keys for `role==='admin'` BEFORE it looks at
  `clearance_id`. Without this an operator can save a clearance that locks themselves out. The proof asserts
  "owner is never clearance-blocked."
- **Built-ins must be locked.** Both edit and delete return 409 when `is_system=1`. Seed them so the operator
  has working examples they can't accidentally break; they clone-then-edit to make their own.
- **Delete falls back DOWN, never UP.** Deleting a level `UPDATE users SET clearance_id=NULL`, dropping those
  users to the legacy-role default (which is *less* access), never orphaning them into more.
- **Filter incoming perm keys against the catalog** (`b.perms.filter(k => ALL_PERM_KEYS.includes(k))`) so a
  client can't inject an unknown/privileged key by editing the request.
- **The gate is server-side and per-request.** The UI hiding a button is cosmetic. `loadPerms` runs inside the
  route handler on every call; never trust a client-sent role/perm.
- **Migration stays additive.** `0020` deliberately avoids a CHECK constraint or FK so it applies to the live
  remote DB with no table-rebuild dance (contrast the role-widening rebuild that a new enum value would force).
- **Legacy fallback keeps old seats alive.** A user created before clearances existed has `clearance_id=NULL`
  and still resolves to a sensible permission set via the role branch — don't remove that branch.
