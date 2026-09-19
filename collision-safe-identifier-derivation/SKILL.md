---
name: collision-safe-identifier-derivation
description: >-
  The small, deterministic technique for turning human-supplied NAMES (entity/field labels, column
  headers, tab titles, menu items, tags) into machine IDENTIFIERS (slugs, DB table/column names, storage
  keys) that are UNIQUE within their scope, never collide with RESERVED/system names, and are IDEMPOTENT
  (re-deriving reproduces the exact same assignment). Two distinct names that naively slug to the same
  string — "Customer Note" and "Customer-Note" both → `customer_note` — otherwise silently share one
  storage key / DB column and OVERWRITE each other's data, or emit a duplicate column that breaks a
  migration; and a field named "id"/"created at" collides with an auto-inserted system column. This atom
  fixes both: suffix `_2, _3…` for in-scope collisions (name+order derived, so it's stable across runs),
  and for reserved collisions either SKIP the field (when the system column already means it) or RENAME
  it deterministically. Use WHENEVER a build derives identifiers from user/AI/import data: "slug from a
  title", "column name from a spreadsheet header", "make these keys unique", "map fields to a table",
  "these two names collide", "reserved/system column clash", "why did two records overwrite each other",
  or any name→key mapping feeding storage. COMPLEMENTS spec-contract-scaffold-pipeline (its
  normalize/spec step calls this), agnostic-import-parser (which maps foreign headers to columns),
  commerce-spine / crm-build-standard / d1-migration-recipes (the schemas these keys land in), and
  single-source-data-embed. Guardrail: identifiers must be derived from name + order ONLY (never a
  random id or timestamp) or the mapping stops being idempotent and re-runs churn the schema.
---

# Collision-Safe Identifier Derivation — unique, reserved-safe, idempotent name→key

## What it is / when to use / what it composes with
A tiny, pure helper set that any build reuses at the seam where **human-supplied names become machine
keys**. It guarantees three properties that naive `slugify()` does not:
- **Unique within scope** — no two distinct names in the same set collapse onto one identifier.
- **Reserved-safe** — a derived key never clashes with an auto-inserted system column / built-in key.
- **Idempotent** — the assignment depends only on the names and their order, so re-deriving (e.g. after a
  round-trip through the model, or a re-import) yields byte-for-byte the same identifiers and never churns
  the schema or breaks existing rows.

The failure it prevents is silent and data-losing: without it, "Customer Note" and "Customer-Note" write
to the same `localStorage` key or the same DB column, clobbering each other; or a `CREATE TABLE` emits two
columns with the same quoted name and the migration fails; or a field named "id" duplicates the primary key.

Use it anywhere a name→identifier mapping feeds storage: spec/scaffold generators, spreadsheet/CSV import,
tag/category systems, tab or route slugs, menu-item keys. Composes with **spec-contract-scaffold-pipeline**
(its `normalize_spec` step), **agnostic-import-parser** (header→column mapping), **d1-migration-recipes** /
**commerce-spine** / **crm-build-standard** (the target schemas), and **single-source-data-embed**.

## Reference implementation (apps/appforge — a prompt→app builder; OPEN these)
- **In-scope uniqueness + idempotence** — `apps/appforge/backend/app/forge/spec.py`:
  - `slug(text)` (129-130) — the base normalizer: lowercase, non-alphanumerics → `_`, trim, and a
    non-empty fallback (`"item"`) so an all-symbol name never yields an empty key.
  - `_unique_slug(text, seen)` (133-149) — the atom: compute the base slug, and while it's already in the
    `seen` set for this scope, suffix `_2, _3, …`; add the result to `seen`. Purely name-and-order derived,
    so re-running reproduces the same assignment. The docstring states exactly the overwrite bug it prevents.
  - `normalize_spec` (152-172) — uses a FRESH `seen` set per scope: one for entity slugs, a new one per
    entity for its field slugs (159-164), so uniqueness is scoped correctly (fields collide only within
    their own entity, not globally).
- **Reserved / system-column safety** — `apps/appforge/backend/app/forge/baas_supabase.py`:
  - `_SYSTEM_COLS = ("id","owner_id","created_at")` and `_SKIP_SYSTEM_COLS = {"id","created_at"}` (23-26) —
    the reserved set, split by whether the system column already *means* the field.
  - `render_migrations` (29-63): seed `taken` with the system columns (39), then for each field: if its
    slug is a "skip" reserved (`id`/`created_at`) drop the field entirely (42-43, the system column covers
    it); if it collides with any other taken name, deterministically rename `base_1, base_2, …` (44-51).
    Result: every emitted column identifier is unique and no system column is duplicated.
- **Proof (hermetic)** — `apps/appforge/backend/tests/test_spec_slug_collision.py`: entity + field
  collisions disambiguated (15-44), the Supabase migration emits no duplicate quoted identifier (47-67),
  and disambiguation is idempotent across two `normalize_spec` runs (70-82).
  `apps/appforge/backend/tests/test_baas_reserved_columns.py:46-65`: fields named "id"/"owner id"/"created
  at" never re-emit a reserved column (owner_id → `owner_id_1`, id/created_at skipped), and no column name
  is defined twice in the whole migration.

## How to reapply (in a CLIENT build)
1. **One base normalizer.** `slug(s)`: lowercase → replace `[^a-z0-9]+` with `_` → strip `_` → fallback to
   a constant when empty. Use it everywhere so keys are consistent.
2. **Add a scoped uniqueness pass.** Carry a `seen` set per scope; for each name, `base = slug(name)`, then
   bump `base_2, base_3…` until free, and record it. Assign the result back onto the record (e.g.
   `field.slug = ...`) so downstream stages use the deduped key, not a re-slug of the name.
3. **Scope the sets correctly.** Fresh `seen` per level: one for top-level entities/tables, a new one per
   parent for its children/columns. Global-only or per-record-only scoping is usually a bug.
4. **Reserve your system keys.** Seed `seen`/`taken` with the identifiers your storage inserts automatically
   (`id`, `created_at`, `owner_id`, a tenant column…). Decide per reserved key whether a colliding field is
   *the same thing* (skip it) or *a different thing* (rename it) — don't blanket-drop.
5. **Keep it name+order derived only.** Never disambiguate with a random suffix, uuid, or timestamp — that
   destroys idempotence and makes every re-import/regeneration churn the schema and orphan existing data.
6. **Test the collision + idempotence explicitly.** Assert distinct names → distinct keys, no duplicate
   emitted identifier, and that deriving twice gives the identical result.

## Gotchas
- **Idempotence is the whole point.** If you ever fold in anything non-deterministic (insertion into a dict
  whose order isn't stable, a random tiebreak), a re-run reassigns keys and existing rows point at the wrong
  column/key. Derive from the ordered list of names and nothing else.
- **Two reserved-collision strategies, not one.** `id`/`created_at` usually mean the auto column, so skip the
  spec field; `owner_id` (or a tenant/user key) is semantically the operator's, so a user field that slugs to
  it must be RENAMED, not dropped — dropping would lose that field's data. Choose per key (see `_SKIP_SYSTEM_COLS`).
- **Empty/degenerate names.** A name of only punctuation slugs to empty; without the fallback it becomes an
  invalid identifier or an accidental shared `""` key. Always fall back to a constant.
- **Case and unicode.** Lowercasing merges "Note" and "note"; that's usually correct for storage keys but
  means they'll be deduped to distinct keys (`note`, `note_2`) — surface the mapping if the UI shows the
  original names, so the operator understands why "two Notes" exist.
