---
name: public-relationship-graph
description: >-
  The "who-can-help-me" engine: take a person or org name and pull its RELATIONSHIP GRAPH from a
  public-accountability dataset (board seats, executive positions, memberships, ownership stakes,
  professional / family / donation ties), then normalize every edge to a warm-introduction view —
  "our role / their role / the related entity" — with WARM business categories (board, exec,
  ownership, professional, hierarchy) ranked and surfaced first, orgs and connected people split
  out, and a bounded, polite resolver so a non-profit API isn't hammered. Answers "the butcher's
  son sits on a bank board" from PUBLIC filings, not a personal skip-trace. Use WHENEVER a build
  must "find a warm path to X", "who does this person/company know", "map their board / ownership /
  professional ties", "who can introduce me", "escalate this brand to its parent / its execs", or
  "give me the relationship graph for this lead". COMPLEMENTS multi-source-identity-resolver
  (which resolves WHO the person is across platforms — this maps who they're CONNECTED to),
  reference-intel-matcher (match a resolved tie back to a curated roster of targets), and
  az-cash-buyer-finder / geo-directory-prospecting (which SOURCE the entities this runs against).
  Guardrails: BUSINESS relationship-mapping only — no personal skip-tracing; every tie is PUBLIC
  RECORD as the source has it and is a CANDIDATE to verify before acting; nothing is fabricated;
  identify yourself and rate-limit as a polite citizen of a non-profit API.
---
# Public Relationship Graph

## What it is / when to use / what it composes with
Given a name, resolve it to an entity in a public-accountability graph, pull its relationships, and
normalize them into a **warm-path** shape a salesperson or an outreach brain can act on: who this
entity is tied to, in what role, and whether the tie is a *warm* business signal (a board seat, an
executive position, an ownership stake, a professional relationship) or merely incidental. It turns
"cold name" into "here are the boards they sit on and the people/orgs they're connected to, warm
ones first."

- **Not `multi-source-identity-resolver`:** that answers "who is this handle, across platforms."
  This answers "who is this known person/org CONNECTED to, and which ties are actionable."
- **Feeds `reference-intel-matcher`:** a surfaced connected entity can be matched back to a curated
  roster of targets ("this lead's professional tie is one of our whales").
- **Runs against entities from `az-cash-buyer-finder` / `geo-directory-prospecting`** and behind
  `residential-edge-relay` when a Worker CRM enqueues the lookup.

## Reference implementation — exact source (lift the proven code)
`~/ronin-osint/littlesis.py`:
- **Edge taxonomy + warm set:** `CATEGORIES` (id → human label) `littlesis.py:25-29`; `WARM` = the
  category ids that signal an actionable business tie (Position, Membership, Professional, Ownership,
  Hierarchy) `littlesis.py:31`.
- **Polite API client:** `get()` sends an identifying User-Agent `littlesis.py:22`,`34-37`.
- **Bounded, deduped, rate-limited resolver:** `resolve_names(ids, warnings, cap=60)` — de-dupes
  with `dict.fromkeys`, caps how many related entities it resolves, sleeps 0.12s between calls to be
  a polite citizen of a non-profit API — `littlesis.py:48-58`.
- **Subject resolution:** by id or by top search hit — `littlesis.py:74-86`.
- **Warm-first ordering + cap:** sort relationships so WARM categories come first, then take the top
  `--max-rel` — `littlesis.py:98-99`.
- **Edge normalization (the key transform):** for each edge decide which side is the subject, emit
  `{category, our_role, their_role, related:{id,name,type,blurb}, is_current, description}` —
  `littlesis.py:101-120`. This is the "our role / their role" symmetry that makes an undirected
  filing readable as a warm path.
- **Summary rollup:** count by category, collect `boards_positions`, split `connected_people` vs
  `orgs` — `littlesis.py:121-131`.
- **Envelope:** `…/relationships@1`, `confidence:"candidate"`, a "verify before acting / no personal
  skip-tracing" note — `littlesis.py:133-146`.

## How to reapply — the schema + THE INVARIANT
1. **Two-hop pull:** resolve the subject entity, fetch its relationships, then batch-resolve the
   *other* endpoint of each edge to a name/type/blurb (`littlesis.py:100-105`).
2. **Normalize each edge to the warm-path shape** with explicit `our_role`/`their_role` so direction
   is legible regardless of how the source stored `entity1`/`entity2` (`littlesis.py:106-120`).
3. **Rank warm-first** and cap volume so the output is a usable shortlist, not a data dump
   (`littlesis.py:98-99`). Roll up a summary the UI can show at a glance (`littlesis.py:121-131`).
4. **Ship `…/relationships@1`** into the same `lead_dossiers` review→import path as the identity
   dossier; an operator confirms a tie before it's used for outreach.

**THE INVARIANT:** every edge is PUBLIC RECORD exactly as the source holds it — a CANDIDATE to
verify, never proof, and never a personal skip-trace. Warm ranking orders the shortlist; it does not
upgrade a tie's certainty. Business relationship-mapping only.

## Gotchas — real pitfalls from the code + how it's validated
- **Undirected edges.** The source stores a tie as `entity1`↔`entity2` with two role descriptions;
  you must pick the subject side to render "our role" vs "their role" correctly
  (`littlesis.py:103-118`). Getting this backwards mislabels every relationship.
- **Be a polite API citizen.** Cap the resolves and sleep between them (`littlesis.py:51`,`57`) — a
  non-profit dataset will (rightly) throttle a hammer, and the tool identifies itself by UA
  (`littlesis.py:22`).
- **Search picks the top hit only.** Name → entity uses the first search result
  (`littlesis.py:81-84`); a common name can resolve to the wrong entity. Support `--id` to pin the
  exact entity, and treat a name-only resolution as lower confidence.
- **Sparse graphs are normal.** Many small-business owners aren't in an accountability dataset at
  all — an empty graph is an honest "no public ties found," not a failure. Warnings capture partial
  resolve failures without aborting (`littlesis.py:55-56`).
- **Don't cross the line.** The point is board/ownership/professional escalation from public filings;
  it is explicitly not a personal skip-trace. Keep any new source on that side.
