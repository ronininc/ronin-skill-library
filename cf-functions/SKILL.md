---
name: cf-functions
description: >
  Add a serverless backend / API to a static site WITHOUT Netlify Functions or
  Lambda — a clone of Netlify Functions built on a single Cloudflare Worker that
  serves the static site AND answers /api/* routes. Use whenever a site needs
  "a backend endpoint", "an API route", "a form/handler on the server", "talk to
  a database", "a contact/chat/booking function", or "server-side logic" and you
  want it on Cloudflare. Covers the one-Worker-serves-both pattern (ASSETS
  binding + /api router), method+path routing with plain JS, JSON helpers, D1
  access, secrets via env, and error handling. Working reference:
  ~/Projects/clients/slik-team-board/src/index.js (standalone repo).
---

# cf-functions — your own serverless backend (Netlify Functions, cloned)

Netlify Functions = "drop a file in `/netlify/functions` and it's an endpoint."
The Cloudflare equivalent is one small Worker that (a) serves your static files
and (b) routes `/api/*` to your code. One deploy, one origin, no CORS.

**Reference implementation:** `~/Projects/clients/slik-team-board/src/index.js` (router at the
bottom) with `~/Projects/clients/slik-team-board/wrangler.jsonc` (the ASSETS + D1 bindings).

## The pattern
`wrangler.jsonc`:
```jsonc
{
  "name": "my-app",
  "main": "src/index.js",
  "compatibility_date": "2025-08-01",
  "assets": { "directory": "./public", "binding": "ASSETS" },
  "d1_databases": [{ "binding": "DB", "database_name": "my-app", "database_id": "…", "migrations_dir": "migrations" }]
}
```

`src/index.js`:
```js
const json = (d, s = 200, h = {}) => new Response(JSON.stringify(d),
  { status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...h } });

async function api(req, env, url) {
  const p = url.pathname, m = req.method;
  if (p === '/api/hello' && m === 'GET') return json({ ok: true });
  // const row = await env.DB.prepare('SELECT …').bind(x).first();
  const match = p.match(/^\/api\/thing\/([^/]+)$/);
  if (match && m === 'DELETE') return remove(match[1], env);
  return json({ error: 'Not found' }, 404);
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname.startsWith('/api/')) {
      try { return await api(req, env, url); }
      catch (e) { return json({ error: 'Server error' }, 500); }
    }
    return env.ASSETS.fetch(req);           // static site
  },
};
```

## Why this order works
Static assets are served first for real files; anything under `/api/*` has no
matching file, so it falls through to your Worker. **Do not** turn on
`not_found_handling: "single-page-application"` unless you also add
`run_worker_first: ["/api/*"]` — otherwise the SPA catch-all would swallow your
API routes and return index.html.

## D1 (SQL) cheat-sheet
- `env.DB.prepare(sql).bind(a, b).first()` → one row (or null)
- `.all()` → `{ results: [...] }`
- `.run()` → write; returns `{ meta }`
- Always parameterize with `.bind(...)`. Never string-concatenate user input.

## Secrets & config
- Non-secret config → `vars` in `wrangler.jsonc`.
- Secrets (API keys) → `wrangler secret put NAME` (or `.dev.vars` locally). Read as `env.NAME`.

Pairs with **cf-identity** (auth middleware), **cf-forms** (form endpoints),
**cf-deploy** (go live). For heavy Node APIs, add `"nodejs_compat"` to
`compatibility_flags`.
