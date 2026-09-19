---
name: quick-capture-inbox
description: >-
  A capture-now / triage-later inbox for a Cloudflare Worker + D1 CRM: snap a note, task, lead, or a photo
  from the phone in one tap now, then clear it from the laptop later. Each capture is a tiny row (kind ∈
  note|task|lead|content, a text body, an OPTIONAL inline image) with an open→done lifecycle; the image is
  stored ONLY as a bounded inline data-URL PREVIEW (client downscales via canvas to a small JPEG, server
  refuses anything over ~400 KB) while full-resolution media is deferred to the Drive/content pipeline — so
  the row and the newest-first list payload stay small. A `content` capture can be PROMOTED into the social
  content queue in one step (carrying the capture id as the media key + explicit consent), which marks the
  capture done. Use WHENEVER a build needs "quick capture", "an inbox to jot things and deal with them
  later", "snap a photo/lead from my phone now", "capture-then-triage", "a scratch queue for the operator",
  "get it out of my head into the CRM", or "send this photo to the post queue later". It COMPLEMENTS
  private-operator-companion-pwa (its usual mobile capture surface), content-studio-publisher (the promote
  target — content_items; do NOT rebuild the publisher), crm-build-standard (a `lead` capture becomes a real
  CRM lead when triaged), and field-encryption-at-rest (wrap the body if a capture can hold PII). Guardrail:
  the inline media is a downscaled PREVIEW, never full-res base64 in D1; `kind`/`status` are CHECK-constrained
  enums (keep the handler's whitelist in sync); open→done is a soft triage (rows persist for audit), not a
  delete.
---
# quick-capture-inbox — snap it now on the phone, triage it later at the desk

## What it is / when to use
The "don't lose the thought / the lead / the photo" queue. One endpoint accepts a fast capture — a line of
text and optionally a small image — from wherever the operator is; a second lists the open ones newest-first;
a third marks one done. A `content` capture has a fourth path: promote it into the social content queue. It
is deliberately tiny and un-opinionated: it is an INBOX, not a workflow — the real home for each item
(a CRM lead, a scheduled post, a task) is another skill, reached when the item is triaged. Reach for it any
time an operator app wants a low-friction "capture now" affordance backed by a durable list.

**Composes with (do not duplicate):**
- **private-operator-companion-pwa** — the mobile app that is the capture's usual front-end (camera →
  downscale → POST). This skill is server-side + the tiny table; that skill hosts the UI.
- **content-studio-publisher** — a `content` capture is promoted into `content_items` (its queue). This
  skill hands off; it does not publish.
- **crm-build-standard** — a `lead` capture is a raw jotting; converting it into a `contacts`/`leads` row is
  a triage step that belongs to the CRM core.
- **field-encryption-at-rest** — the reference stores the body in the clear; if captures can hold PII (a
  `lead`'s name/number), wrap `body` with `encField`/`decField`.

## Reference implementation (ronininc — read these; patterns only, no client data)
- **Handlers** — `worker/captures.ts`:
  - `createCapture` `:9-21` — `kind` validated against `KINDS = {note,task,lead,content}` (falls back to
    `note`); requires a body OR media; **caps inline media**: keep `media_dataurl` only if it starts with
    `data:` and is `<= 400000` chars (~400 KB), else store `null`. Insert `(id,kind,body,media_dataurl,created_at)`.
  - `listCaptures` `:23-28` — `status='open'` newest-first `LIMIT 40`.
  - `captureDone` `:30-37` — flip one row to `status='done'`.
  - `queueContent` `:43-66` — promote: validate a title + a platform whitelist
    (`{instagram,facebook,x,linkedin,youtube,tiktok}`), default `scheduled_for` to tomorrow, mint a
    `public_token`, pull LIGHT media metadata from the capture (`media_provider='phone_capture'`,
    `media_key=captureId`, bytes sync to Drive later), insert a `content_items` row with `explicit_consent=1`,
    then mark the source capture done.
- **Schema** — `migrations/0052_captures.sql`: `captures(id, kind DEFAULT 'note' CHECK IN (...), body
  DEFAULT '', media_dataurl, status DEFAULT 'open' CHECK IN ('open','done'), created_at)` +
  `idx_captures_status(status, created_at DESC)`.
- **Routes** — `worker/admin.ts:334-337` — `GET capture` / `POST capture` / `POST capture/done` /
  `POST content/queue`, all behind the admin/staff gate.
- **Client (the downscale half)** — `public/companion/companion.js`:
  - `downscale(file, max, cb)` `:161-165` — loads the picked/taken image, draws it onto a `<canvas>` scaled
    so its longest edge ≤ `max`, and returns `canvas.toDataURL('image/jpeg', 0.6)`. This is what keeps the
    inline preview under the server cap; the client, not the server, does the shrinking.
  - `postCapture` `:160`, `loadCaps` `:151-159` (thumbnails from `media_dataurl`, non-`content` items as a
    done-able list), and the content editor `:167-187` that calls `postCapture({kind:'content'})` then
    `content/queue`.

## How to reapply it
1. **Migration.** One table: `id`, `kind` (CHECK-constrained enum), `body TEXT DEFAULT ''`, `media_dataurl
   TEXT` (nullable), `status` (`open|done` CHECK), `created_at`; index on `(status, created_at DESC)`.
2. **createCapture.** Validate `kind` against a whitelist that MATCHES the CHECK; require body-or-media;
   accept `media_dataurl` only if it's a `data:` URL under your byte cap, else store null. Nothing else.
3. **list / done.** `WHERE status='open' ORDER BY created_at DESC LIMIT n`; a one-row UPDATE to `done`.
4. **Client downscale.** Before POST, downscale any image on a canvas to a small JPEG (longest edge ~1280,
   quality ~0.6) so it fits the cap; do NOT send the raw camera file.
5. **Promotion (optional).** If a capture kind targets another queue (here `content` → the publisher), add a
   promote endpoint that creates the destination row carrying the capture id as the media key and marks the
   capture done. Full-res media syncs later via your Drive/content pipeline; the capture only carried a preview.
6. **Wire it behind the staff gate** and give it a capture screen (the companion PWA is one).

## Gotchas (from the code)
- **Inline media is a bounded PREVIEW, not storage.** The server hard-caps `media_dataurl` (~400 KB) and the
  client downscales to hit it; full-resolution belongs in Drive/the content pipeline, reached by the
  `media_key` later. Storing full-res base64 in D1 bloats every row AND the 40-row list payload — don't.
- **Oversized media is dropped, not rejected.** `createCapture` silently stores `null` when the data-URL is
  too big rather than erroring — so a capture still saves its text. If you need "photo required," downscale
  client-side first (as the reference does) so it fits, and surface a client-side error if it can't.
- **`kind`/`status` are CHECK-constrained enums.** The handler's whitelist and the SQLite CHECK must agree;
  an unlisted `kind` both falls back to `note` in code and would be rejected by the CHECK. Change both together.
- **Promotion is one-way and hands off governance.** Once a `content` capture becomes a `content_items` row it
  is governed by the publisher's rules (`explicit_consent`, schedule, per-platform send) — the capture is done
  and no longer the source of truth.
- **open→done is a soft triage, not a delete.** Rows persist (useful as an audit of what was captured). Add a
  retention sweep if the table grows; don't repurpose `done` as "deleted."
- **No encryption in the reference.** `body`/`media_dataurl` are stored in the clear. A `lead` capture can hold
  a name/phone — if that's in scope, wrap the body with field-encryption-at-rest like the CRM's notes.
