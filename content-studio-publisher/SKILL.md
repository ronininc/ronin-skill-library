---
name: content-studio-publisher
description: >-
  Native, multi-channel organic-social SCHEDULER + publisher for a Worker+D1 client CRM — publishes
  to Instagram, Facebook, X, LinkedIn, YouTube and TikTok on each platform's OWN official API, with
  no third-party publishing SaaS in the loop. Use WHENEVER a CRM build needs to "schedule social
  posts", "publish to Instagram/FB/X/LinkedIn/YouTube/TikTok from the CRM", "a content calendar",
  "post organic content on a schedule", "queue posts", or "our own Buffer/Hootsuite/Later". It gives
  you: a weekly content queue with timezone-correct next-open-slot scheduling, a per-platform
  publishing LEDGER (queued→publishing→processing→blocked→published/failed) with retry+backoff,
  async provider state machines (Instagram containers, TikTok, YouTube resumable upload), and an
  opaque per-item media proxy so platforms pull media by URL without ever seeing your storage
  account. COMPLEMENTS crm-build-standard (this is the organic-publishing organ, not the CRM core),
  google-oauth-connector (media lives in the connected Drive; do NOT re-implement Drive auth),
  white-label-branding (brand the admin UI), and pluggable-draft-brain (wire it in for AI-drafted
  captions — captions are MANUAL in the reference). For DM/inbound social use social-dm-inbox
  instead; to delegate delivery to a self-hosted backend layer on top of this, add
  pluggable-publisher-backend. Guardrails: money/irreversible never apply here, but posts are
  irreversible once live — ship with the scheduler OFF by default, honor per-item explicit_consent
  (TikTok requires it), and NEVER echo platform tokens (all are Worker secrets).
---
# Content Studio Publisher — own your organic social publishing

A native, six-platform organic-social scheduler that lives inside a Cloudflare Worker + D1 CRM.
Each scheduled item fans out into per-platform **publications**; a 5-minute cron publishes the ones
that are due, driving each platform's official API directly. No Buffer, no Hootsuite, no Zapier.

**When to use:** a client wants to schedule and publish organic posts (feed posts, Reels, videos,
link posts) from their own CRM. **What it composes with:** `crm-build-standard` (the CRM this bolts
onto), `google-oauth-connector` (Drive holds the media bytes — reuse its `getGoogleAccessToken`),
`white-label-branding` (skin the admin panel), `pluggable-draft-brain` (optional AI captions), and
`pluggable-publisher-backend` (optional: swap native delivery for a self-hosted OpenPost instance).

## Reference implementation (ronininc-site — OPEN these, they are the source of truth)
- **`worker/content-studio.ts:1-599`** — the whole native engine:
  - Scheduling math: `localParts` (85-92), `zonedTimestamp` (94-105), `resolveSchedule` (112-122),
    `nextOpenSlot` (124-138) — one post per local day, DST-safe.
  - Read/write API: `contentDashboard` (157-189), `saveContentSettings` (191-204),
    `uploadContentMedia` (251-280 — resumable Drive upload), `driveMetadata` (282-288),
    `scheduleContentItem` (290-328), `updateContentItem` (330-389 — reconciles the per-platform
    ledger when the platform set changes), `contentMedia` (391-407 — the opaque media proxy).
  - Per-platform publishers, each on the official API: `publishX` (415-426), `publishLinkedIn`
    (428-447), `publishFacebook` (449-464), `publishInstagram` (466-497 — async container→poll→
    media_publish), `publishTikTok` (499-537 — creator-info→init→poll), `publishYouTube` (539-559 —
    resumable upload of the Drive video).
  - The engine: `runPublication` (561-587 — retry/backoff + blocked/failed classification),
    `updateItemOutcome` (589-599 — rolls per-platform rows up to published/partial/failed),
    `runScheduledContentPublishing` (725-746 — the cron entry; native branch is 740-744).
- **`migrations/0019_content_studio.sql`** — `content_settings` (single 'default' row),
  `content_items` (the queue + opaque `public_token`), `content_publications` (per-platform ledger,
  `UNIQUE(content_id,provider)`), plus the two indexes.
- **`worker/index.ts:82-89`** — the public opaque media route (`/api/content/media/<token>`,
  GET/HEAD only, no session).
- **`worker/index.ts:190-198`** — cron wiring: `runScheduledContentPublishing(env)` inside the
  `scheduled()` handler, wrapped in `.catch()` so a provider outage can't abort other cron tasks.
- **`worker/admin.ts:304-310`** — the gated admin routes (`content`, `content/settings`,
  `content/upload`, `content/schedule`, `content/item`).
