---
name: pipeline-autopilot
description: >-
  The cron-driven "runs itself" funnel for a Cloudflare Worker + D1 CRM: on the
  existing scheduled() tick it triages inbound campaign replies and, for the
  interested ones, prepares or sends a self-schedule booking link — with a
  per-stage autonomy tier (off | draft | auto), a DISABLED-by-default master
  switch, and an append-only heartbeat feed so it stays "silent unless broken."
  Use WHENEVER a client CRM should "run the follow-up by itself", "set the
  guardrails and watch it work", "auto-handle replies and book calls", "a
  supervised autopilot", or "make the pipeline self-running" — after replies and
  a scheduler already exist. It is the ORCHESTRATOR that wires stages onto cron;
  it COMPOSES rather than duplicates: reply-intent-triage (the classifier it
  calls), self-schedule-booking (the booking-link engine it invokes),
  graduated-autonomy-tiers (the per-stage off/draft/auto dial it honors),
  feature-activation-gate (the ships-dark master switch), governed-email-outreach
  (the send path + suppressions), append-only-audit-log (the heartbeat). Do NOT
  re-implement the classifier, the slot math, or the tier UI here — reference
  those skills and wire them. Guardrail: ships enabled=0, nothing here moves
  money, and every action writes a row to the heartbeat.
---
# pipeline-autopilot — the governed, self-running funnel

## What it is / when to use
A thin orchestration layer that turns a CRM that already *captures* replies and
*can* book meetings into one that does both on its own, on a schedule, under a
dial the operator controls. On every cron tick it: (1) triages new inbound
replies, (2) for interested leads, either prepares a booking link (draft) or
emails it (auto). It ships **disabled** — deploying it changes nothing until the
operator flips the master switch. It is the piece that sits *on top of* the
outreach, triage, and booking primitives; it owns the cadence and the audit
trail, not the mechanics.

**Composes with (do not duplicate):**
- **reply-intent-triage** — the dependency-free classifier + reply routing. The
  autopilot calls it; it does not re-classify.
- **self-schedule-booking** — the token page + slot math + Calendar/Meet event.
  The autopilot only decides *when* to send the link and *whether* to auto-send.
- **graduated-autonomy-tiers** — the reusable per-stage off/draft/auto dial and
  its admin shell. The autopilot stores tiers and branches on them.
- **feature-activation-gate** — the ships-dark master switch (here a plain
  `enabled` column; use the secret variant when it is a paid add-on).
- **governed-email-outreach** — the in-thread Gmail send + suppression list.
- **append-only-audit-log** — the `autopilot_actions` heartbeat feed.

