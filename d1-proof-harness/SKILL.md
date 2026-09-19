---
name: d1-proof-harness
description: >-
  The self-booting, zero-CI integration-proof pattern for any Cloudflare Worker
  + D1 build: one .mjs test file per capability that kills the port, wipes local
  D1, applies migrations, builds, spawns `wrangler dev` DETACHED, polls /health,
  drives the REAL HTTP API with a hand-rolled ok() harness, then reaps the whole
  process GROUP — plus a node:sqlite D1-compatible shim so Worker lib modules run
  UNMODIFIED offline. No test framework, no CI. This packages the house "no fake
  PASS" discipline as reusable tooling. Use WHENEVER you need to prove a Worker
  actually works: "prove it works", "add a proof/integration test", "test the
  worker end to end", "no fake PASS", "test against real HTTP not mocks", "spin
  up wrangler dev and hit it", "why is the proof hanging / zombie on the port",
  "unit-test the D1 logic offline", or standing up the proof:* script suite for a
  new build. Backend/tooling pattern; the most portable asset in a wrangler+D1
  repo — only the seed SQL and assertions change per capability. Guardrails: the
  BSD-safe port kill (`lsof -ti … | while read p; do kill -9 $p; done`, NOT
  `xargs -r` which is GNU-only) both before AND after the run; kill the detached
  process GROUP (`process.kill(-dev.pid,'SIGKILL')`) or a zombie workerd holds
  the port and the next boot hangs; requires node ≥ 22.5 for node:sqlite.
---
# d1-proof-harness — self-booting real-HTTP proofs, no CI

## What it is / when to use
A pattern (not a library) for proving a Cloudflare Worker + D1 app end to end
with plain Node and Wrangler — no Vitest/Jest, no GitHub Actions. Each capability
gets one `*.test.mjs` that boots a fresh local worker, drives its **real** HTTP
API, asserts, and cleans up after itself. Reach for it whenever a claim needs to
be backed by observed behavior rather than a green checkmark, and whenever you
want to unit-test D1 logic offline without deploying.

Two tools:
1. **The integration harness** — boot `wrangler dev` for real, hit it over HTTP.
2. **The node:sqlite D1 shim** — run Worker `lib/*.mjs` modules against a local
   `.db` file, unmodified, for fast offline unit tests of pure logic (routing, scoring).

## Reference implementation (Wavelygth — patterns only, no client data)
- `~/Projects/clients/wavelygth/worker/lib/_proof/companion-token.test.mjs` — the **canonical** integration harness (boot → seed → real HTTP → reap). Read this first.
- `~/Projects/clients/wavelygth/worker/lib/_proof/google-connect.test.mjs` — same harness + a **mock external service** (an in-process `http.createServer`) that the Worker is pointed at via env/settings-overridable URLs. Copy this when the feature calls out to a third party.
- `~/Projects/clients/wavelygth/worker/lib/_proof/clearances.test.mjs` **L21** — the **BSD-safe** `killPort` (`while read p; do kill -9 $p; done`).
- `~/Projects/clients/wavelygth/worker/lib/_proof/d1-node-sqlite-shim.mjs` — the whole ~46-line D1 facade over `node:sqlite` (+ a tiny `fakeR2()`).
- `~/Projects/clients/wavelygth/package.json` `scripts` — the `proof:*` runner convention (`"proof:x": "node worker/lib/_proof/x.test.mjs"`).

