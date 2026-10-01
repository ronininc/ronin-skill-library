---
name: truthful-money-ledger
description: >-
  A TRUTHFUL, tamper-evident money ledger for a Worker+D1 build: a hash-chained, append-only P&L line store
  where REVENUE is written ONLY when a real payment is actually received, COST only when metered / invoiced /
  entered by a human, SIMULATED ("paper") income is NEVER allowed in, corrections are new REVERSING lines
  (nothing is ever edited or deleted), and every write is idempotent on `(source, source_ref, kind)`. The
  chain is `hash = sha256(prev_hash | canonical line)`, the head is defended by a compare-and-insert so two
  writers can never fork it, a `verifyLedger()` recomputes the whole chain and names the first broken line,
  and SQL triggers RAISE(ABORT) on any UPDATE/DELETE. Use WHENEVER a build must report money it can PROVE —
  "a ledger that can't lie", "only count revenue when we're actually paid", "tamper-evident P&L", "append-only
  financial record with a hash chain", "idempotent revenue lines (webhook + poll both fire)", "reverse a
  refund instead of deleting", "keep paper/forecast gains out of the real books", or a per-engine revenue/cost
  rollup. It COMPLEMENTS append-only-audit-log (that logs WHO-DID-WHAT events; this logs MONEY with a hash
  chain and revenue/cost semantics), service-invoice-ledger / prepaid-wallet-ledger (per-job invoices /
  wallet debits — this is the cross-engine truth spine they can book into), and order-pnl-fund-gate-fulfillment
  / money-feed-health-monitor (which compute/aggregate per-order finance — this is the durable immutable line
  of record). Guardrail: a revenue line requires basis `payment_received`; "paper"/simulated P&L must be kept
  in its own non-ledger store and can only ever contribute real METERED COST, never revenue.
---

# Truthful Money Ledger (hash-chained, append-only, revenue-only-on-payment)

## What it is / when to use
One place to record money that is designed so it cannot overstate itself. Every line is `revenue` or `cost`
with a `basis` (`payment_received | invoice | metered | manual | reversal`), the lines form a sha256 hash
chain, the table is append-only at the SQL level, and the write is idempotent on a business key so a webhook
and a poll firing for the same event book exactly one line. Use it as the shared "truth spine" that many
engines write into — a belt floor, a store, an AI-usage meter — whenever the business needs to state money it
can prove, and needs "we were actually paid" to be a hard precondition for revenue.

It COMPLEMENTS, and does not replace: `append-only-audit-log` (event trail, no money), `service-invoice-ledger`
/ `prepaid-wallet-ledger` (invoices/wallets that can book a line here), `order-pnl-fund-gate-fulfillment` and
`money-feed-health-monitor` (per-order P&L + the read-model dashboard over it).

## Reference implementation (exact)
- The line shape + basis vocabulary: `worker/station/ledger.ts:13` (`LedgerBasis`), `:15` (`LedgerLine`).
- The canonical string the hash covers: `worker/station/ledger.ts:32` `canonical()`.
- Append with idempotency + fork-proof head: `worker/station/ledger.ts:36` `appendLedger()` — dedup on
  `(source, source_ref, kind)` (`:38`), then `INSERT OR IGNORE ... WHERE head = prevHash` (`:46-49`) retried
  up to 6×; a lost race re-checks the idempotency key (`:55`).
- Whole-chain verifier: `worker/station/ledger.ts:63` `verifyLedger()` → `{ok, lines, head, broken_at_seq}`.
- Per-belt rollup: `worker/station/ledger.ts:74` `ledgerTotals()` (revenue/cost/net/lines by belt).
- Append-only at the SQL level: `migrations/0150_ronin_station.sql:145` table, `:164-167`
  `BEFORE UPDATE`/`BEFORE DELETE` triggers that `RAISE(ABORT, 'station_ledger is append-only')`.
- A REAL revenue line, booked only on a settled order (+ a refund REVERSAL): `worker/station/asset-packs.ts:460`
  (`basis:'payment_received'`, gated on `status IN (paid,...) AND funded=1`) and `:467` (`basis:'reversal'`,
  negative amount referencing the original).
