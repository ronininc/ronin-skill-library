---
name: cinematic-evidence-walkthrough
description: >-
  A self-contained, static "memory-view" walkthrough PLAYER: a full-bleed cinematic video walk
  through the rooms/positions of ONE thing (an estate, a facility, a build, a venue), with
  holographic EVIDENCE TAGS pinned to the objects inside each frame — select a glowing tag to
  inspect it in place (a description + a SOURCED figure marked verified / modeled / pending), plus
  a whole-asset "dossier" card of headline figures. The visitor drives the whole journey: a drag
  progress scrubber, a thumbnail rail, prev/next arrows, number keys, swipe, and an auto-tour;
  everything is preloaded so movement is instant. One manifest (SCENES + MEDIA + one dossier
  object), zero framework/server, Cloudflare-Pages-ready. This is a FOCUSED, EXTRACTABLE instance
  of the house `immersive-evidence-workspace` skill — specifically the per-item first-person
  "walk" deliverable — and reuses its evidence contract (every figure has a source + a status,
  never a bare number). Use WHENEVER the deliverable is a cinematic room-by-room / stop-by-stop
  tour of a single property or asset: "estate walkthrough", "memory-view tour", "walk the
  property / the building / the space", "video tour with evidence tags / hotspots pinned to
  things", "Ready-Player-One memory view", "scrubber tour of the rooms", "cinematic property
  reel with clickable specs", "digital-twin walk", or a listing's first-person "enter / walk this
  one" view. Do NOT use it to DRIVE and RECORD a live web app (that is `video-walkthrough`), nor
  for the multi-product holographic TABLE / explore-the-system map (that is the parent
  `immersive-evidence-workspace`). Guardrails: it is a hand-authored client-facing player, not a
  recorder; every tag/dossier figure carries a source + honest status (verified/modeled/pending —
  a live/observed number is never "verified" by inflation); builder-editable before deploy, locked
  static for visitors after; keep the three status colors distinct — they carry meaning.
---

# cinematic-evidence-walkthrough — the memory-view room-walk player

## What it is / when to use
A single static HTML file that plays a **cinematic walk through one asset**, room by room (or
stop by stop), in real footage. Over each frame float **holographic evidence tags** pinned to the
objects in view; selecting a tag opens an inspect card **in place** with a description + a
**sourced** figure graded `verified` / `modeled` / `pending`. A separate **dossier** card holds
the asset's headline ledger. The visitor navigates by drag-scrubber, a thumbnail rail, arrows,
number keys, swipe, or a hands-off **auto-tour** — and it's all preloaded, so travel is instant.

Reach for it whenever the job is a **first-person tour of ONE thing** (an estate, a facility, a
venue, a build, a single listing) where you want the specs to live *on the objects*, not in a
sidebar. It is the polished, sellable client-facing player — distinct from the two things it is
often confused with (see below).

**Extends / part of `immersive-evidence-workspace`.** That house skill is the umbrella: a
holographic *table* of many products where you `select → enter → evidence`, and each spatial
product exposes a `walk` URL for a first-person walkthrough. **This skill IS that walk
deliverable, extracted and standalone** — one asset, one manifest, no table. It reuses the parent's
non-negotiable evidence law (every figure has a **source** + a **status**; never a bare number)
and its status palette (`--verified` cyan / `--modeled` blue / `--pending` gold). When a build
needs the multi-product table or the "explore the system" node map, use the parent; when it needs
the per-asset cinematic walk, use this.

**Not `video-walkthrough`.** That skill DRIVES a real web app in a browser and RECORDS a captioned
GIF/MP4 of its screens. This is the opposite: a hand-authored player the *visitor* drives through
pre-shot footage of a physical space. Different tool, don't cross them.

## Reference implementation (lift the proven code)
The proven player is a single file, byte-identical in two places under
`~/Projects/clients/wavelygth/`:
- `walkthrough/index.html` — the standalone hosting package (467 lines).
- `public/camelback/index.html` — the same file served inside the portal build. **Diff-identical**
  to the above; lift either. `walkthrough/README.md` documents deploy + editing; `walkthrough/_headers`
  is the Cloudflare cache rule.

Map of the one file (`index.html`):
- **Manifest (edit this per asset):** `L250–308`
  - `ESTATE` (the dossier object): `name`, `badge`, `ledger` = array of `[label, value, source, status]` — **L250–261**
  - `SCENES` (one entry per room/stop): **L262–306** — each `{ id, key, wing, name, pc, dc, desc, spots[] }`
  - `MEDIA` (key → media map): **L308** — `{ "<key>": { v:"assets/x.webm", p:"assets/x.jpg" }, … }`
