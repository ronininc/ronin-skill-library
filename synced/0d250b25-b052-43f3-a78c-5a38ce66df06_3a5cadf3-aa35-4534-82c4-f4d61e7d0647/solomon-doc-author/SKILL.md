---
name: solomon-doc-author
description: >-
  Write and extend Solomon / TSS governance documents — the SOLOMON_*.md docs, README
  sections, RELEASE_* reports, glossary entries, and doctrine text — in the project's exact
  constitutional voice and Truth Envelope structure. Use this whenever you are authoring or
  expanding narrative/doctrine content in the ronininc/TSS repo: a new SOLOMON_TOPIC.md doc,
  a glossary term, a runbook, a mission/principle/roadmap section, or customer-facing copy.
  Trigger on "write a Solomon doc", "add a doctrine section", "document the connector grants",
  "draft the runbook", "write the glossary entry for X", or "make this read like the rest of
  the README". This governs the prose only — for status markers driven by proofs, use
  solomon-readme-sync; for running/creating proofs, use the solomon-proof-runner/authoring skills.
---

# Solomon Governance Doc Author

Solomon's documentation is written as doctrine, not marketing. It reads like a constitution:
short declarative lines, one claim per line, uncertainty made explicit, and never a claim the
system can't back. When you add a doc or section, it must be indistinguishable in voice and
discipline from the existing README and `docs/SOLOMON_*.md` files. This skill captures that
voice so new docs land right the first time.

If the content includes capability status (ACTIVE / PASS / DEFERRED), that part is governed by
`solomon-readme-sync` and must be driven by real proof output — do not hand-write a positive
status here.

## Voice

- **Short declarative lines.** Frequently one sentence per line with blank lines between, e.g.
  "Governance is the product." / "Planning remains planning." / "Reality does not negotiate."
  This cadence is deliberate; match it in doctrine sections.
- **Define before use.** New architectural terms get a glossary-style definition. Treat terms
  as architectural concepts, not implementation details.
- **Truth Envelope thinking.** Distinguish facts, assumptions, unknowns, constraints,
  confidence, authority, and execution state explicitly. If evidence is insufficient, say so.
- **No hype, no superlatives without backing.** The system optimizes for governed understanding
  over convincing language; the docs must do the same.
- **Terse section stubs for prose, tables for status.** Narrative doctrine flows as lines;
  status/capability matrices are compact rows (`Capability: STATE`).

## The non-negotiable claim discipline

Every Solomon doc inherits the Final Principle. Never write that the system is:

- online when it may be offline,
- remembered when it was not retrieved,
- fabricated when it was estimated,
- deployed when it was only scaffolded,
- validated when it is unproven,
- manufacturing-ready when it is planning-only (Fabrication is planning-only),
- autonomous when operator confirmation is required.

Reserved future Twins (MERCHANT, ORGANIZATION, COMMUNICATION, MEETING, DECISION, TASK,
CREDENTIAL, FINANCIAL, FABRICATION, DEPLOYMENT) and reserved nodes (Titan, Kingmaker,
Operations Command, GMF) are described only as **future / deferred**, never as active runtime.
On the public site specifically, Kingmaker must not be named at all, and Titan appears only as
"Titan (future) … not implemented, not active runtime."

## Structure to reuse

Solomon docs tend to follow: a one-line statement of what the thing is → what it is *not* →
its responsibilities → its governance constraints → what remains deferred. The "what it is not"
list is a signature move (see the Executive Summary's "It is not a chatbot…"). Use it to fence
scope and prevent overclaiming.

For a new `docs/SOLOMON_<TOPIC>.md`, a reliable skeleton:

```markdown
# <Topic>

<One-line definition of what this is.>

## What This Is Not
<Bullet-free declarative lines fencing the scope.>

## Responsibilities
<What the subsystem is accountable for.>

## Governance Constraints
<Fail-closed behavior, operator authority, audit/evidence requirements.>

## Proof
<Which solomon:* proof backs each claim, or DEFERRED with a reason. Driven by real proof output.>

## Deferred
<What is explicitly not yet proven and must not be claimed.>
```

## Glossary entries

Match the existing glossary exactly: term as an H-level heading, then short declarative
definition lines, then (where useful) a bulleted list of sources/examples, then a closing
one-line invariant ("Authority is never fabricated." / "Evidence is always distinguished from
assumptions."). Keep them architectural and implementation-neutral.

## Before you finish

Read the draft against a neighboring existing doc. If any sentence sounds like a product
brochure, promises a reserved/deferred capability as active, or states a status not backed by a
proof, rewrite it down to what is true. A Solomon doc that honestly marks its limits is correct;
one that reads impressively but overclaims is a governance failure.
