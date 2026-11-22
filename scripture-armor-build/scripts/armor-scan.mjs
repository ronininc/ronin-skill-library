#!/usr/bin/env node
// armor-scan.mjs — run Scripture Armor's scan layer over a build and give one verdict.
//
//   node armor-scan.mjs                  # files this branch changed vs its base + uncommitted + untracked
//   node armor-scan.mjs --base origin/main
//   node armor-scan.mjs <path>…          # explicit files / directories (walked; .git + node_modules skipped)
//   node armor-scan.mjs … --json         # machine-readable result
//
// Each file goes through `scan.mjs` (the armor's own scanner, unmodified). HTML is classed as data
// by the scanner, so inline <script> blocks are pulled out and scanned as JS on their own.
// Exit: 0 = clean (pass / info / low / medium only), 1 = needs the owner (high or critical finding,
// a binary that couldn't be scanned, or a scanner error), 2 = usage / armor not found.
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, statSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { join, resolve, relative, extname } from 'node:path';
import { tmpdir, homedir } from 'node:os';

const args = process.argv.slice(2);
const flag = (n) => { const i = args.indexOf(n); if (i < 0) return null; const v = args[i + 1]; args.splice(i, 2); return v; };
const asJson = args.includes('--json'); if (asJson) args.splice(args.indexOf('--json'), 1);
const base = flag('--base');
const ARMOR = process.env.SCRIPTURE_ARMOR_HOME || join(homedir(), 'scripture-armor');
const SCAN = join(ARMOR, 'scan.mjs');
if (!existsSync(SCAN)) { console.error(`Scripture Armor not found at ${ARMOR} (set SCRIPTURE_ARMOR_HOME)`); process.exit(2); }

const git = (...a) => { const r = spawnSync('git', a, { encoding: 'utf8' }); return r.status === 0 ? r.stdout.split('\n').filter(Boolean) : null; };
const SKIP = new Set(['.git', 'node_modules', '.wrangler', '.next', 'dist', '.turbo', '.cache']);
function walk(p, out) {
  const st = statSync(p, { throwIfNoEntry: false });
  if (!st) return;
  if (st.isDirectory()) { for (const e of readdirSync(p)) if (!SKIP.has(e)) walk(join(p, e), out); }
  else if (st.isFile()) out.push(p);
}

let files = [];
if (args.length) for (const a of args) walk(resolve(a), files);
else {
  const root = git('rev-parse', '--show-toplevel')?.[0];
  if (!root) { console.error('not in a git repo — pass the files or folders to scan'); process.exit(2); }
  const b = base || (git('rev-parse', '--verify', '--quiet', 'origin/main') ? 'origin/main' : git('rev-parse', '--verify', '--quiet', 'origin/master') ? 'origin/master' : null);
  const mb = b ? git('merge-base', b, 'HEAD')?.[0] : null;
  const names = new Set([
    ...(mb ? git('diff', '--name-only', '--diff-filter=ACMR', mb, 'HEAD') || [] : []),
    ...(git('diff', '--name-only', '--diff-filter=ACMR', 'HEAD') || []),
    ...(git('ls-files', '--others', '--exclude-standard') || []),
  ]);
  files = [...names].map(n => join(root, n)).filter(f => existsSync(f));
}
files = [...new Set(files)];

const tmp = mkdtempSync(join(tmpdir(), 'armor-scan-'));
function scanOne(file, label = file) {
  const r = spawnSync(process.execPath, [SCAN, file], { encoding: 'utf8', maxBuffer: 32 << 20 });
  const out = r.stdout || '';
  if (r.status === 0) {
    try { const rec = JSON.parse(out.slice(out.indexOf('{'), out.lastIndexOf('}') + 1)); return { file: label, ...rec }; }
    catch { return { file: label, verdict: 'error', error: 'unreadable scanner output' }; }
  }
  const msg = (r.stderr || out).trim().split('\n').pop();
  if (/GHIDRA_NOT_FOUND/.test(msg)) return { file: label, verdict: 'unscanned', error: 'compiled binary — needs Ghidra to scan (fails closed)' };
  return { file: label, verdict: 'error', error: msg.slice(0, 300) };
}

