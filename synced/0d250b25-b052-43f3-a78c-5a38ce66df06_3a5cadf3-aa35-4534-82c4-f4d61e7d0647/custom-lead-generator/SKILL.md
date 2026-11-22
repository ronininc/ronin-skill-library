---
name: custom-lead-generator
description: >-
  The orosolu.org engine — our version of Owner.com. It finds and qualifies local
  restaurant prospects in an area (lead gen), AND for every shop it surfaces (plus
  any target you name that we haven't pitched yet) it auto-runs a deep intelligence
  + media dive — menu, hours, address, phone, socials, reviews, brand colors, logo,
  real photos/videos — synthesized into a Build Brief that feeds website-build-
  standard. Use WHENEVER the task is to find/qualify/score leads, build a prospect
  list, scan an area for shops, OR look up a specific business, pull everything on
  them, gather info + media, onboard a client, or prep a shop for a site build.
  Trigger on "find leads", "build a lead list", "who should we target", "scan an
  area", "qualify these", "look up a shop", "pull their info/menu/photos", "gather
  everything on them", or a business name to build for. Builds on
  business-profile-recon for facts; hands off to website-build-standard. Never
  fabricates facts or media — unverifiable items are Unknown / CLIENT-UPLOAD.
---

# Custom Lead Generator — the orosolu.org Engine

This is orosolu.org's version of Owner.com, as one skill. Owner.com's whole machine
is two moves fused together: **find** the independent restaurants that most need
first-party ordering + marketing, and **onboard** each by automatically pulling
everything about them — menu, brand, photos, video — to stand up their presence.
This skill does both, and never treats them as separate: the moment it finds or is
handed a shop, it runs the deep dive that gets that shop ready to build.

**Three input lanes, one pipeline.** Scan an area, name a shop, or hand in a
storefront photo from the field — the per-shop unit of work is the same **deep dive**
→ site:

```
                        ┌─ PROSPECTING: scan area → qualify (buy-box) → rank ──────────┐
 you ask ──────────────►┤  TARGETED: name one/more shops (even unpitched) ─────────────├─► for EACH shop:
                        └─ FIELD-INTAKE: a storefront photo (+address) of an invisible ─┘        │
                           shop the operator found in person (references/field-intake.md)        ▼
                                              DEEP DIVE  (business-profile-recon facts + media harvest)
                                                                                                 │
                                                                                                 ▼
                                       BUILD BRIEF + MEDIA MANIFEST  ──►  website-build-standard  ──►  cloudflare-ordering-worker
```

**The best prospects are invisible online** (no website/Google/Yelp — cash-only spots
found in person). A web scan can't surface them and a name lookup can't verify them —
that's not failure, it's the highest-need lead, and it comes via **FIELD-INTAKE**: the
operator's storefront photo + the address they're standing at is the recon. Read the
photo as primary evidence, match the brand from the logo, build presence-first, and
mark everything not on the sign as operator-to-confirm — never attach a same-name
shop at the wrong address. See `references/field-intake.md`.

It **builds on `business-profile-recon`** for the verified fact sweep (don't
duplicate it — call it) and **hands off to `website-build-standard`**. The default
target is the Owner.com restaurant; the engine is reconfigurable (`references/config.md`).

## The offer (how orosolu wins the account)

The prebuilt site is the hook, not the product. The product is **payment
processing** (orosolu / smarterswipe). The play: we walk in, show the operator a
site *already built* with their own name, menu, and photos, and say — "this is
yours, live, the day you move your card processing to us." So:

- **Every profile we find is a media source.** Their Instagram, Facebook, TikTok,
  Yelp, and Google photos/videos are the content we pull to populate the site — the
  site should look like *theirs* on first view, because it's built from their media.
- **The site is offered free, tied to processing.** Framing, copy, and the order/
  payment path assume the shop runs payments through orosolu; that's what makes the
  free site pay for itself. Shops that can't even take a card today (cash/Zelle only)
  are the strongest prospects — the offer is "take cards *and* get a site."
- **So the prebuild has to be real and populated,** not a skeleton. The pitch only
  lands if the operator sees themselves already on it.

## The core rule you asked for

**Anytime the engine finds or is given a shop, it does the deep dive — targeted or
not, pitched or not.** Lead gen is never limited to whatever single shop you're
looking at, and a shop never sits on a list as just a name. The only shops that
*don't* get the deep dive are ones the buy-box **DROPs** (national chain, closed,
already handled) — no point harvesting media for a shop orosolu.org would never
build for. Qualified prospects, brand-new targets, and revisits all get the full
treatment.

