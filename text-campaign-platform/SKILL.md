---
name: text-campaign-platform
description: >-
  A sovereign SMS/iMessage campaign platform on plain Cloudflare D1 — campaigns, a render
  queue, and a replies inbox — that sends through a PLUGGABLE EXTERNAL sender via a
  phone-sync heartbeat + claim-once queue-drain contract, sidestepping iOS's block on a web
  app texting directly. The sender (a local Mac Messages relay on your OWN number, or a Twilio
  bridge) polls /api/text/next and reports /api/text/sent; a heartbeat within the TTL means the
  active campaign tops up its queue, and when heartbeats stop, /next stops serving. Use WHENEVER
  a build needs to text its people with no third-party marketing SaaS: "SMS campaign", "text our
  leads/customers", "iMessage blast", "text marketing", "send texts from my own number", "drip
  texts", "why can't the website send texts on iPhone", or any "web app can't do X, hand it to a
  local companion" queue problem (printing, desktop automation). DEPENDS on
  outbound-compliance-gate (consent + shared DNC + STOP) and EXTENDS crm-build-standard (the
  lead store). Guardrails: consent + DNC + dedup gated at enqueue; every message carries "Reply
  STOP" and STOP auto-suppresses via the shared dnc table; claim-once so two poller passes never
  double-send; the sender surface is operator-only; the paid channel ships dark behind an
  activation flag. The send leg is external BY DESIGN — the Worker never texts.
---

# text-campaign-platform — sovereign SMS/iMessage on D1 + a pluggable external sender

## What it is / when to use
Own SMS/iMessage marketing with zero marketing-SaaS dependency. The Worker + D1 hold the
campaigns, a per-message render queue, and a replies inbox, and enforce consent/DNC/dedup. It
does NOT send — a small external **sender companion** (a Mac Messages relay texting from your
own number, or a Twilio bridge) drains the queue over a heartbeat-gated, claim-once HTTP
contract. This is the answer to "iOS won't let a web app send texts": the one piece that
actually texts lives outside the browser, and the platform hands it work only while it's synced.

The heartbeat + claim-once pattern generalizes to ANY "the web app can't do X, so a local
companion does it" problem (printing, desktop automation, native APIs) — the queue is generic;
only the sender changes.

## Reference implementation (Wavelygth — patterns only, no client data)
`worker/index.js` L1121–1253; migration `worker/migrations/0021_text_campaigns.sql`;
routes L3162–3195; proof `worker/lib/_proof/text-campaign.test.mjs`.

- **Constants** L1129–1130 — `TEXT_SYNC_TTL_MS = 120000` ("connected" if a heartbeat landed
  in the last 2 min), `TEXT_BATCH = 50` (enqueued / served per pass).
- **`textEnabled(env)`** L1132–1136 — activation gate (`env.TEXT_ENABLED='1'` OR a saved
  `text_enabled` setting); the paid channel ships dark.
- **`renderText(body, lead)`** L1137–1145 — fills `{{first_name}}`/`{{name}}`/`{{city}}`/
  `{{company}}` and **always appends "Reply STOP to opt out."** unless the body already
  contains "stop" (TCPA on every message).
- **`textConnected(env)`** L1146–1149 — reads `MAX(last_sync_at)` from `text_sync` and returns
  fresh-within-TTL. This is the heartbeat gate.
- **`textEnqueue(env, campaign)`** L1152–1166 — the compliance-gated enqueue: loads the shared
  `dnc` set + already-queued lead ids, walks recent leads, and skips any that are short-number,
  on DNC, already queued, or fail `leadConsented` (from `outbound-compliance-gate`); inserts up
  to `TEXT_BATCH` rendered `text_queue` rows.
- **`handleTextSync(req, env, me)`** L1206–1217 — the operator/companion heartbeat: upserts
  `text_sync` (per `device`), and if the channel is enabled, tops up the single `active`
  campaign's queue. "Sync begins the campaign."
- **`handleTextNext(env)`** L1220–1226 — the sender polls; empty with a `reason`
  (`not_enabled`/`disconnected`) unless enabled AND connected; serves `queued` rows and
  **claims each (`status='sending' WHERE id=? AND status='queued'`) so a second poll serves
  nothing** — the claim-once contract.
- **`handleTextSent(req, env)`** L1228–1234 — the sender reports outcome → `sent`/`failed`.
- **`handleTextInbound(req, env, url)`** L1237–1253 — PUBLIC, `?key=INBOUND_SECRET` gated:
  a STOP-family reply does `INSERT OR IGNORE INTO dnc … 'sms_stop'` + skips that number's
  queued/sending rows; any other reply is matched to a lead (suffix-tolerant phone match) and
  lands in `text_replies`.
