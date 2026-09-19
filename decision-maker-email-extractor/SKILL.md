---
name: decision-maker-email-extractor
description: >-
  A standalone enrichment atom that finds the actual OWNER/CEO/principal of a business — not the
  generic info@ box — from public pages only, then name-matches a person-specific mailbox. It parses
  schema.org Person JSON-LD for a decision-maker job title, falls back to a role±name regex over
  readable page text, follows /about /team /leadership /staff pages, and matches a harvested email to
  the person by first/last-name tokens (flagging inferred addresses do-not-send-without-verification).
  Use WHENEVER a lead needs "find the owner / decision-maker", "who runs this business", "get the CEO's
  email not info@", "the principal's contact", or personalizing outreach to a real named person. It is
  the delta ON TOP of contact-enrichment-deliverability (which grades whether an address is
  DELIVERABLE) and lead-qualifier (which scores fit) — this atom answers WHO and WHICH mailbox; do NOT
  re-implement their MX/SMTP verification or fit scoring here. Pairs with geo-directory-prospecting and
  open-data-signal-discovery (the businesses it runs against). Guardrails: public pages only, strict
  person-name validation to reject "About Us"/"Our Team" false positives, and a hard rule that a
  name-inferred mailbox is a CANDIDATE to verify, never a confirmed send target.
---
# Decision-Maker & Email Extractor

## What it is / when to use
A small, composable extractor: given a business website, return `{name, title, source, email}` for the
most senior public contact, or nothing. Two independent techniques, JSON-LD first (authoritative) then
a text regex (best-effort), across the homepage and up to two likely team pages. It exists so outreach
can address a real person ("Hi Maria,") instead of a role box, which measurably lifts reply rates.

**Composes with:** `contact-enrichment-deliverability` (run this to pick WHO, then that skill verifies
the address is deliverable — the two are designed to chain), `lead-qualifier` (fit), and any sourcing
skill (`geo-directory-prospecting`, `open-data-signal-discovery`) that produces the `businesses`/
candidate rows. This atom owns **person identification + name→mailbox matching only**; it does not
grade deliverability, score fit, or send.

## Reference implementation (ronininc)
Two source homes for the same pattern — confirmed read:
- `worker/lead-generation.ts` L256-352 — the self-contained version used inside the (WIRED)
  geo-directory workflow:
  - `DECISION_ROLE` L256 — the role vocabulary: `Owner|Founder|Co-Founder|President|CEO|Chief Executive
    Officer|Managing Partner|Principal|General Manager|Executive Director|Director`.
  - `readableText()` L258-264 — strips script/style/tags to newline-delimited text for the regex pass.
  - `validPersonName()` L266-270 — `^(Cap word ){1,3}Cap word$` AND rejects a leading
    `About|Contact|Meet|Our|The|Learn|General|Executive|Managing` — this is what keeps "Our Team" or
    "Meet Sarah" section headers from being read as a person.
  - `decisionMakerFromPage()` L272-306 — (1) scans every `ld+json` script, recursively inspects for a
    `@type:Person` whose `jobTitle` matches a decision role and whose `name` validates; (2) falls back
    to two regexes over readable text: `NAME [-–—|,:\n] ROLE` and `ROLE [-–—|,:\n] NAME`, picking the
    person side by which capture matched the role.
  - `likelyTeamPages()` L308-321 — collects ≤2 same-origin links whose path starts
    `/about|/team|/leadership|/staff|/company`.
  - `directEmail()` L343-352 — the name→mailbox matcher: tokenize the person's name, return the first
    harvested email whose local-part contains the first (len>2) or last (len>2) name token, else the
    first email as fallback.
- `worker/discovery/enrichment.ts` L61-96 (JSON-LD `addJsonLd` Person capture into `people`) + L203-210
  (`inferredEmails`: `first.last@domain` construction) — the same idea inside the enrichment spine,
  where a name-inferred address is written at confidence 0.25 with
  `do_not_send_without_further_verification:true`.

## How to reapply it
1. **Lift the four pure functions** from `lead-generation.ts` (`DECISION_ROLE`, `readableText`,
   `validPersonName`, `decisionMakerFromPage`, plus `likelyTeamPages` + `directEmail`). They have no
   dependencies and no schema — they operate on an HTML string and an email list.
2. **Feed it fetched HTML.** Reuse a byte-capped, SSRF-guarded fetch (`fetchPublicHtml` L323-341 here,
   or `extractPage` from contact-enrichment-deliverability). Fetch the homepage, then each
   `likelyTeamPages` URL (best-effort — a failed team page must not reject the lead).
3. **Order matters:** JSON-LD Person wins; only fall through to the text regex when structured data is
   absent. Take the first decision-maker found and stop.
4. **Name→mailbox:** run `directEmail(harvestedEmails, person.name)`. If the match is a *constructed*
   `first.last@domain` (not seen on the page), tag it
   `do_not_send_without_further_verification` and hand it to contact-enrichment-deliverability before
   any send.
5. **Store provenance:** persist `decision_maker_name/title/source` (the page URL where found) — the
   geo workflow puts these on `campaign_recipients` (`decision_maker_title/decision_maker_source`) so
   the operator can audit why a name was attributed. Add a `decision-maker:<title>` tag to the contact.

## Gotchas (from the code)
- **False positives are the enemy.** Without `validPersonName`'s leading-word rejection, "Meet Our
  Team", "About Sarah", "Executive Summary" all parse as names. Keep the blocklist; extend it for the
  client's language/section conventions.
- **Regex ordering ambiguity:** the text pattern must detect which capture group is the role vs the
  name (L300-302 checks `^ROLE$` on group 1) — a title like "Director" can appear on either side of the
  separator. Don't assume name-first.
- **A constructed mailbox is a hypothesis, not a contact.** `directEmail` falls back to `emails[0]` and
  the enrichment path constructs `first.last@` — both are unverified. Confidence 0.25 exists precisely
  so nothing downstream treats them as deliverable. Chain contact-enrichment-deliverability's MX/SMTP
  check before sending.
- **Only public pages.** No login-walled directories, no scraping LinkedIn behind auth — JSON-LD +
  the business's own about/team pages only. This keeps it ToS-clean and privacy-defensible.
- **`Director` is the weakest role** in the vocabulary (many non-owners are "Director of X"); if you
  need only true principals, trim `DECISION_ROLE` to owner/founder/president/CEO/managing-partner.
