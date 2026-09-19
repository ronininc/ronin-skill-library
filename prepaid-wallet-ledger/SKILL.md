---
name: prepaid-wallet-ledger
description: >-
  A prepaid balance WALLET for a Cloudflare Worker + D1 account, with a RACE-SAFE atomic debit and optional
  auto-reload — the money engine behind per-unit billing (per lead, per credit, per seat, per API call). The
  debit is a single `UPDATE ... SET balance = balance - ? WHERE id = ? AND balance >= ? RETURNING balance`:
  that one statement IS the lock, so two concurrent charges can never both push a balance below zero (no
  read-modify-write on a stale in-memory number). If the balance is short it runs ONE auto-reload through a
  processor-agnostic charge adapter (Stripe/Clover/manual/mock, each fail-closed until keys are set), credits
  the wallet, and re-attempts the same atomic debit. Three billing modes — prepaid (debit now), metered
  (accrue for a later invoice), manual (record only) — and every movement is written to a signed ledger with
  the running balance. Use WHENEVER a build charges a partner/customer per unit against a balance they top up
  — "prepaid credits", "wallet balance", "charge per lead/credit/seat", "top-up + auto-reload", "debit their
  balance", "don't let concurrent charges overdraw", "usage billing against a deposit". It COMPLEMENTS
  wire-payment-collect-reconcile (manual wire settlement — this is the automatic prepaid rail),
  order-pnl-fund-gate-fulfillment (per-order P&L — this is per-unit wallet debit), commerce-spine (agnostic
  card-not-present checkout — this reuses that agnostic-processor idea for the RELOAD charge), and
  lead-marketplace-auto-match (its charge-on-match caller). money-never-auto: a reload is a real card charge.
---
# Prepaid Wallet Ledger (race-safe atomic debit + auto-reload)

## What it is / when to use / what it composes with
The balance-and-ledger engine for per-unit billing. The one non-obvious thing it gets right is a **debit that
is safe under concurrency without a transaction or lock table** — the conditional `UPDATE ... RETURNING` is
atomic in D1/SQLite, so it doubles as the guard. Reuse it any time you bill against a balance a customer funds.

- **Composes with**: `lead-marketplace-auto-match` (calls `settleMatchCharge` on delivery),
  `wire-payment-collect-reconcile` (manual-wire lane — orthogonal money rail), `order-pnl-fund-gate-fulfillment`
  (per-order finance — this is per-unit), `commerce-spine` (the agnostic-tender idea, applied to the reload
  charge), `append-only-audit-log`, and `money-feed-health-monitor` (can aggregate the ledger).

## Reference implementation (exact source)
- Billing engine: `/Users/robbiebrown/Projects/case-plug/src/billing.js` (`settleMatchCharge`, 80 lines).
  - **Atomic conditional debit as the lock** (`UPDATE ... WHERE balance_cents >= ? RETURNING balance_cents`,
    `.first()` returns post-debit balance or null): `billing.js:43-50`.
  - One auto-reload → credit → re-attempt debit: `billing.js:51-75`.
  - Modes (prepaid/metered/manual): `billing.js:32-41,77-79`.
  - Signed ledger write helper: `billing.js:15-20`.
- Processor-agnostic charge adapters (interface `charge({amountCents,customerRef,description,idempotencyKey})
  -> {ok,txnRef}`; manual/mock/stripe/clover; `getProcessor`; each **fails closed** without keys):
  `/Users/robbiebrown/Projects/case-plug/src/processors.js` (whole file).
- Schema: `wallet_ledger` (signed `amount_cents`, `balance_after_cents`, `type` CHECK, `processor_txn_ref`)
  `schema.sql:150-163`; wallet columns on the account row (`balance_cents`, `auto_reload_threshold_cents`,
  `auto_reload_amount_cents`, `processor`, `processor_ref`, `billing_mode` CHECK) `schema.sql:45-53`.

## How to reapply
1. **Schema**: on the billable account add `balance_cents`, `billing_mode CHECK IN ('prepaid','metered','manual')`,
   `auto_reload_amount_cents`, `processor`, `processor_ref`. Add a `wallet_ledger(account_id, type CHECK IN
   ('debit_lead','reload','adjustment','invoice_charge','refund'), amount_cents /*signed*/, balance_after_cents,
   ref_id, processor, processor_txn_ref, created_at)` indexed by account.
2. **The debit**: never `SELECT balance` then `UPDATE`. Use the single conditional-update-returning; a `null`
   result means "insufficient at this instant" — that's your signal to reload, not to retry blindly.
3. **Auto-reload once**: on a null debit, if a reload amount is set, charge it through the processor adapter
   with an **idempotency key derived from account+unit** (e.g. `reload-<account>-<unit_id>`) so a retried
   settle can't double-charge; on success credit the wallet (another `UPDATE ... RETURNING`), ledger the
   reload, then re-attempt the SAME atomic debit. If still short → `insufficient_balance`, do not deliver.
4. **Processor seam**: one `charge()` interface, `getProcessor(name, env)` factory, adapters fail closed with
   `{ok:false,'<name>_not_configured'}` until secrets exist; inject `env.__processors` in tests. (For
   card-not-present *checkout* at a storefront, use `commerce-spine`; this seam is just the server-side charge.)
5. **Ledger every movement** with the post-movement balance, so the ledger alone reconstructs the balance.

## Gotchas (from the code)
- **The conditional UPDATE is the concurrency control.** A read-modify-write (`SELECT` then `UPDATE balance =
  :computed`) races: two matches read the same balance and both debit past zero. `billing.js:46-48` avoids it
  entirely — the DB decides atomically whether there's enough.
- **Reload exactly once per settle attempt.** Loop-reloading on repeated shortfalls can drain a card; the
  reference reloads once then gives up with `insufficient_balance`.
- **Idempotency key on the reload charge** prevents a double top-up when the caller retries the whole settle.
- **Modes change the return contract.** `metered` accrues (invoice later), `manual` only records — callers must
  branch on `bill.mode`, not assume money moved.
- **Stripe/Clover adapters are authored but dormant** until their secrets are set (they return
  `*_not_configured`), and verified against the live API at deploy — do not assume a live rail in tests; the
  manual + mock adapters are the fully-exercised ones.
- **Store money in integer cents**; signed `amount_cents` in the ledger (debit negative, credit positive).
