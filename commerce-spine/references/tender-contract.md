# Tender contract — the two-mode integration interface

Every integration is EITHER a `PaymentProcessor` (drives tender) OR a `PeerPlatform` (data sync only).
A closed vertical POS (Toast) is always a `PeerPlatform` and never gets a `PaymentProcessor`.

The contract below is the **operator-approved default capability set** (surcharge/cash-discount,
tips, gateway-vault saved-card, partial capture, void, multi-currency-ready, + a first-class refund
lifecycle). Adapters reuse the TSS runtime: `stripe-checkout-adapter.ts`, `storefront-order-store.ts`,
`payment-account-data-boundary.ts`, `capability-readiness.ts`, and `clover-*` connectors.

## PaymentProcessor (driver)

```ts
interface TenderCapabilities {
  cardPresent: boolean;        // false for a website (CNP only) — informational
  tips: boolean;
  surcharge: boolean;          // surcharge / cash-discount adjustment
  vaultSavedCard: boolean;     // gateway tokenized saved-card (token only; never a PAN)
  partialCapture: boolean;
  void: boolean;
  partialRefund: boolean;
  multiCurrency: boolean;
}

interface PaymentProcessor {
  readonly provider: 'stripe' | 'square' | 'authnet' | 'clover';
  readonly capabilities: TenderCapabilities;

  // Honesty gate — real probe, maps to a capability-readiness state. Never assume READY.
  probe(env): Promise<{ state: ReadinessState; verdict: 'ok'|'degraded'|'blocked'|'error' }>;

  // CNP checkout: returns a HOSTED session/redirect. Card data never returns to us.
  createCheckout(order, opts: { tipCents?; surchargeCents?; currency; vaultToken? })
    : Promise<{ gatewayRef: string; hostedUrl: string }>;

  capture(tenderId, amountCents?): Promise<TenderResult>;   // amountCents omitted = full
  void(tenderId): Promise<TenderResult>;

  refund(req: {
    tenderId: string;
    amountCents: number;              // partial when < captured; equals captured = full
    reasonCode: RefundReasonCode;
    reasonNote?: string;              // stored ENC
    actor: string;
  }): Promise<{ gatewayRefundId: string; status: 'processing' }>;

  // Reconciliation source — settled tenders + refund resolutions come back through here / webhooks.
  getSettlement(range): Promise<SettlementRow[]>;
  verifyWebhook(req): boolean;        // constant-time shared-secret / signature check
}

type TenderResult = { status: 'AUTHORIZED'|'CAPTURED'|'VOIDED'|'FAILED'; capturedCents: number };
type RefundReasonCode =
  | 'requested_by_customer' | 'duplicate' | 'fraudulent' | 'item_returned'
  | 'not_as_described' | 'price_adjustment' | 'canceled_order' | 'goodwill' | 'other';
```

### Driver invariants (non-negotiable)
- `createCheckout` returns a **hosted** URL/token; the raw card never touches the node. Every write is
  run through `payment-account-data-boundary.ts`.
- Order `PAID` and refund `succeeded` are written **only** from `verifyWebhook`-passing events, in the
  same transaction that appends the matching event-log row.
- `refund.amountCents` is validated against `orders.captured_cents` minus already-succeeded refunds
  (over-refund guard) **before** the gateway call.
- Unconfigured ⇒ `probe` returns `NOT_CONFIGURED` and the driver is inert (`needs_review`), never faked.
- A sandbox credential can never resolve to a production host (fail-closed env resolver).

## PeerPlatform (sync only — Toast and other closed POS)

```ts
interface PeerPlatform {
  readonly provider: 'toast' /* | other vertical POS */;
  probe(env): Promise<{ state: ReadinessState; verdict }>;

  pullSales(range): Promise<SaleRow[]>;      // decrement master stock + write inventory_ledger
  pullMenu(): Promise<MenuItem[]>;           // seed / reconcile the catalog
  pullGuests(range): Promise<GuestRow[]>;    // feed CRM (customers + customer_events)
  // NO tender methods. Payments stay with the peer platform, untouched, by design.
}
```

### Peer invariants
- Read-mostly. The one write back is a menu push where the platform's partner API allows it — never tender.
- Ingredient/recipe-level deduction: a peer `SaleRow` maps a sold menu item to its recipe and writes
  `inventory_ledger` rows (`reason='recipe_deduct'`) against the underlying stock products.
- Never propose converting the merchant's payments off the peer platform unless the operator asks.

## capability-readiness → wiring decision

| Readiness state (from real probe) | Action |
|---|---|
| `VERIFIED_READ` / `VERIFIED_WRITE_GATED` | wire checkout (driver) / sync (peer) |
| `CONFIGURED_UNVERIFIED` / `VERIFYING` | show "configured, verifying" — do NOT present as live |
| `WRITE_GATED_UNPROVEN` | read/catalog only until write is proven |
| `NOT_CONFIGURED` / `STALE` | Layer-1 only; checkout CTA → ordering / inquiry routing |
