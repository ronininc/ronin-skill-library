---
name: github-lead-mining
description: >-
  Sovereign, ToS-clean B2B lead sourcing via the official GitHub REST API — no scraping, no anti-bot
  evasion. Searches users/orgs matching a target profile (query + optional type:org/type:user), enriches
  each from its PUBLIC profile (name/company/location/blog/email/bio/hireable), and ingests only the
  candidates that expose a valid public email into the CRM contacts as source='github' (upsert by email,
  idempotent); every other candidate is returned so the operator can pursue it manually. Use WHENEVER a
  lead-gen CRM should "find leads on GitHub", "source developers / dev-shops / tech companies", "mine
  GitHub for [vertical] in [city]", "who's hiring / building X", or needs a B2B/tech-audience sourcing
  lane that isn't a map directory. This is a THIRD sourcing lane that COMPLEMENTS geo-directory-prospecting
  and open-data-signal-discovery (map + open-data lanes) — same downstream contacts table, different
  source; and it PAIRS with contact-enrichment-deliverability (verify the emails it finds),
  crm-build-standard (stores/scores the ingested contact) and lead-qualifier (fit). Do NOT reimplement
  their sourcing/scoring/verification here. It is ON-DEMAND (an admin action), not a cron workflow.
  Guardrails: official API only, ingest ONLY valid public emails (never fabricate), exclude your own
  outreach mailbox, honest 429 when unauthenticated, 512 KB response cap + 15s timeout.
---
# GitHub Lead Mining

## What it is / when to use
A single on-demand handler that turns a **GitHub search query** into CRM contacts. It runs one
`/search/users` query, enriches each hit from its public `/users/:login` profile, and writes the
email-bearing ones into `contacts` with `source='github'`. It exists as a **lawful, sovereign** sourcing
lane: unlike scraping LinkedIn or a directory, it uses GitHub's documented REST API only, so it stays
ToS-clean. Best for B2B / developer-adjacent / tech-company verticals where the decision-maker has a
public GitHub presence. Use it when map-based (`geo-directory-prospecting`) or open-data
(`open-data-signal-discovery`) lanes don't reach the audience.

**Composes with:** `geo-directory-prospecting` + `open-data-signal-discovery` (the other two sourcing
lanes — this is the GitHub lane; all three feed the same `contacts`/campaign store),
`contact-enrichment-deliverability` (run it on the ingested `source='github'` contacts to MX/SMTP-verify
the address before sending — GitHub emails are public but unverified for deliverability),
`crm-build-standard` (the contact/deal store + fit-scoring ML this feeds), `lead-qualifier` (fit),
`governed-email-outreach` (send to what it ingests). This skill owns **GitHub-API sourcing + email-gated
ingest only** — it does not verify deliverability, score fit, dial, or send.

## Reference implementation (ronininc)
- `worker/github-leads.ts` (whole file, ~110 lines) — confirmed read. Live and WIRED as an admin action.
- `worker/admin.ts:41` — `import { githubLeadSearch } from './github-leads'`.
- `worker/admin.ts:303` — route `POST /api/admin/leads/github → githubLeadSearch`.
- `worker/types.ts:45` — `GITHUB_TOKEN?: string` (OPTIONAL secret; raises the rate limit).
- **No dedicated migration** — it writes to the base `contacts` table (`migrations/0001_init.sql`,
  `UNIQUE INDEX idx_contacts_email`) using the `lead_type` column added by `0022_lead_tracks.sql`.
- **Not in cron.** `worker/index.ts` never calls it (verified by grep) — it is operator-triggered/
  on-demand, distinct from the scheduled `geo-directory-prospecting` workflow.

Key spans:
- **Auth-optional headers** `ghHeaders()` L17-21: fixed `User-Agent: ronin-crm` +
  `accept: application/vnd.github+json`; adds `Authorization: Bearer <GITHUB_TOKEN>` only if the secret
  is set. Works with zero keys (60 req/hr) or with a token (5000 req/hr).
- **Bounded fetch** `ghJson()` L23-30: 15s `AbortSignal.timeout`, rejects a response whose
  `content-length` exceeds `MAX_GH_RESPONSE = 512 KB` (L14, L26), tolerant JSON parse (never throws on a
  bad body — returns `{ ok, status, payload:{} }`).
- **Profile enrichment** `enrich()` L39-55: `GET /users/:login`, maps only public fields into a
  `Candidate` (`login/name/type/company/location/website(blog)/email/bio/url/public_repos/hireable`),
  each string length-clamped by `clean()` (L15). Returns null if the user has no `login`.
