---
name: solomon-proof-runner
description: >-
  Run and interpret the Solomon / TSS governance and functional proof suite (the
  npm run solomon:* and npm run test:* commands) truthfully. Use this whenever you
  are working in the ronininc/TSS ("Solomon") repository and need to check release
  readiness, verify a capability, decide whether a README/status claim is backed by
  a passing proof, close the August 2 flagship gate, or investigate a failing proof.
  Trigger on phrases like "run the proofs", "is X proven", "check readiness", "flagship
  gate", "readme scope completion", "governance proof", "why is this proof failing",
  or any request to confirm PASS/FAIL/DEFERRED status before updating docs or releasing.
  Solomon's core doctrine is "no fake PASS" — this skill exists so proof status is
  reported from real command output, in the correct build order, never guessed.
---

# Solomon Proof Runner

Solomon (the `ronininc/TSS` repo) is a proof-driven, governed system. Almost every
capability has a matching `npm run solomon:*` proof script that emits an explicit
PASS / FAIL / DEFERRED / CONFIG-HOLD result. The project's release-safety doctrine is
absolute: **a claim is only true if a proof currently passes.** Your job when this skill
is active is to run the right proofs, in the right order, and report their *real* results
— never to infer, assume, or soften a result to make progress look better.

Read this file, then consult `references/proof-taxonomy.md` for the full categorized
command list and which proofs back which README claims.

## The one rule that matters most

Never report a proof as passing unless you have just seen it pass in command output in
the current environment. If you did not run it, its status is `UNVERIFIED`. If it failed,
it is `FAIL`. If it is deferred by design, it stays `DEFERRED`. This mirrors Solomon's own
Final Principle ("never claim validated when unproven") — you are held to the same standard
the system is. Fabricating or rounding-up a proof result is the single worst outcome here,
worse than reporting that something is still broken.

## Environment setup (do this first, once)

Most proofs are TypeScript runners invoked through the repo's vendored `tsx`, e.g.
`node --experimental-sqlite ./server/node_modules/tsx/dist/cli.mjs tests/<name>/run.ts`.
That path only exists after server dependencies are installed. So before running any
proof in a fresh clone:

```bash
npm install
npm --prefix server install
npm --prefix app install
```

Functional proofs also expect the build outputs to exist. If a proof complains about a
missing `dist/`, `runtime/`, or packaged artifact, build first:

```bash
npm run build:server
npm run build:app
```

Windows-only proofs (`package:win`, `solomon:doctor` which is a PowerShell script,
NSIS installer proofs) cannot PASS on Linux/macOS. On a non-Windows host, report those as
`DEFERRED (platform: not Windows)` rather than FAIL — an unrunnable proof is not a failing
proof, and the README's release rules explicitly forbid claiming a Windows/macOS package
PASS unless proven in the current environment.

## How to run a proof and read the result

1. Run the exact npm script (see `references/proof-taxonomy.md`).
2. Capture full stdout/stderr. Do not truncate away the verdict line.
3. Classify the outcome using the vocabulary below. Look for the script's own explicit
   markers (PASS/FAIL, `✓`/`✗`, exit code) rather than skimming prose.
4. If ambiguous, treat it as `UNVERIFIED` and say why — do not guess.

Status vocabulary (use these exact words in reports):

- `PASS` — the proof ran to completion and declared success in this environment.
- `FAIL` — the proof ran and declared failure, or exited non-zero.
- `DEFERRED` — intentionally not yet proven (reserved future capability, or platform
  mismatch). Carries a short reason, e.g. `DEFERRED (voice: no manual proof)`.
- `CONFIG-HOLD` — blocked only on configuration/keys/unlock, not on code. External
  Provider Reasoning is the canonical example.
- `UNVERIFIED` — not run this session, or output was ambiguous. Never upgrade this to
  PASS without a real run.

## Recommended run orders

For a fast readiness read, start with the aggregate gates before the individual proofs —
they fan out and tell you where to dig:

1. `npm run solomon:readiness`
2. `npm run solomon:aug2-flagship-gate-runner`
3. `npm run solomon:flagship-functional-closure-proof`

For "is the README's claim about capability X real?", map X to its backing proof via
`references/proof-taxonomy.md`, run only that proof, and report the verdict. This is far
faster than running the whole suite and is the common case when syncing docs.

For a full pre-release sweep, run the Core release proofs group, then the Flagship
functional group, then the Governance/integrity group (see taxonomy). Aggregate into a
single status matrix.

## Side-effectful commands — never run without explicit approval

Proofs are read-only and safe to run freely. These are NOT proofs — they publish, upload,
promote, or deploy, and can change real release state or hit external services. Treat every
one as requiring an explicit, in-chat "yes" from the operator before running, and surface
exactly what it will do first:

- `solomon:promote-release`
- `solomon:release:build`, `solomon:release:full`
- `solomon:release:upload-win`, `solomon:release:verify-win`
- `solomon:release:cloudflare`, `solomon:release:cloudflare:validate`

Internet proofs are a middle case: `solomon:internet-proof` performs a real
operator-approved outbound fetch. Run the `validate:` variants freely, but only run the
`--approved` fetch when the operator has approved it in chat, and say so in the report.

## Reporting format

Produce a compact status matrix, one row per proof you actually ran:

```
CAPABILITY                     PROOF                                       RESULT
Project Twin restore           solomon:project-twin-restore-proof          PASS
Voice flagship functional      solomon:voice-flagship-functional-proof     DEFERRED (no manual proof)
External Provider Reasoning    solomon:online-validation-proof             CONFIG-HOLD
```

Then a one-line honest summary and, if asked to gate a release, an explicit
`RELEASE POSTURE:` line that does not overstate what was proven. When a proof fails,
capture the failing assertion / first error so the fix is actionable — a FAIL with no
evidence wastes the next person's time.

## Investigating a failing proof

Read the proof script it points to (`scripts/solomon-*.mjs` or `.ts`, or `tests/<name>/run.ts`)
to see what it actually asserts, then trace to the runtime code under `server/` or `app/`.
Report the specific assertion that failed and the smallest true statement about why. Do not
"fix" a proof by loosening its assertion to make it pass — that violates the no-fake-PASS
doctrine and is almost never what the operator wants.
