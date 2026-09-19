---
name: worker-media-headers
description: >-
  Two production Cloudflare Worker fixes that ship together. (1) CONTENT-AWARE
  security headers: apply CSP / X-Frame-Options / HSTS / no-store ONLY to
  text/html documents and hand every binary response straight through untouched —
  because re-wrapping a media response as `new Response(res.body, …)` re-streams
  it and DROPS Content-Length + byte-range support, which makes <video> report
  "no supported source found" and kills seeking. Plus a DUAL CSP: a tight policy
  for the app SPA vs a looser one for a marketing/static site behind the same
  Worker. (2) BYTE-RANGE 206 serving of ASSETS-bound video/audio (including
  suffix ranges) so <video> actually plays and seeks on Safari/iOS. Use WHENEVER
  media misbehaves behind a Worker or you're adding security headers to one:
  "video won't play on iPhone/Safari", "no supported source found", "video won't
  seek / scrub", "add CSP / security headers to my Worker", "range requests /
  206 / Accept-Ranges", "hero video doesn't load in production but works locally",
  "self-hosted fonts blocked by CSP", or "app shell served stale from the edge".
  Backend on a Cloudflare Worker with an ASSETS binding; pairs with
  website-build-standard. Guardrails: the FIRST line of the header wrapper must
  early-return non-HTML responses untouched (the one bug that breaks all media);
  serveStatic buffers the whole file to slice ranges (fine for hero clips, NOT
  huge files — for those, exclude the path from run_worker_first and let
  Cloudflare's asset pipeline serve native ranges); handle suffix ranges
  (bytes=-N) or iOS won't probe the moov atom; no-store the auth-aware HTML shell.
---
# worker-media-headers — security headers that don't break <video>, + range 206

## What it is / when to use
Two fixes for a Cloudflare Worker that fronts both an app and static media.
First, security headers that are applied **only** to HTML — because the naive
"wrap every response to add headers" approach silently strips the byte-range and
Content-Length support that `<video>` needs, so media stops playing in
production. Second, a `serveStatic` that answers HTTP `Range` requests with `206`
for ASSETS-bound video/audio so Safari/iOS can play and seek. Reach for this the
moment a hero video works locally but fails in prod, a video won't scrub, or CSP
starts blocking self-hosted fonts.

## Reference implementation (Wavelygth — patterns only, no client data)
- `~/Projects/clients/wavelygth/worker/index.js`
  - **L1995–2033** `withSecurityHeaders(res, url)` — the early non-HTML return, the HTML-only header set, `no-store` on the shell, and the dual CSP (tight SPA vs looser marketing).
  - **L2035–2072** `serveStatic(req, env)` — media-only rematerialization, `accept-ranges`, `bytes=start-end` + suffix `bytes=-N` parsing, `416` on unsatisfiable, `206` with `content-range` + `content-length`.
  - **L3287–3289** the router tail — `res = await serveStatic(...)` then `return withSecurityHeaders(res, url)` for BOTH the API and static branches.
- `~/Projects/clients/wavelygth/wrangler.jsonc` — `assets.binding: "ASSETS"` and `assets.run_worker_first: ["/*", "!/media/*", "!/_next/*", "!/fonts/*"]` (Worker-first on documents so CSP lands, but pure static dirs served DIRECTLY by CF's pipeline, which supports native byte-ranges).

## How to reapply it
**1. Content-aware security headers.** The critical move is the early return:
```js
function withSecurityHeaders(res, url) {
  // Non-HTML (media/css/js/fonts/images) passes through UNTOUCHED. Re-wrapping a binary
  // as new Response(res.body,…) re-streams it and drops Content-Length + Range → <video>
  // shows "no supported source found" and can't seek. The static layer already set its headers.
  const ct0 = res.headers.get('content-type') || '';
  if (!ct0.includes('text/html')) return res;

  const h = new Headers(res.headers);
  h.set('x-frame-options', 'DENY');
  h.set('x-content-type-options', 'nosniff');
  h.set('referrer-policy', 'strict-origin-when-cross-origin');
  if (url.protocol === 'https:') h.set('strict-transport-security', 'max-age=31536000; includeSubDomains');
  h.set('cache-control', 'no-store');   // the auth-aware app shell must never be edge-cached stale

  // Dual CSP: the app SPA calls only same-origin /api + Google Fonts (tight); the marketing
  // site self-hosts fonts and plays same-origin media (looser). One shared policy silently
  // breaks the other — a portal-shaped CSP blocks self-hosted marketing fonts.
  const portal = url.pathname === '/app' || url.pathname.startsWith('/app/');
  h.set('content-security-policy', portal
    ? "default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    : "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'");
  return new Response(res.body, { status: res.status, headers: h });
}
```

**2. Byte-range 206 serving for media.** Only touch video/audio; pass everything else through:
```js
async function serveStatic(req, env) {
  const res = await env.ASSETS.fetch(req);
  const ct = res.headers.get('content-type') || '';
  if (req.method !== 'GET' || res.status !== 200 || !/^(video|audio)\//.test(ct)) return res; // stream everything else
  const buf = new Uint8Array(await res.arrayBuffer());
  const len = buf.byteLength;
  const headers = new Headers(res.headers);
  headers.set('accept-ranges', 'bytes');
  const range = req.headers.get('range');
  const m = range && /^bytes=(\d*)-(\d*)$/.exec(range.trim());
  if (m && (m[1] !== '' || m[2] !== '')) {
    let start, end;
    if (m[1] === '') { const n = parseInt(m[2], 10); start = Math.max(0, len - n); end = len - 1; }  // suffix: last N bytes
    else { start = parseInt(m[1], 10); end = m[2] === '' ? len - 1 : Math.min(parseInt(m[2], 10), len - 1); }
    if (isNaN(start) || start > end || start >= len) {
      const h = new Headers(headers); h.set('content-range', `bytes */${len}`);
      return new Response(null, { status: 416, headers: h });
    }
    const chunk = buf.subarray(start, end + 1);
    const h = new Headers(headers);
    h.set('content-range', `bytes ${start}-${end}/${len}`);
    h.set('content-length', String(chunk.byteLength));
    return new Response(chunk, { status: 206, headers: h });
  }
  headers.set('content-length', String(len));
  return new Response(buf, { status: 200, headers });
}
```

**3. Router wiring** — run both on the way out, for API and static alike:
```js
let res;
if (url.pathname.startsWith('/api/')) res = await handleApi(req, env, url);
else res = await serveStatic(req, env);
return withSecurityHeaders(res, url);   // HTML gets headers; media passes through untouched
```

**4. `wrangler.jsonc`** — Worker-first on documents, native pipeline for pure static dirs:
```jsonc
"assets": {
  "binding": "ASSETS",
  "directory": "./public",
  // Worker-first on docs/app/api so CSP + auth-aware shell land; exclude static media/font/chunk
  // dirs so Cloudflare's own pipeline serves them (it supports byte ranges natively).
  "run_worker_first": ["/*", "!/media/*", "!/_next/*", "!/fonts/*"]
}
```

## Gotchas
- **The one line that breaks everything:** without the early
  `if (!ct.includes('text/html')) return res;`, `withSecurityHeaders` re-wraps
  every binary and strips its `Content-Length`/`Range`, so `<video>` reports "no
  supported source found" and can't seek. This is the single most common cause of
  "video works locally, dies in prod."
- **`serveStatic` buffers the whole file** (`await res.arrayBuffer()`) to slice a
  range. Fine for hero clips; for large media it risks the isolate's memory —
  prefer excluding that path from `run_worker_first` so Cloudflare's asset pipeline
  serves native ranges, and let `serveStatic` handle only the media that must route
  through the Worker. The allowlist is the belt; `serveStatic` is the suspenders.
- **Handle suffix ranges (`bytes=-N`).** Safari/iOS sends a suffix range to probe
  the MP4 `moov` atom at end-of-file before it will start playback — skip it and iOS never plays.
- **`no-store` on the HTML shell** fixes the "deployed a new build but the edge keeps
  serving the old auth-aware `/app/index.html`" bug. The HTML is tiny and must always be fresh.
- **Dual CSP or you break one app.** A single tight (portal-shaped) CSP silently
  blocks a marketing site's self-hosted fonts and blob: media; a single loose CSP
  under-protects the app. Branch on the path.
- **CSP must allow `data:`/`blob:` where the app uses them** (inline logo data-URIs
  need `img-src data:`; blob media needs `media-src blob:`) or those assets vanish
  with no visible error.
- **`416` on an unsatisfiable range** with `content-range: bytes */<len>` — don't
  return a broken 206; players rely on the 416 to correct their request.
