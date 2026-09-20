---
name: sovereign-store-zip-writer
description: >-
  Build a real, standards-correct .zip archive from many in-memory files INSIDE a Cloudflare
  Worker (or any pure-JS runtime) with ZERO dependencies — no npm zip lib, no supply-chain surface,
  no native module. Uses the ZIP STORE method (no compression): correct local file headers +
  central directory + end-of-central-directory records + a hand-rolled IEEE CRC32, so the output
  opens in `unzip`, macOS Finder and Windows Explorer unchanged. One pure function
  makeZip(entries, when) -> Uint8Array turns a list of {name, data:Uint8Array} into a single
  downloadable/streamable buffer. Use WHENEVER a build must hand back MANY files as one archive
  from the edge: "back up the CRM / their records", "let me download everything", "we're near the
  R2 limit — export before we purge", "purge old uploads safely", "bundle these attachments +
  a manifest into one zip", "give them a portable export they can re-import", or "generate a zip
  in the Worker without adding a dependency". COMPLEMENTS export-before-delete-reclaim (that skill
  owns the build-archive-BEFORE-any-delete choreography, per-run byte cap and manifest — THIS skill
  is only the byte-exact writer it calls), chunked-uploader (the ingest side: many chunks IN to
  D1/R2 — this is the bundle side: many files OUT as one archive), and drive-rich-doc-generator
  (a single Google-native Doc/Sheet from inline text — this is a portable multi-file .zip that
  needs no SaaS to open). Guardrails: STORE only — it does NOT compress (perfect for
  already-compressed media / gzip, wasteful for large plain text); the whole archive is assembled
  in ONE Uint8Array in isolate memory, so cap total bytes per run (well under the ~128 MB Worker
  ceiling) and paginate big jobs; no ZIP64, so a single archive and any one entry must stay
  under 4 GB. Patterns/contracts only — genericize every field; never copy client names or data.
---
# Sovereign STORE-method ZIP writer (dependency-free, Worker-safe)

## What it is / when to use / what it composes with
A ~110-line, dependency-free ZIP writer that runs in a Cloudflare Worker (or Deno/Bun/browser).
It emits a spec-correct `.zip` using the **STORE** method (no compression), so there is no npm
`zip`/`jszip`/native dependency and no supply-chain surface — the whole thing is `Uint8Array` +
`DataView` + `TextEncoder`. You give it a list of files already in memory; it hands back one
buffer you can return as a download or stream to R2.

Reach for it whenever a build must return **many files as one archive** from the edge: a records
backup, a "download everything" button, an export-before-purge safety archive, or bundling
attachments plus a `manifest.csv` / `records.ndjson` into a single portable file the client can
re-import later.

It composes as the **writer primitive** under three neighbours — extend them, do not re-implement:
- **export-before-delete-reclaim** — owns the *safety choreography* (build the archive BEFORE any
  destructive delete, per-run byte cap, manifest + re-import story). It *calls* this writer. Keep
  the "when do we delete" logic there; keep the "how do bytes become a .zip" logic here. (Both
  skills are in the library; export-before-delete-reclaim currently bundles its own copy of this
  STORE writer — this skill is the extracted primitive it should call, and the canonical home for
  the byte-mechanics. A "bundle + download, no delete" build reaches for THIS skill directly.)
- **chunked-uploader** — the *ingest* direction (slice a big file IN across D1 rows). This is the
  opposite direction: gather many stored blobs OUT into one archive.
- **drive-rich-doc-generator** — delivers a *single* Google-native Doc/Sheet from inline text via
  Drive import. This delivers a *portable multi-file* `.zip` that opens anywhere with no SaaS and
  no OAuth. Pick per deliverable; they don't overlap.

## Reference implementation — exact source (lift the proven code from here)
Proven + shipped in the app-forge CRM baseline (commit `f2fbc68`, "export-before-delete reclaim").
Cite these when a future build lifts the code:

- **`worker/zip.ts`** — the whole writer:
  - `worker/zip.ts:12-20` — CRC32 lookup table, built once via IIFE, polynomial `0xEDB88320`.
  - `worker/zip.ts:22-26` — `crc32(buf)` — init `0xffffffff`, table-driven, final `^ 0xffffffff`,
    forced unsigned with `>>> 0`.
  - `worker/zip.ts:29-33` — `dosDateTime(d)` — packs local mtime into the two 16-bit DOS fields
    (year offset from 1980, seconds/2).
  - `worker/zip.ts:35` — `interface ZipEntry { name: string; data: Uint8Array }` — the only input contract.
  - `worker/zip.ts:39-109` — `makeZip(entries, when=new Date()): Uint8Array`:
    - `:51-64` local file header (30 bytes, sig `0x04034b50`), then `parts.push(header, nameBytes, data)`.
    - `:66-84` central directory record (46 bytes, sig `0x02014b50`), pushed to a separate `central[]`.
    - `:86` running `offset += header.len + nameBytes.len + size` — the relative-offset bookkeeping.
    - `:89-100` end-of-central-directory (22 bytes, sig `0x06054b50`) with `centralSize` + `centralOffset`.
    - `:102-108` allocate one `Uint8Array(total)` and blit parts → central → EOCD in order.
