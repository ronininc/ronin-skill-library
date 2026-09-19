---
name: svg-marketing-asset-generator
description: >-
  Turn a one-line text intent ("make a poster for the grand opening", "logo for
  Blue Fin Sushi", "flyer for happy hour") into a REAL, finished SVG marketing
  asset — poster, logo/badge, flyer, banner, or social card — composed
  deterministically in code (layout + type + palette + shapes), with NO diffusion
  model, NO weights, and NO external fonts (offline / CSP-safe). Use WHENEVER a
  client build needs to PRODUCE a branded graphic from a short description rather
  than research how to make one: "generate a poster/flyer/logo/banner/social
  card", "spin up a promo graphic", "make them a hero mark", "give me an SVG I can
  drop on the page or hand to print", or any create-verb + visual-noun request.
  COMPLEMENTS website-build-standard (drop the SVG into a hero/CTA slot) and
  white-label-branding (feed it the client's palette/monogram so every asset is
  on-brand). Do NOT use for charts/graphs (use vanilla-svg-charts) or for a
  photoreal raster image (that is a pluggable diffusion tier this skill only
  hands off to, never fakes).
---

# Intent → SVG Marketing-Asset Generator

## What it is / when to use

A **deterministic** pipeline that takes a short text intent and emits a genuinely
designed, self-contained `.svg` (plus an optional full-bleed `.html` wrapper) for
a marketing asset. No model gamble: the visual is *composed in code* from a parsed
brief, so the same request always yields the same bytes, it works fully offline,
and it never invents a fact the caller did not supply.

Use it any time a build must **produce** a flat design piece — poster, flyer,
handbill, sign, logo/badge/crest/emblem, banner/billboard/wallpaper/thumbnail,
social card — from a sentence. It is the always-available floor under any
"make me a graphic" feature; a photoreal raster/diffusion path is a *separate,
pluggable upgrade tier* (see Gotchas) that this lane hands off to but never
silently substitutes.

**Composes with:**
- `website-build-standard` — the emitted SVG scales into a hero, CTA, or gallery slot with no raster asset.
- `white-label-branding` — supply the client's palette + monogram to the brief so every generated asset is on-brand instead of seed-picked.
- `vanilla-svg-charts` — the sibling pattern for data viz; this one is for marketing/identity pieces.

## Pipeline (five stages)

1. **Route gate** — fire only on a *create verb* paired with a *visual noun*, and stand down when a competing-lane noun is present (video/site/app). Keeps "how do posters work" (no verb) and "make a promo video" (competing noun) out of the lane.
2. **Intent → brief** — parse the sentence into a structured brief: `subject`, `titleLines`, `kicker` (domain/occasion), `location`, `monogram`, `kind`, `palette`.
3. **Kind → layout family** — the requested kind selects a composition + aspect ratio (portrait poster vs. square emblem vs. landscape banner), so a logo is not just a relabeled poster.
4. **Brief → SVG** — compose gradients, an energy band, a monogram watermark, a fitted headline, kicker rules, an accent slab, and a bottom bar, all in inline SVG with offline font stacks.
5. **Write + hash** — write the `.svg`/`.html`, stem the filename with a content hash so output is replayable, and return `{ svg, svgPath, contentHash, servableUrl }`.

## Reference implementation (TSS-own)

- **Deterministic SVG engine** — `server/src/runtime/poster-design-engine.ts`
  - `parsePosterBrief()` — intent → brief — `poster-design-engine.ts:204`
  - Brief sub-parsers: `stripCommand()` :113 (strips "make me a … for a the"), `extractLocation()` :131 (city-abbr + state-code normalize), `extractKicker()` :148 (longest-first domain match), `stripEntityNoise()` :158, `extractExplicitName()` :188 (quoted / "called|named X" → the subject is the *name*, not the descriptor), `splitTitleLines()` :166 (balance 3+ words into 2 lines), `pickPalette()` :175 (sha256 seed → replayable variety).
  - Palettes: 6 hand-tuned dark-ground/one-accent schemes — `poster-design-engine.ts:48`.
  - Layout families: `EMBLEM_KINDS` / `BANNER_KINDS` sets :101-102; `renderPosterSvg()` :241 (portrait 1080×1440), `renderEmblemSvg()` :326 (square 800, roundel + name slab), `renderBannerSvg()` :377 (landscape 1600×600), dispatched by `renderDesignSvg()` :431.
  - Font fitting without a measure API: `CHAR_ADVANCE = 0.60` + `fitFontSize()` :229-234.
  - Write + content-hash stem: `generatePoster()` :459; `slugify()` :449.
- **Route gate** — `server/src/runtime/creative-design-command.ts:21` (`isCreativeDesignRequest`): `CREATE_VERB` ∧ `VISUAL_NOUN` ∧ ¬`OTHER_LANE_NOUN`.
- **Pluggable palette grounding (optional seam)** — `server/src/runtime/poster-reference-grounding.ts`
  - `paletteFromPixels()` :42 — derive a contrast-safe palette from *any* reference image bytes (downsample 12×12, sort by luminance/saturation, clamp grounds dark, lift accent). Deterministic, fail-open.
  - `accentOverrideFromTranscript()` :126 — an explicit color word in the request ("make it red") overrides the accent; the caller's word wins.
- **Proof/behavioral spec** — `tests/create-route/run.ts` (routing, brief parsing, determinism, prompt-to-enable-raster assertions).

## How to reapply in a CLIENT build

1. **Lift the engine file wholesale.** `poster-design-engine.ts` has zero third-party deps except `node:crypto` + `node:fs` — drop it into the build's server/worker. Keep the palettes or swap in the client's brand colors (this is the `white-label-branding` seam).
2. **Wire the route gate** in front of your intent router so "make a poster/logo/flyer…" produces an asset instead of falling through to a search/answer path.
3. **Feed brand into the brief.** Instead of `pickPalette(subject)`, pass the client's `{ground0,ground1,band,accent,ink,sub}` and monogram so every asset is on-brand and identical across runs.
4. **Serve the output.** Return the `svg` string inline (embed straight in HTML), plus a servable URL to the written file for print/download. The `.html` wrapper renders it full-bleed for preview.
5. **Extend layout families** by adding a `kind` set + a `renderXxxSvg()` (e.g. an Instagram square 1080×1080 "social-card" family) and one line in `renderDesignSvg()`. The aspect ratio and composition live entirely in that function.
6. **(Optional) Add a raster upgrade tier** as a *pluggable seam*: keep this vector generator as the always-available default and, when the caller wants a photoreal image, hand off to a diffusion endpoint — a cloud gen API in a client build — surfaced as an explicit "enable it" option. Never silently answer a create request with research or with a stub.
7. **(Optional) Ground the palette** by pointing `paletteFromPixels()` at any image source the client authorizes (their logo, a licence-clean stock image) instead of the seed palette.

## Gotchas

- **Determinism comes from the content-hash stem, not a clock stamp.** Stamp filenames with `sha256(svg).slice(0,10)`, never `Date.now()`, or the "same request = same file" replay guarantee breaks.
- **Font sizing is heuristic** (`CHAR_ADVANCE ≈ 0.60` for a heavy condensed sans). If you change the display font stack, re-tune the advance or the longest headline line will overflow/underfill — there is no text-measurement API server-side.
- **Offline / CSP-safe by design.** Only use web-safe font *stacks* (`'Arial Black', Impact, …`) — never `@import` or link an external font, or the asset breaks offline and under a strict CSP.
- **XML-escape every interpolated string** (`xmlEscape()`), including the subject and location, or a `&`/`<` in a business name produces invalid SVG.
- **Apostrophes are not name delimiters.** Explicit-name extraction keys on double quotes / "called|named X" only — a straight or curly apostrophe (`Vito's`) must never be read as a quote, or the subject gets truncated.
- **Kicker-was-the-whole-subject** ("a poster for coffee"): retain the pre-kicker phrase as the subject fallback so you don't render "Untitled".
- **Grounded palettes must clamp grounds dark and fail open** — a derived ground that is too light kills text contrast; if the reference is unreadable, keep the seed palette and say so rather than shipping an unreadable design.
- **A logo is not a poster.** Route each kind to its own family/aspect ratio; rendering a badge on a 1080×1440 portrait frame looks wrong even though it "works".
