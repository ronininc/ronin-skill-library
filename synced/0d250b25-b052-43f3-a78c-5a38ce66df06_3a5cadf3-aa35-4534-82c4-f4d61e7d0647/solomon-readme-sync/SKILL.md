---
name: solomon-readme-sync
description: >-
  Keep the Solomon / TSS README and release documents truthful and in sync with real
  proof results. Use this whenever you are editing README.md, RELEASE_READINESS_REPORT.md,
  RELEASE_CANDIDATE_CHECKLIST.md, RELEASE_NOTES.md, README-CUSTOMER.md, or any status /
  "Current Status" / "Definition of Done" / "Known Blockers" / "Verified Governance Proofs"
  section in the ronininc/TSS repo. Trigger on "update the readme", "complete the readme",
  "sync the status", "update release status", "mark X as done/deferred", "refresh the
  blockers list", or writing any new SOLOMON_*.md governance doc. Solomon's doctrine forbids
  claiming a capability is done/validated/online/deployed unless a proof backs it, so every
  status edit here must be driven by real proof output, never by optimism.
---

# Solomon README & Status Sync

The Solomon README is not marketing copy — it is a governed status document. Its
"Current Status", "Verified Governance Proofs", "Definition of Done", and "Current Known
Blockers" sections are load-bearing claims that must match what the proof suite actually
reports. This skill exists to edit those documents so they stay truthful. "Completing the
README" means driving claimed capabilities to real PASS and honestly marking everything
else — not making the prose sound finished.

If you also need to *run* the proofs, use the `solomon-proof-runner` skill first; this
skill turns real proof results into truthful document edits.

## The rule you cannot break

Only write a positive status (ACTIVE / PASS / READY / done) into a document when a proof
currently backs it and you have seen that proof pass this session. If you have not verified
it, the honest markers are DEFERRED, CONFIG-HOLD, NOT READY, BLOCKED, or "unproven". The
README itself states the Final Principle: never claim online when offline, remembered when
not retrieved, deployed when scaffolded, validated when unproven. Your edits are held to
that same standard. When in doubt, mark it down, not up — an understated status is safe; an
overstated one breaks the entire trust premise of the project.

## Workflow

1. **Establish real state.** Run the relevant proofs (via `solomon-proof-runner`) or ask
   for their output. Never edit a status section from memory or assumption.
2. **Map proof → claim.** Each capability line in the README corresponds to a proof (see
   `solomon-proof-runner/references/proof-taxonomy.md`). Update each line from its proof's
   real verdict.
3. **Edit surgically.** Change only the status markers and blocker entries that actually
   changed. Preserve the document's existing structure, ordering, and voice.
4. **Keep the docs consistent with each other.** README, RELEASE_READINESS_REPORT.md, and
   RELEASE_CANDIDATE_CHECKLIST.md must not disagree. If one says a capability PASSES and
   another says DEFERRED, resolve it against the real proof, not by picking the nicer one.
5. **Move closed blockers, don't delete history dishonestly.** When a Known Blocker is
   genuinely resolved (proof now passes), remove it from the blockers list; if it's only
   partially addressed, reword it to state precisely what remains.

## Status vocabulary (use these exact markers)

Match the README's existing conventions:

- Capability lines: `ACTIVE`, `DEFERRED`, `LIMITED`, `NOT PROVEN`
- Proof/gate lines: `PASS`, `FAIL`, `CONFIG-HOLD`
- Release posture lines: `READY`, `NOT READY`, `BLOCKED`, `PROVEN`, `NOT SYNCED`
- Reserved future Twins (MERCHANT, ORGANIZATION, COMMUNICATION, MEETING, DECISION, TASK,
  CREDENTIAL, FINANCIAL, FABRICATION, DEPLOYMENT) must remain truthful **deferred
  placeholders**. Never upgrade a reserved Twin to a product claim.

Deferred is a legitimate, honorable state here — the README deliberately defers voice
runtime proof, Merchant Twin, Operations Command, GMF, and the Titan/Kingmaker execution
stack. Marking something DEFERRED with a clear reason is a *correct* completion, not a gap.

## Writing voice for Solomon docs

When authoring or extending status sections and SOLOMON_*.md docs, match the house style:

- Short declarative lines. One claim per line. The README uses terse, almost constitutional
  phrasing ("Governance is the product." "Planning remains planning.").
- Distinguish facts from assumptions from unknowns explicitly (Truth Envelope thinking).
- Never claim CAD/render/manufacturing readiness for Fabrication — it is planning-only.
- Never claim autonomous execution — Solomon requires operator confirmation for risky work.
- Never claim a Windows/macOS package PASS unless proven in the current environment.
- Do not describe scaffolded artifacts as deployed, or estimated values as fabricated fact.

## Example edits

**Example 1 — a proof now passes:**
Proof output: `solomon:project-twin-restore-proof` → PASS.
Edit the README "Current Status" line from
`Project Restore Proof: DEFERRED` to `Project Restore Proof: ACTIVE`
and, if it was listed as a blocker, remove that blocker line.

**Example 2 — a claim is not backed:**
Proof output: `solomon:voice-flagship-functional-proof` → DEFERRED (no manual proof).
Do NOT write "Voice: complete". Write `Voice Stack: DEFERRED / NOT PROVEN` and keep the
"full voice runtime proof" item under What Is Deferred.

**Example 3 — config, not code:**
Proof output: `solomon:online-validation-proof` → External Provider Reasoning CONFIG-HOLD.
Write `External Provider Reasoning: CONFIG HOLD until provider keys/unlock are configured` —
never `ACTIVE`, because nothing was proven; it was merely not yet configured.

## Before you finish

Re-read your edited section top to bottom and check every positive claim against a proof
you actually saw pass. If any positive claim lacks that backing, downgrade it. A README that
truthfully lists remaining blockers is "complete" in the sense that matters here; a README
that reads as finished but overstates unproven work is a release-safety failure.
