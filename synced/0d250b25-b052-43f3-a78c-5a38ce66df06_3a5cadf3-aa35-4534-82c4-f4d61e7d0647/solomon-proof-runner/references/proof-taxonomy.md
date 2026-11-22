# Solomon Proof Taxonomy

Every proof script in `package.json`, grouped by purpose, with the README claim each one
backs. Source of truth is always the repo's own `package.json` scripts block — if a command
here is missing or renamed, re-read `package.json` before running. Names below match the
repo state at the time this skill was written (commit family around the "Digital Twin Engine"
/ August 2 flagship work).

## Table of contents
1. Aggregate gates (run these first)
2. Core release proofs
3. Flagship functional proofs
4. Governance & integrity proofs
5. Voice proofs
6. Internet / native-retrieval proofs
7. Connector & merchant proofs
8. Packaging / platform proofs
9. Digital Twin engine tests
10. Side-effectful release commands (approval required — NOT proofs)

---

## 1. Aggregate gates (run first)
These fan out over many checks and give the fastest overall read.

| Command | What it gates |
|---|---|
| `npm run solomon:readiness` | Overall release readiness rollup |
| `npm run solomon:readiness:controlled-validation` | Readiness under the Aug 2 controlled-validation profile |
| `npm run solomon:aug2-flagship-gate-runner` | The August 2 flagship gate |
| `npm run solomon:flagship-functional-closure-proof` | All flagship functional proofs closed |
| `npm run solomon:readme-scope-flagship-completion-proof` | **"README completion"** — every capability the README claims is backed by a passing proof |
| `npm run solomon:north-star-completion-stack-proof` | North Star command-loop completion |
| `npm run solomon:final-release-report` | Generates the consolidated release report |
| `npm run solomon:tomorrow-deployment-gate` | Deployment gate check |

> When the operator says "complete the README", the literal proof is
> `solomon:readme-scope-flagship-completion-proof`. Run it, read which claims it reports as
> unbacked, and drive those to PASS (or make the README truthfully mark them DEFERRED).

## 2. Core release proofs
From the README "Core release proofs" list — the standard pre-release sweep.

| Command | Backs |
|---|---|
| `npm run solomon:readiness` | Release readiness |
| `npm run solomon:voice-governance-proof` | Governed voice workflow (`GOVERNED_VOICE_WORKFLOW_PASS`) |
| `npm run package:test` | Windows package builds + smoke-tests (Windows only) |
| `npm run solomon:validate:clean-install` | Builds from a clean clone with no manual repair |
| `npm run solomon:deployment-runtime-proof` | Deployment runtime behaves |
| `npm run solomon:data-leakage-proof` | No cross-tenant / no data leakage |
| `npm run solomon:ui-visual-qa` | UI visual QA |

## 3. Flagship functional proofs
Each proves a flagship capability actually works (not just scaffolded). Pattern:
`test:<x>-flagship-functional` is the runner, `solomon:<x>-flagship-functional-proof` is the proof.

| Command | Capability |
|---|---|
| `npm run solomon:project-twin-flagship-functional-proof` | Project Twin |
| `npm run solomon:build-tree-flagship-functional-proof` | Build Tree |
| `npm run solomon:truth-envelope-decision-engine-flagship-proof` | Truth Envelope + Decision Engine |
| `npm run solomon:voice-flagship-functional-proof` | Voice (often DEFERRED — needs manual proof) |
| `npm run solomon:codegen-flagship-functional-proof` | CodeGen |
| `npm run solomon:fabrication-flagship-functional-proof` | Fabrication (planning-only boundary) |
| `npm run solomon:crm-merchant-flagship-functional-proof` | CRM / Merchant |
| `npm run solomon:evidence-source-flagship-functional-proof` | Evidence source attribution |
| `npm run solomon:project-twin-restore-proof` | Restore without re-running research |
| `npm run solomon:codegen-runnable-proof` | Generated CodeGen artifacts are runnable scaffolds |

## 4. Governance & integrity proofs

| Command | Backs |
|---|---|
| `npm run solomon:audit-integrity-proof` | Append-only audit integrity |
| `npm run solomon:primary-constant-audit` | Primary constant audit |
| `npm run solomon:loopback-exposure-proof` | No unintended network loopback exposure |
| `npm run solomon:data-leakage-proof` | No data leakage |
| `npm run solomon:tenancy-hardening-proof` | Tenant isolation hardening |
| `npm run solomon:self-evolution-governance-proof` | Self-evolution stays governed |
| `npm run solomon:node-generation-governance-proof` | Node generation governance |
| `npm run solomon:release-gate-negative-proof` | Release gate correctly fails closed on bad input |
| `npm run solomon:fabrication-execution-boundary-proof` | Fabrication never claims execution |
| `npm run solomon:governance-soak` / `npm run solomon:soak-proof` | Long-duration governance stability (may be incomplete) |