- **`public/admin/admin.js:2106-2525`** — the admin UI (calendar, composer, per-item status).

## How to reapply it into a client CRM build
1. **Migration.** Copy `0019_content_studio.sql` (renumber to your project). It seeds one
   `content_settings` row (`id='default'`, `enabled` defaults on in 0019 — set it OFF for a real
   client until platforms are connected). `content_publications` is `UNIQUE(content_id,provider)`
   so each platform has exactly one ledger row per item.
2. **Handlers.** Drop in `content-studio.ts`. It imports `getGoogleAccessToken` from the
   google-oauth-connector skill's module — wire that first. Trim `PLATFORMS` (line 14) to only the
   channels the client will actually use; each platform's publisher is self-contained, so deleting
   one is safe.
3. **Routes.** Add the gated admin routes (`admin.ts:304-310` pattern, behind your `requireStaff`
   gate) AND the **public** media route (`index.ts:82-89`) OUTSIDE the admin gate — platforms fetch
   it unauthenticated.
4. **Cron.** Ensure a cron trigger exists (`wrangler.jsonc` `triggers.crons`, e.g. `*/5 * * * *`)
   and call `runScheduledContentPublishing(env)` from `scheduled()`, `.catch()`-guarded
   (`index.ts:190-198`). It is bounded to **3 items × 8 publications per tick** — the next tick
   picks up the rest, keeping CPU well inside limits.
5. **Secrets (per platform, all optional — a platform simply stays "not connected" without them):**
   `INSTAGRAM_ACCESS_TOKEN`+`INSTAGRAM_BUSINESS_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN`+`FACEBOOK_PAGE_ID`,
   `X_USER_ACCESS_TOKEN`, `LINKEDIN_ACCESS_TOKEN`+`LINKEDIN_AUTHOR_URN`, `TIKTOK_ACCESS_TOKEN`;
   YouTube reuses the Google connection's `youtube.upload` scope. Optional `META_GRAPH_VERSION`,
   `LINKEDIN_API_VERSION`. `connectionStatus` (145-155) reports connected/not per platform to the UI.
6. **UI (optional).** Port `admin.js:2106-2525` or rebuild against the same endpoints; brand it with
   `white-label-branding`.
7. **AI captions (optional net-new wiring).** In the reference, captions are typed by the operator —
   there is NO brain call in `content-studio.ts`. To offer drafted captions, call
   `draftWithBrain(env, system, user)` from `pluggable-draft-brain` in a new `content/draft` handler
   and pre-fill the composer; still human-reviewed before scheduling.

## Gotchas (from the code)
- **The media proxy URL must be your real, publicly-reachable production origin.** `mediaUrl` (409)
  hardcodes `https://<brand-domain>/api/content/media/<token>` — Instagram/Facebook/TikTok/YouTube
  pull media by fetching that URL server-side. Localhost or a non-public URL = every media post
  fails. Change the hardcoded origin to the client's deployed domain (make it env-driven).
- **`public_token` must be exactly 64 hex chars.** `contentMedia` (392) enforces
  `/^[a-f0-9]{64}$/i`; `scheduleContentItem` (314) builds it from two dash-stripped UUIDs. If you
  swap the token generator, keep it 64 hex or the media route 404s everything.
- **Async platforms are stateful across cron ticks.** Instagram/TikTok/YouTube return a
  `ProcessingResult` → the row goes `processing` with a `provider_job_id`; the NEXT tick polls that
  job and only then flips to `published`. Never expect a one-shot publish for these three.
- **`blocked` ≠ `failed`.** A `BlockedError` (missing connection, missing consent, wrong media type)
  parks the row as `blocked` (retried hourly) and is NOT counted against the 5-attempt retry budget;
  a transient error retries with `attempts*300s` backoff up to 5, then `failed`. `updateItemOutcome`
  rolls these into the item's `published`/`partial`/`failed` state.
- **TikTok needs `explicit_consent=1`** on the item (`publishTikTok`, 501) AND verified media URLs —
  it will not auto-post without both. Keep the consent checkbox in the composer.
- **Editing after publish is refused.** `updateContentItem` only edits items still in
  `draft/scheduled/cancelled/failed` and preserves any already-`published` per-platform row when the
  platform set changes (363-383). Don't try to "unpublish" — posts are irreversible once live.
- **Ship with `enabled=0` for real clients.** The cron no-ops when disabled (727). Turn it on only
  after at least one platform is connected, or every due item churns into `blocked`.
- **Provider responses are byte-capped** (`boundedText`, 1 MB) and errors are surfaced verbatim from
  the platform (`providerError`) — surface them in the UI; they are the operator's debugging signal.
