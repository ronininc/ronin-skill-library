# Match Methods — the exact method for each of the five tests

This is the operational heart of Profiler. Each test below tells you *what to search*,
*what to read in the browser*, *what counts as a pass*, and *what to record* (the raw
observation, not the conclusion). Run the tests the fragment supports; the combined
weight sets the tier in `confidence-scoring.md`.

**Golden rule for all five:** record the *observation*, not the verdict. Write "bio
link → cornishpastyco.com" not "it's them." The verdict is derived at scoring time
from the observations, so anyone can re-check it.

---

## Test 1 — Account → Business

**Goal:** resolve a handle/account to the single real entity it belongs to, or declare
`ambiguous`.

Method:
1. Locating search: `"<handle or display name>"`, then `site:instagram.com <name>`,
   `<name> <city> instagram/tiktok/facebook`. Collect the profile URL.
2. Read the profile header + bio (browser or `WebFetch`): display name, @handle,
   category, address line, hours, "DM/link to order", any phone.
3. Read the **link-in-bio** — the single strongest account→business signal. Does it
   resolve to the business's own domain, an Owner.com/Square/Toast ordering page, a
   Linktree that lists the business, or a delivery-app store page? Follow it.
4. Check **tagged/most-frequent location** on posts and the "location" field.
5. Skim recent content: does it depict one specific business consistently?

**Pass:** the handle/bio/link/content all point at one entity. **Ambiguous:** two
distinct entities share the name (different cities, a franchise vs a same-named
independent) and nothing disambiguates — record both candidates, resolve with Tests
2–5, and do **not** collapse them. **Fail/Unknown:** account is generic, a fan/UGC
account, or dormant with nothing tying it to a business.

Record: handle, display name, bio text (verbatim key lines), link-in-bio target URL,
tagged location, candidate entity/entities.

---

## Test 2 — Logo match

**Goal:** confirm the mark on the account is the business's mark.

Method:
1. Capture the account's profile picture / header logo.
2. Pull the business's mark from operator-controlled surfaces: website header/favicon,
   Google Business Profile logo, delivery-app listing icon, and — for field-intake —
   the **signage in a storefront photo**.
3. Compare: wordmark text, icon/emblem shape, and color palette. Sample 2–4 hex values
   from each and compare.

**Pass:** same wordmark + same icon + same palette. **Near-match (record, don't
equate):** same name but different styling — likely an **old logo vs a rebrand**, or a
third party using the name. Note it as `logo: near-match (rebrand?)`. **Fail:**
different mark entirely → strong disqualifier for that account.

Record: what each mark shows, the palette hexes, and pass / near-match / fail.

Note: you are comparing a *business logo* to a *business logo*. This is brand
verification, not facial recognition — never use this test to identify a person.

---

## Test 3 — Photo / Video match

**Goal:** confirm the account's media depicts *this* business, and separate the
operator's own account from UGC.

Method:
1. Pick 1–3 distinctive images/clips from the account (interior with signage,
   storefront, a signature dish, the team).
2. Cross-reference against known-good media: GBP photos, the business's own site,
   delivery-app item photos, a field-intake storefront photo. Same room, same signage,
   same plating?
3. **Reverse image search** (browser, `claude-in-chrome`):
   - `navigate` → `https://www.google.com/search?tbm=isch` and use "Search by image",
     or `https://lens.google.com/`, or `https://tineye.com/`.
   - Where else does this exact image appear? If it also appears on the business's
     **own** other profiles → corroborating (same operator). If it appears as **stock**,
     on an **unrelated** business, or as a press/agency image → the account may be
     reposting, not the operator → disqualify or downgrade.
4. For **video**: match visible location/interior/signage/menu boards in the clip to
   known-good imagery; note anything filmed on-site vs a generic reshare.

**Pass:** distinctive media provably depicts the business (matches known-good and/or
appears across their own surfaces). **UGC flag:** media is about the business but the
account is a customer's — record `UGC — not operator-owned` (useful social proof, not
an official account). **Fail:** media is stock/stolen/another business.

Record: which media, where else it appears (reverse-search result), own vs UGC vs
stolen.

Rights note (for downstream media harvest): tag each usable asset `OWN` /
`UNCLEAR` / `CLIENT-UPLOAD` exactly as `custom-lead-generator`'s media-harvest does —
Profiler *verifies ownership of the account*, it does not grant rights to publish the
files.

---

## Test 4 — Account ↔ Website cross-link

**Goal:** find mutual linkage between the account and the business's website — the
strongest single tie when present.

Method:
1. On the **website**: read the header/footer for social icons; view source for
   `<a href>` to instagram/tiktok/facebook and for social `og:`/`twitter:` meta tags.
2. On the **account**: the link-in-bio (Test 1) — does it point back to that same
   domain?
3. Cross-check the **delivery-app / Owner.com listing** for linked socials too.

**Pass (near-conclusive):** two-way — site links the account AND the account links the
site, both on operator-controlled surfaces. **Strong-but-confirm:** one-way linkage.
**None:** no linkage found (doesn't disprove a match; just carries no weight here).

Record: site→account links found, account→site link, one-way vs two-way.

---

## Test 5 — NAP consistency

**Goal:** confirm Name-Address-Phone agree across independent sources (classic entity
resolution).

Method:
1. Pull the N-A-P trio from every source you reached: own site / Owner.com, GBP, Yelp,
   Facebook About, delivery apps — and for **real estate**, the county assessor /
   recorder (owner name + mailing address) and any registered business filing.
2. Normalize (suite numbers, "St" vs "Street", formatted phone) and compare.

**Pass:** N-A-P agree across ≥2 **independent, operator-controlled** sources
(aggregators corroborate but don't count as operator-controlled on their own).
**Conflict (flag, don't smooth):** two different phones or addresses → record as a
conflict to resolve — rebrand, second location, closed/reopened, or two entities
sharing a name. Never average or pick one silently. **Unknown:** trio incomplete
across sources.

Record: the N-A-P from each source, agreement/conflict, and the flag if conflicting.

---

## Reverse-image search — the browser recipe

Reverse search is the one test that genuinely needs the browser. Headless/cron runs
can't drive it — there, note "reverse-search unavailable this run" and lean on Tests
1, 2, 4, 5 (do not claim a photo is verified without running the search).

```
tabs_context_mcp → tabs_create_mcp
navigate → https://lens.google.com/    (or images.google.com → camera icon, or tineye.com)
upload the candidate image (file_upload / the page's upload control)
read_page / get_page_text → collect the domains/pages where the image appears
```

Interpretation: appears on the business's own profiles → corroborates ownership;
appears on stock sites / unrelated businesses / news agencies → the account is
reposting, not the operator. Keep it to *business* verification — never reverse-search
a person's face to identify or locate an individual (`guardrails.md`).

## Which tests to run

- **Just a handle** → 1, then 2/3/4/5 as the profile exposes them.
- **A storefront/field photo + address** → 2 (signage logo) + 3 (photo depicts place)
  + 5 (address); 1/4 if an account is also in hand.
- **A logo file** → 2, plus 1/4 to find the account/site it belongs to.
- **A phone or email** → reverse it (search the number/email as a string) to find the
  listing that carries it, then 5 to confirm it's the same entity across sources.
- **A pile of profiles to de-dupe** → 1 on each, then 2/4/5 to decide which are the
  same entity; emit the Match Sheet.
