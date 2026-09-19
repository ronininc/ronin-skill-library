---
name: signed-webhook-intake
description: >-
  The house security atom for accepting an inbound webhook from an external provider (Meta/Instagram,
  Shopify, Stripe, a payment or messaging platform) SAFELY on a Cloudflare Worker: bounded body reads,
  HMAC-SHA256 signature verification, a TIMING-SAFE comparison, and an idempotency key so redelivery
  never double-processes. Use WHENEVER a client CRM must receive a POST from a system you do not control —
  "add a webhook", "receive orders/messages/events from X", "verify the signature", "the webhook fires
  twice / is being replayed", "handle the Meta/Shopify/Stripe callback", or any provider-callback endpoint.
  This is a shared PRIMITIVE, not a feature: it is the verification layer UNDER social-dm-inbox (the Meta
  DM webhook) and under any order/payment bridge — compose it, do not re-implement the crypto. It
  COMPLEMENTS outbound-compliance-gate (that governs what you SEND; this governs what you ACCEPT) and
  cf-functions (the routing). Fail-closed is the whole point: no secret configured → 503, bad signature →
  401, oversized body → 413, never trust an unsigned or unverified body.
---
# signed-webhook-intake — verify it before you trust it

Every inbound provider webhook is an unauthenticated POST from the public internet until you prove
otherwise. This atom is the four things you must do before the body is allowed to touch your CRM:
bound the read, verify the HMAC, compare in constant time, and dedupe on an idempotency key. It ships
inside two real handlers in the reference CRM — reuse those, don't hand-roll the crypto per provider.

## What it is / when to use
A copy-in verification wrapper for any `POST /api/.../webhook`. Drop it in whenever a build integrates a
provider that signs its callbacks. It is deliberately tiny and provider-agnostic — the only per-provider
differences are the header name, the encoding (hex vs base64), and the idempotency field.

**Composes with:** it is the front door for **social-dm-inbox** (Meta DM ingestion) and for any
order/payment bridge (e.g. a Shopify `orders/create` ingest). **cf-functions** routes to it;
**append-only-audit-log** can record each accepted event. It does not replace **outbound-compliance-gate**
(opt-outs / send caps) — that is the outbound side.

## Reference implementation (ronininc — read these)
Two provider styles, same four primitives:

- **Meta / Instagram webhook** — `worker/social-messaging.ts:191-212` (`handleMetaWebhook`), with helpers
  `hmacHex` (`:37-40`), `secureEqual` (`:28-35`), and `readBoundedResponse` (`:42-58`). Constants
  `MAX_WEBHOOK_BYTES = 1MB` (`:5`). It also does the GET verification handshake (`hub.mode=subscribe` +
  timing-safe `hub.verify_token` → echo `hub.challenge`) at `:192-197`.
- **Shopify order webhook** — `worker/shopify-ingest.ts:22-32` (`verifyHmac`) and the handler
  `:34-50` (secret check → read raw → verify → idempotency dedupe).
- Field-encryption helpers if the verified body is then stored: `worker/http.ts:195-214`
  (`encField`/`decField`, AES-GCM at rest).

## The four primitives
1. **Bound the read.** Reject on `content-length` over the cap AND re-check `rawBody.length` after reading
   (a lying/absent header must not get past you): `if (length > MAX) return 413`. Read the body ONCE as
   text — you need the exact bytes for the HMAC, so never `await request.json()` first.
2. **HMAC-SHA256 over the raw body.**
   `key = crypto.subtle.importKey('raw', enc(secret), {name:'HMAC',hash:'SHA-256'}, false, ['sign'])`,
   then `sign('HMAC', key, enc(rawBody))`. Meta wants the digest **hex** and sends
   `x-hub-signature-256: sha256=<64 hex>`; Shopify wants **base64** in `x-shopify-hmac-sha256`. Match the
   provider's encoding exactly.
3. **Compare in constant time — two acceptable styles, both in the source:**
   - Hash-then-compare (Meta): SHA-256 each side and feed the equal-length digests to
     `crypto.subtle.timingSafeEqual`. This is the cleanest since `timingSafeEqual` requires equal-length
     inputs, which digests guarantee.
   - Length-check + XOR loop (Shopify): `if (a.length !== b.length) return false;` then
     `for … diff |= a.charCodeAt(i) ^ b.charCodeAt(i); return diff === 0;`.
   Validate shape first where you can (Meta regex-checks `/^sha256=[a-f0-9]{64}$/i` before comparing).
   Never use `a === b` on the signature.
4. **Idempotency key.** Providers redeliver. Dedupe on the provider's own id: either a UNIQUE index +
   `INSERT OR IGNORE` and act only when `result.meta.changes` is truthy (Meta message `mid`), or a
   `SELECT` on a stored external ref before insert and return `{ok:true, duplicate:true}` on a hit
   (Shopify `supplier_order_ref = 'shopify:' + id`). Coerce numeric ids with `String(id)` — Shopify sends
   `id` as a NUMBER and a naive string helper drops it.

## How to reapply it
1. **Secret** — store the provider's signing secret as a Worker secret (`wrangler secret put`); never a var.
   If it's unset, the handler returns **503** and stops. No secret, no trust.
2. **Route** — add the path in your router and run it BEFORE any auth/session gate (the provider has no
   session): `if (path === '/api/x/webhook' && req.method === 'POST') return xWebhook(req, env, ctx)`.
   Keep it OUT of the `/api/admin/*` gated block.
3. **Handler skeleton** — secret-present check → size check → `const raw = await req.text()` → verify HMAC
   → 401 on fail → `JSON.parse(raw)` (400 on throw) → idempotency check → `ctx.waitUntil(process(...))`
   → return `200` immediately (providers retry on slow/non-200; do the CRM work in `waitUntil`).
4. **GET handshake** (subscription webhooks like Meta only) — on GET, timing-safe compare the verify token
   and echo the challenge; 403 otherwise.

## Gotchas (from the code)
- **Read the body as text exactly once.** Parsing to JSON first, or reading twice, consumes the
  bytes and the HMAC will never match.
- **`timingSafeEqual` throws on unequal-length inputs** — that's why the Meta path hashes both sides to
  fixed-length digests first, and the Shopify path guards length before the XOR loop.
- **Numeric provider ids** — `String(o.id)`, not a helper that treats non-strings as empty, or your
  idempotency key silently becomes blank and every redelivery re-processes.
- **Return 200 fast, work in `ctx.waitUntil`.** A provider that doesn't see a quick 2xx retries, which is
  exactly the redelivery your idempotency key must absorb — so both halves matter together.
- **Bound provider RESPONSES too** if you call back out (e.g. to send a reply): stream with a byte cap
  (`readBoundedResponse`) so a hostile/broken provider can't exhaust the Worker.
- Local `wrangler dev` with no secret set will pass bodies unsigned via the 503 branch — verify the
  signed path against the real provider (or a signed fixture), not just locally.
