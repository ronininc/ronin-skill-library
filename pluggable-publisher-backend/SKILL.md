---
name: pluggable-publisher-backend
description: >-
  The swap-the-delivery-backend pattern for a social publisher: a `publisher_mode` switch
  (native | openpost) that lets the CRM keep OWNING the schedule, queue and per-platform ledger while
  DELEGATING actual delivery to a self-hosted OpenPost instance (getopenpost/openpost) that holds the
  platform OAuth connections. Use WHENEVER content-studio-publisher exists and you want to "route
  publishing through OpenPost", "use a self-hosted publisher backend", "not hold the platform tokens
  in the CRM", "swap the delivery layer", or need the honest-degrade behavior of "if a platform isn't
  mapped, mark it blocked with a reason instead of silently dropping it". This is a NET-NEW DELTA on
  top of content-studio-publisher — it does NOT re-implement the scheduler, queue, media proxy or
  ledger (that skill owns those); it adds only the mode toggle, the bounded OpenPost REST client, the
  channel-map (our platform → OpenPost account id), the item-level create→schedule→poll state machine
  that folds OpenPost renditions back onto the SAME ledger, and a poll-cap that fails stuck deliveries.
  COMPLEMENTS content-studio-publisher (required base) and scoped-bearer-token (the OpenPost API token
  is a Worker secret, same never-in-D1 discipline). Also a reusable TEMPLATE for any "native or
  delegate to an external service" seam. Guardrails: the backend token is a Worker secret, never
  stored in D1 and never echoed; media is handed to the backend as the CRM's OWN opaque public URL so
  no platform credential ever leaves; an unmapped platform is BLOCKED (honest) never dropped (silent).
---
# Pluggable Publisher Backend — native, or delegate to a self-hosted OpenPost

This is the delivery-backend seam of a social publisher. The CRM stays the orchestrator + ledger; a
`publisher_mode` column decides whether each due item is delivered by the **native** per-platform
publishers (see `content-studio-publisher`) or handed to a **self-hosted OpenPost** instance that
holds the platform OAuth connections and publishes on your behalf. Either way the outcome lands on
the same `content_publications` rows, so the UI, retries and roll-up are identical.

**When to use:** the client (or you) would rather keep platform tokens in one self-hosted publisher
than as CRM Worker secrets, or wants OpenPost's connection UX — while the CRM keeps the calendar and
the record of truth. **What it composes with:** `content-studio-publisher` (the base engine and
ledger this extends) and `scoped-bearer-token` (token discipline). The pattern generalizes to any
"do it natively OR delegate to an external service, and reconcile the result onto our own ledger" seam.

## Reference implementation (ronininc-site — OPEN these)
- **`worker/openpost.ts:1-253`** — the bounded REST client (owns NO DB writes):
  `openpostOrigin` (55-61 — normalize to a clean HTTPS origin, Worker appends `/api/v1`),
  `openpostConfigured` (63-68 — mode+origin+workspace+token all present), `parseChannelMap` (71-81),
  `boundedJson`/`messageFrom`/`opFetch` (83-134 — 1 MB cap, bearer auth, honest error text),
  `openpostListAccounts` (137-153), `openpostCreatePublication` (165-186),
  `openpostSchedule` (188-200 — optimistic concurrency via `expected_revision`),
  `openpostGetPublication` (202-212), `providerFromPlatform` (216-221),
  `deliveryToStatus` (226-231 — classify by MEANING not exact enum), `normalizeRenditions` (233-252).
- **`worker/content-studio.ts:206-249`** — the mode switch + connection setup: `saveOpenpostSettings`
  (209-237 — validates the channel map, refuses openpost mode without URL+workspace+token+≥1 mapping)
  and `openpostAccounts` (241-249 — read-only proxy to list connectable accounts).
- **`worker/content-studio.ts:601-723`** — the delegation state machine: `OPENPOST_POLL_CAP` (607),
  `applyRenditions` (611-623 — only terminal transitions), `bumpProcessing` (627-637 — age one poll,
  fail at the cap), `requeueOrFail` (641-651 — transient create failure backs off, ≤5 attempts),
  `blockProviders` (653-659), `publishItemViaOpenpost` (661-723 — the create→schedule→poll flow).
