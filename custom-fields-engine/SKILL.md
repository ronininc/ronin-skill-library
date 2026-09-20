---
name: custom-fields-engine
description: >-
  The atom that makes a CRM/records app VERTICAL-AGNOSTIC without a code fork: an ADMIN defines an
  extra field schema (label + type + options, scoped per entity) and STAFF set that field's value per
  record — so a dentist, a law firm, a gym, a salon, or a contractor differ only in config rows and
  data, NEVER in schema code. It encodes two hard splits: (1) field-DEFINITION lives in a normalized
  `*_field_defs` table while field-VALUE lives in a JSON blob column on the record, and (2) DEFINING or
  DELETING a field is a schema change (admin-only), while SETTING a value is ordinary data entry
  (staff / records-clearance) — with every value-write whitelisted against the current defs so the blob
  can only ever hold defined keys. Use WHENEVER a build must adapt its record model to a client's
  vertical at runtime: "let them add their own fields", "add a custom field", "don't hardcode the schema
  for this vertical", "make the CRM fit a dentist / gym / law firm", "per-client / per-vertical fields",
  "extra fields on a contact / lead / member / patient / case", "admin defines fields, staff fill them
  in", "EAV / flexible attributes without a migration per client", or "one codebase, many industries".
  COMPLEMENTS (extend, do NOT duplicate): crm-build-standard (this is the mechanism that makes its one
  build serve any pipeline), commerce-spine (the D1 node these defs + values land in), and
  collision-safe-identifier-derivation (call it at the label→key seam when an operator authors several
  fields at once — the base here relies only on a UNIQUE constraint + upsert, which MERGES two labels
  that slug alike instead of suffixing them). Guardrail: the two-tier permission split is non-negotiable
  and values are UNTYPED at rest — never let the value path define schema, and never trust the JSON blob
  to enforce a field's declared type.
---

# Custom Fields Engine — admin-defined schema, staff-set values, one codebase for any vertical

## What it is / when to use / what it composes with
A tiny, self-contained mechanism that lets one records codebase fit **any** industry at runtime instead
of forking the schema per client. An admin declares extra fields on an entity (e.g. a contact/lead:
"Policy Number" as text, "Membership Tier" as a select, "Waiver Signed" as a checkbox); staff then fill
those fields in per record. The vertical lives entirely in **config rows + data**, so the schema code is
identical for every client — which is exactly what makes a house CRM "agnostic" rather than a template
you re-fork.

Use it whenever a build needs runtime-extensible records: extra fields on contacts/leads/members/
patients/cases, "let the client add their own fields", or "one codebase, many industries." It is the
**mechanism layer** under `crm-build-standard` (that skill orchestrates a whole build; this is the one
seam that keeps its record model universal), lands its two objects in the `commerce-spine` D1 node, and
composes with `collision-safe-identifier-derivation` at the label→key derivation seam (see Gotchas).

Do NOT reach for a full EAV (entity-attribute-value) table or a JSON-schema validation engine — the
whole point of this atom is that the def table is small and the values are a merge-into-a-blob. Reach for
those only if you outgrow the deliberate trade-offs below.

## Reference implementation — proven + tested; lift the proven code from these exact lines
Baseline: an app-forge CRM Worker (Cloudflare Worker + D1). Genericize every label/entity example below;
copy the CONTRACTS and shape, not any client's fields.

- **Handlers** — `worker/custom-fields.ts`:
  - `ENTITIES` / `TYPES` allow-sets (11-12) — the entity scope and the closed type set
    (`text | number | date | select | checkbox`). Both are validate-against-set with a fallback, never an
    error, so a bad param degrades to the default entity/type instead of 500ing.
  - `slug(s)` (13) — base label→key normalizer: lowercase, non-alphanumerics → `_`, strip leading/trailing `_` (`replace(/^_+|_+$/g,'')`), `slice(0,40)`.
    Note it does NO collision suffixing (see Gotcha 4).
  - `listFieldDefs(env,url)` (16-21) — `GET …/custom-fields?entity=<e>`: reads defs for the entity ordered
    by `sort, created_at`; `JSON.parse`s each def's `options`. `.catch(() => ({results:[]}))` so a missing
    table reads as "no fields," never a crash.
  - `saveFieldDef(req,env,me)` (26-43) — `POST …/custom-fields`: **admin gate at line 27**
    (`me.role !== 'admin'` → 403). Derives the key via `slug(key || label)`, caps options to 40 × 60 chars
    (35), clamps `sort` to 0–9999 (36), then UPSERTs with `INSERT … ON CONFLICT(entity,key) DO UPDATE` (39)
    so re-saving the same label edits the def in place.
  - `deleteFieldDef(req,env,me)` (46-53) — `DELETE …/custom-fields`: **admin gate at line 47**; removes the
    def by id only (does NOT scrub values — Gotcha 3).
  - `setContactCustom(req,env)` (56-71) — `POST …/custom-fields/value`: **no admin gate** (this is the
    staff/value path). Loads the record's `custom` blob, parses it defensively (63-64), builds an
    `allowed` set from the CURRENT defs (66-67), and merges **only whitelisted keys** into the blob,
    capping string values at 2000 chars (68). Persists the merged JSON (69). This is the enforcement point
    that keeps the blob honest.
- **Schema / migration** — `migrations/0071_custom_fields.sql`:
  - `custom_field_defs` (5-15): `id` PK, `entity` (default the first entity), `key`, `label`, `type` with a
    `CHECK (type IN (...))` matching the `TYPES` set, `options` (JSON text), `sort`, `created_at`, and the
    load-bearing `UNIQUE (entity, key)` (14).
  - `ALTER TABLE <entity_table> ADD COLUMN custom TEXT;` (16) — the JSON `{key:value}` blob that holds the
    values. Additive; no per-client migration ever needed after this.
