---
name: commerce-spine
description: >-
  The house standard for giving any business website a SOVEREIGN, DB-backed commerce + CRM brain
  and an auto-wired, processor-AGNOSTIC checkout. EXTENDS website-build-standard: every business
  site it builds gets a per-site Cloudflare Worker + D1 node (unlimited inventory + CRM + orders),
  which BYPASSES Clover's ~15,000-item ceiling by making the DB the source of truth and syncing a
  hot-set to the POS. Card-not-present checkout is wired automatically wherever the merchant's
  gateway is OPEN (Stripe, Square, Authorize.net, Clover Ecommerce) and degrades honestly to
  catalog + CRM + link-out where it is CLOSED (Toast and other vertical POS). Use this WHENEVER a
  business site needs a store, inventory beyond a POS limit, customer records, an online checkout,
  or "add the database / commerce brain" — on top of, not instead of, website-build-standard.
  Trigger on "add a shop / store", "sell online", "inventory system", "beyond Clover's item limit",
  "beyond D1's 10 GB limit / CRM too big for D1 / shard the database", "CRM for the site",
  "auto checkout", "commerce spine", "add the DB to the site", or building any
  site for a merchant who takes payments. Do NOT use for a pure brochure/no-commerce site (the base
  provisions an empty-ready node but you skip tender), for POS terminal (card-PRESENT) integration,
  or for non-web work. NEVER chase a closed processor's tender (e.g. Toast payments) — spine + CRM
  only for those, payments left untouched.
---

# Commerce Spine

The house standard for the **DB-backed commerce brain** behind a business site. It is a **layer on
top of `website-build-standard`** — read and follow that skill first for the non-negotiable base
(single self-contained `index.html` + `/assets/` + `README.md`, Cloudflare-static deploy,
builder-only Edit Media, image inspector, SVG logos, **payment-ready shop**, per-site inquiry
routing, group-link + hero rules). Everything here is **additive**, and it deliberately adds the one
thing the base forbids on a static site — **a database** — so the base's "no server, no database"
default gets ONE documented exception: a companion per-site Worker + D1 node that the static page
talks to over `/api/*`.

The thesis in one line: **the DB is the source of truth; the payment processor is a swappable driver.**
That is what removes Clover's item cap AND makes the merchant's operations portable across processors.

## Two independent value layers (never blur them)

- **Layer 1 — Inventory + CRM spine. Universal. Rides on DATA.** Ships on every business site,
  including closed-POS merchants (Toast). Unlimited catalog, customer records, order history — in
  the merchant's own D1 node. This is the core, and it is what a static site cannot do alone.
- **Layer 2 — Tender. Optional. Rides on PAYMENT ACCESS.** Auto-wired only where the processor is
  open (see matrix). A closed processor gets Layer 1 and **no tender code at all** — its payments
  are off the table, permanently, not "until we migrate."

A Toast merchant gets Layer 1, full stop. A Clover/Stripe/Square merchant can get both.

## The 15,000-item bypass (why the DB is master)

Clover's cap is a **register-sync limit, not a storage limit** — the device only sells what's in its
local inventory. So:

- The **D1 node holds the full catalog** (unlimited SKUs) and is the source of truth.
- A **hot-set syncer pushes the sellable working window (≤ the POS cap) into the POS**, selected by
  velocity/season/category. `catalog_source: db` (default) = spine is master, POS is a synced cache.
- Reconciliation runs the other way: POS sale webhooks decrement the master and write a ledger row.

> Honesty note — the existing `pineapple-disposables` connector currently runs the OPPOSITE
> direction (POS master → DB mirror, `catalog_source: processor`). Commerce-spine's default INVERTS
> it for over-cap merchants (DB master → POS hot-set). The DB→POS hot-set push is the **one genuinely
> new piece**; everything else is reuse. Mark it clearly in the README as build-vs-reuse.

## The 10,000 MB bypass (why a node isn't capped at 10 GB)