- **Engine (leave alone; it's generic):** `L310–464`
  - Preloaded, primed video pool for zero-latency travel — **L318–328**
  - Thumbnail rail build — **L330–337**
  - Drag progress scrubber (pointer capture + index-from-x math) — **L339–348**
  - Evidence tags: `sideFor(x,y)` auto-placement + `renderSpots(scene)` — **L350–362**
  - Inspect card: `inspect(k)`, `chip(status)`, `positionCardAt(spotEl)`, `closeInspect()` — **L363–395**
  - Dossier card: `openDossier()` — **L376–386**
  - Travel: `go(idx)` — swaps front/leaving scene, sets per-scene `--pc/--dc`, updates caption/rail/scrubber, re-renders spots — **L397–414**
  - Controls (prev/next/dossier/cinema/tags buttons) — **L416–425**
  - Auto-tour (7.2 s tick) — **L427–431**
  - Keyboard (←/→, Esc, `e` tags, `d` dossier, Space play/pause, `1–9` jump) — **L433–441**
  - Swipe-to-walk — **L443–446**
  - Depth **parallax that keeps tags pinned** (stage + spots share ONE translate) — **L448–454**
  - Boot (prime scene 0, first caption, render spots) — **L456–464**
- **CSS (the whole look):** `L40–201` — spots/tags/connectors **L70–103**, inspect card **L105–132**,
  HUD **L134–149**, caption **L151–164**, arrows **L166–169**, dock (scrubber + rail) **L171–194**,
  mobile block **L196–200**.
- **Body shell + `data-mode`:** `L203–247` (`<body data-mode="estate-walk">`; the other mode is `showroom`).

## The manifest contract (the whole editable surface)
Everything a new build changes lives in three JS objects near the top of the `<script>`. The engine
below them never needs to change.

1. **`SCENES`** — an ordered array, **one entry per room/stop**. The array's length is the tour length
   (rail, scrubber ticks, number keys all derive from it). Each entry:
   - `id` — slug (internal).
   - `key` — the **join key into `MEDIA`** (e.g. `"01_terrace"`). Must match exactly.
   - `wing` — the short eyebrow/group label (shown on the caption eyebrow, the readout, the rail thumb).
   - `name` — the display title; the engine italicizes the **last word** (`Infinity <em>Terrace</em>`).
   - `pc` — per-scene **accent** hex (glow/tags/scrubber tint for this room).
   - `dc` — per-scene **description tint** hex (body copy color, matched to the room's lighting).
   - `desc` — one-line caption paragraph.
   - `spots[]` — the evidence tags pinned in this frame. **Each spot:**
     - `x`, `y` — position over the frame **in percent** (0–100), measured on the played video.
     - `label` — the tag's tiny mono kicker (e.g. `"Glass span"`).
     - `val` — the headline figure shown on the tag and big in the card (e.g. `"24 ft"`).
     - `note` — the inspect-card description sentence.
     - `src` — **the source** of the figure (e.g. `"Curtain-wall shop dwg"`). Never omit.
     - `st` — the **status**: `"verified"` | `"modeled"` | `"pending"`. Drives the color dot + chip.
2. **`MEDIA`** — a flat map `key → { v, p }`: `v` is the looping clip (`.webm`/VP9 preferred; `.mp4`
   also fine), `p` is a poster still (`.jpg`) shown until the clip is primed. Keys must cover every
   `SCENES[i].key`.
3. **`ESTATE`** (the dossier) — `name`, `badge`, and `ledger`: an array of **`[label, value, source,
   status]`** tuples that render as the asset's headline financials/figures card. Same four-part
   evidence shape as a spot (`status` ∈ verified/modeled/pending).

## The player mechanics (what the engine gives you for free)
- **Zero-latency travel.** All clips are created up front, `.load()`ed, and each is play→pause primed
  on a stagger so the first frame is decoded before the visitor arrives (`L318–328`). Travel just
  toggles `.front`/`.leaving` classes with a cross-dissolve+scale; it never waits on the network.
- **Five ways to walk, one `go(idx)`.** Drag scrubber, rail thumbnails, prev/next arrows, `←/→`,
  number keys `1–9`, and swipe all resolve to `go(idx)` (wraps modulo length). `go` also swaps the
  per-scene `--pc/--dc` CSS vars, so the whole chrome recolors per room.
- **Auto-tour.** The ▶ button (or Space) starts a 7.2 s-per-scene hands-off tour; any manual nav
  stops it (`stopTour()` is called by every control).
- **Tags pinned by shared parallax.** On `mousemove` the stage AND the spots layer get the **same**
  translate (`L448–454`), so tags appear glued to their objects as the frame drifts. This is why the
  pin illusion holds — do not parallax them separately.
- **Auto tag placement.** `sideFor(x,y)` (`L351`) picks whether a tag flips up/down/left/right based
  on where the spot sits, so tags never run off-frame. The inspect card then positions itself beside
  the selected spot via `positionCardAt` (clamped to the viewport).
- **Inspect + dossier are the same card element**, re-templated: a spot opens `inspect(k)` (label +
  note + val + source chip); the ⌘ button opens `openDossier()` (the ledger). `body.inspect` dims the
  other spots and shows the backdrop; Esc / backdrop / × closes.
- **Cinema + tags toggles.** ▭ adds letterbox bars (`body.cinema`); ◈ / `e` hides all tags
  (`body.notags`) for a pure footage view.
- **`data-mode`.** `estate-walk` (this multi-room build) vs `showroom` (the reusable one-scene /
  one-cinematic-per-position default). Set on `<body>`.

## How to reapply it (point it at a new video + manifest)
1. **Copy the file.** Drop `walkthrough/index.html` into the new project as the tour page (or under
   `public/<asset>/index.html` to serve it inside a portal build, exactly as camelback does).
2. **Drop in footage.** Put one looping clip + one poster per stop in `assets/` (short clips — the
   reference rooms are 1–3 MB `.webm`, all well under Cloudflare's 25 MiB/file cap; total ~15 MB).
   Prefer descriptive, ordered names (`01_terrace.webm` / `.jpg`).
3. **Rewrite the three manifest objects only** (`L250–308`):
   - `SCENES`: one entry per stop, in walk order; set `key` to the media key, `wing`/`name`/`desc`,
     the per-scene `pc`/`dc` accents, and the `spots` with **`x`/`y` in percent** over the frame.
   - `MEDIA`: map each `key` to its `{ v, p }` paths.
   - `ESTATE`: the asset name/badge + the `ledger` tuples for the dossier.
   - Update `<title>`, the brand crest SVG/wordmark, and the readout copy (`L210–222`) to the client.
4. **Place the spots by eye.** Load the page, watch a room, and nudge each spot's `x`/`y` percent
   until the pin sits on its object at the clip's resting frame. (There's no editor UI — this is a
   hand-authored tour; placement is a manual pass. Budget time for it.)
5. **Reskin (optional).** Override the root CSS vars for the client palette (`--cyan/--blue/--violet`
   and the neutrals). **Keep `--verified/--modeled/--pending` visually distinct** — they encode
   meaning, not decoration.
6. **Deploy static to Cloudflare Pages.** Upload the folder contents so `index.html` sits at the root
   with `assets/` and `_headers` beside it — **no build command, no framework**. Ship `_headers`:
   `no-store` on `/index.html`, `public, max-age=31536000, immutable` on `/assets/*`. Same files work
   on Netlify / S3+CloudFront / GitHub Pages (non-CF hosts ignore `_headers`).

## Builder-editable-then-locked pattern
This player sits at the "locked" end of the parent skill's law #2 (*builder before deploy; visitors
never edit after*). There is **no runtime editor exposed to visitors** — the tour is authored by
editing the manifest in source, then shipped as frozen static files. The editing surface is the three
manifest objects (author-side, pre-deploy); after deploy the file is immutable content and the
visitor can only *drive* it (scrub/select/tour), never change it. If a build needs a client to upload
their own footage into slots via a guided boot-prompt, that's the parent
`immersive-evidence-workspace` template's job — compose the two: use its media boot-prompt to fill
the slots, keep this player as the render.

## Gotchas (from the code + README)
- **`SCENES[i].key` must exist in `MEDIA`.** The join is by string key; a typo yields a black scene
  with only the poster (or nothing). `med(k)` returns `{}` on a miss and fails quiet.
- **`x`/`y` are percent of the FRAME, not pixels, and are hand-placed** against the clip's resting
  composition. If the footage is re-shot or re-cropped, the pins drift — re-check placement. Autoplay
  loops mean "resting frame" is approximate; place spots where they read across the loop.
- **Parallax must move stage and spots together.** The pinned-tag illusion depends on `stage` and
  `#spots` receiving the identical translate (`L452–453`). Split them and the tags float off their
  objects.
- **iOS/Safari video quirks are already handled — keep them.** Clips are `muted`, `playsInline`
  (both the property and the two `playsinline` attributes), `loop`, `preload="auto"`; `.play()` is
  wrapped in `.catch()` because autoplay can reject. Don't strip these or mobile goes black/blocked.
- **Never open `index.html` from disk** to preview — `file://` security blocks the videos. Serve over
  http (`python3 -m http.server 8000`) or `wrangler dev`.
- **`_headers` is load-bearing.** Without `no-store` on the HTML, a redeploy can serve a stale shell
  against fresh assets; without the immutable rule the clips aren't cached and travel isn't instant.
- **Evidence honesty is the product.** Every `spot.st` and every `ledger` status must be truthful —
  a live/observed number is `verified` only if it's actually sourced-and-confirmed, a projection is
  `modeled`, an unconfirmed figure is `pending`. Do not inflate a status to make the card look
  stronger; the graded chip is the credibility of the whole piece (this is the parent skill's law #1).
- **Patterns only — no client data.** Author a fresh manifest for the new asset. Never copy another
  client's scenes, figures, sources, ledger, or footage into a new build.
- **Upscale ≠ native.** The reference README notes the shipped clips were 720p finished with an
  upscale+grade to read as 4K; when true high-res source exists, drop it in `assets/` under the same
  names. Don't claim native 4K over an upscale.
