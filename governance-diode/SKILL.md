---
name: governance-diode
description: >-
  A one-way sanitized bridge between two control planes of a CRM: an OVERSIGHT role (a manager, an owner,
  a separate "Kingmaker" brain) can pull ONLY PII-free aggregate status + derived alert codes and CANNOT
  read customer records or write CRM data — its single reverse power is enqueuing a WHITELISTED directive
  into a control_signals table that the OPERATOR role then resolves under governance. Use WHENEVER a build
  needs "let my manager/owner watch the business without seeing customer PII", "an oversight dashboard that
  can't touch data", "separate the watcher from the operator", "a control channel between two brains",
  "aggregate health only, no names", or "raise a directive without direct access." The reusable core is:
  reads are aggregate-only, writes are a queued directive an authority resolves — a data diode, not a
  second admin login. It COMPLEMENTS crm-mcp-server (the diode is a SEPARATE role/route on that same MCP
  transport — build the server with that skill; this adds the sanitized snapshot, the alert derivation, and
  the control_signals table) and append-only-audit-log (each raised/resolved directive is an audit event).
  Guardrails: the oversight token carries NO crm:read/crm:write scope, snapshots emit only counts/totals,
  directives are a closed enum, and the operator — never the overseer — decides whether to apply one.
---
# governance-diode — oversight that can see the shape but not the people, and suggest but not act

Some roles need to WATCH a business (an owner, a manager, an external strategy brain) without the right to
read customer data or change anything. A diode gives them exactly that: aggregate, PII-free status and
derived alerts flowing OUT, and a single narrow channel flowing back — a whitelisted directive dropped into
a queue that the actual operator resolves. It is one-directional by construction: the oversight side has no
scope to read records or mutate the CRM.

## What it is / when to use
The separation-of-planes pattern for a CRM. Reach for it when there must be a watcher distinct from the
doer: owner-vs-staff, a strategy layer vs the operations layer, or a second AI whose job is to notice, not
to act. It is NOT a read-only admin seat (that's `clearance-rbac`); the point is that the watcher sees
aggregates only and can never enumerate customers.

**Composes with:** **crm-mcp-server** (the diode is a distinct role — e.g. `kingmaker` — with its own scope
bundle and its own MCP route on the same server transport; build the transport + token machinery there),
the **governed-operator-console** / operator MCP role (which owns `crm:write` and is the one that reads and
resolves the queued directives), and **append-only-audit-log** (raise + resolve are audit events). The
`control_signals` table IS the diode; both planes touch only it, never each other.

## Reference implementation (ronininc — read these)
- **The oversight plane** — `worker/kingmaker-mcp.ts:1-112`. Note the header comment stating the contract
  (`:1-10`). Key parts:
  - `statusSnapshot(env)` (`:23-37`) — ONE aggregate query: counts, pipeline value, revenue received,
    meetings booked, active campaigns, unread replies, autopilot state. No names, emails, or message text.
  - `alerts(env)` (`:39-58`) — derives PII-free `{code, severity, count, message}` items from counts only.
  - `send_control_signal` tool (`:78-94`) — the ONLY write: gated on a `control:signal` scope, directive
    must be in the `DIRECTIVES` whitelist (`:21`), inserts a `pending` row into `control_signals`. There is
    deliberately no tool here that reads a contact or changes CRM data.
  - Handler `handleKingmakerMcp` (`:99-112`) — requires the `kingmaker:read` scope and nothing more.
- **The operator side of the channel** — `worker/solomon-mcp.ts:279-300`: `list_control_signals` (read the
  pending queue, `:279-287`) and `resolve_control_signal` (`:289-300`) — guarded by `crm:write`, marks a
  row applied/rejected/acknowledged ONLY `WHERE status='pending'`. The operator, under governance, decides.
- **The table** — `migrations/0021_mcp_control.sql` (`control_signals`: source, directive, params JSON,
  status enum, detail, created_by_token, timestamps; index on status+created_at). The migration comment
  spells out the diode contract.
- **Role scopes** — `worker/opportunity-markets.ts:305-315`: the `kingmaker` bundle is exactly
  `'kingmaker:read control:signal'` — pointedly NO `crm:read`/`crm:write`. That absence is the enforcement.

## How to reapply it
1. **Migration** — add `control_signals` (id, `source` [who raised it], `directive`, `params` JSON,
   `status` CHECK IN (pending|applied|rejected|acknowledged) DEFAULT 'pending', `detail`,
   `created_by_token`, `created_at`, `resolved_at`) + an index on (status, created_at).
2. **Role + scope** — via crm-mcp-server, mint an oversight role whose scope bundle is JUST
   `oversight:read control:signal` (or your names). It must NOT include any CRM read/write scope. The
   handler enforces the read scope and rejects everything else.
3. **Sanitized snapshot** — one `SELECT` of aggregate subqueries (counts, sums, booleans). Return only
   numbers and derived state. NEVER select a name, email, phone, or message body into this path.
4. **Derived alerts** — from the same counts, emit `{code, severity, count, message}` items (e.g.
   `REPLIES_UNREAD`, `INTERESTED_PENDING`, `PAYMENTS_PENDING`, `CONTENT_STUCK`, `OUTREACH_IDLE`,
   `AUTOPILOT_OFF`). Codes + counts only — the message is a template over the count, not a record excerpt.
5. **The reverse channel** — one tool, scope-gated on `control:signal`, directive validated against a
   closed enum, that INSERTs a `pending` row. It can enqueue, nothing else. Stamp `created_by_token`.
6. **Operator resolution** — on the operator role/console, a tool to list `pending` signals and one to
   resolve them (`applied|rejected|acknowledged`), guarded by the operator's write scope and updated only
   `WHERE status='pending'` (so two resolvers can't double-apply). The operator remains the authority; the
   resolution records the governed decision. Applying a directive's EFFECT (e.g. actually pausing outreach)
   is a separate operator action — the diode only carries the request.

## Gotchas (from the code)
- **Enforcement is the ABSENCE of scope, not a filter.** The oversight token literally has no `crm:read`,
  so there is no code path — not even a bug — that lets it read a record. Don't "add a small read tool for
  convenience"; that hole defeats the diode. Keep the two scope bundles disjoint.
- **Aggregate-only means aggregate-only.** Every field the snapshot/alerts emit must be a count, sum, or
  boolean. The moment a name or message snippet leaks into an alert message, it's no longer PII-free. Build
  messages as `${count} unread replies`, never `"reply from <name>"`.
- **Directives are a closed enum.** Validate against the whitelist inside the tool even though the schema
  also constrains it — belt and suspenders. An unknown directive is rejected, not stored.
- **The overseer proposes; the operator disposes.** The diode never applies a directive's effect. The
  operator reads the queue and decides — and applying it is a separate, scoped, audited action. Don't wire
  `send_control_signal` to auto-execute anything.
- **`WHERE status='pending'` on resolve** is what makes resolution idempotent and prevents a
  re-resolve/race. Keep it.
- **Never money.** The reference oversight plane cannot touch funds by any path; the strongest directive it
  can raise is "pause outreach" / "set booking tier" / "focus" / "note." Keep money entirely off both the
  read and the directive whitelist.
- **`params` is bounded JSON** (stringify + slice to a cap) so a directive payload can't bloat the row;
  do the same.