- **Admin surface** L1168–1203 — `handleTextCampaignSave` (draft/active/paused),
  `handleTextCampaigns` (campaigns + queue counts + `connected`/`enabled` + unread replies),
  `handleTextResponses`/`handleTextResponseRead` (the inbox).
- **Route guarding** L3162–3169 — `/api/text/sync|next|sent` require `requireOperator`;
  campaign management + inbox (L3191–3195) require `requireAdmin`. The proof confirms an
  investor gets 403 on `/sync`.
- **Schema** `0021_text_campaigns.sql` — `text_campaigns`, `text_queue` (status
  queued→sending→sent/failed/skipped, indexed by status+campaign and by phone), `text_replies`,
  `text_sync` (device PK + last_sync_at). Plain tables, no rebuilds.

## How to reapply it
1. **Depend first.** Install `outbound-compliance-gate` — this platform reuses its `dnc` table,
   `normalizePhone`, and `leadConsented`. Do not fork a second suppression list.
2. **Schema.** Apply the four tables from `0021_text_campaigns.sql`. Store `phone` normalized.
3. **Enqueue.** Copy `textEnqueue`: skip short/DNC/already-queued/unconsented; render per lead
   with the STOP suffix; insert up to a batch. Keep it idempotent per (campaign, lead).
4. **The heartbeat + claim-once contract** (the reusable core):
   - `POST /api/text/sync` — companion upserts `text_sync`; if enabled, top up the active
     campaign. TTL-fresh sync == "connected".
   - `GET /api/text/next` — serve `queued` rows only when enabled AND connected; claim each to
     `sending` in the same pass so a re-poll can't double-serve.
   - `POST /api/text/sent` — companion reports `sent`/`failed` with an optional error.
   Guard all three to operators.
5. **Inbound.** A key-gated public `/api/inbound/text`: STOP → shared dnc + skip queue; else →
   `text_replies` matched to a lead.
6. **Sender companion (external, pluggable).** A tiny always-on client on the operator's Mac
   (or a Twilio bridge): heartbeat `/sync` on an interval well under the TTL, `GET /next`,
   deliver each via the local channel (Messages relay on your own number / Twilio), `POST
   /sent`. Authenticate it with a scoped bearer token, not a session cookie. Keep the Worker
   out of the send path entirely.
7. **UI.** Admin: compose campaign (draft/active/paused), a live "connected / enabled" chip
   from `handleTextCampaigns`, queue counts, and a Responses inbox with unread badges.

## Gotchas (from the code + comments)
- **The Worker never sends — that's the whole design.** iOS blocks a web app from texting, so
  the send leg MUST be an external companion. Don't try to send from the Worker; wire the
  claim-once queue and let the companion drain it.
- **Claim-once is load-bearing.** `/next` claims rows to `sending` in the same query it serves
  them (`WHERE id=? AND status='queued'`). Without it, two poll passes (or two devices)
  double-text. The proof asserts a second `/next` serves nothing.
- **Heartbeat gates the drain, both directions.** No fresh sync → `/next` returns
  `{messages:[], reason:'disconnected'}`; sync resumes it. Set the companion's heartbeat
  interval comfortably under `TEXT_SYNC_TTL_MS` (2 min) or the queue stalls between beats.
- **STOP suppresses via the SHARED dnc**, so a STOP text also stops future *calls* and the
  number's in-flight queued/sending rows are skipped immediately. Never keep an SMS-only
  suppression list.
- **Every message carries "Reply STOP."** `renderText` appends it unless already present —
  keep that; it's a TCPA requirement, not a nicety.
- **Inbound phone matching is suffix-tolerant** (`d === from || d.endsWith(from) ||
  from.endsWith(d)`) to survive `+1`/formatting differences — but everything is compared
  through `normalizePhone` first. A raw formatted number will miss the DNC set otherwise.
- **Operator-only sender surface.** `/sync|next|sent` are gated to operators and the campaign
  admin routes to admins; an investor/viewer seat must 403. Enforce it at the router, per the
  proof.
- **Only one `active` campaign drains at a time** (the enqueue picks the most-recently-updated
  active one). If you need concurrent campaigns, key the queue and heartbeat by campaign.
- **Ships dark.** `textEnabled` is an activation flag — a paid channel that a build enables per
  account; a disabled channel serves nothing rather than erroring.
