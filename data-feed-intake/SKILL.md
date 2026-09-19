---
name: data-feed-intake
description: >-
  An admin "connect any source" intake for a Cloudflare Worker + D1 app: store a pasted,
  processor-AGNOSTIC adapter spec (a curl command, an API endpoint + key, a CLI invocation, a
  webhook URL, or raw JSON/YAML) VERBATIM as a registered feed, with a heuristic kind-classifier
  that badges it (api / cli / webhook / text) but NEVER executes anything at capture time — plus
  R2-less large-FILE ingestion as base64 chunks across D1 rows (the chunked-uploader storage half).
  Use WHENEVER a build needs "let me connect a data source", "paste in an API / curl / webhook",
  "register a feed", "hook up an external system", "a place to drop integration configs or big
  files", "adapter registry", or a source-agnostic ingest inbox that a future runner will process.
  Backend + a thin admin UI. EXTENDS commerce-spine (the per-site Worker + D1 node it lives in) and
  shares its file-upload/download/reap code with chunked-uploader. Guardrails: capture is INERT —
  the classifier only labels, it never runs the curl/CLI/webhook (executing a pasted command is a
  separate, gated, out-of-band concern); adapter text is size-capped (~200 KB) and stored as-is;
  the whole surface is admin-only; treat every stored adapter as untrusted operator input, never as
  a command to auto-run.
---
# data-feed-intake — "connect any source", stored inert

## What it is / when to use
A registry of data sources where the operator can paste whatever an integration needs — a curl
line, an endpoint + key, a CLI command, a webhook, or free JSON — and it is stored verbatim,
classified for display, and left for a future ingestion runner to read deliberately. Big files go
in the same table as chunked base64. Use it as the "inbox" for integrations on an admin console
when you want to accept sources of unknown shape without committing to a per-source connector yet.

## Reference implementation (Wavelygth — lift from here)
- **Backend** — `~/Projects/clients/wavelygth/worker/index.js` L2878-3053
  - Constants L2887-2890: `FEED_KINDS = ['file','api','cli','webhook','text']`,
    `FEED_NAME_MAX = 200`, `FEED_ADAPTER_MAX = 200000` (200 KB of pasted text),
    `FEED_CHUNK_B64_MAX = 900000`.
  - `classifyAdapter(text)` L2894-2902 — **heuristic label only**: `curl`/url+auth-header ⇒ `api`;
    `…/webhook|hook|callback` or the word webhook ⇒ `webhook`; bare `http(s)://…` ⇒ `api`;
    leading `npx|node|python|bash|sh|deno|bun|wrangler|psql|aws|gcloud|az` ⇒ `cli`; else `text`.
    Storage is verbatim either way — the badge never changes what is kept.
  - `handleFeedCreate(req, env, me)` L2905-2920 — validates non-empty + under the adapter cap,
    classifies when kind is unset/`file`, inserts a `feeds` row (`status='stored'`), audits.
  - `handleFeedUpload` L2928-2968 (the chunked-uploader server half — see that skill), plus
    `handleFeedList` L2971-2977 (metadata only, never bytes), `handleFeedGet` L2981-2986 (returns
    the stored adapter text for a direct feed; `null` for a file), `handleFeedDownload` L2994-3022
    (streams a file feed), `handleFeedDelete` L3025-3036 (batch chunks+row), `reapStaleFeeds`
    L3041-3053 (cron cleanup of abandoned uploads).
  - Routes L3250-3260; admin gate L3172.
- **Schema** — `~/Projects/clients/wavelygth/worker/migrations/0004_feeds.sql`: `feeds`
  (id, kind, name, **adapter** TEXT [direct feeds], content_type/size_bytes/chunk_count [file
  feeds], status, note, created_by, created_at, updated_at) + `feed_chunks`. Comment in the file:
  "Stored verbatim … We never execute it at capture time."
- **Admin UI** — `~/Projects/clients/wavelygth/portal/index.html`: feed list/render L1981-2010,
  the paste-an-adapter form `btnAddFeed` L2056+, and the dropzone/upload (chunked-uploader) above.

## How to reapply it
1. **Migration:** copy `0004_feeds.sql` (both tables). It is additive and pins to a single DB /
   shard-0 (admin-tenant, low volume — don't route it).
2. **Server:** copy `classifyAdapter` + `handleFeedCreate` for the "paste a spec" path, and the
   file upload/download/list/get/delete/reap set (shared with chunked-uploader) for the "drop a
   file" path. Gate the whole `/feeds` surface admin-only.
3. **UI:** a two-mode panel — a textarea + kind dropdown ("auto" ⇒ classify) that POSTs to
   `/feeds`, and a dropzone that runs the chunked uploader. List shows kind badge + size + a
   Download link only for `status='stored'` files.
4. **Later (out of scope here):** a deliberate, sandboxed, separately-gated *runner* reads a
   stored adapter and actually fetches/executes it. That is NOT part of intake and must never be
   wired to auto-run on capture.

## Gotchas (from the code + comments)
- **Capture is inert by design.** `classifyAdapter` only badges; nothing runs the pasted
  curl/CLI/webhook. This is the safety boundary — a pasted `curl … | bash` is DATA, not a command.
  If you ever add a runner, it is a separate, explicitly-gated, human-in-the-loop step.
- **Store adapters verbatim.** The classifier's guess must not rewrite or "normalize" what was
  pasted — the operator needs to read/copy it back exactly (`handleFeedGet` returns it as-is).
- **Cap the adapter text** (~200 KB); anything bigger is a file, not a config — route it to the
  chunked upload path instead.
- **List returns metadata only**, never the bytes/adapter in bulk — fetch the body per-id on demand.
- Everything the file-upload side needs (chunk recompute, stream-download, status='stored' gate,
  atomic delete, stale reap) is documented in `chunked-uploader` — this skill and that one share
  the `feeds`/`feed_chunks` tables.
- Treat a stored webhook/endpoint as untrusted input if you ever surface it — don't auto-follow
  redirects or echo secrets into logs.
