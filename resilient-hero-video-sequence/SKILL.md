---
name: resilient-hero-video-sequence
description: >-
  Play a HERO as a sequence of autoplaying video shots that hard-cut one to the next and can NEVER show
  a blank box — each clip is layered over the last and revealed only once it is genuinely painting
  frames, so a failed fetch, a refused autoplay, or a throttled tab at worst rests on whatever was last
  showing. Pure hand-coded JS, no library/CDN, reduced-motion-safe, and adding a shot is markup (not
  code). Use WHENEVER a site hero is MULTIPLE video clips rather than one loop or a photo slideshow:
  "cycle hero videos", "play these clips in sequence in the hero", "hero video sequence", "hard-cut
  between shots", "hero that never goes black", "montage hero", or a cinematic multi-shot opener. It is
  a NEW effect atom that COMPLEMENTS web-effects-catalog and is the video counterpart to
  website-build-standard's default photo hero slideshow (use this once real footage exists). Pairs with
  site-media-fetch (source the clips) and worker-media-headers (range-serve them). Do NOT add a fade
  between shots that share no geometry (reads as a smear) and do NOT hide the outgoing clip on a timer
  (that is exactly how a hero goes blank).
---
# Resilient Hero Video Sequence

## What it is / when to use / what it composes with
A hero that walks over however many `.hero-shot` clips exist, playing each one-way camera move in turn
and resting on the last one's final frame. The governing rule is **THE HERO MUST NEVER BE BLANK**: each
shot is layered on top of the previous and revealed only when it is producing frames. It is a hardened
**effect atom for web-effects-catalog**, the video sibling of the default photo hero in
**website-build-standard**, and it wants **worker-media-headers** to range-serve the clips.

## Reference implementation — exact source
`site/assets/js/hero-sequence.js:1-124` — the entire sequencer. The 20-line header comment documents
why each decision is the way it is (it is the design spec).

## How to reapply
**Markup contract:** a `.hero` container with a first `.hero-video:not(.hero-shot)` (shot 0) plus N
`.hero-shot` elements, each `muted playsinline` with `data-src-1080` / `data-src-1440` and an optional
`data-scrim="heavy"`. CSS carries **no transition** on `.hero-shot` (the header explains: a dissolve
between shots that share no geometry reads as a smear), and `.is-live` is what makes a revealed shot
visible. Copy the file; the load-bearing techniques are:
- **Walk, don't hardcode** (`:22`): `queue = querySelectorAll('.hero-shot')`, `chain(current, index)`
  hands off on `ended` and lines up the next — a 4th shot is markup, not a rewrite.
- **Prefetch the next at 55 %** (`:83`): `arm(next)` on `timeupdate` past 0.55 so the cut is never gated
  on the network; `arm()` sets `preload='auto'`, assigns the tier `src`, `load()`s, and **primes the
  decoder** by setting `currentTime = 0` on `loadeddata` (buffered bytes are not a decoded frame).
- **Reveal on the first PAINTED frame** (`:97`): `requestVideoFrameCallback` fires per presented frame,
  so `reveal(next)` lands ~1 vsync after `play()`. This replaced a `timeupdate` reveal that measured
  264 ms of the previous clip frozen. Fallback for older Safari/Firefox: `playing` + two rAFs.
- **`timeupdate` backstop** (`:116`): deliberately last so a healthy browser never uses it, but it is
  what reveals in an **occluded tab where rVFC never fires**.
- **Hold the last frame** (`:72`): on the final shot's `ended`, pause and set `currentTime` to
  `duration - 0.05` — otherwise some browsers repaint the poster, which is shot 0's poster (wrong scene).
- **Autoplay-refusal safe** (`:107`): `play()` can be refused even when muted; `.catch(()=>{})` so a
  refusal leaves the current shot's last frame up, never a paused black element.
- **Reduced motion** (`:30`): CSS has already swapped in a still — return immediately, download nothing.
- **Tier by breakpoint at assign time** (`chooseSrc`, `:35`): `<source media>` is evaluated at parse
  time, but these `src`s are set later, so the 1200 px choice is made in JS with `matchMedia`.

## Gotchas
- **Never hide the outgoing clip on a timer** — the header calls out an early version that did and could
  show an empty box. Layer + reveal-when-painting instead; nothing is ever hidden or unloaded.
- `data-src-1440` does NOT become `dataset.src1440` (dash-to-camelCase only fires before a letter) — use
  `getAttribute`, the same reason the scroll-scrub engine does.
- One-way camera moves cannot loop (a restart reads as a snap-back) — the sequence rests, it does not loop.
