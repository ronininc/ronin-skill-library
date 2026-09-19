---
name: local-seo-location-pages
description: >-
  The programmatic local-SEO page-fan-out generator for a static site: from ONE data array of locations (or target
  cities) + ONE template function, emit one dedicated, individually-indexable landing page per location — each with
  its own LocalBusiness/Restaurant JSON-LD (real NAP + geo), a canonical URL, a maps deep-link, a location switcher,
  and cross-links to sibling locations — plus a hub page (with an optional pin map) and matching sitemap entries.
  This is the pSEO technique that turns a single-page brochure into N pages that rank for "<business> in <city>".
  Use WHENEVER a build has MORE THAN ONE physical location, or wants to rank in nearby cities/neighborhoods:
  "a page per location", "per-city landing pages", "location pages for SEO", "we have 8 stores, give each its own
  page", "rank for the surrounding towns", "multi-location site", "location switcher + store finder", or "generate
  the location pages from a list". It EXTENDS website-build-standard (which builds the ONE site; this fans it out to
  per-location pages and their JSON-LD/sitemap), and is DISTINCT from geo-directory-prospecting (that mines geo
  directories for INBOUND leads — this PUBLISHES outbound landing pages), auto-blog-network (a blog-content network,
  not location NAP pages), and single-source-data-embed (that inlines assets into one self-contained file — orthogonal;
  a location generator can still inline per-page). Pairs with business-profile-recon (pull each location's REAL NAP —
  never fabricate an address, phone, or hours).
---

# Local SEO Location Pages

## What it is / when to use / what it composes with
A build step (Node `.mjs` or Python) that reads a small **`LOCATIONS[]`** data structure and a **`page(loc)`**
template, then writes one static HTML file per location into a predictable path (`/locations/<slug>.html` or
`/<segment>/<slug>/index.html`). Each page is a real, standalone, indexable local landing page — its own title,
canonical, `LocalBusiness`/`Restaurant` JSON-LD, address/phone/hours, a Google Maps deep-link, and a nav that
lets a visitor switch locations. A hub/index page lists all of them (optionally on a pin map), and the sitemap
gets an entry per page. The whole point is search reach: one page that ranks in each city, not one page trying
to rank everywhere.

- **EXTENDS `website-build-standard`** — build the site first; this adds the per-location fan-out + their structured
  data. The single-site immersive centerpiece, media editor, deploy, etc. all still come from the base skill.
- **Feed it from `business-profile-recon`** — every address/phone/hours on a location page must be the location's
  REAL verified NAP. Never placeholder or invent one; a wrong NAP actively hurts local ranking and trust.
- **Orthogonal to `single-source-data-embed`** — you can still base64-inline each page's assets for a self-contained
  artifact; that's a different concern from the page fan-out.
- Distinct from `geo-directory-prospecting` (inbound lead mining) and `auto-blog-network` (blog content network).

## Reference implementation — exact source
- **Node generator (clean canonical form):** `clients/berry-divine/build-locations.mjs`
  - `LOCATIONS[]` (array of `{slug, name, area, street, city, tel, hours, tag?, blurb, noOrder?}`) + `page(l, i)`
    (~line 46+) → `writeFileSync('./locations/<slug>.html', page(l,i))` in the trailing loop (~line 202).
  - Per-page `application/ld+json` `Restaurant` node with `name/url/telephone/address(PostalAddress)` (~line 6+ of
    the template) and a canonical URL `.../locations/<slug>.html`.
  - `navDropdown()` / `otherLocationsLinks(current)` — the location switcher + sibling cross-links (~line 34–44).
  - Round-robin hero image pool so each page looks distinct (`HEROES[i % HEROES.length]`).
- **Python generator (adds a map hub + per-location commerce routing):** `clients/fiesta-mexicana/build/build_site.py`
  - `LOCATIONS` list of dicts (`slug, city, state, region, zip, lat, lng, hours, hero`) → one
    `mexican-restaurants/<slug>/index.html` per location (`out.write_text(body)`, ~line 472) + the hub `index.html`
    (~line 575).
  - `mapdata = json.dumps([{slug, city, lat, lng, href} …])` (~line 506) — the store-finder pin map on the hub.
  - `order_url(l)` / `has_online_order(l)` (~line 253) — per-location ordering link routing (present vs link-out),
    the honest-degrade seam for locations without online ordering.

## How to reapply
1. **Model the data.** One array of location objects: `slug` (URL-safe), display `name`/`city`, `street`, `zip`,
   `tel`, `hours`, `lat`/`lng` (for the map), and per-location flags (`noOrder`, `tag: 'new'|'soon'`).
2. **Write the page template** — a pure `(loc, i) => html`. Include per-page: `<title>`/meta, `<link rel="canonical">`,
   `LocalBusiness`/`Restaurant` JSON-LD (name, url, telephone in `+1-XXX-XXX-XXXX`, `PostalAddress`, geo, openingHours),
   the location switcher, sibling cross-links, and a Maps deep-link (`encodeURIComponent("<name>, <street>, <city>")`).
3. **Emit files** to a stable path (`/locations/<slug>.html` or `/<segment>/<slug>/index.html`) and a hub page that
   lists every location (optionally a pin map from the lat/lng).
4. **Regenerate the sitemap** with one `<url>` per generated page (and the hub); keep robots.txt allowing them.
5. **Wire the build** into the deploy (a `build` npm script / `node build-locations.mjs` before `cf-deploy`), and copy
   the generated dir into `dist/`.

## Gotchas — real pitfalls from the code
- **NAP must be REAL and consistent.** The single biggest local-SEO failure is a fabricated or inconsistent address/
  phone. Source every field via `business-profile-recon`; if a location has no online ordering or opens later, model
  that (`noOrder`, `tag:'soon'`) — never invent hours or a phone to fill the template.
- **Escape everything interpolated** into HTML and JSON-LD (`esc()` in the reference) — location names/blurbs are data.
- **Canonical per page.** Each location page needs its OWN canonical (self-referential), or duplicate-content
  signals collapse the fan-out back into one page.
- **Give pages real differentiation.** Round-robin heroes + a unique blurb/area per location keep them from reading
  as thin near-duplicates (which Google demotes). The switcher + sibling links also build internal linking.
- **Phone formatting is structured data.** JSON-LD `telephone` should be E.164-ish (`+1-602-555-1234`); the display
  string can differ, but keep the structured one clean.
- **Regenerate the sitemap in the SAME build.** A page that isn't in the sitemap (and a stale sitemap after you add a
  location) is the quiet way these fan-outs go un-indexed.
- **Two dialects, one pattern.** The Node and Python references prove the technique is language-agnostic — it's the
  `data[] + template → one file per row + hub + sitemap` shape that matters, not the runtime.
