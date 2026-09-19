# Web Effects Catalog — build recipes

Per-effect implementation guidance. Every effect states **hook** (markup/attr), **tech**,
**fallback** (reduced-motion / touch / no-JS), and **needs** (asset/data, if any). All
self-contained; vendor any dependency into `/assets` (no CDN). Accents inherit the site palette —
these atoms ship motion + structure, never brand colors.

House invariant restated: **content is visible by default.** No atom may hide content behind a
script that must run for it to appear.

---

## 1. Scroll & entrance

### `reveal` — scroll-entrance (slideInUp family) · TIER 1
- **What:** blocks slide up (or down/left/right/zoom/fade) and fade in as they scroll into view. The
  house-correct version of Elementor's `slideInUp` entrance — same look, but it never leaves content
  invisible if JS fails or a crawler visits.
- **Hook:** `class="reveal"`; optional `data-reveal="left|right|down|zoom|fade"` (default up);
  optional `data-reveal-delay="120"` (ms). **First line in `<head>`:**
  `<script>document.documentElement.classList.add('reveal-armed');</script>`
- **Tech:** `assets/reveal.css` + `assets/reveal.js`. The start-hidden state is scoped to
  `.reveal-armed .reveal`, so it exists **only** once the inline head script has armed it. An
  `IntersectionObserver` (threshold 0.12, `rootMargin: -8%` bottom) adds `.is-in` once, then
  unobserves. A `load`+1.2s safety sweep reveals anything still hidden but on-screen so content can
  never get stuck. Transitions are `transform`+`opacity` only (compositor).
- **Fallback:** reduced-motion **or** no `IntersectionObserver` → `reveal-armed` is dropped and
  everything shows immediately (CSS `!important` guard for reduced-motion). No-JS → the hidden state
  is never armed, so content is fully visible.
- **Needs:** nothing.

---

## 2. Product & item inspection

### `xv` — exploded-view inspector · TIER 1 (signature)
- **What:** hover / focus / tap an item and its parts **blow apart** along radial or authored
  vectors, lift toward the viewer (Z), and **drift gently as if in a vacuum**, revealing per-part
  labels; on leave they **coalesce** back into the assembled item. "See what's in your order" for a
  bowl or burger; the same engine explodes furniture into components or a computer into its internals.
- **Hook:**
  ```html
  <div class="xv-scene" data-xv aria-label="Açaí bowl">
    <div class="xv-stage">
      <div class="xv-part" data-label="Açaí base">…</div>
      <div class="xv-part" data-label="Granola" data-dx="-120" data-dy="-40" data-dz="60">…</div>
    </div>
  </div>
  ```
  Per-part px/deg: `data-dx data-dy data-dz` (explode offset — omit dx+dy for an auto radial burst
  from the scene center), `data-dr` (rotation). Scene: `data-xv-spread` (multiply burst distance).
- **Tech:** `assets/xv.css` + `assets/xv.js`. **Two motions are split onto two elements** so they
  don't fight: the outer `.xv-part` carries the explode offset via a CSS `transition`
  (`cubic-bezier(.22,1,.36,1)`, ~0.58s = the spring-out/coalesce); an auto-injected inner
  `.xv-inner` carries a per-frame `requestAnimationFrame` sine/cosine drift (the vacuum float, no
  transition). The stage adds pointer-driven `rotateX/Y` parallax tilt. Vectors are computed once on
  setup and on resize; auto-radial pushes each part outward from center by
  `max(w,h) * 0.34 * spread`. rAF runs **only while exploded** and is canceled on coalesce.
- **Fallback:** **reduced-motion** → no travel, no drift; the scene still reveals its part **labels**
  on hover/focus/tap (information preserved, movement dropped) and marks the assembled item with an
  inset ring. **Touch** (no hover) → tap **pins** the exploded state, tap again coalesces.
  **Keyboard** → the scene is a `role="button"` with `tabindex=0`; Enter/Space toggles; focus
  explodes on pointer devices. `aria-pressed` reflects state.
- **Needs:** the item split into `.xv-part` layers. Ideal source = a **layered SVG** (one group per
  ingredient/component) or stacked transparent PNGs in `/assets`; the demo uses styled discs +
  emoji to prove the motion with zero assets. For a real menu item, one photo per ingredient (or SVG
  groups) makes it read like an exploded assembly diagram.
- **Proven:** `demo.html` (açaí bowl = authored vertical stack; desktop PC = authored radial). Both
  explode/coalesce verified live; banana part resolves to its authored `(-134,14)` + Z-float.

**Authoring tips**
- *Layered stack items* (bowls, burgers, cakes): author `data-dx/dy` so layers fan into a readable
  column or arc — auto-radial collapses to ~0 when every layer shares a center.
- *Laid-out items* (furniture, PCs, gadget kits): let auto-radial handle it, or author vectors that
  echo an exploded-assembly diagram.
- Keep parts ≤ ~10 for legibility; give each a real `data-label`.
- Pair with `reveal` on the card so the whole scene enters gracefully before it's interactive.

---

## 3. Roadmap atoms (not yet shipped — add here in the same format)

Graduate an atom by: writing its `assets/` file(s), adding its **What/Tech/Fallback/Needs** block
here, listing it under "Shipped" in `SKILL.md`, and proving it in `demo.html`.

- **`parallax`** — scroll-linked layer depth. Tech: `IntersectionObserver` + scroll ratio → per-layer
  `translateY`. Fallback: static. (Replaces Elementor Motion-FX — 37 scroll effects on the acai site.)
- **`marquee`** — duplicated-track `translateX` keyframe loop for a news/menu/logo ticker. Fallback:
  static strip. Needs: a real feed if labeled "live".
- **`flip`** — CSS 3D flip card (`rotateY`, `backface-visibility`) front↔back on hover/tap. Fallback:
  show back stacked / tap-toggle. (Replaces Elementor flip-box.)
- **`sticky-header`** — condense/shrink header past a scroll threshold via a class toggle. Fallback:
  plain sticky.
- **`tilt`** — pointer → 3D `rotateX/Y` on a card (shared with `xv`'s tilt helper). Fallback: none.
- **`count-up`** — per-digit `translateY` odometer to a target on scroll-in. Fallback: final value.
  Needs: real number; static/`—` if "live".
- **`carousel`** — minimal hero/testimonial slider (pointer + snap) without vendoring Swiper.
- **`cursor-spotlight`** — radial-gradient light following the pointer over a hero. Fallback: static.
