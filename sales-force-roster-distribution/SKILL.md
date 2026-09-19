---
name: sales-force-roster-distribution
description: >-
  A commission sales-force roster + automatic daily lead distribution for any Cloudflare Worker + D1
  CRM: a `reps` table (archetype / status / commission% / leads-per-day allotment), a public /join
  recruiting application (same-origin + honeypot, upsert-by-email), an admin roster editor, and a
  guarded round-robin cron that hands each ACTIVE rep the OLDEST unassigned leads up to that rep's
  daily cap — least-recently-fed rep first, conditional UPDATE so two ticks can never double-assign a
  lead, and a per-tick ceiling so it stays inside CPU limits. Daily throughput scales with how many reps
  are active × their allotment. Use WHENEVER a CRM runs a managed closer/rep operation on top of lead
  flow: "hand leads to my reps", "sales team roster", "commission reps", "round-robin lead assignment",
  "distribute leads daily", "recruiting page for closers", "rep allotments", "who owns this lead". This
  is the roster + distribution engine only. It COMPLEMENTS clearance-rbac + cf-identity: reps here are
  RECORDS, not logins — if reps must sign in and see only their own assigned leads, add clearance-rbac
  (a per-rep scoped seat) on top; do NOT rebuild auth here. Also complements crm-build-standard (the
  contacts/leads pipeline it feeds off). Guardrails: partner-track leads are excluded from the commission
  force; assignment is money-adjacent but never pays anyone — commission% is a stored attribute only.
---

# sales-force-roster-distribution — commission rep roster + daily lead hand-out

## What it is / when to use
The back-half of a managed sales operation: you recruit reps (SaaS reps, D2D reps going remote,
high-ticket closers, agencies), mark them **active**, and a five-minute cron automatically hands each
active rep a slice of the unassigned lead pool every day — up to each rep's `leads_per_day` allotment,
oldest-lead-first, fairest-rep-first. Total daily volume distributed = number of active reps × their
allotments, so onboarding more reps directly raises throughput. Reach for it whenever a CRM already
captures leads and the operator wants them routed to a human sales force instead of worked solo.

**Composes with (do not duplicate):**
- **crm-build-standard** — provides the `contacts` pipeline (`status='lead'`), `activities` feed, and
  `lead_type` track. This skill only adds the `reps` table, two columns on `contacts`, and the
  distributor. Build the CRM first.
- **clearance-rbac + cf-identity** — reps in this source are **rows, not seats**: there is no rep login,
  and the roster/distribution routes sit behind the operator's `team` clearance. If you want reps to log
  in and see only leads where `assigned_rep_id = me`, that is a clearance-rbac scoped seat + a
  `WHERE assigned_rep_id=?` filter — layer it on; this skill does not touch auth.
- **cf-abuse-guard** — the /join honeypot here is minimal; add its rate-limit/Turnstile for a hardened
  public recruiting form.

## Reference implementation (ronininc — open and confirm before lifting)
Catalog pointer: `CRM_SKILLS_CATALOG.md` → "sales-force-roster-distribution".
- **`worker/sales-team.ts` L1–151** — the whole engine:
  - `ARCHETYPES` / `STATUSES` / `STATUS_RANK` sets + `MAX_ASSIGN_PER_RUN = 200` (per-tick ceiling) — L13–16
  - `dayStart()` — UTC-midnight epoch seconds, the daily-cap boundary — L21–24
  - `salesTeamDashboard(env)` — roster + `counts` by status + `active_reps` + `recommended_daily_leads`
    (`SUM(leads_per_day) WHERE status='active'`) + `unassigned_pool` — L28–49
  - `saveRep(request, env)` — admin create/update; email is UNIQUE → **409** on duplicate insert — L53–82
  - `applyRep(request, env, url)` — public /join: same-origin gate, `website_hp` honeypot,
    `ON CONFLICT(email) DO UPDATE` upsert, `status='applied'`, `source='join-page'` — L85–106
  - `distributeLeads(env)` — the round-robin cron core — L114–151
- **`migrations/0024_sales_team.sql`** — `reps` table; `ALTER TABLE contacts ADD COLUMN assigned_rep_id`
  + `assigned_at` + index; and `campaigns.campaign_kind`/`archetype` (so one recruiting campaign per
  archetype reuses the outreach engine — outreach itself is governed-email-outreach, not this skill).
- **Routing:** `worker/admin.ts` **L314–316** — `GET sales-team`, `POST sales-team/rep`,
  `POST sales-team/distribute`; gated behind the `team` section in `SUB_SECTION` (`auth.ts` L185).
- **Public route + cron:** `worker/index.ts` **L59** (`/api/join` → `applyRep`) and **L207**
  (`distributeLeads(env)` inside the `scheduled` handler's `Promise.all`, `.catch`-guarded so it can
  never abort the other cron tasks). Import at **L21**.
- **UI:** `public/admin/admin.js` **L2026–2104** — `loadSalesTeam` (metrics + add-rep form + roster with
  inline status/commission/allotment edit + "Distribute leads now" button) and `stRepRow`.

