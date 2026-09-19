# CRM feature catalog — every reusable feature, de-conflicted

Profiled from the proven client builds (pineapple, slik, wavelygth, case-plug, oro-talent) and the
guts skills. Each feature names **where it's proven**, its **free-tier cost**, and any **conflict**.
"Don't walk on each other's toes" = pick ONE per conflict group; everything else composes additively.

Legend — free-tier cost: **Free✓** (no paid dependency) · **Free~** (free but budget a daily limit) ·
**Paid** (needs Workers Paid).

## Conflict groups — pick exactly ONE of each
- **Substrate:** Cloudflare D1 node (`commerce-spine`) **— default** ▸ *or* ▸ client-owned Notion
  (`notion-intake-crm-cloner`) for a lead-driven firm that wants no dev. Never both.
- **Auth:** `cf-identity` PBKDF2 — the only auth. Don't add a second.
- **Hosting:** static UI on Pages + one Worker for `/api/*` (`run_worker_first`). One deploy path
  (`cf-deploy`). Don't mix Pages Functions and a standalone Worker for the same routes.

## Core (every CRM) — Free✓
| Feature | Proven in | Notes |
|---|---|---|
| D1 record brain: contacts/pipeline/deals/activities | commerce-spine + `starter-schema.sql` | the aggregate root = the contact |
| Append-only activity/history log | all | the truth; every touch + stage change |
| Pipeline stages as DATA (config not code) | `starter-schema.sql` | client funnel = rows in `pipeline_stages` |
| `tenant_id` identity + money-as-cents + AES-GCM at rest | commerce-spine | invariants the rest depend on |
| Serverless API `/api/*` | cf-functions | the endpoints the UI calls |

## Auth & security — Free✓
| Feature | Proven in | Notes |
|---|---|---|
| Login / signup / sessions / roles (owner·admin·staff) | cf-identity | PBKDF2 **100k iters max** (runtime cap) |
| Login lockout (brute-force throttle) | wavelygth, slik (`login_failures`) | count failures, lock window |
| Admin 2FA (TOTP) | wavelygth | gate admin actions; lives in the profile |
| Shared sign-up code / invite-only | cf-identity, oro-talent | gate who can register |
| Minor-safeguarding (guardianship + messaging approvals) | oro-talent | ⛔ only when minors are involved |

## Capture & import — Free✓
| Feature | Proven in | Notes |
|---|---|---|
| Forms → DB (contact/lead/booking/RSVP) | cf-forms | set `consent_basis` at capture |
| Admin data-feed ingestion (drag-drop files + agnostic API/CLI paste) | wavelygth | unlimited bulk import, any shape |
| Webhook idempotency + loop-safe dedupe | commerce-spine, pineapple, slik | `${mId}:${obj}:${type}:${ts}` key |
| Real photos from client connectors (never clip-art) | memory | product/flyer media = real files |

## Views, admin & reporting — Free✓
| Feature | Proven in | Notes |
|---|---|---|
| Admin record search | wavelygth | index the searched columns (stay < 5M reads/day) |
| Profile popup + admin UI customization | wavelygth | per-user settings, brandable admin |
| Report generator (periodic/monthly) | wavelygth | aggregate from D1; render server-side |
| CRM game-map / pipeline board UI | tss-crm-game-map | offline OSM basemap + todo cards (optional) |

## Intelligence (optional, governed) — see free-tier notes
| Feature | Proven in | Free-tier cost |
|---|---|---|
| **Scoring** (lead-conversion / churn / reorder), explainable | `references/intelligence/score.mjs` | **Free✓** — pure JS, zero egress, zero neurons |
| **Forecasting** (reorder/demand, cost/duration) | `references/intelligence/forecast.mjs` | **Free✓** — pure JS |
| **Semantic** (search / dedup / recommend) | `references/intelligence/semantic.mjs` (Vectorize) | **Paid** (Vectorize). Free path = embeddings-in-D1 + in-Worker cosine, see free-tier-playbook |
| **LLM assist** (summarize / draft / classify / extract), governed | `references/intelligence/assist.mjs` | **Free~** — Workers AI 10k neurons/day; cache, small models |
> Scoring + forecasting are the free-tier stars (no neuron cost). Assist is free within the daily
> neuron budget. Semantic is the one feature that wants Paid — use the D1 fallback until then.

## Outreach (optional, governed) — Free~
| Feature | Proven in | Notes |
|---|---|---|
| Power dialer (live-agent, DNC/TCPA/consent gated) | `references/power-dialer.md` | needs a telephony account (Twilio) — not a CF cost |
| Governed drafts (never auto-send; `requiresApproval`) | assist.mjs | outbound always human-approved |

## Commerce (optional) — Free✓ for catalog/CRM; tender needs a gateway
| Feature | Proven in | Notes |
|---|---|---|
| Unlimited catalog (15k-POS bypass) + pricing tiers + inventory ledger | commerce-spine, pineapple | DB is master; hot-set syncs to POS |
| Orders / line-items / invoices / checkout sessions | pineapple, slik | money = cents |
| Processor-agnostic tender (Stripe/Square/Authnet/Clover) | commerce-spine | only where the gateway is OPEN; else catalog+CRM only |
| Member/wholesale CRM + spend ledger + tiers | pineapple | businesses→contacts→notes→spend |

## Messaging (optional) — Free✓
| Feature | Proven in | Notes |
|---|---|---|
| Encrypted message board / conversations | slik, oro-talent | AES-GCM bodies; ⛔ no ML on minors' content |

## Truth & ops (the credibility layer) — Free✓
| Feature | Proven in | Notes |
|---|---|---|
| Append-only audit log | everywhere | who did what, immutable |
| Data-quality flags + staleness detection | wavelygth | e.g. NAV-staleness; DATA_INTEGRITY not a domain signal |
| Honest labels (never fake a status) | wavelygth (POF labels) | show real state; no optimistic "ready" |
| Backups / restore | wavelygth (`BACKUP_RESTORE.md`) | scheduled D1 export; documented restore |

## Scale — Free✓ (to 5 GB account) then Paid
| Feature | Proven in | Notes |
|---|---|---|
| D1 10 GB shard-overflow (sticky, co-located by root) | commerce-spine `sharding.md` + all 5 rollouts | on FREE, shard across 500 MB DBs up to the 5 GB account cap |
| R2 offload for blobs (2 MB row-cap escape) | commerce-spine `r2-offload.mjs`, pineapple images | 10 GB free; zero egress |
| i18n / bilingual | pineapple (bilingual catalog), ronininc (12-lang) | region-agnostic copy |

## Deploy — Free✓
| Feature | Proven in | Notes |
|---|---|---|
| Client-viewable preview → remote D1 + migrations → go live | cf-deploy | operator approves every real deploy |
