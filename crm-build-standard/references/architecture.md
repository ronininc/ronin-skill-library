# CRM architecture — how the guts compose

A CRM built this way is one Cloudflare Worker + D1 node (the `commerce-spine` brain) with layers
bolted around it. Each layer is an existing skill; this doc is the wiring diagram and the order.

```
                       ┌─────────────────────────────────────────────┐
  browser / app  ─────▶│  cf-identity  (login, sessions, roles)       │
                       └───────────────┬─────────────────────────────┘
                                       │ authed requests
  public forms ──cf-forms──▶  /api/*  ─┤
                                       ▼
                       ┌─────────────────────────────────────────────┐
                       │  cf-functions  (the CRM API endpoints)       │
                       └───────────────┬─────────────────────────────┘
                                       ▼
                       ┌─────────────────────────────────────────────┐
                       │  commerce-spine  (D1 node = the CRM brain)   │
                       │   contacts · pipeline · deals · activities   │
                       │   + 10 GB shard-overflow  + R2 offload       │
                       └───────┬───────────────────────┬─────────────┘
                               │                       │
          references/intelligence/             references/power-dialer.md
          score·forecast·semantic·assist       governed live-agent dialer
          (advisory, governed)                 (DNC/TCPA/consent gated)
                                       ▼
                              cf-deploy  (preview → go live)
```

## Layer-by-layer

1. **commerce-spine — the brain.** The per-site Worker + D1 node. Provides the record tables
   (customize via `starter-schema.sql`), the append-only activity log, money-as-cents, the
   `${tenant}:${kind}:${key}` identity convention, AES-GCM at rest, the **D1 10 GB shard-overflow**
   (sticky, co-located by aggregate root — here the `contact`), and **R2 offload** for blobs. Read
   its `references/provision.md` for the bring-up, `references/sharding.md` for scale-out.
2. **cf-identity — the gate.** PBKDF2 users/sessions, owner/admin/staff roles, a members-only wall.
   Map the role ranks to the client's team. (Runtime caps PBKDF2 at 100k iterations — don't exceed.)
3. **cf-forms — inbound capture.** Contact/lead/booking forms writing straight into `contacts` +
   an `activities` row. Set each lead's `consent_basis` at capture — the dialer and any outreach
   depend on it.
4. **cf-functions — the API.** The authed `/api/*` the CRM UI calls (list/search/create/update a
   record, move a stage, log an activity, pull a contact's timeline).
5. **intelligence (optional) — make it smart.** Copy `references/intelligence/` into
   `worker/lib/crm-intelligence/`. Two engines are pure-JS, zero-egress (scoring, forecasting);
   two use the platform's edge models (semantic via Vectorize, assist via Workers AI). You write the
   **feature extractors** for this record model; the engines are reused. Everything is explainable
   and governed (assist never sends). Prove with the bundled `_proof` harness pattern.
6. **power-dialer (optional) — reach out.** A live-agent dialer inside the CRM, gated on DNC / TCPA
   hours / consent. See `references/power-dialer.md`.
7. **cf-deploy — ship.** Client-viewable preview (wrangler dev), remote D1 + migrations, go-live on
   a real URL. Operator approves every real deploy.

## Build order (dependencies)

`commerce-spine` (schema + node) → `cf-identity` (gate) → `cf-forms` + `cf-functions` (capture + API)
→ optional `intelligence` → optional `power-dialer` → `cf-deploy`. Intelligence and the dialer are
always last and always optional; the CRM is fully functional without them.

## Substrate choice (decide at step 1)

- **Cloudflare D1 node (default):** sovereign, owned, scales via sharding, hosts intelligence +
  dialer. Use for almost everything.
- **Notion workspace (`notion-intake-crm-cloner`):** when a lead-driven service firm wants to own
  the CRM in their OWN Notion and run it without a dev. Leads/intake/marketing-ROI scope only (no
  PHI). You skip commerce-spine/cf-* and clone the Notion databases instead; intelligence/dialer
  don't apply.

## Proven in the field

The sharding + intelligence guts were rolled out across five real client CRMs (pineapple, slik,
wavelygth, oro-talent, case-plug) — each additive, each with local proof, each respecting its
guardrail (wavelygth non-advisory; oro-talent metadata-only for minors). That rollout is the
reference for how these layers drop onto an existing node without rewriting it.
