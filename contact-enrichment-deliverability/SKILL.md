---
name: contact-enrichment-deliverability
description: >-
  Turn a business website into VERIFIED, sendable contact points with a confidence ladder: an
  HTMLRewriter harvest of emails/phones/socials/people (anchors + mailto/tel + JSON-LD), a Cloudflare
  DoH MX-record check, a disposable-domain blocklist, libphonenumber normalization, and an optional
  HMAC-signed off-edge SMTP-verifier callback that upgrades a contact to 'deliverable'. Every contact
  stores WHERE it came from and WHAT was actually verified — MX proves a domain accepts mail, never a
  fabricated mailbox. Use WHENEVER a lead-gen CRM needs to "verify these emails", "are these contacts
  real / deliverable", "clean the contact list", "check MX / bounce risk", "enrich a business's
  contacts", or grade contact confidence before outreach. COMPLEMENTS lead-qualifier and
  outbound-compliance-gate (which decide fit and whether you're ALLOWED to send) and
  geo-directory-prospecting / open-data-signal-discovery (which SOURCE the businesses) — this skill
  verifies EXISTENCE/deliverability, the piece those don't cover; do NOT duplicate their sourcing or
  compliance logic. Guardrails: SSRF-guarded fetches, 400 KB byte cap, 7-day domain cache, never marks
  an inferred pattern-address deliverable (flags do_not_send_without_further_verification).
---
# Contact Enrichment & Deliverability

## What it is / when to use
Given a business row with a website, this extracts every public contact method, grades each on a
**confidence ladder**, and (optionally) closes the loop with a real mailbox check. The ladder:
`candidate-unverified` (0.25, pattern-inferred) → `valid-format` phone (0.72) →
`domain-valid` email (0.78, MX accepts mail) → `publisher-linked` social (0.85) →
`smtp-deliverable` (0.97, off-edge verifier confirmed the mailbox). Use it as the verification stage
between sourcing and outreach in any lead-gen CRM.

**Composes with:** `geo-directory-prospecting` / `open-data-signal-discovery` (source the `businesses`
rows this reads), `decision-maker-email-extractor` (find the right person, then this verifies their
address), `lead-qualifier` + `outbound-compliance-gate` (fit + permission to send — different jobs),
`governed-email-outreach` (send only to `domain-valid`/`smtp-deliverable` contacts). This skill owns
**existence/deliverability grading**; it does not decide fit or consent.

## Reference implementation (ronininc)
- `worker/discovery/enrichment.ts` (whole file, ~350 lines) — confirmed read.
- `worker/discovery/verifier-callback.ts` (55 lines) — the off-edge SMTP callback receiver.
- `worker/discovery/disposable-domains.ts` (33 lines) — compact CC0 blocklist (extend from
  disposable-email-domains/disposable-email-domains).
- Schema: `migrations/0009_business_enrichment.sql`.

⚠️ **Ships DISCONNECTED in the source.** The `enrichment.ts` code, its `BUSINESS_ENRICHMENT` workflow,
`checkEmail`/`triggerEnrichment`/`receiveEmailVerdict` handlers and the `0009` schema all exist and are
type-referenced in `Env` (`types.ts:66,77`), but the workflow is **not** declared in `wrangler.jsonc`,
no cron calls `runEnrichmentTick`, and no `/api/admin/*` route reaches `triggerEnrichment`/`checkEmail`
or a public route reaches `receiveEmailVerdict` (verified by grep across `worker/`). Reapplying this
means shipping its bindings + routes + cron yourself (see step 5). This is the same disconnected Phase
1-3 discovery spine that `index.ts:183-185` describes.

Key spans:
- **HTML harvest** `extractPage()` L111-138: `redirect:'manual'` loop (≤3), 15s timeout, `text/html`
  guard, then `HTMLRewriter` with `AnchorCollector` (L77-96: mailto/tel/social/contact-page anchors) +
  `JsonLdCollector` (L98-109 → `addJsonLd` L61-75: `email`/`telephone`/`sameAs`/Person `name`), plus a
  raw-regex email sweep on the byte-capped body.
- **MX + disposable verdict** `domainVerdict()` L140-175: Cloudflare DoH (`cloudflare-dns.com/dns-query
  ?type=MX`), an MX answer is valid only if `type===15` and not the null `"0 ."` root; result cached in
  `domain_enrichment_cache` for 7 days per `(tenant,domain)`.
- **Deterministic contact id** `contactId()` L177-180: `SHA-256(business|kind|value)` → stable upsert
  key so re-enrichment is idempotent.
- **Save with provenance** `saveContact()` L182-197: stores `source`, `verdict`, `confidence`,
  `detail_json`; `ON CONFLICT(tenant,business,kind,value)` updates in place.
- **Pattern inference (last resort)** `inferredEmails()` L203-210 + L249-254: only when NO verified
  email found and the domain has MX — writes `info@/contact@/hello@/sales@` and `first.last@` at
  confidence **0.25** with `do_not_send_without_further_verification:true`. Never marked deliverable.
- **Phone normalization** L256-262: `libphonenumber-js` `parsePhoneNumberFromString(raw, region)`,
  region inferred `ON→CA else US` (`region()` L199-201), only `isValid()` numbers stored (0.72).
- **Off-edge SMTP callback** `receiveEmailVerdict()` (verifier-callback.ts): a separate service does the
  actual RCPT probe (never from the Worker's shared IPs) and POSTs back; the Worker verifies an
  **HMAC-SHA256** over `timestamp.body` with a **timing-safe** compare (L10-15), rejects a timestamp
  skew >300s (replay guard), then batches an upsert into `email_verification_callbacks` + an UPDATE of
  the matching `business_contacts` to `smtp-<verdict>` (deliverable→0.97, risky→0.45, else 0).

## How to reapply it
1. **Schema.** Copy `0009`: adds `enrichment_status`/`enriched_at` to `businesses`, and creates
   `business_contacts` (confidence CHECK 0..1, UNIQUE(tenant,business,kind,value)),
   `domain_enrichment_cache`, `email_verification_callbacks`. Requires the `businesses` table from the
   discovery spine (`0008`) or your own equivalent with `id,tenant_id,name,website,state`.
2. **Copy the harvesters.** `AnchorCollector` + `JsonLdCollector` + `addJsonLd` are dependency-free
   HTMLRewriter handlers — drop them in. Keep `safeWebsite()` (SSRF guard) and `limitedHtml()` (400 KB
   cap) unchanged.
3. **MX check.** `domainVerdict()` needs only the DoH fetch + your D1 cache table; no key required.
   Ship `disposable-domains.ts` (extend the CC0 list to taste).
4. **Phone.** `npm i libphonenumber-js`; set the region default for the client's country.
5. **WIRE IT (the missing half):**
   - `wrangler.jsonc` → `workflows`: `{ binding:"BUSINESS_ENRICHMENT", class_name:"BusinessEnrichmentWorkflow" }`; `export { BusinessEnrichmentWorkflow }` from the entry.
   - Admin routes: `POST enrichment/trigger → triggerEnrichment`, `POST enrichment/check-email → checkEmail`.
   - Cron: add `runEnrichmentTick(env)` to the `scheduled()` batch (picks 3 `pending` businesses / tick).
   - Optional SMTP verifier: set secret `SMTP_VERIFIER_HMAC_SECRET`, expose a **public** (not admin,
     HMAC-gated) route `POST /api/enrichment/verdict → receiveEmailVerdict`, and stand up the off-edge
     verifier that signs `HMAC(timestamp.body)` and POSTs `{email,verdict,checked_at}`.
6. **Consume the confidence.** Downstream outreach should send only to `verdict IN
   ('domain-valid','smtp-deliverable')` and treat `candidate-unverified` as suppressed.

## Gotchas (from the code + comments)
- **MX ≠ mailbox.** `domain-valid` (0.78) means the domain accepts mail, not that the address exists.
  The comment in `0009` is explicit: "MX proves only that a domain accepts mail; it never becomes a
  fabricated mailbox claim." Only the off-edge SMTP callback earns `deliverable` (0.97).
- **Never send from the edge for verification.** A real RCPT-TO probe from Workers' shared IPs would
  get those IPs blocklisted; that's why the SMTP check is a separate signed service, not inline.
- **Callback security is load-bearing:** timing-safe HMAC compare + a 300s timestamp window (replay
  guard) + a strict verdict allowlist. Don't relax these — the callback mutates contact confidence.
- **Pattern-inferred addresses are a trap:** they exist only to give a human something to verify. They
  carry `do_not_send_without_further_verification` and confidence 0.25 — never promote them to a send.
- **Byte cap + timeouts** (400 KB, 15s, ≤3 redirects) are per-page DoS guards against hostile sites;
  the contact-page follow (L227-233) is best-effort and must not fail the whole enrichment.
- **Disconnected spine:** enrichment only ever runs if you wire step 5 — the reference repo never calls
  it in production. Don't assume it "already works" because the code and types are present.