## How to reapply it
**Copy one test as a template and change only the seed + assertions.** The skeleton:
```js
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { writeFileSync } from 'node:fs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..'); // repo root
const PORT = 8894, B = `http://localhost:${PORT}`;
let pass = 0, fail = 0;
const ok = (n, c, x = '') => { if (c) { pass++; console.log(`  ✓ ${n}`); } else { fail++; console.log(`  ✗ ${n} ${x}`); } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// BSD-safe (macOS): `xargs -r` does NOT exist on BSD — use while-read.
const killPort = () => spawnSync('sh', ['-c', `lsof -ti tcp:${PORT} | while read p; do kill -9 $p; done`], { stdio: 'ignore' });

killPort();                                                                    // free the port BEFORE
spawnSync('rm', ['-rf', join(ROOT, '.wrangler', 'state', 'v3', 'd1')], { stdio: 'ignore' }); // fresh DB
spawnSync('npx', ['wrangler', 'd1', 'migrations', 'apply', 'DB', '--local'], { cwd: ROOT, stdio: 'ignore' });
spawnSync('sh', ['scripts/build-public.sh'], { cwd: ROOT, stdio: 'ignore' });  // if the app has a build step
// Seed by writing a .sql file and executing it (CLI can't take bind params cleanly):
writeFileSync(join(ROOT, '.wrangler', 'seed.sql'), `INSERT INTO … VALUES (…);`);
spawnSync('npx', ['wrangler', 'd1', 'execute', 'DB', '--local', '--file', join(ROOT, '.wrangler', 'seed.sql')], { cwd: ROOT, stdio: 'ignore' });

const dev = spawn('npx', ['wrangler', 'dev', '--port', String(PORT), '--var', 'SOME_FLAG:1'], { cwd: ROOT, stdio: 'ignore', detached: true });
let failed = false;
try {
  for (let i = 0; i < 80; i++) { try { if ((await fetch(B + '/api/health')).ok) break; } catch {} await sleep(500); } // cold boot 20–40s
  // …drive the real API with fetch(); assert with ok(); log in ONE flow…
  console.log(`\n${pass}/${pass + fail} passed`);
  failed = fail > 0;
} catch (e) { console.error('proof error:', e); failed = true; }
finally {
  try { process.kill(-dev.pid, 'SIGKILL'); } catch {}   // kill the GROUP: wrangler → workerd child
  killPort();                                            // and sweep the port AFTER
}
process.exit(failed ? 1 : 0);                            // non-zero exit on any failed assertion
```
Then add `"proof:x": "node worker/lib/_proof/x.test.mjs"` to `package.json` scripts.

**Cookie vs Bearer requests** (auth surfaces): send `origin: B` on cookie
requests (so same-origin/CSRF passes) and send **no** Origin header on Bearer
requests (to prove the token path is CSRF-exempt). Capture the session with
`(r.headers.get('set-cookie')||'').split(';')[0]`.

**Mock an external service** (OAuth, an email provider): stand up an in-process
`http.createServer` on a second port, and point the Worker at it through
env/settings-overridable endpoints — Wavelygth seeds `google_token_url` /
`google_api_base` into `app_settings` so the token exchange and API calls hit
`127.0.0.1:MOCK` instead of the real host. Design your config resolver so every
outbound base URL is overridable; that seam is what makes the flow provable.

**Offline unit tests** — the D1 shim lets a `lib/*.mjs` run against a real file:
```js
import { openD1 } from './d1-node-sqlite-shim.mjs';       // node >= 22.5
const db = openD1(':memory:');                            // or a temp .db path
db.exec('CREATE TABLE t(id TEXT PRIMARY KEY, n INTEGER)');
// db.prepare(sql).bind(...).first() / .all() / .run() — the subset of D1 the module uses.
```

## Gotchas
- **BSD-safe kill.** `lsof -ti tcp:$PORT | xargs -r kill -9` uses GNU `xargs -r`
  (`--no-run-if-empty`), which **does not exist on macOS/BSD** — on an empty
  pipe BSD `xargs` still runs `kill -9` with no args (harmless but noisy) and the
  `-r` flag itself errors. Use `… | while read p; do kill -9 $p; done`, which is
  portable. (Several Wavelygth proofs use the `-r` form and only work because the
  port is usually non-empty; the clearances proof shows the correct form.)
- **Reap the process GROUP, not the pid.** `wrangler dev` spawns a `workerd`
  child. `kill(dev.pid)` leaves that child alive holding the port, so the *next*
  run's `/health` poll never succeeds and the suite hangs. `spawn(..., {detached:true})`
  puts them in one group; `process.kill(-dev.pid, 'SIGKILL')` (negative pid) kills
  the group. Belt AND suspenders: run `killPort()` both before boot and in `finally`.
- **node ≥ 22.5** for `node:sqlite` (the shim's `DatabaseSync`). Older Node has no built-in SQLite.
- **Wipe D1 state each run** (`rm -rf .wrangler/state/v3/d1`) so every proof
  starts from migrations-only — a leftover DB makes tests pass/fail on stale rows.
- **Boot is slow & cold.** Poll `/health` 40–80× at 500 ms; a first-run wrangler
  can take 20–40 s (it may download workerd). If boot never succeeds, temporarily
  flip `stdio` from `'ignore'` to `'inherit'` to see wrangler's error.
- **Seed via a written .sql file**, not inline `--command` with values — you avoid
  quoting hell and can regenerate rows mid-test (e.g. expire a token to prove refresh).
- **Inject time/behavior flags with `--var KEY:VALUE`** (e.g. an "allow all hours"
  flag) so logic gated on wall-clock or environment is deterministically testable.
- **The shim mirrors only the D1 subset the module uses** (`prepare().bind().first()/.all()/.run()`,
  `.exec()`). It is deliberately minimal — extend it if a module needs `.batch()`; don't
  treat it as a full D1. `.first()` returns `null` (not `undefined`) to match D1.
