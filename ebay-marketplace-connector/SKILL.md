---
name: ebay-marketplace-connector
description: >-
  The turnkey eBay SELL-side connector for a Worker+D1 commerce build — list a CRM product on eBay, reprice it,
  handle best offers, ship and refund orders — the LIST/OUTBOUND sibling of the inbound shopify-order-bridge
  and the clover-connector. Three isolated pieces: (1) OAuth (authorization-code grant) mirroring a Google
  connector — the operator connects their OWN seller account through eBay's consent screen, the encrypted
  refresh token lives in the shared `integrations` table, a short-lived access token is minted per call, and a
  sandbox/production switch lives in settings; it ships INERT until the client id/secret/RuName secrets are set
  and an agent never sees the credentials. (2) PURE pricing math (no I/O, no env, deterministic so proofs pin
  exact outputs): list price for a target margin, a FLOOR = cost + fees + minimum margin that a reprice may
  never cross, a stale-listing step-down repricer, a best-offer accept/counter/decline policy, and a flip
  estimate from the MEDIAN of owner-supplied sold comps (no comps → no estimate, never invented). (3) a GATED
  executor — the list side NEVER calls eBay directly; it only ENQUEUES an action row whose stored payload is
  the EXACT request body, and a separate executor sends it only after a human Approve, re-checking a hard
  per-action money ceiling at approve time; the only auto path is a best-offer AUTO-ACCEPT at/above both the
  threshold and the floor when the owner opted in AND the engine is ON. Use WHENEVER a build must "list on
  eBay", "connect my eBay seller account", "reprice eBay listings", "auto-handle best offers within my floor",
  "ship/refund eBay orders from my CRM", or "source flip candidates with real comps". It COMPLEMENTS
  shopify-order-bridge (inbound webhook: sales INTO the CRM) and clover-connector (POS) as the OUTBOUND
  marketplace leg, commerce-spine (the sovereign catalog it lists from), and governed-mcp-tool-actuator /
  station-engine-floor (the propose → human-approve → execute cage). Guardrail: nothing reaches eBay without a
  human Approve; publishing is a SECOND approval and needs the engine ON; "buy inventory" is never an automated
  spend (approval only acknowledges the decision); never list or reprice below the floor; a money ceiling is
  re-checked at approve time.
---

# eBay Marketplace Connector (OAuth + pure pricing math + gated executor)

