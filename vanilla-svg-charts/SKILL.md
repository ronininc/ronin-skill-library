---
name: vanilla-svg-charts
description: >-
  Dependency-free inline-SVG dashboard charts — NO Chart.js / d3 / plotting library. Two proven
  primitives: an allocation DONUT built purely from stroke-dasharray arithmetic on stacked <circle>
  arcs (with an auto-generated legend + percentages), and a NAV / time-series AREA+LINE chart with
  min/max autoscaling, a gradient stroke + fill, and graceful degradation ("history builds as data
  arrives") when there are fewer than two points. Both are palette-driven so they inherit the app's
  brand accent colors (works with portal-design-system + white-label-branding). Use WHENEVER a
  no-framework page needs a small, crisp chart and you don't want a charting dependency — trigger on
  "add a chart without a library", "donut / pie of the breakdown", "allocation chart", "portfolio /
  NAV / balance-over-time line", "sparkline-ish area chart", "SVG chart, no Chart.js", "CSP blocks
  the chart CDN", or a dashboard tile in vanilla-spa-shell. Best for one-or-two-series overview
  charts sized to a card; for dense/interactive/multi-axis analytics reach for a real library
  instead. Guardrails: escape any label rendered into SVG, autoscale from the data (never assume a
  zero baseline), and always render the thin-data fallback so an empty series never looks broken.
---

# Vanilla SVG Charts — a donut + an area/line chart, zero dependencies

## What it is / when to use
Two small inline-SVG chart functions you paste into a vanilla page: a
composition **donut** and a time-series **area+line**. No library, no CDN (so a
tight CSP can't break them), palette-driven so they match the theme. Use for
overview tiles on a dashboard; not for heavy interactive analytics.

## Reference implementation
`~/Projects/clients/wavelygth/portal/index.html` (patterns only, no client data):
- **L1129-1156** — `renderDash()`: the surrounding tile (fills a positions table, then calls both charts). Shows the intended data shape: an array of items each with `{kind, value, label, symbol, …}`.
- **L1158-1178** — `renderDonut()`: the donut.
- **L1180-1203** — `renderLine()`: the async area+line NAV chart (fetches history, autoscales, degrades).
- **L688** — `PALETTE = ['#38e6d0','#5b8cff','#a884ff','#e7c78a','#8b97a6']` (the accent ramp both charts index into).
- CSS holders: `portal-design-system` L119-123 (`.donutRow`, `.legend`, `#lineChart{width:100%;height:190px}`).

## The two primitives

**Donut — stroke-dasharray arithmetic on a stacked circle (L1158-1178):**
The trick: a `<circle r="15.9">` has a circumference of ~100 units, so a slice
is literally its percentage. Each slice is one `<circle>` with
`stroke-dasharray="pct (100-pct)"` and a running `stroke-dashoffset`.
```js
function renderDonut(entries) {           // entries: [ [label, value], … ]
  const total = entries.reduce((a,[,v]) => a+v, 0) || 1;
  const svg = $('donut'); svg.innerHTML = '';
  let off = 25;                            // 25 → start at 12 o'clock
  entries.forEach(([label, v], i) => {
    const pct = v/total*100;
    const c = document.createElementNS('http://www.w3.org/2000/svg','circle');
    c.setAttribute('cx',21); c.setAttribute('cy',21); c.setAttribute('r',15.9);
    c.setAttribute('fill','none'); c.setAttribute('stroke', PALETTE[i%PALETTE.length]);
    c.setAttribute('stroke-width',4);
    c.setAttribute('stroke-dasharray', `${pct} ${100-pct}`);
    c.setAttribute('stroke-dashoffset', off);
    svg.appendChild(c); off -= pct;        // walk the offset so slices abut
  });
  // legend: one <span><i bg=color></i>label · NN%</span> per entry
}
```
Markup: `<svg id="donut" viewBox="0 0 42 42"></svg>` + a `#donutLegend` element.

**Area+line — autoscaled NAV chart (L1180-1203):**
```js
async function renderLine(series) {        // series: [ {total:Number}, … ]
  const svg = $('lineChart'); svg.innerHTML = '';
  if (series.length < 2) {                 // graceful degradation
    svg.innerHTML = '<text x="10" y="30" fill="#586472" font-size="12">History builds as data arrives — check back soon.</text>';
    return;
  }
  const W=600, H=190, PAD=8;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const vals = series.map(s => s.total);
  const min = Math.min(...vals), max = Math.max(...vals), span = (max-min)||1;  // autoscale, never assume 0
  const pts = series.map((s,i) => [ PAD + i/(series.length-1)*(W-PAD*2),
                                    H - PAD - (s.total-min)/span*(H-PAD*2) ]);
  const line = pts.map((p,i) => (i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');
  svg.innerHTML =
    `<defs><linearGradient id="lg" x1="0" x2="1"><stop offset="0" stop-color="#38e6d0"/><stop offset=".5" stop-color="#5b8cff"/><stop offset="1" stop-color="#a884ff"/></linearGradient>`
    + `<linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5b8cff" stop-opacity=".25"/><stop offset="1" stop-color="#5b8cff" stop-opacity="0"/></linearGradient></defs>`
    + `<path d="${line} L ${pts.at(-1)[0]} ${H} L ${pts[0][0]} ${H} Z" fill="url(#fill)"/>`   // filled area
    + `<path d="${line}" fill="none" stroke="url(#lg)" stroke-width="2"/>`;                    // stroked line
}
```

## How to reapply it
1. Style with `portal-design-system` (supplies `.donutRow`/`.legend` and sizes `#lineChart`); define a `PALETTE` array (or read `--cyan`/`--blue`/`--violet`).
2. Donut: add `<svg id="donut" viewBox="0 0 42 42">` + `<div id="donutLegend" class="legend">`; call `renderDonut(entries)` with `[label, value]` pairs (aggregate your rows first, e.g. sum value by category).
3. Line: add `<svg id="lineChart">`; fetch/pass a `series` of `{total}` points (oldest→newest) and call `renderLine(series)`.
4. Recolor by editing `PALETTE` and the two `<linearGradient>` stops — align them to your brand vars so `white-label-branding` reskins the charts too.

## Gotchas
- **r=15.9 is not arbitrary:** 2π·15.9 ≈ 99.9, so dasharray values read directly as percentages. Change `r` and the "pct" math breaks — keep `cx/cy=21`, `r=15.9`, `viewBox="0 0 42 42"`.
- **Offset starts at 25 to put slice 0 at 12 o'clock**, and you *subtract* each pct as you go. Get the sign wrong and slices overlap.
- **`||1` and `||span=1` guard divide-by-zero** for an all-zero or single-value series. Keep both fallbacks.
- **Autoscale from min/max, don't assume a zero baseline** — NAV/balance lines barely move relative to their absolute value, so a 0-based axis flattens them. This chart intentionally frames min→max.
- **Always render the `<2 points` fallback text.** An empty or one-point series must show the "history builds…" message, not a blank/broken SVG.
- **Escape labels** before putting them in SVG `innerHTML` / legend (use `esc()` from `vanilla-spa-shell`) — a category or symbol name is user/data-derived.
- **These are overview charts.** No tooltips, no zoom, no second axis. If the ask is dense interactive analytics, use a real library; don't stretch these.
