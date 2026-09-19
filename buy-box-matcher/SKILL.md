---
name: buy-box-matcher
description: >-
  A saved-criteria registry + idempotent matcher for any CRM that distributes an item to whichever
  subscribers said "this is what I want." Each subscriber (cash buyer, investor, hiring manager,
  wholesale customer) has a "buy-box" of simple filters — cities, max price, min beds/size, allowed
  types, active/paused — and the matcher scores each ACTIVE buy-box against a given item, treating an
  empty criterion as a wildcard, and records every match as a UNIQUE-guarded pair advanceable through
  matched→sent→interested→passed. Use WHENEVER a build needs "match a deal/listing/item to buyers",
  "who wants this", "saved search criteria", "buy-box", "notify subscribers whose criteria fit",
  "distribute a deal to my cash-buyer list", or "record which buyers a deal was matched to." This is
  the reusable MATCH + pairing atom EXTRACTED from a wholesale real-estate disposition step; it
  COMPLEMENTS az-cash-buyer-finder (which SOURCES/BUILDS the buyer list — this does not scrape or
  rank buyers) and wholesale-real-estate (the vertical pipeline that feeds it a deal), and it feeds a
  send step (governed-email-outreach / text-campaign-platform) — the matcher RECORDS the pairing, it
  does not send. Capture only the saved-criteria + idempotent-pairing delta, not the RE pipeline or
  the buyer-sourcing. Guardrails: null/empty criterion = matches all (document it), INSERT OR IGNORE
  + a UNIQUE(item,subscriber) index makes re-running safe, and matching ≠ contacting.
---

# Buy-Box Matcher

## What it is / when to use
A generic "saved search + match + record" primitive: subscribers register a small set of criteria,
and given any item you find every active subscriber whose box fits and idempotently record the
pairings so a downstream step can act on them. Reach for it whenever the CRM broadcasts an item to a
self-selected audience: cash buyers for a wholesale deal, investors for a listing, candidates for a
role, wholesale customers for a SKU.

**Composes with:** `az-cash-buyer-finder` (builds/ranks the buyer list from public records — this
matcher consumes that roster, it does not source it); `wholesale-real-estate` (the disposition step
that calls it); `confirmed-inputs-decision-gate` (upstream — the item's price should be a confirmed
number before you match on it); `governed-email-outreach` / `text-campaign-platform` (the send step
the recorded matches feed). The matcher's job ends at recording the pair.

## Reference implementation (ronininc CRM — OPEN before lifting)
Cloudflare Worker + D1, `worker/acquisitions.ts` (cash-buyer disposition):
- **The matcher** — `matchBuyers` L149-166. Pulls `cash_buyers WHERE status='active'`, and for each
  buyer evaluates four criteria where **absent/empty = wildcard**:
  - `cityOk` L156 — buyer's comma-separated `cities` split/trimmed; matches if any entry is a
    substring of the item's city (or the buyer has no city filter, or the item has no city).
  - `priceOk` L157 — `!max_price_cents || price <= max_price_cents`.
  - `bedsOk` L158 — `!min_beds || (item.beds != null && item.beds >= min_beds)`.
  - `typeOk` L159 — buyer's comma-separated `property_types` contains the item's type (or no filter).
  - On all-true: `INSERT OR IGNORE INTO re_deal_buyers (…, 'matched', …)` and count via
    `r.meta.changes` (L161-162) → idempotent, re-run-safe.
- **The registry CRUD** — `saveBuyer` L200-215: create/update a buy-box (name, contact, `cities`,
  `max_price_cents`, `min_beds`, `property_types`, `status` active|paused).
- **Schema** — `migrations/0028_acquisitions.sql` L47-70:
  - `cash_buyers` L47-60 — the buy-box columns: `cities` (comma-sep), `max_price_cents`, `min_beds`,
    `property_types` (comma-sep), `status CHECK IN ('active','paused')`.
  - `re_deal_buyers` L62-70 — the pairing table: `status CHECK IN ('matched','sent','interested',
    'passed','assigned')`, `UNIQUE(deal_id, buyer_id)` (L68) — this constraint + `INSERT OR IGNORE`
    is the whole idempotency guarantee. Index on `deal_id` L70.
- **Wiring** — `worker/admin.ts` L345 (`POST acquisitions/buyer` → `saveBuyer`), and `matchBuyers`
  is invoked from the disposition action (`advanceDeal` action `'disposition'`, `acquisitions.ts`
  L236) and from cron when `disposition_tier==='auto'` (`runAcquisitions` L180-183).

## How to reapply it
1. **Schema.** A `subscribers` table with the buy-box columns (comma-separated list fields for
   set-membership criteria, numeric bounds for range criteria, a `status` active/paused). A pairing
   table `<item>_<subscriber>` with a `status` enum for the follow-through lifecycle and — critically
   — `UNIQUE(item_id, subscriber_id)`.
2. **Matcher.** For a given item, load active subscribers and evaluate each criterion with the
   "empty = wildcard" rule (`!filter || itemMatchesFilter`). On a full match,
   `INSERT OR IGNORE` the pair and count `meta.changes` so a re-run reports only NEW matches.
3. **CRUD.** A save endpoint to create/edit a buy-box; validate the `status` enum; store list
   fields as trimmed comma-separated text (or a child table if you need exact-set matching).
4. **Wire.** Call the matcher from the item's "distribute/match" action and, optionally, from cron
   for auto-distribution. Keep a manual action too.
5. **Hand off.** Read the `matched` pairs into your send step (email/SMS) and advance them
   matched→sent→interested→passed as the subscriber responds.

## Gotchas
- **Empty criterion = matches everything.** A subscriber with a blank buy-box matches every item —
  intentional (a buyer with no filters wants to see all deals) but surprising; surface it in the UI
  so nobody creates an accidental catch-all.
- **Comma-separated `.includes` matching is loose.** City/type matching is substring-based
  (`item.city.includes(buyerCity)`), so `"mesa"` matches `"east mesa"` — cheap and forgiving, but it
  can over-match short tokens. For exact-set semantics, normalize to a child table and match on
  equality.
- **Idempotency lives in the DB, not the code.** `UNIQUE(item, subscriber)` + `INSERT OR IGNORE` is
  what makes re-matching safe; never replace it with a SELECT-then-INSERT (it races and duplicates).
  Trust `meta.changes` for "new matches this run."
- **Only `status='active'` subscribers match** — paused buy-boxes are skipped; don't forget the
  filter or paused subscribers get spammed.
- **Matching is not contacting.** The matcher records a `matched` pair and nothing more. The actual
  outreach is a separate governed step — keep it that way so a match can't auto-blast a subscriber.
- **Price/beds are hard numeric bounds** (`<=`, `>=`) and require the item's value to be present and
  trustworthy — pair with `confirmed-inputs-decision-gate` so you're not matching on a guessed price.
