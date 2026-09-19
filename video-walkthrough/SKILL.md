---
name: video-walkthrough
description: >-
  Generate a polished VIDEO / GIF WALKTHROUGH of any web app, site, CRM, or portal by driving it in
  a real browser through its key flows — logging in, clicking each screen, capturing every state —
  then assembling a captioned walkthrough asset (animated GIF, MP4 slideshow, or storyboard). This is
  the house "here's your new system in 90 seconds" deliverable: a sales demo, a client-onboarding
  tour, or a portfolio piece for every Ronin build. Use WHENEVER the ask is a "walkthrough", "demo
  video", "screen recording", "product tour", "record the flow", "make a GIF of the app", "show the
  client how it works", or a visual proof-of-flow of something built or reachable by URL. Works on a
  local dev server (wrangler dev / vite) or a live URL; logs in with supplied or seeded demo
  credentials; NEVER uses real client data — seed a throwaway demo account. Trigger on a finished
  build the client hasn't seen, an investor/stakeholder demo, an onboarding handoff, or "i need a
  walkthrough of [app]". Pairs with cf-deploy (walk a preview before go-live) and any build skill
  (deliver the walkthrough alongside the site/CRM).
---

# Video Walkthrough

Turn any web app into a narrated visual tour. You DRIVE the app in a browser, CAPTURE each flow at
rest, then ASSEMBLE the frames into a deliverable. Three output modes, cheapest first:

1. **Animated GIF** — smooth, silent, loops. Best for a quick "look what it does" (email, text, deck).
2. **MP4 slideshow** — captioned frames held for a few seconds each, optional title cards. The
   "onboarding tour" deliverable. (H.264 — never H.265/x265 on this host, it's broken.)
3. **Captioned storyboard** — an HTML/artifact strip of the frames with a caption under each. Best
   when the client wants to scan steps, not watch.

## Step 0 — Gather inputs (ask only what you can't infer)
- **Target**: a local dev URL (start it yourself — `wrangler dev` / `vite`) or a live URL.
- **Access**: how to get in. Prefer a **seeded demo account** over real credentials, and NEVER real
  client data — register a throwaway admin / demo user against a fresh local DB, or use a read-only
  clearance/viewer login. (For a Ronin CRM/portal: `POST /api/auth/register` a demo admin, or mint a
  read-only seat.)
- **Flow list**: the screens/actions to show, in order. If not given, DISCOVER them — read the SPA's
  tab/nav structure (`read_page`, or grep the markup for `data-tab` / `data-view` / nav buttons) and
  propose a 5–8 step tour (e.g. login → dashboard → the one killer feature → create-something → result).
- **Branding**: a title card (client name + "powered by Ronin") and a per-step caption line.

## Step 1 — Pick the browser surface
- **In-app Browser pane** (`mcp__Claude_Browser__*`) — fastest, DOM-aware (`read_page` gives refs for
  precise clicks). Screenshots are clean **at rest**. GOTCHA: it returns BLACK frames on pages that are
  scrolled with fixed backgrounds or mid-animation — screenshot the resting state, or switch surfaces.
- **Real Chrome** (`mcp__claude-in-chrome__*`) — captures animated/scrolled pages faithfully AND has
  `gif_creator` to record a sequence straight to an animated GIF. Use this when the app has motion, or
  when you want the GIF built for you. (Needs the extension connected.)

Default: drive in the **Browser pane** for a static-ish app (deterministic, screenshot per step);
use **real Chrome + gif_creator** when the app is animated or the client wants a moving GIF.

## Step 2 — Drive + capture (the loop)
For each flow step, in order:
1. `navigate` / `preview_start` to the view (or click the tab: `find` the label → `computer` left_click the ref).
2. Perform the action — `form_input` to fill fields, `computer` click/type to trigger it.
3. Let it settle (the state you want is **at rest**, not mid-transition), then `computer { action: "screenshot" }`.
4. Save the PNG to a working dir in order: `walkthrough/01-login.png`, `02-dashboard.png`, …
   (Browser-pane screenshots come back inline — write them to disk via the capture you control, or use
   real-Chrome capture which returns files; for the pane, drive `gif_creator` in real Chrome instead
   when you need saved frames.)

Deterministic drive rules: log in ONCE up front; go tab-by-tab in the order of the tour; never depend
on real data — create the demo record on camera (that IS the "create-something" step and it shows the
app working). Keep captions to one line per step.

## Step 3 — Assemble
**GIF (real Chrome):** drive the flow, then `mcp__claude-in-chrome__gif_creator` over the sequence →
one animated GIF. Fastest path to a moving walkthrough.

**MP4 slideshow (sovereign, from saved PNGs):** hold each frame ~2.5s, H.264, scaled to a clean width.
On THIS host ffmpeg's x265 is broken — use `libx264`, never `libx265`:
```bash
# frames are 01-*.png, 02-*.png … in ./walkthrough, one per step
ffmpeg -y -framerate 1/2.5 -pattern_type glob -i 'walkthrough/*.png' \
  -vf "scale=1280:-2:flags=lanczos,format=yuv420p" -c:v libx264 -r 30 walkthrough.mp4
```
Add caption cards by burning text per frame (`drawtext`) or by generating a title PNG per step and
including it in the glob. If ffmpeg misbehaves on this host, fall back to a GIF:
```bash
ffmpeg -y -framerate 1/2.5 -pattern_type glob -i 'walkthrough/*.png' \
  -vf "scale=900:-1:flags=lanczos" walkthrough.gif
```

**Storyboard (no encoding):** build a simple HTML strip — each frame with its caption underneath —
and publish it as an Artifact, or hand over the PNGs + a captions list.

## Step 4 — Deliver
- `SendUserFile` the GIF/MP4/storyboard to the operator.
- Frame it as a product asset: "Here's a 90-second walkthrough of your new system." This ships with
  EVERY build — a preview walkthrough before go-live, an onboarding tour at handoff, a portfolio clip.
- Clean up: stop any dev server you started (`lsof -ti tcp:PORT | while read p; do kill -9 $p; done`);
  never leave a zombie wrangler on a port.

## House rules
- **Demo data only** — seed a throwaway account/DB; never film a client's real records or PII.
- **At rest, not mid-animation** — captured motion in the pane goes black; capture the settled frame,
  or use real Chrome for moving shots.
- **Own the drive** — enumerate flows from the app's own nav; don't guess screens that aren't there.
- **One login, ordered tour, killer feature early** — the viewer decides in the first 15 seconds.
- **Brand it** — a title card and a one-line caption per step turn screenshots into a walkthrough.
