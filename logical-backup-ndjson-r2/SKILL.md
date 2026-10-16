---
name: logical-backup-ndjson-r2
description: >-
  The recovery story a single-D1 app otherwise never gets: dump EVERY business
  table to newline-delimited JSON ({"_t":table,"r":row} per line), gzip it in the
  Worker runtime (~8-12x on repetitive rows), and write it to a PRIVATE R2 prefix
  (backups/<ISO-timestamp>.ndjson.gz) that no public route serves — plus a daily
  cron that runs it unattended (at most once/24h), tunable keep-N retention that
  prunes the oldest so R2 stays bounded, a viewer-readable run log, an admin-only
  on-demand run + streamed download, and a DOCUMENTED MANUAL restore (never a
  one-click endpoint). The dump is SCHEMA-AGNOSTIC — it enumerates tables from
  sqlite_master and SELECTs *, so it keeps capturing whatever columns/tables were
  added later with zero backup-code changes. Use WHENEVER a build needs: "back up
  the CRM / the database", "give this a recovery story / disaster recovery",
  "export the whole DB", "how do we restore this / restore from backup", "keep
  only the last N backups", "prune old backups so R2 stays bounded", or when they
  add their own tables/fields and the backup must keep working untouched. (For a
  pure storage-cap "refuse uploads past the limit" / usage-readout intent, or an
  archive-then-delete-attachments purge, reach for r2-upload-budget-guard /
  export-before-delete-reclaim instead — this skill is the DB dump + restore
  lifecycle.) Backend pattern on a Cloudflare Worker + D1 + R2. COMPLEMENTS
  d1-migration-recipes (restore = re-apply the migration chain, THEN reload rows;
  the schema ships as one additive Mode-A migration), append-only-audit-log (the
  backup_runs table is that same provable-log discipline, specialized to backup
  outcomes), and d1-proof-harness (prove a dump→gzip→restore round-trip end to
  end). Draws a hard boundary with r2-upload-budget-guard: THAT skill owns the
  account-wide R2 budget guard (refuse uploads past the cap), the usage readout,
  and the export-before-delete reclaim — it only gestures at backups; THIS skill
  owns the backup/restore lifecycle in full (dump format, run log, cron, export,
  manual restore, round-trip proof). The shared seam is the keep-N retention
  prune. And custom-fields-engine is what LETS users add their own fields; this
  skill's schema-agnostic dump merely captures them for free. Guardrails: R2 put
  + retention prune are BEST-EFFORT (never fail the
  backup, and never throw into the cron); the run is ALWAYS logged, even on
  failure (ok=0 + error); restore is a DELIBERATE manual procedure into a FRESH
  db, never a blind overwrite of live data; skip sqlite_/\_cf_/d1_ internal tables
  and the migration ledger; column is run_trigger, NOT trigger (reserved SQLite
  keyword); backups contain PII so the bucket stays private and the download
  endpoint admin-only; credentials never leave the DB (key/OAuth/session/invite
  tables skipped, credential columns dumped NULL, a schema-scan proof).
---
# logical-backup-ndjson-r2 — the recovery story for a single-D1 app

