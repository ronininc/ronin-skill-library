---
name: d1-migration-recipes
description: >-
  A two-mode migration playbook for evolving a LIVE, remote Cloudflare D1
  (SQLite) database without downtime or data loss. MODE A (default, reach for it
  first): purely ADDITIVE change — CREATE TABLE IF NOT EXISTS, CREATE INDEX IF
  NOT EXISTS, ALTER TABLE ADD COLUMN with a DEFAULT, and idempotent INSERT OR
  IGNORE seeds — applies cleanly on the remote DB with no foreign-key dance.
  MODE B (only when a CHECK constraint / enum must WIDEN, which SQLite cannot
  ALTER in place): the full-table rebuild — PRAGMA defer_foreign_keys=ON, CREATE
  the new table with the widened CHECK, INSERT…SELECT with an EXPLICIT column
  list, DROP, RENAME. Use WHENEVER you are writing or reviewing a D1 migration:
  "add a column", "new migration", "add a role / status / enum value", "widen a
  CHECK constraint", "alter the constraint", "migrate the live D1", "why does my
  ALTER fail on --remote but pass locally", "foreign key error on migrate", or
  "add a read-only/seat flag". Backend pattern; pairs with wrangler d1 migrations
  and is the schema-evolution half under cf-identity / commerce-spine builds.
  Guardrails: prefer additive — a boolean flag column beats a new enum value and
  avoids the rebuild entirely; ADD COLUMN NOT NULL REQUIRES a DEFAULT; D1
  ENFORCES foreign keys remotely (miniflare does NOT), so a rebuild that passes
  local can trip on --remote unless you defer_foreign_keys; list columns
  EXPLICITLY in the copy (never SELECT *) so order can't drift; apply --local and
  prove, THEN --remote.
---
# d1-migration-recipes — evolve a live D1 without breaking it

## What it is / when to use
Concrete recipes for changing a running D1 schema. SQLite (and therefore D1) can
add tables, indexes, and columns cheaply, but it **cannot** alter or drop a
`CHECK` constraint in place — so widening an enum (adding a role/status value)
needs a table rebuild, and that rebuild interacts badly with the fact that D1
enforces foreign keys on the remote database. This skill is the decision — additive
vs rebuild — and the exact safe form of each.

