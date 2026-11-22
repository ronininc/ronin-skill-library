# Identity Match Dossier — <fragment>

> One dossier per fragment resolved. Fill every field you can from evidence read THIS
> run; mark the rest `Unknown`. The tier must fall out of the evidence grid via
> `references/confidence-scoring.md` — write the firing rule.

## Fragment handed in
- **Type:** (handle / logo / photo / video / phone / email / website / storefront photo)
- **Value:** `...`
- **Vertical / target:** (restaurant · orosolu/Owner.com) or (real-estate owner · wholesale)
- **Question being answered:** e.g. "is this IG really Cornish Pasty Co?"

## Verdict
- **Resolved entity:** `<business / owner name>`  — or `Unknown` / `ambiguous`
- **Entity confidence tier:** `Confirmed` / `Likely` / `Possible` / `Unknown`
- **Firing rule:** e.g. "rule 2 — two-way link + logo match"
- **If ambiguous:** candidate A vs candidate B, and what would break the tie.

## Five-test evidence grid (record the OBSERVATION, not the conclusion)
| Test | Ran? | What was observed | Result |
|------|------|-------------------|--------|
| 1. Account → Business | | handle/bio/link-in-bio target/tagged location | pass / ambiguous / n/a |
| 2. Logo match | | wordmark + icon + palette compared vs which surface | pass / near-match(rebrand?) / fail / n/a |
| 3. Photo / video match | | which media, reverse-search result (where else it appears) | own / UGC / stolen / n/a |
| 4. Account ↔ website | | site→account links, account→site link | two-way / one-way / none / n/a |
| 5. NAP consistency | | N-A-P from each source; agree or conflict | agree / conflict / partial / n/a |

## Conflicts flagged for a human
- (e.g. two different phones across sources; second location; possible rebrand) — or "none"

## Contact block (each item tiered; stamp compliance)
| Item | Value | Tier | Source(s) |
|------|-------|------|-----------|
| Business / owner phone | | Confirmed/Likely/Possible/Unknown | |
| Email | | Confirmed/Likely/Possible/PATTERN-GUESS/Unknown | |
| Mailing address (real estate) | | | assessor |

**Compliance stamp:** phone → DNC-scrub before calling; SMS → 10DLC registration;
email → CAN-SPAM (unsubscribe + physical address). Operator is responsible for lawful
use; Profiler does not send.

## Confirmed socials (own vs UGC)
- Instagram: @… — own / UGC
- TikTok: @… — own / UGC
- Facebook: … — own / UGC
- (media rights already flagged OWN / UNCLEAR / CLIENT-UPLOAD for downstream harvest)

## Handoff
- To: `custom-lead-generator` / `wholesale-real-estate` / standalone
- Passed: resolved entity + tier + evidence grid + contact block. Outreach/writes/spend
  NOT triggered (needs explicit yes).

## Sources
- <markdown links to every profile / record actually read this run>
