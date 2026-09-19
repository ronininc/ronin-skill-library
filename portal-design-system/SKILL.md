---
name: portal-design-system
description: >-
  A self-contained dark "fintech" CSS design system in a single <style> block — CSS-var color
  tokens (ink/panel/fg/muted + cyan/blue/violet/gold/red accents + a spectral gradient), and the
  full component kit built on them: sticky header + crest, panels, pill tabs, ghost/CTA buttons,
  forms, data tables with tabular-nums, semantic evidence chips (verified/market/modeled/pending),
  a dashed dropzone + upload bars, toast + modal ("pop") shells, avatars, a print stylesheet for
  clean PDF export, and a mobile block that stops iOS zoom-on-focus. Use WHENEVER you need a
  polished dark dashboard / portal / admin / CRM / investor-console look with ZERO CSS framework
  (no Tailwind/Bootstrap) — trigger on "dark fintech UI", "admin dashboard styling", "portal look",
  "give it that dark investor-console feel", "data table + chips + tabs", "no-framework dark theme",
  or as the styling layer under vanilla-spa-shell / vanilla-svg-charts / white-label-branding. It is
  the design layer those three frontend skills expect; pairs with website-build-standard for a
  productized client build. The tokens are engineered so white-label-branding can reskin the whole
  thing by overriding three CSS vars at runtime — keep colors as vars, never hard-code hex in rules.
---

# Portal Design System — dark "fintech" CSS, one <style> block, zero framework

## What it is / when to use
One drop-in `<style>` block that skins an entire gated dashboard/portal in a dark
"fintech" aesthetic: token-driven colors, panels, pill tabs, forms, data tables,
evidence chips, uploads, modals, toasts, a print sheet, and a mobile hardening
block. No Tailwind/Bootstrap/CSS-in-JS. Use it as the visual base under any
single-file SPA (it is the styling layer `vanilla-spa-shell`, `vanilla-svg-charts`
and `ops-console` all assume), and design it so `white-label-branding` can reskin
it live by overriding three CSS vars.

## Reference implementation
Extracted from the Wavelygth investor portal (patterns only, no client data):
- `~/Projects/clients/wavelygth/portal/index.html` **L11-166** — the entire `<style>`.
  - **L12-18** — `:root` token block (the whole palette + type stacks + `--spectral` gradient).
  - **L8-10** — the Google Fonts `<link>` (Fraunces + Space Grotesk) with `preconnect`.
  - L19-23 reset + `.wrap` container; L26-40 header/crest/avatars; L42-54 `.pop`/`.popCard` modal shells; L56-63 panels + type scale + responsive `.grid`; L65-72 forms + `.cta`/`.err`/`.note`; L74-78 auth card; L80-89 dashboard hero + `.tabs`/`.tab`; L91-103 `.dropzone` + upload bars + `textarea`/`.kindBadge`; L105-117 tables + `.chip.verified/market/modeled/pending` + `.tblwrap`; L119-123 chart holders; L125-139 POF sheet **plus the `@media print` block**; L141-151 admin bits + `.sysAct`; **L152-162 the `@media(max-width:640px)` block**; L163-165 `.hidden` + `.toast`.

## The token contract (copy L12-18 verbatim, then rename nothing)
```css
:root{
  --ink:#05070a; --panel:#0a0e13; --panel2:#0e141b; --fg:#eef2f6; --muted:#8b97a6;
  --faint:#586472; --line:rgba(255,255,255,.10); --cyan:#38e6d0; --blue:#5b8cff;
  --violet:#a884ff; --gold:#e7c78a; --red:#ff7a7a;
  --spectral:linear-gradient(90deg,var(--cyan),var(--blue),var(--violet));
  --head:'Space Grotesk',system-ui,sans-serif; --serif:'Fraunces',Georgia,serif;
}
```
Roles: `--ink` = page bg, `--panel`/`--panel2` = surfaces, `--fg`/`--muted`/`--faint`
= text tiers, `--line` = hairline borders, accents drive chips/charts, `--spectral`
is the signature gradient for CTAs, avatars, and the wordmark. **Every rule reads a
var — no rule hard-codes a hex.** That is what makes the whole system re-skinnable.

## How to reapply it
1. In `<head>`: add the fonts `<link>` (L8-10) — always with real fallbacks
   (`system-ui`, `Georgia`) so it renders before/without the webfont.
2. Paste the full `<style>` (L11-166) into the page. Nothing else is required; it
   is self-contained and dependency-free.
3. Build markup against the class vocabulary:
   - Layout: `.wrap` (max 1120px, gutter) → `<header><div class="wrap bar">…` → `<main class="wrap">`.
   - Cards: `.panel`; grids `.grid.cols2` / `.grid.cols31` (collapse to 1-col under 900px).
   - Nav: `.tabs > .tab[data-view]`, add `.on` to the active one (see `vanilla-spa-shell`).
   - Buttons: `.cta` (gradient primary), `.ghost` (outline; `.on` for toggled), `.mini`, `.iconBtn`, `.linklike`.
   - Type: `h1` (serif display), `h2` (uppercase tracked label), `.kicker`, `.spectral-text`.
   - Tables: `<div class="tblwrap"><table>…`; right-align numbers with `td.num`/`th.num` (tabular-nums).
   - Evidence: `<span class="chip verified|market|modeled|pending">…`.
   - Uploads: `.dropzone`(`.drag` while dragging) + `.upList > .upItem`(`.ok`/`.err`) with a `.bar > i` progress fill.
   - Modals: `.pop.hidden` wrapper + `.popCard` (toggle `.hidden`); `.toast` (add/remove `.show`).
   - Print/PDF: nothing to add — the `@media print` block already hides chrome and re-inks a `.pofSheet` for a clean statement export.
4. To make it brandable, layer `white-label-branding` on top: it overrides
   `--blue`/`--cyan`/`--ink` (and rebuilds `--spectral`) at runtime.

## Gotchas
- **iOS zoom-on-focus:** the `@media(max-width:640px)` block sets `input,select,textarea{font-size:16px}` on purpose — inputs under 16px make Safari auto-zoom on focus. Do not "tidy" that to a smaller size.
- **`--panel2` vs `--panel`:** inputs/textarea/modals use `--panel2` (one step lighter than `--panel`) so fields read as inset against cards. Keep both tokens.
- **`.hidden` uses `!important`** (`display:none!important`) so it always wins over a component's own `display`. Show/hide by toggling this class, which is exactly what the SPA shell does.
- **Chip class == data value:** chips are styled by the literal strings `verified|market|modeled|pending`, so server payloads emit those exact tokens (see `vanilla-svg-charts`/evidence rendering). Rename in both places or not at all.
- **Print sheet is opt-in by structure:** clean PDF export only works for content inside `.pofSheet`; the print block hides `header`, `.tabs`, `.pofActions`. Wrap anything meant to print in that container.
- **The mobile `.tabs` becomes a horizontal scroll-strip** (`flex-wrap:nowrap;overflow-x:auto`, scrollbar hidden). Expect many tabs to scroll, not wrap, on phones — that is intended.
