# Turnkey reproduction — cloning the full Ronin OS for a client

This is how `crm-build-standard` reproduces the **whole product** (not just a bespoke
mini-CRM) so it sells en masse: **clone the de-branded Ronin OS template, parameterize
it to the client, deploy, and let the client plug in keys.**

## Two reproduction modes — pick the right one

| Mode | When | How |
|---|---|---|
| **A · Bespoke-from-guts** | A client wants a *small, custom* CRM with their own record model | Compose `commerce-spine` + `cf-identity` + `cf-forms` + `cf-functions` from `references/starter-schema.sql` (the rest of this skill). Regenerates a minimal CRM. |
| **B · Clone-the-OS (turnkey)** | "use our website and CRM skills for &lt;client&gt;" — the full Ronin OS, sold as a plan | **This file.** Clone the maintained template; do NOT regenerate a 77-module OS from references. |

You cannot regenerate the Ronin OS (77 worker modules, 72+ migrations, a 359 KB admin
SPA, PWA, cron autopilot, 3 MCP servers) from a skill. Mode B **clones and parameterizes**.

## Canonical source of truth

- **Product/template:** `~/Projects/ronininc-site`. `main` **is what's deployed** (prod
  Worker `9d86b00c`); live work happens in `.claude/worktrees/*` and merges to `main` via
  PR. Deploy is **one shared Worker, last-write-wins, from consolidated `main` only.**
- **Migration head:** `0072_telephony` (main); `0073_tasks` in flight (PR #13). A fresh
  clone targets the current head. Migrations are **additive-only ("Mode A"), sequential,
  D1 FKs enforced local + remote.**
- **Template hygiene to fix before cloning en masse:** migration numbers **0033 and 0034
  are each used twice** (0033_clearances + 0033_deal_finder; 0034_deal_closer +
  0034_inbox_labeler) and **0064 is missing**. Duplicate prefixes make `wrangler d1
  migrations apply` ordering ambiguous — renumber to a clean sequence in the template.
- **The client-facing marketing site under `public/` is Ronin's own content** — a turnkey
  build does NOT ship it. It is regenerated per client by `website-build-standard` +
  `business-profile-recon` (step 2 of the chain). The template contributes the **`/admin`
  app, `/m` PWA, `worker/`, and `migrations/`** — the CRM, not Ronin's brochure pages.

## The turnkey chain (Mode B, full OS)

1. **Recon — `business-profile-recon`** (+ `site-media-fetch`, `spanish-regional-localization`):
   pull the client's REAL facts + media + brand palette/logo. Start from truth.
2. **Site — `website-build-standard`** (or a vertical): build the client's public site from
   those facts. **Emit a theme-token set** (palette, accent, logo) — this feeds step 4's reskin.
3. **Clone the OS template** — copy the CRM half of `ronininc-site` (`worker/`, `migrations/`,
   `public/admin/`, `public/m/`, `public/portal/`, `wrangler.jsonc`) into the client project.
4. **Parameterize (de-brand)** — run the checklist below so nothing says "Ronin".
5. **Deploy — `cf-deploy`** — create D1, apply migrations **remotely (scoped API token, see
   below)**, deploy, bind the custom domain. Operator-approved. Verify login is unchanged.
6. **Set the tier** — `POST /api/admin/instance/tier {tier:N}` (Good/Better/Best); above-tier
   apps lock into the upsell automatically. Keep `re_vertical` **OFF** (Ronin-only).
7. **Plug in keys** — the client adds their secrets; every feature is **inert until its
   secret exists**, so it comes alive key-by-key with no redeploy.

## De-brand parameterization checklist (every Ronin literal → a client variable)

**Config (`wrangler.jsonc`):** `name`, `account_id` (currently the operator's personal CF
account, hardcoded), D1 `database_name` + `database_id`, R2 `bucket_name`, `GOOGLE_REDIRECT_URI`,
`GOOGLE_OUTREACH_EMAIL`, `VAPID_PUBLIC` (regenerate a keypair per client), and every
`www.ronininc.org` URL → all become per-client values.

**Admin shell branding** (the seam exists — `instance_config.client_name` + `brand_color`,
applied by `applyInstanceBrand()` in `public/admin/admin.js` — but the shell doesn't fully
consume it yet):
- `public/admin/index.html` — the logo images (`/assets/ronin-logo*.png`) and literal
  "RONIN INC" text → drive from `instance_config` + a per-client logo in `public/assets/`.
- `public/admin/admin.js` — hardcoded copy strings ("Ronin CRM", proposal title, campaign
  default name/sender, wire beneficiary "Ronin Inc / Sovereign Systems") → read from config.
- `worker/plaid.ts` (`client_name:'Ronin Inc'`), `worker/partners.ts` (`ronininc.org/r/...`).

**Logo/favicon assets:** swap the PNGs in `public/assets/`.

**Verify de-brand:** `grep -ri "ronin" public/admin worker | grep -v node_modules` returns
nothing but variable *names* — no user-visible "Ronin" string survives.

## Theme-token layer — "the CRM matches their site" (the one NET-NEW piece)

Today branding = `brand_color` (one hex) + logo swap. To make a resold CRM actually *look*
like the client's site, extend the existing seam from one color to a **token set**.

**The mechanism already exists:** `admin.js` `applyInstanceBrand()` reads `instance_config`
and sets CSS custom properties (`--accent`/`--gold`/`--brand`) from `brand_color`; the admin
CSS is already fully driven by vars (`--accent`, `--accent-bright`, `--gold`, `--brand`,
`--surface`, `--bg1`, `--line`, `--text`). So the change is: carry the full set, not one color.

**The token contract** (`website-build-standard` emits this from the client's site palette;
it is stored as `instance_config.theme_tokens` JSON and applied verbatim as CSS vars):

```json
{
  "accent":       "#RRGGBB",   // primary brand color → --accent, --brand
  "accentBright": "#RRGGBB",   // lighter accent for links/emphasis → --accent-bright
  "gold":         "#RRGGBB",   // secondary/highlight → --gold
  "surface":      "#RRGGBB",   // card/panel background → --surface
  "bg1":          "#RRGGBB",   // app background → --bg1
  "line":         "#RRGGBB",   // borders/dividers → --line
  "text":         "#RRGGBB"    // primary text → --text
}
```

Every value is validated `^#[0-9a-fA-F]{3,8}$`; a missing/invalid token falls back to the
theme default (never a broken color). `brand_color` stays as the `accent` fallback for
back-compat. `website-build-standard` derives these from the client's real brand (logo/site
palette pulled in recon) so the CRM ships already wearing the client's colors — the operator
tunes them in **System → Setup & Connectors** with no redeploy.