## How to reapply it
1. **Migration (additive, live-D1 safe).** Copy `0024_sales_team.sql`: `CREATE TABLE IF NOT EXISTS reps`
   (id, name, email UNIQUE, phone, archetype default `'closer'`, status CHECK-list default `'applied'`,
   `commission_pct` 0–100, `leads_per_day` 0–200, source, notes, timestamps, `last_assigned_at`); then
   `ALTER TABLE contacts ADD COLUMN assigned_rep_id TEXT REFERENCES reps(id)` + `assigned_at INTEGER` +
   `idx_contacts_assigned_rep`. Rename the archetypes to your vertical's rep types if needed.
2. **Handlers.** Lift `sales-team.ts` wholesale. Keep the input clamps (`clean`, commission/allotment
   `Math.min/Math.max/Math.floor`, `validEmail` with CRLF rejection). Keep the dashboard's
   `recommended_daily_leads` = sum of active allotments — it's the operator's capacity readout.
3. **Wire the distributor into cron.** Add `distributeLeads(env).catch(...)` to your `scheduled`
   `Promise.all` (mirror index.ts:207) so a throw never aborts the other tasks. Also expose a manual
   `POST .../distribute` (returns `{assigned, reps_fed, pool_remaining}`) for a "distribute now" button.
4. **Public /join route.** Route `/api/join` → `applyRep`; it self-guards (same-origin + honeypot).
   Ship a static `/join/` page that POSTs `{name,email,phone,archetype,message,website_hp}`.
5. **Admin routes + gate.** Register the three routes behind your roster section's clearance (here:
   `team`). Add the section key to your RBAC `SUB_SECTION` map so scoped seats resolve correctly.
6. **UI.** Copy `loadSalesTeam`/`stRepRow` — metric strip, add-rep form, roster rows with inline
   status/commission/allotment `<select>`+number inputs and per-row Save, plus the Distribute button.

### The distribution algorithm (the reusable core — worker/sales-team.ts L114–151)
- Select active reps with `leads_per_day > 0`, **`ORDER BY COALESCE(last_assigned_at,0) ASC`** — the rep
  fed least recently goes first (round-robin fairness), `LIMIT 200`.
- Per rep: `done = COUNT(contacts WHERE assigned_rep_id=rep AND assigned_at>=dayStart())`;
  `remaining = min(leads_per_day - done, MAX_ASSIGN_PER_RUN - assigned)`. Skip if `<= 0` (cap already met).
- Pull the oldest unassigned client leads:
  `WHERE assigned_rep_id IS NULL AND status='lead' AND COALESCE(lead_type,'direct')<>'partner' ORDER BY created_at ASC LIMIT remaining`.
- **Guarded claim** for each: `UPDATE contacts SET assigned_rep_id=?,assigned_at=? WHERE id=? AND assigned_rep_id IS NULL`
  and only count it (and write the `assigned` activity, actor `'autopilot'`) when `meta.changes > 0`.
- After a rep's batch, `UPDATE reps SET last_assigned_at=?` so the next tick rotates to a different rep.

## Gotchas (from the code)
- **Double-assign safety is the conditional UPDATE, not a lock.** The `WHERE ... assigned_rep_id IS NULL`
  clause + the `meta.changes` check is what makes two overlapping cron ticks (or a manual "distribute
  now" racing the cron) safe — a lead already claimed by the other tick updates 0 rows and is skipped.
  Never replace it with a plain `UPDATE` or a read-then-write.
- **Daily caps reset at UTC midnight, not local.** `dayStart()` uses `Date.UTC(...)`. A rep in a western
  timezone sees the counter roll over mid-afternoon local. If per-local-day caps matter, pass the
  operator's timezone through an `Intl.DateTimeFormat` day-key (as `business-apps.ts` `localDayHour`
  does) instead of UTC.
- **Partner-track leads are deliberately excluded.** `COALESCE(lead_type,'direct')<>'partner'` keeps
  white-label/partner-sourced leads out of the commission force. Preserve that filter (and the
  `status='lead'` filter) or reps will get leads that were never theirs to close.
- **`MAX_ASSIGN_PER_RUN = 200` bounds each tick, not the day.** A large backlog drains over several ticks;
  that's intentional CPU-budget protection, not a bug. Raise it only if your cron budget allows.
- **Reps are records, not logins.** `commission_pct` is a stored attribute — nothing in this skill pays
  or notifies a rep. Payout, and any rep-facing view of "my leads", live outside it (clearance-rbac seat
  + a `assigned_rep_id=me` filter, plus your own payout ledger).
- **Email is UNIQUE.** `saveRep` returns 409 on a duplicate insert; `applyRep` upserts on the conflict
  (updates name/phone/archetype/notes, never downgrades an existing rep's status). Keep both behaviors —
  a re-application from /join must not reset an already-active rep to `applied`.
- **`recommended_daily_leads` is capacity, not a guarantee.** It's the sum of active allotments; actual
  assignment is capped by the real `unassigned_pool`. Surface both so the operator sees when demand
  (rep capacity) outstrips supply (leads) and needs more lead-gen.
