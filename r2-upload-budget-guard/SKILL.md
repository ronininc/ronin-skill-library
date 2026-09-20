---
name: r2-upload-budget-guard
description: >-
  Keep a Cloudflare R2 build from silently tripping into overage: the 10 GB free tier is
  ACCOUNT-wide (shared by every bucket AND every instance on the account), so this puts a
  per-instance upload BUDGET GUARD in front of the one unbounded multiplier — writes are
  REFUSED (HTTP 507) once total R2 usage would cross a soft budget (default 9 GB, 1 GB
  headroom under the cap), using an early-stopping running sum that stops the moment it
  exceeds the budget so it costs a full list only while there's room. Ships with a live
  USAGE READOUT (R2 bytes grouped by key-prefix + D1 size via PRAGMA page_count × page_size
  and per-table row counts vs the free caps, with headroom + an over_budget flag) and an
  edge-cache (Cache API `caches.default`) proxy for third-party imagery so hot tiles are
  NEVER stored in R2. Use WHENEVER a build touches R2 free-tier limits or storage safety:
  "we're near the R2 limit", "refuse uploads past the free tier", "how much R2/D1 am I
  using", "keep many instances under one account's storage cap", or "edge-cache third-party
  tiles instead of storing them in R2". COMPLEMENTS (extend, do NOT duplicate): d1-image-store
  (the no-R2 free-tier baseline — this guards the build AFTER it graduates to R2),
  worker-media-headers (range/CSP serving of the bytes), chunked-uploader (the no-R2 big-file
  path this bounds), and its two storage-lifecycle SIBLINGS — logical-backup-ndjson-r2 (the DB
  dump / retention / restore; the readout here only DISPLAYS `backups/` bytes, that skill OWNS
  writing + pruning them) and export-before-delete-reclaim (archive-then-purge to free space;
  this refuses the WRITE, that reclaims the SPACE). Guardrails: the budget is ACCOUNT-wide, not
  per-bucket — sum the whole bucket, refuse (never truncate), and re-check the TRUE object size
  after the put when Content-Length was absent (roll the object back if it crossed); edge-cache
  third-party imagery, don't store it.
---
# R2 Upload Budget Guard — account-wide free-tier discipline for a Worker + R2 build

## What it is / when to use
Cloudflare's R2 free tier is **10 GB of stored bytes, ACCOUNT-wide** — every bucket and every
instance deployed on the account draws from the same 10 GB. A build that lets users upload files
(the one storage line with no natural ceiling) will quietly cross that cap once you run several
instances, and the first you hear of it is a bill. This capability is the discipline that stops
that: a per-instance **budget guard** that refuses an upload before it can push the account into
overage, a **usage readout** so an operator can watch the caps directly from inside the Worker, and
an **edge-cache** for third-party imagery so it never lands in R2 at all.

Reach for it on any Cloudflare Worker + R2 build the moment uploads are in play — especially a
multi-instance / multi-tenant product where one account fans out to many deployments. It is
patterns and contracts only; wire it to your own bucket binding, your own upload path, and your
own entity model.

**What it composes with**
- **d1-image-store** — the free-tier BASELINE that stores bytes as base64 in D1 with no R2 at all.
  This guard is what you add *after* a build graduates to R2. Different layer: d1-image-store avoids
  R2; this bounds R2.
- **worker-media-headers** — owns byte-range 206 / CSP / content-type serving. This skill owns
  *whether the bytes are allowed to be written*; that owns *how they're served*.
- **chunked-uploader** — the sovereign no-R2 path for big files. This guard bounds the R2 upgrade
  path it exists to avoid.
