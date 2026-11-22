---
name: solomon-engine-verifier
description: >-
  Run a standardized verifier checklist for each Solomon / TSS engine and node (Solomon
  Runtime, Digital Twin Engine, Decision Engine / Truth Envelope, CodeGen, Fabrication,
  CRM / Merchant, Voice, Native Internet, Evidence & Screenshot, Project Twin, Build Tree),
  and capture the required evidence — which for every engine MUST include a screen recording
  with audio. Use this whenever you need to verify one or more Solomon engines end to end,
  produce release/flagship sign-off evidence, prove an engine works on real hardware (not just
  that its automated proof passes), or attach an audited A/V capture to a Project Twin. Trigger
  on "verify the engines", "engine verifier checklist", "sign off engine X", "record proof of X
  working", "screen recording with audio", or "does CodeGen / Fabrication / CRM actually work".
  Automated proofs are necessary but not sufficient; this skill pairs each engine's proof with an
  observable functional checklist and an audited screen+audio recording so a claim is real.
---

# Solomon Engine Verifier

An automated `solomon:*` proof tells you the code asserts an invariant. It does not show a human
that the engine actually works — the workspace renders, the governed workflow runs, the Truth
Envelope appears, the voice speaks. Solomon's Evidence Screenshot Workspace doctrine already
treats evidence as first-class and attaches it to the Twin. This skill extends that discipline
into a repeatable, per-engine verifier checklist whose evidence, for every engine, includes a
**screen recording with audio capture**. The recording is what turns "the proof passed" into
"here is the engine working, watched and heard."

Pair this with the other Solomon skills: `solomon-proof-runner` executes the proof commands,
`solomon-readme-sync` records the resulting status, and the engine-specific
`solomon-voice-verification` / `solomon-native-internet` skills carry the deep checks this
skill references.

## How to use this skill

1. Pick the engine(s) to verify. Read its checklist in `references/engine-checklists.md`.
2. Run the engine's automated proof(s) via `solomon-proof-runner`. Record real PASS/FAIL.
3. **Start a screen recording with audio** (see `references/av-capture.md`), then perform the
   engine's functional checklist live so the recording captures it. Narrate what you are doing
   out loud — the audio track is part of the evidence, and for Voice it is the evidence.
4. Stop the recording, compute its audit hash, and register the evidence with a capture-state.
5. Emit the engine verdict line. An engine is only "verified" when its proof passes AND the
   functional checklist passed on camera AND the recording exists with capture-state CAPTURED.

## The screen-recording-with-audio requirement (mandatory, every engine)

This is the non-optional part. Every engine verification produces one A/V artifact.

- **What it must contain:** the screen showing the engine's workspace/workflow, plus a live
  audio track. Audio is the operator narrating each checklist step ("creating a Project Twin…
  now saving… now restoring without re-running research…"). For the Voice engine the audio must
  also contain the actual spoken request and the TTS response.
- **Duration:** long enough to show every checklist item for that engine, start to finish, in
  one continuous take. Do not stitch clips — a single take is harder to fake and matches the
  "no fake PASS" doctrine.
- **How to capture:** use the exact OS-specific commands in `references/av-capture.md`
  (ffmpeg-based, cross-platform, plus native fallbacks). Screen + system audio + microphone.
- **Where it goes:** save under an evidence path (e.g. `.test-runtime/evidence/<engine>/`,
  which is gitignored) — never commit the media into the repo.
- **Audit + attach:** compute `sha256` of the file, record `{engine, file, sha256, durationSec,
  captureState, capturedAt, checklistItemsShown[]}`, and attach it to the Project Twin exactly
  as screenshot evidence is attached today.

### Capture-state vocabulary (reuse the workspace's own terms)

- `CAPTURED` — a real screen+audio recording exists and shows the checklist.
- `NOT_CAPTURED` — no recording was made. The engine is then UNVERIFIED, regardless of proof.
- `FAILED` — capture was attempted but the file is unusable (no audio track, corrupt, empty).
- `UNSUPPORTED` — the environment cannot record (e.g. headless CI, no audio device). Say so
  honestly and mark the engine DEFERRED for A/V evidence rather than claiming it verified.

Never report an engine as verified with capture-state anything other than `CAPTURED`. A missing
or audio-less recording is the same as no evidence.

## Per-engine checklist (summary — full detail in references/engine-checklists.md)

Each engine's checklist has the same five parts: **Proof** (automated command), **Functional
checks** (what a human must observe pass), **Governance invariants** (what must remain true /
absent — e.g. no auto-execute, planning-only, fail-closed), **Recording must show** (the specific
moments the A/V capture has to contain), and **Verdict**.

Engines covered:

1. Solomon Runtime (governance core / deterministic routing / audit)
2. Digital Twin Engine (intent → Twin → workspace)
3. Decision Engine & Truth Envelope
4. CodeGen (constraint discovery → Project Twin → Build Tree, planning-not-execution)
5. Fabrication (planning-only boundary; no CAD/render/manufacturing claims)
6. CRM / Merchant
7. Voice (mic → STT → governed runtime → Truth Envelope → TTS; audio is the proof)
8. Native Internet (approved fetch, fail-closed, lanes separated)
9. Evidence & Screenshot workspace (capture-state truthfulness)
10. Project Twin & Build Tree (persist, restore without re-running research, export)

Read the full checklist for an engine before verifying it — the summary is not enough to sign off.

## Reporting

Produce one row per engine plus its evidence:

```
ENGINE                    PROOF                                       FUNCTIONAL   RECORDING            VERDICT
Digital Twin Engine       test:digital-twin-engine                    PASS         CAPTURED (av <hash>) VERIFIED
Decision Engine / TE      truth-envelope-decision-engine-flagship     PASS         CAPTURED (av <hash>) VERIFIED
Voice                     voice-flagship-functional-proof             DEFERRED     UNSUPPORTED          DEFERRED (no audio device)
Fabrication               fabrication-flagship-functional-proof       PASS         CAPTURED (av <hash>) VERIFIED (planning-only)
```

Then a single honest closure line, e.g.
`ENGINES VERIFIED: 8/10 (Voice DEFERRED: no audio device; CRM DEFERRED: merchant sandbox offline)`.
Hand the PASS/DEFERRED results to `solomon-readme-sync` to update the README status — and only
mark an engine ACTIVE/VERIFIED there if this skill produced a CAPTURED recording for it.

## The rule that ties it together

A green proof with no recording is UNVERIFIED. A recording with no audio is FAILED. A recording
that shows the workspace but skips a checklist step does not verify that step. Verification means
proof + observed function + audited screen-and-audio recording, together. Anything less gets the
honest lower status — which is a correct outcome, not a failure of this skill.
