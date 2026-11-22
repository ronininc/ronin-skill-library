---
name: profiler
description: >-
  The house identity-resolution engine — the Owner.com research layer beneath our
  lead-gen skills. Given an online account, logo, photo/video, handle, phone, or
  email, it proves which REAL BUSINESS it belongs to and pulls verified contact info.
  Runs five match tests — account→business, logo, photo/video, account↔website
  cross-link, and NAP (name-address-phone) consistency — scores each with a confidence
  tier, then enriches emails/phones. Serves BOTH verticals: restaurant prospects
  (orosolu / Owner.com, via custom-lead-generator) and real-estate owner targets (via
  wholesale-real-estate). Use for "whose account is this", "does this IG/TikTok belong
  to that shop", "match this logo/photo to a business", "is this account the same as
  this website", "find their email/phone", "verify this profile is really them", or
  "de-dupe these profiles". Uses web search + the Chrome browser for reverse-image and
  profile reads. Public business data only; never fabricates — unmatched = Unknown,
  every match shows its evidence + tier.
---

# Profiler — the Owner.com Research & Identity-Match Engine

`business-profile-recon` answers *"what are this named business's facts?"*
`custom-lead-generator` and `wholesale-real-estate` answer *"who should we build
for / do a deal with?"* **Profiler answers the question that comes before both of
those: "is this account, logo, photo, handle, number, or website actually THEM?"**

It's the identity-resolution layer. You hand it a fragment — an Instagram handle, a
storefront photo, a logo, a phone number scraped off a flyer, a TikTok that might be
the shop's own or might be a customer's — and it does the work of tying that fragment
to a single real business (or telling you honestly that it can't). Then it hands the
resolved, contactable entity back up to the lead-gen engines so they never pitch the
wrong shop, attach a stranger's photo, or dial a wrong number.

**One question, five tests, one verdict:**

```
 you hand in a fragment ──►  ┌─ 1. ACCOUNT → BUSINESS   (handle/bio/link → which entity?)
 (handle · logo · photo ·    │  2. LOGO MATCH          (this mark == their mark?)
  video · phone · email ·    │  3. PHOTO / VIDEO MATCH  (this media == their place/food/team?)
  website · storefront pic)  │  4. ACCOUNT ↔ WEBSITE    (does the profile link the site & vice-versa?)
                             └─ 5. NAP CONSISTENCY      (name-address-phone agree across sources?)
                                        │
                                        ▼
                          MATCH VERDICT + confidence tier  ──►  CONTACT ENRICHMENT (email / phone)
                                        │
                                        ▼
                          IDENTITY MATCH DOSSIER  ──►  custom-lead-generator  /  wholesale-real-estate
```

The verticals differ only in the target and the corroborating record set: a
restaurant resolves against Owner.com / GBP / delivery apps / socials; a real-estate
owner resolves against the county assessor / recorder + people-search + socials. The
five tests, the confidence math, the contact rules, and the "never fabricate"
doctrine are identical. Configure the target per `references/handoffs.md`.

## Prime directives (these govern everything)

1. **Never fabricate a match or a contact.** A match you can't evidence this run is
   `Unknown`; a match with weak evidence is `UNVERIFIED — confirm`. A wrong match is
   worse than no match — it sends the whole pipeline (site build, cold call, mailer,
   contract) at the wrong person. Never synthesize or "complete" a partial phone
   number or guess an email pattern and present it as found.
2. **Every verdict shows its evidence and its tier.** No profile is declared "theirs"
   without naming *which* of the five tests passed and *what you saw*. The confidence
   tier (`Confirmed` / `Likely` / `Possible` / `Unknown`) is re-derivable from the
   evidence row — same evidence → same tier, always (`references/confidence-scoring.md`).
3. **Reconnaissance of BUSINESSES, not surveillance of people.** Resolve accounts to
   *businesses* and pull *business* contact info. For real-estate owners the target
   is the property-owner-as-counterparty via public records — you may resolve a name
   to a mailing address and a business/contact number, but do **not** compile a
   private dossier on an individual (relationships, movements, health, finances beyond
   the public record, real-time location). See `references/guardrails.md` — it is not
   optional reading.
4. **Public sources only; respect every fetch boundary.** Public profiles and public
   records. If `WebFetch`/`WebSearch`/the browser is blocked or a source is
   login-walled, that field is `Unknown` — never route around it with shell/HTTP
   tools, never scrape behind a login, never defeat an access control.
5. **Contact law is the caller's to satisfy, and you flag it.** Phones you surface
   must be DNC-scrubbed and (for SMS) 10DLC-registered by the operator before use;
   emails are subject to CAN-SPAM. You produce the enriched, tiered contact — you
   also stamp the compliance obligation (`references/contact-enrichment.md`).
6. **Approval before any outreach, write, or spend.** Resolving identity and drafting
   are free. Sending a message, writing to a CRM, or paying for a lookup needs an
   explicit yes each run.

## The five match tests

Each test is a summary; the exact method — what to search, what to read in the
browser, what counts as a pass — is in `references/match-methods.md`. **Read it
before running the tests.** You rarely need all five; run the ones the fragment and
the target support, and let their combined weight set the tier.

### 1. Account → Business
The anchor test. Take the handle/bio and resolve *which entity* it represents:
display name and @handle vs the business name, the **bio** (address line, "DM to
order", category), the **link-in-bio** (does it point at the business's own domain /
Owner.com / Linktree?), tagged locations, and the content itself. Output: the single
business this account most likely belongs to, or `ambiguous` if two entities share
the name (extremely common — same-name shops in different cities, franchise vs
independent). Never collapse two entities into one to force a match.

### 2. Logo match
Does the mark on the account match the business's mark elsewhere? Compare the profile
picture / header logo against the logo on their own website, Google Business Profile,
signage in a storefront photo, and delivery-app listing. A match is *same wordmark,
same icon, same colors* — note near-matches (old logo vs rebrand) explicitly rather
than calling them equal. This is often the fastest high-confidence tie for a shop
with no website.

### 3. Photo / video match
Does the media on the account depict *this* business — its interior, storefront,
food, team, product? Cross-reference against known-good photos (GBP, their own site,
a field-intake storefront photo). Use **reverse image search** in the browser
(`Codex-in-chrome`) to check whether a photo appears on the business's other
profiles (corroborating) or is a stock/stolen/someone-else's image (disqualifying).
For video, match the location/interior/signage visible in the clip. This is also how
you separate the operator's **own** account from **UGC** (a customer's post about
them) — both are useful, but only one is *theirs*.

