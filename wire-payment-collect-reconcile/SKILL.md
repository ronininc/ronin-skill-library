---
name: wire-payment-collect-reconcile
description: >-
  Manual settlement-by-wire for a Cloudflare Worker + D1 CRM whose high-ticket deals close by bank
  transfer instead of a card rail: from a proposal, generate a unique human-readable reference code,
  pick a kind (deposit | balance | full) with a sensible default amount and a due window, flip the
  proposal draft→sent, and dedupe so a proposal never accrues two open requests; the operator sends the
  client the reference + encrypted-at-rest wire instructions, verifies the deposit in their own bank,
  marks it received, and receipt RECONCILES the payment and fires onboarding. Use WHENEVER a CRM must
  "invoice by wire / bank transfer", "no card processor", "send wire instructions", "track a deposit
  until it lands", "mark a payment received", "ACH/wire deposit then start work", or "settle a
  high-ticket engagement manually". It COMPLEMENTS commerce-spine (which wires card-not-present checkout
  where a gateway is OPEN — this is the manual-settlement lane commerce-spine does NOT model) and
  services-delivery-lifecycle (receipt calls that skill's `activateOnboarding` to open the project — do
  NOT re-implement onboarding here). Guardrails: money-never-auto — there is NO bank API; "received" is
  the operator's attested verification of a real deposit, gated behind a confirm dialog; the reference
  is UNIQUE; wire instructions are AES-GCM encrypted in settings; a cancelled request can't be received.
---

# wire-payment-collect-reconcile — invoice-by-wire, verify, reconcile, hand off

## What it is / when to use
The settlement layer for deals that pay by bank wire, not card. You turn a proposal into a **wire
request**: a unique reference code, an amount (deposit/balance/full), and a due date. The operator sends
the client that reference plus the firm's wire instructions, watches their bank, and when the funds land
marks it **received** — which reconciles the record and triggers the delivery handoff. There is no
payment processor and no bank connection in the loop; the human is the settlement oracle. Reach for it on
high-ticket services engagements, B2B deals, or any market where "send us a wire" is the norm and a
card rail is absent or undesirable.

**Composes with (do not duplicate):**
- **commerce-spine** — owns the *card* rail (Stripe/Square/Authorize.net/Clover Ecommerce checkout,
  catalog, orders). It does not model a manually-verified bank transfer. This skill is that missing lane;
  run both if a merchant takes cards for products AND wires for engagements.
- **services-delivery-lifecycle** — owns `proposals`, `projects`, and **`activateOnboarding`**.
  `receiveWirePayment` here CALLS `activateOnboarding` to open the project on receipt. Do not rebuild
  onboarding; import and call it. (If you settle by card, that skill's onboarding is fired by your paid
  webhook instead — same hook, different trigger.)

## Reference implementation (ronininc — open and confirm before lifting)
Catalog pointer: `CRM_SKILLS_CATALOG.md` → "wire-payment-collect-reconcile".
All in **`worker/business-apps.ts`** (L223–293):
- **`createWirePayment(req, env, me)` — L223–252.** Loads the proposal+contact; **dedupes** — if a
  `status='pending'` wire already exists for the proposal it returns that one (`existing:true`) instead of
  making a second; picks `kind` from {deposit, balance, full} (default `deposit`); default amount =
  `amount_cents` for `full`, else `deposit_cents || amount_cents`; `due_at = now + wire_due_days*86400`
  (from settings); mints `reference = <PREFIX>-YYYYMMDD-<4 hex upper>`; in one `env.DB.batch` inserts the
  `pending` wire, flips `proposals→'sent'` **only `WHERE status='draft'`**, and logs a `wire-request`
  activity.
- `listWirePayments(env)` — L254–265. Joins proposal+contact, orders pending→received→other; **returns
  the decrypted `wire_instructions`** from settings so the UI can show/copy them.
- **`receiveWirePayment(req, env, me)` — L267–285.** Refuses a `cancelled` record; sets
  `status='received'`, `received_at = COALESCE(received_at, now)` (so a re-mark keeps the original time),
  stores `sender_reference` + encrypted `notes`; then calls `activateOnboarding(env, proposal_id, me.name)`
  and returns the `project_id`. Onboarding failure returns 500 with a message that the wire WAS recorded.
- `cancelWirePayment(req, env)` — L287–293. `pending→'cancelled'` only.
- Settings side: `saveBusinessSettings` (L456–472) clamps `wire_due_days` 1–90 and **`encField`s
  `wire_instructions`**; `getBusinessSettings` decrypts it for the form.
