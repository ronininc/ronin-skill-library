# Keys & Connectors — turnkey onboarding list

Every third-party key the Ronin-OS CRM (`ronininc-site`) can consume, grounded from
the live worker (`grep env.<KEY>` across `worker/` + `wrangler.jsonc`, 2026-09-19).
This is the "plug your keys in and it's live" surface for reselling.

**Design principle — inert until keyed.** Every connector reads its `env.X` and
**no-ops safely when unset**. A resold instance boots on the Tier-0 set and lights up
each capability only when the operator adds that key. Nothing here blocks first boot
except the Tier-0 bindings.

---

## Three mechanisms (they onboard differently)

| Kind | What it is | How you set it |
|---|---|---|
| **Binding** | A Cloudflare resource (D1, R2, Workers AI, static assets) | `wrangler d1 create` / `wrangler r2 bucket create`, then reference in `wrangler.jsonc` |
| **Var** | Non-secret config, committed in `wrangler.jsonc` → `vars` | Edit `wrangler.jsonc` per client |
| **Secret** | Credential, never committed | `echo "VALUE" \| npx wrangler secret put NAME` |

---

## Tier 0 — minimum to boot (required)

| Name | Kind | Purpose |
|---|---|---|
| `DB` | binding (D1) | The CRM database. `wrangler d1 create <client>-crm` → paste id into `wrangler.jsonc`. |
| `ASSETS` | binding | Static asset serving (admin SPA, `/m` PWA). |
| `AI` | binding (Workers AI) | On-platform inference (scoring/assist). Free-tier 10k neurons/day. |
| `ENCRYPTION_KEY` | secret (**optional**) | AES-GCM for notes/messages at rest. Unset = stored in clear + Worker still runs. `openssl rand -base64 32`. **Set it for any real client.** |
| `ADMIN_SIGNUP_CODE` | secret (**optional**) | Gate for claiming the FIRST admin. Unset = first signup bootstraps as admin with no code. |

---

## Vars (edit in `wrangler.jsonc` → `vars`, per client)

| Name | Current value / meaning |
|---|---|
| `GOOGLE_REDIRECT_URI` | OAuth callback — **must** become `https://<client-domain>/api/integrations/google/callback` |
| `GOOGLE_OUTREACH_EMAIL` | The Gmail the CRM sends outreach from |
| `META_GRAPH_VERSION` | e.g. `v25.0` |
| `LINKEDIN_API_VERSION` | e.g. `202609` |
| `VAPID_PUBLIC` | Web-Push public key (safe to expose; private half = `VAPID_JWK` secret) |

**Read by code but NOT declared — confirm per deploy:** `PUBLIC_BASE_URL` (client's
canonical URL — set as a var), `CLOVER_ENV` (`sandbox`/`production`), `PLAID_ENV`
(`sandbox`/`development`/`production`). Add these to `vars` when wiring those connectors.

---

## Secrets by capability (`wrangler secret put NAME`)

Add only the groups a client actually uses. Each group is independent.

### Email
| Key | Notes |
|---|---|
| `RESEND_API_KEY` | Transactional/outreach email (Resend). Pick one provider. |
| `SENDGRID_API_KEY` | Alternative email provider (SendGrid). |
| `SMTP_VERIFIER_HMAC_SECRET` | Signs email-verification links. |

### Google (Gmail / Calendar OAuth)
| Key | Notes |
|---|---|
| `GOOGLE_CLIENT_ID` | OAuth app client id. |
| `GOOGLE_CLIENT_SECRET` | OAuth app secret. (+ `GOOGLE_REDIRECT_URI`, `GOOGLE_OUTREACH_EMAIL` vars.) |

### Telephony / SMS (pick a provider)
| Key | Notes |
|---|---|
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | Twilio voice/SMS (power-dialer). |
| `TELNYX_API_KEY` / `TELNYX_PUBLIC_KEY` | Telnyx alternative. |

### Payments
| Key | Notes |
|---|---|
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Stripe. |
| `CLOVER_API_TOKEN` / `CLOVER_MERCHANT_ID` | Clover POS (+ `CLOVER_ENV` var). |

### Banking
| Key | Notes |
|---|---|
| `PLAID_CLIENT_ID` / `PLAID_SECRET` | Plaid (+ `PLAID_ENV` var). |

### Web Push (mobile `/m` companion)
| Key | Notes |
|---|---|
| `VAPID_JWK` | Private push key (JWK w/ `d`). Pairs with `VAPID_PUBLIC` var. Unset = logs but no push (safe). |

### Social — inbound + outbound (Meta suite + others)
| Key | Notes |
|---|---|
| `META_APP_SECRET` / `META_VERIFY_TOKEN` | Meta app + webhook verify. |
| `INSTAGRAM_ACCESS_TOKEN` / `INSTAGRAM_BUSINESS_ID` | Instagram Messaging. |
| `FACEBOOK_PAGE_ACCESS_TOKEN` / `FACEBOOK_PAGE_ID` | Facebook page. |
| `X_USER_ACCESS_TOKEN` | X/Twitter. |
| `LINKEDIN_ACCESS_TOKEN` / `LINKEDIN_AUTHOR_URN` | LinkedIn (+ `LINKEDIN_API_VERSION` var). |
| `TIKTOK_ACCESS_TOKEN` | TikTok. |
| `OPENPOST_API_TOKEN` | Cross-post aggregator. |

### E-commerce
| Key | Notes |
|---|---|
| `SHOPIFY_WEBHOOK_SECRET` | Verifies Shopify webhooks. |

### AI brains (beyond Workers AI)
| Key | Notes |
|---|---|
| `ANTHROPIC_API_KEY` | Claude. |
| `OPENAI_API_KEY` | OpenAI. |
| `BRAIN_API_KEY` / `BRAIN_BASE_URL` / `BRAIN_MODEL` | Self-hosted/custom brain endpoint. |

### Affiliate / partner networks
| Key | Notes |
|---|---|
| `PARTNERSTACK_API_KEY` | PartnerStack. |
| `IMPACT_API_KEY` | Impact.com. |
| `GOHIGHLEVEL_API_KEY` | GoHighLevel. |
| `UPWORK_CLIENT_ID` / `UPWORK_CLIENT_SECRET` | Upwork. |

### Data enrichment / lead discovery engine
| Key | Notes |
|---|---|
| `SAM_GOV_API_KEY` | Federal contract data (SAM.gov). |
| `PAGESPEED_API_KEY` | Google PageSpeed (site-audit lead hook). |
| `SOCRATA_APP_TOKEN` | Open-data (Socrata). |
| `GITHUB_TOKEN` | GitHub API. |
| `MAPILLARY_TOKEN` | Street-level imagery. |

---

## Feature flags / bindings — NOT paste-in keys (verify)

Read by the discovery engine; appear to be toggles or bindings, not third-party
credentials: `OPEN_DATA`, `OPEN_DATA_IMPORT`, `DOMAIN_PROBES`, `NEED_PROBE`,
`BUSINESS_ENRICHMENT`. `LEAD_GENERATION` / `MAPTILES` are R2 bindings (create the
bucket, no key). Confirm each usage before treating as a key.

## Not yet wired
- `CJ_API_KEY` — appeared in an earlier key dump but is **not read by current code**.
  No plumbing exists yet; adding the secret does nothing until a connector reads it.

---

### One-glance count
5 bindings · 5 vars (+3 undeclared to add) · ~40 secrets across 12 capability groups.
Tier-0 boot needs 3 bindings (+2 optional secrets). Everything else is opt-in.