### 4. Account ↔ Website cross-link
The strongest single signal when it exists: mutual linkage. Does the website link out
to the account (social icons in the footer/header) **and** does the account's
link-in-bio point back to the website? Two-way linkage from surfaces the operator
controls is near-conclusive. One-way linkage is strong-but-confirm. Also check the
website's source for social meta tags and the delivery-app listing's linked socials.

### 5. NAP consistency
Name, Address, Phone agreeing across independent sources is the classic entity-
resolution proof. Pull the trio from each source you reached (own site, GBP, Yelp,
delivery app, Facebook, county record for real estate) and check agreement. Full
agreement across ≥2 independent operator-controlled sources = strong. A conflict
(two different phones, two addresses) is not a match failure by itself — it's a
**flag to resolve** (rebrand? second location? closed and reopened?), recorded as
such, never smoothed over.

## Scoring the match

Combine the tests that fired into one tier with `references/confidence-scoring.md`.
The short version: two-way website↔account linkage OR (logo match + NAP agreement
across 2+ operator sources) → **Confirmed**; one strong test + one corroborating →
**Likely**; a single suggestive signal → **Possible**; nothing that ties → **Unknown**
(and the fragment stays unresolved, not force-matched). Every tier writes the
evidence that produced it into the dossier so it's auditable and reproducible.

## Contact enrichment (email / phone)

Once the entity is resolved, get reachable, correct contact info —
`references/contact-enrichment.md` has the method and the honest accuracy ceiling.

- **Restaurant / shop:** the business line and email come from operator-controlled
  surfaces first — own site / Owner.com contact page, GBP, Facebook "About", the
  bio, ordering platform. Tier each (`Confirmed` = on ≥2 operator surfaces).
- **Real-estate owner:** the counterparty's mailing address comes from the assessor;
  phone/email is best-effort skip tracing against public people-search + records,
  with the same accuracy ceiling and paid-tool honesty as
  `wholesale-real-estate` Stage 3. Corroborate with a second source; `Unknown` beats
  a wrong number.

