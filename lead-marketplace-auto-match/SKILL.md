---
name: lead-marketplace-auto-match
description: >-
  The PUSH side of a two-sided lead marketplace: the instant a lead qualifies, auto-match it to the best
  eligible BUYER and charge on delivery. Matching is state x case-type x capacity with a hard eligibility
  gate (buyer must be 'accepting' AND have a fee agreement on file), ranked by price, LIMIT 1; the winning
  price is SNAPSHOTTED onto the match row; billing settles at match time; and an atomic deliver-commit flips
  match->billable/delivered + lead->matched + audit together so there is never a window where the lead reads
  "matched" but the match is still "offered". If no buyer covers the lead, or billing fails, it degrades to a
  staff WORKLIST (owner + next-action) and fires an alert instead of dropping the lead. Use WHENEVER a build
  ROUTES/SELLS/DISTRIBUTES a lead to a partner, buyer, vendor, rep, or branch on capture -- "auto-assign the
  lead", "route to the right partner", "sell leads to attorneys/agents/contractors", "charge per delivered
  lead", "round-robin by coverage area", "lead distribution/marketplace", "ping-post". It COMPLEMENTS
  lead-qualifier (which decides IF a lead is worth keeping -- this decides WHO gets it), crm-build-standard
  (the record store), tcpa-consent-capture (the consent basis it requires), prepaid-wallet-ledger (the
  charge-on-match money path it calls), and dormant-event-alert-router (the unmatched/matched alerts). For
  the PULL model (buyers browse + claim) see exclusive-lead-claim-desk.
---
# Lead Marketplace Auto-Match (push route + charge-on-delivery)

## What it is / when to use / what it composes with
A capture-time router that turns a qualified lead into a delivered, billed match — the sell-side engine of a
lead marketplace. Any business that resells or distributes leads to partners on a per-lead basis needs this
exact flow: eligible-buyer match → snapshot price → settle charge → atomic deliver → else worklist.

- **Composes with**: `tcpa-consent-capture` (must have run — the match query requires consent), `prepaid-wallet-ledger`
  (`settleMatchCharge` is the money path), `dormant-event-alert-router` (matched/unmatched alerts),
  `append-only-audit-log`, and `crm-build-standard` (the staff desk/worklist that works the fallback).
- **Two distribution models, pick per build**: this (PUSH: system assigns + charges on delivery) vs
  `exclusive-lead-claim-desk` (PULL: buyers browse masked leads and claim). Case Plug runs both against the
  same tables.

## Reference implementation (exact source)
- Auto-match + charge + deliver: `/Users/robbiebrown/Projects/case-plug/src/index.js:162-207`.
  - Eligibility + ranking query (coverage `LIKE`, `capacity='accepting'`, `fee_agreement_on_file=1`, order by
    price DESC, LIMIT 1): `index.js:162-170`.
  - No-buyer fallback → worklist + alert: `index.js:172-176`.
  - Create match with **price snapshot**: `index.js:178-182`.
  - Settle charge, and on failure re-open the lead as `qualified_unmatched`: `index.js:184-191`.
  - **Atomic deliver-commit** (`batch`: match→billable/delivered, lead→matched, audit): `index.js:193-200`.
- Staff worklist (qualified + no delivered match, with owner + next_action): `index.js:270-285`.
- Schema: `matches(lead_id, attorney_id, status, price_cents, delivered)` `schema.sql:117-130`;
  buyer table with coverage JSON + capacity + fee-agreement + billing columns `schema.sql:30-55`;
  match index on `(attorney_id, status)` `schema.sql:129`.

## How to reapply
1. **Buyer schema**: a partners/buyers table with `states_covered TEXT DEFAULT '[]'`, `case_types TEXT DEFAULT '[]'`
   (JSON arrays used as matching keys), `capacity CHECK IN ('accepting','paused','full')`, an eligibility flag
   (`fee_agreement_on_file`), `per_lead_price_cents`, plus the billing columns from `prepaid-wallet-ledger`.
2. **Match table**: snapshot `price_cents` at match time (never read the live buyer price when billing later —
   the buyer may have changed it). `delivered` is a separate 0/1 from `status`.
3. **The match query**: gate on `capacity='accepting' AND fee_agreement_on_file=1`, filter coverage with
   `states_covered LIKE '%"XX"%' AND case_types LIKE '%"yy"%'` (quotes around the token so a substring can't
   partial-match), order by your priority (price DESC here; swap for round-robin/last-assigned for fairness),
   `LIMIT 1`. **Sanitize state/case_type first** (see tcpa-consent-capture) so the LIKE can't be wildcarded.
4. **Charge, then deliver atomically**: call the wallet settle; only on `ok:true` run the deliver `batch`.
   On billing failure, set the match `payment_failed`, roll the lead back to `qualified`, alert staff.
5. **Fallback is a feature**: a consented, qualified, unmatched lead lands on a worklist with an owner and a
   next action — never silently lost. Fire an alert so a human works it.

## Gotchas (from the code)
- **Snapshot the price onto the match.** Billing later reads the snapshot, not the buyer's current price.
- **The deliver-commit must be one `batch`.** Two separate UPDATEs leave an interruptible window where a
  reader sees a matched lead with an un-delivered match (or vice-versa). `index.js:193-200` commits all three together.
- **Match only fee-agreement-on-file, accepting buyers.** The eligibility gate is in the SQL WHERE, not in app
  logic you might forget — an ineligible buyer must be *unselectable*, not merely "shouldn't be picked".
- **Billing failure ≠ lead loss.** Re-open as `qualified_unmatched` and alert; don't leave the lead `matched`
  against a match that never got paid.
- **Order-by is your fairness policy.** `price DESC` maximizes revenue but starves cheaper buyers; switch to
  round-robin / least-recently-assigned when partners expect even flow (add a `last_assigned_at` column).
- **Single-tenant today.** `schema.sql:4-6` warns: add `tenant_id` + globally-unique ids BEFORE white-labeling
  or D1 shard-overflow — per-DB `INTEGER AUTOINCREMENT` roots collide across shards.
