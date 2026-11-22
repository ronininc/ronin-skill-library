---
name: assignment-contract-review
description: >-
  Review (or draft-check) an ASSIGNMENT / flip contract where Ronin locks an asset at one price and assigns
  the contract to an end buyer for a spread — vehicles first (car-flip / Ronin Flipper deals), real-estate
  wholesale assignments second. Gives a fixed playbook (standard / fallback / escalate per clause), a
  RED-first triage (licensing gate → enforceability → closing mechanics), and a ready-to-insert redline
  library (consideration, closing mechanics, seller-breach remedy, access + test drives, release on
  assignment, risk of loss). Use WHENEVER someone drafts, pastes, or asks to review a "vehicle assignment
  agreement", "assignment contract", "purchase-and-assign", "wholesale contract", "flip contract", "option
  to buy and assign", a Muse/Solomon-drafted deal contract, or asks "is this contract safe to send to a
  seller". Serves as the PLAYBOOK for `legal:review-contract` (which otherwise falls back to generic
  standards) and COMPLEMENTS `wholesale-real-estate` (sourcing → assignment & close) and the car-flip
  engine. STATUS: NOT ATTORNEY-REVIEWED — authored by Codex from one generic review; every output must
  carry that banner and route to a licensed Arizona attorney before signing.
---

# Assignment Contract Review

> **NOT ATTORNEY-REVIEWED.** Minted 2026-10-10 by Codex from a single generic contract review (the Muse
> "Vehicle Assignment Agreement" draft). No attorney wrote or approved these positions. Treat it as a
> structured checklist that gets a draft *ready for* counsel, never as a substitute for counsel. When an
> Arizona attorney signs off on the positions below, record their name/date here and drop this banner.

## What it is / when to use
Ronin's flip deals (cars via Ronin Flipper, houses via the wholesale engine) share one contract shape:
**Seller agrees to sell to Ronin at price P → Ronin finds an end buyer at P + spread → Ronin assigns the
contract and collects the spread as an "Assignment Fee" → Seller deeds/titles directly to the end buyer.**
Ronin never takes possession or title. That shape has a predictable set of failure modes; this skill
checks for all of them in a fixed order and supplies fix language.

Composes with:
- `legal:review-contract` — run it with THIS skill as the playbook (positions table below) instead of
  "generic commercial standards". Output format stays theirs (GREEN / YELLOW / RED + redlines).
- `wholesale-real-estate` — stage 7 "assignment & close" for real property; this skill is the contract
  check that stage hands off to.
- `wholesale-close-playbook` — RE close-mode research (state-law table, no-debt contract guardrails, how an
  AI-sent contract binds the owner under UETA §14). Also UNVERIFIED; where the two disagree, keep the
  stricter rule. This skill is the clause-level check; that one is the close-mode policy.
- `outbound-compliance-gate` / governed send — a reviewed contract is still an outbound message; sending
  to a Seller stays a human tap.
- `docs` — publish the redlined v2 as a Codex Doc for the attorney, never as a "final".

## Review order (RED first — stop early if Step 1 fails)

### Step 1 — Licensing gate (regulatory, not drafting)
Ask before reading a single clause: **does repeatedly doing this deal type require a license Ronin
doesn't hold?** No clause cures this.
- **Vehicles (Arizona):** dealers and brokers are licensed by ADOT MVD under A.R.S. Title 28, ch. 10.
  The commonly cited trigger is selling more than six vehicles in 12 months; arranging sales for a fee
  without taking title can read as *brokering*. Repeated assignment of vehicle purchase contracts is the
  textbook "curbstoning" fact pattern. → **RED / escalate to AZ attorney** with the exact question:
  "Does Ronin need a dealer or broker license to assign vehicle purchase contracts it never titles, at
  N deals/year?" If yes, the structure changes (partner with a licensed dealer who buys; Ronin takes a
  referral fee) — don't patch the contract.
