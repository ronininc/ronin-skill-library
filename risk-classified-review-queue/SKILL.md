---
name: risk-classified-review-queue
description: >-
  A governed intake→build→release lifecycle for any request that a control plane must vet before acting:
  classify each request GREEN/YELLOW/RED from a checklist of impact flags (touches governance/audit, exposes
  IP or internal architecture, affects privacy / cross-tenant data / revenue / liability, requires
  fabrication), route it into a lane (autonomous | review | founder/owner table), project a SEPARATE
  public-facing status vs internal status, gate whether even a public ESTIMATE is allowed, and move it
  through an explicit "nothing teleports" transition state-machine where each stage requires the prior
  stage's artifact (intent→objective→queued→capability→building→validating→registered→ready→released). RED
  can never proceed without owner/founder review; money/irreversible/high-impact work is escalated by
  construction. Use WHENEVER a build needs "vet requests before we act on them", "auto-approve the safe ones,
  escalate the risky ones", "a change/feature-request approval pipeline", "owner review gate", "risk-tier the
  intake", "don't let anything skip a stage", "show the requester a safe public status while we work
  internally", or "a governed build queue". It COMPLEMENTS graduated-autonomy-tiers (that dials off/draft/auto
  per STAGE inside an ON feature; this classifies a whole REQUEST into a lane and decides if human review is
  required at all), confirmed-inputs-decision-gate (which gates the TRUST of one input value; this gates a
  whole request's progression), governed-operator-console (which gates individual actions), and
  append-only-audit-log (every classification + transition is an audit event). Guardrail: the classifier is
  fail-safe toward escalation — any RED flag forces owner review and blocks build/release/public-estimate.
---
# Risk-Classified Review Queue

## What it is / when to use / what it composes with
The governance spine that decides, for an incoming request, **how much human oversight it needs** and **that
it can't skip steps**. Three moving parts: a **classifier** (impact flags → GREEN/YELLOW/RED), a **queue
projection** (lane + dual public/internal status + estimate-allowed flag), and a **no-teleport transition
map** (each stage requires the prior artifact).

- **`graduated-autonomy-tiers`** is per-stage off/draft/auto INSIDE an already-approved feature. This decides,
  earlier, whether a request is even allowed to proceed autonomously or must go to an owner review table.
- **`confirmed-inputs-decision-gate`** gates the trust of a single input value before math runs; this gates a
  whole request's movement through a lifecycle.
- **`governed-operator-console`** gates discrete actions; **`append-only-audit-log`** stores the trail.

## Reference implementation — exact source
`~/Projects/Kingmaker/contracts/runtime-sovereignty.ts`:
- **The classifier:** `classifyKingmakerRequest(input)` — `:309-352`. A list of boolean impact flags
  (`touchesGovernance`, `touchesAudit`, `exposesRoninIp`, `exposesInternalArchitecture`,
  `affectsCrossTenantData`, `affectsPrivacy`, `affectsRevenueModel`, `affectsVaultLaw`, `createsLiabilityRisk`)
  → any hit ⇒ RED + `founderReviewRequired` + a plain reason listing the triggers (`:322-331`). Fabrication /
  incubation ⇒ YELLOW (review before canonize/release) (`:333-342`). Else GREEN, delegated-autonomy
  approvable (`:344-351`). Input/result shapes: `KingmakerClassificationInput`/`Result` `:118-145`.

`~/Projects/Kingmaker/contracts/kingmaker-queue.ts`:
- **Lane routing:** `selectKingmakerQueueLane(riskClass)` — `:60-64` (RED→founder table, YELLOW→review,
  GREEN→autonomous).
- **Dual status + estimate gate:** `publicStatusForRisk` `:66-70` (public sees "under review" / "founder
  review pending" / "selected for build", NOT the internal status) and `estimateAllowedForRisk` `:72-74` (RED
  gets no public estimate).
- **Create / guards / advance:** `createKingmakerQueueItem` `:76-115` (status = `AWAITING_FOUNDER_REVIEW` for
  RED else `QUEUED`); `mayKingmakerMoveWithoutFounder` / `mustGoToFounderTable` `:117-123`;
  `advanceKingmakerQueueItem` `:125-135` (only changes status + timestamp).

`~/Projects/Kingmaker/contracts/lifecycle-transitions.ts` + `lifecycle-stage.ts`:
- **"Nothing teleports":** `LIFECYCLE_TRANSITION_RULES` — `lifecycle-transitions.ts:13-24`. Each rule names a
  `from`/`to` and a `requiresReference` (e.g. `objectiveRef`, `queueRef`, `capabilityRef`, `vaultRef`) — you
  cannot reach BUILDING without a selected capability, or RELEASED without validation+registration.
  `canTransitionLifecycle` `:26-29` (only `BLOCKED` is reachable from anywhere), `nextLifecycleStages` `:35-37`.
- **Stage state + block/release predicates:** `lifecycle-stage.ts:40-74` — `isLifecycleBlocked`,
  `canLifecycleRelease`, and the public/internal `LifecycleMessagePair`.
- **Snapshot container:** `lifecycle-snapshot.ts` — one lifecycle's stage + the artifact refs, with
  `withLifecycleReference` / `withLifecycleStage` immutable updates.
- **Engine wiring (glue):** `runtime/kingmaker-engine.ts:22-66` — `routeObjectiveThroughKingmaker` composes
  create-item + the two founder predicates into an `{ok, founderReviewRequired, reasonPlain}` result.

## How to reapply
- **Adapt the flag set** to your domain (drop the IP/architecture flags, keep money/privacy/irreversible/
  cross-tenant). Keep the rule: any high-impact flag ⇒ RED ⇒ owner review, no build/release/public estimate.
- **Store two statuses.** Persist the internal status for operators and project a coarser public status for
  the requester — never leak internal state.
- **Enforce transitions in code, not convention.** Check `canTransitionLifecycle(from,to)` and that the
  required artifact ref exists before advancing; refuse otherwise.

## Unwired — bindings you must add
These are **pure types + pure functions, no I/O** — no persistence, routes, cron, or UI ship in the source
(README "Status": contract + engine layer only). To productionize:
- **D1:** a `queue_items` table (queueItemId, sourceType, riskClass, lane, status, publicStatus, timestamps)
  and a `lifecycle_snapshots` table (stage + the artifact-ref columns).
- **Routes:** `POST /intake` (classify + create item + snapshot), `POST /advance` (guarded transition),
  `GET /queue` (operator, internal status) and a public `GET /status/:id` (public status + estimate only if
  allowed). Gate writes with `governed-operator-console` / `crm-mcp-server` scopes; audit each transition.
- **Cron:** advance GREEN items through automatable stages; leave YELLOW/RED parked for review.

## Gotchas (from the code)
- **Escalation is the safe default.** The classifier returns RED on the FIRST impact flag and forbids
  proceeding — err toward review, never toward autonomy (`runtime-sovereignty.ts:322-331`).
- **RED gets no public estimate.** Don't leak a timeline for something that hasn't cleared owner review
  (`kingmaker-queue.ts:72-74`).
- **A stage without its artifact is a teleport — refuse it.** The whole point of `requiresReference` is that
  you cannot build without a selected capability or release without validation+registration.
- **Public status ≠ internal status.** Keep the projection; the requester sees "under review", not your
  internal `SCOPING`/`VALIDATING` machinery.
