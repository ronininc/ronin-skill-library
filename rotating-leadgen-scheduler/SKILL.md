---
name: rotating-leadgen-scheduler
description: >-
  An auto-replenish scheduler that keeps a lead pipeline full on a cadence WITHOUT re-running the same
  market twice in a row: one stored schedule (timezone, daily local time, cadence 60/120/240/360/720/
  1440 min, a market-rotation list, vertical) plus a rotation cursor that advances across markets ×
  verticals every tick, and an at-most-once slot-claim UPDATE that guarantees exactly one launch per
  time slot even when cron ticks overlap. Use WHENEVER a lead-gen CRM should "generate leads on a
  schedule", "keep the pipeline topped up automatically", "rotate through cities/markets", "run lead
  gen every N hours", "daily lead replenishment", or "don't hammer the same directory". This is a thin
  DELTA that sits ON TOP of geo-directory-prospecting (it schedules and rotates that workflow — it does
  NOT re-implement discovery/enrichment/ranking) and on the governed-email-outreach continuous-send
  loop (the send side); it adds only the local-sunrise send-time gating, the market/vertical rotation,
  and the concurrency-safe slot claim. Do NOT rebuild the outreach campaign engine or the lead workflow
  here. Guardrails: one lead run at a time, the claim is conditional so overlapping cron ticks can't
  double-launch, and it degrades honestly (records last_error, never silently drops a slot).
---
# Rotating Lead-Gen Scheduler