## What it is / when to use
A whole app's CRM, ledger, and everything else often lives in **one** D1 with no
recovery story. This is the sustainability layer that gives it one: a **logical**
backup — every business table serialised to gzipped NDJSON, written to a private
R2 prefix on a daily cron, with bounded retention, a provable run log, an
on-demand download, and a documented manual restore. Reach for it whenever a
build should survive an accidental wipe, a bad migration, or a fat-fingered
delete — and whenever storage cost/limits (R2's 10 GB free cap shared account-wide)
mean backups must self-prune rather than pile up forever.

**Logical, not physical.** You dump *rows*, not the SQLite file. Restore =
re-create the schema (re-apply migrations) and reload the rows. That is why the
dump deliberately **excludes** the migration ledger and SQLite/CF internals.

**Credentials never ride along.** The download is gated admin-only, but "admin"
includes every admin login and any automation bearer that maps to one. A
schema-agnostic `SELECT *` hands all of them every API key, OAuth refresh token and
live session token in the database. The dump therefore skips **credential tables**
outright and blanks **credential columns** inside business tables. A proof scans the
schema so a new secret can't slip in unclassified. Restore then means re-entering
keys and signing in again, and that is the right trade.

**Default-include vs default-deny.** `ops-console` teaches the other design: a
JSON backup of an explicit allowlist of durable tables. Credentials are left out by
construction, because nobody lists `sessions`. Use that when the schema is small and
fixed. Use this skill's dump-everything-minus-credentials when the backup must
capture tables and fields added later (custom fields, new engines) without code
changes. It is weaker by default: a credential column the classifier misses
ships. So the classification proof below is not optional.

**Composes with (extend these, do not re-implement):**
- **d1-migration-recipes** — the backup schema ships as ONE additive (Mode A)
  migration, and restore's step 1 is "re-apply the migration chain to a fresh DB."
  This skill leans on that skill for schema evolution; it does not re-teach it.
- **append-only-audit-log** — `backup_runs` is the same immutable-provable-log
  discipline (no UPDATE/DELETE route, best-effort write that never breaks the
  caller), specialized to *backup outcomes* rather than privileged user actions.
  Log the backup; audit the human who toggled it.
- **d1-proof-harness** — to *prove* the mechanism, boot a worker, take a backup,
  and replay the dump into a fresh DB, asserting row counts match. This skill
  provides the round-trip; that skill provides the harness to run it under.

**Boundary — do NOT re-implement these (they own the storage envelope):**
- **r2-upload-budget-guard** — owns the account-wide R2 budget guard (refuse
  uploads at HTTP 507 past a soft cap), the usage readout (R2 bytes by prefix +
  D1 `page_count`), and the edge-cache proxy. It references the same
  `worker/backup.ts` but treats the backup as one line-item; the keep-N retention
  prune is the **shared seam**. Lift the *dump + restore lifecycle* from here and
  the *budget/usage/refuse* logic from there — don't copy either into the other.
- **export-before-delete-reclaim** — owns purging *attachments/uploads* to
  reclaim space with an archive-then-delete invariant (build the ZIP of exactly
  what's about to go BEFORE any delete). That is a different concern from this
  skill's *backup* dump: reclaim frees blobs and needs a multi-file ZIP writer;
  this skill dumps DB rows to a single NDJSON. Route "clean up old attachments
  but keep the records" there; route "back up / restore the database" here.

## Reference implementation — exact source file:line
Proven + shipped in the ronininc-crm baseline (app-forge worktree), except the
credential exclusion, which is **pending ronininc-crm#321** (open, not yet on
`main`). Genericise every name below (binding, bucket, tables) when you lift it —
patterns only. `worker/backup.ts` is cited by symbol because its line numbers move
with every edit; the other files keep baseline line refs.
- `worker/backup.ts` `gzip()` — WHATWG Compression Streams in the Workers
  runtime (`new CompressionStream('gzip')`), no library. NDJSON is highly
  repetitive → ~8-12x smaller stored footprint.
- `worker/backup.ts` `dumpDatabase()` — the schema-agnostic core. Reads
  table names from `sqlite_master`, filters them through `skip()`
  (`sqlite_`/`_cf_`/`d1_` prefixes + `SECRET_TABLES`), `SELECT *` per table with the
  name quoted and the LIMIT capped at `MAX_ROWS_PER_TABLE = 50000`, blanks
  `SECRET_COLUMNS`, emits `{_t, r}` one row per line.
- `worker/backup.ts` `SECRET_TABLES` / `SECRET_COLUMNS` (pending #321) — the
  credential exclusion. The baseline shipped without it and leaked live session
  tokens (the login cookie itself), plaintext OAuth tokens and the LLM-judge keys
  to anyone who could pull the export. `worker/lib/_proof/backup.test.mjs` (pending
  #321) — the schema scan + seeded-secret proof (export AND the stored R2 object).
- `worker/backup.ts` `runBackup()` — dump → gzip → `R2.put` under a timestamped
  key → keep-N retention prune → log `backup_runs` + stamp
  `backup_settings.last_run_at`; a no-R2 fallback reports the raw size, and the
  error is captured (`slice(0,300)`), never thrown.
- `worker/backup.ts` `maybeBackup()` — the cron guard (enabled? + ≥24h since
  last run?).
- `worker/backup.ts` admin handlers — `listBackups` (viewer read),
  `runBackupRequest`, `backupExport` (streamed NDJSON download, no R2 needed),
  `saveBackupSettings` (toggle).
- `migrations/0065_backups.sql:7-26` — the additive Mode-A schema:
  `backup_settings` (singleton) + seed (**:13**), `backup_runs` + index. Note
  **:23** — the column is `run_trigger`, NOT `trigger` (reserved SQLite keyword).
- `worker/index.ts:315-319` — cron wiring: `maybeBackup(env)` inside the
  `scheduled()` `Promise.all`, each task `.catch()`-guarded so one failure can't
  abort the others. `wrangler.jsonc:94-95` — `"crons": ["*/5 * * * *"]` (the
  24h throttle lives in code, not the cron expression).
- `worker/admin.ts:536-539` — route table: `GET backup`, `GET backup/export`
  (admin-only gate at **:537**), `POST backup/run`, `POST backup/settings`.
- `public/admin/admin.js:591-613` — the Backups tab UI (auto-toggle checkbox,
  "Back up now", "Download full backup" link, run-log table); **:341** loads it.
- `worker/types.ts:12,16-18` — env contract: `R2Bucket` binding + `BACKUP_KEEP`
  (default 14) + an R2-budget note. `BACKUP_RESTORE.md` — the shipped manual
  restore doc (the source of the "How to reapply → Restore" section below).

## How to reapply

**1. Migration (additive — see d1-migration-recipes Mode A).** A singleton
settings row + an append-only run log:
```sql
CREATE TABLE IF NOT EXISTS backup_settings (
  id          TEXT PRIMARY KEY CHECK (id='default'),
  enabled     INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),  -- ships ON: backups are a safe, free default
  last_run_at INTEGER NOT NULL DEFAULT 0,
  updated_at  INTEGER NOT NULL DEFAULT (unixepoch())
);
INSERT OR IGNORE INTO backup_settings (id) VALUES ('default');

CREATE TABLE IF NOT EXISTS backup_runs (
  id          TEXT PRIMARY KEY,
  r2_key      TEXT,                            -- null when R2 unbound / export-only
  tables      INTEGER NOT NULL DEFAULT 0,
  rows        INTEGER NOT NULL DEFAULT 0,
  bytes       INTEGER NOT NULL DEFAULT 0,      -- the COMPRESSED footprint when stored gzipped
  ok          INTEGER NOT NULL DEFAULT 1 CHECK (ok IN (0,1)),
  error       TEXT,
  run_trigger TEXT NOT NULL DEFAULT 'manual',  -- manual | cron  — NOT "trigger" (reserved keyword)
  created_at  INTEGER NOT NULL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_backup_runs_created ON backup_runs(created_at DESC);
```

**2. Handlers.** Schema-agnostic dump, then a best-effort store + always-log run:
```js
const MAX_ROWS_PER_TABLE = 50000;
// Tables that ACT AS the app (provider keys, OAuth grants, live logins, unused invites): never dumped.
// Name YOUR app's tables here: sessions are the one every app has.
const SECRET_TABLES = new Set(['sessions', 'auth_tokens', 'oauth_states', 'integrations', 'provider_secrets']);
// Credentials inside tables that otherwise belong in a backup: row kept, value dumped as NULL.
const SECRET_COLUMNS = { org_bank: ['plaid_access_enc'] };
const skip = (n) => n.startsWith('sqlite_') || n.startsWith('_cf_') || n.startsWith('d1_') // internals + migration ledger
  || SECRET_TABLES.has(n);

async function gzip(text) {                                            // no library — WHATWG streams
  const s = new Response(text).body.pipeThrough(new CompressionStream('gzip'));
  return new Uint8Array(await new Response(s).arrayBuffer());
}

async function dumpDatabase(env) {                                     // survives new tables/columns untouched
  const tbls = await env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").all();
  const names = (tbls.results || []).map((t) => t.name).filter((n) => !skip(n));
  let ndjson = '', rows = 0, tables = 0;
  for (const name of names) {
    // name comes from sqlite_master (trusted); quote it defensively
    const res = await env.DB.prepare(`SELECT * FROM "${name}" LIMIT ${MAX_ROWS_PER_TABLE}`).all().catch(() => ({ results: [] }));
    tables++;
    const redact = SECRET_COLUMNS[name] || [];
    for (const r of res.results || []) {
      for (const c of redact) if (c in r) r[c] = null;                 // the row survives, the credential doesn't
      ndjson += JSON.stringify({ _t: name, r }) + '\n'; rows++;
    }
  }
  return { ndjson, tables, rows };
}

async function runBackup(env, trigger = 'manual') {
  const t = now(), id = uid();
  let key = null, ok = 1, error = null, bytes = 0, tables = 0, rows = 0;
  try {
    const dump = await dumpDatabase(env); tables = dump.tables; rows = dump.rows;
    if (env.BUCKET) {                                                  // your private R2 binding
      const gz = await gzip(dump.ndjson); bytes = gz.byteLength;       // record the COMPRESSED size
      key = `backups/${new Date(t * 1000).toISOString().replace(/[:.]/g, '-')}.ndjson.gz`; // sorts chronologically
      await env.BUCKET.put(key, gz, { httpMetadata: { contentType: 'application/gzip' } });
      try {                                                            // retention — best-effort, never fails the backup
        const KEEP = Math.max(1, parseInt(env.BACKUP_KEEP || '14', 10) || 14);
        const listed = await env.BUCKET.list({ prefix: 'backups/' });
        const keys = (listed.objects || []).map((o) => o.key).sort();  // one sort spans legacy .ndjson AND new .ndjson.gz
        for (const stale of keys.slice(0, Math.max(0, keys.length - KEEP))) await env.BUCKET.delete(stale).catch(() => {});
      } catch { /* pruning is best-effort */ }
    } else { bytes = dump.ndjson.length; }                            // no R2: still return a size
  } catch (e) { ok = 0; error = String(e.message).slice(0, 300); }    // capture, don't throw
  await env.DB.prepare('INSERT INTO backup_runs (id,r2_key,tables,rows,bytes,ok,error,run_trigger,created_at) VALUES (?,?,?,?,?,?,?,?,?)')
    .bind(id, key, tables, rows, bytes, ok, error, trigger, t).run().catch(() => {}); // ALWAYS log, even a failed run
  await env.DB.prepare("UPDATE backup_settings SET last_run_at=?, updated_at=? WHERE id='default'").bind(t, t).run().catch(() => {});
  return { id, r2_key: key, tables, rows, bytes, ok: !!ok, error };
}

async function maybeBackup(env) {                                     // cron: enabled + ≥24h throttle
  const s = await env.DB.prepare("SELECT enabled, last_run_at FROM backup_settings WHERE id='default'").first().catch(() => null);
  if (!s || !s.enabled) return;
  if (now() - (s.last_run_at || 0) < 24 * 3600) return;
  await runBackup(env, 'cron');
}
```
`backupExport(env)` returns `dumpDatabase()`'s NDJSON as an `attachment`
(`content-type: application/x-ndjson`) — needs no R2, so it's the always-available
escape hatch. `listBackups` returns settings + the recent `backup_runs`;
`saveBackupSettings` flips `enabled`.

**3. Routes + cron wiring.** Reads viewer-visible; run/export/settings admin-only:
```js
if (m === 'GET'  && sub === 'backup')          return listBackups(env);
if (m === 'GET'  && sub === 'backup/export')   { if (me.role !== 'admin') return bad('Export is admin-only.', 403); return backupExport(env); }
if (m === 'POST' && sub === 'backup/run')      return runBackupRequest(env);
if (m === 'POST' && sub === 'backup/settings') return saveBackupSettings(req, env);
```
In `scheduled()`, add `maybeBackup(env).catch((e) => console.error('backup', e))`
to the guarded `Promise.all`. The cron can fire every few minutes; the 24h cap is
enforced in code, not the cron expression.

**4. UI (optional).** A "Backups" admin tab: an enabled checkbox
(→ `POST backup/settings`), a "Back up now" button (→ `POST backup/run`), a
"Download full backup" link (`<a href="/api/admin/backup/export">`), and a table
of recent runs from `GET backup`.

**5. Restore — the documented MANUAL path (ship this as a doc).**
Deliberately not an endpoint. (a) Fetch the dump — from a downloaded export, or
`wrangler r2 object get <bucket>/backups/<ts>.ndjson.gz --file r.ndjson.gz --remote && gunzip r.ndjson.gz`.
(b) Recreate schema on a **fresh** DB: `wrangler d1 migrations apply <target> --remote`
(this is where d1-migration-recipes carries the load). (c) Reload rows — group the
NDJSON by `_t` and emit `INSERT OR REPLACE` per row; load parents before children,
or wrap in `PRAGMA defer_foreign_keys=ON`. (d) Verify with `SELECT COUNT(*)`, point
the Worker at the restored DB, do a live login + record round-trip before trusting it.
(e) Re-attach what the dump left out on purpose. Everyone signs in again (no
sessions); re-enter stored provider keys; reconnect OAuth integrations; re-issue any
blanked column (bank link, webhook or wake secrets); re-send unused invites. Restore
with the SAME `ENCRYPTION_KEY`, or encrypted columns you kept won't decrypt. Ship
this list in the restore doc, one line per excluded table or column.

### THE INVARIANT
**Restore is never automatic; the backup path never breaks the app.** There is NO
one-click restore endpoint — overwriting live data must be a deliberate human act
into a fresh database. And every side of the backup that *can* fail (R2 put,
retention prune, the log write itself) is best-effort and swallowed: a backup
failure records `ok=0` and moves on, it never throws into the cron or the request.
And **no credential ever leaves the database**: a backup is a file someone will
download, so it carries data, never the keys to act as the app.

## Gotchas — real pitfalls from the code + how it's validated
- **`trigger` is a reserved SQLite keyword.** The column is `run_trigger`. Naming
  it `trigger` makes the `INSERT` fail at runtime (miniflare may be lax; D1 remote
  is not) — caught only by an end-to-end proof, never by a local dry-run.
- **Store the COMPRESSED size in `bytes`.** That is what counts against the R2 cap.
  Recording the raw dump length overstates footprint ~10x and misleads the
  usage/budget view. The no-R2 branch reports raw size *because* nothing was stored.
- **Timestamped keys must sort chronologically** so `list().sort().slice(0, len-KEEP)`
  prunes the OLDEST. ISO timestamps do; a random `uid` key would silently prune
  the wrong objects. The single sort also spans a format change (legacy `.ndjson`
  + new `.ndjson.gz`), so old uncompressed backups age out correctly.
- **Exclude the migration ledger + internals** (`d1_migrations`, `_cf_*`,
  `sqlite_*`). Restore re-applies migrations to build schema; replaying the ledger
  rows fights that, and the CF KV shadow isn't yours to restore.
- **`MAX_ROWS_PER_TABLE` is a silent truncation.** A table past 50k rows dumps
  only its first 50k with no error. Raise the cap AND paginate before any table
  gets that big; a proof that seeds >cap rows and checks the dump count surfaces it.
- **Backups contain PII.** Keep the bucket private, put backups under a `backups/`
  prefix no public route serves, and gate the download endpoint admin-only. If the
  R2 bucket is shared with public assets, a prefix-scoped budget guard keeps the
  two from colliding.
- **"Admin-only" is not "safe to hold credentials."** The real incident: the
  baseline dumped `sessions` (the PK *is* the login cookie), plaintext Upwork
  OAuth tokens, the Google refresh token, unused invites, the Plaid token and the
  LLM-judge keys. The export route checked `role === 'admin'`, and an automation
  master bearer counted as admin. So whoever held that bearer could sign in as the
  owner and act at every connected provider. The worst of it (`sessions`, the OAuth
  tables, the bank table) existed BEFORE the backup was written. The dump leaked
  from day one, because nobody classified credentials when it was built. Later
  tables (LLM-judge keys, bot-desk wake secrets) then joined silently. The one table
  that never leaked was the provider-key vault: it was excluded in the same change
  that created it. So classify at build time, then keep a proof that forces the
  question for every new column.
- **Classify every credential-shaped column; don't hunt for them by eye.** Scan the
  migrated schema and fail unless each hit is SKIPPED (its table is in
  `SECRET_TABLES`), REDACTED (in `SECRET_COLUMNS`), or KEPT with a written reason.
  Read the schema from the local miniflare `.sqlite` file: D1, even local, refuses
  `pragma_table_info` with SQLITE_AUTH. Use `node:sqlite` (no flag from Node 22.13 /
  23.4; 22.5–22.12 need `--experimental-sqlite`) or the `sqlite3 <file>` CLI on older
  Node. Match at least
  `/(_enc|token|secret|signing_key|api_key|access_key|private_key|password|passwd|credential|cookie|_pin|_otp)$/i`.
  Treat any other `*_key` column as a hit too, with a short NOT-a-secret allowlist
  (`idempotency_key`, `dedupe_key`, `r2_key`, `cache_key`, object/media keys…) so
  real ones like `api_key` or `stripe_key` can't hide among them. Column names
  can't see inside JSON. Any `*_json` / `config` / `settings` / `params` blob that
  might hold a key gets read by hand and marked KEPT ("no credentials, checked
  <date>") or REDACTED. Keep on purpose: encrypted values the app needs to stay
  correct after a restore (2FA seeds, an HMAC key that signs links already sent,
  encrypted PII); unsubscribe and other per-record links already in people's
  inboxes; short-lived nonces. Token *ids* aren't credentials. Hashes (`*_hash`) are
  safe to keep only when they're slow and salted (PBKDF2/bcrypt/scrypt/argon2 for
  passwords) or hashes of high-entropy random tokens. A fast or unsalted hash of a
  password, PIN, OTP or short invite code is crackable offline: redact it or skip
  its table. Blanking a 2FA seed while `totp_enabled=1` stays set locks users out,
  so keep it encrypted rather than redacting it.
- **Co-tenanting R2.** The reference reuses one bucket for tiles, uploads, AND
  backups behind distinct prefixes; a keep-N cap + an upload budget stop backups
  from ever silently tripping account-wide R2 overage. Give each concern its own
  prefix and its own bound.
- **How it's validated:** with d1-proof-harness — boot a worker, seed rows across
  several tables (including a user-added one, to prove schema-agnosticism),
  `POST /backup/run`, assert `ok && tables && rows`, then replay the exported
  NDJSON into a fresh DB and assert `COUNT(*)` matches per table. That round-trip,
  not a green log line, is the proof the recovery story actually recovers. For the
  credential rule, seed a marked row in every `SECRET_TABLES` table and
  `SECRET_COLUMNS` column, and use a REAL session cookie from a login. Then assert
  that neither the export nor the stored R2 object (read back with
  `wrangler r2 object get … --local`, gunzipped) carries a skipped table's `_t`, any
  marker, or the cookie value, and that redacted rows are present with the column
  NULL. Run it once against the unpatched dump to see it fail.
