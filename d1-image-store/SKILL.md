---
name: d1-image-store
description: >-
  Serve product/entity images straight out of D1 as base64 TEXT — NO R2, NO object store, no paid
  subscription or card — so a build can ship real imagery entirely on Cloudflare's free tier. The
  bytes live in their OWN table (one row per owner, keyed by owner id) so normal catalog queries never
  drag image bytes along; images are served at `/api/media/<id>` with an ETag + a 1-day cache; and each
  image is CAPPED (~650 KB) so one row's base64 (~4/3 of raw) stays under D1's per-query response /
  2 MB row limit — the honest workaround for storing bytes in a SQL row. Two sources feed the SAME
  rails: a manual staff upload (works immediately) and a POS/Clover image mirror ("train tracks"), and
  a demand-ranked pass auto-populates photos for the top-N most-ordered items. Use WHENEVER a build
  needs images but "no R2 / no subscription / free tier only", "store the image in the database",
  "serve product photos without object storage", "base64 image in D1", "why is my image too big for a
  D1 row", or "auto-pull top sellers' photos from the POS". It is the free-tier BASELINE that
  COMPLEMENTS commerce-spine's R2 offload (the UPGRADE path once R2 is affordable: move bytes to R2,
  keep a tiny pointer — this is what you run before that) and worker-media-headers (which owns the
  ASSETS-bound video/range-serving + CSP; this is the D1-backed image path beside it). Guardrails:
  keep the bytes in a SEPARATE table + flag the owner row so list queries stay lean; enforce the size
  cap on BOTH upload and mirror (reject, don't truncate); never invent an image — an unmapped/imageless
  item keeps the curated fallback.
---
# d1-image-store — base64 images in D1, free-tier, with the row-cap discipline

## What it is / when to use
The "we can't/won't provision R2 yet" image path. It stores image bytes as base64 in a dedicated D1
table and serves them cached with an ETag, so a merchant site gets real photos with zero object
storage and zero card on file. Reach for it on any free-tier build that needs images and hasn't
crossed the threshold where R2 is worth it — then graduate to commerce-spine's R2 offload later
without changing the serving URL.

## Reference implementation (patterns only, no client data)
All in `worker/lib/media.js`:
- `MAX_IMAGE_BYTES = 650_000` L10 — the cap that keeps base64 under D1's row/response limit.
- `serveImage(env, id)` L26–35 — decode base64 → `Response(bytes)` with `Content-Type`, `ETag`, and
  `Cache-Control: public, max-age=86400`.
- `storeImage(env, productId, ct, bytes, source)` L37–50 — `INSERT … ON CONFLICT(product_id) DO UPDATE`
  upsert into `product_images`, then flag the owner row (`products.image_key='db'`, `image_source`) so
  the catalog query can emit an `image_url` WITHOUT selecting the bytes.
- `uploadImage` L53–60 — manual staff upload path (raw bytes → D1), rejects empty / over-cap.
- `syncItemImage` / `syncAllImages` L63–90 — mirror a POS/Clover item image into D1 (the "train tracks").
- `topOrderedProductIds` L97–108 + `syncTopImages` L111–124 — DEMAND-ranked auto-populate: pull photos
  for the top-N most-ordered mapped items; `syncImageByCloverItem` L127–131 is the webhook-driven re-pull.
- **Schema:** `worker/migrations/0010_image_store_d1.sql` — `product_images(product_id PK, content_type,
  data_b64, bytes, etag, source, updated_at)`, its own table so bytes never ride along.
- Base64 helpers L12–23 chunk `String.fromCharCode` (0x8000) to avoid arg-length limits on big buffers.

## How to reapply
1. Migration: a dedicated `<entity>_images` table (PK = owner id) holding `data_b64` + `content_type` +
   `etag` + `bytes` + `source`; add an image flag/columns to the owner table for lean list queries.
2. Route: `GET /api/media/<id>` → `serveImage` (see `worker/index.js` L119); `POST …/image` → `uploadImage`
   (L1074) with the raw body + its `Content-Type`.
3. Optional POS mirror + demand-ranked top-N sync on a cron / admin button (L1021).

## Gotchas (from the code)
- Enforce the cap on BOTH paths (upload AND mirror) and REJECT over-cap with a clear message — never
  truncate image bytes.
- Keep bytes in a separate table and never `SELECT *` them in a list query; emit an `image_url` from the
  owner-row flag instead, or every catalog read pays the base64 tax.
- This is the free-tier baseline; the growth escape (past ~10 GB / for bigger images) is commerce-spine's
  R2 offload — move bytes to R2 + a pointer row, keeping the same `/api/media/<id>` URL.
- Never fabricate imagery: an unmapped or imageless item keeps the curated fallback rather than inventing one.
