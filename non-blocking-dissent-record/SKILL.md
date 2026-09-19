---
name: non-blocking-dissent-record
description: >-
  A governance artifact for a multi-owner / partnership system: record one party's OBJECTION to a proposed
  action as a timestamped "logged verdict" that does NOT block the action (no paralysis) but shifts the
  consequences — the party that proceeds over a recorded dissent bears SOLE risk and liability, indemnifies
  the dissenting party (and, optionally, its owner personally) and the joint entity, and takes the economics
  of that action for its own account instead of a normal split. Validity turns on CONTEMPORANEITY: the record
  is valid evidence only if it was made BEFORE the action proceeded; a later objection is just a complaint,
  with no risk-shift protection. Ships as pure types + pure functions: build the record (compute the
  proceeding party, the contemporaneity flag, and the consequences), validate its structure, and test
  "is this valid dissent evidence?". Use WHENEVER a system must let one owner/partner formally disagree
  without stopping the other — "record my objection but let them proceed", "logged veto that shifts liability
  not a hard block", "proceed-at-your-own-risk record", "partner dissent evidence", "warn-then-commit
  governance", "who bears the risk if we do it anyway", or a JV/co-owner decision trail. It COMPLEMENTS
  append-only-audit-log (this is the specific decision-dissent event, with computed consequences + a validity
  gate, that you APPEND there), and it is the OPPOSITE of a hard gate like confirmed-inputs-decision-gate /
  governed-operator-console (those BLOCK until satisfied; this never blocks — it reallocates risk). Guardrail:
  it is a governance/evidence artifact, NOT legal advice — strip any specific party names, owners, and
  contract section numbers and parameterize them; the two parties, the owner-of map, and the exact
  consequences are configuration.
---
# Non-Blocking Dissent Record

## What it is / when to use / what it composes with
Encodes the "one party can object on the record, but a single objection never paralyzes the other" governance
pattern (warn → commit). A dissent doesn't stop the action; it moves the risk, liability, and economics onto
whoever proceeds over it — and it only counts as protective evidence if it was logged *before* the action.

- **`append-only-audit-log`** is where this record lands as an immutable event; this skill is the specific
  shape + the computed consequences + the contemporaneity validity check that log entry carries.
- **Opposite of a hard gate:** `confirmed-inputs-decision-gate` and `governed-operator-console` BLOCK an action
  until a condition is met. This never blocks — its whole purpose is "no paralysis," reallocating risk instead
  of stopping the other party.

## Reference implementation — exact source
`~/Projects/Kingmaker/contracts/record-of-dissent.ts` (pure types + pure functions, no I/O):
- **Build the record:** `createRecordOfDissent(input)` — `:70-98`. Computes the *proceeding* party as the
  OTHER party (an `OTHER_MEMBER` map), sets `contemporaneous = actionStartsAt ? recordedAt <= actionStartsAt
  : true` (`:74`), and attaches the consequences: `proceedingMemberBearsSoleRiskAndLiability:true`,
  `dissentingMemberBearsNoLiability:true`, an `indemnifies` list (the dissenting party, its owner personally,
  the joint entity), `economics:'PROCEEDING_MEMBER_OWN_ACCOUNT'`, and `blocksAction:false` (`:85-96`).
- **Structural validation:** `validateRecordOfDissent(record)` — `:103-113` (required fields non-empty, the
  two parties are distinct, `recordedAt` is a valid ISO timestamp) → `{valid, blockers[]}`.
- **Evidence gate:** `isValidDissentEvidence(record)` — `:120-122`: valid structure AND
  `contemporaneous === true`. A non-contemporaneous record is explicitly NOT the protective evidence.
- **Config maps to parameterize:** `OTHER_MEMBER` and `OWNER_OF` — `:22-23` (in the source these are two named
  parties + their owners; genericize them).

## How to reapply
- **Parameterize the parties.** Replace the hard-coded party ids, the owner-of map, and any contract-section
  labels with configuration: `{ parties: [A, B], ownerOf: {A, B}, consequences, bindingRefs }`. The technique
  is the two-party risk-shift + contemporaneity gate — nothing about it is specific to any one agreement.
- **Enforce contemporaneity honestly.** Capture `recordedAt` server-side at the moment of logging and, when
  you know it, `actionStartsAt`; compute (don't accept) the `contemporaneous` flag. Only a record that
  precedes the action is protective evidence.
- **Append, don't mutate.** Write the finished record into `append-only-audit-log`; never edit it afterward —
  its value is that it's a contemporaneous, immutable artifact.

## Unwired — bindings you must add
Pure functions only. To use it: expose a `POST /dissent` action (operator-authenticated) that builds the
record with a server timestamp, validates it, and appends it to the audit log; surface recorded dissents in
the operator console read-only. Do NOT add an edit/delete route (it would destroy the evidence property).

## Gotchas (from the code)
- **It must NOT block.** `blocksAction` is `false` by construction (`record-of-dissent.ts:94`) — if your
  implementation ever halts the other party on a dissent, you've built a veto, not this pattern.
- **Contemporaneity is the whole game.** A dissent logged after the action carries no risk-shift protection —
  `isValidDissentEvidence` returns false for it (`:120-122`). Timestamp at capture, not from client input.
- **The two parties must differ.** The proceeding party is the *other* one; validation rejects a record where
  they're equal (`:110`).
- **Not legal advice, and strip the specifics.** The source mirrors one specific agreement (named parties,
  owners, section numbers). Capture ONLY the mechanism; never carry those names into a build.
