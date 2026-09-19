# Workforce productivity — real-time "who's working, who's not" (optional)

Gives the CRM **admin** a live dataset of employee productivity, grounded ONLY in real CRM work that
already flows through the system. Same feature Solomon's own dashboard ships; this is the per-client-CRM
port (its own D1, its own Worker endpoint, the SAME shared view core).

## Doctrine (non-negotiable — do not drift into surveillance)
- Productivity = real **work output** already in the CRM: a lead added, a note filed, a message sent,
  a deal/stage moved. **Never** keystrokes, screen capture, or idle-time tracking — that's gameable and
  a privacy violation. "Activity" is always a real unit of CRM work.
- **Roster ∪ events:** pass the staff roster so an employee who did nothing still shows (offline, 0) —
  the "who's NOT working" signal. Absence of activity is the point.
- **Rate = weighted work ÷ distinct active hours**, not clock hours (intensity while working; fair to
  part-timers; hard to game).
- Live status by recency of the last work event: active ≤15 min, idle ≤120 min, else offline (tunable).
- The `crm_activity_events` ledger is **append-only** — never edit/delete, so the record can't be quietly rewritten.

## Files to copy (build once — these mirror TSS's canonical source)
- `references/workforce-compute.mjs` → `worker/lib/workforce-compute.mjs` (pure engine).
- `references/workforce-panel.mjs`   → `public/workforce-panel.mjs` (framework-neutral view; same core as TSS `workforce-panel.ts`).

## 1. D1 schema (also in `starter-schema.sql`)
```sql
CREATE TABLE IF NOT EXISTS crm_activity_events (
  id TEXT PRIMARY KEY,
  employeeId TEXT NOT NULL,
  employeeName TEXT NOT NULL,
  kind TEXT NOT NULL,            -- lead_added | note_filed | note_dispatched | message_sent | deal_updated | queue_action | login | custom
  weight REAL NOT NULL DEFAULT 1,
  occurredAt TEXT NOT NULL,      -- ISO
  metaJson TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_crm_activity_time ON crm_activity_events(occurredAt);
CREATE INDEX IF NOT EXISTS idx_crm_activity_emp  ON crm_activity_events(employeeId, occurredAt);
```
Note: a client CRM is single-tenant (one D1 per site), so there is NO tenantId column — the database IS
the tenant boundary. (TSS's server table has tenantId because it is multi-tenant.)

## 2. Log activity on the CRM's write paths (best-effort — never fail the real action)
```js
import { DEFAULT_ACTIVITY_WEIGHTS } from './workforce-compute.mjs';
export async function recordActivity(env, { employeeId, employeeName, kind, weight, occurredAt, meta }) {
  if (!employeeId) return;
  try {
    await env.DB.prepare(
      `INSERT INTO crm_activity_events (id, employeeId, employeeName, kind, weight, occurredAt, metaJson)
       VALUES (?,?,?,?,?,?,?)`
    ).bind(
      crypto.randomUUID(), employeeId, employeeName || employeeId, kind,
      Number.isFinite(weight) ? weight : (DEFAULT_ACTIVITY_WEIGHTS[kind] ?? 1),
      occurredAt || new Date().toISOString(), JSON.stringify(meta || {}),
    ).run();
  } catch { /* best-effort */ }
}
```
Call it from the handlers you already have, attributed to the signed-in user (from `cf-identity`'s session):
`recordActivity(env, { employeeId: session.user.id, employeeName: session.user.name, kind: 'note_filed', meta:{ leadId } })`
— on lead create (`lead_added`), note/activity add (`note_filed`), message send (`message_sent`), deal/stage change (`deal_updated`), etc.

## 3. Admin endpoint — GET /api/workforce  (gate to admin via cf-identity)
```js
import { computeWorkforceProductivity } from './workforce-compute.mjs';
export async function handleWorkforce(request, env /*, session (require admin) */) {
  const url = new URL(request.url);
  const windowDays = Math.min(90, Math.max(1, parseInt(url.searchParams.get('windowDays') || '7', 10) || 7));
  const since = new Date(Date.now() - windowDays * 86400000).toISOString();
  const events = (await env.DB.prepare(
    `SELECT employeeId, employeeName, kind, weight, occurredAt FROM crm_activity_events WHERE occurredAt >= ? ORDER BY occurredAt ASC`
  ).bind(since).all()).results || [];
  // Roster from your users table (adjust column names to cf-identity's schema):
  const roster = ((await env.DB.prepare(
    `SELECT id AS employeeId, COALESCE(displayName, username, id) AS employeeName FROM users WHERE role IN ('admin','staff','worker')`
  ).all()).results || []);
  const data = computeWorkforceProductivity(events, { windowDays, roster });
  return Response.json({ ok: true, data });
}
```

## 4. Mount the panel in the admin page
```html
<div id="workforce"></div>
<script type="module">
  import { mountWorkforcePanel } from '/workforce-panel.mjs';
  mountWorkforcePanel(document.getElementById('workforce'), { endpoint: '/api/workforce', windowDays: 7 });
</script>
```

## Free-tier note
The ledger is a few small rows per action — negligible against D1 free limits. The compute is pure JS in
the Worker (zero neurons, zero egress). Only turn it on for CRMs whose owner manages a team.
