---
name: contribution-credit-canon
description: >-
  A governed capability/contribution registry where a customer-, community-, or partner-built system becomes
  the owner's proprietary CANON while the CONTRIBUTOR's credit is permanently preserved — and contributing
  NEVER raises the contributor's price. Every entry carries a dual watermark (owner + contributor), an
  explicit `customerDataIncluded:false` (only the capability/pattern is canonized, never the data it ran on),
  a `mayBeSoldAsStandaloneUpsell:false`, a `noPriceIncreaseFromContribution:true`, and a canonization gate
  that refuses to promote an entry unless the watermarks are present, no customer data is included, and an
  authority approved it. On top of the registry it adds an OPEN idea program: contributors submit ideas,
  an eligibility check enforces attribution+ownership before an idea can enter a weekly public draw, the draw
  is announced with contributor credit, completion is tracked, and public "expansion telemetry" (time since
  last release, active drawn idea, next estimate) is exposed for a marketing page. Use WHENEVER a build needs
  "credit contributors without giving away ownership", "customers can extend the product and we canonize it",
  "a public idea/feature-request program with recognition", "weekly community draw", "preserve attribution
  on contributed capabilities", "no price penalty for contributing", or "public roadmap/expansion telemetry".
  It COMPLEMENTS partner-referral-program (money for REFERRALS — this is CREDIT for contributed CAPABILITY,
  no money moves), white-label-branding (rebranding — this instead preserves the contributor's mark under the
  owner's canon), ventures-portfolio-rollup, and risk-classified-review-queue (the review/build lane a drawn
  idea actually flows through). Guardrail: customer DATA never enters the canon; only the capability does.
---
# Contribution Credit Canon

## What it is / when to use / what it composes with
Two linked pieces: (1) a **capability registry** that turns a contributed system into the owner's governed
canon while permanently crediting the contributor and never charging them for it, and (2) an **open idea
program** (submit → eligibility → weekly public draw → announce → track → public telemetry) that feeds it.
The whole point is to let a product grow from its community/customers without either giving away ownership or
punishing the people who help.

- **`partner-referral-program`** moves money for referrals; this moves *credit* for contributed capability and
  explicitly refuses a price increase or a standalone upsell.
- **`white-label-branding`** rebrands FOR a client; this keeps the *contributor's* mark visible under the
  owner's canon watermark.
- A drawn/approved idea flows through **`risk-classified-review-queue`** to actually get built and released.

## Reference implementation — exact source
`~/Projects/Kingmaker/contracts/vault-registry.ts`:
- **Contributed entry:** `createCustomerCreatedVaultEntry(input)` — `:108-145`. Sets `status:'UNDER_REVIEW'`,
  `origin:'CUSTOMER_CREATED_USING_SOLOMON'`, and the invariant flags: `customerDataIncluded:false`,
  `proprietaryToRonin:true`, `mayBeSoldAsStandaloneUpsell:false`, `noPriceIncreaseFromContribution:true`, plus
  a `watermark` object carrying BOTH an owner watermark and the contributor's org name + a credit line
  (`:131-138`).
- **Price rule is a constant:** `canChargeAdditionalPriceForVaultContribution(entry): false` — `:147-149`
  (the type literally returns `false`).
- **Watermark check + canon gate:** `hasRequiredWatermarks` — `:151-155` (owner mark present; a customer-origin
  entry MUST carry the contributor mark); `canCanonizeVaultEntry` — `:157-165` refuses unless watermarks
  present AND `customerDataIncluded===false` AND proprietary AND not-standalone-upsell AND
  no-price-increase AND `approvedBy !== 'NOT_APPROVED'` AND status is VALIDATING/APPROVED.

`~/Projects/Kingmaker/contracts/open-dev-hall-of-fame.ts`:
- **Idea + eligibility:** `createOpenDevIdea` — `:82-108` (stamps owner+contributor watermark, no-price flag);
  `canEnterWeeklyIdeaPot(idea)` — `:110-117` gates on attribution/ownership/public-eligibility before a draw.
- **Draw + announcements + telemetry:** `markIdeaDrawn` `:119-132`, `createWeeklyDrawAnnouncement` `:134-136`,
  `createReleaseAnnouncement` `:138-140` (always credits the contributor), `createPublicExpansionTelemetry`
  `:142-164` (time-since-last-release, active drawn idea, next-estimate for a public page).

`~/Projects/Kingmaker/runtime/open-dev-engine.ts` — the orchestration glue: `submitOpenDevIdea` `:24-32`,
`qualifyIdeaForWeeklyPot` `:34-51`, `drawWeeklyIdea` `:53-80`, `releaseOpenDevIdea` `:82-95`,
`generateOpenDevTelemetry` `:97-103`.

## How to reapply
- **Adapt the watermark to your brand.** The source hard-codes a specific owner mark string; replace it with
  your own owner watermark, keep the dual (owner + contributor) shape and the four invariant flags.
- **Make the price rule structural.** Model "no price increase" as a type/DB constraint the canon gate reads —
  not a policy note someone can forget.
- **Eligibility before the draw.** Only ideas that already carry attribution + ownership + public-eligibility
  may enter the pot; check it at submit and again at draw.

## Unwired — bindings you must add
Pure types + pure functions (README status: contract + engine layer only; no persistence/routes/UI). To
productionize:
- **D1:** a `vault_entries` table (the registry record) and `open_dev_ideas` / `open_dev_draws` /
  `contributors` tables; store the watermark object as columns or JSON.
- **Routes/UI:** a contributor submit form (`cf-forms`), an internal review/canonize action (gate with
  `governed-operator-console` + `append-only-audit-log`), and a PUBLIC page fed by
  `createPublicExpansionTelemetry`.
- **Cron:** the weekly draw (pick one eligible idea, mark drawn, publish the announcement).

## Gotchas (from the code)
- **Capability, not data.** `customerDataIncluded` must be `false` and the canon gate enforces it — you
  canonize the *pattern/system*, never the customer's records (`vault-registry.ts:159`).
- **No price penalty is an invariant, not a promise.** It's a returned-`false` and a checked flag — keep it
  that way so no path can quietly upsell a contributor (`:147-149`, `:162`).
- **Credit survives every stage.** Draw, release, and telemetry all re-emit the contributor watermark
  (`open-dev-hall-of-fame.ts:135`, `:139`, `:159`) — don't drop it on the release notes.
- **Nothing canonizes without approval.** `approvedBy === 'NOT_APPROVED'` blocks canonization
  (`vault-registry.ts:163`); pair with `risk-classified-review-queue`.