Cloudflare D1 caps a **single database at 10 GB** — but grants **50,000 databases per account**,
and its own documented fix for `Exceeded maximum DB size` is *"shard your data into multiple
databases."* So a per-site node is not capped at 10 GB; it's capped at ~500 TB. The house model is
**per-merchant first, then hash the big one** — a normal merchant lives in one `DB` forever, and
only when a **single** node nears the wall does it spread NEW customers across `DB_1`, `DB_2`, …:

- **Route by aggregate root, co-located.** A customer and their whole footprint (orders, events,
  tenders, refunds, media) live on **one** shard, so "show this customer" is a single-DB read — D1
  can't join across databases, and co-location means it never has to.
- **Sticky assignment, never `hash % N`.** `shard_routes` (in shard 0) maps each root to a shard for
  life; adding a shard moves nothing, only redirects new roots. Growth is O(new), not O(all).
- **Fat bytes go to R2.** D1's 2 MB row cap means recordings/attachments/email-HTML can't live
  inline anyway — R2 holds the bytes, D1 holds a co-located `media_objects` pointer.

Pieces: `references/schema-sharding.sql` (registry + R2 pointers), `references/crm-shard-router.mjs`
(the `.dbFor()` router), `references/r2-offload.mjs`, and `references/sharding.md` (doctrine +
operator runbook). Proven end-to-end by `references/_proof/shard-router.test.mjs` (real modules over
three local SQLite shards — sticky routing, co-location, overflow, fan-out, R2 offload). This is the
same shape as the 15k-item bypass: **the DB is master, the platform limit becomes a routing problem.**

## Processor capability matrix (open vs closed — the honesty gate)

Decide open-vs-closed **by probe, never by assumption** — use the `capability-readiness` state machine
(`NOT_CONFIGURED / CONFIGURED_UNVERIFIED / VERIFYING / VERIFIED_READ / WRITE_GATED_UNPROVEN /
VERIFIED_WRITE_GATED / STALE`; invariant: *configuration means CONFIGURED_UNVERIFIED, never READY*).

| Processor | Mode | Web tender (CNP) | Notes |
|---|---|---|---|
| **Stripe** | driver | ✅ hosted checkout | reference adapter; card data never touches us |
| **Authorize.net** | driver | ✅ Accept Hosted | |
| **Square** | driver | ✅ Web Payments SDK | |
| **Clover Ecommerce** | driver | ✅ hosted checkout | POS tender stays card-present on-device |
| **Toast** (+ vertical POS) | **peer** | ❌ none | Layer-1 only; checkout CTA → their ordering / inquiry routing |
| unknown / none | — | ❌ | catalog + CRM + inquiry routing until a gateway is confirmed |

A `driver` implements the tender contract (`references/tender-contract.md`). A `peer` implements a
read-mostly data sync (menu/sales/guests in, ingredient-level stock deduction) and **never** a tender.

## Non-negotiable data rules (inherit base + these)

- **Money is integer cents. Quantity is milli-units (thousandths, `qty_mu`).** No floats for money.
- **Every stock change writes an append-only `inventory_ledger` row in the SAME transaction.** The
  cached `stock_qty_mu` on a product is a convenience, never the truth — the ledger is the truth.
- **`tenantId` is in every record identity** (`${tenantId}:${kind}:${key}`). Omitting it lets two
  tenants collide on a primary key and leak across merchants — the layout mirrors the OCSF Drive
  folder convention onto the code key `provider__tenant__merchant`.
- **Free-text / sensitive columns are AES-GCM encrypted at rest** (`encField`/`decField`, keyed by an
  `ENCRYPTION_KEY` secret) — customer notes, refund reasons, credentials. Never plaintext.
- **Permissions are enforced in the Worker, not the DB** (SQLite has no RLS): role ranks
  owner/lead/tech/worker, `run_worker_first: ["/*"]` so security headers cover every path.
- **`PAID` and refund `succeeded` are written ONLY from a verified gateway webhook** — never from a
  client callback, never optimistically. Total refunds for an order can never exceed its captured
  amount (over-refund guard, enforced in the same transaction).
