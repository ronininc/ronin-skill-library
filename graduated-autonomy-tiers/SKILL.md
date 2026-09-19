---
name: graduated-autonomy-tiers
description: >-
  A reusable governance dial for any self-running CRM feature: every risky
  pipeline stage carries its OWN autonomy tier — off (ignore) | draft (prepare
  the action, wait for one human click) | auto (advance without a human) —
  honored by the cron, with money-moving and irreversible steps NEVER given an
  auto path. It ships as the shared admin "shell" (a master On/Off switch + a
  tier <select> per stage + a heartbeat feed) that sits behind every self-running
  vertical. Use WHENEVER a feature mixes safe-to-automate and must-stay-human
  steps and the operator needs a per-step dial: "let me choose what runs
  automatically", "draft vs auto", "prepare it but let me approve", "per-stage
  automation levels", "supervised automation", "how much autonomy per step". It
  is the graduated DELTA on top of feature-activation-gate: that skill is the
  binary ON/OFF (and the ships-dark master switch you still use); this adds the
  three-way per-stage tier layered inside the ON state. Do NOT rebuild the
  enable/paywall switch here — compose feature-activation-gate for that and
  append-only-audit-log for the heartbeat. Guardrail: money/irreversible stages
  are excluded from 'auto' by construction — a stage that moves money gets no
  auto branch in the cron and its validator forbids the tier.
---
# graduated-autonomy-tiers — the off/draft/auto dial per stage

## What it is / when to use
The pattern for giving each stage of an automated pipeline an independent
autonomy level, honored by the same cron that runs the feature. Three tiers:
- **off** — the cron ignores the stage entirely.
- **draft** — the cron *prepares* the action (creates the artifact, stages the
  record) and stops, leaving a one-click "send/approve" for a human.
- **auto** — the cron advances the stage on its own.

It is deliberately a thin delta: feature-activation-gate answers "is this feature
ON at all?" (and is the ships-dark/paywall switch); this answers "given it's ON,
how much of *each step* runs itself?" Use it behind any vertical that has both
safe steps (classify a reply, draft a doc) and steps you'd never fully automate
(send money, sign, submit a bid).

**Composes with (do not duplicate):**
- **feature-activation-gate** — the binary master switch (`enabled`, or the
  Worker-secret paywall). Check it FIRST; the tiers only matter once ON.
- **append-only-audit-log** — the heartbeat every tiered action writes.
- **pipeline-autopilot / any self-running vertical** — the consumers that store
  tiers and branch the cron on them.

## Reference implementation (ronininc — patterns only, no client data)
Two independent verticals use the identical dial — proof it's reusable:
- `worker/autopilot.ts`
  - **L16–21** `AutopilotSettings` — each stage is its own tier column (`reply_triage`, `auto_booking`, `followups`, `winbacks`).
  - **L24** `const TIERS = new Set(['off','draft','auto']);`
  - **L53–64** the tier VALIDATOR: `tier(value, allowDraft=true)` returns the value only if in `TIERS`, and rejects `'draft'` when `allowDraft` is false (used for a stage where "prepare and wait" is meaningless, e.g. internal triage → off|auto only). Note `reply_triage` is constrained to `off|auto` (no draft) because it sends nothing.
  - **L419–433** the cron SWITCH on tier inside `runBookingStage` / `runAutopilot`: `if (tier==='auto') send(); else if (tier==='draft') stageAndLogOnce();` and the stage runs at all only `if (auto_booking!=='off')`.
- `worker/acquisitions.ts`
  - **L18–21, 28–31** `ReSettings` — four stage tiers (`underwrite_tier`, `offer_tier`, `legal_tier`, `disposition_tier`) with defaults (underwrite `auto`, the rest `draft`).
  - **L33–45** `saveReSettings` — the same `['off','draft','auto'].includes(...)` validator.
  - **L168–184** `runAcquisitions` — cron advances a stage only when its tier is `auto`; **the money/irreversible steps (the actual offer/assignment) are simply never wired to an auto branch** — that's how "money never auto" is enforced here.
