---
name: solomon-proof-authoring
description: >-
  Author NEW Solomon / TSS governance and functional proofs in the repo's exact house
  pattern — a scripts/solomon-*.mjs (or .ts) proof, an optional tests runner under tests/,
  and the package.json wiring — so a currently-unproven capability can be driven to a real
  PASS. Use this whenever you are in the ronininc/TSS repo and need to close a "proof is
  missing / not fully proven" blocker (e.g. Persona Router invariance, Source Triage
  accepted/rejected metadata), add a proof for a newly built capability, or convert a manual
  check into an automated deterministic proof. Trigger on "write a proof for X", "add a
  governance proof", "close the missing-proof blocker", "the persona router proof is missing",
  "wire up a new solomon: proof script", or "make X provable". A capability without a proof
  cannot be claimed in the README, so authoring the proof is how the flagship actually closes.
---

# Solomon Proof Authoring

In Solomon, a capability is only "done" when a deterministic proof asserts it and passes.
Several README blockers are literally *missing proofs*. Closing them means writing a new
proof in the repo's established pattern — not loosening an existing one, and not writing a
proof that trivially passes. A good proof fails loudly when the capability regresses; a
proof that can't fail proves nothing.

To run/interpret proofs, pair this with `solomon-proof-runner`. This skill is about
*creating* them.

## The house proof pattern (`scripts/solomon-<name>-proof.mjs`)

Solomon proofs are self-contained Node scripts that read real source/artifacts, run a list
of named boolean checks, write a JSON report to `.test-runtime/proofs/<name>.json`, print
it, and set a non-zero exit code on any failure. Follow this exact shape so the proof reads
like the others and `solomon-proof-runner` can classify it:

```js
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const proofDir = path.join(root, '.test-runtime', 'proofs');
const proofPath = path.join(proofDir, '<name>-proof.json');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

const checks = [];
function add(name, passed, details = {}) {
  checks.push({ name, status: passed ? 'PASS' : 'FAIL', passed, ...details });
}

// 1. Read the REAL artifacts the claim depends on (source files, generated output,
//    package.json, audit logs). Never hard-code the answer.
const source = read('server/src/runtime/<relevant-file>.ts');
const packageJson = JSON.parse(read('package.json'));

// 2. Assert observable, regression-catching properties.
add('<capability> defines the governed invariant', source.includes('<REQUIRED_CONSTANT>'));
add('<capability> fails closed on missing authority', source.includes('INTERNET_BLOCKED') /* etc */);

// 3. Self-register: prove the script is wired into package.json.
add('proof script is registered',
  packageJson.scripts?.['solomon:<name>-proof'] === 'node scripts/solomon-<name>-proof.mjs');

const failed = checks.filter((c) => !c.passed);
const report = {
  status: failed.length ? '<NAME>_FAILED' : '<NAME>_PASS',
  checkedAt: new Date().toISOString(),
  checks,
  blockers: failed.map((c) => c.name),
};
fs.mkdirSync(proofDir, { recursive: true });
fs.writeFileSync(proofPath, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
process.exitCode = failed.length ? 1 : 0;
```

Key conventions, drawn from existing proofs (e.g. `solomon-native-internet-boundary-proof.mjs`):

- One explicit `status` string ending in `_PASS` or `_FAILED`, plus a `blockers` array naming
  each failed check. This is what human status docs and the runner read.
- Every check has a human-readable name that states the invariant, so a failure is
  self-explanatory ("operator approval is required for live proof/fetch").
- Prove **negatives** too, using denylist-style assertions — e.g. "source does NOT import an
  external LLM provider adapter", "output does NOT contain forbidden term". Solomon proofs
  routinely assert what must be absent, not only what must be present.
- Include a self-registration check asserting the exact `package.json` script string, so a
  proof can't drift out of the build without failing.
- Write the report under `.test-runtime/` — which is gitignored (see Repository Rules), so
  proof artifacts never get committed.

## The runner pattern (`tests/<name>/run.ts`)

For proofs that need to exercise runtime behavior with SQLite/state, add a TypeScript runner
under `tests/<name>/run.ts` and invoke it through the vendored tsx, matching sibling tests:

```json
"test:<name>": "node --experimental-sqlite ./server/node_modules/tsx/dist/cli.mjs tests/<name>/run.ts",
"solomon:<name>-proof": "node scripts/solomon-<name>-proof.mjs"
```

Some proofs are pure `.ts` run directly through tsx (see the many
`node --experimental-sqlite ./server/node_modules/tsx/dist/cli.mjs scripts/solomon-*.ts`
entries). Mirror whichever form the nearest existing proof for that subsystem uses rather
than inventing a third style.

## Wiring checklist

When you author a proof, do all of these or the proof is only half-real:

1. Create `scripts/solomon-<name>-proof.mjs` (or `.ts`) following the pattern above.
2. If runtime state is needed, create `tests/<name>/run.ts`.
3. Add the `solomon:<name>-proof` (and any `test:<name>`) entry to `package.json` scripts.
4. Make the proof self-register (assert its own package.json entry).
5. Run it and confirm it PASSES for real — and, critically, temporarily break the underlying
   invariant to confirm it FAILS. A proof you haven't seen fail is not yet trustworthy.
6. If this proof backs a README claim, hand off to `solomon-readme-sync` to update the status
   line — only after you've seen the proof pass.

## Anti-patterns to avoid

- Do not write a check that is always true (`add('exists', true)`) or that asserts a constant
  you just wrote in the same file with no external anchor. This creates a fake PASS, the exact
  thing Solomon's doctrine forbids.
- Do not weaken or delete an existing failing proof to make the suite green. Fix the code, or
  mark the capability DEFERRED honestly.
- Do not require external provider keys / network for a proof that is supposed to validate the
  local, offline-first path — mirror how `native-internet-boundary-proof` asserts provider env
  tokens are *absent* during the proof run.
- Do not commit anything under `.test-runtime/`, `runtime/`, `dist/`, or `data/`.

## Worked example: closing the Persona Router invariance blocker

README lists "Persona Router invariance proof is missing." A faithful proof would:
read `tests/persona-router/run.ts` and the persona-router runtime source; assert that
identical governed input yields identical routing regardless of persona (the invariance
property); assert routing is deterministic across repeated runs; assert no persona can escalate
authority; self-register `solomon:persona-router-invariance-proof`; write the report; exit
non-zero if any invariance check fails. Then verify it fails when you perturb the router, and
passes on the real code — and only then let `solomon-readme-sync` flip the status.