- **logical-backup-ndjson-r2** *(sibling — cite, don't duplicate)* — owns the D1 → gzip-NDJSON → R2
  backups + keep-N retention + restore. The usage readout here just *reports* the `backups/` prefix's
  byte total; it never writes or prunes backups — that skill does.
- **export-before-delete-reclaim** *(sibling — cite, don't duplicate)* — owns the archive-then-purge
  choreography that frees space when the budget is hit. This skill refuses the WRITE at the door;
  that skill is the reclaim you run when the readout shows `over_budget`.

Do NOT re-author the backup or reclaim mechanics here — the two siblings own them. This skill owns
only the account-wide budget refusal, the usage readout, and the edge-cache-instead-of-R2 rule.

## Reference implementation (proven, shipped + tested — lift the proven code from here)
A Cloudflare Worker + R2 + D1 CRM baseline. R2 is exposed as an OPTIONAL bucket binding
(`env.<BUCKET>`, optional so the Worker still type-checks and boots without R2); genericize the
binding name, the key prefixes, and the entity/record model when you reapply.

- **The budget refusal (the load-bearing part)** — `worker/attachments.ts`
  - `r2Budget(env)` **L30-33** — read `R2_BUDGET_BYTES` env, default `9 * 1024**3` (1 GB headroom
    under the 10 GB cap).
  - `r2UsedBytes(env, stopAt)` **L34-43** — the **early-stopping running sum**: page the whole
    bucket with `.list({ limit: 1000, cursor })`, add each object's `.size`, and `return` the
    instant `used >= stopAt`. Costs a full bucket list only while there's still room; once over, it
    bails on the first page that crosses.
  - Upload handler **L79-99** — the actual refusal: pre-check `r2UsedBytes(env, budget) + declared > budget`
    → `507`; after the `.put`, re-check with the **true** returned size (`put.size`) and, when
    Content-Length was absent, roll the object back (`.delete`) if it crossed. Also enforces a
    per-file byte cap independent of the account budget.
- **The usage readout** — `worker/usage.ts`
  - Free-cap constants **L12-17** — `R2_FREE = 10 GB` (commented ACCOUNT-wide), `D1_FREE = 5 GB`,
    same `r2Budget` default.
  - `usageReport(env)` **L19-66** — R2: page the bucket, sum bytes, and **group by key-prefix**
    (`backups/`, `uploads/…`, `.pmtiles`, other) so the readout shows *what* is using space (the
    `backups/` line is written by the logical-backup-ndjson-r2 sibling; here it's read-only display);
    compute `headroom_bytes` + `over_budget`. D1: real size from `PRAGMA page_count` × `PRAGMA
    page_size`, plus per-table `COUNT(*)` for the top tables. Returns a plain-English `note` naming
    the account-wide caveat and the mitigations.
- **Edge-cache third-party imagery, NOT R2** — `worker/sattiles.ts` **L15-37** — a same-origin proxy
  that serves hot third-party raster tiles from `caches.default` (`cache.match` → on miss `fetch`
  upstream → `cache.put(key, out.clone())` via `ctx.waitUntil`), with a long immutable
  `Cache-Control`. Repeat hits never re-fetch and are never written to R2.
- **Env contract** — `worker/types.ts` **L12-18** — optional bucket binding + `R2_BUDGET_BYTES?`,
  with the account-wide caveat documented inline.
- **Route + UI** — `worker/admin.ts` **L397** (`GET usage`), **L664-666** (upload / list / serve);
  `public/admin/admin.js` **L3472-3491** — fetch `/api/admin/usage`, render R2 vs budget with a
  headroom line and a "Budget reached" pill when `over_budget`.
- **Proof** — `worker/lib/_proof/attachments.test.mjs` — upload → list → serve → tenancy 404s against
  a real Worker + D1 harness; the budget refusal is a pure function of `r2UsedBytes` + the
  declared/true-size checks, so it's covered by driving an upload against a budget-constrained bucket.

## How to reapply

### 1. Env
No migration for the guard itself — it reads the live bucket. Add to your `Env`:
```ts
BUCKET?: R2Bucket;        // your R2 binding — optional so the Worker boots without R2
R2_BUDGET_BYTES?: string; // soft ceiling; default below leaves 1 GB headroom under 10 GB
```

### 2. The budget guard (drop in front of every R2 write)
```ts
const r2Budget = (env: Env) => {
  const n = parseInt(env.R2_BUDGET_BYTES || '', 10);
  return Number.isFinite(n) && n > 0 ? n : 9 * 1024 * 1024 * 1024; // 9 GB default
};
// Early-stopping running sum: full list ONLY while there's room; bails once over.
async function r2UsedBytes(env: Env, stopAt: number): Promise<number> {
  let used = 0, cursor: string | undefined;
  do {
    const page = await env.BUCKET!.list({ limit: 1000, cursor }).catch(() => null);
    if (!page) break;
    for (const o of page.objects) { used += o.size; if (used >= stopAt) return used; }
    cursor = page.truncated ? page.cursor : undefined;
  } while (cursor);
  return used;
}
```
In the upload handler, **before** the put use the declared size; **after** the put re-check the
true size and roll back if it crossed:
```ts
const budget = r2Budget(env);
if ((await r2UsedBytes(env, budget)) + (declared || 0) > budget)
  return bad('Storage budget reached — free up space or raise R2_BUDGET_BYTES.', 507);
const put = await env.BUCKET.put(key, req.body, { httpMetadata: { contentType } });
const size = (put && put.size) || declared || 0;
if (!declared && (await r2UsedBytes(env, budget + size)) > budget) {
  await env.BUCKET.delete(key).catch(() => {});       // undeclared size crossed → roll back
  return bad('Storage budget reached — free up space or raise R2_BUDGET_BYTES.', 507);
}
```
When the readout shows `over_budget`, the space is freed by the **export-before-delete-reclaim**
sibling — do not implement a purge here.

### 3. Usage readout handler → `GET /…/usage`
Sum the bucket grouped by key-prefix; read D1 size from `PRAGMA page_count` × `PRAGMA page_size` and
per-table `COUNT(*)`; return `{ r2: { bytes, groups, budget_bytes, headroom_bytes, over_budget,
limit_bytes }, d1: { bytes, rows, top_tables, limit_bytes }, note }`. Request/op COUNTS are
account-level metrics not queryable from a Worker without an analytics token — point the operator to
the dashboard for those rather than faking them.

### 4. Edge-cache third-party imagery (Cache API, not R2)
For repeatedly-fetched third-party assets (map tiles, remote thumbnails), proxy same-origin through
`caches.default` — `cache.match(key)` → miss → `fetch` upstream → `cache.put(key, res.clone())` via
`ctx.waitUntil`, with a long `immutable` `Cache-Control`. Never `.put` these into R2.

### THE INVARIANTS
1. **The budget is ACCOUNT-wide.** Sum the whole bucket and refuse against the total — never assume a
   per-bucket ceiling. To scale past one account's free tier, deploy each tenant to its own account.
2. **Refuse, never truncate.** An over-budget write returns `507`; it does not write a partial or
   silently overwrite.
3. **Re-check the true size after the put.** Content-Length can be absent; if the real returned size
   crossed the budget, delete the object and refuse.

## Gotchas (real pitfalls from the code + how they're validated)
- **The cap is not per-bucket.** The single most common wrong mental model. `usage.ts:12` and
  `types.ts:12-18` document it inline precisely because it's the thing everyone gets wrong: 10 GB is
  shared across every bucket and every instance on the account.
- **A naive "sum the bucket" is unbounded.** `r2UsedBytes` takes a `stopAt` and returns early
  (`attachments.ts:39`) so the guard costs a full list only when there's room. Without early-stop, a
  large bucket makes every upload pay a full enumeration.
- **Content-Length lies (or is absent).** The declared-size pre-check is necessary but not
  sufficient; the post-put re-check with `put.size` and the rollback (`attachments.ts:96-99`) is what
  makes an undeclared-size upload unable to sneak past the budget.
- **Third-party imagery in R2 is a self-inflicted overage.** Hot tiles/thumbnails belong in
  `caches.default` (`sattiles.ts:19-35`), which is free and edge-local; storing them in R2 both eats
  the budget and adds egress.
- **Request/op counts aren't queryable from the Worker.** Don't fabricate them — the readout measures
  storage directly and points to the dashboard for account-level op metrics (`usage.ts:6`, `:64`).
- **Don't reclaim here.** When the budget is hit, the fix is the export-before-delete-reclaim sibling
  (archive-then-purge) and pruning old backups via logical-backup-ndjson-r2's keep-N — not a purge
  bolted onto this guard. Keeping the write-refusal and the space-reclaim in separate skills is what
  keeps each one's invariant intact.
