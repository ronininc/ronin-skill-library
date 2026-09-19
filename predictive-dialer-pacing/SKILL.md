---
name: predictive-dialer-pacing
description: >-
  The FTC-safe PREDICTIVE/parallel dialing math that decides HOW MANY lines to originate to keep agents busy
  without ever breaching the TSR abandonment ceiling (<3% rolling) — the one piece a compliance gate that
  forbids predictive dialing deliberately does NOT model. A pure, deterministic `computePacing` with a safety
  ladder (0 free agents -> dial 0; preview/power -> strict 1:1, no over-dial; predictive but under a minimum
  sample -> 1:1 warmup on an unproven answer rate; abandonment at/over ceiling -> THROTTLE back to 1:1; only
  proven-safe -> over-dial to ~free/answerRate, hard-capped at a max lines-per-agent), plus a `rollup` that
  turns recent call rows into answer/abandon rates, plus the ROLLING abandonment-ceiling check that sits inside
  the single dial gate. Use WHENEVER a build does outbound calling at volume and must pace it safely — "predictive
  dialer", "parallel dial / over-dial to fill seats", "how many lines to dial", "don't breach the 3% abandonment
  cap", "power vs predictive pacing", "FTC TSR abandonment", or an agent-pacing/wallboard. It COMPLEMENTS
  outbound-compliance-gate (which owns consent/DNC/calling-hours and explicitly refuses predictive dialing — THIS
  is the predictive delta layered beside it), pluggable-voice-carrier (which places the calls this counts), and
  local-presence-did-pool. It decides ORDER-agnostic VOLUME; attack-list-priority-queue decides WHICH leads.
---
# Predictive Dialer Pacing (FTC-safe over-dial math + abandonment ceiling)

## What it is / when to use / what it composes with
The highest-risk code in an outbound call platform, isolated into a pure function so it can be pinned by
adversarial unit tests: it over-dials to fill agent seats but **fails safe** the instant the rolling
abandonment rate approaches the FTC TSR ceiling. Reuse it any time you place calls faster than agents can
answer and must stay legal.

- **Composes with**: `outbound-compliance-gate` (consent/DNC/hours — that skill explicitly says "never
  predictive dialing"; this is the predictive engine that lives *next to* it), `pluggable-voice-carrier`
  (originates the recommended count), `local-presence-did-pool` (from-numbers), `attack-list-priority-queue`
  (chooses which leads; this chooses how many lines). Per-dial gating still runs for every single call.

## Reference implementation (exact source)
- Pacing algorithm + rollup: `/Users/robbiebrown/Projects/case-plug/src/pacer.js` (whole, 68 lines).
  - Constants `MIN_SAMPLE=20`, `MAX_LINES_PER_AGENT=3`: `pacer.js:16-17`.
  - Safety ladder in `computePacing`: `pacer.js:25-51` (0 agents `:32`, preview/power 1:1 `:37`, warmup `:40`,
    throttle at ceiling `:43`, proven-safe over-dial `free/answerRate` capped `:46-50`).
  - `rollup(rows)` → `{answerRate, abandonRate, sample}` from newest-first status window: `pacer.js:54-68`.
- The rolling abandonment-ceiling GATE (inside the single dial gate): `/Users/robbiebrown/Projects/case-plug/src/dialer.js:66-75`
  (`SUM(abandoned)/SUM(connected) >= ceiling` over the last 200 calls, enforced once `conn >= 20`).
- Wired recommendation endpoint (`GET /call/pacing`, feeds the wallboard): `src/calls.js:160-176`.
- Schema: `campaigns.dialing_mode CHECK IN ('preview','power','predictive')` + `abandon_ceiling REAL DEFAULT 0.03`
  `schema.sql:222-228`; `calls.status` includes `abandoned`/`machine` `schema.sql:233`.

## How to reapply
1. **Keep the pacer PURE** (`computePacing(inputs) -> {dial, throttled, reason}`) and deterministic — no DB, no
   clock — so unit tests can pin every rung. Do the DB rollup separately (`rollup(rows)`).
2. **Implement the ladder in order** (each rung caps risk before the next can loosen it): no free agents → 0;
   preview/power → `free - inFlight` (never over-dial); predictive & `sample < MIN_SAMPLE` → 1:1 warmup;
   predictive & `abandonRate >= ceiling` → throttle to 1:1 (`throttled:true`); else over-dial
   `min(free/answerRate, free*MAX_LINES_PER_AGENT) - inFlight`.
3. **Clamp the answer rate** to a sane floor (e.g. `[0.05, 1]`, default 0.3) so a near-zero rate can't demand an
   absurd line count; the hard `MAX_LINES_PER_AGENT` cap is the backstop whatever the math says.
4. **Enforce the ceiling twice**: as a THROTTLE input to the pacer AND as a per-dial refusal in the compliance
   gate (so even a mis-paced burst can't push a single extra call once the rolling rate is breached). Only start
   enforcing once the sample is meaningful (`conn >= 20`) to avoid tripping on the first abandoned call.
5. **Roll over a bounded window** (last ~200 calls) so the rate reflects "now", not all-time.

## Gotchas (from the code)
- **The pacer only RECOMMENDS — nothing here auto-originates the recommended `plan.dial` lines.** `GET /call/pacing`
  returns the number for the wallboard/dial-mode UI to act on; there is no cron/loop that places them. **Binding
  if you want autonomous pacing**: a scheduled/loop worker that reads the plan, then calls the carrier `placeCall`
  `plan.dial` times, each still passing through the single dial gate. Keep money/irreversible autonomy gated.
- **Fail safe, not fair.** When in doubt (thin sample, unknown answer rate, at-ceiling) it drops to 1:1 — under-
  dialing wastes agent time but never creates an illegal abandoned call. That asymmetry is intentional.
- **`preview`/`power` must NEVER over-dial** — 1 live call per free agent, zero abandonment risk. Only `predictive`
  with proven-safe data over-dials.
- **`inFlight` prevents double-counting** — subtract calls already queued/ringing or you'll stack lines every poll.
- **Abandonment denominator is CONNECTED calls** (`answered|machine|completed|abandoned`), not all dials — using
  total dials understates the rate and slips past the ceiling.
