---
name: crm-build-standard
description: >-
  The house standard for building a CUSTOMIZABLE CRM for any client or business — all the guts
  ready, assembled from proven building blocks, then tailored to the client's actual pipeline.
  Use this WHENEVER the deliverable is a CRM or the system behind one: "build a CRM", "give them
  a CRM", "a CRM for [client]", "customer/contact/lead management system", "intake + pipeline +
  follow-up", "track leads/customers/deals", "members area with records", "add a CRM brain to the
  site", or productizing lead-gen / customer records as a per-client node. Sells as good/better/best
  TIERS — "a tier-1 / tier-2 / tier-3 CRM", "good better best CRM package", "tiered CRM",
  "core / growth / full-OS plan" — one build, three price points gated by a single instance
  tier (references/tiers.md). ALSO the orchestrator for
  a FULL client build — trigger on "build the whole thing for [client]", "use our CRM + website +
  Owner.com skills and build this for [client]", or "stand up a full site + CRM for [client] from
  their real data" — running the three-skill chain: business-profile-recon (the "Owner.com skill":
  pull the client's REAL verified data from Owner.com / Google Business Profile / socials) →
  website-build-standard (the site) → this CRM brain → cf-deploy, verifying login is never disturbed.
  It is an ORCHESTRATOR: it composes the existing guts skills rather than re-inventing them —
  business-profile-recon (Owner.com/profile data), website-build-standard (the site), commerce-spine
  (the sovereign D1 data + CRM + commerce brain, with the 10 GB shard-overflow and R2 offload),
  cf-identity (real login/signup/sessions/roles), cf-forms (lead/contact/booking capture into the
  DB), cf-functions (the serverless API), and cf-deploy (preview + go live) — and adds the optional
  intelligence layer
  (references/intelligence: sovereign explainable scoring, forecasting, semantic search, governed LLM
  assist) and an optional governed power-dialer (references/power-dialer.md). For a lead-driven
  service firm that wants to own the CRM in their OWN Notion workspace instead of a Cloudflare node,
  route to notion-intake-crm-cloner. Do NOT use this for a pure brochure site with no records
  (website-build-standard alone), for POS terminal / card-present work, or for non-CRM software.
  Respects the hard guardrails: non-advisory only for regulated-finance CRMs, and no ML over minors'
  content without a safeguarding review.
---

# CRM Build Standard

The house standard for standing up a **customizable CRM** — the full guts ready to assemble, then
tailored to the one thing that actually differs between clients: **their pipeline and their records.**
Everything below the record model is reused, proven, and governed; the record model is where you
customize.

This skill is an **orchestrator**. It does not re-implement auth, a database, form capture, an API,
or deploy — those already exist as focused skills. It wires them into one coherent CRM and adds the
two layers that make a CRM more than a table: **intelligence** and **outreach**, both governed.

## The thesis in one line

**The DB is the source of truth; auth, capture, API, intelligence, and outreach are swappable layers
around it.** Customizing a CRM = changing the record model + pipeline, not rebuilding the plumbing.

## Tiered packaging — good / better / best (how you SELL it)

One build, three price points. The whole OS ships in every instance; a single **tier** (1/2/3)
decides what's unlocked, and apps above the tier show as locked ("Upgrade to unlock") — the upsell
is built in. This is how a client picks a **plan**, not a checklist.

- **Tier 1 · Good — "Core CRM":** records + pipeline + capture + auth + delivery (get paid) + the Daily Brief cockpit.
- **Tier 2 · Better — "CRM + Growth + AI":** + lead engine, sales team + rep coaching, Studio content, Autopilot, the Solomon console + autonomous **Solomon Pipeline**, and governed intelligence (scoring/forecast/assist).
- **Tier 3 · Best — "Full Ronin OS":** + the Ops Map, Ronin Wholesale/Flipper/Dropshipping, Opportunity Markets, semantic search, and the governed power dialer.

The gate is a **proven runtime mechanism**, not a promise: `app_store.min_tier` + `instance_config.tier`
+ `applyTier()` in `worker/app-store.ts`, enforced on install and in the sidebar, proven by
`worker/lib/_proof/tiers.test.mjs` (13/13). Provisioning a client at a tier is one extra step in the
build chain (set the sold tier via `POST /api/admin/instance/tier`); upgrading later is one call, no
redeploy. **The operator's own instance runs Tier 3.** Full matrix, the gate internals, and the
one-command tiered provision: **`references/tiers.md`**.

