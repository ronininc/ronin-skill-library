---
name: hands-free-daily-shift
description: >-
  A hands-free DAILY SHIFT for a self-running Worker+D1 business: a START/STOP pair that a person (or an
  assistant, or the cron) presses to put the whole machine to sleep at night and wake it in the morning —
  SAFELY. A STOP first SNAPSHOTS exactly what was running (active campaigns, armed daemons, the lead-gen
  schedule) and only then engages the kill switch; the next START restores EXACTLY that snapshot and nothing
  more — unlike a naive resume, it never silently arms daemons you had turned off or re-activates campaigns you
  paused. START also REFUSES to override a Stop it didn't make (the owner's kill switch is sacred; only the
  owner can lift it), and a cron presses the SAME buttons once per local day at the owner's hours with
  claim-based idempotency that catches up a missed tick. It ships with PII-light morning/evening reports built
  for a third-party assistant (counts, statuses, task titles with emails/phones/links REDACTED — never notes
  or messages) and a machine-health read. Use WHENEVER a build should "run itself during the day and rest at
  night", "start/stop everything with one button", "resume exactly how I left it", "let my assistant open and
  close the shop without breaking my settings", "a daily on/off schedule", "morning brief + evening wrap", or
  "don't let the start button override my kill switch". It COMPLEMENTS daemon-fleet-switchboard (shift
  snapshots which daemons were armed and restores them — it does not replace the switchboard or its kill
  switch) and graduated-autonomy-tiers (the shift is the time-of-day master on/off above the per-stage dials).
  Guardrail: START never overrides the owner's own Stop; a STOP preserves every queue; the schedule records a
  refused start once per day and does not retry it.
---

# Hands-Free Daily Shift (snapshot-restore START/STOP + cron + redacted reports)

## What it is / when to use
Two buttons and a schedule that open and close a self-running business for the day without ever corrupting its
configuration. STOP snapshots the live set (campaigns, armed daemons, lead-gen schedule), then stops; START
restores that exact snapshot — nothing more. The owner's own Stop can only be lifted by the owner. A cron
presses the same buttons, once per local day, at the owner's configured hours. Reports are PII-light so a
third-party assistant can read them.

Use it when a build should rest at night and wake in the morning, when an assistant must open/close the shop
without rewriting the operator's setup, or when a naive "stop all / start all" would silently arm things the
operator had deliberately turned off. Compose with `daemon-fleet-switchboard` (it snapshots/restores that
fleet) and `graduated-autonomy-tiers` (time-of-day master above the per-stage dials).

## Reference implementation (exact)
- STOP (snapshot THEN stop): `worker/station/shift.ts:70` `shiftStop()` — captures active campaigns, armed
  daemons, lead-gen enabled into `snapshot`, then `stopRevenueWorkflow`, logs it (`:81-84`).
- START (restore exactly the snapshot; refuse to override a foreign Stop): `worker/station/shift.ts:90`
  `shiftStart()` — owner-over-any-Stop branch `:97`, the kill-switch refusal `:103` (`refused_kill_switch`),
  the restore of the last shift Stop's snapshot `:109-124` (only known daemons, only paused→active campaigns).
- Hands-free cron: `worker/station/shift-schedule.ts:42` `shiftScheduleTick()` — `dueAction()` from the local
  hour `:34`, claim-once per `(day, action)` via `INSERT OR IGNORE` `:49`, re-claim a crashed press `:53`,
  catch up a missed tick (the 08:05 fires if 08:00 was skipped). Ships OFF (`shift_auto=0`, `:45`).
- PII-light reports: `redact()` masks email/phone/link `worker/station/shift.ts:30`; `dayReport('morning'|
  'evening')` `:195` records a morning plan and grades the evening against it; `activity()` counts tasks/runs/
  sends/replies/leads/money `:172`.
