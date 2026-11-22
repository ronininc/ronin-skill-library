# Buy-Box — orosolu.org default target (orosolu-restaurant v1)

The buy-box defines who counts as a prospect during a **prospecting scan** — before
you look at any specific shop, so you can't reverse-engineer the criteria to fit
whoever you happened to find. It's also what tiers a **targeted** shop so you know
its priority. This is the shipped default: the exact restaurant Owner.com goes
after. To target another vertical, copy this file, change the values, bump the
version, name it in the run header (see `config.md`). **Record the buy-box
name+version on every lead.**

## Ideal Customer Profile (who we want)

An **independent, owner-operated restaurant** — typically 1–5 locations, not a
national chain or franchise of a major brand — with:

- **Real, proven demand** they already capture (they have customers), but
- **Margin leaking to third-party delivery** (on DoorDash / Uber Eats / Grubhub,
  paying ~15–35% per order), and
- **Weak or no first-party ordering** — you can't order directly on their own site;
  ordering happens only through marketplaces or by phone, and
- **Poor discoverability** — no optimized website (Facebook-only, stale template, or
  nothing) and weak Google presence.
- **A reachable decision-maker** — owner/operator name and a business phone/email
  outreach can land on.
- **Takeout-friendly cuisine** — pizza, Mexican, wings, burgers, sandwiches, Asian,
  BBQ, breakfast, bowls (formats that do real off-premise volume).

Bullseye: a busy, well-reviewed independent already doing delivery volume through
the apps but keeping none of the customer relationship and paying a tax on every
order. Highest need, highest close — exactly what orosolu.org fixes.

## Disqualifiers (any one → DROP, reason recorded, no deep dive)

Drops are dropped *before* the expensive deep dive — no point harvesting media for a
shop you'd never build for.

- **National chain or franchise of a major brand** (they have corporate tooling).
- **Permanently or temporarily closed / not operating.**
- **Already on first-party ordering + loyalty** (already running Owner.com or an
  equivalent direct-ordering + marketing stack) — low remaining need. Note which.
- **No off-premise business at all** — reservations-only fine dining with no
  takeout/delivery, or a format where online ordering doesn't apply.
- **Not a real, current business** at a real address.

## Scoring dimensions and weights

Each dimension scores 0–5 from evidence (anchors in `scoring-rubric.md`) × weight.
Weights sum to 20 → a 0–100 score.

| # | Dimension | Weight | Measures |
|---|-----------|:------:|----------|
| 1 | Third-party dependence | 4 | Reliance on delivery marketplaces (presence + count). Higher = more margin to win back. |
| 2 | Direct-ordering gap | 4 | Absence/weakness of ordering on their *own* site. Higher = bigger fix we sell. |
| 3 | Discoverability gap | 3 | Weak website / SEO / Google Business Profile. |
| 4 | Demand proof | 4 | Review volume × rating — real traffic worth converting. |
| 5 | Reachability | 3 | Quality of decision-maker contact available. |
| 6 | Fit | 2 | Independent, right size, takeout-friendly cuisine. |

Dimensions 1–5 are **core** (their `Unknown` count drives the `INCOMPLETE` gate).
Fit is a modifier. Weights are tunable policy — change them here between runs, never
mid-run, and bump the version.

## Outreach angle — the offer (draft only, approval-gated)

The pitch is not "let us build you a site." It's **"your site is already built —
it's yours when you process payments with orosolu."** The prebuilt site (populated
from their own photos/videos) is the hook; card processing is the product.

- **Open with the built site:** "We already built your site — your name, your menu,
  your photos. Here's the link." (Show, don't offer.)
- **The gap → the offer:** name what they lack — "no way to order on your own site"
  or, stronger, "you're cash/Zelle only, you can't even take a card" — then: "move
  your processing to us and this goes live, free, with card + commission-free online
  ordering built in."
- **Proof (their demand):** cite the real number the deep dive pulled — "4.6★ across
  640 reviews; you've got the demand."
- **Ask:** a short call to switch processing and flip the site live.

Never invent the numbers or the gap. If a claim is `Unknown`, soften it or route the
lead back to enrichment — do not assert it. The strongest prospects are shops that
**can't take a card today** (cash/Zelle only): the offer is "take cards *and* get a
site."