## Who you are when you run this

A **senior CRM builder with decades on Cloudflare's free tier** — you've shipped enough of these to
have opinions. You build **free-first**: every default fits inside the free plan, and you move a
client to Paid ($5/mo) only when a *named, real* limit forces it — never as an upsell. You know the
free ceilings cold (Workers 100k req/day; D1 500 MB/db, 5 GB/account, **5M rows read/day — enforced**,
100k written/day; R2 10 GB + zero egress; Workers AI 10k neurons/day; **Vectorize is Paid-only**) and
you design around them reflexively: index every filter, blobs to R2, shard across free 500 MB DBs,
semantic via embeddings-in-D1 + in-Worker cosine (not Vectorize) until Paid, assist cached and
on-demand within the neuron budget, scoring/forecasting leaned on because they cost zero neurons. You
compose the proven guts, you never re-plumb, you prove before you claim, and you degrade honestly
when a free limit is hit (never a fake success). The full discipline is `references/free-tier-playbook.md`;
the complete, de-conflicted feature set is `references/feature-catalog.md`.

## Full client build — the one-liner that composes it all

When the operator says **"use our CRM + website + Owner.com skills and build this for
[client]"** (or just "build the whole thing for [client]"), this skill is the orchestrator
that runs the three-skill chain end to end, in order, from the client's REAL data:

> **Reproduction model — clone the OS, don't regenerate it.** The sellable product is the
> full **Ronin OS** (77 worker modules, 72+ migrations, the admin SPA, the `/m` PWA, cron
> autopilot, MCP servers) — it is reproduced by **cloning the maintained template
> (`~/Projects/ronininc-site`, whose `main` IS what's deployed) and parameterizing it per
> client**, NOT by regenerating from references. The complete turnkey runbook — the de-brand
> checklist (every "Ronin" literal → a client variable), the theme-token reskin that makes
> the CRM match the client's site, the plug-in-keys/secrets surface (inert-until-keyed), the
> deploy path + the remote-D1 `7403` scoped-token fix, the tier gate, and the **37-app
> manifest → tier** — is **`references/turnkey-reproduction.md`**. Regenerating from
> `references/starter-schema.sql` (below) is the *bespoke-mini-CRM* mode, not the OS. Known
> turnkey gaps (theme-token layer, one-command provision, seam-vs-workflow connectors) are
> tracked honestly in that runbook — do not claim them until built.

1. **Owner.com / profile recon — `anthropic-skills:business-profile-recon`.** Reach the
   client's live profiles FIRST — Owner.com, Google Business Profile, Yelp, Instagram/
   TikTok/Facebook, Apple Maps, delivery/ordering platforms — and pull VERIFIED facts
   (hours, address, phone, menu/catalog, prices, brand, photos, socials). Never invent or
   placeholder a real business's facts. Pair with `anthropic-skills:site-media-fetch` to
   harvest their real photos/video, and `anthropic-skills:spanish-regional-localization`
   for bilingual copy. This is the "Owner.com skill" step — it makes the build start from
   truth, exactly like Pineapple started from real Clover catalog data.
2. **The site — `anthropic-skills:website-build-standard`.** Build the client-facing site
   from those verified facts + real media (immersive centerpiece, cinematic hero, SVG
   logo, payment-ready shop, inquiry routing — the house defaults). For a sports team use
   `sports-website-standard`; for a restaurant/service business its vertical variant.
3. **The CRM brain — THIS skill.** For the **full OS (turnkey product): CLONE the template**
   (`references/turnkey-reproduction.md`) — copy `worker/` + `migrations/` + `public/admin/`
   + `/m` + `wrangler.jsonc` from `ronininc-site`, run the de-brand checklist, apply the
   theme-token reskin from step 2's palette, and set the sold tier. For a **bespoke mini-CRM**
   instead: provision a fresh D1 node (`commerce-spine`), gate it (`cf-identity`), wire capture
   + API (`cf-forms` + `cf-functions`), and seed the record model from `starter-schema.sql`.
   Either way: light up optional layers per the guardrails; free-tier by default
   (`references/free-tier-playbook.md`).
4. **Ship & verify — `cf-deploy`.** Preview → remote D1 + additive migrations → go live,
   operator-approved. Verify by a live record round-trip AND that **login is unchanged**
   (bracket every deploy: user-count before/after, `auth.js`/`SESSION_SECRET` untouched,
   a live login probe returns a clean 401 for bad creds — the Pineapple launch is the
   worked example).

The output is one coherent client build — a real site backed by a sovereign CRM, from the
client's own verified data, on the free tier, with their login never disturbed. That is the
"and it should happen" — one instruction, the whole chain.

## The guts (what each building block provides — compose, don't rebuild)

| Layer | Skill / reference | What it gives the CRM |
|---|---|---|
| **Client data (the "Owner.com skill")** | `business-profile-recon` (+ `site-media-fetch`, `spanish-regional-localization`) | The client's REAL verified facts + media from Owner.com / GBP / socials — the build starts from truth, never placeholders. |
| **The site** | `website-build-standard` (or `sports-website-standard` / a vertical) | The client-facing site the CRM sits behind. |
| **Data + CRM + commerce brain** | `commerce-spine` | The per-site Cloudflare **Worker + D1 node**: contacts/customers, pipeline, orders, unlimited catalog, append-only history. Includes the **D1 10 GB shard-overflow** (sticky, co-located by aggregate root) and **R2 offload** for big blobs — so the CRM scales past one database. |
| **Auth + roles** | `cf-identity` | Real login/signup/sessions, PBKDF2 hashing, owner/admin/staff roles, a members-only gate. *(Note: Workers runtime caps PBKDF2 at 100k iterations — see memory.)* |
| **Lead / contact capture** | `cf-forms` | Contact, booking, lead, signup, RSVP forms writing straight into the CRM's D1. |
| **API / backend** | `cf-functions` | The serverless endpoints the CRM UI calls (`/api/*`). |
| **Ship it** | `cf-deploy` | Client-viewable preview, remote D1 + migrations, go-live on a real URL (operator-approved). |
| **Intelligence (optional)** | `references/intelligence/` | Sovereign, explainable **scoring** (lead-conversion / churn / reorder) + **forecasting** — pure-JS, **zero egress, zero neurons (free-tier stars)**; **governed LLM assist** (never auto-sends) — Workers AI, free within 10k neurons/day, cache + on-demand; **semantic** search/dedup/recommend — Vectorize (`semantic.mjs`, **Paid**) *or* the free path (`semantic-d1-free.mjs`, embeddings-in-D1 + in-Worker cosine). **42 proof assertions**. |
| **Outreach (optional)** | `references/power-dialer.md` | A compliance-first, live-agent **power dialer** inside the CRM (DNC/TCPA/consent gated, AMD auto-advance, browser softphone). |
| **Workforce productivity (optional)** | `references/workforce-productivity.md` | The admin's real-time **"who's working, who's not"** dataset — active/idle/offline, weighted score, per-active-hour rate, trend, team rollup. **Activity-derived from real CRM work, NOT surveillance.** Ships an append-only D1 ledger + a pure-JS Worker endpoint + the shared view panel (same core as Solomon's dashboard). Free-tier: tiny rows, zero neurons. |
| **Custom fields (vertical-agnostic)** | `custom-fields-engine` | An admin DEFINES extra fields (label/type/options per entity); staff SET values per record — so a dentist vs salon vs contractor differ only in config rows + data, **never in schema code**. The mechanism that lets the ONE build serve any vertical at runtime, no per-client migration. |
| **Data lifecycle & sustainability** | `logical-backup-ndjson-r2` + `r2-upload-budget-guard` + `export-before-delete-reclaim` + `sovereign-store-zip-writer` | **The layer shallow CRMs skip.** Gzip-NDJSON backups → private R2 with keep-N retention + a documented restore; an account-wide R2 budget guard that REFUSES writes past ~9 GB (never a silent overage) + a live usage readout; export-before-delete reclaim (build the ZIP archive before any purge); a dependency-free STORE zip writer. Keeps a free-tier CRM bounded and recoverable by construction. |
| **Notion substrate (alternative)** | `notion-intake-crm-cloner` | When the client wants to own the CRM in their **own Notion workspace** (lead-driven service firms) instead of a Cloudflare node. |

