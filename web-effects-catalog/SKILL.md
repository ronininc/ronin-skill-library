---
name: web-effects-catalog
description: >-
  The house library of reusable, SOVEREIGN web animations & interactions — the mix-and-match effect
  atoms every client/team site pulls from, hand-coded (no WordPress/Elementor/page-builder, no CDN),
  accessible-by-default, and reduced-motion-safe. Use this WHENEVER a build needs motion or an
  interactive flourish and you want to compose it from proven house parts instead of inventing one:
  scroll-entrance reveals (the slideInUp family), the signature "exploded-view" inspector (hover an
  item — a bowl, a burger, furniture, a computer — and its parts blow apart, float as if in a vacuum,
  then coalesce back), parallax, marquees/tickers, flip cards, sticky headers, tilt, count-ups, and
  more. Trigger on "add an animation/effect", "make it interactive", "reveal on scroll", "slide up as
  you scroll", "see what's inside / see what's in your order", "exploded view", "blow it apart",
  "show the internals", "hover to inspect", "floating parts", "keep the animations as skills", or any
  motion request on top of website-build-standard / sports-website-standard / commerce-spine. Each
  effect ships a drop-in file in assets/, a What/Tech/Fallback/Needs recipe in
  references/effects-catalog.md, and a real reduced-motion fallback. Do NOT reach for a page-builder,
  a heavyweight animation framework, or a CDN library when an atom here (or a small hand-coded one in
  the same style) will do. Non-negotiable house rules: content is VISIBLE BY DEFAULT (motion is an
  enhancement, never a gate on content or SEO), every effect degrades under prefers-reduced-motion and
  on touch, and nothing fakes live data.
---

# Web Effects Catalog — the house motion & interaction library

This is the **shared, business-agnostic** effect library. `sports-website-standard` already has a
sport-themed catalog (`references/animation-catalog.md`); this is the **neutral** one every other
build — restaurants, salons, contractors, product/portfolio sites — pulls from, and the place new
reusable effects land so they don't get trapped inside one vertical's skill.

It is a **layer used by** `website-build-standard` (and its extensions). Follow that skill first for
the non-negotiable base (single self-contained `index.html` + `/assets/` + `README.md`,
Cloudflare-static deploy, builder-only Edit Media, SVG logos, payment-ready shop). Everything here is
**additive motion**, composed from atoms.

## Doctrine (every effect obeys these — no exceptions)

1. **Sovereign.** Hand-coded CSS/JS, vendored into `/assets`. No WordPress, no Elementor, no
   page-builder, no CDN. If an atom needs a library, vendor the exact file locally.
2. **Visible by default.** Content renders fully with no JS and to crawlers. Motion is layered on
   top only when JS + capability + motion-preference allow. This is the one thing stock page-builder
   sites get wrong — their entrance animations leave content `opacity:0` until JS fires (bad for SEO,
   bad on failure). We never do that; see `reveal` below.
3. **Reduced-motion & touch safe.** Every atom has a real `prefers-reduced-motion: reduce` path and a
   sensible touch behavior (no hover on touch → tap/pin or auto-show). Information is never lost when
   motion is off — only the movement is.
4. **Cheap on mid-range phones.** Prefer `transform`/`opacity` (compositor-only). Pause off-screen
   work with `IntersectionObserver`. Never block first paint.
5. **Never fake data.** A live-looking counter/ticker needs a real source, else it shows a static/`—`
   value.

## The atoms (mix and match)

Full build recipes — **hook / tech / fallback / needs** — live in `references/effects-catalog.md`.
Read the recipe before wiring an atom. Drop-in files are in `assets/`.

**Shipped & proven**
- **`reveal` — scroll-entrance (the slideInUp family).** Blocks slide/fade/zoom in as they enter the
  viewport, visible-by-default and reduced-motion-safe. `assets/reveal.css` + `assets/reveal.js`.
  Directions: `up` (default) · `down` · `left` · `right` · `zoom` · `fade`; per-element delay.
- **`xv` — exploded-view inspector (signature).** Hover / focus / tap a "scene"; its `.xv-part`s
  blow apart along authored or auto-radial vectors, lift toward the viewer (Z), and drift gently as
  if floating in a vacuum, revealing per-part labels — then coalesce back on leave. Works for any
  layered item: açaí bowls & burgers (ingredients), furniture (components), computers/gadgets
  (internals). `assets/xv.css` + `assets/xv.js`. Live demo: `demo.html`.

**Roadmap (add here as they graduate — same format, same doctrine)**
- `parallax` — scroll-linked background/layer depth (replaces Elementor Motion-FX).
- `marquee` — infinite ticker strip (news/menu/logos); reduced-motion → static strip.
- `flip` — CSS 3D flip card on hover/tap (front → back); replaces Elementor flip-box.
- `sticky-header` — shrink-on-scroll condensing header.
- `tilt` — pointer-driven 3D tilt on cards/media.
- `count-up` — odometer number roll on scroll-in (real numbers only).
- `carousel` — vendored-Swiper-free hero/testimonial slider.
- `cursor-spotlight` — radial light that follows the pointer over a section.

## Using an atom (pattern)

1. Copy the atom's file(s) from `assets/` into the site's `/assets/`.
2. Add the markup hooks from the recipe (`class="reveal"`, `data-xv`, …).
3. For `reveal`, put the one-line arm script **first in `<head>`** so there's no flash:
   `<script>document.documentElement.classList.add('reveal-armed');</script>`
4. Verify: content is fully present with JS disabled, and the reduced-motion path is clean.

## Exploded-view (`xv`) — quick reference

```html
<div class="xv-scene" data-xv aria-label="Açaí bowl">
  <div class="xv-stage">
    <div class="xv-part" data-label="Açaí base">…</div>
    <div class="xv-part" data-label="Granola" data-dx="-120" data-dy="-40">…</div>
    <!-- omit data-dx+data-dy to auto-compute a radial burst from the centre -->
  </div>
</div>
```
Per-part (px/deg): `data-dx data-dy data-dz` (explode offset), `data-dr` (rotation). Scene:
`data-xv-spread` (burst-distance multiplier). Hover/focus explodes on pointer devices; tap pins on
touch; Enter/Space toggles for keyboard. Reduced-motion → labels reveal statically, no travel.

## The mix-and-match principle (why this skill exists)

Our big skills (website, sports, commerce-spine, crm-build-standard, the Solomon engines) each bundle
many capabilities. The house direction is to **decompose them into atoms that can be recombined** —
so a build pulls exactly the parts it needs. This catalog is the first worked example of that for the
motion layer. The cross-skill decomposition index lives in
`references/skill-atoms-index.md`.
