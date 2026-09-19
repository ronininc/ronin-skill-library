---
name: sports-website-standard
description: >-
  The house standard for building SPORTS-TEAM websites — arena/football/basketball/soccer clubs,
  leagues, athletic programs, and fan/ticketing sites. EXTENDS website-build-standard with the
  sports animation & interaction system: a physics "Wall Crash" page loader, a 3D WebGL helmet
  configurator, a neon ribbon-board marquee, a parallax mascot/logo breakdown, a 3D virtual seat
  viewer, arcade scoreboard counters, live-game tickers, impact-frame player cards, 50-yard
  scrollytelling, ironman offense/defense toggles, kinetic jersey swappers, and confetti-blast cart
  micro-interactions. Use this WHENEVER building, redesigning, or drafting a website for a sports
  team, club, league, athletic program, arena, or a fan/ticket/roster/schedule site — on top of, not
  instead of, website-build-standard. Trigger on "sports site", "team website", "arena football
  site", "fan site", "ticket page", "roster/stats page", "make a site for [team]", or a team name
  (e.g. Valley Titans). Arena/stadium reference model is the Arizona Rattlers' real home, Desert
  Diamond Arena (Glendale, AZ). Do NOT use for a non-sports business site (use website-build-standard
  alone) or non-web work.
---

# Sports Website Standard

This is the house standard for **sports-team sites**. It is a **layer on top of
`website-build-standard`** — read and follow that skill first for the non-negotiable base
(single self-contained `index.html` + `/assets/` + `README.md`, Cloudflare-static deploy,
builder-only drag-and-drop Edit Media, image inspector, scalable SVG logos, payment-ready
shop, per-site inquiry routing, group-link + hero + video-latency rules). Everything here is
**additive**: the sports animation/interaction system below, plus the arena reference model.

The bar is the same as the base standard, with one sports addition: **the site should feel
like walking into the arena on game day — and a fan on a mid-range phone must still get a
fast, fully-usable site.** Every effect here ships with a real reduced-motion / low-power
fallback, and nothing fakes live data.

## Arena / stadium reference model (use this whenever a build needs a real venue)

When a feature needs a real indoor arena — the seat viewer, the ribbon-board marquee, the LED
ring, the 50-yard field — model it on **Desert Diamond Arena, Glendale, AZ**, the Arizona
Rattlers' real 2026 home (indoor arena, LED ring/ribbon boards, arena-football 50-yard field).
This is the house arena reference for AZ arena-football clients (incl. Valley Titans, who have
no venue of their own). Details + the seat-map / field data model live in
`references/arena-reference.md`. Never present the client team as *playing* there unless it's
true — it is a **visual/spatial reference model**, not a factual claim about the team's schedule.

## The sports animation & interaction system (the catalog)

Full build recipes — tech, markup hooks, physics, fallbacks, and data requirements — are in
`references/animation-catalog.md`. Read it before implementing any item. Summary of the
standard set (four groups, 15 effects):

**1. Hero & Team Identity**
- **Wall Crash page loader** — a 3D football slams into the screen and shatters the loader into
  physics turf fragments, revealing the home page.
- **3D Helmet Configurator** — WebGL; rotate the team helmet, mouse-hover fires localized neon
  reflections off the metallic shell and the **crest/fin running down the center**.
- **Neon Ribbon-Board Marquee** — high-brightness infinite marquee of league news, simulating the
  arena's LED ring boards.
- **Parallax Mascot Breakdown** — scroll-driven layered assembly of the mascot/primary logo with
  chromatic-aberration accents.

**2. Fan Experience & Ticket Conversion**
- **3D Virtual Seat Viewer** — WebGL camera sweep from a top-down arena map into the chosen seat row.
- **"Rebound Net" Ticket Drop** — drag-drop seat-zone filters; a football ricochets off a digital
  rebound net before highlighting available blocks.
- **Arcade Scoreboard Ticket Counter** — slot-machine number flips for "Tickets Remaining" / "Fans in Seats".
- **"Next Game" Countdown** — pulsing high-contrast clock that transitions into a date/calendar tool.

**3. Roster & Live Game Stats**
- **Impact-Frame Player Cards** — hover pops the athlete out of frame amid smoke/sparks.
- **Compressed 50-Yard Scrollytelling** — scroll down a vector 50-yard arena field, pausing to reveal
  stats at the goal lines and ironman positions.