Never invent an email from a `first@domain` pattern and present it as verified — a
pattern guess is labeled `PATTERN-GUESS — unverified`, never `Confirmed`.

## What it produces — the Identity Match Dossier

The deliverable is the **Identity Match Dossier** (`assets/dossier-template.md`): for
each fragment you were handed, the resolved business (or `Unknown`), the five-test
evidence grid with the tier, the enriched contact block with per-item tiers, any
conflicts flagged for a human, and the source links. For a batch (de-duping a pile of
profiles, resolving a list of handles), also emit the **Match Sheet**
(`assets/match-sheet-template.csv`) — one row per fragment with its verdict, tier, and
resolved entity — so it drops straight into the lead workbook or the wholesale CRM.

Deliver both as real files with `SendUserFile`. When Profiler is invoked mid-pipeline
by another skill, hand the resolved entity + contact block back inline instead.

## How to run

1. **Read the fragment → pick the target vertical.** Restaurant/shop → orosolu /
   Owner.com record set; property/owner → wholesale record set. Echo back what you
   were handed and what you're resolving it to.
2. **Read `references/match-methods.md`**, then run the applicable tests, recording
   what you actually saw for each (not a conclusion — the observation).
3. **Score the tier** per `references/confidence-scoring.md`. If `Unknown`, say so
   plainly and stop — do not force a match to have an answer.
4. **Enrich contact** per `references/contact-enrichment.md`, tiering every item and
   stamping the DNC/10DLC/CAN-SPAM obligation on anything meant for outreach.
5. **Write the dossier** (and Match Sheet for a batch); flag every conflict for a
   human; deliver the files.
6. **Hand off** per `references/handoffs.md` — resolved entity → `custom-lead-generator`
   or `wholesale-real-estate`; never trigger outreach/writes/spend without a yes.
7. **Prove the run.** Confirm every verdict names its evidence and tier, no contact
   item is asserted without a source, every conflict is surfaced, and any batch cap is
   stated. Only then present.

## Guardrails (summary — full text in `references/guardrails.md`)

Public business profiles and public records only. Resolve businesses, don't build
dossiers on private individuals. No login-bypass, no scraping behind access
controls, no shell/HTTP end-run around a blocked fetch. Reverse-image search is for
verifying a photo belongs to the business — not for identifying private people.
Never surface protected or sensitive personal data. Contact info is for legitimate
business outreach the operator is responsible for making compliant.

## Reference & asset index

- `references/match-methods.md` — the exact method for each of the five tests (what to search, what to read in the browser, what counts as a pass, how to reverse-image-search).
- `references/confidence-scoring.md` — the deterministic tier rubric; same evidence → same tier.
- `references/contact-enrichment.md` — email/phone method per vertical, accuracy ceiling, DNC/10DLC/CAN-SPAM stamps, paid-tool honesty.
- `references/guardrails.md` — public-only, business-not-person, fetch-boundary, and sensitive-data rules. Not optional.
- `references/handoffs.md` — vertical config + how the resolved entity feeds `custom-lead-generator` and `wholesale-real-estate`.
- `assets/dossier-template.md` — the per-fragment Identity Match Dossier.
- `assets/match-sheet-template.csv` — one row per fragment for batch resolution / de-dupe; maps into the lead workbook and the wholesale CRM.

## Example

**Input:** "This IG @thepastyhouse keeps popping up near Cornish Pasty Co — is it
actually them, and do we have a number?"

**Right (this skill):** Resolve *account→business* (bio says "Tempe · handmade
pasties", link-in-bio → cornishpastyco.com — points at the real domain). *Logo match*:
profile pic wordmark == site header wordmark. *Photo match*: reverse-image a hero shot
→ it also appears on their GBP → own media, not stolen. *Account↔website*: site footer
links the IG **and** the bio links the site = two-way. *NAP*: name/address/phone on
site == GBP == DoorDash. Four tests pass, two-way linkage present → **Confirmed**.
Enrich: business phone on site + GBP (`Confirmed`), no public email → `Unknown`, DNC
stamp attached. Dossier out, entity handed to `custom-lead-generator`.

**Wrong:** "Yeah that's them" with no test named, or pasting a phone number that only
appeared on one stale aggregator as `Confirmed`, or reverse-searching the *owner's*
face to find their home. Those are the exact failures this skill exists to prevent.