- A REAL metered-cost line that accrues sub-cent and books whole cents via compare-and-set:
  `worker/station/jev.ts:192` `meterJev()` (idempotent on a cent-range `source_ref`), and
  `worker/station/asset-packs.ts:306` `bookMakeCost()` (Workers-AI + Images list price, rounded UP, one line
  per paid service per make).
- The "paper never enters the ledger" boundary: `worker/station/copy-desk.ts:15` (paper P&L lives in
  `copy_paper_trades`, NOT `station_ledger`); the only real line that belt emits is Jev's metered cost.

## How to reapply
1. **Schema.** `station_ledger(seq INTEGER PK AUTOINCREMENT, id, at, belt_id, item_id, kind, amount_cents,
   currency, basis, source, source_ref, memo, actor, prev_hash, hash)` + the two append-only triggers. Index on
   `(belt_id, seq)`. (`migrations/0150_ronin_station.sql:145`.) `seq` orders the chain; `id` is a public handle.
2. **Append through ONE helper.** `appendLedger(env, line)`:
   - reject a non-integer or zero amount;
   - dedup on `(source, source_ref, kind)` → return the existing line (idempotent, not an error);
   - read the head hash, compute `hash = sha256(prevHash + '|' + canonical(row))`, and
     `INSERT OR IGNORE ... SELECT ... WHERE COALESCE((head),'genesis') = prevHash` — the WHERE clause IS the
     lock, so a concurrent writer that moved the head loses and retries; on a lost race, re-check the key.
3. **THE INVARIANT — revenue is written ONLY on a real payment.** A `kind:'revenue'` line must carry
   `basis:'payment_received'` and be booked from a row that is actually paid+funded (or `invoice` only when a
   real invoice exists). COST is `metered` (from real usage counters, rounded up so it is never understated),
   `invoice`, or `manual` (a human entered it). Mistakes are fixed with a NEW `reversal` line (a negative amount
   referencing the original `source_ref`) — the table is append-only, so nothing is ever edited or deleted.
   Simulated / "paper" / forecast P&L is kept in its OWN table and may contribute only real metered cost here.
4. **Sub-cent costs: accrue in nanos, book whole cents once.** Keep a per-source meter in nano-units; when the
   floored whole-cent total exceeds what's booked, claim the cent range `[booked, due)` with a compare-and-set
   UPDATE, then append one line with `source_ref = '<key>:cents:<booked>-<due>'` — two writers can never book
   the same cents (`jev.ts:197-213`).
5. **Verify + surface.** `verifyLedger()` recomputes the chain and names the first bad `seq`; a health check
   should raise an error when `ok:false` (see `worker/station/shift.ts:152`). `ledgerTotals()` gives per-engine
   revenue/cost/net for a dashboard.

## Gotchas (from the code)
- **Idempotency key is `(source, source_ref, kind)`, not just `source_ref`** — a revenue and a cost line can
  share a ref. Make `source_ref` deterministic from the event (`'<order_id>:<product_id>'`, a cent range),
  never a random id, or dedup silently fails and you double-book.
- **The chain head is compare-and-inserted, not locked** — on D1 there are no transactions across statements,
  so the retry loop is the concurrency story. Keep the 6-attempt loop and the re-check; don't "optimize" it to a
  bare INSERT or two near-simultaneous writes fork the chain.
- **Rounding direction is a truth decision**: cost rounds UP (`Math.max(1, Math.ceil(...))`) so you never claim
  a service was cheaper than it was; the memo states the list price and that a free allocation may cover it.
- **Keep `cloudflare:workers` out of this file** — `ledger.ts` imports only types + `hub` + `http`, so the
  commerce/store bundles that book revenue through it stay bundle-safe.
- **Validated** by `verifyLedger()` in the machine-health check (`shift.ts:152` raises on a broken chain) and
  by the per-belt proofs that assert a revenue line appears only after a funded order.