## Reference implementation (Wavelygth — patterns only, no client data)
- `~/Projects/clients/wavelygth/worker/migrations/0019_readonly_seats.sql` — **additive** `ALTER TABLE … ADD COLUMN readonly INTEGER NOT NULL DEFAULT 0;` with a note that a plain flag avoids the FK dance a new role value forces.
- `~/Projects/clients/wavelygth/worker/migrations/0005_hardening.sql` and `0006_profile_branding.sql` — **additive**: `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `ADD COLUMN`.
- `~/Projects/clients/wavelygth/worker/migrations/0003_sharding.sql` **L41–42** — **idempotent seed** with `INSERT OR IGNORE` so re-running the chain (e.g. on every shard) is harmless.
- `~/Projects/clients/wavelygth/worker/migrations/0015_agent_role.sql` — the **CHECK-widening rebuild** (the whole file): `PRAGMA defer_foreign_keys=ON` → new table with widened CHECK → explicit `INSERT…SELECT` → DROP → RENAME, with the comments explaining every line.

## Mode A — additive (the default; safe on live remote)
```sql
-- New table: idempotent, so re-applying the chain never errors.
CREATE TABLE IF NOT EXISTS thing (
  id         TEXT PRIMARY KEY,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_thing_created ON thing(created_at);

-- New column: NOT NULL MUST carry a DEFAULT (SQLite fills existing rows with it).
ALTER TABLE users ADD COLUMN readonly INTEGER NOT NULL DEFAULT 0;

-- Seed a required row idempotently.
INSERT OR IGNORE INTO registry (id, state, created_at) VALUES ('root', 'active', CAST(strftime('%s','now') AS INTEGER) * 1000);
```
No FK dance, no rebuild, applies cleanly on `--remote`. **Reach for this first.**
If you need a new *variant* of something (a read-only seat, a paused state that
isn't in a constrained set), a boolean/flag column here beats adding an enum value.

## Mode B — CHECK-widening rebuild (only when an enum must grow)
SQLite can't `ALTER` a `CHECK`. To let `role IN ('admin','investor')` also accept
`'agent'`, rebuild the table:
```sql
-- FKs (sessions/portfolios/… .user_id) reference users by NAME, so they re-bind to
-- the rebuilt table after RENAME — but D1 CHECKS them remotely at COMMIT. Defer the
-- check (PRAGMA foreign_keys can't toggle inside a txn; defer_foreign_keys CAN).
PRAGMA defer_foreign_keys = ON;

CREATE TABLE users_new (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  email        TEXT NOT NULL UNIQUE,
  role         TEXT NOT NULL DEFAULT 'investor' CHECK (role IN ('admin','investor','agent')), -- widened
  pass_hash    TEXT NOT NULL,
  pass_salt    TEXT NOT NULL,
  active       INTEGER NOT NULL DEFAULT 1,
  created_at   TEXT NOT NULL,
  mfa_secret   TEXT,
  mfa_enabled  INTEGER NOT NULL DEFAULT 0,
  avatar       TEXT,
  source       TEXT,
  onboarded_at TEXT
);

-- EXPLICIT column list on BOTH sides (never SELECT *) so order can't silently drift
-- across every prior migration that added a column.
INSERT INTO users_new (id, name, email, role, pass_hash, pass_salt, active, created_at, mfa_secret, mfa_enabled, avatar, source, onboarded_at)
  SELECT id, name, email, role, pass_hash, pass_salt, active, created_at, mfa_secret, mfa_enabled, avatar, source, onboarded_at FROM users;

DROP TABLE users;
ALTER TABLE users_new RENAME TO users;
-- Recreate any indexes the old table had here (they are dropped with the table).
```

## How to reapply it
1. Name the file `NNNN_description.sql` in your `migrations_dir` (zero-padded, monotonic).
2. `npx wrangler d1 migrations apply DB --local` — apply locally first.
3. Prove it (see `d1-proof-harness`): boot the worker, exercise the changed surface.
4. `npx wrangler d1 migrations apply DB --remote` — only after local passes.
5. If you shard (commerce-spine), the **same chain runs on every shard**; registry
   tables that are authoritative only on shard 0 sit present-but-empty elsewhere — which
   is why seeds must be `INSERT OR IGNORE` and creates must be `IF NOT EXISTS`.

## Gotchas
- **SQLite can't ALTER/DROP a CHECK.** Widening an enum is the ONLY common reason
  to rebuild — everything else is additive. If you find yourself rebuilding for a
  non-enum reason, stop and look for an additive path.
- **D1 enforces FKs on the remote; miniflare does not.** A `DROP TABLE users` mid-rebuild
  trips children that reference `users(id)` on `--remote` even though it passed `--local`.
  `PRAGMA foreign_keys` can't be toggled inside a transaction, but
  `PRAGMA defer_foreign_keys = ON` **can** — it delays the FK check to `COMMIT`, by which
  point the rebuilt+renamed table has restored every id. Put it at the TOP of the migration.
- **List columns explicitly** in the new table and the `INSERT…SELECT`. `SELECT *`
  will silently misalign the moment column creation order differs from the new
  definition — enumerate them in creation order across all prior migrations.
- **`ADD COLUMN NOT NULL` requires a `DEFAULT`** so SQLite can fill existing rows.
- **FKs bind by table NAME**, so children re-attach to the rebuilt table after
  `RENAME` — no child rows are touched, *provided* you deferred the check.
- **Recreate indexes** after a rebuild — `DROP TABLE` drops its indexes too.
- **Idempotent everything** (`IF NOT EXISTS`, `INSERT OR IGNORE`) so re-running the
  chain, or running it on a fresh shard that already seeded, never errors.
- **Never change a live database's binding id / name in `wrangler.jsonc`** — that
  repoints the Worker at a different (empty) DB. Migrations change schema, not identity.