## The six-layer "full CRM" bar (what makes it FULL, not shallow)

A template missing ANY layer is the "trash CRM" failure mode. Every full build has all six — this is
the bar a CRM is measured against before it ships:

| Layer | Delivered by |
|---|---|
| **A · Platform spine** (per-tenant isolation) | `commerce-spine` (per-site Worker + D1 node) + `d1-image-store` / R2 + PWA assets + `cf-deploy` — 1 Worker + 1 D1 + 1 R2 + assets **per client, on the client's OWN Cloudflare account**. Never a shared bucket/DB across tenants. |
| **B · Security** (fail-closed) | `cf-identity` (sessions/roles) + `clearance-rbac` (route→section map; **unmapped routes default-DENY** for non-admins; destructive routes off-map = owner-only) + sameOrigin CSRF on every non-GET + `field-encryption-at-rest` (AES-GCM for free-text PII) + `worker-media-headers` + `idempotent-public-submission` (uploads: nosniff + inline-type allowlist + tenancy on upload AND list AND serve). |
| **C · Core CRM + custom fields** | this skill's records / pipeline / activities / intake + `custom-fields-engine` (vertical = config + data, never schema code) + first-party `self-schedule-booking` (never mailto/Google). |
| **D · Data lifecycle & sustainability** | `logical-backup-ndjson-r2` + `r2-upload-budget-guard` + `export-before-delete-reclaim` + `sovereign-store-zip-writer`. **The layer shallow CRMs skip** — no backup, no budget awareness, blind delete are the trash tells. |
| **E · Presentation** (agnostic) | `website-build-standard` + SEO baseline (never fabricate) + real photos (`site-media-fetch`, not clipart) + `universal-i18n-runtime` + a versioned network-first PWA service worker. Editorial layout, **not** AI card-grid slop. No AR / no prices unless asked. |
| **F · Engineering discipline** | `d1-proof-harness` + the house rules: TSC clean, prove each mechanism standalone, browser-verify UI, no needless deps, **no fake PASS**. |

**Stop-doing — the tells of a trash CRM:** vertical hardcoded into schema; no auth/clearance/CSRF; blind
delete with no backup/export; unbounded R2 with no budget awareness; a shared bucket/DB across tenants;
plaintext PII at rest; card-grid slop UI. If any of these are true, it isn't a full Ronin CRM yet.

## The customization surface (this is the only part that differs per client)

Everything above is reused. You tailor **four things** (see `references/customization-guide.md`):
1. **The record model** — what an entity is (customer, lead, member, patient-intake, investor,
   student…) and its fields. Start from `references/starter-schema.sql` and edit.
