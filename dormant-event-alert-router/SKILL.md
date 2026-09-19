---
name: dormant-event-alert-router
description: >-
  The "leads don't die in the DB" internal-alert layer for a Cloudflare Worker + D1 build: an event-notification
  router whose recipients, provider, and subscribed-event list live in CONFIG (a settings row), so it is
  attach-and-activate with NO redeploy — and it is DORMANT-SAFE, meaning with no recipients configured it is a
  clean no-op that STILL writes a log row, so the wiring is provable before a single real address exists.
  Transports (email via resend/sendgrid/mailchannels, OR a webhook/Slack URL) are pluggable and each FAIL CLOSED
  without their secret; `notify()` NEVER throws into the request path; and every outcome (sent | no_recipients |
  disabled | event_off | failed:<why> | error) is recorded to a notifications_log you read to prove it. Use
  WHENEVER a build must alert the OPERATOR/STAFF when something happens — "notify me when a lead comes in / a
  form is submitted / a payment fails", "send a Slack/email alert on X", "don't let events go unnoticed", "wire
  alerts now, set the address later", "prove the notification pipeline before launch". It COMPLEMENTS
  email-provider-honest-degrade (the email SEND-leg — reuse its transports; this adds the event router,
  webhook/Slack channel, subscription filter, and provable-wiring log ON TOP) and governed-email-outreach
  (that emails your CONTACTS at scale; this is one-off INTERNAL alerts to your own team). Fires from the write
  path of lead-marketplace-auto-match and friends.
---
# Dormant Event-Alert Router (internal alerts, provable-wiring log)

## What it is / when to use / what it composes with
A small, safe fan-out for internal/operator alerts that can be fully WIRED at build time and ACTIVATED later
by config (no redeploy). Its distinctive value is that it is provable while dormant: every call logs an
outcome, so "is the alert pipeline connected?" is answered by reading a log, not by hoping. It also degrades
honestly — no fake sends — and never breaks the request it's reporting on.

- **Composes with**: `email-provider-honest-degrade` (the email transport leg — this reuses that honest-degrade
  behavior and adds the event router + webhook channel + subscription + log), `governed-email-outreach` (that's
  outbound-to-contacts at scale; this is internal one-off alerts), and any write path that should notify
  (`lead-marketplace-auto-match`, a payment-failure handler, an application form).

## Reference implementation (exact source)
- Whole module: `/Users/robbiebrown/Projects/case-plug/src/notify.js` (146 lines).
  - Config defaults (channel/provider/from/to/webhook_url/events) in a settings row, attach-and-activate:
    `DEFAULT_NOTIFY` `notify.js:15-23`; `getNotifyConfig`/`putNotifyConfig` (validated, capped): `:26-46`.
  - **`notify()` — never throws, logs every path** (disabled → event_off → no_recipients → send), returns `{ok,status}`:
    `notify.js:122-139`.
  - Pluggable transports, each fail-closed; `log` = dormant default that "succeeds without sending": `resolveTransport` `:74-116`.
  - Per-event internal-alert templates (staff need the callback number): `render` `:57-71`.
  - `recentNotifications` (read the proof): `:141-146`.
- Config + log routes (Bearer-gated): `src/index.js:317-334` (`GET/PUT /notifications/config`, `GET /notifications/log`).
- Schema: `notifications_log(event, status, channel, provider, detail)` + index `(event, created_at)`:
  `schema.sql:262-266`; config stored in the shared `settings(key,value)` table `schema.sql:204-207`.

## How to reapply
1. **Config, not code**: store `{enabled, channel:'email'|'webhook'|'none', provider, from, to:[], webhook_url,
   events:[...]}` in a `settings` row; expose a Bearer-gated `PUT /notifications/config` so a non-technical
   operator sets real addresses at close with no redeploy. Validate + cap the recipient list on write.
2. **Log table**: `notifications_log(event, status, channel, provider, detail, created_at)`. Write a row on
   EVERY outcome — including the no-ops.
3. **`notify(env, event, payload)`** order: disabled → `logNote('disabled')`; event not in subscribed list →
   `event_off`; no recipients → `no_recipients`; else render + send + log `sent`/`failed:<err>`. Wrap the whole
   thing in try/catch that logs `error:<msg>` — it must NEVER throw into the request that called it.
4. **Transports fail closed**: each provider returns `{ok:false,'<provider>_not_configured'}` without its
   secret; the default `log` provider returns `{ok:true, skipped:true}` so a brand-new deploy is provably wired
   with nothing to send. Reuse `email-provider-honest-degrade` for the email leg.
5. **Template per event** for internal readers (include the phone/state/type so staff can act immediately).

## Gotchas (from the code)
- **Logging must never break the request** — `logNote` itself is try/caught (`notify.js:48-55`), and `notify` is
  called best-effort from the write path; a broken alert can't fail an intake.
- **Dormant ≠ silent.** The point of logging `no_recipients`/`disabled` is that you can PROVE the pipeline is
  wired before any address exists. A build that only logs on success can't be verified pre-launch.
- **Never fake a send.** The `log` provider reports `skipped:true`, not a fake `sent` — honest-degrade all the way.
- **Channel switches the recipient source**: `webhook` uses `webhook_url`, `email` uses `to[]`; check the right
  one for emptiness or you'll "send" to nobody and report success.
- **Subscription list is a real gate** — an event not in `cfg.events` logs `event_off` and does nothing; adding a
  new alert type means adding it to both `render` and the default `events`.
