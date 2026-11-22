# Contact Enrichment — email / phone, per vertical, with the honest ceiling

Once the entity is `Confirmed`/`Likely`, get reachable, correct contact info. This
mirrors `custom-lead-generator`'s recon (restaurant) and `wholesale-real-estate`
Stage 3 (owner skip trace), unified here. Two rules dominate everything below:
**never synthesize a contact**, and **stamp the compliance obligation** on anything
meant for outreach.

## Restaurant / local-shop (orosolu / Owner.com target)

Pull from operator-controlled surfaces first, in priority order:
1. Own website / Owner.com contact or footer — business phone + email.
2. Google Business Profile — the canonical public phone.
3. Facebook "About", Instagram bio, Yelp business page.
4. Delivery / ordering platform listing (Owner.com, DoorDash, Toast, Square, Clover).

Tier each item per `confidence-scoring.md`: `Confirmed` = same value on ≥2 operator
surfaces; `Likely` = one operator surface; `Possible` = aggregator only; `Unknown` =
not found. A general info@ / hello@ address on their own site is `Confirmed`; a guessed
`owner@theirdomain.com` is **`PATTERN-GUESS — unverified`**, never presented as real.

## Real-estate owner / investor (wholesale target)

The counterparty is the property owner. Follow `wholesale-real-estate` Stage 3
doctrine:
1. From the resolved entity take `owner name` + `property / mailing address` (assessor
   is the source of the mailing address — free, authoritative).
2. Best-effort skip trace phone/email against **public people-search aggregators +
   public records**. Corroborate with a second source.
3. Tier: `Confirmed` (2+ sources agree) / `Likely` (1 source) / `Unknown`. **Never**
   complete a partial number or invent one. A blank beats a wrong-party call.
4. For an LLC/business owner, resolve the registered agent / business filing for a
   business contact rather than probing a private individual.

## Accuracy ceiling — say it to the operator

Free/public lookups return partial or stale numbers and lower hit rates than paid
data. For real volume the standards are, by vertical:
- **Business contact:** the operator's own surfaces are usually enough; for scale,
  data providers exist but the public surfaces are the source of truth here.
- **Owner skip trace:** BatchSkipTracing, Skip Genie, IDI/LexisNexis; bundled into
  PropStream, BatchLeads, DealMachine. Recommend paid the moment the list is more than
  a few dozen rows. (Same guidance as `wholesale-real-estate`.)

State plainly when the free method has hit its ceiling — overclaiming a hit rate costs
the team money and wrong-party contacts.

## Reverse-lookup a number or email you were handed

If the *fragment* is a phone or email (not an account), enrich in reverse: search the
value as a string (`"(602) 555-0143"`, `"info@shop.com"`) to find the listing/profile
that carries it, then run Test 5 (NAP) to confirm it belongs to the entity across
sources. A number that appears only on one scraper and nowhere operator-controlled is
`Possible`, not `Confirmed`.

## Compliance stamps (attach to every outreach-bound contact)

You surface contact info; the operator is responsible for lawful use. Stamp the
dossier's contact block with:
- **Phone (calls):** must be scrubbed against the **DNC registry** before dialing.
- **Phone (SMS):** requires **10DLC** carrier registration; consent rules apply.
- **Email:** **CAN-SPAM** — accurate header/subject, physical address, working
  unsubscribe.
- **General:** TCPA governs calls/texts. Profiler does not send; it drafts and hands
  off, and sending needs explicit approval (`SKILL.md` directive 6).

Do not skip-trace or enrich for any purpose other than legitimate business outreach.