- **Route + clearance wiring** — `worker/admin.ts` import (75) and routes (519-522): `GET`/`POST`/`DELETE`
  `custom-fields` + `POST custom-fields/value`. `worker/auth.ts`: `SUB_SECTION['custom-fields'] = 'crm'`
  (252) puts the whole sub-section behind records-clearance at the ROUTE tier; `sectionForSub` (267) +
  `authorizeAdmin` (270) enforce it. The admin re-gate inside the two schema handlers is the SECOND tier.
- **UI** — `public/admin/admin.js`:
  - Define/list/remove (admin "Setup" surface): fetch defs (626), render the card + list (658-661),
    `POST` a new field (690), wire per-row `DELETE` (692).
  - Set-value (per-record surface): fetch defs, degrade to a "no access" message on `403` (2121),
    render one input **per declared type** — checkbox / select-with-options / number|date|text (2128-2130),
    collect and `POST` the values (2133-2136). Type only shapes the INPUT; it is not enforced server-side.
- **Proof (hermetic)**:
  - `worker/lib/_proof/turnkey.test.mjs` (43-48): a field is created with a **derived key** (label
    "Policy Number" → `policy_number`), appears in the entity defs, and on value-set a defined key is saved
    while an **undefined key is ignored** (`!('bogus_key' in custom)`).
  - `worker/lib/_proof/clearances.test.mjs` (65-70): a records-clearance user **MAY** read defs and set a
    record's values but is **DENIED** defining a field (`POST` → 403), while an admin **MAY** define one —
    the exact permission split, asserted.

## How to reapply
1. **Migration** — add a `<entity>_field_defs` table (id, entity, key, label, type + CHECK, options JSON,
   sort, created_at, `UNIQUE(entity,key)`) and `ALTER TABLE <record_table> ADD COLUMN custom TEXT`. Keep it
   additive so no client ever needs a bespoke migration.
2. **Handlers** — port the four functions: `list` (parse options, order by sort), `save` (**admin-gate
   first**, derive key, upsert on `(entity,key)`, clamp options/sort), `delete` (**admin-gate first**,
   by id), and `setValue` (**no admin gate**, load blob → build allow-set from current defs → merge only
   allowed keys, cap string length → persist).
3. **Routes + clearance** — map `GET/POST/DELETE custom-fields` and `POST custom-fields/value` and put the
   sub-section behind records-clearance at the route tier; the schema handlers re-gate to admin internally.
4. **UI** — one admin panel to define/list/remove fields; one per-record panel that reads the defs and
   renders a type-appropriate input for each, degrading to a "no access" note on 403.
5. **THE INVARIANT** — *Definition is schema (admin-only, normalized table); value is data (staff, JSON
   blob on the record); every value-write is whitelisted against the CURRENT defs so the blob can hold only
   defined keys.* Hold this and a new vertical is pure config + data — the schema code never changes.

## Gotchas — real pitfalls from the code
1. **Silent whitelist, not an error.** `setValue` drops keys that aren't defined fields rather than
   rejecting the request (turnkey.test.mjs:48 proves it). Good (blocks arbitrary blob injection), but the
   caller gets no "unknown field" signal — surface it in the UI if operators need to know.
2. **Values are UNTYPED at rest.** The server stores whatever string the client sent; it does NOT validate
   the value against the field's declared `type` (a "number" field can hold `"abc"`, a "select" can hold a
   value not in `options`). Type only shapes the input widget (admin.js 2128-2130). If you need integrity,
   add server-side coercion/validation — do not trust the blob.
3. **Deleting a def orphans its values.** `deleteFieldDef` removes only the def row; existing values stay in
   every record's `custom` blob, now hidden (list won't return them, the whitelist won't re-accept them).
   Re-creating a field with the same derived key RESURRECTS the stale values. Add a blob-scrub pass on
   delete if that surprises anyone.
4. **`slug()` here MERGES colliding labels — it does not suffix.** Two distinct labels that normalize to the
   same key (e.g. "Client Note" and "Client-Note" → `client_note`) UPSERT into one def via
   `ON CONFLICT(entity,key)`; the second silently overwrites the first. Fine for one-at-a-time admin entry;
   for any flow that derives several keys at once (bulk/import/AI-authored fields), compose
   **collision-safe-identifier-derivation** at the label→key seam so distinct labels get `_2, _3…` instead.
5. **The two-tier permission split is mandatory — neither tier alone is correct.** Route-clearance only
   (`SUB_SECTION`) would let records-staff edit the schema; the in-handler `me.role !== 'admin'` re-gate is
   what confines DEFINE/DELETE to admins. Handler-gate only (no route mapping) would make the sub-section
   unreachable to staff and break value-setting. Both, together, are least-privilege — and both are asserted
   in clearances.test.mjs:67-70.
6. **Abuse bounds are load-bearing.** Options cap (40 × 60 chars, line 35), sort clamp (0–9999, line 36),
   and the 2000-char value cap (line 68) keep a hostile or fat-fingered payload from bloating the def table
   or the record blob. Keep them when porting.
7. **Entity scope is real but one-wired.** The def table is `entity`-scoped and the `ENTITIES` set exists so
   more record types can opt in, but the baseline wires exactly one entity and only that table has a `custom`
   column. To add another (e.g. deals/orders): add it to `ENTITIES`, `ALTER` that table `ADD COLUMN custom
   TEXT`, and add a value-setter handler + route for it. Do not assume every table already carries `custom`.
8. **Validated by proof, not by types.** The guarantees (derived key, undefined-key rejection, the
   admin/staff split) are enforced by the two hermetic `_proof` tests above, not by the DB or TypeScript —
   port the tests alongside the code so the invariant stays proven in the new build.
