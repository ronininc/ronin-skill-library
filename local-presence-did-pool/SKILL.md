---
name: local-presence-did-pool
description: >-
  A caller-ID reputation manager for an outbound calling platform, pure D1, no third-party dependency: a pool
  of local-presence phone numbers (DIDs) from which the dialer presents a HEALTHY number local to the person's
  state, spread least-recently-used so no single number gets burned by volume, with a health ladder
  (good -> flagged -> spam -> retired) and a reputation-ingest seam that flips a number's health and rotates it
  out of service automatically from a provider spam-label feed (First Orion / Numeracle) or a manual report.
  Use WHENEVER an outbound dialer needs better answer rates and clean caller-ID reputation — "local presence
  dialing", "rotate our phone numbers so they don't get flagged as spam", "our numbers are marked spam likely",
  "DID pool / number pool management", "present a local area-code number", "burn down / retire a flagged
  number", or "ingest a spam-reputation feed". It COMPLEMENTS pluggable-voice-carrier (it supplies the
  `fromPool` DID that carrier's `placeCall` dials from) and predictive-dialer-pacing (clean numbers keep the
  answer rate — and therefore the safe over-dial ratio — up). Dormant-safe: with an empty pool `pickDid`
  returns null and the carrier falls back to its default caller ID; the reputation feed is optional/config-driven.
---
# Local-Presence DID Pool (caller-ID reputation + LRU rotation)

## What it is / when to use / what it composes with
Answer rates live and die on caller-ID reputation. This is the owned, provider-independent layer that (a)
presents a number local to the called party's state, (b) spreads usage so no number is over-dialed into a
spam flag, and (c) reacts to spam-label feedback by pulling burned numbers automatically. Pure D1 + auditable.

- **Composes with**: `pluggable-voice-carrier` (`pickDid` output becomes `placeCall({fromPool})`),
  `predictive-dialer-pacing` (reputation protects the answer rate the pacer trusts), `append-only-audit-log`.

## Reference implementation (exact source)
- Whole module: `/Users/robbiebrown/Projects/case-plug/src/did-pool.js` (78 lines).
  - `pickDid(state)` — GOOD + state-local, **least-recently-used first**, falls back to any GOOD, else null;
    stamps `last_used_at` on the chosen number: `did-pool.js:19-30`.
  - `addDids` (derives area_code from the number, INSERT OR IGNORE): `:32-46`.
  - `markHealth` (good|flagged|spam|retired): `:48-54`.
  - `ingestReputation(signals, threshold)` — score → health flip + rotate out: `:56-69`.
  - `listDids` (with per-health counts): `:71-78`.
- Consumed in the dial path (campaign pool first, else `pickDid` for the lead's state): `src/calls.js:82-86`;
  management endpoints `GET/POST /call/dids`, `/call/dids/health`, `/call/dids/reputation`: `src/calls.js:191-206`.
- Schema: `did_pool(did PK, state, health CHECK IN ('good','flagged','spam','retired'), area_code,
  last_used_at, spam_score, carrier)` + index `(state, health, last_used_at)`: `schema.sql:254-258`.

## How to reapply
1. **Schema**: `did_pool` as above; the composite index on `(state, health, last_used_at)` is what makes the
   LRU-by-state pick a single indexed lookup.
2. **Pick**: `SELECT did FROM did_pool WHERE health='good' AND state=? ORDER BY (last_used_at IS NULL) DESC,
   last_used_at ASC LIMIT 1` (never-used first, then oldest), fall back to any GOOD, else return null; then
   stamp `last_used_at` so the next pick rotates on. Return the DID as the carrier's from-number.
3. **Health ladder**: `good → flagged` (early spam signal, deprioritized) `→ spam` (pulled from rotation) `→
   retired` (removed). Only `good` numbers are ever picked.
4. **Reputation ingest** (dormant seam): accept `[{did, spam_score, retire?}]` from a provider feed or a manual
   report; write the score, then set health = `retired` if flagged for retire, else `spam`/`flagged`/`good` by
   threshold; only write (and audit) when health actually changes.

## Gotchas (from the code)
- **LRU is the anti-burn mechanism.** Always picking the "best" number hammers it into a spam flag; ordering by
  `last_used_at ASC` (nulls first) spreads volume so reputation stays clean. Don't "optimize" it to a fixed number.
- **`pickDid` returning null is normal, not an error** — an empty/all-flagged pool means the carrier uses its
  default caller ID. The whole module is dormant-safe on zero rows.
- **The reputation feed is optional and config-driven** — `ingestReputation` is wired to an endpoint but no
  provider is called until you POST signals to it (or a provider posts them). State that it's inactive until fed.
- **Derive `area_code` from the number when not supplied** (`did-pool.js:38`) so state/area-code presence works
  even for bare DID strings.
- **Threshold has a mid-band**: `>= threshold` → spam (pulled), `>= threshold/2` → flagged (deprioritized, still
  eligible? no — only `good` is picked), so a flagged number is effectively benched until it recovers or retires.
- **All movements audit to `entity='did'`** so a burned-number decision is defensible later.
