---
name: station-engine-floor
description: >-
  The ENGINE FLOOR that sits one layer ABOVE a daemon switchboard: instead of toggling background jobs,
  it moves work items along named BELTS where each ordered stage is worked by exactly ONE hired "desk"
  that must hold the capability "gear" that stage declares, and every gated stage HALTS the item until the
  operator approves the EXACT bytes (a sha256 of recipient + latest artifacts) — an edit voids any prior
  approval, and re-reading the new hash is required. One registry of belts (definitions in code, runtime
  state in D1), one advance() that runs stage-by-stage and stops cleanly at a gate / wait / block / terminal,
  a per-belt kill switch, an operator-armed capped STANDING OK for inbound-only belts, an advisory
  pre-screen on every review card, and a hibernating-WebSocket event hub so pages react to runs (events,
  never polling). Use WHENEVER a build needs "one money bot per engine", "a work conveyor with human
  approval gates", "pipelines where each step is done by a worker that needs a permission", "approve the
  exact thing before it goes out", "a station/floor of self-running belts I can watch live", or to turn a
  pile of cron daemons into governed, inspectable production lines. It COMPLEMENTS daemon-fleet-switchboard
  (each belt can BE a daemon; the floor is the orchestration above it), pipeline-autopilot /
  graduated-autonomy-tiers (per-stage autonomy dials — the gate here is the hardest tier), and
  confirmed-inputs-decision-gate (that gates a NUMBER; this gates the OUTGOING BYTES). Guardrail: the ONLY
  way past a gate is an exact-hash approval or an operator-armed standing OK within its daily cap for an
  inbound item — never an agent, never auto; money/sends still ride their own governed senders.
---

# Station Engine Floor (belt → desk → gear → exact-bytes gate)

## What it is / when to use
A general work-conveyor orchestration. A **belt** is an ordered list of **stages**; each stage is worked by
one hired **desk** that must hold the **gear** (capability token) the stage declares; a `gate: true` stage
stops the item until the operator approves the exact bytes. This is the layer *above* a daemon switchboard:
a daemon flips a job on/off, but a belt is a governed production line whose every step is typed, hired,
capability-checked, logged as a run, and (where it matters) human-gated.

