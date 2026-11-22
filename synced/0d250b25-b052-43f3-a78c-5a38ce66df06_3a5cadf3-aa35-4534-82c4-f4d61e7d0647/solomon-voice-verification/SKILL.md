---
name: solomon-voice-verification
description: >-
  Verify Solomon / TSS native voice interaction end to end and decide truthfully whether the
  voice stack can be claimed or must stay DEFERRED. Use this whenever you need to check voice
  in the ronininc/TSS repo: the mic to speech-recognition to governed-runtime to Truth Envelope
  to text-to-speech loop, whether voice auto-executes (it must not), whether risky workflows
  require confirmation, or whether the voice flagship proof can pass. Trigger on "verify voice",
  "does voice work", "test the voice stack", "native voice interaction", "whisper bridge",
  "voice governance proof", "can we mark voice as done", or "is voice still deferred". Voice is
  Solomon's primary interface but is DEFERRED until a real manual hardware proof exists, so this
  skill separates what automated proofs cover from what still needs a human at a microphone.
---

# Solomon Voice Verification

Voice is Solomon's intended primary interface, but the README keeps it **DEFERRED / NOT PROVEN**
because passing automated governance tests is not the same as a human speaking into a real
microphone and getting a governed spoken response. This skill exists to run the automated voice
proofs, then honestly identify the manual gap, so voice is only ever claimed when it is truly
proven. The governing rule: voice changes the interface, never the governance — it must not
auto-execute, and risky workflows still require explicit confirmation.

Use `solomon-proof-runner` to actually execute the commands below; use `solomon-readme-sync` to
record the resulting status.

## The interaction loop being verified

```
Microphone -> Speech Recognition -> Governed Runtime -> Workflow Classification
           -> Project Twin Update -> Truth Envelope -> Governed Recommendation
           -> Text-to-Speech -> User
```

Every stage must preserve governance. The transcript is editable before submit; voice shares the
same governed submit path as typed input; TTS may speak the response but governance metadata
stays visible; nothing executes without confirmation.

## Layer 1 — automated proofs (necessary, not sufficient)

Run these and record real verdicts:

| Command | Verifies |
|---|---|
| `npm run solomon:voice-governance-proof` | Governed voice submit path; the milestone `GOVERNED_VOICE_WORKFLOW_PASS` |
| `npm run solomon:voice-stack-proof` | Voice stack assembly |
| `npm run solomon:voice-runtime-proof` | Voice runtime behavior |
| `npm run solomon:voice-flagship-functional-proof` | Voice flagship functional path |
| `npm run solomon:voice-transcript-proof-runtime` | Transcript is captured/editable before submit |
| `npm run solomon:whisper-bridge-proof` | Whisper STT bridge |
| `npm run solomon:local-stt-adapter-proof` | Local STT adapter (offline-first) |
| `npm run solomon:manual-capture-smoke-proof` | Manual capture smoke path |

Governance assertions these should back (verify they are actually checked, not assumed):
voice does not auto-execute; risky workflows require confirmation; voice does not require
external provider tokens (offline-first); transcript is editable pre-submit.

If any of these FAIL, voice stays DEFERRED and you report the failing check — do not round up.

## Layer 2 — the manual hardware proof (the actual blocker)

Automated proofs cannot prove that real speech becomes a governed action on real hardware.
This is why voice is DEFERRED. A truthful "voice works" claim needs a human-in-the-loop capture,
which you should walk the operator through and record as evidence:

1. On the target device with a real microphone, launch the packaged runtime.
2. Speak a benign governed request (e.g. "create a project twin for a coffee cart").
3. Confirm the transcript appears and is **editable before** submit (voice did not auto-submit).
4. Confirm the governed runtime classifies it and returns a Truth Envelope with visible
   governance metadata (facts/assumptions/unknowns/authority/execution state).
5. Speak a *risky* request and confirm it requires explicit confirmation before anything happens.
6. Confirm TTS speaks the response while the governance metadata remains on screen.
7. Capture evidence (screenshot / recording / the audit entry) and attach it to the Project Twin,
   with capture state CAPTURED. If any step could not be performed, mark it NOT_CAPTURED /
   FAILED / UNSUPPORTED honestly.

Only when both layers are satisfied and evidence exists may voice move from DEFERRED to a proven
status. Absent the manual proof, the correct README line remains `Voice Stack: DEFERRED / NOT PROVEN`
and "full voice runtime proof" stays under What Is Deferred.

## Reporting

Produce a two-part verdict: (a) the automated proof matrix with real PASS/FAIL, and (b) the
manual-proof state (done + evidence path, or the specific step that blocks it). Then a single
honest line: either `VOICE: PROVEN (automated + manual evidence <path>)` or
`VOICE: DEFERRED (<reason>)`. Never emit the first form without the manual evidence.

## Failure investigation

For a failing voice proof, read the referenced `scripts/solomon-voice-*.mjs` /
`tests/voice-*/run.ts`, then the voice runtime under `server/`. Report the exact assertion that
failed. Common truthful outcomes: STT adapter missing on the host, no microphone in the
environment (→ DEFERRED, not FAIL), or a governance check (auto-execute / confirmation) genuinely
failing (→ a real bug to fix, never to suppress).