## 5. Voice proofs
Voice is truthful/deferred unless manual proof exists — expect DEFERRED unless proven.

| Command | Backs |
|---|---|
| `npm run solomon:voice-governance-proof` | Governed voice submit path |
| `npm run solomon:voice-stack-proof` | Voice stack |
| `npm run solomon:voice-runtime-proof` | Voice runtime |
| `npm run solomon:voice-flagship-functional-proof` | Voice flagship functional |
| `npm run solomon:whisper-bridge-proof` | Whisper STT bridge |
| `npm run solomon:local-stt-adapter-proof` | Local STT adapter |
| `npm run solomon:manual-capture-smoke-proof` | Manual capture smoke |

## 6. Internet / native-retrieval proofs
Distinguish **native internet retrieval** (provable) from **external provider reasoning**
(CONFIG-HOLD until keys/unlock). Only run the `--approved` fetch with operator approval.

| Command | Notes |
|---|---|
| `npm run solomon:validate:internet-proof` | Safe validate variant |
| `npm run solomon:internet-proof` | Performs a REAL approved outbound fetch — approval required |
| `npm run solomon:live-internet-validation` | 13-check live validation incl. fail-closed on invalid target |
| `npm run solomon:online-validation-proof` | Native retrieval PASS; external provider reasoning CONFIG-HOLD |
| `npm run solomon:native-internet-boundary-proof` | Native internet boundary |

## 7. Connector & merchant proofs

| Command | Backs |
|---|---|
| `npm run solomon:connector-orchestration-proof` | Connector orchestration |
| `npm run solomon:connector-permission-grants-proof` | Voice-authenticated connector permission grants (access ≠ execution) |
| `npm run solomon:local-device-fallback-proof` | Governed local-device fallback (fail closed, proposal-only) |
| `npm run solomon:clover-validated-menu-snapshot-diff-proof` | Clover validated menu snapshot diff |
| `npm run solomon:merchant-ops-clover-runtime-proof` | Clover runtime only |
| `npm run solomon:merchant-ops-clover-orchestrator-proof` | Clover orchestrator only |
| `npm run solomon:google-workspace-evidence-connector-bridge-proof` | Google Workspace evidence bridge |

## 8. Packaging / platform proofs
Windows/NSIS proofs are DEFERRED on non-Windows hosts (do not FAIL them there).

| Command | Backs |
|---|---|
| `npm run package:test` | Win package + smoke (Windows only) |
| `npm run solomon:signing-readiness-proof` | Code-signing readiness (currently NOT READY per README) |
| `npm run solomon:installer-branding-proof` | Installer branding |
| `npm run solomon:mac-artifact-proof` | macOS artifact |
| `npm run solomon:packaged-health-proof` | Packaged app health |
| `npm run solomon:public-saas-readiness-proof` | Public SaaS readiness (currently BLOCKED per README) |
| `npm run solomon:customer-runtime-proof` | Customer runtime |
| `npm run solomon:customer-zero-proof` | Customer-zero scenario |
| `npm run solomon:deployment-runtime-proof` | Deployment runtime |

## 9. Digital Twin engine tests
Lower-level runners behind the engine claims.

| Command | Backs |
|---|---|
| `npm run test:digital-twin-engine` | Digital Twin Engine runtime |
| `npm run test:project-twin` | Project Twin |
| `npm run test:digital-twin-integration` | Engine ↔ route integration |
| `npm run test:evidence-screenshots` | Evidence screenshot attachment state |
| `npm run test:source-attribution` | Source attribution |
| `npm run test:persona-router` | Persona router invariance (README lists this as an open blocker) |

## 10. Side-effectful release commands — approval required (NOT proofs)
Never run without explicit in-chat operator approval. Surface what each does first.

- `npm run solomon:promote-release`
- `npm run solomon:release:build`
- `npm run solomon:release:upload-win`
- `npm run solomon:release:verify-win`
- `npm run solomon:release:cloudflare`
- `npm run solomon:release:cloudflare:validate`
- `npm run solomon:release:full`

---

## Known open blockers (from README — expect these to not PASS yet)
- Source Triage accepted/rejected metadata + rejection reasons not fully proven
- Persona Router invariance proof missing
- External Provider Reasoning CONFIG-HOLD (needs provider keys/unlock)
- Production ronininc.org serving stale cached Vite shell, not the validated Cloudflare zip
- Unsigned Windows/macOS release proof incomplete
- Public SaaS boundary/payment/entitlement automation unproven
- True CAD/render/manufacturing engines missing (Fabrication is planning-only)
- Long-duration soak testing incomplete
- D1 governance hardening not fully finalized
