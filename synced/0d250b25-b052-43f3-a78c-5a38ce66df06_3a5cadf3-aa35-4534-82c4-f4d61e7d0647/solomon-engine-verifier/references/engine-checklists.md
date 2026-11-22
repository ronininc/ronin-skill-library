# Solomon Engine Verifier — Per-Engine Checklists

Each engine uses the same five-part structure: **Proof**, **Functional checks**,
**Governance invariants**, **Recording must show**, **Verdict**. Every engine requires a
screen recording with audio (see `av-capture.md`); the "Recording must show" list is the
minimum the A/V capture has to contain for that engine. Proof commands are run via
`solomon-proof-runner`; confirm the exact script names against `package.json`.

Setup for all engines (once): `npm install && npm --prefix server install && npm --prefix app install`,
then `npm run build:server && npm run build:app`. Windows-only steps are DEFERRED on other hosts.

---

## 1. Solomon Runtime (governance core)
**Proof:** `npm run solomon:readiness`; `npm run solomon:audit-integrity-proof`;
`npm run solomon:primary-constant-audit`.
**Functional checks:**
- A request is classified and routed deterministically (same input → same route twice).
- Governance runs before generation (the workflow shows classification → governance → recommendation).
- An append-only audit entry is written for the workflow.
**Governance invariants:** deterministic routing; governance never bypassed; audit is append-only
(no edit/delete of prior entries).
**Recording must show:** submitting the same request twice and the identical route; the audit
entry appearing; narration of each stage.
**Verdict:** VERIFIED only if routing is visibly deterministic and audit is append-only.

## 2. Digital Twin Engine
**Proof:** `npm run test:digital-twin-engine`; `npm run test:digital-twin-integration`.
**Functional checks:**
- A conversation resolves intent → a canonical Twin type → the correct workspace renders.
- Twin lifecycle (create/select) works from conversation, not a dashboard.
- Evidence/research attach to the Twin, not to floating UI.
**Governance invariants:** reserved future Twins (MERCHANT, ORGANIZATION, etc.) return the
deferred marker, not a fake workspace.
**Recording must show:** speaking/typing an intent, the Twin resolving, the workspace rendering,
and a reserved Twin correctly refusing with a deferred marker.
**Verdict:** VERIFIED only if intent→Twin→workspace is observable and reserved Twins stay deferred.

## 3. Decision Engine & Truth Envelope
**Proof:** `npm run solomon:truth-envelope-decision-engine-flagship-proof`.
**Functional checks:**
- A deterministic question (e.g. an inventory calc) returns the discovered answer, not an invented one.
- A probabilistic question returns possible futures + confidence + assumptions, not false certainty.
- Every recommendation carries a Truth Envelope: facts / assumptions / unknowns / constraints /
  confidence / authority / execution state.
**Governance invariants:** unknowns stay unknown; planning labeled planning; no fabricated confidence.
**Recording must show:** both a deterministic and a probabilistic query, with the Truth Envelope
fields visible on screen and read aloud.
**Verdict:** VERIFIED only if the Truth Envelope is present and honestly distinguishes fact from assumption.

## 4. CodeGen
**Proof:** `npm run solomon:codegen-flagship-functional-proof`; `npm run solomon:codegen-runnable-proof`.
**Functional checks:**
- A build request triggers constraint discovery BEFORE any code (questions asked first).
- A Project Twin and Build Tree are created with requirements/architecture/dependencies.
- Generated artifacts are labeled local scaffolds, exposing requirements + missing requirements.
**Governance invariants:** planning is never presented as execution; generated code is never called
deployed; every stage has its own governance state.
**Recording must show:** the constraint-discovery questions, the Project Twin + Build Tree
appearing, and the artifact explicitly marked as a scaffold (not deployed).
**Verdict:** VERIFIED only if planning-vs-execution separation is visible.

## 5. Fabrication
**Proof:** `npm run solomon:fabrication-flagship-functional-proof`;
`npm run solomon:fabrication-execution-boundary-proof`.
**Functional checks:**
- A concept triggers governed engineering planning (constraint discovery → material → validation).
- A Project Twin + Build Tree + manufacturing plan are produced as PLANS.
**Governance invariants (critical):** Fabrication is planning-only. It must NOT claim CAD readiness,
measured render accuracy, manufacturing/physical fabrication readiness, or machine-adapter execution.
**Recording must show:** the planning workflow, and the UI explicitly declining/So-labeling any
CAD/render/manufacturing readiness claim (i.e. the boundary holding).
**Verdict:** VERIFIED (planning-only). Never VERIFIED as "manufacturing-ready."