Reach for it when a build has outgrown "a pile of cron jobs" and needs inspectable, gated production lines
with live status — a sales pipeline, a content/asset factory, an onboarding/provisioning flow. Compose it
with `daemon-fleet-switchboard` (the belt's tick can be one daemon), `pipeline-autopilot` /
`graduated-autonomy-tiers` (autonomy dials), and `confirmed-inputs-decision-gate` (gate a computed number).

## Reference implementation (exact)
- Belt/stage/gear/role registry (definitions in code, typed): `worker/station/belts.ts:9` (gear),
  `:47` (ROLES recruitment templates), `:62` (the `BELTS` array), `:231` (`beltById`/`stageIndex`).
- The engine loop: `worker/station/engine.ts:54` `advance()` — walks stages, stops at gate/wait/block/terminal.
- The exact-bytes gate math: `worker/station/store.ts:92` `gateHash()` (sha256 of `{item, to, latest artifact shas}`);
  the gate branch `worker/station/engine.ts:70`; approval binding `worker/station/engine.ts:179` (reject if
  `input.hash !== current || item.gate_hash !== current`); an edit voids approval `worker/station/engine.ts:174`.
- Standing OK (inbound-only, operator-armed, daily-capped): `worker/station/engine.ts:79` + the daily counter
  `worker/station/engine.ts:46` (`standingUsedToday`); `standingAllowed` per belt `worker/station/belts.ts:95,106`.
- Desk/gear resolution + default seeding: `worker/station/store.ts:125` `deskFor()` (first hired desk holding
  ALL needed gear, else first hired so the block can name the missing gear), `:107` `ensureDefaultDesks()`.
- Runs + artifacts + item state: `worker/station/store.ts:133` `startRun`/`:142` `finishRun`,
  `:76` `saveArtifact`, item states `worker/station/store.ts:12`, `TERMINAL` `:43`.
- Advisory pre-screen on each review card (does the draft overclaim vs the facts?):
  `worker/station/prescreen.ts:36` `ruleFlags()` (pure grounding check — unbacked amounts/percents/ratings/
  counts/phones/links/promises/website claims), `:65` `prescreenGate()` (one per `(item, gate_hash)`, NEVER
  approves/blocks/edits), called from the gate at `worker/station/engine.ts:88`.
- Event hub (hibernating WebSocket DO): `worker/station/hub.ts:29` `publish()` (never throws; backs off when
  nobody is watching), `worker/station/hub-do.ts:10` `StationHub` (the only file importing `cloudflare:workers`).
- Wiring: route `worker/admin.ts:444` (`station` is owner-only, deliberately absent from `SUB_SECTION`);
  DO + Workflow exported `worker/index.ts:87,88`; migration `migrations/0150_ronin_station.sql`.
- MCP surface (external brain): `worker/station/mcp.ts:29` `registerStationTools` — read belts/results,
  propose a run, start after go-ahead, relay an exact-hash approval.

## How to reapply
1. **Define belts in code, keep state in D1.** `StageDef {key,label,role,gear[],gate?,operatorOnly?,implemented}`
   and `BeltDef {id,stages[],standingAllowed,needs[],hardLines[],status}` (`belts.ts:13,24`). Runtime rows:
   `station_items`, `station_desks`, `station_runs`, `station_reviews`, `station_belt_settings`,
   `station_artifacts` (migration 0150). `status: 'live' | 'partial' | 'needs_connector'` tells the truth —
   an unbuilt stage sets `implemented:false` and `advance()` blocks with the belt's `needs`.
2. **Write stage handlers, register per belt.** A `StageHandler` returns `{kind:'next'|'wait'|'blocked'|'done'}`
   (`engine.ts:25`); `HANDLERS[beltId][stageKey]` dispatches (`engine.ts:32`). `advance()` saves any artifact,
   finishes the run, patches the item to the next stage, and loops (bounded to 14 steps, `engine.ts:57`).
3. **THE INVARIANT — the gate binds the exact bytes.** A gate computes `gateHash(item)` over the recipient and
   the sha256 of the latest artifact of each kind. Approval is accepted only if the submitted hash equals the
   current hash equals `item.gate_hash`. Any edit (a `revise`) re-saves the artifact, recomputes the hash, and
   NULLs `approved_hash/by/at` — "the work changed since you read it; re-read and approve its hash"
   (`engine.ts:179`). The only non-interactive bypass is a standing OK: inbound item + `standingAllowed` belt +
   operator-armed + under `standing_daily_cap` that day; it writes a `'standing'` review receipt bound to the
   same hash. Never an agent, never auto.
4. **Each stage needs a hired desk holding its gear.** No desk → block ("hire a <role> in the Recruitment Bay");
   wrong gear → block naming the missing gear. Gear is a ceiling the stage still has to match exactly
   (`store.ts:125`). This is how a capability (send mail, read payments, build pages) is granted per-stage.
5. **Publish an event around every mutation and run** (`hub.publish`), authenticate the WebSocket upgrade in the
   Worker before forwarding to the DO, and keep the DO in its own file so publish-only modules stay bundle-safe.

## Gotchas (from the code)
- **Bundle hygiene is load-bearing.** The DO (`hub-do.ts`) and the pack Workflow (`pack-maker.ts`) are the only
  files importing `cloudflare:workers`; `hub.ts`/`engine.ts` hooks are split out so modules that merely publish
  (outreach, commerce) don't drag the whole belt graph + the workers runtime into their bundles
  (`engine.ts:204`, `hub.ts:7`). Keep that seam or Node-side proofs and the Stripe/commerce bundles break.
- **`advance()` re-reads the item every iteration** and re-checks the kill switch and gear each loop, so a belt
  paused or a desk retired mid-run stops cleanly (`engine.ts:57-64`). The 14-step guard prevents a runaway.
- **A failed handler fails the item with the message** and finishes the run `failed` (`engine.ts:107`); a `wait`
  (e.g. waiting on payment) parks without advancing; a `blocked` writes a human-readable reason.
- **The pre-screen is advisory only** — it must never gate. It is wrapped so it can't throw, is idempotent per
  `(item, gate_hash)`, and only annotates the review card (`prescreen.ts:65`). The gate stays the operator's hash.
- **Validated** by an E2E proof that drives a belt stage-by-stage (commit "E2E proof: CRM-factory belt end to
  end (32/32)", and "lead-gen → outreach 15/15"). Reuse `d1-proof-harness` to assert each stop state.
- Do not confuse this with `graduated-autonomy-tiers` (a per-stage off/draft/auto dial): the gate here is the
  hardest tier — exact-bytes human approval — and money/sends additionally ride their own governed senders.
