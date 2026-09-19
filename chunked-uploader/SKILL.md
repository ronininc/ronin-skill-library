---
name: chunked-uploader
description: >-
  Upload files of ANY size into a Cloudflare Worker + D1 app with NO R2 — the browser slices the
  file into fixed raw chunks, base64-encodes each, and POSTs them sequentially past the Worker's
  per-request body cap; the server assembles them across D1 rows (a feeds row + ordered feed_chunks
  rows), recomputes size from ground truth on every chunk, and streams the file back one chunk at a
  time on download so the isolate never OOMs. Use WHENEVER a build must accept a big upload and you
  don't want (or can't enable) object storage: "let them upload a file", "attach a document/video/
  export", "upload is failing / too large", "413 on upload", "store the file in the database",
  "no R2 / sovereign storage", or a drag-and-drop dropzone with a progress bar. EXTENDS
  commerce-spine / cf-functions (the Worker + D1 node it stores into). Guardrails: per-chunk base64
  stays safely under D1's ~2 MB row cap; best-effort rollback of a half-written upload on error;
  a cron reaps abandoned "uploading" feeds; only a finished ('stored') file is downloadable so a
  truncated upload is never served as complete. NOT for card-present/POS or for files that belong
  in R2 when R2 IS available (use R2 then) — this is the sovereign-in-D1 fallback.
---
# chunked-uploader — big uploads on Workers, no R2

## What it is / when to use
Cloudflare Workers cap a single request body (and D1 caps a single row at ~2 MB), so you cannot
POST a large file in one shot or stuff it in one row. This capability streams the file up in
bounded base64 chunks (one HTTP request each), threads a server-assigned id through the sequence,
assembles the chunks across D1 rows, and streams them back on download. Reach for it on any
Cloudflare-hosted app that needs to accept files larger than a request body when R2 isn't in play.

## Reference implementation (Wavelygth — lift from here)
- **Client** — `~/Projects/clients/wavelygth/portal/index.html`
  - `FEED_RAW_CHUNK = 512 * 1024` L1968 — 512 KB raw ⇒ ~683 KB base64 body (well under caps).
  - `bufToB64(bytes)` L1976-1980 — base64-encodes a `Uint8Array` in **0x8000-byte windows** via
    `String.fromCharCode.apply` (a single `apply` over a big array throws "too many arguments").
  - `uploadFile(file)` L2013-2044 — the chunk loop: `Math.ceil(size / FEED_RAW_CHUNK)` chunks,
    `file.slice(...).arrayBuffer()` per chunk, POST `?seq=N&last=0|1` (+ `name` on seq 0), body
    `{ b64, content_type? , feed_id? }`; **seq 0 returns the server-assigned `feed_id`** which is
    threaded into every subsequent chunk; per-file progress bar; on error, `catch` marks the row
    failed and fires a **best-effort DELETE** of the partial upload.
  - `ingestFiles` + dropzone/drag wiring L2045-2055.
- **Server** — `~/Projects/clients/wavelygth/worker/index.js`
  - `FEED_CHUNK_B64_MAX = 900000` L2890, `FEED_UPLOAD_BODY_MAX = 1400000` L2927.
  - `handleFeedUpload(req, env, me, url)` L2928-2968 — reads `seq`/`last` from the query; **seq 0
    creates the feeds row** (status `uploading`) and mints the id; later chunks validate the id
    exists; `INSERT OR REPLACE INTO feed_chunks (feed_id, seq, bytes, bytes_b64)`; then it
    **recomputes** `chunk_count`/`size_bytes` from `SELECT COUNT(*)/SUM(bytes)` (NOT additively —
    a replayed/out-of-order seq can't inflate the total); `last=1` flips status to `stored`.
  - `handleFeedDownload(env, id)` L2994-3022 — refuses unless `status='stored'`, then a
    `ReadableStream` whose `pull()` fetches ONE chunk row, `atob`-decodes to bytes, enqueues — flat
    isolate memory regardless of file size (a buffered reassembly OOMs the ~128 MB isolate).
  - `handleFeedDelete` L3025-3036 (batch: chunks + row drop together) and `reapStaleFeeds(env)`
    L3041-3053 (cron reaps feeds stuck `uploading` > 1h).
- **Schema** — `~/Projects/clients/wavelygth/worker/migrations/0004_feeds.sql`: `feeds`
  (id, kind, name, content_type, size_bytes, chunk_count, status, …) + `feed_chunks`
  (feed_id, seq, bytes, bytes_b64, PRIMARY KEY (feed_id, seq)).
- **Routes** — L3252 upload, L3253-3257 get/download, L3258-3260 delete; admin gate L3172.

## How to reapply it
1. **Migration:** add a parent table with `status` + `size_bytes` + `chunk_count`, and a
   `*_chunks(parent_id, seq, bytes, bytes_b64, PRIMARY KEY(parent_id, seq))`.
2. **Server:** copy `handleFeedUpload`'s shape — seq-0-creates, later-chunks-validate,
   `INSERT OR REPLACE` the chunk, **recompute** count/size from the chunk table. Add a `readJson`
   body cap sized for one chunk (~1.4 MB). Copy the streaming `handleFeedDownload` and the
   status='stored' guard verbatim.
3. **Client:** copy `bufToB64` and the `uploadFile` chunk loop; thread the server id from seq 0;
   drive a progress bar off `(seq+1)/total`; on failure fire the best-effort DELETE.
4. **Cron:** wire `reapStaleFeeds` into your `scheduled()` so abandoned uploads self-clean.

## Gotchas (from the code + comments)
- **Base64 in windows.** `btoa(String.fromCharCode.apply(null, hugeArray))` throws — chunk the
  `fromCharCode` in 0x8000-byte slices (`bufToB64`).
- **Recompute size from ground truth, never a running total.** `INSERT OR REPLACE` means a client
  retry/replay of a seq must not double-count — always `SELECT SUM/COUNT` after each write.
- **Stream downloads chunk-by-chunk.** Buffering the whole file to reassemble will OOM the isolate
  on a genuinely large "any size" file. The `ReadableStream.pull` pattern keeps memory flat.
- **Only serve a finished file.** Gate download on `status='stored'` (409 otherwise) or a
  half-uploaded file gets handed back silently truncated as if complete.
- **Delete atomically** (batch chunks + row) so a concurrent continuation chunk can't orphan a row.
- Keep the raw chunk (512 KB) × 4/3 base64 expansion comfortably under BOTH the D1 row cap (~2 MB)
  and your `readJson` body cap. Don't push the chunk size to the limit.
- This is the **no-R2 fallback**. If R2 is enabled on the account, use R2 for large binaries — this
  pattern exists precisely because R2 was off.
