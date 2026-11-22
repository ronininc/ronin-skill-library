# Auto-Prebuild — every qualified lead ships with a starter site attached

The orosolu.org promise isn't a list of names — it's a list where **each qualified
lead already has a house-standard website built and attached**, populated from the
deep dive. When the operator sends the lead list, a prebuilt site rides along for
every shop, so the pitch is "here's your site, live in a click" instead of "we could
build you a site."

**Every qualified (A/B/C) and every targeted shop gets a prebuild. DROP shops don't**
(no site for a shop we'd never build for). This runs automatically at the end of each
deep dive — it is not an optional extra step.

## What a prebuild is

A single-page, house-standard **starter** site built with `website-build-standard`'s
defaults — deliberately the lightweight 2D standard mode, not the full immersive
centerpiece (that upgrade happens when the lead converts). Each prebuild ships:

- **Hero = video slot** with the shop's best photo as the poster, so it looks alive
  immediately and their 10–20s reel drops straight in. If the deep dive found a
  usable video, wire it; otherwise the poster + slot.
- **Photo frames below the hero**, populated with the cataloged `OWN` photos; empty
  slots are branded `CLIENT-UPLOAD` fallbacks, never broken boxes.
- **Real facts loaded** — name, concept, hours, address(es), phone, menu/prices —
  each sourced or marked `UV`. Never invent; `UV` shows on anything unconfirmed.
- **Socials wired** where found (Instagram/Facebook/TikTok); clean open slots where not.
- **The media-editor kit** (`website-build-standard/assets/media-editor-kit.html`),
  builder-only, so the operator/client swaps media with no code.
- **Payment-ready order CTA** pointing at their current ordering (or a placeholder
  that becomes commission-free ordering via `cloudflare-ordering-worker`).
- **Inquiry routing** — the prebuilt preview routes to `leads@orosolu.org` until the
  client is onboarded; one labeled line to change at launch (never hard-coded per the
  house standard — it's a config slot).
- A **README** per site: media-swap steps, the `UV`/before-launch list, and the
  Cloudflare deploy steps.

## How to produce them

Use the generator at `assets/prebuild-generator.py` (or follow its shape): it stamps
one `index.html` + `README.md` per shop from the deep-dive data — palette, facts,
socials, menu, and the real hero/gallery image URLs. It inlines the media-editor kit
and derives each site folder as `prebuilt/<slug>/`. Then:

1. **Verify each site** with headless Chromium: zero JS `pageerror`s, hero + sections
   render, and the editor is present locally / absent on a hosted host (the kit's gate).
2. **Put each site in the `sites/` folder** as `sites/<slug>.html` (self-contained),
   shipped in the same zip as the workbook.
3. **Link them from the Lead Workbook** (`references/lead-workbook.md`) — the Leads and
   Websites tabs hyperlink each row to `sites/<slug>.html`, so clicking opens the
   rendered template. The workbook and the sites travel together in one zip.

## Honesty rules (same as everywhere)

- **Real media only, rights respected.** Prebuilds show the shop's *own* photos
  (`OWN`) as the starter; `UNCLEAR` third-party photos are not baked in, they're left
  as `CLIENT-UPLOAD` slots. The client confirms/owns everything before launch.
- **No invented facts.** A prebuild with a guessed menu or made-up hours is a
  liability on a real business's would-be site. `UV` chips stay visible in the page.
- **Starter, not final.** The prebuild is the hand-raise: a real, standard-compliant
  draft the client can see themselves in. The full immersive build + live ordering
  come when they say yes.