## Reference implementation (ronininc — patterns only, no client data)
Start from `CRM_SKILLS_CATALOG.md`, then read:
- `worker/autopilot.ts`
  - **L16–37** `AutopilotSettings` type + `autopilotSettings()` default (ships `enabled:0`, per-stage tiers).
  - **L30–80** settings read/save (`saveAutopilotSettings`), tier + timezone + window validation.
  - **L82–109** `autopilotDashboard()` — settings + heartbeat actions + live pipeline counts + booking queue (booking token rewritten to a URL, never exposed raw).
  - **L379–405** `triageReplies()` — pulls untriaged replies, calls the classifier, writes intent + `autopilot_state`, suppresses opt-outs. (This is the reply-intent-triage skill's body; the autopilot just invokes it per tick.)
  - **L407–427** `runBookingStage(env, tier)` — the tiered stage: `auto` sends the link, `draft` ensures a token + logs a one-time `booking_link_ready` heartbeat (idempotent guard so it logs once).
  - **L429–434** `runAutopilot(env)` — the tick: **returns immediately if `!enabled`**, then runs triage (if `reply_triage==='auto'`) and the booking stage (if `auto_booking!=='off'`).
- `migrations/0020_autopilot.sql`
  - **L7–28** `autopilot_settings` (single `id='default'` row, `enabled` DEFAULT 0, tier columns with CHECK constraints).
  - **L30–43** `autopilot_actions` heartbeat table + indexes.
  - **L45–48** `campaign_replies` ALTERs (`intent`, `autopilot_state`, `handled_at`).
- `worker/index.ts`
  - **L20** import; **L199–204** cron wiring — `runAutopilot(env).catch(...)` inside the existing `scheduled()` `Promise.all`, **guarded** so a failure can't abort outreach/lead-gen.
- `worker/admin.ts` **L311–313** — `GET autopilot` (dashboard), `POST autopilot/settings`, `POST autopilot/booking/send` (one-click send, any tier).
- `worker/solomon-mcp.ts` **L148–166** — `set_autopilot` MCP tool (enable + tiers over the operator brain).
- `public/admin/admin.js` **L1502–1599** — the admin shell: master switch, tier selects, booking config, live counts, booking queue, and the heartbeat activity list.

## How to reapply it
**1. Migration.** Add `autopilot_settings` (one `default` row, `enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1))`, plus a tier column per stage `TEXT ... CHECK(x IN ('off','draft','auto'))`) and an append-only `autopilot_actions(id, stage, contact_id, ref_id, action, detail, tier, created_at)` with time + contact indexes. ALTER your replies table to carry `intent`, `autopilot_state`, `handled_at`. `INSERT OR IGNORE ... VALUES('default')`.

**2. Settings handler.** A reader that returns the row or a safe default, and a save handler that validates each tier against `{'off','draft','auto'}`, clamps the booking window/hours/interval, and validates the timezone with `new Intl.DateTimeFormat('en-US',{timeZone:tz})` inside try/catch. (See graduated-autonomy-tiers for the tier validator; feature-activation-gate for the enable pattern.)

**3. The tick.** Write `runAutopilot(env)` that:
```ts
export async function runAutopilot(env: Env): Promise<void> {
  const s = await autopilotSettings(env);
  if (!s.enabled) return;                       // ships dark; no-op until flipped
  if (s.reply_triage === 'auto') await triageReplies(env);   // reply-intent-triage
  if (s.auto_booking !== 'off') await runBookingStage(env, s.auto_booking);
}
```
`runBookingStage` selects a bounded batch (`LIMIT 5`) of interested, unsent meetings and, on `auto`, sends the booking link (self-schedule-booking); on `draft`, ensures a token and logs a one-time `booking_link_ready` heartbeat.

**4. Heartbeat.** Every branch writes one `autopilot_actions` row via a `logAction(stage, action, {contactId, refId, detail, tier})` helper — this is both the operator's "what did it do" feed and the sanitized status a Kingmaker/oversight diode pulls.

**5. Cron wiring.** Add `runAutopilot(env).catch(err => console.error('autopilot', err))` to the existing `scheduled()` `Promise.all([...])`. It MUST be `.catch`-guarded so an autopilot fault never aborts the other cron tasks.

**6. Routes + UI.** `GET /api/admin/autopilot` (dashboard), `POST /api/admin/autopilot/settings`, `POST /api/admin/autopilot/booking/send` (one-click, works in any tier). Admin shell = the graduated-autonomy-tiers `cs-shell`: master switch + a tier `<select>` per stage + live counts + the heartbeat list.

**7. Verticalize the stages.** The two stages here (triage → booking) are the reference set. Add stages the same way — one tier column, one branch in the tick, one heartbeat action — for followups, review/referral asks, dunning, etc. Money/irreversible stages get **no auto branch** (see Gotchas).

## Gotchas
- **Ships dark, and the master switch is checked FIRST.** `runAutopilot` returns before any work when `!enabled`. Deploy = zero behavior change until the operator explicitly turns it on (autonomy-release-gate doctrine). Never default `enabled` to 1.
- **Money never auto.** The reference autopilot moves no money by design — the only stages wired to an `auto` cron branch are triage (internal) and booking-link send (a message, reversible). Do not add an auto branch for a payment, a purchase, or any irreversible spend; leave those at `draft` or gate them behind graduated-autonomy-tiers' forbid-auto guard.
- **`draft` must be idempotent.** The draft branch logs `booking_link_ready` once per meeting — guard with `SELECT 1 FROM autopilot_actions WHERE ref_id=? AND action='booking_link_ready' LIMIT 1` before inserting, or every 5-minute tick re-logs the same "ready" line.
- **Bound every batch.** The tick runs on a 5-minute cron with a CPU budget shared with outreach/lead-gen. `LIMIT` each stage's query (booking uses 5, triage 25) so one tick stays cheap; the next tick picks up the rest.
- **Guard the cron entry.** Wrap `runAutopilot` in `.catch` inside the `Promise.all`; an unguarded throw takes down the whole scheduled batch.
- **Triage state, not just intent.** Store an `autopilot_state` (`pending|handled|skipped`) alongside `intent` so the booking stage only chases `interested` + `pending`, opt-outs go straight to `handled`, and auto-replies/bounces are `skipped` — otherwise the funnel re-processes the same rows.
- **Never expose the raw booking token in the dashboard.** Rewrite it to a `/schedule/?t=…` URL server-side and blank the token field (the dashboard does `booking_token: undefined`).
