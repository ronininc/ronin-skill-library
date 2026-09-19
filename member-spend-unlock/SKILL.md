---
name: member-spend-unlock
description: >-
  The wholesale/loyalty "spend your way to a tier" engine for a Cloudflare Worker + D1 CRM: an
  APPEND-ONLY, idempotent spend ledger accrues a member's cumulative spend, and a tier unlocks only
  when TWO gates both hold — a staff in-store verification AND cumulative spend ≥ the member's
  threshold (default configurable per member) — so nothing unlocks on money alone. Accrual is
  idempotent by construction: a duplicate POS order id / local order id is silently ignored (a partial
  UNIQUE index), so webhook + poll replays never double-count; the cached `spend_cents` on the member
  is always RECOMPUTED as the SUM of the ledger (the ledger is authoritative, the column is a cache).
  Its sharpest trick is CROSS-CHANNEL crediting: a member who buys on the merchant's public RETAIL
  store — which mints its OWN POS customer id that won't match the stored one — is still credited by
  matching the order's email (case-insensitive) or phone (last 10 digits), and on the first match the
  real POS customer id is BACKFILLED so every future order matches instantly. Use WHENEVER a build has
  "spend $X to unlock wholesale/VIP pricing", "loyalty tier by cumulative spend", "credit their online
  orders toward the threshold too", "auto-upgrade when they hit the number", "idempotent spend ledger",
  or "match a retail order to a member by email/phone". It COMPLEMENTS commerce-spine / crm-build-standard
  (the members + orders spine it rides on), clover-connector (the POS orders that feed accrual), and
  graduated-autonomy-tiers (a different axis — that gates ACTION autonomy; this gates a PRICING tier by
  spend). Guardrails: money is integer cents; the ledger is append-only and authoritative; verification
  and spend are independent gates (both required); an admin override still records WHY.
---
# member-spend-unlock — two-gate tier unlock on an idempotent, cross-channel spend ledger

## What it is / when to use
The engine behind "spend $5k to become wholesale" (or any spend-to-tier program). It keeps an honest,
replay-safe ledger of what a member has spent across every channel and flips their pricing tier only
when they're both verified and over the line. Reach for it on any merchant CRM with a loyalty/wholesale
threshold and orders arriving from more than one place (in-store, portal, public retail store).

## Reference implementation (patterns only, no client data)
All in `worker/lib/members.js`:
- `memberProgress(business)` L23–31 — pure: spend/threshold/remaining/pct/unlocked/verified for display + tests.
- `businessByContact(db, {email, phone})` L50–62 — the cross-channel match: exact lowercased email,
  else phone by LAST 10 DIGITS (formatting-proof); members are few so the phone pass loads them.
- `accrueSpend(db, {businessId, amountCents, source, orderId, cloverOrderId, …})` L84–110 — inserts an
  `member_spend_ledger` row; a UNIQUE-violation on the order id ⇒ `{accrued:false, duplicate:true}`
  (idempotent); then RECOMPUTES `spend_cents` as `SUM(amount_cents)` and calls `maybeUnlock`.
- `maybeUnlock(db, businessId)` L116–125 — the TWO-GATE rule: returns true (and applies the tier) only
  if `verified_in_store` AND `spend_cents ≥ threshold`; `grantWholesale` L128–134 is the audited admin override.
- `verifyMember(db, env, businessId)` L153–183 — sets verified, creates the linked customer at the base
  tier, upserts the member to the POS as a customer, then re-checks unlock.
- `setThreshold` L226–232 — per-member override of the default threshold.
- **Schema:** `member_spend_ledger` + partial UNIQUE indexes in `worker/migrations/0007_member_crm.sql`
  (backing the idempotent accrual).

## How to reapply
1. Migration: `businesses` (with `spend_cents` cache, `wholesale_threshold_cents`, `verified_in_store`,
   `wholesale_unlocked`, `clover_customer_id`) + append-only `member_spend_ledger` with partial UNIQUE
   indexes on `order_id` and the POS order id.
2. Feed `accrueSpend` from every paid-order path (portal checkout, webhook, poll). For a RETAIL order
   whose POS customer id doesn't match, resolve the member via `businessByContact`, accrue, and backfill
   `clover_customer_id` (see `worker/index.js` L1264 `businessByContact` → L1271 accrue).
3. A `CREDIT_RETAIL_MEMBERS` var toggles whether retail orders count (default on).

## Gotchas (from the code)
- The cache column is derived — always recompute it from the ledger SUM after an accrual; never
  increment it in place (that drifts under replays).
- Spend alone must NOT unlock — the in-store verify gate is the anti-abuse half. Keep both checks in
  `maybeUnlock`, not split across call sites.
- Phone matching on the last 10 digits is deliberately lenient for US numbers; email match is exact —
  don't loosen email to substring or you'll cross-credit unrelated members.
