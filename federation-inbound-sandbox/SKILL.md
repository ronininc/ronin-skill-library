---
name: federation-inbound-sandbox
description: >-
  The RECEIVING end of a one-way control-plane diode: treat every report a node pushes UP to an oversight
  brain as hostile and SANDBOX it before ingest. Strict per-kind schema validation, a required `sanitized:
  true` flag (refuse anything not marked sanitized), a DEEP forbidden-key scan that quarantines any object
  carrying a payload/source/code/exec/sql key or a prototype-pollution key (__proto__/constructor/prototype)
  at any depth, size + count + id-format caps, and a QUARANTINE lane that records why each bad line was
  refused without ever ingesting it. Clean reports are accepted as METADATA ONLY (identity/category/
  graduation/threat-category — never source, code, or customer data), imported STAGED-UNDER-REVIEW (never
  auto-promoted to canon), and de-duplicated idempotently across repeated pulls via a persisted seen-set.
  Use WHENEVER an oversight/aggregator layer INGESTS reports from CRMs, tenants, edge nodes, or partner
  installations it does not trust — "pull sanitized status from each node", "accept reports from untrusted
  installations", "schema-firewall the inbound feed", "make sure a compromised node can't push code/data
  up", "quarantine malformed reports", "federate abilities/threat-intel across installs", or "the consuming
  end of the diode". It COMPLEMENTS governance-diode (that skill is the SENDING side — the aggregate-only
  reads + whitelisted-directive writes at the node; THIS is the sandbox at the collector where those reports
  land), signed-webhook-intake (transport auth happens there — this is content sandboxing AFTER auth), and
  append-only-audit-log (log every staged/quarantined line). Guardrail: metadata only, never evaluate — there
  is no code to run, so sandboxing == strict validation + anomaly quarantine; nothing is auto-canon.
---
# Federation Inbound Sandbox

## What it is / when to use / what it composes with
When a central brain PULLS reports from many nodes it does not control, every inbound line is untrusted. This
is the schema-firewall + quarantine + never-auto-promote pattern that lets the aggregator accumulate the
*abilities and threat-intel* of every node while giving a compromised node **no path to push code or data
upward**. There is nothing to execute — reports are metadata — so "sandbox" means strict validation and
anomaly quarantine, not evaluation.

- **`governance-diode` is the other end.** That skill builds the node-side sanitized aggregate reads and the
  whitelisted reverse-directive writes. This skill is what the *collector* does with those reports when they
  arrive: refuse anything that isn't a clean, sanitized, in-schema report.
- **`signed-webhook-intake`** authenticates the transport (who sent it). This runs AFTER that: is the payload
  actually a sanitized, in-schema report, or a weaponized one?
- **`append-only-audit-log`** records each staged ability, threat-intel row, and quarantine reason.

## Reference implementation — exact source
`~/Projects/Kingmaker/contracts/federation-report.ts`:
- **Report shapes (metadata only):** `FederationSkillReport` / `FederationInventoryReport` — `:12-26`. Note
  each carries `sanitized: true` and NO source/code/data field.
- **Forbidden-key list + deep scan:** `FORBIDDEN_KEYS` — `:55` (sourcetext/source/code/script/sql/payload/
  exec/command/cmd/bytes/blob/__proto__/constructor/prototype); `hasForbiddenKey(value, depth)` — `:62-69`
  recurses to depth 6 and quarantines on any hit.
- **The sandbox:** `sandboxIncomingReport(raw)` — `:75-103`. Order matters: reject non-object → deep
  forbidden-key scan → require `sanitized === true` → per-`kind` field validation (`idRe` `:59`,
  `MAX_STRING`/`MAX_SKILLS` `:56-57`, verdict enum, bounded categories array, per-skill field checks) → typed
  report or `{ok:false, reason}`.

`~/Projects/Kingmaker/runtime/solomon-federation-collector.ts`:
- **The pull loop:** `collectFromSolomonOutbox(outboxPath, {state, at})` — `:32-69`. Missing/unreadable source
  ⇒ empty result (never fabricate). Split into lines, `JSON.parse` each (parse failure → quarantine), sandbox,
  then: `federation` reports STAGE each skill as `status:'STAGED_UNDER_REVIEW'`, `origin:'…_FEDERATED'`,
  `customerDataIncluded:false` (`:52-58`); a `BLOCKED` skill report becomes a `ThreatIntelRecord` (`:59-64`);
  an `ALLOWED` skill report adds no ability and is ignored (`:65`).
- **Idempotent dedup:** `CollectorState { seen:Set }` — `:22-23`; keys `installationId␟skillId` and
  `blocked␟skillId` skip anything already accumulated (`:54-56`, `:60-62`). Persist `state` between pulls.
- **Proof:** `~/Projects/Kingmaker/test/federation-collector.test.ts` — a payload-key line, a malformed-JSON
  line, and an un-`sanitized` line are ALL quarantined; only the clean graduated ability is staged (under
  review); the blocked skill becomes threat intel; a re-pull stages nothing new.

## How to reapply
- **Copy the two contracts verbatim** — they are pure, dependency-free functions (import them; do not
  re-derive the forbidden-key scan).
- **Persist the seen-set** (a KV/D1 row of seen keys, or a hash column) so idempotency survives process
  restarts, not just one run.
- **Never auto-canon.** Accepted abilities land `STAGED_UNDER_REVIEW`; a SEPARATE governed step (a human or a
  higher-authority routine — see `risk-classified-review-queue`) promotes them.

## Unwired — bindings you must add
The reference is a pure sandbox + a **file-based** collector (`readFileSync` of a local append-only outbox,
`solomon-federation-collector.ts:37`). To productionize:
- **Transport:** replace the file read with your real pull (an authenticated fetch of the node's read-only
  outbox endpoint, or a scheduled drain of a queue) — put `signed-webhook-intake`-style auth in front.
- **Persistence:** write `staged` abilities and `threats` to D1 tables; keep the `seen` set in KV/D1.
- **Cron:** run the collector on a schedule (Worker cron trigger) and audit each pull.

## Gotchas (from the code)
- **Scan for forbidden keys FIRST and DEEP.** The check runs before schema validation and recurses, so a
  payload hidden in a nested object still quarantines (`federation-report.ts:77`, `:62-69`). Include the
  prototype-pollution keys, not just "source".
- **`sanitized:true` is mandatory.** A report that simply omits the flag is refused — absence is not consent
  (`:79`).
- **A missing source is empty, not an error.** Never fabricate an ability you didn't read
  (`solomon-federation-collector.ts:37`).
- **Metadata only — do not "run" a report.** There is no execution path here; the security property is that
  abilities are inert descriptions. Keep it that way.
