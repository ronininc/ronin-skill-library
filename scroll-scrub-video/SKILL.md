---
name: scroll-scrub-video
description: >-
  Turn ONE self-hosted video into a scroll-driven "scrubber": scroll position maps 1:1 to the clip's
  currentTime, so scrolling the section plays the yard being built / the product assembling / the
  before→after, and stopping scroll stops the build on that exact frame. Pure hand-coded JS + an
  ffmpeg encode recipe — no library, no CDN, Cloudflare-static-ready, reduced-motion-safe. Use
  WHENEVER a build wants "scroll to build/assemble/reveal", "scrubber video", "video timeline that
  follows the scroll", "scroll-controlled animation", "playhead follows scroll", "the yard builds as
  you scroll", or a cinematic scroll section driven by real footage. It is a NEW effect atom that
  COMPLEMENTS web-effects-catalog (drop it in assets/ beside the other atoms) and REQUIRES
  worker-media-headers (the Range/206 byte-serving that lets the browser seek into an un-downloaded
  stretch — without it the scrubber stalls). Pairs with site-media-fetch / a generated continuous
  clip. Do NOT sample the video into per-frame stills (fast scroll visibly skips) and do NOT hold
  decoded frames in memory (blows an 8 GB machine) — seek ONE Range-served video.
---
# Scroll-Scrub Video

## What it is / when to use / what it composes with
A section whose scroll progress is the playhead of a muted, self-hosted `<video>`. The frame shown is
a **pure function of where the page is** — no autoplay, no easing, no state of its own. Use it for the
signature "watch it build as you scroll" hero-adjacent section. It is an **effect atom for
web-effects-catalog** and sits on top of **worker-media-headers** (the byte-range 206 serving of an
`ASSETS`-bound clip is what makes seeking into a not-yet-buffered stretch work). The clip itself comes
from a real render or `site-media-fetch`; a jump-free continuous take matters far more than fps.

## Reference implementation — exact source
- **Client engine:** `site/assets/js/site.js:89-378` (the `.build` section handler). This is the
  hardened, production version — every guard in it is a bug that was hit.
- **Encode recipe:** `scripts/build-frames.sh:1-30` — the single knob that matters is the **dense GOP**.
- **Generation guidance (jump-free source):** `docs/higgsfield-scrub-recipe.md`.

## How to reapply
**1. Encode the clip with a dense keyframe interval.** Scrubbing seeks to an arbitrary `currentTime`
constantly, and each seek decodes from the nearest prior keyframe — so a keyframe every 3rd frame keeps
each seek ~6 ms (well under the 16.7 ms/60fps budget). From `build-frames.sh`:
```
ffmpeg -v error -y -i in.mp4 -vf "scale=1440:810:flags=lanczos" -an \
  -c:v libx264 -preset medium -crf 20 -g 3 -keyint_min 3 \
  -pix_fmt yuv420p -movflags +faststart out.mp4
```
`-g 3 -keyint_min 3` is the whole trick; `+faststart` puts the moov atom first so ranges serve
immediately. 1440×810 was the measured quality/latency sweet spot (~54 MB, med 6.1 ms/p95 7.7 ms/seek).
Provide 720/1080/1440 tiers.
**2. Markup:** a tall `.build` "track" (its height IS the scroll travel), a sticky viewport holding the
`<video muted playsinline preload="none">` with `data-src-720/1080/1440`, a `[data-step]` label and a
`[data-bar]` progress fill. `STAGES` (`site.js:105`) is `[fraction, label]` cut points so the caption
changes exactly when that stage starts moving.
**3. Serve it range-enabled** — apply the worker-media-headers 206 serving to the video path (Cloudflare
`ASSETS` + `run_worker_first`), or host on R2 which serves ranges natively.
**4. The engine's load-bearing techniques (copy them, don't re-derive):**
- **Self-clocking seek pump** (`pump()`, `:189`): issue ONE seek, wait for the `seeked` event, only then
  issue the next if the target moved. A video services one seek at a time and drops assignments while
  `seeking` is true (WebKit discards them) — assigning `currentTime` every rAF is the freeze.
- **No easing** (`:220`): `shown = target`; a lerp keeps moving after you stop scrolling and reads as the
  image being "pulled."
- **Buffered-lead reveal** (`:305`): keep the poster until ~10 s of contiguous clip is buffered from 0,
  then reveal — seeking into an undownloaded gap serves out-of-order frames that read as glitching.
- **Tiered src by viewport, chosen once** (`attach()`, `:130`) and attached only when the section is
  ~3.5 viewports away (never re-chosen — swapping src mid-scroll drops the buffer).
- **Watchdog** `setInterval(…,250)` (`:270`) + `resync()` on `load`/`pageshow`/`visibilitychange`:
  drives the seek directly when rAF is throttled (background tab, low-power, screenshot, bfcache restore).
- **iOS unlock** (`:340`): iOS paints no frame until the element has `play()`ed once off a user gesture —
  take the first touch/pointer/wheel/key, `play()` then immediately `pause()`.
- **Error retry-once then fall back to the poster** (`:363`).

## Gotchas
- **Never sample to stills** and **never hold decoded frames** — the header comment in `build-frames.sh`
  is the scar: stills skip on fast motion, bitmaps OOM. One Range-served video is the answer.
- **`window.innerHeight` can be 0** (zero-height iframe / preview pane / pre-layout) — every geometry test
  scales with it, so a 0 makes the section never load. Fall back to `clientHeight || 800` (`viewportH()`).
- Browsers cap paused-video buffering (~18 MB in Chrome), so a 40 MB clip never reports "fully buffered" —
  that is why the reveal waits for a **lead**, not the whole file, and why Range serving is mandatory.
- Reduced-motion / no-JS must leave a real poster still — the section is an enhancement, never content.
