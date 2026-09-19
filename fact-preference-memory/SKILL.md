---
name: fact-preference-memory
description: >-
  A tiny, deterministic "what we know + what they told us" memory for any CRM/app: one keyed,
  tenant-scoped store that holds two KINDS of value per key — a FACT (observed/inferred, lower default
  confidence) and a PREFERENCE (an explicit choice the user/operator stated, top confidence) — and a
  merge rule that resolves them to a SINGLE governing value the same way every time, regardless of write
  order: an explicit preference always beats an inferred fact; within a kind the most-recently-updated
  wins; then higher confidence; then a stable serialized-value tiebreak. Writing the same key again
  overwrites its prior value of that kind (a keyed upsert, not an append log). Fail-closed: a write or
  read with no tenant or no key throws rather than silently crossing tenants. Use WHENEVER a build needs
  to "remember a customer's/user's preference", "store what we learned about a contact", "let an
  explicit setting override our guess", "per-user settings that beat defaults", "remember their preferred
  language/channel/tone/appointment window", "learned vs. stated preferences", or "a small key→value
  memory that survives restarts". COMPLEMENTS crm-build-standard / commerce-spine (the record store it
  annotates), d1-tenancy-wall (tenant isolation — this reuses the same tenantId-in-the-key discipline),
  and pluggable-draft-brain / any personalization step (feed it the merged preference to tune output).
  It is NOT full-text search (see sqlite-fts5-knowledge-base), NOT an audit trail (see
  append-only-audit-log — this keeps only the current value per key/kind), and NOT bulk import
  (agnostic-import-parser). Guardrail: the merge is pure and order-independent by design — never let
  precedence depend on which write happened to land last unless recency is the explicit tiebreak within
  one kind.
---
# fact-preference-memory — explicit preference beats inferred fact, deterministically

## What it is / when to use
A small memory spine for personalization: keep, per `(tenant, key)`, the best value the app knows —
distinguishing a **fact** it *inferred/observed* ("this customer usually orders in the evening") from a
**preference** the person *explicitly stated* ("text me, don't call"). When both exist for a key, a
single pure `mergeSpecs` decides which governs, so every read gets the same answer no matter what order
the writes arrived in. Reach for it whenever an app should act on "what we know about you" and let an
explicit setting override a guess: preferred language, contact channel, tone, delivery window, seat,
dietary flag, whatever the client's domain needs.

It is deliberately NOT:
- **full-text/document search** — that's `sqlite-fts5-knowledge-base`;
- **an event/audit log** — that's `append-only-audit-log`; this stores only the current value per key/kind (a keyed upsert);
- **bulk record import** — that's `agnostic-import-parser`.

It pairs with any CRM record store (`crm-build-standard`, `commerce-spine`) as the "learned + stated
preferences" annotation on a contact, and with any personalization/draft step that should consume the
merged value.

## Reference implementation (exact files — lift from here)
**The merge spine** — `server/src/storage/knowledge-preference-store.ts` (TSS-own)
- `MemorySpec` L12-20: `{ tenantId, kind: 'fact'|'preference', key, value, confidence, source, updatedAt }`.
- Fail-closed normalizers L31-46: `normalizeTenantId` / `normalizeKey` **throw** on empty (never a
  cross-tenant or keyless write); `clampConfidence` pins to `[0,1]`, defaulting `0.5`.
- Writers L48-70: `writeFact` (default confidence `0.7`, source `observed`) and `writePreference`
  (default confidence `1`, source `explicit`) both call `writeSpec`, which **upserts** by key — writing
  the same key again overwrites the prior value of that kind.
- Readers L72-88: `readFact` / `readPreference` (one kind), `readSpecs` (both kinds for a key).
- **The rule** `mergeSpecs` L90-113 — resolve all specs for one key to the single governing spec,
  order-independent:
  1. `KIND_RANK = { preference: 1, fact: 0 }` — an explicit preference always outranks an inferred fact;
  2. within the same kind, the most recently `updatedAt` wins;
  3. tie → higher `confidence`;
  4. tie → lexicographic on the serialized value (pure determinism).
  It throws if the specs don't all share one key (a guard against merging apples and oranges).
- `readMergedSpec(tenantId, key)` L116-119 — the one-call read side: gather every spec for the key,
  return the resolved winner or `null`.

**The backing store** — `server/src/storage/db.ts` (an isolated per-node SQLite table; the store above
persists through it so a read touches only this concern, never the app's main tables)
- `putNodeRecord` L276-288 / `getNodeRecords` L291-297: a generic `node_records(recordId, tenantId,
  kind, recordKey, valueJson, …)` upsert/read. Note L279-282: the default `recordId` is
  `tenantId:kind:key` — **the tenant is part of the row identity**, so two tenants sharing a store can't
  collide on the primary key and silently overwrite each other. This is the same tenant-in-the-key
  discipline `d1-tenancy-wall` enforces.

## How to reapply (in a CLIENT build)
1. **Table.** Any keyed store works: a D1/SQLite table `memory(tenant_id, kind, mem_key, value_json,
   confidence, source, updated_at, PRIMARY KEY(tenant_id, kind, mem_key))`. `kind` is `'fact'` or
   `'preference'`. Ship it via `d1-migration-recipes`.
2. **Write.** `writeFact({tenantId, key, value, confidence?})` when the app *infers* something;
   `writePreference({tenantId, key, value})` when the user/operator *states* it. Both upsert on
   `(tenant, kind, key)`. Keep the default confidences (fact `0.7`, preference `1.0`) unless the domain
   needs otherwise.
3. **Read.** Call `readMergedSpec(tenantId, key)` wherever the app needs "the value we should act on".
   Feed `.value` into the personalization/draft step. Show `.source`/`.kind` in an admin UI so a human
   can see whether a value was stated or guessed.
4. **Fail closed.** Keep the empty-tenant / empty-key throws — a keyless or tenantless memory write is
   almost always a bug that would leak across tenants.

On a Worker + D1 build the whole thing is ~40 lines: the two writers, `readSpecs`, and `mergeSpecs`
(copy the comparator verbatim — it's the value of the skill), over one `env.DB` table.

## Gotchas
- **Merge must be order-independent.** The value of this pattern is that the SAME `(tenant, key)` always
  resolves to the SAME governing value regardless of write order. Recency is a tiebreak *within* one kind
  only — never let "last write wins" leak across kinds and let a stale inferred fact clobber a standing
  explicit preference.
- **Upsert, not append.** This stores the current value per key/kind. If the client needs the history of
  changes (who/when/what it was before), layer `append-only-audit-log` alongside — don't turn this into a
  log.
- **Tenant is part of the identity.** The default record id includes `tenantId`; if you re-key, keep the
  tenant in the primary key or two tenants will overwrite each other's memory.
- **Confidence is advisory.** It only tie-breaks within a kind and defaults sensibly; don't build gating
  logic on the raw number without deciding what the scale means for your domain.
- **`value` is opaque JSON.** Serialize deterministically (stable key order) if you rely on the
  value-string tiebreak, so equal values always compare equal.
