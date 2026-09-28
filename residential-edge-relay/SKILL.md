---
name: residential-edge-relay
description: >-
  The home-box relay that defeats edge-IP blocks: a Cloudflare Worker's datacenter IP gets
  429/403 from free data APIs (ADS-B, OpenSky, most listing sites) and can't run a browser or
  reach a LAN service (SearXNG, Ollama, a GPU model) — so a tiny script on the operator's
  RESIDENTIAL connection does the fetch/compute and PUSHES the result to the Worker over a
  bearer token, into the exact cache row / job queue the Worker already serves. NO edge egress,
  NO Worker change to the serve path, one D1 upsert per push, and an operator ARM-GATE (a green
  button in the app) that the Worker checks before accepting a push. Two shapes: PUSH (the home
  box pumps a live feed on a cadence) and CLAIM (the home box polls for jobs the edge enqueued,
  does them locally, posts results back). Use WHENEVER a build hits "the edge can't fetch this /
  is rate-limited / is IP-blocked / can't run a browser or a local model", "keep the live map/feed
  warm from home", "run the heavy/blocked part on my machine and feed it to the site", "a local
  companion that works a queue from the Worker", or any "web app can't do X, hand it to a home
  runner" problem. COMPLEMENTS scoped-bearer-token (the auth primitive it rides — don't
  re-implement the token), data-feed-intake (the inert adapter registry — this is the RUNNER that
  actually executes), money-feed-health-monitor / connector-egress-circuit-breaker (health + fail-
  closed on the SERVE side), and text-campaign-platform (the outbound send-queue cousin of the
  CLAIM shape). Guardrails: the relay only ever pushes INBOUND public data or its own compute to
  the operator's OWN Worker; the arm-gate means a stopped relay degrades to "no data", never a
  crash; every relay reports and keeps its loop alive across transient upstream errors; never point
  a "free by design" relay's model host at a paid remote (assert localhost).
---
# Residential Edge Relay

## What it is / when to use / what it composes with
A Cloudflare Worker lives on shared datacenter IPs. Free/public data sources rate-limit or block
those IPs, the edge can't launch a headless browser, and it can't reach anything on the operator's
LAN (a local search engine, a local LLM, a GPU model). The fix is a **residential relay**: a small
long-running script on the operator's home machine — where those APIs answer and the LAN services
live — that does the blocked work and hands the result to the Worker through the front door (a
bearer-token HTTP endpoint), writing the **same cache row or job the Worker already knows how to
serve**. The edge serve path never changes; it just starts finding data there.

Two shapes, one doctrine:
- **PUSH** — the relay pumps a live feed on a cadence (aircraft, prices, forecasts, mining stats).
  The Worker caches the last push and serves it with a short TTL. Example: `flight-relay.py`.
- **CLAIM** — the edge enqueues jobs it can't do; the relay polls `claim`, does the work locally,
  posts to `result`. Examples: `dm-relay.py`, `browser-relay.py`, `car-relay.py`, `runner.py`.

**Composes with:** `scoped-bearer-token` (the revocable key every relay sends as `Authorization:
Bearer …` — reuse it, don't invent auth), `data-feed-intake` (stores source specs INERT; this skill
is the deliberate runner that executes one), `money-feed-health-monitor` (shows "is the feed warm?"
on the serve side — a relay that stops should surface as stale, not silent), `connector-egress-
circuit-breaker` (fail-closed on the Worker's own outbound), and `text-campaign-platform` (the
outbound-send sibling: same claim-once/heartbeat contract pointed the other way).

## Reference implementation — exact source (lift the proven code)
Cleanest PUSH relay — `~/ronin-osint/flight-relay.py`:
- Why-it-exists docstring (edge 429/403 → home IP → push to `feed_cache`, no serve-path change) —
  `flight-relay.py:7-30`.
- `SOURCES` list of free mirrors tried in order until one answers — `flight-relay.py:52-56`.
- `fetch_aircraft()` — fetch + normalize into the EXACT GeoJSON feature shape the Worker serves,
  incl. the airline-vs-private classifier — `flight-relay.py:67-107`.
- `push(features)` — `POST … Authorization: Bearer {TOKEN}` of the FeatureCollection —
  `flight-relay.py:110-117`.