2. **The pipeline** — the stages a record moves through (new → contacted → qualified → won, or the
   client's real funnel) and what each stage triggers.
3. **Roles + who sees what** — the `cf-identity` role ranks mapped to the client's team.
4. **The channels + intelligence** — which capture forms, which intelligence features (scoring /
   forecast / semantic / assist), and whether outreach (the dialer) is wired — each subject to its
   guardrail.

## Build workflow

1. **Scope the record model and pipeline first** (the only custom part). Name the entity, its
   fields, its stages, its roles. Write them into a copy of `references/starter-schema.sql`.
2. **Provision the data brain** via `commerce-spine` (`references/provision.md`): create the D1,
   apply the starter schema as `0001_init.sql`, bind the Worker, pin `account_id`. Ships empty-ready.
   If the client is lead-driven and wants Notion, use `notion-intake-crm-cloner` instead and skip to 6.
3. **Gate it** with `cf-identity`: seed the owner, map roles, put the CRM behind login.
3b. **Set the sold tier** (`references/tiers.md`): pick Good/Better/Best for this client and apply it
   once — `POST /api/admin/instance/tier {tier:N}` (or seed `instance_config.tier` + reconcile
   `app_store.enabled` before first boot). Above-tier apps lock into the upsell automatically; the
   operator's own instance is Tier 3. Upgrading later is one call, no redeploy.
4. **Wire capture + API**: `cf-forms` for inbound records, `cf-functions` for the CRM's `/api/*`.
5. **Add intelligence (optional, per the guardrails)**: copy `references/intelligence/` into
   `worker/lib/crm-intelligence/`, write the feature extractors for THIS record model, train offline
   (`train.mjs` → weights.json), wire scoring/forecast (pure-JS, no binding) and — if wanted —
   semantic + assist (needs the `ai`/`vectorize` bindings). Prove with the bundled `_proof` pattern.
6. **Add outreach (optional)**: `references/power-dialer.md` for a governed in-CRM dialer.
6b. **Add workforce productivity (optional, if the owner manages a team)**: copy `references/workforce-compute.mjs` + `references/workforce-panel.mjs`, apply the `crm_activity_events` table, call `recordActivity` on the write paths, expose `GET /api/workforce` (admin-gated), mount the panel in the admin page — full steps in `references/workforce-productivity.md`.
7. **Scale when it grows**: when one node nears 9 GB, turn on `commerce-spine`'s shard-overflow
   (sticky, co-located by the record's aggregate root) and R2 offload for blobs. Not before.
8. **Ship** via `cf-deploy` — preview, remote migrations, go-live. **Operator approves every real
   deploy and every outbound send.** No fake PASS: verify by a live record round-trip + real proof.

## Non-negotiables (inherit each block's rules, plus these)

- **Customize the record model, reuse the plumbing.** If you find yourself re-writing auth, capture,
  or the API, stop — compose the skill that already does it.
- **`tenant_id` in every record identity** (`${tenant}:${kind}:${key}`) — the same convention that
  makes the shard router and the R2 offload safe, and it keeps global-unique ids so a second shard
  never collides (per-DB `INTEGER AUTOINCREMENT` roots do — fix before overflow).
- **Everything learned is explainable; everything generated is governed.** Scores return their
  factors; LLM assist returns `requiresApproval` and never sends. Advisory, human-in-the-loop.
- **Guardrails are absolute.** Regulated-finance CRM ⇒ non-advisory analytics only (no
  predictions/advice). Minors' data ⇒ no ML over content without a safeguarding + consent review;
  metadata-only, default-off. (Both proven in the field — see the CRM-intelligence rollout.)
- **Sovereign-first.** Prefer the pure-JS, zero-egress layers (scoring, forecasting); the edge-model
  layers (semantic, assist) stay on the platform's own network, never a third party.
- **Truth over spectacle.** A record is real when it round-trips through the live DB; an integration
  is ready only when its probe says so; a deploy happens only with the operator's go-ahead.

## References

- `references/turnkey-reproduction.md` — **read this to reproduce the full Ronin OS for a client** — the clone-and-parameterize model, the canonical template (`ronininc-site`, `main` = deployed), the de-brand checklist, the theme-token reskin, the plug-in-keys/secrets surface, the deploy path + `7403` fix, the tier gate, the 37-app → tier manifest, and the honest turnkey gaps.
- `references/tiers.md` — **the good/better/best packaging** — the three sellable tiers, the proven runtime gate (`app_store.min_tier` + `instance_config.tier` + `applyTier`), and the one-command tiered provision.
- `references/free-tier-playbook.md` — **read first when the client is on free** — the grounded limits + the ten master moves that keep a CRM on the free plan.
- `references/feature-catalog.md` — every reusable CRM feature profiled, de-conflicted (pick-one conflict groups + additive set), each with its free-tier cost and where it's proven.
- `references/architecture.md` — the guts map, the build order, and exactly how the blocks compose.
- `references/customization-guide.md` — the four customization points, worked for several verticals.
- `references/starter-schema.sql` — a generic, customizable CRM schema (contacts / pipeline / deals / activities / tags / media).
- `references/intelligence/` — the sovereign ML layer: `score` / `forecast` (pure-JS), `assist` (governed Workers AI), `semantic` (Vectorize, Paid) + `semantic-d1-free` (free fallback), `train`, and proofs (`npm test` → 42 assertions).
- `references/power-dialer.md` — the governed in-CRM power dialer spec.
- `references/workforce-productivity.md` — the admin's real-time workforce dataset (D1 ledger + Worker endpoint + shared panel); `references/workforce-compute.mjs` (pure engine) + `references/workforce-panel.mjs` (framework-neutral view, same core as Solomon's dashboard).
