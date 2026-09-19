---
name: crm-workforce-productivity
description: >-
  The admin's real-time "who is working, who is not" dataset for ANY Cloudflare Worker + D1 CRM you build —
  activity-derived, never surveillance. It is grounded ONLY in real units of CRM WORK that already flow through
  the system (a lead added, a note/report filed, a message sent, a deal moved), weighted and rolled up per
  employee into live active/idle/offline status, a weighted score, a per-ACTIVE-hour intensity rate, and a
  today-vs-window trend — plus a team rollup. Its two sharp tricks: (1) the roster is MERGED into the events, so
  an employee who did NOTHING still surfaces (offline, 0) — that is the "not working" signal an events-only view
  would silently hide; (2) the scoring core is a PURE function over an event list (hermetically testable in Node)
  with thin durable I/O around it. Use WHENEVER a build needs "who's working right now / who's idle", "employee
  productivity dashboard", "staff activity leaderboard", "are my people actually doing the work", "real-time team
  status", "productivity score per rep", or "surface the people doing nothing" — for a CRM, dialer, sales floor,
  or ops team. It COMPLEMENTS crm-build-standard (the CRM whose work events it measures), governed-operator-console
  (the operator surface that hosts the panel), sales-force-roster-distribution (that DISTRIBUTES work; this MEASURES
  the output of it), append-only-audit-log (both append events — that is the trust trail, this is the productivity
  aggregation), and d1-tenancy-wall (every read is tenant-scoped). It is NOT surveillance and must never be built as
  keystroke/screen monitoring — "activity" is always a real CRM work unit, and every weight/threshold is tunable.
---

# CRM Workforce Productivity

## What it is / when to use / what it composes with
A drop-in engine + framework-neutral render panel that turns the work events ALREADY happening in a CRM into an
honest, real-time picture of who is on it and who is not. The doctrine is explicit and non-negotiable: it is
**activity-derived, not surveillance** — "activity" means a real unit of CRM output (a lead, a filed note, a sent
message, a moved deal), never keystrokes or screen capture (that is against the privacy doctrine *and* trivially
gameable). Reach for it whenever an admin/owner asks "is my team actually working?" on top of a CRM you built.

- Composes ON TOP of `crm-build-standard` — it reads the work events that CRM already emits.
- Renders inside `governed-operator-console` (or any dashboard); the panel core is shared by a React dashboard AND
  a vanilla client CRM from ONE file.
- Sits beside `sales-force-roster-distribution` (assigns/claims work) and `append-only-audit-log` (the audit trail):
  this is the *productivity read-model* over the same activity stream.
- Every read is tenant-scoped (`d1-tenancy-wall`): pass the bound tenant + that tenant's own accounts as the roster.

## Reference implementation — exact source
- **Engine (pure core + durable I/O):** `TSS: server/src/runtime/crm-workforce-productivity.ts`
  - `computeWorkforceProductivity(events, options)` — the PURE function (lines ~112–200): flat `ActivityEvent[]`
    → per-employee + team `WorkforceDataset`. No DB, no time-of-call ambiguity (`options.now` injectable).
  - `recordActivity(input)` — append one work event, best-effort (lines ~213–236).
  - `getWorkforceProductivity(tenantId, options)` — read the tenant's window + compute (lines ~239–246).
  - `DEFAULT_ACTIVITY_WEIGHTS` / `DEFAULT_PRESENCE_THRESHOLDS` (lines ~27–46) — the tunable defaults.
- **Route + roster wiring:** `TSS: server/src/routes/merchant.ts`
  - `GET /crm/workforce` (~line 208), role-gated (`requireRoles(['ROOT','OPERATOR'])`), `windowDays` clamped 1–90,
    roster = the tenant's own non-banned accounts mapped to `{employeeId, employeeName}`.
  - `recordActivity({...})` fired best-effort from the action attributor (~line 130) — never fails the real action.
- **Framework-neutral panel:** `TSS: app/src/dashboard/components/workforce-panel.ts`
  - `renderWorkforcePanelHTML(dataset)` — PURE (dataset → XSS-escaped HTML string), so it is testable in Node.
  - `mountWorkforcePanel(el, endpoint)` — DOM-only fetch→render loop with loading + honest-failure states. React
    wraps it via a ref; a vanilla client CRM includes the file verbatim and calls `mountWorkforcePanel`.
- **Proof:** `TSS: tests/crm-workforce-productivity/run.ts` and `tests/crm-workforce-panel/run.ts`.

## How to reapply
1. **Schema** — one append-only table:
   ```sql
   CREATE TABLE crm_activity_events (
     id TEXT PRIMARY KEY, tenantId TEXT NOT NULL, employeeId TEXT NOT NULL,
     employeeName TEXT NOT NULL, kind TEXT NOT NULL, weight REAL NOT NULL,
     occurredAt TEXT NOT NULL, metaJson TEXT NOT NULL DEFAULT '{}'
   );
   CREATE INDEX idx_crm_activity_tenant_time ON crm_activity_events(tenantId, occurredAt);
   ```
2. **Copy the pure core verbatim** — `computeWorkforceProductivity` + the two default tables + the types. It is
   schema-agnostic; do not modify the math.
3. **Emit events at the real work sites** — call `recordActivity({tenantId, employeeId, employeeName, kind})`
   wherever a unit of work completes (lead created, note filed, message sent, deal moved). Wrap it in try/catch:
   the productivity ledger must NEVER fail the underlying action.
4. **Route** — `GET /crm/workforce?windowDays=7`, role-gated to admin/operator. Build the roster from the tenant's
   own accounts and pass it so zero-activity members surface. Clamp `windowDays` (1–90).
5. **UI** — mount the panel (`mountWorkforcePanel(el, '/api/.../crm/workforce')`). It shows the working-first
   roster with status pill, weighted score, per-active-hour rate, trend arrow, and the team rollup.

## Gotchas — real pitfalls from the code
- **Roster merge is the whole point.** An events-only aggregation hides the person who did nothing — the exact
  signal an owner wants. Always seed `options.roster` with the full team; the engine merges it (offline, 0).
- **Window + future guard.** Events outside `[now − windowDays, now]` are dropped, including future-dated rows —
  a clock-skewed or spoofed `occurredAt` can't inflate a score.
- **`ratePerActiveHour` uses DISTINCT active-hour buckets**, not wall-clock — it measures intensity *while working*,
  so someone who did a burst in one hour isn't punished for the idle rest of the day.
- **`recordActivity` is best-effort and append-only.** No attribution (missing tenant/employee) → silently no-ops;
  never throw it into the request path.
- **Keep the pure core pure.** `computeWorkforceProductivity` takes `now` as an option — never call `Date.now()`
  inside it, or the tests (and reproducibility) break.
- **Not surveillance — enforce it in the weights.** `login` is a weak 0.5 presence signal; the heavy weights go to
  real output (`deal_updated: 4`, `note_filed: 3`). Never add a keystroke/screen-time "kind".
- **The panel HTML must escape.** `renderWorkforcePanelHTML` XSS-escapes employee names — keep that if you extend it.