- **Card data never lands in the node.** Route CNP to the gateway's hosted/tokenized fields; run the
  PCI-DSS boundary scanner on every write so a stored order can't contain a PAN/CVV/track/PIN.
- **Fail closed on environment.** A sandbox credential can never resolve to a production host
  (mirror `clover-environment.ts`). Unconfigured integration ⇒ inert `needs_review`, never faked.
- **Webhooks are idempotent + loop-safe.** Dedupe on a stable `${mId}:${objectId}:${type}:${ts}` key
  into `webhook_events`, with an `origin` tag so self-inflicted sync pushes don't echo back as new events.

## What this composes (assembly, not greenfield)

- **DB node skeleton** — `slik-team-board` Worker + D1 (`worker/index.js`, numbered `migrations/`,
  pinned `account_id`, AES-GCM at rest, Worker-enforced roles) + the TSS per-node layer
  (`getNodeDb`/`node_records`, tenant in the key).
- **CRM + media** — Sanctum per-node source store (`sanctum_sources`, kinds incl. `crm/image/video/audio`).
- **Auth** — `cf-identity` PBKDF2 `users`/`sessions` (or TSS `auth_*` tables).
- **Clover driver** — `pineapple-disposables` `CloverService` (config-gated, atomic orders, cents +
  milli-units, idempotent webhooks) + fail-closed `clover-environment.ts`.
- **CNP checkout** — `stripe-checkout-adapter.ts` + `storefront-order-store.ts` (state machine, PAID
  from verified webhook) + `payment-account-data-boundary.ts` (PCI guard) + `capability-readiness.ts`.
- **Schema + contracts** — `references/schema.sql`, `references/tender-contract.md`, `references/provision.md`.
- **Scale-out (D1 10 GB bypass)** — `references/schema-sharding.sql`, `references/crm-shard-router.mjs`,
  `references/r2-offload.mjs`, `references/sharding.md`; proof in `references/_proof/`.

## Workflow (applying this standard on a build)

1. Run the **base `website-build-standard` workflow first** (scope, standing questions, research,
   scaffold, media editor, SVG logo, verify-by-render, deliver). Ask the base's per-site questions
   PLUS: *which payment processor does this merchant use, and does the catalog exceed the POS cap?*
2. **Provision the per-site node** (`references/provision.md`): create the D1, apply the schema
   migrations, bind the Worker, pin `account_id`. Ships even on a brochure site — **empty-ready**, so
   there is never a retrofit.
3. **Probe the processor** with `capability-readiness`. Open → wire the matching hosted checkout
   (Layer 2) via the tender contract. Closed/unknown → Layer 1 only; checkout CTA routes to their
   ordering / the base inquiry destination. **Never wire tender you haven't probed as open.**
4. If the catalog exceeds the POS cap, set `catalog_source: db` and wire the **hot-set syncer**
   (DB → POS) + reconciliation (POS webhooks → ledger). Mark this piece build-vs-reuse in the README.
5. **Verify by rendering + real calls** — a live catalog read from D1, one order through the state
   machine to `AWAITING_PAYMENT`, a webhook-driven `PAID`, and (if wired) a partial refund to
   `succeeded`. Zero card data in any stored row. No fake PASS.
6. **Deliver** per base, and in the README list: the node's D1 name, each integration's mode
   (driver/peer) and probed readiness state, the tender capabilities enabled, and any piece still
   pending (esp. the DB→POS hot-set if built). The operator must approve any real deploy.

## Notes

- **Closed processors are not a target to convert.** Never wire, propose migrating, or "free them
  from" a closed processor's tender unless the operator explicitly asks. Spine + CRM only.
- **Truth over spectacle.** An integration is only "ready" when `capability-readiness` says so from a
  real probe; a refund is only `succeeded` from a real gateway webhook; stock is only what the ledger
  sums to. Never present configured-but-unverified as working.