- **The handler** `githubLeadSearch()` L58-110:
  - Inputs L61-67: `query` (≥2 chars, else `bad(...)`), `kind` (`org`|`user`→`type:` qualifier L69),
    `per_page` clamped **1..10** default 6 (L64), `lead_type` default `'client'`, `vertical`, `ingest`
    default **true**.
  - Search L70-76: `GET /search/users?per_page&q=<query + typeQualifier>`; on `403` returns an **honest
    429** — `"GitHub rate limit reached. Add a GITHUB_TOKEN secret or try again later."` (L72), any other
    failure → 502. Takes `items[].login`, sliced to `per_page`.
  - Enrich loop L79-82: one `/users/:login` per hit (sequential — search doesn't return full profiles).
  - Ingest gate L84-100: for each candidate, **skip unless `validEmail()`** (L32, `[^@\s]+@[^@\s]+\.[^@\s]+`)
    AND **skip your own** `GOOGLE_OUTREACH_EMAIL` (L88); build audit tags
    `github-lead, gh:<login>, type:<user|org>, vertical:<v>`; `INSERT INTO contacts (... source='github',
    status='lead' ...) ON CONFLICT(email) DO UPDATE` (L91-97) — keeps a non-empty existing name,
    refreshes tags, `COALESCE`s lead_type, bumps `updated_at`. Idempotent by email.
  - Response L102-109: `{ ok, found, with_email, ingested, token:<bool>, candidates }` — returns the full
    candidate list (including no-email ones) for manual pursuit, and whether a token was in effect.

## How to reapply it
1. **Schema — reuse, don't add.** No new migration. The client CRM must already have the base `contacts`
   table with `UNIQUE(email)` (crm-build-standard / `0001_init.sql`) and a `lead_type` column
   (`0022_lead_tracks.sql` or equivalent `ALTER TABLE contacts ADD COLUMN lead_type TEXT`). If the CRM
   isn't dual-track, drop `lead_type` from the INSERT.
2. **Copy the handler.** `github-leads.ts` is self-contained (only `Env` + the `http` helpers
   `bad/json/now/readJson/str/uid`). Keep `ghHeaders`/`ghJson`/`enrich`/`validEmail`/`clean` intact —
   the byte cap, timeout, and tolerant parse are the safety envelope.
3. **Route.** Register `POST leads/github → githubLeadSearch` on the admin router (mirror `admin.ts:303`).
   Keep it behind the same admin auth as the rest of the CRM — it writes to `contacts`.
4. **Token (optional).** Add `GITHUB_TOKEN?: string` to `Env` and set it as a Worker **secret** to lift
   60/hr → 5000/hr. It is genuinely optional — the handler works unauthenticated and says so in the
   response (`token:false`) and in the 429 message.
5. **No cron.** This is deliberately on-demand. If you want it scheduled, don't bolt a loop onto this
   handler — enqueue queries through `rotating-leadgen-scheduler` / the geo workflow pattern so the
   at-most-once slot-claim and one-run-at-a-time guards apply.
6. **UI (optional, minimal).** A single admin form is enough: a query box (e.g.
   `"web agency location:phoenix"`), a `kind` select (any/org/user), `per_page`, an optional
   `vertical`/`lead_type`, an ingest toggle, and a results table showing `found / with_email / ingested`
   plus the returned candidates so the operator can manually pursue the no-email ones.
7. **Chain verification.** Immediately after ingest, run `contact-enrichment-deliverability` on the new
   `source='github'` rows — a public GitHub email is a real address but is NOT graded for deliverability
   until MX/SMTP-checked.

## Gotchas (from the code + comments)
- **ToS discipline is the whole point.** Official REST API only — no HTML scraping, no anti-bot evasion.
  The header comment (L1-8) is explicit. Don't "improve" recall by scraping profile pages; that's the
  line this skill exists to stay behind.
- **Two rate limits, both real.** Core is 60/hr unauthenticated → 5000/hr with a token, but the **search**
  endpoint has its own tighter limit (≈10/min unauth). `per_page` is capped at 10 and each result costs an
  extra `/users/:login` call, so a single search burns ~11 requests. Unauthenticated bulk use hits 403
  fast — the handler surfaces that as a 429 with the "add a token" message rather than pretending to
  succeed. Keep that honest 403→429 mapping.
- **Ingest ONLY valid, public emails.** Most GitHub users hide their email; `with_email` is typically a
  small fraction of `found`. The no-email candidates are returned, never fabricated into `first.last@`
  addresses. Do not add a pattern-inference path here — if you need inferred mailboxes, that's
  contact-enrichment-deliverability's `do_not_send_without_further_verification` lane, not this one.
- **Self-exclusion matters.** The `GOOGLE_OUTREACH_EMAIL` skip (L88) stops you ingesting your own sending
  address as a "lead" and then mailing yourself in a loop. Port it (or your CRM's equivalent sender
  address) when you reuse the handler.
- **Sequential enrichment is intentional.** Search returns thin user stubs; the full profile needs a
  second call per login. Firing those in parallel multiplies your request rate against the search-window
  limit — keep it sequential (or add a small concurrency cap with backoff), don't `Promise.all` all 10.
- **`kind` shapes the query, not a filter after.** `org`/`user` append `type:org`/`type:user` to the
  GitHub query string; an unknown value just means "no qualifier". Validate/clamp it (L63) so a caller
  can't inject query syntax.