## What it is / when to use
The "set it and it keeps the pipeline full" layer. The reference CRM already had continuous outreach
send + a one-shot lead-gen workflow; this adds the missing piece — a durable schedule that, on each
cron tick, decides whether a fresh lead run is *due*, picks the *next* market+vertical from a rotation
(so it doesn't re-scrape the identical OSM directory every hour), and launches exactly one run. Use it
whenever lead sourcing should run unattended across a metro's surrounding markets.

**Composes with:** `geo-directory-prospecting` (THE workflow it schedules — it calls
`launchLeadGeneration` with a rotated location/vertical), `governed-email-outreach` (the continuous
send loop that drains what gets queued — this only fills the queue), `crm-build-standard` (the campaign
the schedule targets). It is a **cadence + rotation + concurrency delta**, not a lead engine.

## Reference implementation (ronininc)
- `worker/lead-schedule.ts` (~161 lines) — confirmed read. Live and WIRED.
- `worker/index.ts:188` — `runScheduledLeadGeneration(env, controller.scheduledTime)` in the cron batch.
- `worker/admin.ts:390` — `POST outreach/schedule → saveLeadGenerationSchedule`.
- Schema: `migrations/0011_lead_generation_schedule.sql` + `migrations/0018_hourly_lead_replenishment.sql`
  (adds `cadence_minutes`, `market_rotation`, `rotation_cursor`, `last_run_slot`).

Key spans:
- **Single-row schedule** `0011` — `lead_generation_schedule` with `id='default'` CHECK (one row),
  `enabled`, `campaign_id`, `local_time`, `timezone`, `location`, `vertical`, `offer_profile`,
  `target_deal_cents`, `target_count`. `0018` adds `cadence_minutes` (CHECK IN
  60/120/240/360/720/1440), `market_rotation` (newline-joined list), `rotation_cursor`, `last_run_slot`.
- **Local-clock gating** `localClock()` L48-58 (Intl `en-CA` parts → `{day, minutes}` in the schedule's
  tz) and `runScheduledLeadGeneration()` L107-118: for daily cadence (1440) it fires only once the local
  minute-of-day passes `local_time` AND `last_run_day != today`; for sub-daily cadences it fires only
  when `scheduledSeconds - last_run_at >= cadence*60`.
- **Rotation math** L126-135: `slot` = the day (daily) or `floor(scheduledSeconds / (cadence*60))`
  (sub-daily); `rotationIndex = |rotation_cursor| % (markets*verticals)`; picks
  `markets[floor(idx/verticals) % markets]` × `verticals[idx % verticals]`. A `local-services` vertical
  fans out across `ROTATING_VERTICALS` (L34-37) so one schedule sweeps many verticals.
- **At-most-once slot claim** L136-142 — the load-bearing trick: a single
  `UPDATE ... SET last_run_slot=?, rotation_cursor=rotation_cursor+1, ... WHERE id='default' AND
  enabled=1 AND COALESCE(last_run_slot,'') <> ? AND (?=1440 OR last_run_at IS NULL OR last_run_at<=?)`.
  If `claim.meta.changes !== 1`, another overlapping tick already took this slot — return. This makes
  the whole thing safe under the every-5-minute cron without a lock.
- **Launch + honest failure** L143-160: builds `LeadGenerationParams` (deriving `leadType` from the
  rotated vertical) and calls `launchLeadGeneration`; on error writes `last_error` to the schedule row
  and rethrows. Also short-circuits if a run is already `queued`/`running` (L117-118) or the campaign
  was deleted (L121-125).
- **Save handler** `saveLeadGenerationSchedule()` L65-105: validates `local_time` (HH:MM), timezone
  (`Intl` round-trip), vertical allowlist, count 1-100, cadence in the set, deal $500-$1M; dedupes and
  caps the market list to 24; upserts the single row.

## How to reapply it
1. **Schema.** Apply `0011` then `0018` (or fold both into one migration): the single `default` row +
   the rotation columns. Requires a `campaigns` table and the geo-directory `lead_generation_runs`
   engine already present.
2. **Cron.** Add `runScheduledLeadGeneration(env, controller.scheduledTime)` to the Worker's
   `scheduled()` batch. It needs the cron to tick at least as often as the shortest cadence you offer
   (the reference ticks every 5 min; sub-daily cadences are multiples of that).
3. **Admin route + UI.** `POST outreach/schedule → saveLeadGenerationSchedule`. UI: an enable toggle,
   a timezone + daily-time picker, a cadence <select>, a textarea of markets (one per line), a vertical
   <select>, target count + deal. Load current state via `getLeadGenerationSchedule`.
4. **Wire to your source.** The launch call at L154 targets geo-directory-prospecting's
   `launchLeadGeneration`. If your source is different, swap that call but keep the claim + rotation
   logic intact.
5. **Seed a rotation.** `0018` shows the pattern: for a Phoenix campaign it pre-populates the 8
   surrounding cities and sets the cursor. Do the equivalent for the client's metro so the first ticks
   don't all hit one market.

## Gotchas (from the code)
- **The conditional claim is the concurrency guard — do not simplify it.** Reading the row, deciding,
  then writing in separate statements would let two overlapping 5-minute ticks both launch. The
  atomic `UPDATE ... WHERE last_run_slot <> ? AND (time condition)` + `changes === 1` check is what
  makes it exactly-once. Keep the `WHERE enabled=1` in the claim too (a mid-tick disable then wins).
- **Slot definition differs by cadence.** Daily uses the local calendar day; sub-daily uses a UTC-epoch
  bucket `floor(seconds / cadence*60)`. Mixing them (e.g. daily keyed on epoch) reintroduces
  double-fires around local midnight / DST. The tz-aware `localClock` only gates the daily case.
- **One run at a time is a hard dependency.** L117-118 refuses to launch if any run is `queued`/
  `running`; geo-directory-prospecting enforces the same at its own entry. A stuck run silently pauses
  the schedule — surface `lead_generation_runs.status` so a wedged run is visible.
- **Rotation size = markets × verticals.** With `vertical='local-services'` the effective vertical list
  is `ROTATING_VERTICALS` (9), so 8 markets × 9 = 72 distinct slots before repeating — that's the point
  (don't re-scrape the same directory). Any other vertical fixes the vertical axis to 1.
- **Market list is capped at 24 and deduped** (L78) — a huge paste is trimmed, not rejected.
- **Honest degrade:** a failed launch records `last_error` on the row (surface it in the UI); it does
  not silently skip. A deleted campaign disables sourcing with a clear message rather than erroring
  every tick.