- **`worker/content-studio.ts:728,734-738`** — `runScheduledContentPublishing` chooses the branch via
  `openpostConfigured(env, settings)`; the OpenPost branch calls `publishItemViaOpenpost` then
  `updateItemOutcome`, reusing the same roll-up as native.
- **`migrations/0029_openpost_publisher.sql`** — the columns this adds to the base tables:
  `content_settings.publisher_mode` (CHECK native|openpost), `openpost_base_url`,
  `openpost_workspace_id`, `openpost_content_profile`, `openpost_channel_map` (JSON),
  and `content_items.openpost_publication_id` + `content_publications.provider_url`.
- **`public/admin/admin.js`** — the publisher-mode toggle + channel-map editor in the Content section.

## How to reapply it (delta on top of content-studio-publisher)
1. **Prereq.** `content-studio-publisher` must already be installed — this reuses its
   `content_settings` / `content_items` / `content_publications` tables and its cron.
2. **Migration.** Apply `0029_openpost_publisher.sql` (renumber). It only ADDs columns; the base
   tables are untouched.
3. **Client module.** Add `worker/openpost.ts` verbatim — it is self-contained and DB-free. Import
   its exports into `content-studio.ts`.
4. **Mode + delegation in content-studio.ts.** Add `saveOpenpostSettings` / `openpostAccounts`
   (206-249) and the whole OpenPost delegation block (601-723), then make
   `runScheduledContentPublishing` branch on `openpostConfigured` (728). No other change to the
   native path.
5. **Routes.** Add gated `content/publisher` (POST → `saveOpenpostSettings`) and
   `content/openpost/accounts` (GET → `openpostAccounts`) beside the existing content routes.
6. **Secret.** Set `OPENPOST_API_TOKEN` as a Worker secret (never a settings column). The dashboard
   only ever reports `token_configured: Boolean(env.OPENPOST_API_TOKEN)` — never the value.
7. **Operator flow.** Save the instance URL + workspace id → GET accounts → map each of your
   platforms to an OpenPost `social_account_id` → set an OpenPost `content_profile` → flip mode to
   `openpost`. Now the cron delegates.
8. **Generalize the pattern.** For any other "native or delegate" seam: a `*_mode` enum column, a
   `*Configured(env,settings)` gate, one bounded REST client that owns no DB, and a branch in the
   worker loop that folds the external result onto your existing ledger with a poll-cap.

## Gotchas (from the code)
- **One OpenPost publication carries ALL platforms** — unlike native (one API call per provider).
  So the OpenPost path is an ITEM-level create→schedule→poll machine: create once (store
  `openpost_publication_id` so retries poll instead of re-creating), schedule, then each cron tick
  polls and folds renditions back per-provider.
- **Unmapped platforms are BLOCKED with a reason, never silently dropped** (`publishItemViaOpenpost`
  672-674). This is the honest-degrade contract — keep it; do not "helpfully" skip them.
- **Optimistic concurrency on schedule.** `openpostSchedule` sends `expected_revision`; on a 409/422
  the code re-reads the current revision and retries the schedule ONCE (717-721). OpenPost bumps the
  revision on create, so a stale revision is expected — this retry is load-bearing.
- **`deliveryToStatus` classifies by meaning, not an exact enum** (226-231), because OpenPost's
  `delivery.state` values are instance/version dependent. Unknown/pending states stay `processing`
  so the poller keeps checking rather than declaring a false outcome — don't tighten it to `===`.
- **Poll cap prevents a stuck item hanging forever.** `bumpProcessing` ages each `processing` row and
  fails it at `OPENPOST_POLL_CAP` (30 polls ≈ 2.5h at 5-min cron). Keep this or a silently-stuck
  delivery leaves the item `publishing` indefinitely.
- **Transient create/reach failure re-queues, doesn't blow up.** `requeueOrFail` backs off and, because
  `openpost_publication_id` stays null, the CREATE re-runs next tick — idempotent by construction.
- **Media never exposes a credential.** OpenPost is handed the CRM's own opaque public media URL
  (the `content-studio-publisher` proxy), so no storage/OAuth secret leaves the Worker. Keep it that
  way — do not hand OpenPost a Drive file id or a signed storage URL.
- **`openpostOrigin` only accepts HTTPS** and strips any path — the client appends `/api/v1` itself.
  A base URL with a path or `http:` normalizes to `''` and the client refuses to call.