- **Real estate:** wholesaling regulation is state-specific and changing (marketing the contract vs.
  marketing the property, disclosure statutes). → route through `wholesale-real-estate` + counsel.
- Verify every statute cite with counsel before relying on it — thresholds above are "commonly cited",
  not confirmed.

### Step 2 — Enforceability (is there a contract at all?)
The typical Ronin draft gives Ronin a **free, no-reason exit** and gives the Seller **nothing** for being
tied up. That is the classic *illusory promise / option without consideration* problem: the Seller can
revoke anytime and the "exclusive" right is worthless.
- Fix = redline **A** (option fee + no-shop). This is the single most important drafting fix.
- Also check: the free exit should stay — it's the business model — but it must be *bought* by the option
  fee, not free.

### Step 3 — Closing mechanics (can it actually close?)
Drafts that describe the spread but never say who pays whom, or how title moves, fail at the table.
Must answer: who pays Seller the price; lien payoff to lienholder first; Seller signs title / deed
**directly** to the end buyer (Ronin never in chain of title); bill of sale; federal odometer disclosure
(vehicles); where it closes (title/escrow, MVD Authorized Third Party). → redline **B**.

### Step 4 — Clause-by-clause against the playbook
Use the positions table. Then the holistic check: is the risk allocation so one-sided that it creates
the Step 2 problem? (It usually is.)

## Playbook positions (feed to `legal:review-contract`)

| Clause | Standard (GREEN) | Acceptable fallback (YELLOW) | Escalate (RED) |
|---|---|---|---|
| Parties / signature | Entity signs: "Ronin Inc, an Arizona [corp/LLC], By: ___, its ___" | Individual + "on behalf of Ronin Inc" | Individual signs with no entity → personal liability |
| Asset description | VIN/APN, mileage, title brand, lienholder + payoff | Lien "to be disclosed before closing" | Title status unknown / "other" with no description |
| Consideration | Option fee $25–100 at signing, credited at close | $10 + mutual-promise recital | No consideration + free Ronin exit |
| Exclusivity | Seller no-shop during period, with remedy (redline C) | No-shop without liquidated damages | "Exclusive" with no Seller obligation |
| Assignment fee | Disclosed to and acknowledged by Seller | Disclosed as "difference in price" | Spread hidden from Seller (fraud exposure) |
| Period | 14 days + mutual written extension | Fixed 14 days | Open-ended |
| Inspection | 72h window, plus free exit anyway | Exit only on "material difference" | No inspection right |
| Possession / risk | Seller keeps asset, bears risk of loss, maintains condition, mileage cap | Possession only, risk silent | Ronin takes possession/registers/insures |
| Access | Show/photograph/inspect on 24h notice; test drives under Seller's insurance (redline D) | Access "by agreement" | No access during the marketing period |
| Ronin exit | Written notice any channel, no liability, option fee kept by Seller | Exit limited to listed reasons | Ronin owes damages on exit |
| Seller breach | Liquidated damages ≈ lost fee, or refund + documented costs | Refund of option fee only | No remedy |
| Seller reps | Owner, no liens except disclosed, not stolen, title brand accurate, odometer accurate, reps true through close | Owner + title only | None |
| Ronin warranties | None to anyone; asset sold Seller→end buyer AS-IS (redline E) | Silent | Ronin makes condition reps to end buyer |
| Release on assignment | Assignee assumes, Ronin released (redline E) | Silent | Ronin stays liable after assignment |
| Casualty | Damage/theft before close → auto-terminate (redline F) | Silent | Ronin bears loss |
| Law / venue | Arizona, Maricopa County | Another AZ county | Out-of-state |
| Boilerplate | Entire agreement, severability, counterparts, e-signatures | Entire agreement only | — |

## Redline library (insert-ready; bracketed values are operator decisions)

