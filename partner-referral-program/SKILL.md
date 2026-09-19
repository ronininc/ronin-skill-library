---
name: partner-referral-program
description: >-
  A sovereign reseller / affiliate / referral program for a Cloudflare Worker + D1 CRM, where a
  REFERRAL becomes trackable currency: partners get a status-gated referral code + link; a public
  /r/:code hit logs a click, drops a 90-day HttpOnly first-party attribution cookie, and
  internal-allowlist-redirects (NO open redirect); the CRM's conversion handler (booking/lead)
  reads the cookie and credits the partner; a payout LEDGER records amounts while actual money
  movement stays a manual operator action; and external partner networks (PartnerStack / Impact /
  GoHighLevel) plug in as API tracks that report "connected" ONLY after a real authenticated 2xx
  probe. Use WHENEVER a build needs "referral tracking", "affiliate / reseller program", "give
  partners a referral link", "attribute a sale to whoever referred it", "partner payouts",
  "white-label reseller signups", or "50/50 partner attribution". No existing house skill covers
  affiliate/reseller attribution — this is the net-new piece. It COMPLEMENTS crm-build-standard (the
  contacts/deals it attributes against), cf-forms (the public partner-application form), and
  cf-abuse-guard (the honeypot/rate-limit on that form) — do NOT rebuild the CRM, form intake, or
  abuse guard here. Guardrails: no open redirect (internal paths only), unknown codes still redirect
  but attribute nothing (never leak which codes exist), API keys are Worker secrets never stored in
  D1, and payouts record intent — they never send money.
---

# Partner Referral Program

## What it is / when to use
The attribution + payout-ledger organ that makes referrals a measurable channel. Reach for it when
a CRM must know **who referred a customer** and pay them for it: reseller/white-label partners,
affiliates, plain word-of-mouth referrers. It ships the public click-tracking link, the first-party
attribution cookie, the conversion-credit hook, the partner roster + payout ledger, and honest API
bridges to external partner networks.

**Composes with:** `crm-build-standard` (contacts/deals — attribution links a partner to the
converting contact/deal); `cf-forms` (the public "apply to be a partner" form); `cf-abuse-guard`
(honeypot + rate-limit on that form). This skill is ONLY the partner/attribution/payout layer — it
consumes the CRM's existing conversion event, it does not own the pipeline.

## Reference implementation (ronininc CRM — OPEN before lifting)
Cloudflare Worker + D1. Start at `CRM_SKILLS_CATALOG.md`, then read:
- **`worker/partners.ts`**
  - `refCookie` L23-26 — the 90-day attribution cookie: `HttpOnly; Secure; SameSite=Lax`, Path `/`.
    Only the Worker ever reads it.
  - `handleReferralClick` L34-54 — public `GET /r/:code`: validate code shape; resolve to an
    `active` partner; on hit INSERT a `partner_referrals` row (status `clicked`) and set the cookie;
    ALWAYS 302 to the `?to=` destination — but only if `?to=` matches `^/[A-Za-z0-9/_-]*$`
    (internal paths only, no open redirect); reuse an existing valid visitor token.
  - `attributeReferral` L59-69 — the conversion hook: read the cookie, find the visitor's most
    recent `clicked` referral, advance it to `lead` and link the `contact_id`/`deal_id`. Safe to
    call on every conversion (no-op without a cookie).
  - `applyPartner` L72-93 — public application: `sameOrigin` + honeypot (`website_hp`) + email
    validation, upsert-by-email to status `pending`.
  - `createPartnerRecord` L122-142 — approve a partner → mint a `referral_code` + link (code is only
    minted once status becomes `active`); commission% defaults by kind (reseller 50 / else 25).
  - `partnerPayoutRequest` L158-189 — payout LEDGER: create (pending), then advance
    pending→approved→paid→void; marking `paid` closes out that partner's converted referrals. Money
    movement is NOT performed — this records intent only.
  - `programApiKey` L197-202 + `testPartnerProgram` L221-245 + `syncPartnerProgram` L247-279 — the
    external-network bridge: the API key is a Worker SECRET (never in D1); `connected=1` is written
    ONLY after a live authenticated call returns 2xx; sync refuses unless already connected.
