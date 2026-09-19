---
name: governed-email-outreach
description: >-
  A Mailchimp-lite email engine for any CRM/portal with governance baked in: an audience
  builder that de-dupes and excludes opt-outs, a preview-that-NEVER-sends → explicit
  confirm:true → send flow (with a test-to-me first), {{merge}} fields including per-recipient
  single-use invite links, a full per-recipient audit ledger, bounded concurrency, AND an
  optional cron ML-ranked daily drip under consent/DNC/opt-out/cooldown/cap — with inbound
  replies captured into a Responses inbox. Use WHENEVER a build needs to email its people at
  scale: "email blast", "send a campaign", "email all customers/investors/leads", "newsletter",
  "bulk email", "daily drip / automated outreach", "email the imported list", "campaign with an
  audit trail", "capture replies". EXTENDS crm-build-standard (the record store + optional ML
  ranking) and DEPENDS on email-provider-honest-degrade (the send leg) and
  outbound-compliance-gate (consent/DNC/opt-out/unsubscribe). Guardrails: preview never sends;
  a send requires confirm:true; every recipient is logged; honest-degrade when no provider is
  connected (records "skipped", never a fake send); a per-campaign recipient ceiling; the
  automated drip is a PAID add-on shipped dark behind an activation flag.
---

# governed-email-outreach — bulk + automated email with a preview→confirm→audit spine

## What it is / when to use
Two related engines over the same CRM records and the same governance:
1. **Bulk/manual campaign** — admin composes → previews the exact recipient list + a rendered
   sample (no send) → sends only on `confirm:true`, optionally test-to-me first. Every
   recipient row is logged.
2. **Automated daily drip** (paid, shipped dark) — a cron ranks the top-N consented leads
   (ML if present, static score otherwise) and emails them under a cooldown + daily cap;
   inbound replies land in a Responses inbox.

Use it for any "email our people" feature. It is resellable as a Mailchimp-lite for any
portal/CRM. Compliance (unsubscribe/DNC/consent/opt-out) is NOT re-implemented here — it comes
from `outbound-compliance-gate`; the actual send + honest-degrade comes from
`email-provider-honest-degrade`.

## Reference implementation (Wavelygth — patterns only, no client data)
All in `worker/index.js`; migrations under `worker/migrations/`.

- **Bulk campaign** L1703–1918:
  - `escHtml` L1713, `renderEmailBody` L1775–1794 (escaped body + text part + merge fields +
    CAN-SPAM footer) — shared with `email-provider-honest-degrade`.
  - `audienceRecipients(env, audience)` L1796–1813 — builds the list and **de-dupes by
    lowercased email across investors + leads**, then filters out everyone in `email_optout`
    (`clean()`). Audiences: `all_constituents`, `imported` (users with `source='import'`),
    default investors.
  - `handleEmailPreview` L1831–1844 — returns provider status, exact `count`, `over_limit`
    against `EMAIL_MAX_RECIPIENTS` (250), first 50 recipients, and a rendered `sample_html`.
    **Never sends.**
  - `handleEmailSend` L1847–1910 — rejects unless `confirm === true`; validates subject/body;
    a `test_to` sends only to the tester (and skips the audit campaign row); enforces the 250
    ceiling; mints a per-recipient single-use invite link when `{{invite_link}}` is in the body
    (via `createAuthToken` + `linkFor`); builds a per-recipient unsubscribe link; sends with
    **bounded concurrency** (`EMAIL_CONCURRENCY = 8`); records every recipient as
    `sent`/`failed`/`skipped`; honest-degrade note when no provider.
  - `handleEmailCampaigns` L1912–1918 — the past-campaign audit list.
- **Automated daily drip (paid, dark)** L1013–1094:
  - `outreachEnabled(env)` L1023–1027 — activation gate (Worker secret `OUTREACH_ENABLED=1`
    OR a saved `outreach_enabled` setting).
  - `runDailyCampaign(env, trigger, origin)` L1030–1067 — double-gated (`outreachEnabled` +
    `emailProvider`); pulls consented, non-DNC, non-opt-out, past-cooldown leads
    (`CAMPAIGN_COOLDOWN_DAYS = 3`); ranks by `mlScoreEntity` (falls back to static `score`);
    caps at `CAMPAIGN_DAILY_CAP = 100`; records a campaign + per-recipient rows; stamps
    `last_campaign_at`.
  - `handleOutreachStatus/Config/Run` L1069–1094 — the manual-trigger endpoint returns a
    **purchase-shaped 402** ("not activated on this account. Contact Ronin to enable it.")
    when the paywall is off — never a fake success.
  - Inbound reply capture `handleInboundEmail` L1107–1119 — a shared-secret webhook
    (`?key=INBOUND_SECRET`) matches the sender to a lead and stores a `campaign_replies` row;
    `handleListResponses`/`handleResponseRead` L1095–1104 drive the inbox.
