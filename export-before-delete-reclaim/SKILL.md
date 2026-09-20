---
name: export-before-delete-reclaim
description: >-
  The choreography that makes a space-freeing purge reversible: any reclaim FIRST assembles a
  COMPLETE archive of exactly what is about to disappear — the blobs + a records.ndjson of the
  owning DB rows (child AND parent) + a manifest.csv + a summary — and only deletes AFTER the
  archive bytes exist in hand. The whole export-then-purge sequence lives in ONE handler, so the
  invariant holds no matter what pulls the trigger: an admin "reclaim space" button, a "we're near
  the R2 limit" prompt, or a future auto-sweep. Ships a read-only preview endpoint (what a run WOULD
  free, deletes nothing) beside the destructive one, a per-run byte budget so a Worker never blows
  its ~128 MB isolate ceiling (reporting how much remains for a follow-up run), and the discipline
  that EVERY purged record is represented in the archive even when its blob is already gone. Use
  WHENEVER a build must purge to reclaim space and you want it reversible: "back up before you
  delete", "purge old uploads safely", "we're near the R2 / storage limit", "clean up old
  attachments but don't lose the records", "export their records before deleting", "archive-then-
  delete", "give me a download of what I'm about to remove". Backend on a Cloudflare Worker + D1 +
  an object store (R2). COMPLEMENTS (extends, does NOT duplicate): sovereign-store-zip-writer (the
  byte-exact STORE-method makeZip this HANDS its entries to — that skill owns "how bytes become a
  .zip", this owns "what must be in the archive and when we may delete"); r2-upload-budget-guard
  (owns the account-wide budget refusal + usage readout that DECIDE when to reclaim — this is the
  safe purge it invokes); logical-backup-ndjson-r2 (the scheduled WHOLE-DB backup — this is the
  targeted, on-demand purge that shares its {"_t","r"} ndjson line format so a reclaim archive
  re-imports through the same restore path); and append-only-audit-log (log every reclaim run + its
  freed bytes). Guardrails: build the archive BEFORE the first delete — archive throws ⇒ nothing is
  deleted; require an explicit confirm on the destructive call; bound each run by a byte cap and
  report the remainder; NEVER purge the backups themselves (that is the recovery story); gate the
  destructive route to the OWNER, not a sub-clearance; a single blob over the run cap is listed, not
  truncated.
---
# export-before-delete-reclaim — archive the bytes, THEN reclaim the space

## What it is / when to use / what it composes with
The **safety choreography** for freeing object-store space without ever losing a record. A
read-only **preview** reports what a run would free; a destructive **export-purge** assembles a
complete archive (blobs + `records.ndjson` + `manifest.csv` + a summary) and deletes the originals
**only after** those bytes exist. Reach for it on any Worker + D1 + R2 build that accumulates blobs
(attachments, uploads, media, generated files) and will eventually hit a storage budget — so an
operator can shrink usage and still restore anything by re-importing.

This skill owns **the invariant and what the archive must contain** — it does NOT re-implement the
ZIP encoder or the budget math. It sits at the seam between three neighbours:

- **sovereign-store-zip-writer** — the dependency-free `makeZip(entries) => Uint8Array` this hands
  its assembled `ZipEntry[]` to. Keep "how do bytes become a valid .zip" (headers, CRC32, EOCD)
  THERE; keep "what goes in and when we delete" HERE. Do not copy the encoder into this skill.
- **r2-upload-budget-guard** — owns the account-wide budget refusal (HTTP 507) and the usage
  readout that answer *whether/when* to reclaim. This skill is the safe purge that guard invokes
  once usage is near the cap; it does not measure the account or refuse uploads.
- **logical-backup-ndjson-r2** — the scheduled WHOLE-DB backup (every table, gzip, cron, retention).
  This is the *targeted, on-demand* purge that also carries the deleted blobs' bytes. Both write the
  same `{"_t":table,"r":row}` ndjson lines, so a reclaim archive re-imports through that same
  documented restore path.
- **append-only-audit-log** — after a purge, log `reclaim_purge` (files / freed bytes / remaining)
  so the destructive act itself leaves an immutable trail.

## Reference implementation — exact source file:line (lift the proven code)
Proven + shipped in a Worker+D1 CRM baseline (`app-forge` worktree). Cite, don't copy verbatim —
genericize entity names (`activities`/`contacts`), the R2 binding (`MAPTILES`), and the filename.

**`worker/reclaim.ts` — the orchestration + the invariant (this skill's core)**
- **L1–16** the doctrine comment: the invariant lives in ONE place (`reclaimExportPurge`) so it
  holds for the button AND any auto-trigger; backups are deliberately EXCLUDED from scope (they
  self-prune and they ARE the recovery story).
- **L25** `RECLAIM_MAX_BYTES = 30 * 1024 * 1024` — per-run in-memory budget (blobs held once + the
  assembled ZIP copy stays well under the isolate's ~128 MB ceiling; bigger jobs = more runs).
- **L28** `cutoffFrom(days)` — age cutoff, defaults 30d; **L29** `csv()` — RFC-4180 cell quoting.
- **L33–38** `oldAttachments(env, cutoff)` — `SELECT … FROM activities WHERE type='attachment' AND
  created_at < ? ORDER BY created_at ASC LIMIT 5000` (oldest-first, bounded).
- **L39–41** `metaOf(body)` — parse the child row's JSON `body` into `{key,name,size,type}` (the R2
  key + display metadata live on the child row).
- **L44–58** `reclaimPreview` — **read-only** `GET …/reclaim/preview?days=`: returns
  `{attachments:{count,bytes,oversize}, days, cutoff, per_run_cap_bytes, note}` and deletes nothing. The dry-run every
  destructive tool ships beside itself.
- **L62–154** `reclaimExportPurge` — the destructive `POST …/reclaim/export-purge`:
  - **L63** `if (!env.MAPTILES) return bad(…503)` — refuse when the store binding is absent.
  - **L66** `if (b.confirm !== true) return bad('Confirmation required.')` — explicit intent gate.
  - **L81–104** the assembly loop: **L85** a single blob larger than the per-run cap is pushed to
    `skipped` (listed, never archived/truncated); **L86** stop adding once the run budget is hit and
    `remaining++` for a later run; **L91** push the row's metadata into `ndjson` **before** the
    `if (obj)` check — so a record with an already-missing blob is still represented (manifest kind
    `attachment-missing-blob`, **L101**) and still deleted (**L103**); **L96–99** for a present blob
    add its bytes as a `ZipEntry` + a manifest row + queue its R2 key & activity id for deletion.
  - **L106–108** early return when nothing is older than the cutoff (deletes nothing).
  - **L111–119** fetch the **owning parent rows** (`contacts`) in chunks of 100 and add them to
    `ndjson`, so the archive is a complete "their records" export, not orphaned children.
  - **L121–129** append `manifest.csv`, `records.ndjson`, `_reclaim-summary.json` as ZIP entries;
    the summary carries the re-import instructions (the restore story travels with the archive).
  - **L131–132 THE INVARIANT** — `const zip = makeZip(entries);` (imported from `./zip`,
    L20) builds the whole archive FIRST. `makeZip` is synchronous: it returns the full buffer or
    throws, so if assembly fails, execution never reaches the deletes below.
  - **L134–139 THE PURGE** — only now: `for (k of purgeKeys) await env.MAPTILES.delete(k)`, then
    `DELETE FROM activities WHERE id IN (…)` in chunks of 50.
  - **L141–153** stream the ZIP back as `application/zip` + `content-disposition: attachment` +
    `x-reclaim-*` headers (files / activities / freed / remaining / skipped) for the UI to read.
- Filename sanitization: **L95** maps `[^\w.\-]+ → _` and slices to 120 chars so a hostile
  attachment name can't break the in-archive path.

> The byte-level writer it calls (`worker/zip.ts`, `makeZip`, STORE method, CRC32/EOCD) is the
> **sovereign-store-zip-writer** skill — read that for the encoder internals; do not re-derive them
> here.

**Wiring (where it plugs in)**
- **`worker/admin.ts` L72** `import { reclaimPreview, reclaimExportPurge } from './reclaim'`;
  **L398–399** the two routes, reached **after `requireAdmin()`** (dispatcher note L385) and, for
  the POST, behind a **CSRF `sameOrigin` gate** (L390).
- **`worker/auth.ts` L248–266** `SUB_SECTION` map: **`reclaim` is deliberately absent**, so
  `authorizeAdmin` gives a sub-clearance holder a 403 and only the **owner** can run reclaim.
- **Schema:** no new migration — reclaim reuses existing tables (`activities` type='attachment'
  child rows + their `contacts` parent, `migrations/0001_init.sql` L85 & L32). **No cron:** it is
  operator-triggered (button / limit-reached prompt), and the one-code-path invariant is exactly
  what makes wiring an auto-trigger later safe.

## How to reapply
**1. Schema / assumptions.** No new table if blobs are already referenced by DB rows carrying
`{ key, name, size, type }` (R2 key + display metadata). If not, add those to the row that owns each
blob. Identify the child row type to purge and its owning parent table.

**2. Preview handler (read-only).** `GET …/reclaim/preview?days=N` → the same selection query
(oldest-first, `created_at < cutoff`, `LIMIT`) → `{attachments:{count, bytes, oversize}, days, cutoff, per_run_cap_bytes, note}`.
Deletes nothing. Every destructive tool ships this dry-run beside it.

**3. Export-purge handler (destructive) — enforce THE INVARIANT:**
```
// 1. refuse if the store binding is missing; require confirm:true
if (!env.R2) return bad('File storage is not configured.', 503);
if (body.confirm !== true) return bad('Confirmation required.');

// 2. assemble entries within the per-run byte budget — for each old CHILD row:
//    - push the row's metadata to ndjson BEFORE checking if the blob exists
//      (a missing blob is still represented; the row is still queued for deletion)
//    - if the blob exists: add its bytes as a ZipEntry + a manifest row; queue key + id
//    - a single blob larger than the whole run cap → push to `skipped` (list it, don't archive)
//    - once bytes + next > cap → stop adding, `remaining++` for the next run
// 3. add the OWNING PARENT rows to ndjson (chunked IN (...) of 100) — complete "their records"
// 4. append manifest.csv, records.ndjson ({"_t","r"} lines), _summary.json (with re-import note)

const zip = makeZip(entries);            // <-- ARCHIVE FIRST (sovereign-store-zip-writer). throws => nothing deleted.

for (const k of purgeKeys) await env.R2.delete(k).catch(()=>{});   // <-- PURGE only after
for (const chunk of chunksOf(purgeIds,50))
  await env.DB.prepare(`DELETE FROM child WHERE id IN (${qs})`).bind(...chunk).run();

await audit(env, me.id, 'reclaim_purge', `${files}/${freed}B, ${remaining} left`);  // append-only-audit-log
return new Response(zip, { headers:{ 'content-type':'application/zip',
  'content-disposition':`attachment; filename="<app>-reclaim-${date}.zip"`, /* x-reclaim-* */ }});
```
Keep the `makeZip` line as the last thing before the first delete — that single ordering IS the
skill. Never move a `delete` above it; never split export and purge into separate handlers.

**4. The ZIP writer.** Do NOT re-implement it — pull `makeZip` from **sovereign-store-zip-writer**
(dependency-free, runs on the Workers runtime as-is). This skill only builds the `ZipEntry[]` and
owns the ordering.

**5. Routes / gating / UI.**
- Register both routes **after** the admin gate; require **same-origin** on the POST (CSRF).
- Gate the destructive route to the **owner** — leave it OUT of any sub-clearance map so a delegated
  admin cannot purge. Preview may be more broadly readable.
- UI: a "Reclaim space" button that first calls preview and shows "will free N files / X MB", then
  on confirm POSTs and downloads the returned ZIP. Read the `x-reclaim-*` headers to show
  "archived N, freed X, M remaining — run again" and loop until `remaining` is 0.

**6. Restore story.** The archive is self-describing: re-import `records.ndjson` (identical shape to
a **logical-backup-ndjson-r2** dump) and re-upload the matching files from `attachments/…` keyed by
`manifest.csv`'s r2_key. State this in `_summary.json` so whoever holds the ZIP can undo the purge.

## Gotchas — real pitfalls from the code + how it's validated
- **Order is the entire contract.** `makeZip(entries)` (reclaim.ts L132) MUST complete before the
  first `.delete` / `DELETE` (L135–138). If archive assembly throws, no delete runs and the operator
  retries with nothing lost. One handler, one path — do not let a button and a future auto-trigger
  take different routes to the delete.
- **Archive the record even when the blob is already gone.** L91 pushes row metadata to `ndjson`
  before the `if (obj)` check; a missing blob is logged `attachment-missing-blob` (L101) but the row
  is still deleted (L103) and still represented. Otherwise a purge silently erases records whose
  bytes had already vanished.
- **Include the parents, or the export is incomplete.** L111–119 pulls the owning `contacts` rows
  into the archive. Exporting only the child blobs hands back an un-restorable set. Chunk the
  `IN (...)` (100 here) to respect SQLite's variable cap.
- **Bound every run; report the remainder.** L86 stops once `RECLAIM_MAX_BYTES` is hit and counts
  `remaining`; the response header tells the UI to run again. A single blob over the whole cap (L85)
  is *listed as skipped*, never truncated — handle those out of band. This is what keeps peak memory
  (blobs once + the ZIP copy) under the isolate ceiling.
- **Never let reclaim eat the backups.** The doctrine (L11–13) excludes backups from purge scope on
  purpose. A "free space" feature that deletes its own recovery path defeats itself — leave
  logical-backup-ndjson-r2's `backups/` prefix untouched.
- **Owner-only + confirm + same-origin.** Three independent gates: `confirm:true` (L66), CSRF
  same-origin on the POST (admin.ts L390), and absence from `SUB_SECTION` (auth.ts) so only the
  owner — not a delegated clearance holder — can trigger a destructive reclaim.
- **Don't confuse "when to purge" with "how to purge safely."** The budget refusal and usage readout
  belong to r2-upload-budget-guard; the ZIP byte layout belongs to sovereign-store-zip-writer. This
  skill is only the invariant + archive contents between them — resist re-implementing either.
- **Validation:** self-validating by construction — download → `unzip -t` → re-import
  `records.ndjson` → re-upload from `attachments/` per `manifest.csv`, and assert row + blob counts
  match. Pair with a d1-proof-harness round-trip (purge N, restore N) and confirm the `reclaim_purge`
  audit row exists. Host-bound / hand-validated (no CI).
