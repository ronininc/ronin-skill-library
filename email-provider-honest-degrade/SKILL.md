---
name: email-provider-honest-degrade
description: >-
  A pluggable, Resend-compatible transactional-email layer for a Cloudflare Worker that a
  NON-TECHNICAL operator can connect with no terminal, and that DEGRADES HONESTLY when no
  provider is set — it returns null, every caller records "skipped / no_provider", and NOTHING
  ever fakes a send. Use WHENEVER a Worker/D1 build needs to send email — invite links, password
  resets, receipts, notifications, or campaigns — and you want to own the send path with no SDK:
  "send an email", "email the invite/reset link", "connect email", "let the client hook up their
  own email", "email provider", "why did no email go out". Config resolves from Worker SECRETS
  first, then a portal-saved setting (app_settings), else no provider. Guardrails: no key ⇒ no
  provider ⇒ honest skip (never a silent fake success); every body is HTML+text with escaped
  merge fields. Pairs with cf-identity (invite/reset emails) and is the send leg beneath
  governed-email-outreach. The compliance footer/unsubscribe lives in outbound-compliance-gate.
---

# email-provider-honest-degrade — pluggable email, or an honest "not connected"

## What it is / when to use
One tiny module that turns "does this build have email?" into a truthful answer. It resolves a
provider config from Worker secrets OR a portal-saved setting, exposes `sendOneEmail(env, msg)`,
and — critically — when no provider is configured it returns `{ ok:false, reason:'no_provider' }`
so every caller can record a real "skipped" outcome instead of pretending. Use it as the send
leg under any Worker that emails. It is provider-shaped like Resend (`{from,to,subject,html,
text}` POST) but works with any Resend-compatible endpoint.

## Reference implementation (Wavelygth — patterns only, no client data)
All in `worker/index.js`:

- **`escHtml(s)`** L1713–1715 — escapes `& < > " '`; merge values pass through it so a body can
  never inject markup.
- **`emailConfig(env)`** L1719–1723 — the resolution order: **(1)** `env.EMAIL_API_KEY +
  env.EMAIL_FROM` (secrets — most secure, `source:'secret'`); **(2)** a config the operator
  saved in the portal → `app_settings` (`email_api_key`/`email_from`, `source:'saved'`, so email
  connects with no terminal); **(3)** neither ⇒ `null`. `EMAIL_API_URL` defaults to
  `https://api.resend.com/emails`.
- **`emailProvider(env)`** L1725 — returns `'rest'` or `null`; the one-liner every caller checks
  first.
- **`sendOneEmail(env, msg)`** L1726–1738 — resolves config; if none, returns
  `{ok:false, reason:'no_provider'}`; else POSTs `{from,to:[to],subject,html,text}` with a
  `Bearer` header; maps a non-2xx to `{ok:false, reason:'http_<status>'}` and a throw to a
  truncated `reason`. Never throws to the caller.
- **`sendInviteEmail` / `sendResetEmail`** L1743–1771 — honest-degrade wrappers: if
  `!emailProvider(env)` they return `{sent:false, reason:'no_provider'}` and send nothing. The
  invite caller then still returns the link so an admin can deliver it by hand; the reset link is
  delivered ONLY by email (never handed back to an unauthenticated caller) — that asymmetry is
  the security detail.
- **`renderEmailBody(body, r, inviteLink, unsubLink)`** L1775–1794 — admin-written plain text →
  escaped HTML (`\n`→`<br>`) + a parallel text part; fills `{{name}}`, `{{email}}`,
  `{{invite_link}}`, `{{unsubscribe_link}}`; appends the CAN-SPAM footer when an unsub link is
  passed. (The footer/unsubscribe policy itself belongs to `outbound-compliance-gate`.)
- **Saved-config write path** — the operator's "connect email" form writes `email_api_key`/
  `email_from`/`email_api_url` into `app_settings` via the standard `INSERT … ON CONFLICT DO
  UPDATE` upsert (see the outreach/settings handlers).

No dedicated migration — it reuses the `app_settings (key, value, updated_at)` KV table.

## How to reapply it
1. **Secrets:** `wrangler secret put EMAIL_API_KEY` and `EMAIL_FROM` (a verified sender). For a
   different Resend-compatible provider, also set `EMAIL_API_URL`.
2. **Or portal-connect:** give the operator a form that upserts `email_api_key` + `email_from`
   (+ optional `email_api_url`) into `app_settings`. Now email connects with no terminal.
3. **Lift** `escHtml`, `emailConfig`, `emailProvider`, `sendOneEmail`, `renderEmailBody`
   verbatim. Swap the brand string in the invite/reset templates.
4. **Every caller checks provider first** and records the real outcome: `sent` / `failed
   (http_NNN)` / `skipped (no_provider)`. Surface a "No email provider is connected, so nothing
   was delivered" note in any response where a send was expected.
5. **Show status on the ops console:** an "email connected / off" chip driven by
   `!!(await emailProvider(env))`.

## Gotchas (from the code + comments)
- **No key ⇒ no provider ⇒ honest skip.** The whole point: never return a success shape when
  nothing was sent. `runDailyCampaign` and `handleEmailSend` both branch on `provider` and write
  `status='skipped'`/`'no_provider'` — copy that discipline.
- **Secrets beat saved settings.** If both exist, the secret wins (`source:'secret'`), so a
  deploy-time key can't be silently overridden by a stale portal value.
- **`from` must be a verified sender** at the provider or the POST 4xx's — you'll see
  `http_403`/`http_422`, not `no_provider`. Distinguish "not connected" from "connected but
  rejected" in your UI; they're different fixes.
- **Reset links are email-only.** Never hand a password-reset token back to an unauthenticated
  caller as a fallback the way invite links are — that would be an account-takeover vector.
- **Bodies are escaped, then merged.** `renderEmailBody` escapes the whole body first, so admins
  can't (accidentally or otherwise) inject HTML; keep that order if you extend it.
- **Truncate error reasons** (the code caps at ~120 chars) before storing — provider errors can
  be huge and you don't want them bloating the recipients log.