**A · Consideration + no-shop (must-have)**
> In consideration of the exclusive assignment right, Buyer shall pay Seller **$[25–100]** upon signing
> (the "Option Fee"), which is non-refundable and credited toward the Purchase Price at closing. During
> the Assignment Period, Seller shall not sell, list, or offer the [Vehicle/Property] to any other party.

**B · Closing mechanics (must-have)**
> At closing: (i) the end buyer pays the Purchase Price to Seller (or to Seller's lienholder up to the
> payoff amount, balance to Seller) and the Assignment Fee to Buyer; (ii) Seller signs title directly to
> the end buyer and provides a bill of sale and the federal odometer disclosure; (iii) Buyer is never in
> the chain of title. Closing may occur through a title/escrow service or an MVD Authorized Third Party.

**C · Seller breach (should-have)**
> If Seller sells or transfers the [Vehicle/Property] to anyone other than Buyer's assignee during the
> Assignment Period, Seller shall pay Buyer **$[X]** as liquidated damages, which the parties agree is a
> reasonable estimate of Buyer's lost Assignment Fee.
*Fallback:* refund of the Option Fee plus Buyer's documented costs. Keep X proportionate — a penalty is
unenforceable.

**D · Access + test drives (should-have; vehicles)**
> Seller shall make the Vehicle reasonably available for photos, inspection and showing on 24 hours'
> notice. Any test drive is at Seller's discretion, under Seller's insurance, and Buyer is not liable for
> any loss, injury or damage arising from it.

**E · Release on assignment + no warranty (should-have)**
> Upon assignment, the assignee assumes all of Buyer's obligations and Buyer is released. Buyer makes no
> representation or warranty about the [Vehicle/Property] to any person; it is sold by Seller to the end
> buyer AS-IS.

**F · Risk of loss (nice-to-have)**
> Risk of loss remains with Seller until title transfers. If the [Vehicle/Property] is materially
> damaged, destroyed or stolen before closing, this Agreement terminates under [exit section].

## Negotiation stance
- Lead with A + B (they make the contract real); C + D give exclusivity teeth and let Ronin sell; E + F
  are cleanup and good concession cover.
- With private sellers, a small upfront option fee usually *helps* close the signature.
- Keep the spread disclosed — transparency is the fraud defense, and matches the house rule that the
  Seller sees the real numbers.

## Output contract
Every review produced with this skill:
1. Opens with the **NOT ATTORNEY-REVIEWED** banner.
2. Reports Step 1 (licensing) first, even if the contract text is fine.
3. Uses GREEN / YELLOW / RED per clause + the redline letters above (so v2 drafts can cite "A, B, C").
4. Ends with the attorney question list (Step 1 question verbatim + any RED items).
5. Never marks a document "final", never sends it, never e-signs — producing a redlined v2 is fine;
   sending to a Seller or signing is a human tap after attorney review.

## Gotchas
- **The free exit is the trap.** The more one-sided the draft is for Ronin, the more likely it isn't
  enforceable against the Seller at all. Drafters (including Muse) optimize for "zero liability" and
  break consideration — check this every time.
- **Real-estate assignment logic doesn't port to vehicles.** RE wholesaling assigns an equitable
  interest in land; a vehicle flip without title looks like unlicensed brokering. Step 1 exists because
  of this.
- **An agent-sent contract can bind Ronin.** Under UETA, an electronic agent's sends can form a contract
  (see `wholesale-close-playbook`). Muse/Solomon may draft and redline; the send and the signature stay
  a human tap.
- **"Seller may not sue Buyer"** waivers don't protect against fraud claims; don't rely on them.
- **Lien payoff** is the most common closing failure on vehicles — always capture lienholder + payoff in
  the asset section.
- **Signature block**: an individual signing without the entity named invites personal liability.
- Provenance: derived from the 2026-10-10 review of a Muse-drafted Vehicle Assignment Agreement for
  Ronin Inc. No client data is embedded; bracketed values are per-deal operator decisions.