- **Schema** — `0007_email.sql` (`email_campaigns` + `email_recipients` audit tables, `source`
  column on users), `0017_outreach.sql` (`campaign_replies` + `last_campaign_at`),
  `0013_email_optout.sql` (the suppression list, owned by `outbound-compliance-gate`).
- **Routes** — L3200–3204 (`/api/admin/outreach*`, `/api/admin/responses`) + the email
  send/preview/campaigns admin routes; inbound webhook is public + key-gated.
- **Proofs** — `worker/lib/_proof/outreach.test.mjs` (drip gate + ranking + cooldown),
  `mass-email.test.mjs` (preview-never-sends, confirm gate, opt-out excluded, audit rows).

## How to reapply it
1. **Depend first.** Install `outbound-compliance-gate` (dnc + `email_optout` + consent
   predicate + unsubscribe) and `email-provider-honest-degrade` (`emailConfig`/`sendOneEmail`/
   `renderEmailBody`). This skill assumes both exist.
2. **Schema.** Apply `email_campaigns` + `email_recipients` (per-recipient audit) and, for the
   drip, `campaign_replies` + a `last_campaign_at` column on your lead table. Add `source` to
   users if you want an `imported` audience.
3. **Audience builder.** Copy `audienceRecipients`: de-dupe by lowercased email, exclude
   `email_optout`, return `{user_id, name, email}`. Add your own audience keys as SQL branches.
4. **Preview endpoint.** Return provider status + exact count + over-limit flag + a rendered
   sample. It must NOT send.
5. **Send endpoint.** Require `confirm:true`; support `test_to` first; enforce a per-campaign
   ceiling; mint per-recipient invite links only when the body uses `{{invite_link}}`; build a
   per-recipient unsubscribe link; send with bounded concurrency; log every recipient with its
   outcome; return an honest note when no provider.
6. **Optional drip.** Gate behind an activation flag (see `feature-activation-gate` doctrine),
   rank with your CRM ML (or static score), respect cooldown + daily cap, and run it from
   `scheduled()`. Return a 402 (not a fake 200) when the manual trigger is hit while dark.
7. **Replies inbox.** A key-gated public webhook writes `campaign_replies`; surface unread
   count + a mark-read action.
8. **UI.** Compose form → Preview (shows count + sample) → "Send test to me" → Send (confirm
   dialog) → campaign history; a Responses tab.

## Gotchas (from the code + comments)
- **Preview must never send, send must require confirm.** These are two separate endpoints for
  a reason; the `confirm !== true` early-return is the guardrail an operator relies on. Keep
  them split.
- **De-dupe by lowercased email across every audience.** An investor who is also a lead must
  get ONE email; `audienceRecipients` merges by `email.toLowerCase()` — don't skip it or you
  double-send and inflate the audit.
- **Opt-out is excluded at build time, in every audience.** `clean()` runs on all branches,
  including `all_constituents`. A new audience you add must also filter `email_optout`.
- **Bounded concurrency, not a fan-out of 250 fetches.** Send in slices of ~8; a Worker will
  otherwise blow subrequest limits and rate-limit the provider.
- **Honest-degrade is a first-class outcome.** With no provider, still record the campaign and
  every recipient as `skipped`/`no_provider` and tell the operator nothing went out — never a
  fake "sent."
- **The drip is double-gated + capped + cooled-down.** `outreachEnabled` AND `emailProvider`
  AND cooldown AND daily cap — and stamps `last_campaign_at` so it can't re-hit the same person
  tomorrow. A miss on any gate is a clean `{skipped: …}`, not an error.
- **Merge fields are filled AFTER escaping the body**, so `{{name}}` can't be used to inject
  markup; invite/unsubscribe links are inserted as real anchors. Preserve that order.
- **Parameterize the brand + default subject/body.** The reference hard-codes them; pull them
  from settings (`campaign_subject`/`campaign_body`) and your own audience/lead table names.
- **The inbound webhook is shared-secret gated** (`?key=INBOUND_SECRET`) and rejects a bad key
  with 403 — never leave it open, it writes to your DB.
