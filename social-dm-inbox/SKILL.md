---
name: social-dm-inbox
description: >-
  Turn inbound social DMs (Instagram/Meta today; the same shape fits Facebook/TikTok/X) into governed CRM
  conversations: an HMAC-verified webhook lands each user-initiated message, bodies are encrypted at rest,
  a dependency-free intent classifier ranks buying signals and catches opt-outs, a 24-hour platform
  messaging window is tracked and enforced, a rate-limited template auto-reply handles first contact, an
  AI can DRAFT a reply but never sends it, and each thread rides an open→qualified→booked→closed pipeline.
  Use WHENEVER a client CRM serves a business that gets DMs — "add the Instagram inbox", "route DMs into
  the CRM", "auto-reply to new DMs", "reply to leads from Instagram", "qualify DM leads". The reusable
  core is WINDOW-GATING + reply-only + human-in-the-loop send: NO cold DMs, ever. It COMPLEMENTS
  crm-build-standard (the contact/deal spine it feeds), signed-webhook-intake (the verification layer it
  sits on — compose it, don't re-implement the HMAC), and outbound-compliance-gate (opt-out suppression).
  Do NOT use it to blast unsolicited DMs — the platform window and reply-only rule exist to make that
  impossible.
---
# social-dm-inbox — inbound DMs become governed CRM conversations

Cold DMing gets accounts banned and is against every platform's ToS. This skill does the legal, durable
thing instead: it receives DMs a person sent you, files them as CRM conversations, and lets you (or a
supervised auto-reply) respond only inside the platform's messaging window. The AI helps you draft; a
human always sends.

## What it is / when to use
An inbound-only DM lane for a business CRM. Reach for it when a build needs the shop's Instagram (or other
social) DMs to show up as rankable leads with history, not scattered in a phone app. It is opinionated:
reply-only, window-gated, opt-out-aware.

**Composes with:** **signed-webhook-intake** (the webhook's HMAC verification + GET handshake + idempotency
— reuse it), **crm-build-standard** (the conversation/lead is a first-class CRM record; graduate a
qualified thread into a contact + deal), **outbound-compliance-gate** (honor `stop`/opt-out across all
channels), and **crm-mcp-server** (expose `list_social_conversations` / `send_social_reply` to an operator
brain — read/write behind token scopes). The AI draft step uses a pluggable brain helper.

## Reference implementation (ronininc — read these)
- **Everything** — `worker/social-messaging.ts:1-346`. Key parts:
  - `handleMetaWebhook` (`:191-212`) — the signed intake (defer to signed-webhook-intake for the crypto).
  - `processMetaWebhook` (`:137-189`) — the ingest: classify → upsert conversation → `INSERT OR IGNORE`
    the message → maybe auto-reply.
  - `classifyIntent` (`:60-74`) — the dependency-free buying-signal / opt-out classifier.
  - `sendSocialReply` (`:81-126`) — the window-gated, opt-out-checked send via the Graph API.
  - `draftSocialReply` (`:274-305`) — AI drafts, never sends.
  - `personalizedReply` (`:76-79`) — template with `{{message}}`.
  - `connected` (`:24-26`) — the honest "is this actually wired?" gate.
- **Schema** — `migrations/0017_social_messaging.sql` (three tables + the seed channel row + the unique
  indexes that make ingest idempotent).
- **Router** — `worker/index.ts:80` (`/api/integrations/meta/webhook`, public, NOT under the admin gate).
- **Admin dispatch** — `worker/admin.ts:298-302` (`social`, `social/settings`, `social/send`,
  `social/draft`, `social/conversation`).
- **Inbox UI** — `public/admin/admin.js:1316-1370` (thread list, window pill, Draft-with-AI, Reply).

## How to reapply it
1. **Migration** — copy the three tables: `social_channels` (per-account config + `auto_reply_template`),
   `social_conversations` (one row per external user; carries `status`, `intent`, `intent_score`,
   `messaging_window_expires_at`, `UNIQUE(provider,channel_id,external_user_id)`), and `social_messages`
   (`direction`, encrypted `body`, `automated`, `UNIQUE(provider,external_message_id)` for idempotency).
   Seed one channel row in `status='setup'`.
2. **Webhook handler** — mount `POST/GET /api/integrations/<provider>/webhook` PUBLIC (a DM sender has no
   session). GET does the subscription handshake; POST verifies the HMAC, then `ctx.waitUntil(process(...))`
   and returns 200 immediately. All of this is the signed-webhook-intake atom.
3. **Ingest** (`process`): for each event — skip echoes/empty; `ensureChannel`; `classifyIntent(text)`;
   upsert the conversation (new → `open`, set the window to `ts + 86400`; existing → refresh window +
   intent, flip to `opted_out` if the classifier saw a stop word); `INSERT OR IGNORE` the message;
   auto-reply ONLY when `meta.changes` (a genuinely new message) AND auto-reply is on AND the classifier
   didn't see an opt-out AND no automated reply was sent in the last 6h.
4. **Send guardrails** (`sendSocialReply`): refuse if `status='opted_out'`, if the window is missing or
   `<= now()`, or if the account isn't connected. Insert the outbound row `status='sending'` first, call
   the platform API, then flip to `sent`/`failed`. Encrypt the body with your `encField` before it hits D1.
5. **AI draft** — build a short transcript (decrypt the last ~8 messages), pass it to your draft brain with
   a system prompt that bars inventing prices/timelines and pushes toward a booking; return the text for a
   human to edit and send. The brain has NO send path of its own.
6. **Admin routes + UI** — GET dashboard, POST settings (toggle + template), POST send, POST draft, PATCH
   status. UI shows a window-open pill and disables Reply/Draft when the window is closed or opted-out.
7. **Secrets** — the four provider credentials as Worker secrets; `connected()` returns false (and the UI
   says "setup required") until all are present, so nothing pretends to work.

## Gotchas (from the code)
- **The messaging window is a hard wall.** Platforms only allow a reply within ~24h of the user's last
  message. Track `messaging_window_expires_at` and refuse past it — a closed-window send is an API error
  and a policy violation, so the UI greys the button out too.
- **Auto-reply anti-storm.** A person firing three DMs in a row must not get three auto-replies: gate on
  "no automated outbound in the last 6h (21600s) for this conversation." Ship the auto-reply toggle so an
  operator can turn it off.
- **Idempotency is the unique index, not app logic.** `INSERT OR IGNORE` on `(provider,external_message_id)`
  + acting only on `meta.changes` is what makes webhook redelivery safe; don't `SELECT`-then-`INSERT`.
- **Encrypt message bodies at rest** (`encField`/`decField`, AES-GCM keyed by `ENCRYPTION_KEY`). With no
  key set locally they pass through in clear — fine for dev, set the secret in prod.
- **The classifier is intentionally dependency-free** (regex signal-counting), so it runs free on every
  webhook tick with no model call. Keep the LLM for the *draft*, not the triage.
- **Reply-only is the design, not a limitation.** There is deliberately no path to insert a cold-recipient
  conversation. Don't add one — window-gating only protects you if there's no back door around it.
- **`is_echo` events** (your own outbound reflected back) must be skipped in ingest or you double-log.