**Implementation (in the `ronininc-site` template, coordinated via the CRM/OS chat):**
1. Migration (additive Mode A, next free number): `ALTER TABLE instance_config ADD COLUMN
   theme_tokens TEXT;`
2. `worker/app-store.ts`: extend `GET/POST /api/admin/instance/config` to carry + hex-validate
   `theme_tokens`.
3. `admin.js` `applyInstanceBrand()`: map each token to its CSS var; extend the Setup form
   (color inputs or a pasted-palette field).
4. Proof: `worker/lib/_proof/` round-trip (save tokens → read back → assert applied).

**STATUS: BUILT** — merged to `main` (PR #15, merge commit `b5717c7`): migration `0074`
(`instance_config.theme_tokens`), the extended config API, `applyInstanceBrand` applying the
token set, and the Setup paste-palette field; proven `theme-tokens.test.mjs` 8/8 + typecheck
clean. **Cloning `main` now gives a resold CRM this reskin.** (Remote D1 apply of `0074` is
pending the scoped `CLOUDFLARE_API_TOKEN`; until then the deployed CRM runs fine and the
palette GET degrades to null — only *saving* a palette 500s.)

## Plug-in-keys surface (inert-until-keyed — the turnkey enabler)

**Worker secrets** (`wrangler secret put`; each feature is a no-op until its secret exists):
`ENCRYPTION_KEY`, `ADMIN_SIGNUP_CODE`, `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI`,
`RESEND_API_KEY` *or* `SENDGRID_API_KEY`, `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET`,
`TWILIO_ACCOUNT_SID`+`TWILIO_AUTH_TOKEN` and/or `TELNYX_API_KEY`+`TELNYX_PUBLIC_KEY`,
`SHOPIFY_WEBHOOK_SECRET`, `CJ_API_KEY`, `VAPID_JWK`+`VAPID_PUBLIC`, `PLAID_*`,
`MAPILLARY_TOKEN`, `SAM_GOV_API_KEY`, `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` (drafting brain;
falls back to Workers AI), `GITHUB_TOKEN`.

**Bindings/config (`wrangler.jsonc`):** CF `account_id`, D1 `database_id`, R2 bucket, the
`AI` binding, the `LEAD_GENERATION` workflow, the `*/5 * * * *` cron.

**Runtime config (in-app, no redeploy — persisted in D1):** from-address, from-number,
white-label name/color, the agnostic email provider pick, custom-field definitions, CSV
import — all via the admin **System → Setup & Connectors** tab. This is the client's
self-serve onboarding surface; document it as "what you set in the app vs. what needs a key."

## Deploy runbook (`cf-deploy`) + the remote-D1 blocker

`wrangler d1 create <client-db>` → paste `database_id` into `wrangler.jsonc` → `wrangler d1
migrations apply <db> --remote` → `wrangler deploy` → bind the custom domain.

**Known blocker:** remote D1 migrations **fail under a `wrangler login` OAuth token (7403)** —
use a **scoped Cloudflare API token** (D1 edit + Workers scripts) via `CLOUDFLARE_API_TOKEN`
instead (see the `wrangler-oauth-token-cannot-query-d1-7403` memory). A one-command
fresh-client provision script (create → migrate → deploy → domain) is a **turnkey gap**; today
it's manual and token-gated.

## Tier gate (how the plan is enforced)

Data-driven and proven, not a promise: `app_store` (catalog of apps with `is_core` +
`min_tier`, `migrations/0035_app_store.sql`) × `instance_config.tier` (`0061_crm_tiers.sql`)
× `applyTier()` in `worker/app-store.ts`, proven by `worker/lib/_proof/tiers.test.mjs`.
Set the sold tier once; above-tier apps show "Upgrade to unlock". `re_vertical`
(`pipeline_settings`) gates the RE-wholesale vertical **OFF by default for resold instances**
(generic `planCore` runs) — it is Ronin-only, opt-in.

## App manifest — the 37 engines → tier (authoritative min_tier lives in `0035_app_store.sql`)

The full inventory + per-app source files is `~/Projects/ronininc-site/docs/CRM_SKILLS_CATALOG.md`
(37 net-new skills, each with its `worker/*.ts` + migration). Tier groupings:

- **Tier 1 · Good "Core CRM":** contacts/companies/deals/pipeline/activities, capture,
  cf-identity auth + clearances (RBAC), dialer + DNC, tasks, delivery/get-paid
  (`services-delivery-lifecycle`, `wire-payment-collect-reconcile`), the Daily Brief +
  `attack-list-priority-queue`, audit, notifications+push, CSV import/export, tiering.
- **Tier 2 · Better "CRM + Growth + AI":** `geo-directory-prospecting` + `open-data-signal-
  discovery` + `contact-enrichment-deliverability` + `decision-maker-email-extractor` +
  `website-need-scorer` + `github-lead-mining` + `rotating-leadgen-scheduler` (the lead
  engine), `sales-force-roster-distribution` + rep coaching, `content-studio-publisher` +
  `pluggable-publisher-backend` + `auto-blog-network`, `pipeline-autopilot` +
  `reply-intent-triage` + `self-schedule-booking`, `social-dm-inbox`,
  `governed-operator-console` (Solomon console), the intelligence layer
  (`references/intelligence/` scoring/forecast/assist), `pluggable-draft-brain`,
  `graduated-autonomy-tiers`, `dormant-reactivation`.
- **Tier 3 · Best "Full Ronin OS":** `crm-mcp-server` + `governance-diode` (Solomon/Kingmaker
  MCP + oversight), the Ops Map, `opportunity-markets-bid-desk`, the commerce/dropship
  engines (`order-pnl-fund-gate-fulfillment`, `capital-leak-breaker`, `mystery-box-balancer`,
  `digital-product-kit`, `shopify-order-bridge`, `installment-financing-intent`,
  `money-feed-health-monitor`), `partner-referral-program`, `ventures-portfolio-rollup`,
  semantic search (`references/intelligence/semantic*`), the governed power dialer
  (`references/power-dialer.md`), and the RE-wholesale vertical (Ronin-only, `re_vertical` opt-in).

Because the gate is `min_tier` in `app_store`, selling a plan = setting `instance_config.tier`;
the manifest above is the human-readable view of that data.

## Honest turnkey gaps (do NOT claim these until built)

1. ~~Theme-token reskin~~ — **BUILT + merged** (PR #15 / migration `0074`, commit `b5717c7`). Only remaining step: apply `0074` to remote D1 (scoped token) to activate palette *saving*.
2. **One-command fresh-client provision** — manual, and 7403-blocked on remote D1 (scoped
   token fix above).
3. **Connector seams ≠ wired workflows** — Stripe not wired to proposals/subscriptions; the
   agnostic `sendEmail` is only called by the test button; custom fields saved-but-not-shown
   (being fixed). A resold instance's "connected" ≠ "workflow complete" for these.
4. **Scoped-token / secret onboarding UX** — per-key `wrangler secret put`, no batch UX.
5. **Migration renumber** (dup 0033/0034, missing 0064) — fix in the template before mass cloning.
