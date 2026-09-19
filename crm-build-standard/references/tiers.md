# CRM tiers — good / better / best packaging

The house way to **sell** the CRM: one build, three price points. The whole Ronin OS
ships in every instance; a single `tier` value decides what's **unlocked**. Apps above
the instance's tier render as **locked** (greyed, un-installable, "Upgrade to unlock") —
that locked state *is* the upsell path, and upgrading a client is a one-field change, not
a rebuild.

This is the productization layer on top of `references/feature-catalog.md`: the catalog is
every feature à la carte; this file bundles them into **Good (Tier 1) / Better (Tier 2) /
Best (Tier 3)** so a client picks a plan, not a checklist. It is **free-first** end to end —
every tier fits the Cloudflare free plan (`references/free-tier-playbook.md`); a client
moves to Paid ($5/mo) only when a *named, real* limit forces it, never as a tier upsell.

## The three tiers

### Tier 1 — GOOD · "Core CRM"
Everything a service business needs to run leads → work → get paid. No ML, no outreach engine.
- **Core** (every CRM): D1 record brain (contacts/pipeline/deals/activities), append-only
  history, pipeline-stages-as-data, `tenant_id`/money-as-cents/AES-GCM, the `/api/*` API.
- **Auth & security**: login/signup/sessions/roles, lockout, invite/sign-up code.
- **Capture & import**: forms→DB, admin data-feed ingestion, webhook idempotency, real media.
- **Views/admin/reporting**: record search, profile popup + admin customization, report generator.
- **Delivery**: projects, retainers, payments, store — the get-paid spine.
- **Daily Brief cockpit** (the "just check it" pane) + Overview + Approvals — the always-on shell.

### Tier 2 — BETTER · "CRM + Growth + AI"
Everything in Good, plus the growth engine, the governed AI operator, and a team.
- **Lead engine**: Lead Finder (find + qualify + decision-makers), outreach + deliverability, reactivation win-backs.
- **Team**: Sales Team (recruit reps, distribute leads) + the **rep coaching tier of Solomon** (Workers-AI, whisper-in), scoreboard.
- **Partners / referrals**.
- **Studio**: content + auto-blog + 8am/8pm SEO cadence + social lines.
- **Automation & AI**: Autopilot (reply triage), the Solomon console, and the **Solomon Pipeline** — the autonomous planner that reads live state and proposes/runs the next actions (Kingmaker gates money & sends).
- **Intelligence** (governed): explainable **scoring** + **forecasting** (pure-JS, zero neurons) and **LLM assist** (Workers AI, free within the daily neuron budget; never auto-sends).

### Tier 3 — BEST · "Full Ronin OS"
Everything in Better, plus the full sovereign command surface and the multi-engine deal machine.
- **Ops Map**: live targets, districts, routes, street view — the full-OS command surface.
- **Ronin Wholesale**: the real-estate/other-vertical deal engine (find → score → match → draft → close), incl. the RE-wholesale planner vertical (`re_vertical`).
- **Ronin Flipper** + **Ronin Dropshipping** + **Opportunity Markets**.
- **Semantic** layer (embeddings-in-D1 + in-Worker cosine on free; Vectorize on Paid).
- **Power dialer** (governed, DNC/TCPA/consent-gated; needs a telephony account, not a CF cost).

> Moving a feature between tiers is a one-line change — see "How the gate works" below. The
> split above is the default; re-bundle per the operator's pricing.

## How the gate works (the proven runtime mechanism)

Built and proven in the Ronin OS codebase — reuse it, don't re-invent:

- **`app_store.min_tier`** (migration `0061_crm_tiers.sql`): every app in the App Store catalog
  (`0035_app_store.sql`) carries `min_tier` 1/2/3. Each app owns one or more nav tabs.
- **`instance_config`** (singleton, `0061`): the instance's `tier` (1/2/3, default 3 = Ronin's own
  full OS) + optional white-label `client_name` / `brand_color`.
- **`worker/app-store.ts`**:
  - `instanceTier(env)` — the current tier.
  - `appStoreDashboard` — tags each app `locked = min_tier > tier`, forces a locked app's `enabled`
    to 0, and adds its tabs to `hidden_tabs` so the sidebar hides above-tier features.
  - `toggleApp` — **refuses** installing an app whose `min_tier > tier` (403 "upgrade to unlock").
  - `applyTier(env, tier)` — sets `instance_config.tier`, installs everything `min_tier<=tier`,
    uninstalls everything above. This is the one call that provisions or upgrades a tier.
- **Admin routes**: `GET /api/admin/instance` (tier + brand, viewer-visible) and
  `POST /api/admin/instance/tier {tier}` (admin-only) → `applyTier`.
- **Client UI**: the App Store tab shows the tier badge, a Good/Better/Best switch, and locked
  cards with an "Upgrade" button (the upsell). Locked tabs disappear from the sidebar via the
  existing `applyAppVisibility` (it already hides `hidden_tabs`).
- **Proof**: `worker/lib/_proof/tiers.test.mjs` (13/13) — a tier-1 CRM can't install a tier-3 app;
  upgrading unlocks + installs it; downgrading re-locks + hides it.

## Provisioning a client at a tier (the one-command build)

Fold the tier into the full-client chain from `SKILL.md` — recon → site → CRM brain → deploy —
as one extra parameter. When the operator says **"build a Tier-2 CRM for [client]"**:

1. **Run the chain** exactly as in `SKILL.md` (business-profile-recon → website-build-standard →
   this CRM brain → cf-deploy). The CRM brain provisions the Ronin OS instance and applies migrations
   `0001…` through the current head (which includes `0061`).
2. **Set the sold tier** at provision time — the only tier-specific step. Either:
   - after the owner is seeded, call `POST /api/admin/instance/tier {tier: N}` as the owner, **or**
   - seed it directly before first boot:
     ```bash
     wrangler d1 execute <db> --remote --command \
       "INSERT INTO instance_config (id,tier,client_name) VALUES ('default',<N>,'<Client>')
        ON CONFLICT(id) DO UPDATE SET tier=<N>, client_name='<Client>';
        UPDATE app_store SET enabled=1 WHERE min_tier<=<N>;
        UPDATE app_store SET enabled=0 WHERE min_tier>&lt;N&gt;;"
     ```
     (this is exactly what `applyTier` does — use the endpoint when the Worker is live, the SQL when
     seeding before first boot.)
3. **Verify** (no fake PASS): `GET /api/admin/instance` returns the sold tier; `GET /api/admin/app-store`
   shows above-tier apps `locked`; a live login round-trips; and — bracket every deploy — the user
   count is unchanged and `auth.js`/`SESSION_SECRET` untouched (see `SKILL.md` step 4).

Default a **new build to the sold tier**; default the **operator's own instance to Tier 3**. Upgrades
later are a single `POST /api/admin/instance/tier` — no redeploy, no data migration.

## Guardrails carried into tiering

- The tier gates **visibility + install**, never data safety. Auth, `tenant_id`, AES-at-rest, and the
  governance rules (LLM assist never auto-sends; money/sends stay human-confirmed) apply at **every**
  tier, including Tier 1.
- Regulated-finance instances stay **non-advisory** at every tier (no predictions/advice) — tiering
  never unlocks past a hard guardrail.
- Free-first holds across tiers: a higher tier turns on more *features*, not a bigger *bill* — Paid is
  triggered only by a real limit (Vectorize, or a named free-tier ceiling), never by the tier itself.
