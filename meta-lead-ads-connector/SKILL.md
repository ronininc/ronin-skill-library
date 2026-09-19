---
name: meta-lead-ads-connector
description: >-
  The connector delta for ingesting Meta (Facebook/Instagram) Lead Ads into a Cloudflare Worker + D1 CRM:
  the GET subscription-verification handshake (hub.mode / hub.verify_token → echo hub.challenge), the POST
  leadgen event loop, resolving a bare `leadgen_id` to its answers via the Graph API with a Page access
  token, and mapping Meta's `field_data[]` (full_name/first_name/last_name/email/phone_number/company_name/
  city/custom questions) into your normalized lead shape. Use WHENEVER a build must "capture Meta/Facebook/
  Instagram Lead Ads", "wire the Lead Ads webhook", "verify the Meta webhook subscription", "resolve a
  leadgen_id", "pull lead-form answers from the Graph API", or run a first-party opt-in funnel off Meta ads.
  This is the PROVIDER-SPECIFIC layer that sits ON TOP of signed-webhook-intake — that skill owns the HMAC
  SHA-256 verification, timing-safe compare, fail-closed secret handling, and idempotency you MUST reuse
  here; do NOT re-implement the crypto. It COMPLEMENTS social-dm-inbox (the Meta DM webhook sibling — same
  provider, different `field`) and hands each captured lead to lead-qualifier / reference-intel-matcher /
  blended-score-trust-gate for scoring. Guardrail: first-party opt-in only (Custom Audiences must be
  first-party); the intel/score is NEVER returned to the public form response.
---
# Meta Lead Ads Connector

## What it is / when to use / what it composes with
The Meta Lead Ads ingestion path is a **two-verb endpoint** on one route (`/webhook/meta`): `GET` answers
Meta's subscription challenge, `POST` ingests `leadgen` change events. It is the specific provider adapter
that turns raw Meta webhook traffic into normalized CRM leads.

- **Composes UNDER it:** `signed-webhook-intake` — the HMAC-SHA256 + timing-safe + fail-closed + idempotency
  primitive. This skill is only the Meta-shaped delta on top: the verify handshake, the Graph API
  resolution, and the field mapping. Build the verification layer with that skill; add this on top.
- **Sibling:** `social-dm-inbox` is the same Meta webhook transport for the `messages`/`messaging` field;
  Lead Ads is the `leadgen` field. Same signature scheme, different payload.
- **Feeds:** the normalized lead flows straight into `lead-qualifier`, `reference-intel-matcher`, or
  `blended-score-trust-gate` for scoring, then into any CRM contacts table.

## Reference implementation — exact source
`~/Projects/ronin-jv-lead-engine/src/index.js`:
- **Subscription verify (GET):** `metaVerify(url, env)` — `src/index.js:47-53`. Checks
  `hub.mode === "subscribe"` && `hub.verify_token === env.META_VERIFY_TOKEN`, echoes `hub.challenge`, else 403.
- **Signature (reuse signed-webhook-intake):** `timingSafeEqualHex` `src/index.js:54-59`; `verifySig`
  `src/index.js:60-72` — imports the app secret as an HMAC key, signs the raw body text, compares
  `sha256=<hex>` to `x-hub-signature-256`. **Fail-closed:** no `META_APP_SECRET` ⇒ auth is OFF only when the
  explicit off-by-default dev flag `JV_DEV_ALLOW_UNSIGNED === "1"` is set (`src/index.js:63`).
- **leadgen_id resolution:** `fetchMetaLead(leadgenId, env)` — `src/index.js:74-81`. GETs
  `graph.facebook.com/v19.0/<leadgenId>?access_token=<META_PAGE_ACCESS_TOKEN>`; returns null if no token / not ok.
- **field_data mapping:** `fromFieldData(fd)` — `src/index.js:82-90`. `g(k)` reads `fd.find(f=>f.name===k).values[0]`;
  composes `full_name` OR `first_name`+`last_name`; maps email/phone_number/company_name/city and a custom
  question to `message`.
- **The POST loop:** `src/index.js:221-241` — for each `body.entry[].changes[]` where `ch.field === "leadgen"`,
  use inline `ch.value.field_data` if present, else resolve via Graph, else store a stub `leadgen_id <id>
  (resolve via Graph API)`; save with the `leadgen_id` as the idempotency key; count only newly-`inserted` rows.

## How to reapply
- **Secrets** (Worker secrets, never in D1 or committed — see `wrangler.toml:12-16`): `META_VERIFY_TOKEN`,
  `META_APP_SECRET`, `META_PAGE_ACCESS_TOKEN`.
- **Route:** one path, both verbs. `GET` → `metaVerify`; `POST` → read body **as text first**
  (`await req.text()`) so the signature is computed over the exact bytes, verify, THEN `JSON.parse`.
- **Idempotency (schema):** store the provider event id and collapse replays with a *partial* unique index —
  `schema.sql:26`: `CREATE UNIQUE INDEX ... ON leads(event_id) WHERE event_id IS NOT NULL`, written via
  `INSERT OR IGNORE` (`src/index.js:31-42`). Landing-page leads pass `event_id = NULL` and stay unconstrained;
  only Meta rows dedup. `changes` (`meta.changes`) tells you if the row was actually new.
- **Meta app wiring:** point the Meta app's **Webhooks → Page → `leadgen`** subscription at `/webhook/meta`
  with verify token = `META_VERIFY_TOKEN`; grant a **Page access token** so `leadgen_id` resolves to fields.

## Gotchas (from the code)
- **Verify the raw body, parse after.** Reading JSON first and re-stringifying will change bytes and break the
  HMAC. `src/index.js:224-226` reads text, verifies, then parses.
- **A `leadgen_id` alone is not the lead.** Meta often sends only the id; without a Page token you can't
  resolve it — the code stores a resolvable stub rather than dropping it (`src/index.js:234`).
- **Fail closed on a missing secret.** A missing `META_APP_SECRET` must NOT silently disable auth — the only
  bypass is an explicit, off-by-default local dev flag (`src/index.js:63`).
- **Replays are normal.** Meta redelivers; the partial-unique `event_id` + `INSERT OR IGNORE` makes a replay a
  no-op. Count `meta.changes > 0`, not "the POST arrived."
- **First-party only.** Seed Custom Audiences / Lookalikes from *opted-in* leads captured here; never from
  scraped/appended third-party PII. Never echo the internal score back in the public form response
  (`src/index.js:217`).