- Machine health (one rolled-up `overall`): `worker/station/shift.ts:129` `machineHealth()` — per-daemon last
  run, Google/sender state, the LEDGER CHAIN check (`verifyLedger`, `:152`), hub bound, review/blocked counts.
- DST-exact local-day windows: `worker/station/shift.ts:45` `localDay()`; next local hour
  `worker/station/intake-router.ts:24` `nextMorning()`.
- Wiring: owner route `worker/admin.ts:441` (`shiftScheduleRoute`); cron `worker/index.ts:435`
  (`station-shift-schedule`) + `:432` (`station-morning`); MCP for the assistant `worker/muse-mcp.ts`
  (`shift_start`/`shift_stop`/`machine_health`/`day_report`). Migrations `0152_station_shift.sql`,
  `0154_station_shift_schedule.sql`.

## How to reapply
1. **Model the shift on top of your existing kill switch**, don't replace it. Keep a `revenue_workflow_state`
   (or equivalent) with `{state, changed_by, changed_at}`. Add a `station_shift_log` (action, outcome, actor,
   `snapshot_json`, message, at) and, for the cron, a `station_shift_schedule_runs(day, action, at, outcome)`
   with a UNIQUE `(day, action)`.
2. **STOP = snapshot, then stop.** Read what is live (active campaigns, daemons whose settings are enabled, the
   lead-gen flag), store it as the snapshot, THEN engage the kill switch. Preserve every queue (you are pausing,
   not draining). Log the snapshot so START can read it back.
3. **THE INVARIANT — START restores exactly the snapshot, and never overrides a Stop it didn't make.** Tag the
   actor on every stop (`shift:<actor>`). On START: if the last Stop's `changed_by` does NOT start with
   `shift:`, refuse (`refused_kill_switch`) unless the caller is the owner. Otherwise re-arm ONLY the daemons in
   the snapshot (and only ones you recognize), flip ONLY `paused→active` for the snapshot's campaigns, restore
   the lead-gen flag, and mark the workflow active as `shift:<actor>`. "Nothing new was switched on."
4. **Cron presses the same buttons once per local day.** Compute the due action from the local hour
   (`>= stop_hour → stop`, `>= start_hour → start`). Claim `(day, action)` with `INSERT OR IGNORE`; only the
   claimer presses. Re-claim a press whose outcome is `error`; a completed press — INCLUDING a refused start —
   is final for the day (so a refused start is not retried into a fight with the owner). Ship it OFF.
5. **Reports are redacted by default.** Build them from CRM rows only; run every title/note through `redact()`
   (mask `email`/`phone`/`link`) and expose counts/statuses/titles — never message bodies. Record the morning
   plan; grade the evening against it (done vs rolled-over, reviews cleared, money received).

## Gotchas (from the code)
- **A naive daily stop/start silently rewrites your setup** — the raw kill switch's own Start arms EVERY safe
  daemon (even ones you turned off) and never resumes campaigns. The snapshot/restore exists precisely to avoid
  that (`shift.ts:8-9`). Don't shortcut it to "stop all / start all".
- **Local hours must be DST-exact.** Use `Intl.DateTimeFormat` round-tripping (`localDay`/`nextMorning`), not
  `getHours()` + a fixed offset, or the shift drifts an hour twice a year.
- **The cron must never throw.** `shiftScheduleTick` wraps everything and returns `null` off-slot; a press that
  crashes is recorded `error` and re-claimed next tick — a shift bug can't abort the rest of the cron.
- **Reports feed a third party** (e.g. Meta's assistant), so redaction is a privacy contract, not cosmetics —
  emails/phones/links out, notes/messages never included.
- **Machine health folds in the ledger chain check** (`verifyLedger`) — a broken money chain surfaces as an
  `error`-level health issue, which the readiness report then flags as `MACHINE_DOWN`.
- **Validated** by commit "feat(station): hands-free daily shift — the cron presses STOP at 18:00 and START at
  08:00 (#55)"; assert the refused-start-after-owner-Stop path and the once-per-day claim in a proof.