- `worker/solomon-mcp.ts` **L148–166** — `set_autopilot` exposes the tiers over the operator MCP (`reply_triage: enum('off','auto')`, `auto_booking: enum('off','draft','auto')`).
- `migrations/0020_autopilot.sql` **L12–24** and `migrations/0028_acquisitions.sql` **L18–21** — the tier columns as **DB-level CHECK constraints**: `TEXT NOT NULL DEFAULT 'draft' CHECK (x IN ('off','draft','auto'))` (and `off|auto` for send-nothing stages).
- `public/admin/admin.js` **L1505–1508** `apTierSelect(id, value, withDraft)` — the reusable tier `<select>` (drops `draft` when `withDraft` is false); **L1518–1542** the `cs-shell` card (master switch + tier selects + live counts + heartbeat).

## How to reapply it
**1. Schema.** One tier column per stage, guarded at the DB:
```sql
reply_triage  TEXT NOT NULL DEFAULT 'auto'  CHECK (reply_triage IN ('off','auto')),        -- send-nothing stage: no draft
auto_booking  TEXT NOT NULL DEFAULT 'draft' CHECK (auto_booking IN ('off','draft','auto')),
-- a money/irreversible stage: give it off|draft only, never 'auto'
settle_tier   TEXT NOT NULL DEFAULT 'off'   CHECK (settle_tier IN ('off','draft'))
```
Keep a single-row settings table (`id='default'`) with the feature's master `enabled` alongside.

**2. Validator.** Reject anything outside the allowed set, and encode the money rule as a per-stage `allowAuto`/`allowDraft` flag:
```ts
const TIERS = new Set(['off','draft','auto']);
const tier = (v, {allowDraft=true, allowAuto=true}={}) => {
  const x = String(v||'').trim();
  if (!TIERS.has(x)) return null;
  if (!allowDraft && x==='draft') return null;
  if (!allowAuto  && x==='auto')  return null;   // <- money/irreversible stages
  return x;
};
```

**3. Cron switch.** In the tick, gate each stage on its tier — and NEVER write an `auto` branch for a money/irreversible stage:
```ts
if (!s.enabled) return;                          // feature-activation-gate first
if (s.auto_booking !== 'off') await bookingStage(env, s.auto_booking); // off skips
// bookingStage: tier==='auto' -> send; tier==='draft' -> prepare + log once
if (s.settle_tier === 'draft') await stageSettlementForApproval(env);  // no 'auto' case exists
```
The `draft` branch must be **idempotent** (log/prepare once — guard on an existing audit row) so repeated ticks don't re-stage.

**4. UI shell.** Reuse one `tierSelect(id, value, withDraft)` helper and one card: a master On/Off switch, a labeled tier `<select>` per stage (pass `withDraft=false` / omit `auto` per the stage's rule), and a heartbeat list of recent actions. This "shell" is the standard face of every self-running vertical.

**5. Heartbeat.** Every tiered action logs `{stage, action, tier, detail}` — the tier-at-time-of-action is part of the audit so "why did this send?" is answerable.

## Gotchas
- **Money/irreversible never gets `auto` — enforce it, don't just intend it.** In the reference it's enforced by *omission* (the money stage has no auto cron branch). Harden it further: constrain the column CHECK to exclude `auto`, and add `allowAuto:false` in the validator so an API/MCP caller can't set it either. Don't rely on the UI alone to hide the option.
- **A stage that sends/acts on nothing shouldn't offer `draft`.** Internal classification is `off|auto` — a "prepare and wait" tier is meaningless there and just confuses the operator.
- **`draft` must be idempotent.** The prepare branch runs every tick; guard it (e.g. `SELECT 1 FROM audit WHERE ref_id=? AND action='prepared'`) or it re-creates the artifact each cron cycle.
- **Master switch is checked before any tier.** `if (!enabled) return;` — the tiers describe behavior *inside* the ON state; a disabled feature does nothing regardless of tiers.
- **This is a DELTA, not a new gate.** Don't re-implement enable/paywall/secret logic — that's feature-activation-gate. This skill only adds the three-way per-stage layer on top of it.
- **Validate at every entry point.** The tier can be set from the admin UI, an MCP tool, or a settings API — run the same validator in all of them; the DB CHECK is the last-resort backstop, not the only guard.
- **Defaults encode your risk posture.** Ship safe stages `auto` and everything touching money/legal/irreversible `draft` or `off`. The reference underwrites automatically but leaves offer/legal/disposition at `draft`.
