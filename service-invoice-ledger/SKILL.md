---
name: service-invoice-ledger
description: >-
  Per-JOB customer invoicing for a service/contractor CRM on a Cloudflare Worker + D1: an invoice hung
  off a job with line items (service | material | custom, fractional quantities, server-computed integer
  cents), tax in basis points, a payment SCHEDULE (full | split | financing — deposit/progress/final
  milestones), an APPEND-ONLY payments ledger that captures how/when/by-whom real money was collected
  (cash/check/Zelle/etc.) INCLUDING partials, a single-source-of-truth "how much is paid" calc that
  rolls status draft→partial→paid without ever double-counting, and a PUBLIC view-only pay page reached
  by an unguessable per-invoice token. Use WHENEVER a build must "invoice a customer for a job", "line
  items + tax + a deposit/progress/final schedule", "record a cash/check payment", "track partial
  payments toward a balance", "a pay link the customer can open", "mark an invoice paid", or "what's the
  balance on this job". It COMPLEMENTS commerce-spine (that is card-not-present CHECKOUT over a
  product catalog — this is a SERVICE invoice with labor/material lines + a manual-collection ledger),
  wire-payment-collect-reconcile (proposal-level wire settlement — this is job-level line-item
  invoicing), clover-connector / clover-operations-command (the optional hosted card link), and
  append-only-audit-log (payments are an append-only ledger). Guardrail: money is INTEGER CENTS
  everywhere (no float), amounts are computed server-side (the client total is display-only, never
  trusted), and the public token is view-only — it can never move money.
---
# Service Invoice Ledger

## What it is / when to use / what it composes with
The customer-billing side of a job: line items + tax + a payment schedule + an append-only
money-received ledger + a public tokenized pay page. It sits beside a crew job (see
**crew-job-scheduler**) and PII is encrypted via **field-encryption-at-rest**. It is the service-invoice
lane that **commerce-spine** (product checkout) and **wire-payment-collect-reconcile** (proposal wire)
do not model; a Clover hosted link (**clover-connector**) can settle it in Phase 2.

## Reference implementation — exact source
- **Schema** (`worker/migrations/`): `0005_invoicing.sql` (`job_invoices` 1:1 with a job, `job_line_items`,
  `invoice_schedule`), `0006_invoice_tax_token.sql` (tax bps + `access_token`), `0009_manual_payments.sql`
  (the `invoice_payments` append-only ledger), `0015_payout_cents.sql`.
- **Handlers** (`worker/index.js`): invoice-build block inside `createJob` (`:1579-1656`),
  `invoicePaidCents` (`:1674`, the single source of truth), `recomputeInvoiceStatus` (`:1686`),
  `recordPayment` (`:1708`), `listPayments` (`:1772`), `getInvoice` (`:1785`), `getPayInvoice` (`:1810`,
  public), `updateInvoice` (`:1839`).

## How to reapply
- **Three-table model (`0005`):** `job_invoices` holds the rolled-up state (subtotal/tax/total cents,
  `payment_type`, `status`, encrypted customer PII, `access_token`); `job_line_items` holds
  service/material/custom lines (`quantity` REAL so 2.5 tons works, `amount_cents = round(qty*unit)`);
  `invoice_schedule` is the PLAN (one row for `full`, or deposit/progress/final rows for split/financing).
  `invoice_payments` (`0009`) is the ACTUALS — an append-only ledger with method/reference/received_at/
  recorded_by, plus a partial UNIQUE index on `clover_payment_id` for idempotent card ingestion later.
- **Compute money server-side (`createJob` invoice block):** clamp quantity/unit/count to `MAX_*`, tax =
  `round(taxableBase * tax_rate_bps / 10000)` (bps, capped at 3000 = 30%), total computed here —
  the client-sent total is never trusted. Mint `access_token = randomHex(24)`. Encrypt customer
  name/email/phone/financing with `encField` up front (batch can't hold promises). It all rides the
  one `env.DB.batch` with the shift + assignments (see crew-job-scheduler).
- **The single source of truth for "paid" (`invoicePaidCents`, `:1674`):** paid =
  `SUM(invoice_payments.amount_cents)` **plus** any `invoice_schedule` row marked `paid` that has NO
  ledger row behind it (a legacy "mark paid" click or the Clover webhook) — the `id NOT IN (SELECT
  schedule_id FROM invoice_payments …)` guard is what stops double-counting. `recomputeInvoiceStatus`
  reads it: `paid >= total > 0` → `paid`, `paid > 0` → `partial`, else `draft`. EVERY money mutation
  (`recordPayment`, `updateInvoice`, mark-paid) calls this one function so status can never drift.
- **Record a real payment (`recordPayment`, `:1708`):** money-role gate; validate amount is a positive
  bounded integer cents; method against a fixed enum; append a ledger row; settle either the named
  `schedule_id` or the OLDEST still-due rows in order until the money is consumed; then recompute; then
  `notifyStore` a heads-up (no-ops until email is configured). Balance = `total − invoicePaidCents`, so
  cumulative partials just work.
- **Public pay page (`getPayInvoice`, `:1810`):** no auth — the unguessable token IS the key. Return a
  CUSTOMER-SAFE shape only (business name, job title, line items, schedule, totals, balance, status,
  optional Clover pay_url) — no ids, no crew, no other jobs, and it can never move money.
- **Wiring:** the write RPCs sit behind the auth middleware and `canMoney` (rank ≥ 30); the public
  `getPayInvoice` is an unauthenticated GET keyed by `?token=`.

## Gotchas
- **Integer cents ONLY.** `0015` migrated crew payouts off a float `amount` column precisely because
  float money is imprecise and couldn't be bounds-checked; mirror invoices + Clover with `amount_cents`.
- **Never double-count a settled schedule row** — the `NOT IN` guard in `invoicePaidCents` is load-bearing
  once both a "mark paid" click and a ledger payment can touch the same row.
- The Clover columns (`clover_invoice_id`/`clover_pay_url`/`clover_payment_id`) are Phase-2 placeholders;
  wire them through **clover-connector**, don't invent a second money path here.
- Keep the append-only discipline: never add an UPDATE/DELETE route to `invoice_payments` — correct a
  mistake with a compensating negative-or-reversal row, same spirit as append-only-audit-log.
