---
name: printable-invoice-document
description: >-
  Turn an order into a numbered, self-contained, PRINT/PDF-ready invoice DOCUMENT on a Cloudflare
  Worker + D1 build. Three distinct primitives: (1) RACE-SAFE, gap-free sequential numbering via a
  single `UPDATE counters SET value = value + 1 … RETURNING value` (the one statement IS the lock — no
  read-then-write race, no duplicate numbers under concurrency) formatted like `INV-000123`; (2) a
  DUAL-SOURCE line SNAPSHOT — the invoice copies its own line items so it renders IDENTICALLY whether
  it was built from a LOCAL order (your `order_lines`) or a POS/Clover online order (`lineItems`
  elements, unitQty in thousandths), and it preserves the REAL historical sale date on a backfill
  instead of the import time — and it is idempotent (one invoice per order id / POS order id); (3) a
  branded, fully self-contained printable HTML (inline styles, `@media print` rules, `@page` margins,
  a one-tap Print button, optional `?auto=1` auto-print for a "generate PDF" flow, and a conditional
  "Pay online" button when a pay link exists). Use WHENEVER a build needs "a printable invoice /
  receipt", "generate a PDF invoice", "give it an invoice number", "sequential order/invoice/ticket
  numbers with no gaps or races", "an invoice from a POS order", "a print-ready document", or "email
  a receipt that renders in any client". It COMPLEMENTS service-invoice-ledger (which owns the
  per-job payment SCHEDULE + append-only PAYMENTS ledger + public pay page — THIS owns the numbered
  DOCUMENT + its printable render + POS-order sourcing; use that for collection, this for the artifact),
  commerce-spine / clover-connector (the orders it renders), and send-once-idempotent-email (which
  mails the receipt). Guardrails: money is INTEGER CENTS; the number counter is the ONLY correct way
  to avoid races (never `SELECT max+1`); snapshot the lines at issue time (don't re-derive from a
  mutable order later); the HTML must be self-contained (no external CSS/JS) so it prints anywhere.
---
# printable-invoice-document — atomic numbering + dual-source snapshot + print/PDF-ready HTML

## What it is / when to use
The document side of invoicing: give an order a gap-free number, freeze its lines into a record, and
render a branded page a human can print or save as PDF (or that emails cleanly). It deliberately does
NOT own money collection — pair it with service-invoice-ledger (schedules + payments + pay page) for
that. Reach for it whenever the deliverable is the invoice/receipt ARTIFACT itself, especially when
the source order can come from either your own DB or a POS.

## Reference implementation (patterns only, no client data)
All in `worker/lib/invoices.js`:
- `nextInvoiceNumber(db)` L16–20 — **race-safe numbering**: `UPDATE counters SET value = value + 1
  WHERE name='invoice' RETURNING value`, zero-padded. The single statement is the lock; no SELECT-max.
- `createInvoiceForLocalOrder(db, order, business, …)` L52–76 — idempotent on `order_id`; snapshots
  `order_lines` into `invoice_lines` (name, qty_text, unit + line cents).
- `createInvoiceFromCloverOrder(db, cloverOrder, business, …)` L79–108 — idempotent on `clover_order_id`;
  maps POS `lineItems.elements` (unitQty/1000 → qty_text) into the SAME `invoice_lines` shape, and
  preserves the real sale date (`issued_at` from the POS order's `createdTime`) for historical backfill.
- `insertInvoice` L29–49 — writes the invoice header + snapshotted lines in order (`sort_order`).
- `setInvoiceStatus(db, id, status)` L130–135 — `issued|paid|void`, stamps `paid_at`.
- `renderInvoiceHTML({invoice, lines})` L140–220 — self-contained branded HTML: `:root` tokens,
  `@media print` + `@page` rules L177–184, a `noprint` Print button, an optional "Pay online" button
  when `invoice.pay_url` + status `issued` L212–215, and an auto-print script on `?auto=1` L218
  (the "make me a PDF" hook).
- **Schema:** `counters` + `invoices` + `invoice_lines` in `worker/migrations/0008_invoices.sql`;
  `pay_url` added in `worker/migrations/0018_invoice_paylink.sql`.

## How to reapply
1. Migration: a `counters(name, value)` row per sequence; `invoices` (with `subtotal/discount/tax/total`
   cents, `status`, `source`, `issued_at`, a unique index on `order_id` and on the POS order id for
   idempotency) + `invoice_lines`.
2. Create path: resolve/snapshot lines from whichever order source, `nextInvoiceNumber`, insert once
   (catch the UNIQUE violation → return the existing invoice).
3. Serve path: `GET /invoice/<n>` → `renderInvoiceHTML`; a `?auto=1` variant for a print-to-PDF capture;
   hand the pay link (e.g. from clover-connector's Hosted Checkout) in as `pay_url`.

## Gotchas (from the code)
- NEVER number with `SELECT MAX(n)+1` — two concurrent issues collide. The `UPDATE … RETURNING` counter
  is the correct atomic primitive (reuse it for order numbers, tickets, POs — any gap-free sequence).
- Snapshot the lines at issue time; the invoice must render the same later even if the source order or
  its prices change. Idempotency keys (order id / POS order id) stop replays making duplicate invoices.
- Keep the HTML self-contained (inline CSS, no external JS/fonts) or it won't render in email clients or
  print reliably. `@page` margins + `break-inside: avoid` on rows keep multi-page invoices clean.
- POS line prices arrive as integer cents with `unitQty` in thousandths — convert consistently
  (`price * unitQty / 1000`) so the printed total matches what the POS collected.