- **"Ironman" Toggle Transitions** — fluid morph between Offense and Defense stat layouts.
- **Real-Time Blitz Live Tickers** — a slide-and-fade alert tray that drops from the header on
  turnovers / wall-collisions **during live games**.

**4. Merchandise & E-Commerce**
- **Kinetic Jersey Swapper** — color swatches trigger a fabric-ripple that morphs home ↔ away.
- **"Add to Cart" Blast** — a team-color confetti micro-explosion confined to the button, morphing to a check.
- **Sticky Mini-Cart Slide** — spring-physics slide-out checkout that never leaves the page.

## Tiering — what ships always vs. what needs real assets/data (honesty gate)

Do not fake capability. Tag each build item:

- **TIER 1 — ships on every sports site** (CSS/JS/canvas only, no heavy deps, no special data):
  Wall Crash loader, Ribbon-Board Marquee, Parallax Mascot Breakdown, Arcade Scoreboard counter,
  Next-Game countdown, Rebound-Net filter, Impact-Frame cards, 50-Yard scrollytelling, Ironman
  toggle, Kinetic Jersey Swapper, Add-to-Cart Blast, Sticky Mini-Cart.
- **TIER 2 — flagship; needs a real asset or feed** (build when it exists, otherwise ship the
  documented graceful fallback, never a fake):
  - **3D Helmet Configurator** → needs a helmet **GLB/3D model** (or a pre-rendered turntable
    fallback until one exists).
  - **3D Virtual Seat Viewer** → needs the **arena seat-map + zone data** (see arena-reference);
    fallback is the 2D interactive seat map.
  - **Blitz Live Tickers / "Tickets Remaining" / "Fans in Seats"** → need a **live feed / real
    inventory**. With no feed, show the scheduled next game and static/`—` counts — **never invent
    a live score, a turnover, or a remaining-tickets number.**

## Non-negotiable tech rules (inherit base + these)

- **Self-contained & Cloudflare-static** (from base): one `index.html`, inline CSS/JS. For 3D/WebGL,
  **vendor the library into `/assets`** (e.g. a pinned local `three.min.js`) and reference it
  same-origin — **never a CDN**. Lazy-load heavy 3D modules so the above-the-fold render stays instant.
- **Reduced-motion / low-power / 2D fallback for EVERY effect.** `prefers-reduced-motion` and a
  low-power path are mandatory: the Wall Crash becomes an instant fade, the seat viewer becomes the 2D
  map, scrollytelling becomes static stat blocks, confetti/physics disable. Immersive is the default;
  the clean 2D version is one switch away (mirrors base "standard mode").
- **Performance budget:** above-the-fold interactive fast on a mid-range phone; hero clip rule from
  base (10–20s, ~<15MB) still applies; 3D scenes cap texture/poly weight and pause when off-screen.
- **Builder-only vs viewer** (from base): Edit Media stays builder-only; the 3D viewers/inspectors are
  viewers, so they stay on for visitors.
- **Brand-driven:** all neon/confetti/ribbon accents pull from the site palette (Valley Titans:
  green `#137a3b` / orange `#ff6a1a` / white on dark `#070c08`). Use the client's real logos/crest.

## Workflow (applying this standard on a build)

1. Run the **base `website-build-standard` workflow first** (scope, three standing questions,
   research, scaffold, media editor, SVG logo, verify-by-render, deliver).
2. Layer the **sports catalog**: pick the TIER-1 set to ship by default; propose TIER-2 flagship
   items and confirm which real assets/feeds exist (helmet GLB, seat data, live feed). Build TIER-2
   only where the asset exists; otherwise ship the documented fallback and mark it in the README.
3. Wire the **arena reference** (Desert Diamond Arena) for any venue-dependent feature.
4. **Verify by rendering** (headless Chromium): hero + loader + one 3D/scroll effect, zero JS errors,
   reduced-motion path works, one real drag-drop swap.
5. **Deliver** per base, and in the README list each sports effect, its tier, and any asset/feed it's
   waiting on (so the client knows exactly what unlocks the flagship pieces).

## Notes

- These immersive/3D features are **opt-in by team request** (consistent with "no AR/immersive on
  client sites unless asked") — the operator asked for them as the sports standard, so they are the
  default *for sports sites* while non-sports sites stay on the base standard.
- Never fabricate scores, schedules, ticket counts, or league news. Real feed → live; no feed →
  scheduled/static, clearly. Truth over spectacle, always.
