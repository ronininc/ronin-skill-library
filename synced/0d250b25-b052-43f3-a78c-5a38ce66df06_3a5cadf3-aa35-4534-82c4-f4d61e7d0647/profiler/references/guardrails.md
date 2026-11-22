# Guardrails — not optional reading

Profiler resolves **businesses**. Its power — reverse image search, cross-source
matching, contact enrichment — is exactly the power that, pointed at a private
individual, becomes surveillance. These rules keep it on the business side of that
line. If a request would cross the line, do the business-side part and decline the
rest, plainly.

## The line

- **Resolve businesses, not private people.** The target is always a business entity:
  a shop, a restaurant, an LLC, a property-owner-as-counterparty. You may tie an
  account/logo/photo/number to *a business* and pull *that business's* contact info.
  You may not build a profile of a private person's life.
- **Public sources only.** Public profiles and public records (assessor, recorder,
  business filings, GBP, socials set to public). No login-walled content, no
  friends-only posts, no paywalled personal data.
- **No access-control bypass, ever.** If `WebFetch`/`WebSearch`/the browser is blocked,
  robots-disallowed, or login-walled, that field is `Unknown`. Never route around it
  with curl/wget/scripts/HTTP libraries, never scrape behind a login, never defeat a
  captcha or rate limit. (This matches every other house skill.)
- **Reverse image search is for business verification.** Use it to check whether a
  *photo of a place/food/logo* belongs to the business or is stock/stolen. Never
  reverse-search a **person's face** to identify, locate, or profile an individual.

## Never surface or store (even if a source exposes it)

Protected and sensitive personal data about any individual — race, religion, sexual
orientation, gender identity, immigration status, disability or health, union
membership; political affiliation; criminal history; government ID / SSN; card or
bank numbers; personal date of birth; and **real-time location** ("where they are
right now"). If matching happens to pass through such data, use only the minimal
business fact (e.g. "owner name → mailing address on the deed") and drop the rest.

For real-estate owners specifically: the public record gives you owner name and
mailing address for a legitimate real-estate transaction. That is the ceiling. Do not
extend it into relationships, employer, movements, or anything the deal doesn't need.

## Same-entity discipline (the accuracy guardrail)

- **Never force a match.** No answer (`Unknown`/`ambiguous`) is a valid, correct
  output. A confident wrong match is the worst outcome — it sends real outreach,
  money, and a site build at the wrong party.
- **Never collapse two entities** that share a name to produce a single verdict.
- **Never smooth a NAP conflict** — flag it for a human.
- **Never present `PATTERN-GUESS` or single-aggregator contact as `Confirmed`.**

## Outreach / writes / spend

Resolving and drafting are free and need no approval. **Sending** a message, **writing**
to a CRM, or **paying** for a lookup each need an explicit yes in the run. Profiler
produces the dossier; it does not act on it unprompted.

## If a request crosses the line

Do the legitimate business-resolution part, and decline the rest in one sentence
naming what you won't do ("I can confirm which business runs that account and pull its
public business number; I won't reverse-search the owner's face or compile a personal
profile"). Don't lecture; just hold the line and deliver what's in bounds.
