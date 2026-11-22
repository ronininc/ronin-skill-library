# Handoffs — vertical config + feeding the lead-gen engines

Profiler is the identity layer *under* the two lead-gen engines. It rarely ships work
alone — it resolves an entity and hands the resolved, contactable entity up so the
right shop gets built for or the right owner gets a deal. This file is the config knob
and the two handoff contracts.

## Vertical config

Pick the target from the fragment; it only changes the corroborating record set, never
the five tests or the scoring.

| | Restaurant / local shop | Real-estate owner / investor |
|---|---|---|
| Anchor sources | Owner.com / own site, GBP, delivery apps, IG/TikTok/FB, Yelp | County assessor + recorder, business filings, people-search, socials |
| Entity is | the business | the property owner (person or LLC) as deal counterparty |
| Contact source | operator surfaces (`contact-enrichment.md` §restaurant) | assessor mailing address + skip trace (`§real-estate`) |
| Hands off to | `custom-lead-generator` | `wholesale-real-estate` |

To retarget to a new vertical (contractor, clinic, e-comm), swap the anchor source
row; everything else is identical.

## Handoff → custom-lead-generator (restaurant)

When Profiler was called to answer "is this account/media/number really this shop"
during a lead run, hand back **inline** (not a separate file):
- Resolved entity name + which single business, with the entity tier and firing rule.
- The five-test evidence grid (so the deep dive doesn't re-derive it).
- Confirmed socials (own vs UGC flagged) → these wire straight into the media harvest
  and the site's social slots.
- Contact block with per-item tiers + the DNC/10DLC/CAN-SPAM stamp.
- Any `UNCLEAR`/`OWN`/`CLIENT-UPLOAD` rights flags already noted on media.

`custom-lead-generator` then runs its deep dive / Build Brief on the *right* entity,
never a same-name shop at the wrong address.

## Handoff → wholesale-real-estate (owner)

When Profiler resolved an owner/entity for a deal, hand back:
- Owner name + mailing address (assessor-sourced) + entity tier.
- Skip-traced phone/email with tiers and the compliance stamp — drops into the CRM
  contact columns (`assets/lead-sheet-template.csv`), `Unknown` where unconfirmed.
- Any LLC → registered-agent resolution.
- Conflicts flagged (two mailing addresses, name mismatch on the deed) for Stage 3/5.

## Standalone runs

When the ask is *only* identity resolution ("de-dupe these 40 profiles", "whose number
is this", "confirm we have the right entity before we pitch"), Profiler ships its own
deliverables — the Identity Match Dossier per fragment and, for a batch, the Match
Sheet — via `SendUserFile`, and stops there. No downstream skill fires without a yes.

## Never do on handoff

- Never hand off an `Unknown`/`ambiguous` entity as if resolved — pass it as
  unresolved with the tie-breaker note.
- Never trigger the downstream skill's outreach/writes/spend; handoff is data, not an
  action.
