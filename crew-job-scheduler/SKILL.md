---
name: crew-job-scheduler
description: >-
  A field-crew scheduling / dispatch board for a Cloudflare Worker + D1 staff portal: dated jobs
  ("shifts") with title/location/start/end and encrypted site notes, many-to-many crew ASSIGNMENTS
  (who's on which job), a calendar-window read that returns a whole month's jobs + their assignees in a
  bounded number of queries, an "only my jobs" scope filter, and per-job crew PAYOUT rows visible to
  money roles only. The whole schedule is intentionally OPEN to every logged-in crew member (they cover
  for each other); money is the server-enforced exception. Use WHENEVER a staff/crew app needs "assign
  the crew to jobs", "a job/shift schedule", "who's working which job", "a dispatch board", "put people
  on a job", "field crew calendar", "my jobs today", or "schedule + assignments for a service team". It
  COMPLEMENTS cf-identity (crew ARE its users — assignees are logins, not records) and clearance-rbac
  (role rank gates create/edit and money visibility), and is DIFFERENT from sales-force-roster-distribution
  (commission sales REPS as records with round-robin LEAD hand-out) and services-delivery-lifecycle
  (post-deal project/task board). Pairs with service-invoice-ledger (a job carries the customer invoice)
  and field-encryption-at-rest (job notes). Guardrail: no foreign keys in D1 — validate every assignee
  against an ACTIVE user, cap crew-per-job, and NEVER let job notes hold anything about a person
  (they're readable by every crew member; personal matters belong in team-messaging-board).
---
# Crew Job Scheduler

## What it is / when to use / what it composes with
The scheduling + dispatch half of a crew portal: jobs, crew assignments, a fast calendar read, and
money-gated payouts. Assignees are **cf-identity** users; create/edit and money visibility ride
**clearance-rbac** role rank. It is NOT a sales-rep roster (**sales-force-roster-distribution**) nor a
delivery/project board (**services-delivery-lifecycle**) — it is field dispatch. The customer-billing
side of a job lives in **service-invoice-ledger**.

## Reference implementation — exact source
- **Schema** (`worker/migrations/0001_init.sql`): `shifts(id,title,location,starts_at,ends_at,notes,connector_id,external_uid,…)`,
  `shift_assignments(shift_id,user_id)` (composite PK), `installments(id,shift_id,due_date,amount_cents,label,status)`
  (crew payouts; `0015_payout_cents.sql` moved them from float dollars to integer cents),
  `connectors(…)` (a calendar-import registry).
- **Handlers** (`worker/index.js`): `listJobs` (`:964`), `createJob` (`:1522`), `validAssignees` (`:1506`),
  `listInstallments` (`:1010`), add-connector (`:2194`).
- **Roles** (`:44-47`): `canManage` (rank ≥ 20 / tech+) creates/edits jobs; `canMoney` (rank ≥ 30 / lead+)
  sees & sets payouts and invoice status.

## How to reapply
- **Calendar read done right (`listJobs`, `:964`):** take a `[from,to]` ISO window; select jobs where
  `COALESCE(ends_at,starts_at) >= from AND starts_at < to`; fetch ALL assignees for the window in ONE
  query and group in JS (a month view was 1+N round trips otherwise). Crucially, that assignee query
  uses a **repeated subquery on the same window, NOT `IN (?,?,…)` of the job ids** — D1 caps a statement
  at 100 bound params and a busy month exceeds 100 jobs. `scope='me'` filters to jobs the caller is on;
  decrypt `notes` per row; `delete invoice_status` unless `canMoney`.
- **Create in ONE batch (`createJob`, `:1522`):** `canManage` gate; encrypt notes up front (before the
  batch — `batch()` holds statements, not promises); one `env.DB.batch([...])` inserts the shift + every
  assignment + (money role only) bounded payout rows, so a mid-way failure is all-or-nothing instead of
  a shift with no crew. `validAssignees` de-dupes, caps at `MAX_ASSIGNEES`, and drops any id that isn't
  an active user. Payouts are integer cents, each bounded `0 ≤ cents ≤ MAX_CENTS` (a fat finger can't
  write a negative/Infinity/million-dollar payout).
- **Money is the server-enforced exception:** payouts never travel with a job in `listJobs`;
  `listInstallments` returns `[]` for anyone below `canMoney` before it even queries (`:1011`).
- **The open-schedule doctrine (`:949-963`):** the entire schedule (notes included) is readable by every
  login — decided after an audit found the server already behaved that way while the UI pretended
  otherwise. Consequence you MUST honor when writing a job: notes are for gate codes / site instructions,
  never for anything about a person.

## Gotchas
- **The `connectors` table + add/list is a REGISTRY only — no iCal sync ships.** `shifts.connector_id`/
  `external_uid` and add-connector (`:2194`, `kind='ical'`) exist, but the only real provider fetch loop
  in the Worker is Clover (`:2249`); there is NO iCal fetch/parse/upsert. To actually import an external
  calendar you must add: a `fetch(connector.url)` + ICS `VEVENT` parser, an idempotent
  `INSERT … ON CONFLICT(connector_id,external_uid)` upsert into `shifts`, a `last_synced_at`/`last_status`
  write, and a cron tick (the `triggers.crons` already fire every 10 min). Until then, treat connectors
  as inert metadata.
- No FKs → always validate assignee/mention ids against active users (`validAssignees`).
- Single-day jobs store `ends_at = NULL`; the window predicate `COALESCE(ends_at, starts_at)` handles it —
  keep the two predicates in `listJobs` byte-identical or the assignee join drifts from the job list.
