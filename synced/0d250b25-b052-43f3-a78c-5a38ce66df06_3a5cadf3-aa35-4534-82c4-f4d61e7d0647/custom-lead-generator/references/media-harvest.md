# Media Harvest — catalog real media, wire the slots, never blind-download

Owner.com fills a new restaurant's site with the restaurant's own photos and video.
We do the same, honestly: **find and catalog** every usable real asset, map each to
a build slot, and flag anything the client must confirm or upload. We do **not**
scrape media files onto the client's site — that's both a rights problem and often
a fetch-blocked one. The build's drag-and-drop editor is where the client drops the
files they own; our job is to tell them exactly what goes where.

## The rule

- **Catalog, don't copy.** Record each asset's source URL, what it shows, a
  quality note, and a rights flag. Do not download image/video files into the
  site's `/assets`. If a build needs the real file, the client supplies it via the
  Edit Media editor.
- **Rights flag on every asset:**
  - `OWN` — from the restaurant's own website / Instagram / TikTok → **likely
    usable with the client's permission**. Still confirm before publishing.
  - `UNCLEAR` — Google/Yelp/DoorDash user-uploaded photos, press images → **rights
    unclear, client must confirm or replace.**
  - `CLIENT-UPLOAD` — no usable asset found for a needed slot → the client uploads.
- **Never present `UNCLEAR` media as ready-to-publish.** Catalog it as a reference/
  candidate only.

## What to harvest

Sweep the same profiles the fact sweep used, this time for media:

- **Logo / wordmark** — from their site header, IG profile pic, GBP. Note if it can
  be rebuilt as a clean **SVG** (per `website-build-standard` → `logo-svg.md`).
- **Hero-candidate video** — their own IG Reels / TikToks / site background clips.
  Apply the **10–20s rule**: flag clips in that range, muted-loop-friendly, as hero
  candidates; note longer ones as "trim needed." These are almost always `OWN`.
- **Food photography** — dish shots from IG, own site, and delivery item images.
  The gallery + menu-item slots draw from here.
- **Interior / exterior / ambiance** — room, storefront, patio; sets the vibe slots.
- **Team / owner** — if present; else the roster slot is `CLIENT-UPLOAD`.
- **Brand palette** — sample 2–4 hex colors from the logo and dominant photo tones.
  This feeds the build's palette directly, so the site matches their real brand.

## Social discovery — run every platform, expect several

Independent shops usually run **several** social accounts even with no website, so
never conclude "no socials" from one search. Run an explicit query per platform and
collect them all:

- Instagram — `"<name>" <city> instagram` and `site:instagram.com <name>`
- Facebook — `"<name>" <city> facebook` (watch for `/people/…` profile pages, and
  more than one page — many shops have a duplicate)
- TikTok — `"<name>" <city> tiktok`; distinguish the shop's **own** account from
  **customer buzz** (UGC people posting about them — still valuable social proof, but
  label it as UGC, not an official account)
- Yelp — always link the Yelp business page (reviews + photos), and note the count
- Snapchat / Google Business Profile / Nextdoor — check for place tags and posts

Record each with its URL and whether it's the operator's **own** account or UGC/place
tag. Wire the real ones into the site's social slots; leave clean open slots only for
platforms genuinely absent. A shop being "invisible" (no site) makes its socials
*more* important to find, not less.

**Socials are the media library, not just links.** Instagram, Facebook, TikTok,
Yelp, and Google photos/videos are where the prebuild gets its content — pull the
best food/interior shots and any short clips from these profiles to populate the
hero and gallery, so the site looks like *theirs* on first view. That populated look
is what makes the offer ("here's your site, already built") land. Rights-flag every
pulled asset (`OWN` = their own account; `UNCLEAR` = Yelp/Google user upload or UGC
TikTok → operator confirms before publish) and, where a file can't be pulled, keep a
`CLIENT-UPLOAD` slot naming exactly what to add.

## Pulling real photo URLs (the method that works)

Yelp/IG/FB block direct fetching, but their image **CDN URLs** are hotlinkable once
you have them. The reliable way to get them: open a **Google Images** search for the
business in the browser (`claude-in-chrome`) and extract the CDN URLs from the page:

```
navigate → https://www.google.com/search?tbm=isch&q=<name> <address>
javascript_tool → scan document HTML for https URLs ending .jpg/.jpeg/.png/.webp,
  strip query strings, keep hosts: yelpcdn / googleusercontent / ggpht / fbcdn /
  cloudfront / squarespace  (drop logos/icons/gstatic thumbnails)
```

This returns real `s3-media*.fl.yelpcdn.com/bphoto/<id>/1000s.jpg` (and `/l.jpg`)
photos of the actual food/interior. Pick a landscape one for the hero and a few for
the gallery, and **verify one loads** (navigate to it + screenshot) before embedding —
yelpcdn/googleusercontent hotlink fine. Embed the URLs directly in the site so it
renders populated. Rights: Yelp/Google user photos are `UNCLEAR` — fine for the
prebuilt pitch preview, flag them for the operator to confirm/replace at launch.
Headless (cron) runs can't drive the browser — there they fall back to reachable
sources (own site / Google Business / delivery-app CDNs) and `CLIENT-UPLOAD` slots.

## Quality notes to record

For each cataloged asset, a one-line note: rough resolution/orientation (is it big
enough for a hero? square for a card?), whether it's watermarked/branded by a third
party, and whether it's on-brand. This lets the builder pick the best real asset per
slot instead of the first one found.

## Slot wiring plan (the handoff)

Map `website-build-standard`'s visual slots to specific assets. Every slot resolves
to either a cataloged asset (with its rights flag) or `CLIENT-UPLOAD`:

| Build slot | Source asset (or CLIENT-UPLOAD) | Rights |
|------------|--------------------------------|--------|
| Hero (video or image) | e.g. IG oven reel ~15s | OWN — confirm |
| Logo | e.g. site wordmark → rebuild as SVG | OWN — confirm |
| Gallery cards | e.g. IG food set (list URLs) | OWN — confirm |
| Menu-item shots | e.g. DoorDash/own item photos | OWN/UNCLEAR per item |
| Interior / ambiance | e.g. Yelp interior shot | UNCLEAR — client confirm |
| Team / roster | (none found) | CLIENT-UPLOAD |

Deliver this as the **Media Manifest** (template in `assets/media-manifest.template.csv`)
so the builder pre-labels every drop zone and the client knows exactly which files
to supply.

## Boundaries

- Public profiles only; never scrape behind a login or defeat access controls.
- If a source blocks fetching, that asset is noted as "seen but not retrievable —
  client to supply," not routed around with shell/HTTP tools.
- Media harvest is reconnaissance, not appropriation: we're building a plan the
  client approves, not republishing strangers' photos.