## What it is / when to use
The sell-side half of a marketplace integration, built so an agent or a cron can PREPARE listings, reprices
and offer responses but never fire one at eBay without a human Approve. One OAuth module owns the seller
connection, one pure module owns all list-side math (so it's provable), and one gated executor is the only
thing that talks to eBay — and only after approval, re-checking a money ceiling. It is the outbound sibling of
`shopify-order-bridge` (inbound) and `clover-connector` (POS).

Use it to list a sovereign-catalog product on eBay, reprice stale listings toward a floor, auto-handle only
safe best offers, ship/refund from the CRM, or score flip candidates from real comps. Compose with
`commerce-spine` (catalog), `shopify-order-bridge` / `clover-connector` (the other rails), and the
propose→approve→execute cage of `governed-mcp-tool-actuator` / `station-engine-floor`.

## Reference implementation (exact)
- OAuth (authorization-code; refresh token in `integrations`; sandbox/prod switch; inert until secrets set):
  `worker/ebay-oauth.ts:31` `ebayConfigured()`, `:75` `startEbayConnection()` (consent URL + CSRF state), `:91`
  `finishEbayConnection()` (exchange code, re-check the admin is still active, encrypt the refresh token), `:140`
  `getEbayAccessToken()` (mint per-call), scopes `:20`, sandbox/prod endpoints `:43`.
- PURE pricing math (no I/O, deterministic): `worker/ebay-pricing.ts:22` `feesCents`, `:26` `priceForMargin`,
  `:37` `floorCents` / `ceilingCents` / `listPriceCents`, repricer `:46` `repriceDecision()` (step a stale
  listing down toward — never below — the floor; pull an out-of-band price back inside), best-offer policy
  `:63` `bestOfferDecision()` (`auto:true` ONLY for accept ≥ threshold AND ≥ floor), flip estimate `:76`
  `flipEstimate()` (median of owner-supplied sold comps; none → no estimate). Sell-API body builders `:92`
  `buildInventoryItem` / `:104` `buildOffer` / `:122` `buildRespondToBestOffer`.
- The list side only ENQUEUES exact-body actions: `worker/ebay-listing.ts:46` `prepareListing()` (refuses what's
  missing 422, refuses a price below the floor 409, enqueues ONE `create_listing`), `:95` `bestOfferRequest()`
  (pure decision → one gated action; auto-executes only on auto-accept + opt-in + engine ON), flip candidates
  `:123` (`addFlipCandidate` records a proposal; approving it buys NOTHING).
- The GATED executor (the only thing that calls eBay): `worker/ebay.ts` — `enqueue`/`executeGated`/`decideAction`;
  the hard money ceiling re-checked at approve time `worker/ebay.ts:215`; `create_listing` creates an
  UNPUBLISHED offer (publish is a separate gated action) `worker/ebay.ts` (the `create_listing` case); `buy_inventory`
  only ACKNOWLEDGES — never an automated spend (that case in `ebay.ts`).
- Wiring: routes `worker/admin.ts:657-671` (dashboard/settings/actions/queue/decide/listing-prepare/best-offer/
  flip) + `:680-682` (OAuth status/start/disconnect). Migrations `0103_ebay.sql`, `0131_ebay_listing_flip.sql`.

## How to reapply
1. **Isolate the connection.** One OAuth module, mirroring your other provider connectors, stores the encrypted
   refresh token in a shared `integrations` row keyed by provider; a one-time hashed CSRF `state` row carries
   the consent round-trip; a short-lived access token is minted per call. Ship INERT until `CLIENT_ID /
   CLIENT_SECRET / REDIRECT(RuName) / ENCRYPTION_KEY` are set. The operator consents in eBay's own screen; an
   agent never sees or enters credentials. Keep a `settings.environment` sandbox/prod switch.
2. **Put ALL list-side math in a pure, env-free module** so proofs can pin exact cents. Fees = `fee_pct% + fixed`.
   `floor = cost + fees + minimum-margin` is the line nothing may cross. The repricer only steps a STALE listing
   down toward the floor and pulls an out-of-band price back inside `[floor, ceiling]`. The best-offer policy
   returns `accept|counter|decline` and marks `auto:true` ONLY for an accept at/above both the threshold and the
   floor. A flip estimate is the median of owner-supplied sold comps — no comps, no estimate.
3. **THE INVARIANT — nothing reaches eBay without a human Approve.** The prepare functions NEVER call eBay; they
   build the exact request body, refuse what's missing (422) or a price below the floor (409), and ENQUEUE one
   pending action whose payload IS the body. A separate executor sends it only on Approve, and re-checks a hard
   per-action money ceiling AT approve time (not just at enqueue). Publishing a created (unpublished) offer is a
   SECOND gated action and needs the engine ON. "Buy inventory" is never automated — approval only acknowledges
   the decision; the operator completes the purchase. The one auto path is a best-offer auto-accept, and only
   when it is an auto-accept AND the owner opted in AND the engine is ON.
4. **Record flip candidates as proposals, not purchases** — approving one records a decision and buys nothing.
5. **Dedup the queue** (an action with the same ref is not re-enqueued) so a retry can't double-list.

## Gotchas (from the code)
- **Dual API surface.** Listings/offers/ship/refund are the Sell REST APIs; best offers are NOT on REST, so
  responding uses the Trading API `RespondToBestOffer` XML (`ebay-pricing.ts:122`, executed via `tradingCall`).
  Budget for both auth/content types.
- **`priceForMargin` walks up from just under the closed form** because fee rounding makes the exact minimum
  differ by a few cents — don't replace it with the analytic formula or you'll occasionally list a cent under
  the intended margin (`ebay-pricing.ts:31`).
- **The money ceiling is re-checked at APPROVE time, not just enqueue** (`ebay.ts:215`) — a stale queued action
  can't slip past a lowered ceiling.
- **`create_listing` makes an UNPUBLISHED offer on purpose**; publishing is deliberately a separate approval, so
  "prepared" never means "live" (`ebay.ts` create_listing case + `ebay-listing.ts:88` note).
- **The callback re-verifies the initiating user is still an active admin** before accepting tokens, and refuses
  if credential encryption is unavailable (`ebay-oauth.ts:104,128`) — a revoked admin can't complete a connect.
- **Validated** by the deterministic pricing proofs (pure functions pin exact cents) and commit "Cash flow: ...
  wholesale disposition + eBay listing (#38)"; assert floor-refusal, auto-accept-only-when-opted-in, and the
  enqueue-not-call behavior.
