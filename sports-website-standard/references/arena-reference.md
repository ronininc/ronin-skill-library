# Arena Reference — Desert Diamond Arena (house model)

The house **visual/spatial reference** for arena-football sites (seat viewer, ribbon board,
LED ring, 50-yard field). Model on **Desert Diamond Arena, Glendale, AZ** — the Arizona
Rattlers' real 2026 home.

> **Truth rule:** this is a *reference model for look & spatial layout only*. Do NOT state that a
> client team (e.g. Valley Titans) plays here unless it's confirmed true. Any venue/schedule fact
> that appears as on-site copy must be verified first (see "Verify before publishing" below).

## Venue facts (confirmed)
- **Name:** Desert Diamond Arena. **City:** Glendale, Arizona (Phoenix West Valley sports district).
- **Type:** enclosed multipurpose **indoor arena** with a center-hung LED scoreboard and
  **LED ribbon/fascia boards** around the bowl — the real-world basis for the ribbon-board marquee
  and the arena "LED ring" look.
- **Tenant:** Arizona Rattlers (IFL) play their 2026 home schedule here (season opener Mar 28, 2026).
- History (context only, not for on-site copy): opened 2003; previously Glendale Arena → Jobing.com
  Arena → Gila River Arena → renamed Desert Diamond Arena (2022); former NHL Coyotes venue.

> **Verify before publishing** (do not hard-state without a source check at build time): exact seating
> capacity, precise section/row counts, current tenant list, and any schedule. These change; confirm
> against azrattlers.com / the arena site before they become visible text.

## Seat-map data model (drives the 2D map AND the 3D seat viewer)
Keep venue geometry in one JSON block so the 2D map and the WebGL viewer read the same source.

```js
const ARENA = {
  name: "Desert Diamond Arena",
  city: "Glendale, AZ",
  // Bowl = concentric tiers around a rectangular arena-football field.
  tiers: ["floor", "lower", "club", "upper"],
  // Sections run around the bowl; sides face the sidelines, ends face the end zones.
  zones: [
    // id, tier, side, angle(deg around bowl), rows, viewPoint {x,y,z} for the 3D camera target
    { id: "L-101", tier: "lower", side: "west-sideline", angle: 270, rows: 20, view: { x:-14, y:6,  z:0 } },
    { id: "L-110", tier: "lower", side: "east-sideline", angle: 90,  rows: 20, view: { x: 14, y:6,  z:0 } },
    { id: "L-120", tier: "lower", side: "north-endzone", angle: 0,   rows: 18, view: { x: 0,  y:6,  z:-26 } },
    { id: "U-210", tier: "upper", side: "east-sideline", angle: 90,  rows: 24, view: { x: 22, y:16, z:0 } }
    // …extend around the full bowl; keep symmetric N/S/E/W.
  ],
  ledRing: { present: true }, // enables the ribbon-board look
};
```
- **2D map:** render zones as SVG polygons positioned by `angle`/`tier`; click → highlight + show a
  static "view from here" image if one exists.
- **3D viewer:** low-poly bowl shell + field at origin; selecting a zone tweens the camera to its
  `view` point (target = field center) over ~1.5s. Pause render when off-screen.
- Populate real section IDs/rows from the venue's actual manifest when a build needs true seat data;
  the sample above is a spatially-correct placeholder, not real inventory.

## Arena-football field dimensions (for the 50-yard scrollytelling + field render)
Indoor/arena football standard (confirm against the client's league rules if it differs):
- Playing field **50 yards** long between goal lines; **8-yard end zones** (≈66 yards total).
- Field width **85 feet** (≈28.3 yards) — much narrower than outdoor.
- **Padded boards / dasher walls** enclose the field ("wall-collision" events reference these).
- **Rebound nets** flank the uprights behind each end zone (the "Rebound Net" ticket effect motif).
- Uprights are narrower than outdoor. Yard lines every 5 yds; hash marks; end-zone team art.

Use these for the SVG field so the scrollytelling geometry is real, not a generic gridiron.