- **`migrations/0031_partners.sql`** — `partners` (UNIQUE email, kind/status CHECKs, `referral_code`
  UNIQUE, `commission_pct`), `partner_referrals` (status CHECK clicked→lead→customer→paid→void,
  `visitor_token` index — NOTE the comment at L25-26: a `referrals` table already exists from an
  earlier migration, so this is deliberately named `partner_referrals`), `partner_payouts`,
  `partner_programs` (seed rows L71-74, `connected` flag defaults 0).
- **Wiring:** `worker/index.ts` L19 (import), L62 (public `POST /api/partner/apply`), L146-149
  (public `/r/:code` route, wrapped so a throw still 302s to `/`). `worker/booking.ts` L19 + L125-127
  — the conversion handler calls `attributeReferral(env, req, {contactId, dealId})` in a try/catch
  ("attribution is best-effort"). `worker/admin.ts` L381-386 — admin dispatch (dashboard, save
  partner, payout, program save/test/sync). `public/admin/admin.js` L152-206 — the panel
  (create/approve form, copy-link, record-payout prompt, external-program cards showing
  connected / key-set / needs-key state).
- **`wrangler.jsonc`** — `assets.run_worker_first` MUST include `"/r/*"` (and `/api/*`) so the Worker
  sees the referral link before the static asset service does.

## How to reapply it
1. **Migration.** Copy the four tables. Watch the naming collision — if the CRM already has a
   `referrals` table, keep this one `partner_referrals`. Seed `partner_programs` only for networks
   the client actually uses.
2. **Public routes.** Add `GET /r/:code` (→ `handleReferralClick`) and `POST /api/partner/apply`
   (→ `applyPartner`, behind `sameOrigin` + honeypot). Add `"/r/*"` to `run_worker_first` in the
   assets config or the link 404s from the static service.
3. **Conversion hook.** In the CRM's existing conversion handler (booking, order, signup), after the
   contact/deal is written, call `attributeReferral(env, req, {contactId, dealId})` inside a
   try/catch. That single line is what credits the partner — attribution is best-effort, never let
   it break the conversion.
4. **Admin.** Port the dispatch routes + panel: approve a partner (mints the code), copy the link,
   record a payout, and the external-program save/test/sync cards.
5. **External networks (optional).** Set each `<KIND>_API_KEY` as a Worker secret. `testPartnerProgram`
   flips `connected` only on a real 2xx; `syncPartnerProgram` imports partners only once connected.

## Gotchas
- **No open redirect.** `?to=` is regex-clamped to internal paths (`^/[A-Za-z0-9/_-]*$`). Never
  redirect to an attacker-supplied absolute URL — a referral endpoint is a classic open-redirect
  hole.
- **Unknown/inactive codes still 302, but attribute nothing** — this is intentional so the endpoint
  never reveals which codes exist. Don't "helpfully" 404 on a bad code.
- **The cookie is HttpOnly/Secure/SameSite=Lax and Worker-read-only** — attribution logic lives
  server-side; client JS must not be trusted to report the referrer.
- **API keys are Worker SECRETS, never stored in D1 and never echoed to the client.** The UI shows
  only "connected / key set / needs key", derived from whether the secret is present.
- **`connected=1` only after a real authenticated 2xx.** Do not assume a saved base URL means the
  network is reachable — the honest-probe pattern is the point (mirrors the connector-status model
  in opportunity-markets-bid-desk).
- **Payouts record intent, not money.** The ledger advances pending→approved→paid; the operator
  moves the actual funds out of band. Never wire an automatic transfer here (money-never-auto).
- **Best-effort attribution.** `attributeReferral` runs in a try/catch and no-ops without a cookie —
  a returning customer with no referral cookie simply isn't credited; that's correct.
