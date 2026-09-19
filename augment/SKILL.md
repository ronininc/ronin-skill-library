---
name: augment
description: >-
  Offload MECHANICAL, bulk, or classification work to a local model via the `augment` CLI instead of
  generating it inline — so it costs zero Anthropic tokens and saves Claude usage limits. Reach for
  this WHENEVER about to hand-produce something a small model can draft: boilerplate, a config/schema/
  type/test stub, a first-draft function or refactor, a D1 migration + matching proof stub, or an
  "explain/review this file" pass; AND whenever the task is a typed DECISION over text — classify,
  score, or yes/no (e.g. "is this a lead or a customer", "rate urgency 1-5", "does this handle nulls")
  — use `augment judge` for a calibrated answer. Also trigger on the user saying "use augment",
  "offload this", "do it locally", "don't burn my limits", or "save tokens". The local model DRAFTS;
  Claude REVIEWS and integrates. Keep hard reasoning, architecture, security-critical code, and
  anything correctness-critical on Claude — never blind-trust local output.
---

# augment — local-model helper (save Claude limits)

`augment` is a local-first CLI (on PATH; repo `~/Projects/offline-augment`, also
`ronininc/offline-augment` on GitHub) that reuses Solomon's routing + model
selection + egress gate to run work on a local Ollama model. Use it to move
mechanical work OFF Claude's usage budget.

## The division of labor (this is the whole point)

| Offload to `augment` (local, free) | Keep on Claude |
|---|---|
| boilerplate, config, schema/type/test stubs | architecture & design decisions |
| first-draft function / refactor | tricky bugs, subtle logic |
| D1 migration + proof-harness stub (`scaffold`) | security/auth/money/tenancy code |
| explain / review a file | anything correctness-critical, unreviewed |
| classify / score / decide over text (`judge`) | multi-step reasoning |

Always **review** local output before integrating — small models draft, they
don't finish.

## Commands

```bash
augment health                         # ollama up? which models, escalation policy
augment "write a debounce in TS"       # ask: streams an answer, local-first
augment gen "<spec>" -o FILE --yes     # generate a file (auto-picks a fitting coder)
augment edit FILE "<change>" --yes     # rewrite a file (LOCAL ONLY, never egresses)
augment explain FILE                   # summarize a file (local only)
augment review FILE                    # bug/risk pass (local only)
augment judge "<question>" --type bool|choice|score [--options a,b,c] [--levels N]
augment scaffold "<spec>" --name SLUG --table NAME   # D1 migration + proof stub, house pattern
cat data | augment "<prompt>"          # stdin as context (sensitive → local only)
```

## The limit-saving loop (how Claude uses it)

For a mechanical subtask, shell out instead of typing it yourself:

```bash
augment gen "a zod schema for User { id, email, createdAt }" -o user.ts --yes -m qwen2.5-coder:7b
```

then Read the file, verify it, and fix edge cases. The generation cost no
Anthropic tokens. For a decision, `augment judge "..." --type choice --options ...`
returns `{value, confidence, reason}` as JSON you can branch on.

## Non-negotiables

- **Source stays local.** `edit`/`explain`/`review`/`scaffold`, refactors, and
  piped stdin are marked sensitive — Solomon's egress gate refuses all cloud
  tiers. Never pass proprietary source to a cloud tier.
- **Calibration ≠ correctness.** A small local model (esp. the 8GB tier) can be
  confidently wrong. Gate on `confidence`, pin a stronger model with `-m` for
  high-stakes calls, keep `judge` for SEMANTIC decisions (arithmetic → code).
- **Drafts, not deliverables.** Review `gen`/`edit`/`scaffold` output; the SQL
  from `scaffold` is a starting draft (it validates in SQLite but review it).
- **8GB gotcha:** repeated model loads can crash ollama — if a call says "local
  model unreachable", run `ollama serve` and retry.
- **Model quality is host-bound.** On a bigger machine `augment` auto-climbs to a
  stronger coder; no code change needed.

## When NOT to reach for it

Hard reasoning, architecture, security/money/tenancy code, or anything where a
confidently-wrong draft would be worse than spending the tokens. Those stay on
Claude.
