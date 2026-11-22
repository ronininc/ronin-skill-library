# Lead Sheet — the prospecting-run output (ranked list, each linked to a Build Brief)

A prospecting scan delivers a **lead sheet**: one ranked row per shop found. Because
every qualified/targeted shop also gets the deep dive, each qualifying row **links to
that shop's Build Brief + Media Manifest** — the lead sheet is the index, the Build
Briefs are the depth. (A single targeted deep dive skips the sheet and just produces
the Brief.)

## Run header (top of the sheet)

```
RUN: <date>  ·  mode: prospecting  ·  vertical: <e.g. independent restaurants>
geography: <city/ZIP/radius>  ·  buy-box: <name vX>  ·  wanted: <N qualified>
delivered: <A>/<B>/<C>/<DROP>/<INCOMPLETE>  ·  deep-dives produced: <count>
sourced-from: <maps, delivery-app category pages, directories used>
platform: orosolu.org
```

## Columns (ranked A→B→C, then INCOMPLETE, DROPs last)

| Column | Contents |
|--------|----------|
| Rank | within tier |
| Business | display name |
| Tier | A / B / C / INCOMPLETE / DROP |
| Score | 0–100 (blank for disqualifier DROP) |
| Top gap / hook | strongest evidenced reason (e.g. "on 3 apps, no own-site ordering, 640 reviews @4.6★") |
| Location | city / neighborhood / address |
| Cuisine / type | as they really operate |
| Decision-maker | owner/manager if found, else `Unknown` |
| Contact | email / phone / form — each verified or `Unknown` |
| Own-site ordering | none / marketplace-only / weak / strong |
| Delivery apps | which marketplaces list them |
| Demand | review count + rating, with source |
| Status/gate | qualified / `DROP: <reason>` / `INCOMPLETE: <missing dims>` |
| Deep dive | link/path to this shop's Build Brief + Media Manifest (or "—" for DROP) |
| Buy-box | name vX used |
| Sources | links to profiles actually read |

Deliver as `.csv`/`.xlsx` (use the `xlsx` skill for a workbook) or `.md`.

## The auto-deep-dive rule

- **Every qualified (A/B/C) and every targeted shop gets a deep dive** → its own
  Build Brief + Media Manifest, per the main workflow. That's the orosolu.org
  promise: not just a name on a list, a shop ready to build.
- **DROP shops do not get a deep dive** — a disqualified prospect (chain, closed,
  already handled) isn't worth harvesting. The row records why.
- **INCOMPLETE shops** get a light dive at most (whatever was reachable) and their
  Open Items name what's missing before they can advance.
- On a **large scan**, if you cap how many deep dives run in one pass, `log` the cap
  plainly (e.g. "deep-dived top 15 A/B; 22 more queued") — never present a partial
  batch as if every shop was fully worked.

## Nothing hidden

INCOMPLETE and DROP rows still ship, with their reasons. A transparent short list
beats a padded false one — the "no fake completion" rule at the artifact level.
