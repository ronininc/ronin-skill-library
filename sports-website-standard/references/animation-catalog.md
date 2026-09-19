# Sports Animation Catalog — build recipes

Per-effect implementation guidance. Every effect: **hook** (markup/data attr), **tech**,
**fallback** (reduced-motion/low-power), **needs** (asset/feed, if any). All self-contained;
vendor any library into `/assets` (no CDN). Accents pull from the site palette.

---

## 1. Hero & Team Identity

### Wall Crash page loader  · TIER 1
- **What:** a 3D football flies in and shatters a full-screen loader overlay into physics turf
  fragments, revealing the page.
- **Tech:** `<canvas>` overlay, `position:fixed; inset:0; z-index:9999`. Ball = sprite or simple
  extruded mesh; on "impact" spawn 24–60 fragment quads with a light 2D physics step (gravity +
  velocity + rotation, ~1s) using `requestAnimationFrame`; fade canvas out and remove. Turf =
  green gradient tiles. Trigger on `window.load` (or a max-timeout so it never blocks forever).
- **Fallback:** reduced-motion/low-power → skip physics, 200ms fade of a static overlay. Never
  gate content behind the animation; DOM is ready underneath.
- **Needs:** nothing (uses palette + a football sprite in `/assets`).

### 3D Helmet Configurator  · TIER 2 (needs helmet GLB)
- **What:** rotate the team helmet in WebGL; mouse-hover drives localized neon reflections off the
  metallic shell and the **crest/fin down the center**.
- **Tech:** vendored `three.min.js` in `/assets`. `GLTFLoader` for `assets/helmet.glb`
  (PBR metallic-roughness). Pointer position → move a point/rect-area light for the traveling neon
  highlight; slow auto-rotate, drag to spin. Lazy-load the module on first scroll to the section so
  it never blocks first paint. Cap texture size; `renderer.setPixelRatio(Math.min(devicePixelRatio,2))`;
  pause `render` when the canvas is off-screen (IntersectionObserver).
- **Fallback:** no GLB or reduced-motion/no-WebGL → a pre-rendered **turntable** (image sequence or
  short muted loop) of the helmet, or the static crest logo. Document "add `assets/helmet.glb`" in README.
- **Needs:** a helmet **GLB** model. Until then ship the turntable/static fallback.

### Neon Ribbon-Board Marquee  · TIER 1
- **What:** high-brightness infinite marquee of league/team news, like the arena's LED ring.
- **Tech:** duplicated track, `transform: translateX` keyframe loop (from base marquee pattern) with
  an LED look — tight letter-spacing, glow via `text-shadow`/`filter`, scanline overlay, palette accent.
  Content is a JS array; if a **real news feed** is wired, render from it, else use static team lines.
- **Fallback:** reduced-motion → static, non-scrolling headline strip.
- **Needs:** optional live news feed (else static — never fake "live league news").

### Parallax Mascot Breakdown  · TIER 1
- **What:** scroll assembles the mascot/primary logo from layered pieces with chromatic-aberration accents.
- **Tech:** logo split into layers (SVG groups or stacked PNGs in `/assets`); scroll progress
  (IntersectionObserver + scroll ratio) drives each layer's `translate`/`opacity`; chromatic aberration
  = offset red/cyan duplicates fading to 0 as it assembles. Prefer SVG layers so it stays crisp.
- **Fallback:** reduced-motion → the assembled logo, no motion.
- **Needs:** a layered logo (SVG groups ideal). Can derive layers from the supplied crest.

---

## 2. Fan Experience & Ticket Conversion

### 3D Virtual Seat Viewer  · TIER 2 (needs seat data)
- **What:** WebGL camera sweep from a top-down arena map into the selected seat row.
- **Tech:** vendored Three.js; a low-poly arena shell modeled on Desert Diamond Arena
  (see `arena-reference.md`) + a seat-zone data model (sections → rows → view point). Selecting a
  seat tweens the camera (position+target) from overhead to that row's eye point over ~1.5s (easing).
  Lazy-load; pause off-screen.
- **Fallback:** no data / no WebGL / reduced-motion → the **2D interactive seat map** (SVG zones,
  click to highlight + show a static "view from here" photo if available).
- **Needs:** arena **seat-map + zone data** (and optional per-zone view images). Ship 2D map until then.

### "Rebound Net" Ticket Drop  · TIER 1
- **What:** drag-drop seat-zone filters; clicking a zone bounces a football erratically off a digital
  rebound net before highlighting available blocks.
- **Tech:** SVG/canvas zones; on select, animate a ball with a few randomized reflection bounces
  (2D vector math, ~700ms) then apply the filter and highlight matching blocks. Drag-drop via pointer
  events for reordering/among filters.
- **Fallback:** reduced-motion → instant filter apply, no bounce.
- **Needs:** the ticket/zone list (static or from inventory).

