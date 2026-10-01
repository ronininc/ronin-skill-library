---
name: revenue-readiness-report
description: >-
  A read-only "WHY are the money engines idle?" diagnostic for a Worker+D1 revenue app, built so an AI
  operator can answer "make me money" by READING it first and then proposing approval-gated actions — it
  invents nothing and COMPOSES the gates the app already has (revenue kill switch, the daemon switchboard,
  machine health, deliverability/bounce breaker, Stripe readiness, Google-connected, approval-queue COUNTS,
  the deployed build id) into a severity-sorted list of plain-language BLOCKERS, each with a concrete FIX and
  an `operator_only` flag. Hard privacy contract: NO secret values/tokens/PII ever leave — secrets appear only
  by NAME with a present/absent boolean, queues only as counts, a batch only as its count + manifest hash. It
  ships with ONE narrow write (`set_daemon`) that flips exactly the admin toggle and refuses to arm a
  sends/publishes daemon without the operator's explicit go-ahead and refuses to arm ANYTHING while the kill
  switch is Stopped. Use WHENEVER a build needs "why isn't anything making money", "what's blocking revenue",
  "a readiness check before I turn things on", "tell the AI what's wrong and how to fix it, but don't let it
  see secrets", "one status read my assistant can act on", or a pre-flight gate in front of a governed console.
  It COMPLEMENTS daemon-fleet-switchboard (it READS that switchboard + wraps its toggle with go-ahead/kill-switch
  guards — it does not re-implement it), money-feed-health-monitor (that is the money IN/OUT/net read-model;
  this is the WHY-IDLE blocker read), governed-operator-console / least-privilege-mcp-connector (this is the
  grounding snapshot the caged AI reads before it proposes). Guardrail: read-only and PII-free; the single
  write never touches revenue-control state or any approval, and never arms past a stopped kill switch.
---

# Revenue Readiness Report (why the money engines are idle, PII-free)

## What it is / when to use
A composed, read-only snapshot that explains — in plain language, worst-first — everything standing between
the business and revenue, so an AI operator (or an oversight app) can act on it safely. It re-implements none
of the gates: it calls the app's existing status functions and turns them into `{id, severity, text, fix,
operator_only}` blockers. It is the natural pre-flight read in front of a caged operator console, and the
grounding an external brain is handed before it proposes anything.

Use it when "make me money" needs a truthful answer, when an assistant must know what's wrong without being
trusted with secrets, or when the operator wants one status read that doubles as a to-do list. Compose it with
`daemon-fleet-switchboard` (it reads the switchboard and wraps its toggle), `money-feed-health-monitor` (the
money read-model), and `governed-operator-console` / `least-privilege-mcp-connector` (the caged surfaces that
consume it).

## Reference implementation (exact)
- The whole read: `worker/revenue-readiness.ts:211` `revenueReadiness()` — composes `revenueWorkflowStatus`,
  `daemonSwitchboard`, `machineHealth`, `deliverabilityGate`, `campaignReadiness`, `approvalQueues`,
  `stripeReadiness`, `secretPresence`, `buildInfo` and returns `ready` + `summary` + sorted `blockers`.
- The pure blocker logic (easy to prove): `worker/revenue-readiness.ts:125` `computeBlockers(Inputs)` — each
  blocker carries a `severity`, human `text`, a `fix`, and `operator_only`; sorted by severity `:208`.
- PII-free primitives: `secretPresence()` names only + boolean `worker/revenue-readiness.ts:102`;
  `approvalQueues()` counts only `:47`; `campaignReadiness()` statuses + queued/held counts `:67`;
  `buildInfo()` from the version-metadata binding `:94`.
- The narrow write + its guards: `worker/revenue-readiness.ts:257` `setDaemonFromSolomon()` — refuses an
  unknown/switchless daemon, refuses to arm a `sends`/`publishes` daemon without `operatorGoAhead===true`
  (`:262`), and refuses to arm anything while the kill switch is Stopped (`:265`).
- Wiring (MCP tools on the external-brain surface): `worker/solomon-mcp.ts:29` import, `:352` `revenue_readiness`,
  `:366` `machine_health`, `:373` `set_daemon`. Migration context: `migrations/0110_revenue_batch_control.sql`.

## How to reapply
1. **List the gates that stand between you and revenue** and write a tiny read for each that returns state, not
   secrets: kill-switch state, daemon switchboard, machine health, deliverability (verifier + bounce breaker +
   send-pause), payment processor readiness (configured + webhook), identity/OAuth connected, approval-queue
   counts, deployed build id.
2. **Make the blocker logic a PURE function** `computeBlockers(inputs): Blocker[]`. Each blocker: a stable `id`
   (e.g. `WORKFLOW_STOPPED`, `EMAIL_VERIFY_MISSING`, `STRIPE_WEBHOOK_MISSING`), a `severity`
   (`critical|high|medium|low`), a human `text` that states the real consequence, a copy-pasteable `fix`, and
   `operator_only` (true when only a human can do it — connect OAuth, put a secret). Sort by severity. `ready` =
   no critical/high blockers.
3. **THE INVARIANT — read-only and PII-free, and the AI reads before it acts.** Secrets appear ONLY as
   `{NAME: boolean}`; queues ONLY as counts; a pending batch ONLY as `{count, manifest_hash}`. No token value,
   no recipient, no message body ever appears. The report proposes fixes; it performs none. An agent consuming
   it must still go propose → operator confirm → execute.
4. **Expose at most ONE scoped write, and guard it three ways.** `set_daemon(id, on, operator_go_ahead)` flips
   exactly the admin toggle and: refuses unknown/always-on daemons; refuses to ARM a `sends`/`publishes`-tier
   daemon unless `operator_go_ahead===true`; refuses to arm ANYTHING while the revenue kill switch is Stopped.
   It never changes kill-switch state and never approves a queued item.
5. **Serve it as a read tool** on your operator/MCP surface and let the caged console read it for grounding.

## Gotchas (from the code)
- **Every count query is wrapped so a missing table reads as `null` (unknown), never a crash** (`count()`
  `worker/revenue-readiness.ts:39`) — the readiness read must survive a half-migrated instance.
- **Severity drives behavior**: an allow-unverified override DOWNGRADES a missing-verifier blocker from
  critical to high but makes the text admit cold mail is going out unproven (`:137`) — tell the truth about the
  trade-off instead of hiding it.
- **`operator_only` is the honesty bit** for an AI caller: it marks the blockers the assistant physically cannot
  fix (connect Google, put a Worker secret) so it proposes the right next human step instead of pretending.
- **The one write is the same toggle the admin UI flips** (`writeEnabled`), not a parallel path — so the
  switchboard, the UI, and the AI can never disagree about a daemon's state.
- **Keep it composed, not copied.** If you re-derive deliverability/Stripe/health here you create a second
  source of truth that drifts; call the existing functions (`:212-219`).
- **Validated** by the pure-function proofs over `computeBlockers` and by `revenue_readiness` being the grounding
  read the governed MCP surface serves before any proposal.