- **`migrations/0013_wire_payments.sql`** — `ALTER business_settings ADD wire_instructions` +
  `wire_due_days`; `CREATE TABLE wire_payments` with `reference TEXT NOT NULL UNIQUE`,
  `amount_cents CHECK (>0)`, `status` deposit-tracking enum, three indexes.
- **Routing:** `worker/admin.ts` **L355–358** — `GET business/payments`, `POST business/payment/wire`,
  `POST business/payment/received`, `POST business/payment/cancel`; behind `crm` in `SUB_SECTION`.
- **UI:** `public/admin/admin.js` **L561–616** — `loadPayments` (copy-wire-details, mark-received behind
  a "verified in your bank?" confirm, cancel) and the Settings form's wire-instructions textarea + due-days.

## How to reapply it
1. **Migration.** Apply `0013` after `0012`: add `wire_instructions` (default `''`) and `wire_due_days`
   (default 7) to `business_settings`, then `CREATE TABLE wire_payments`. Keep `reference … UNIQUE` and
   `amount_cents … CHECK (amount_cents > 0)`.
2. **Create.** Lift `createWirePayment`. Preserve the dedupe (return the existing pending request), the
   kind→default-amount logic, and the batched insert that also flips the proposal to `sent` **guarded on
   `status='draft'`** so it never regresses a paid/sent proposal. Swap the `<PREFIX>` in the reference for
   the client's brand.
3. **List + instructions.** Lift `listWirePayments`; it must decrypt and return `wire_instructions` so the
   operator can copy a complete client-facing message.
4. **Receive = reconcile + hand off.** Lift `receiveWirePayment`. Keep: the `cancelled` guard; the
   `COALESCE(received_at, ?)` idempotent timestamp; encrypted notes; and the call to
   `activateOnboarding(...)` from services-delivery-lifecycle. Return the new `project_id`.
5. **Cancel.** Lift `cancelWirePayment` (pending→cancelled only).
6. **Settings.** Add `wire_instructions` (encrypted) + `wire_due_days` to your business-settings form.
7. **Routes + gate + UI.** Register the four routes behind your CRM clearance and copy `loadPayments`.
   **Keep the confirm dialog** ("Have you verified this wire in the receiving bank account?") on
   mark-received and the bank-reference prompt — that dialog IS the money-never-auto gate.

## Gotchas (from the code)
- **There is no bank API — "received" is a human attestation.** Nothing verifies the deposit
  programmatically; the operator confirms they saw it land, then marks it. The confirm dialog and the
  manual bank-reference are the whole control. Never wire an auto-mark-received off a heuristic; that
  would fabricate settlement and auto-open delivery on unpaid work.
- **Dedupe is per-proposal-per-pending, by query not constraint.** `createWirePayment` returns the
  existing pending wire rather than inserting a second. There's no UNIQUE on `(proposal_id, status)`, so
  two truly-simultaneous creates could still both insert; if that matters under load, add a partial unique
  index. In the normal single-operator flow the query dedupe is sufficient.
- **Receipt records the wire BEFORE onboarding, and does not roll back.** `receiveWirePayment` sets
  `status='received'` first, then calls `activateOnboarding` inside a try/catch. If onboarding throws, the
  wire is already `received` and you get a 500 saying so — the payment is NOT un-received. That ordering
  is deliberate (never lose a recorded payment) but means a failed onboarding needs a manual re-trigger,
  not a re-mark. `activateOnboarding` is idempotent, so re-firing it is safe.
- **`reference` is UNIQUE — a collision throws.** The `<PREFIX>-YYYYMMDD-<4 hex>` format has ~65k codes
  per day; fine at low volume. At high volume widen `randomHex(4)` to avoid an insert failing on the
  unique constraint.
- **Wire instructions are encrypted at rest and only meaningful with a key.** `saveBusinessSettings`
  `encField`s them; `listWirePayments`/`getBusinessSettings` decrypt. With `ENCRYPTION_KEY` unset (dev)
  they pass through in the clear. The UI gates the "copy wire details" button on instructions being
  present — so an operator who hasn't filled them in can't send an incomplete request.
- **`proposal→sent` flip is guarded.** It's `UPDATE proposals SET status='sent' … WHERE status='draft'`,
  so preparing a wire on an already-`sent`/`paid` proposal won't rewind its status. Preserve the guard.
- **Only `pending` is actionable.** Cancel requires `pending`; receive refuses `cancelled`. Keep those
  state guards so a cancelled/received request can't be flipped by a stale button.