### Arcade Scoreboard Ticket Counter  · TIER 1
- **What:** slot-machine number flips rolling up for "Tickets Remaining" / "Fans in Seats".
- **Tech:** per-digit vertical strip 0–9, `transform: translateY` eased to the target digit; odometer
  feel; segmented-LED styling. Animate once on scroll-in.
- **Fallback:** reduced-motion → set the final number directly.
- **Needs:** the number. **If it's meant to be live ("remaining"/"in seats"), it needs a real feed —
  with none, show a static/`—` value; do not animate a made-up live count.**

### "Next Game" Countdown  · TIER 1
- **What:** pulsing high-contrast countdown that transitions into a date/calendar tool.
- **Tech:** `setInterval` diff to the target datetime, DD:HH:MM:SS with a pulse on the seconds; a
  "add to calendar" that emits an `.ics` (data-URI download) / Google Calendar link. Config the game
  datetime + opponent at the top of the script.
- **Fallback:** reduced-motion → no pulse; numbers still tick (or static if truly reduced).
- **Needs:** the real next-game datetime + opponent (else placeholder, flagged in README). Example
  slot: `Sat Apr 4 2026 7:00 PM vs. The Rivals` — replace with confirmed schedule.

---

## 3. Roster & Live Game Stats

### Impact-Frame Player Cards  · TIER 1
- **What:** hover pops the athlete out of the card frame amid smoke/sparks.
- **Tech:** card with `overflow:visible` on hover; player cutout (transparent PNG) scales/translates
  beyond the frame; particle burst via a small canvas or CSS pseudo-sprites; drop-shadow for lift.
- **Fallback:** reduced-motion → simple scale/border highlight, no particles.
- **Needs:** transparent player cutouts (else use the framed photo with a lift-only hover).

### Compressed 50-Yard Scrollytelling  · TIER 1
- **What:** scroll down a vector 50-yard arena field, pausing at goal lines to reveal stats + ironman positions.
- **Tech:** a tall pinned section; scroll progress drives a "camera" down an SVG field (yard lines,
  end zones, hash marks — arena 50-yard dimensions from `arena-reference.md`); waypoints reveal stat
  cards. Use scroll ratio + `transform`, not scroll-jacking.
- **Fallback:** reduced-motion → the field + all stat blocks shown statically, stacked.
- **Needs:** team/player stats (static ok).

### "Ironman" Offense/Defense Toggle  · TIER 1
- **What:** fluid morph between Offense and Defense stat layouts (arena ironman rule).
- **Tech:** a toggle; FLIP-style transition (measure → animate) or crossfade+translate between the two
  layouts sharing the same container; icons/positions animate to new slots.
- **Fallback:** reduced-motion → instant swap.
- **Needs:** both stat sets.

### Real-Time Blitz Live Tickers  · TIER 2 (needs live feed)
- **What:** a slide-and-fade alert tray dropping from the header on turnovers/wall-collisions during live games.
- **Tech:** a fixed top tray; new events slide down + fade; queue with auto-dismiss. Source = a live
  game feed (websocket/poll).
- **Fallback / no feed:** the tray simply doesn't arm; header shows the scheduled next game. **Never
  emit a fake turnover/score.** Only arms when a real feed is connected and a game is live.
- **Needs:** a **live game data feed**.

---

## 4. Merchandise & E-Commerce

### Kinetic Jersey Swapper  · TIER 1
- **What:** color swatches trigger a fabric-ripple that morphs the jersey home ↔ away.
- **Tech:** stacked jersey images (home/away/alt) or SVG recolor; on swatch click run a ripple mask
  (`clip-path`/canvas displacement) sweeping across as the layer crossfades. Recolor via CSS filters
  only if it reads true; otherwise swap prepared images from `/assets`.
- **Fallback:** reduced-motion → instant image/color swap.
- **Needs:** jersey images per colorway (or a clean recolor source).

### "Add to Cart" Blast  · TIER 1
- **What:** a team-color confetti micro-explosion confined to the button, morphing into a check.
- **Tech:** button-local `<canvas>`/particles clipped to the button bounds; ~12–20 confetti bits in
  palette colors, ~500ms, then swap label → checkmark. Pure client-side; integrates with the base
  payment-ready cart structure.
- **Fallback:** reduced-motion → label → check, no confetti.
- **Needs:** nothing.

### Sticky Mini-Cart Slide  · TIER 1
- **What:** spring-physics slide-out cart that keeps the fan on the page.
- **Tech:** off-canvas panel, spring easing (`cubic-bezier` or a tiny spring); focus-trap; updates line
  items live; checkout hands off to the base payment-ready flow (Clover/Stripe/Square worker) when live.
- **Fallback:** reduced-motion → plain slide/instant open; fully keyboard-usable.
- **Needs:** the shop structure from base (payment processor bolts on when chosen).