const results = [];
let n = 0;
for (const f of files) {
  const rel = relative(process.cwd(), f) || f;
  results.push(scanOne(f, rel));
  if (/\.html?$/i.test(extname(f))) {                    // the scanner calls HTML data; its scripts are code
    const html = readFileSync(f, 'utf8');
    let i = 0;
    for (const m of html.matchAll(/<script\b(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)) {
      if (!m[1].trim()) continue;
      const p = join(tmp, `s${n++}.js`); writeFileSync(p, m[1]);
      results.push(scanOne(p, `${rel} <script #${++i}>`));
    }
  }
}
rmSync(tmp, { recursive: true, force: true });

// Known over-match in scan-rules (Phase 4 runs every language pack on every file): the Python
// rule /\b(eval|exec)\s*\(/ also fires on JS *method calls* — RegExp#exec, db.exec — which run no
// code from a string. Real JS command execution is caught by src-child-process-exec-interp anyway.
// Such hits (and a composite-critical built only on them) are shown as notes with the reason.
const BARE_EVAL = /(?<![.\w$])(eval|exec)\s*\(/;
for (const r of results) {
  const fs = r.findings || [];
  const py = fs.filter(x => x.rule === 'src-py-eval-exec');
  for (const x of py) if (x.excerpt && !BARE_EVAL.test(x.excerpt) && !/child_process|\bspawn|\bexecFile|\bexecSync|\bshell/.test(x.excerpt)) {
    x.severity = 'note'; x.detail = '`.exec(` / `.eval(` method call (regex or SQL), not code run from a string — known scanner over-match';
  }
  if (py.length && py.every(x => x.severity === 'note'))
    for (const x of fs) if (x.rule === 'source-composite-critical' && /eval-exec/.test(x.detail || '')) {
      x.severity = 'note'; x.detail = `composite built on the eval/exec over-match above — ${x.detail}`;
    }
}
const real = (r) => (r.findings || []).filter(x => x.rule !== 'source-lane-notice');
const blocking = results.filter(r => r.verdict === 'unscanned' || r.verdict === 'error' || real(r).some(x => x.severity === 'critical' || x.severity === 'high'));
const notes = results.filter(r => !blocking.includes(r) && real(r).length);
const summary = {
  scanned: results.length,
  code: results.filter(r => r.verdict !== 'not-applicable').length,
  data: results.filter(r => r.verdict === 'not-applicable').length,
  needs_owner: blocking.length,
  notes: notes.length,
  verdict: blocking.length ? 'needs-owner' : 'clean',
};

if (asJson) { console.log(JSON.stringify({ armor: ARMOR, summary, results }, null, 2)); process.exit(blocking.length ? 1 : 0); }

const line = (r) => r.error ? `  • ${r.file} — ${r.error}`
  : real(r).map(x => `  • ${r.file} — ${x.severity.toUpperCase()} ${x.rule}: ${x.detail}${x.location && x.location !== r.file ? ` (${x.location})` : ''}`).join('\n');
console.log(`Scripture Armor scan — ${summary.scanned} item(s): ${summary.code} code, ${summary.data} data (not code)`);
if (blocking.length) { console.log(`\nNEEDS THE OWNER (${blocking.length}) — do not ship until each is explained or fixed:`); blocking.forEach(r => console.log(line(r))); }
if (notes.length) { console.log(`\nNotes (${notes.length}) — worth a look, not blocking:`); notes.forEach(r => console.log(line(r))); }
if (!blocking.length && !notes.length) console.log('Clean: no risky-behavior patterns found.');
console.log('\n(Pattern scan of source text: it catches risky behavior — code run from strings, shell commands, hidden persistence,\n sensor access, pipe-to-shell downloads. It is not a full vulnerability audit: no SQL injection / XSS / auth logic checks.)');
process.exit(blocking.length ? 1 : 0);
