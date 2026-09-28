---
name: daemon-fleet-switchboard
description: >-
  The ONE operator panel that registers every background daemon on a Cloudflare Worker + D1 app's cron,
  shows whether each is on and when it last ran, and arms them from a single control — because a fleet of
  cron daemons that each ship OFF behind their own `*_settings.enabled` flag makes the machine feel dead
  ("nothing is happening") with no one place to see or fix it. Each daemon is one row in a registry with a
  SAFETY TIER (safe = internal work only | sends = produces outbound comms | publishes = posts public
  content | always-on/connector-gated), a uniform singleton-settings toggle, a resilient run-recorder, an
  "arm all safe" that turns on internal daemons ONLY, and a shared kill-switch. Use WHENEVER a build has
  grown several scheduled jobs and the operator needs to command them: "one switchboard for all my
  background jobs", "why isn't anything running", "turn on the automation", "arm everything safe", "a panel
  of every daemon with last-run + on/off", "kill all automation now", or "everything should be a toggle."
  It COMPLEMENTS pipeline-autopilot and any single self-running vertical (each becomes ONE daemon in this
  registry, not a bespoke panel), graduated-autonomy-tiers (the per-STAGE dial inside one daemon; this is
  the per-DAEMON fleet layer above it), and feature-activation-gate (the ships-dark switch a daemon still
  honors). Guardrails: money/outbound/publish daemons are NEVER turned on by "arm all safe" — only the
  'safe' tier is; the run-recorder swallows every daemon error so one crash never kills the cron tick.
---
# Daemon Fleet Switchboard — see, arm, and kill every background daemon from one place

## What it is / when to use / what it composes with
A single-file registry + control surface for the WHOLE fleet of cron daemons in a Worker+D1 app. Any app
that has quietly accumulated scheduled jobs (a geocoder, an enricher, an outreach cycle, a content
publisher, a pipeline planner, a backup…) — each with its own on/off flag that ships OFF — needs this: one
place that lists every daemon, its live enabled state, its last run + status, and one-button arming that
respects a safety tier so internal work can be switched on in bulk while anything that spends money, sends
outbound, or publishes stays deliberate.

**Composes with:** **pipeline-autopilot** / any self-running vertical (each is registered here as a single
daemon row rather than owning its own switchboard), **graduated-autonomy-tiers** (that dials off/draft/auto
WITHIN one daemon's stages — orthogonal to this fleet-level on/off), **feature-activation-gate** (a daemon
can still be gated dark by a secret/paywall — check that first), and an external-brain "run the day" caller
(share `armSafeDaemons` / `disarmControllableDaemons` so the AI and the admin button flip the exact same
flags).

## Reference implementation — EXACT source
`ronininc-site/worker/daemons.ts` (a Cloudflare Worker + D1 CRM):
- The tier type + daemon record shape — `worker/daemons.ts:27` (`type Tier`), `:28-37` (`type Daemon`).
- **The fleet registry** (the heart): `worker/daemons.ts:40-57` — one object per daemon with `table` (its
  singleton `*_settings` table, or `null` for always-on/connector-gated), `tier`, and an operator-facing
  `note`.
- Uniform singleton toggle over each daemon's own settings table — `worker/daemons.ts:62-73`
  (`readEnabled` / `writeEnabled`; `INSERT … ON CONFLICT(id) DO NOTHING` seeds the `id='default'` row).
- **Resilient run-recorder** — `worker/daemons.ts:76-90` (`recordDaemonRun` upserts one `daemon_runs` row
  per daemon; `track(env,id,fn)` runs a daemon, records ok/error, and NEVER rejects).
- Status endpoint `GET /api/admin/autopilot/status` — `worker/daemons.ts:93-116` (joins the registry with
  live `enabled` + last-run; computes `safe_armable`).
- Toggle `POST /api/admin/autopilot/toggle {id,on}` — `worker/daemons.ts:119-128`.
- **Arm-all-safe** `POST /api/admin/autopilot/arm-safe` + shared `armSafeDaemons` — `worker/daemons.ts:131-144`
  (turns on ONLY `tier==='safe'` controllable daemons).
- Shared kill-switch `disarmControllableDaemons` — `worker/daemons.ts:149-155`.
- Wiring: routes/imports in `worker/admin.ts:3`; the cron uses `track` (`worker/index.ts:22`, e.g.
  `worker/index.ts:370`); the "run the day" path + kill-switch reuse the shared helpers
  (`worker/run-day.ts:18`, `worker/revenue-control.ts:7`).

## How to reapply — the wiring + THE INVARIANT
1. Declare the registry: one row per scheduled job — `{ id, label, category, table, tier, note }`. `table`
   is that daemon's singleton settings table (holding an `enabled` 0/1 in row `id='default'`), or `null`
   for a daemon that is always-on / gated by a connector rather than a simple flag.
2. Wrap EVERY cron invocation in `track(env, id, fn)` so each run is recorded and one thrown daemon can't
   abort the tick. Each daemon's own body still checks its `*_settings.enabled` (or its connector) — the
   switchboard writes the flag, it doesn't re-implement the guard.
3. Expose status (registry ⨝ `daemon_runs` ⨝ live `enabled`), a per-daemon toggle, an arm-all-safe, and a
   disarm-all. Share `armSafeDaemons` / `disarmControllableDaemons` between the admin buttons and any AI
   "run/stop the day" caller so both flip the identical flags.
4. **THE INVARIANT:** "arm all safe" arms the `'safe'` tier ONLY. A daemon that sends outbound comms,
   publishes public content, or moves money is `'sends'` / `'publishes'` (or connector-gated) and is armed
   one at a time, deliberately — never in bulk. Money is never auto.

## Gotchas — real pitfalls from the code + how it's validated
- **A missing/never-migrated settings table must read as "off/unknown", not throw.** `readEnabled` catches
  and returns `null` (`worker/daemons.ts:66`), and `autopilotStatus` tolerates a missing `daemon_runs`
  table (`worker/daemons.ts:99`) — the panel renders on a half-migrated DB instead of 500ing.
- **Seed the singleton before flipping it.** `writeEnabled` does `INSERT … ON CONFLICT(id) DO NOTHING`
  then `UPDATE` (`worker/daemons.ts:71-72`) — a daemon that has never been saved still toggles.
- **`table` is interpolated into SQL** (`SELECT enabled FROM ${table}`) — it is safe ONLY because every
  value comes from the hard-coded registry, never user input. Keep it that way; never let a request pick
  the table name.
- **Always-on daemons are shown but not toggled here.** `autopilotToggle` refuses a `table:null` daemon
  (`worker/daemons.ts:124`); those are stopped at their own source (connector/revenue-control), so the
  panel stays honest about what it can and can't switch.
- Validated by the operator seeing the fleet light up: after "arm all safe", the `safe` daemons report
  `enabled:true` and, on the next 5-minute tick, a fresh `last_run_at` — the proof the machine is alive.