- **`worker/reclaim.ts`** — the reference consumer that proves the writer end-to-end:
  - `worker/reclaim.ts:20` — `import { makeZip, type ZipEntry } from './zip'`.
  - `worker/reclaim.ts:72-129` — assembles `ZipEntry[]` from R2 blobs plus a generated
    `manifest.csv`, `records.ndjson` (re-importable) and `_reclaim-summary.json`.
  - `worker/reclaim.ts:132` then `:135-139` — **THE INVARIANT** (see below): `makeZip(entries)`
    returns bytes *before* the first `.delete()` / `DELETE` runs.
  - `worker/reclaim.ts:143-153` — returns the buffer as `application/zip` with a
    `content-disposition: attachment; filename=...` plus `x-*` count headers.
- **Wiring**: `worker/admin.ts:72` imports the handlers; `worker/admin.ts:398-399` routes
  `GET .../reclaim/preview` (read-only estimate) and `POST .../reclaim/export-purge`.
  Admin-only by omission — `worker/reclaim.ts:14-15` notes it is deliberately NOT in the
  clearance `SUB_SECTION`, so only the owner reaches it.

## How to reapply
No migration or schema of its own — `zip.ts` is a leaf module with zero imports. You wire the
*consumer*, not the writer.

1. **Copy the primitive.** Lift `zip.ts` verbatim into the new Worker's `worker/`. It has no env,
   no bindings, no dependencies. Contract: `makeZip(entries: {name,data}[], when?) => Uint8Array`.
   Entry `name` may contain `/` to create folders inside the archive (e.g. `attachments/<id>/<file>`).
2. **Build entries from your own data.** Pull each file's bytes into a `Uint8Array`
   (`new Uint8Array(await r2obj.arrayBuffer())`, or `TextEncoder().encode(str)` for generated
   `.csv`/`.ndjson`/`.json`). Sanitize every `name` — the reference maps `[^\w.\-]+` → `_` and
   slices to 120 chars (`reclaim.ts:95`) so a hostile filename can't break the archive layout.
3. **Route a handler.** A read-only *preview* (what would be archived / how many bytes) plus a
   *do-it* POST that requires `confirm:true`. Return the buffer with `content-type: application/zip`
   and `content-disposition: attachment; filename="export-YYYY-MM-DD.zip"`.
4. **UI**: a "Download / Back up" or "Reclaim space" button that hits preview, shows the estimate,
   then POSTs with confirmation and saves the streamed file.
5. **Cron (optional)**: only if you want scheduled backups — guard it so a hiccup can't abort other
   cron tasks. (The reference reclaim is manual/admin-triggered, not cron.)

**THE INVARIANT — the reason this pattern exists:** when the archive precedes a *destructive*
action (purge/reclaim), build the complete archive FIRST and only run deletes AFTER `makeZip`
returns. `makeZip` is synchronous and either returns the full buffer or throws — so if archiving
fails, nothing is deleted (`reclaim.ts:132` then `:135-139`). Every record that will be deleted
must be represented in the archive (the reference even writes a metadata row for a blob whose
bytes are already gone, `reclaim.ts:100-102`), so "export before delete" holds literally.

## Gotchas — real pitfalls from the code + how it's validated
- **STORE only — it does not compress.** Method field is `0` and *both* size fields are set to the
  raw length (local header `zip.ts:59-60`; central directory `:75-76`). Ideal for already-compressed inputs (media, gzipped
  NDJSON backups); if you archive large plain text expecting it to shrink, it won't — that's by
  design (cheapest CPU on the edge, no zlib dependency).
- **CRC32 is mandatory even for stored entries.** Get the exact recipe right: poly `0xEDB88320`,
  init `0xffffffff`, final `^ 0xffffffff`, and `>>> 0` to stay unsigned (`zip.ts:16,23-25`). A
  missing final-XOR or a signed wrap yields "CRC mismatch" from `unzip`.
- **Everything is little-endian.** Every `setUint16/32` passes `true`. One big-endian write and
  the archive is unreadable.
- **Offset bookkeeping must match the byte order exactly.** The central record's relative offset
  (`zip.ts:83`) points at each local header; it only stays correct because `offset` advances by
  `header.len + nameBytes.len + size` in the *same* order bytes are pushed (`:64`, `:86`). Change
  the push order and every offset lies.
- **EOCD counts and sizes must be truthful.** Entry count is written twice (this-disk + total,
  `:96-97`) and `centralSize`/`centralOffset` (`:98-99`) must equal the real bytes, or readers
  report a broken/truncated archive.
- **In-memory, whole-buffer, no streaming.** `makeZip` allocates one `Uint8Array(total)`
  (`:103`). Cap total bytes per run well under the ~128 MB isolate ceiling and paginate — the
  reference caps at 30 MB/run and reports `remaining` for a follow-up run (`reclaim.ts:25,86`).
- **No ZIP64.** All size/offset fields are 32-bit, so a single archive and any one entry must be
  < 4 GB. For bigger, split into multiple archives (the per-run cap does this naturally).
- **UTF-8 filenames**: bit 11 of the flags is set (`0x0800`, `:54`,`:70`) so non-ASCII names
  extract correctly; still sanitize names as above.
- **DOS date floor**: `dosDateTime` offsets the year from 1980 (`:31`); a pre-1980 `when`
  underflows. Default `new Date()` is fine.
- **How it's validated**: open the emitted buffer with a real `unzip` (list + extract) and do a
  binary round-trip — extract each entry and byte-compare it against the original `data`, and
  confirm CRC/sizes via `unzip -t`. This is host-bound / hand-validated (no CI); the reference
  shipped in commit `f2fbc68`. Re-run that round-trip after any change to header offsets or CRC.