## What it produces

- **Primary deliverable — the Lead Workbook** (`references/lead-workbook.md`): a real
  `.xlsx` spreadsheet (or a Google Sheet when Drive is connected) with a **Leads** tab
  (one ranked row per qualified shop, with the pitch hook and social links) and a
  **Websites** tab where each row links to that shop's prebuilt site file — click it
  and the template opens rendered in the browser. **Not** an HTML dashboard.
- **A prebuilt starter site per qualified lead** (`references/prebuild.md`) —
  house-standard, populated with the shop's facts/socials/photos, shipped in a
  `sites/` folder alongside the workbook so the links resolve.
- The whole run ships as **one zip** (workbook + `sites/`), backed by the same scoring
  (`references/scoring-rubric.md`) and a Build Brief + Media Manifest per shop.
- **Targeted run** → a one-row workbook + that shop's prebuilt site. Same format,
  one lead.

The **Build Brief** (`references/build-brief.md`) is the synopsis shaped to
`website-build-standard`. The **Media Manifest** (`references/media-harvest.md`)
catalogs every real photo/video/logo, rights-flagged, mapped to build slots.

## The discipline (why orosolu.org output stays trustworthy)

- **Evidence before conclusions.** No fact, score, or media attribution without a
  source read this run. Didn't see it → `Unknown`.
- **Unknown is valid / fail closed.** Unverified facts become labeled placeholders,
  never guesses; a shop with too many unknown core dimensions is `INCOMPLETE`, not
  qualified; a disqualifier is a `DROP`.
- **Deterministic scoring.** Same evidence + buy-box version → same tier, always
  re-derivable from the row (`references/scoring-rubric.md`).
- **Catalog media, don't blind-download.** Find and describe real media with source
  URLs and a rights flag; the client supplies the files they own via the build's
  editor. Photos from someone else's profile are candidates, not ready-to-publish.
- **Respect fetch + access boundaries.** Public profiles only; if a fetch is blocked
  the field is `Unknown` — never route around it with shell/HTTP tools or scrape
  behind a login.
- **Approval before outreach / writes / spend.** Drafting is free; sending, CRM
  writes, and spend need an explicit yes each run.
- **No fake completion.** Every row is scored-with-evidence, `DROP`+reason, or
  `INCOMPLETE`+missing-items; every brief's Open Items list is complete. Never
  present a partial batch or an invented pipeline as finished.

## Workflow

1. **Read the ask → pick the mode (Intent).** *Prospecting* if it names an area/
   vertical/"find leads." *Targeted* if it names one or more specific shops. Echo
   back the mode, the buy-box version, and — for prospecting — geography + count.

2. **PROSPECTING only — source + qualify.**
   - **Source candidates** in the geography with `WebSearch` + any approved maps/
     directory connector (`"<cuisine> <city>"`, "best takeout <city>", delivery-app
     category pages). Aim ~2–3× the wanted count. Record where each came from.
   - **Qualify** each against `references/buy-box.md` + `references/scoring-rubric.md`:
     disqualifier → `DROP` (stop, no deep dive); ≥2 core Unknowns → `INCOMPLETE`;
     else Tier A/B/C. This is a cheap first pass to decide who's worth the dive.

3. **DEEP DIVE — run on every qualified/targeted shop.** For each shop that isn't a
   DROP:
   - **Verified facts via `business-profile-recon`** → Profile Card (menu, hours,
     address, phone, socials, reviews, what they really sell), each sourced or
     `UNVERIFIED`. Don't duplicate the sweep; consume it. (`references/intel-checklist.md`
     is the field checklist.)
   - **Media harvest** (`references/media-harvest.md`) → catalog logo, hero-candidate
     video (10–20s rule), food/interior/team photos; sample the brand palette (hex);
     rights-flag every asset (`OWN` / `UNCLEAR` / `CLIENT-UPLOAD`). Catalog, don't
     download.

