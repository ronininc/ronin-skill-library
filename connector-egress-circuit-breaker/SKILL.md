---
name: connector-egress-circuit-breaker
description: >-
  The fail-closed resilience funnel every outbound third-party WRITE/READ should pass through: a
  per-request TOTAL timeout (AbortSignal.timeout) so a hung or black-holed provider ABORTS and fails
  closed instead of holding a request open forever, PLUS a per-(tenant, provider) CIRCUIT BREAKER that
  trips after N consecutive TRANSPORT-level failures (a thrown network error or a timeout — NEVER a
  provider's own HTTP 4xx/5xx verdict, and NEVER a business/validation refusal), short-circuits further
  writes for a cooldown WITHOUT touching the provider, auto-recovers with a half-open trial, and resets on
  any executed write. It can only ever DEFER a write, never cause one. Use WHENEVER a build sends outbound
  calls to a third-party API that can hang, rate-limit, or flap — "the provider is down / timing out",
  "stop hammering a dead API", "add a circuit breaker / retry budget", "our writes hang forever", "fail
  closed when the vendor is unreachable", or any multi-tenant connector funnel (payments, email/SMS, CRM
  sync, KV/object-store writes). COMPLEMENTS ssrf-safe-egress-transport (that hardens WHERE a request may
  go; this bounds WHEN it may be attempted) and outbound-compliance-gate (that decides IF you may send;
  this decides whether the transport is healthy enough to try). Also composes UNDER clover-connector,
  google-oauth-connector, and any pluggable-* backend as the shared outbound bound.
---

# Connector Egress Circuit Breaker

## What it is / when to use
Two strictly ADDITIVE bounds around the one funnel every outbound provider call passes through, so a
flaky vendor can never hang a request or make you machine-gun a dead endpoint:

1. **Timeout** — cap each provider request with a total deadline. A hung or black-holed provider aborts
   and fails CLOSED after the deadline instead of holding a governed write open indefinitely.
2. **Circuit breaker** — count consecutive TRANSPORT-level failures per `(tenant, provider)`; after a
   threshold the breaker OPENS and short-circuits further calls for a cooldown *without touching the
   provider*, returning a fail-closed result. After the cooldown a half-open trial is allowed; any
   executed call resets it.

Reach for it whenever a build makes outbound calls to something you don't control that can hang or flap:
a payments/refund call, an email/SMS send, a CRM/inventory sync, a KV/object-store write, an MCP tool
call. Especially in a multi-tenant CRM where one tenant's dead provider must not degrade everyone.

The load-bearing rule: **the breaker counts ONLY thrown/timed-out transport errors** — never a
provider's own HTTP verdict (a 404/409/422 is a real answer the caller must see) and never a
business/validation/authorization refusal (a correct outcome, not a fault). Conflating those either
hides real answers or opens the breaker for the wrong reason. The breaker is a pause/cap only: it can
never cause a call to happen, only defer one.

## What it composes with
- **ssrf-safe-egress-transport** — that decides WHERE a request may go; this decides WHEN it may be
  attempted. Use together on any outbound funnel.
- **outbound-compliance-gate** — that decides IF you're legally allowed to send (consent/DNC/hours);
  this is downstream, deciding whether the transport is currently healthy enough to try.
- **clover-connector / google-oauth-connector / pluggable-\* backends** — this is the shared bound they
  all dispatch through, so resilience is defined once, not per connector.

## Reference implementation (TSS-own source)
`TSS/server/src/runtime/connector-transports.ts`:
- Bounds + tunables: `CONNECTOR_TRANSPORT_TIMEOUT_MS` L31, breaker threshold/cooldown L32-33.
- Bounded fetch that never overrides a caller-supplied signal, else caps with `AbortSignal.timeout`:
  `timedFetch` L43-46.
- Breaker state (a `Map` keyed `tenant::adapter`) + queries + record-failure/record-success:
  L48-73 (`connectorBreakerOpen` L53, `connectorBreakerCooldownRemaining` L58,
  `recordConnectorTransportFailure` L62 opens at threshold, `recordConnectorTransportSuccess` L69 resets).
- The funnel: check breaker → if OPEN, return fail-closed with cooldown seconds WITHOUT touching the
  provider (L425-436); else dispatch under a try/catch where ONLY a thrown/timed-out error records a
  failure and an `EXECUTED` result records success (`executeConnectorTransport` L417, dispatch L442-449).
- A test seam to shorten the timeout so the bound is provable without a 30s wait: L37-40; a test-only
  breaker reset L73 — the runtime never calls either.

Proof: `TSS/tests/connector-transport-resilience/run.ts` stubs `globalThis.fetch` per case and asserts:
a hung provider aborts and fails closed; repeated transport failures open the breaker and the next call
never touches fetch; a business refusal is NOT counted; the breaker auto-closes after cooldown.

## How to reapply (in a CLIENT build)
1. Route every outbound provider call through ONE dispatch function (don't scatter raw `fetch`).
2. Wrap the fetch: `fetch(url, { ...init, signal: AbortSignal.timeout(TIMEOUT_MS) })` — but do NOT
   override a signal the caller already supplied.
3. Keep a `Map<"tenant::provider", { failures, openUntil }>`. Before dispatch, if `openUntil > now`,
   return a fail-closed result carrying the cooldown seconds — do not call the provider.
4. Dispatch inside try/catch:
   - thrown error OR timeout → `recordFailure` (increment; open the breaker at the threshold) and return
     a normalized fail-closed result;
   - an executed/successful call → `recordSuccess` (delete the entry);
   - a provider HTTP error or a validation/authorization refusal → pass through UNCHANGED, and do NOT
     touch the breaker.
5. On a Cloudflare Worker the same shape applies with `AbortSignal.timeout`; keep the breaker map in a
   Durable Object (or a D1/KV row) instead of process memory so it is shared across isolates, or accept
   that a per-isolate breaker only protects that isolate.
6. Expose `breakerOpen(tenant, provider)` and `cooldownRemaining(...)` so a readiness/health surface can
   show a provider as cooling-down rather than silently failing.

## Gotchas
- **Never count a provider's HTTP verdict as a breaker fault.** A 4xx/5xx is a real answer; opening the
  breaker on it hides answers the caller must see and can wedge a healthy provider.
- **Never count a business/validation/authorization refusal.** Those are correct outcomes; only
  thrown/timed-out TRANSPORT errors are faults.
- **Key the breaker by tenant AND provider.** A global breaker lets one tenant's dead vendor deny service
  to everyone; a provider-only key does the same across tenants.
- **Process-memory state doesn't survive a restart or span isolates.** Fine for a single Node process;
  on Workers/serverless put it in a Durable Object or a DB row or scope your claims to one isolate.
- **The timeout must be a TOTAL deadline**, not merely a connect timeout — a provider that accepts the
  connection then stalls is the exact hang you're bounding.
- **Half-open trial, not a flood.** After cooldown, let ONE call through to probe; open again on failure,
  reset on success. Don't release the full backlog at once.
- **Fail CLOSED, always.** A breaker-open or timed-out write returns "not sent" — it must never
  optimistically report a write as landed.