## 6. CRM / Merchant
**Proof:** `npm run solomon:crm-merchant-flagship-functional-proof`; connector proofs as applicable
(`solomon:connector-permission-grants-proof`, `solomon:clover-validated-menu-snapshot-diff-proof`).
**Functional checks:**
- Customer/merchant context is created and persists as governed operational memory.
- A governed conversation produces a traceable decision + follow-up + audit entry.
- Connector permission grants show access ≠ execution (grant does not auto-run actions).
**Governance invariants:** connector actions require the governed permission grant; unsupported
channels fail closed (then may offer approved local-device fallback, proposal-only).
**Recording must show:** granting a connector permission, and an action requiring explicit approval
(not auto-executing); a fail-closed channel offering an audited local fallback.
**Verdict:** VERIFIED only if access-is-not-execution is observable.

## 7. Voice
**Proof:** `npm run solomon:voice-flagship-functional-proof` and the voice proof set
(see `solomon-voice-verification`).
**Functional checks:** mic → STT transcript (editable pre-submit) → governed runtime → Truth
Envelope → TTS response. Risky request requires confirmation. Voice does not auto-execute.
**Governance invariants:** voice changes only the interface, never governance; no auto-submit; no
provider key required (offline-first).
**Recording must show (audio is the proof here):** the operator speaking a request aloud; the
transcript appearing and being editable; the governed response; the TTS speaking back with
governance metadata still visible; a risky request pausing for confirmation.
**Verdict:** VERIFIED only with an audio track containing real speech + TTS. Otherwise DEFERRED.

## 8. Native Internet
**Proof:** `npm run solomon:native-internet-boundary-proof`; `npm run solomon:online-validation-proof`;
approved fetch `npm run solomon:internet-proof` (operator approval required — see `solomon-native-internet`).
**Functional checks:** a real operator-approved fetch over the device network yields a
SOURCE_EXTRACTED record with an audit hash; an invalid/unapproved target fails closed
(INTERNET_BLOCKED); native retrieval and external provider reasoning are shown as separate lanes.
**Governance invariants:** no external provider key required for native retrieval; provider lane is
CONFIG-HOLD; no hidden internet calls.
**Recording must show:** approving the fetch, the source + audit hash appearing, and an invalid
target being refused (fail-closed).
**Verdict:** `NATIVE INTERNET: VERIFIED`; `PROVIDER REASONING: CONFIG-HOLD` — never merged.

## 9. Evidence & Screenshot Workspace
**Proof:** `npm run test:evidence-screenshots`; `npm run solomon:interface-screenshot-gallery-proof`.
**Functional checks:** a real capture shows capture-state CAPTURED; when no capture exists the state
is NOT_CAPTURED (not faked); blocked/absent capture paths show FAILED/UNSUPPORTED; evidence attaches
to the Twin.
**Governance invariants:** capture-state is always truthful; evidence is attached to the Twin, not floating.
**Recording must show:** a successful capture flipping to CAPTURED, and a no-capture case honestly
showing NOT_CAPTURED. (This engine's own A/V recording is itself an example of the standard.)
**Verdict:** VERIFIED only if capture-state truthfully reflects reality in each case.

## 10. Project Twin & Build Tree
**Proof:** `npm run solomon:project-twin-flagship-functional-proof`;
`npm run solomon:build-tree-flagship-functional-proof`; `npm run solomon:project-twin-restore-proof`.
**Functional checks:** create → save → restart runtime → restore the Twin WITHOUT re-running
research; Build Tree renders nodes with completion/dependencies/governance/audit; export summary works.
**Governance invariants:** research/governance stay attached across restore (not re-run); nothing
disappears into conversation.
**Recording must show:** creating and saving a Twin, closing/reopening the runtime, the Twin
restoring intact with research still attached (not recomputed), and an export summary produced.
**Verdict:** VERIFIED only if restore-without-re-running-research is visibly demonstrated.

---

## Sign-off rule
An engine is VERIFIED only when all three hold: (1) its automated proof PASSES this session,
(2) its functional checklist passed under observation, and (3) a screen recording with audio
exists with capture-state CAPTURED showing the "Recording must show" items. Any gap → the honest
lower status (DEFERRED / UNVERIFIED) with the specific reason. Feed results to `solomon-readme-sync`.