4. **Plan the media slots.** Map `website-build-standard`'s slots (hero, gallery,
   menu-item, logo, roster) to specific assets or `CLIENT-UPLOAD` → the Media Manifest.

5. **Synthesize the Build Brief** (`references/build-brief.md`): sections, copy seeds
   from real facts (never invented), palette + logo direction, hours/address/phone,
   menu/products for the shop, socials, and the two standing prompts the builder must
   ask (inquiry routing, group/community link). Mark every unverified field as a
   labeled placeholder. Attach the buy-box tier + score trace so priority is visible.

5b. **Auto-prebuild the starter site** (`references/prebuild.md`) — for every
   qualified/targeted shop (never a DROP). Stamp a house-standard single-page site
   from the Build Brief: hero = video slot with the best photo as poster, cataloged
   photos in the frames below, socials wired, real facts + menu loaded (`UV` on
   anything unconfirmed), the builder-only media-editor kit, payment-ready order CTA,
   and inquiry routing to `leads@orosolu.org` until onboarding. Verify each with
   headless Chromium (zero JS errors, editor builder-only), package Cloudflare-ready.
   This is automatic — the lead list ships with a site attached per lead.

6. **Assemble the Lead Workbook (primary deliverable).** Build a real `.xlsx` per
   `references/lead-workbook.md` (use the `xlsx` skill / `assets/workbook-builder.py`):
   a **Leads** tab (ranked rows, pitch hook, social links, `UV` on unverified) and a
   **Websites** tab where each row hyperlinks to `sites/<slug>.html`. Ship the workbook
   and the `sites/` folder as **one zip** so the links open the rendered templates;
   verify each link resolves and each site renders. If Google Drive is connected,
   also create the sheet in Drive. Do **not** build an HTML dashboard.

7. **Hand off + upgrade (approval-gated).** Every qualified lead already has a
   starter site attached — so the ask isn't "should we build one," it's which lead to
   **take live and upgrade**: wire commission-free ordering via
   `cloudflare-ordering-worker` and add the full immersive centerpiece via
   `website-build-standard`. Draft the orosolu.org outreach angle (from `buy-box.md`)
   but don't send or write to a CRM without a yes.

8. **Prove the run.** Confirm every shop is deep-dived (or correctly DROP/INCOMPLETE),
   no asserted fact lacks a source, every Media Manifest asset is rights-flagged, and
   any deep-dive cap on a big scan is stated plainly. Only then present the result.

## Scale note

On a big prospecting scan the deep dive is the expensive part. Default is to
deep-dive every qualified shop; if you must cap a single pass, dive the A/B tiers
first, `log` exactly what was dived vs queued, and never imply the rest were worked.
DROP shops are always skipped. This keeps "deep-dive everything" honest instead of
silently partial.

## Other verticals

Restaurants are the default (the Owner.com outcome). Swap the buy-box and the field/
media checklist per `references/config.md`; the two-mode pipeline, the deep-dive
rule, the discipline, and the Build-Brief handoff stay identical.

## Example

**Prospecting:** "Find 15 restaurant leads in Tempe worth building for." → mode:
prospecting, buy-box orosolu-restaurant v1. Source ~40 candidates; qualify (a
national chain → `DROP`, no dive). For each survivor run the deep dive: e.g.
*Cornish Pasty Co.* — on DoorDash+Uber Eats+Grubhub, own site has a menu but no
order button, 3.9k reviews @4.7★, owner-operated → Tier A (86); recon Profile Card +
media harvest (two ~15s IG oven reels as hero candidates, food set for gallery,
palette sampled) → Build Brief. Deliver the ranked sheet of 15, each qualifying row
linked to its Brief.

**Targeted (unpitched):** "Do a deep dive on Pizzeria Bianco — we haven't pitched
them." → mode: targeted. Skip the sheet; run the full deep dive + Build Brief +
Media Manifest, note its tier, hand to `website-build-standard`. A brand-new,
unpitched target gets the exact same depth as a scanned one — that's the whole point.

**Wrong:** returning a list of 15 names with no depth, or deep-diving a shop with
guessed hours and a scraped stranger's photo. That's a name-only list or a fabricated
onboarding — the two failures this engine exists to prevent.