- `one_cycle()` + `main()` — `--once` / `--dry-run` / loop, and a loop that stays alive across
  transient upstream errors — `flight-relay.py:120-148`.

CLAIM relay — `~/ronin-osint/dm-relay.py`:
- `api(path, payload)` first-party bearer POST — `dm-relay.py:93-98`.
- `cycle()` — `claim` a job → `handle()` → `result` — `dm-relay.py:392-398`.
- Loop paces tight when it worked a job, backs off when idle — `dm-relay.py:425-431`.

Other proven instances of the same contract:
- `browser-relay.py:49-62` — claim a read job, render locally, post text/err back.
- `runner.py:20-57` — claim → shell out to `enrich.py` → post dossier/err (subprocess variant).
- `kronos-relay.py:208-220` — **dual-cadence** variant: a fast on-demand request lane
  (`claim_requests`/`serve_requests`, `:140-183`) plus a slow full-sweep cadence.
- `ronin-miner.py:200-216` — a **report** relay whose Worker reply carries the arm-gate
  (`halted` → "arm the rig in the app to record stats").

## How to reapply — the wiring + THE INVARIANT
1. **Endpoint pair on the Worker.** PUSH: `POST /feeds/push/<name>` writes one `feed_cache` row;
   the serve route reads that row behind a short TTL. CLAIM: `POST /api/<x>/claim` hands out one
   job (atomic claim), `POST /api/<x>/result` records the outcome.
2. **Auth = one shared bearer** (`scoped-bearer-token`). Set it as a Worker secret; export the same
   string on the home box. `printf '%s' "$SECRET" | npx wrangler secret put <NAME>` (see
   `flight-relay.py:31-33`).
3. **Arm-gate** on the serve/accept side: a boolean the operator flips in the app. The Worker
   IGNORES pushes (or refuses to serve) when disarmed and tells the relay so (`ronin-miner.py:209`).
   A stopped relay then reads as "no data / stale", never an error page.
4. **Loop hygiene:** `--once` and `--dry-run` for testing; the long loop catches transient
   upstream/network errors, logs, and continues (`flight-relay.py:143-148`); jitter/backoff on
   sources that rate-limit (see grounded-llm-extraction for the rotation).
5. **Cost/sovereignty guard:** if the relay claims to be "free," assert its model/service host is
   localhost so it can't silently start billing a remote — `dm-relay.py:401-409`,
   `geospy-relay.py:41-44`.

**THE INVARIANT:** the relay does the work the edge *can't* and hands the Worker a value in the
schema it *already serves* — so the serve path is unchanged and unaware. The edge stays the source
of truth and the arm-gate; the home box is a disposable feeder. Kill the relay and the feature
degrades to empty, never to broken. It only ever moves INBOUND public data (or the operator's own
compute) INTO the operator's OWN Worker.

## Gotchas — real pitfalls from the code + how it's validated
- **Datacenter-IP blocks are the whole reason.** Don't "fix" it by fetching from the Worker — that
  is the thing that 429s. The residential IP is load-bearing (`flight-relay.py:50-51`).
- **Match the served schema exactly.** `flight-relay.py:92-105` builds features the serve route
  already expects; a mismatched push silently renders nothing. Validate with `--dry-run` first.
- **Idempotency on CLAIM.** The claim must be atomic (one relay gets one job) and results dedup;
  re-posts must be harmless. `runner.py` posts either `{dossier}` or `{error}` so a job always
  closes (`runner.py:53-57`).
- **Keep the loop alive.** One bad upstream response must not kill a 24/7 relay — every loop here
  wraps the cycle in `try/except` and sleeps (`flight-relay.py:143-148`, `dm-relay.py:425-431`).
- **Frugal by design:** one D1 upsert per push, nothing persisted to R2 (`flight-relay.py:17-18`).
- **Liveness is host-bound:** the feature is live only while the home box + relay run — the same
  constraint the memory notes flag for the flight relay. Pair with `money-feed-health-monitor` so
  the app shows staleness honestly.
- **Operator policy can ship a relay dark.** Some relays here (the comms ones) are currently
  disabled by business policy, not by breakage — an arm-gate is exactly what makes that safe.
