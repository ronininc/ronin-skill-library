---
name: google-oauth-connector
description: >-
  From-scratch Google OAuth 2.0 (Drive + Calendar) on a Cloudflare Worker using
  raw fetch and NO SDK: a state-verified connect/callback auth-code flow
  (single-use, TTL'd CSRF state), automatic refresh-token rotation 60s before
  expiry, token storage in D1, and the actual capability calls — list Drive
  spreadsheets/CSVs, create a Calendar event. Every Google endpoint is
  env/settings-overridable so the whole flow is provable against a mock. Config
  (client id/secret) resolves from a Worker secret OR an operator-saved setting.
  Use WHENEVER a build needs to connect a Google account without a library:
  "connect Google", "link their Google Drive / Calendar", "import a list from
  Drive", "book a call on their calendar", "Google OAuth without googleapis /
  no SDK", "let the client authorize their Google account", "sign in with
  Google to read their files". Backend on a Cloudflare Worker + D1. Config
  presence is itself the activation gate (see feature-activation-gate — returns
  a 402 when creds aren't wired); log connect/disconnect with append-only-audit-log.
  Guardrails: the refresh_token comes back ONLY on the first consent
  (access_type=offline&prompt=consent) — COALESCE it on upsert so a re-connect
  never nulls it; state is single-use with a ≤900s TTL; the callback is a PUBLIC
  route (Google redirects the browser there with no cookie) so it sits in the
  pre-auth allowlist while everything else is admin-gated; refresh 60s BEFORE
  expiry for clock skew; store expiry as unix seconds.
---
# google-oauth-connector — Google Drive + Calendar, raw fetch, no SDK

## What it is / when to use
A complete Google OAuth 2.0 authorization-code flow implemented with `fetch` and
D1 — no `googleapis` client, no third-party auth service. It connects one Google
account to the app (a fund's/company's own account by default), keeps the access
token fresh via the refresh token, and exposes two concrete capabilities: listing
Drive files (to import a list) and creating a Calendar event (to book a call).
Use it any time a build must read Drive or write Calendar on a user's behalf and
you want to own the flow. The same shape generalizes to any Google scope.

## Reference implementation (Wavelygth — patterns only, no client data)
- `~/Projects/clients/wavelygth/worker/index.js`
  - **L1260** `GOOGLE_SCOPES` — openid/email + `drive.readonly` + `calendar.events`.
  - **L1262–1273** `googleConfig(env)` — id/secret + endpoints from env OR `app_settings`; returns `null` when unconfigured (the activation gate). Endpoints overridable = the test seam.
  - **L1275–1284** `googleAccessToken(env)` — cached until `expiry > now+60`, else refresh with `grant_type=refresh_token`, store the new token.
  - **L1286–1295** `handleGoogleConnect` — mint state, insert, build the consent URL.
  - **L1296–1313** `handleGoogleCallback` (PUBLIC) — verify state + age ≤900s, delete it, exchange the code, fetch userinfo, upsert tokens (COALESCE refresh_token), redirect to `#connected`.
  - **L1314–1323** status + disconnect. **L1324–1343** Drive files + Calendar event.
  - Routes: **L3106** `/api/google/callback` (public, above the session gate); **L3207** `/api/google/connect` (admin).
- `~/Projects/clients/wavelygth/worker/migrations/0018_google.sql` — `google_tokens` (singleton row `id='default'`) + `google_oauth_state`.
- `~/Projects/clients/wavelygth/worker/lib/_proof/google-connect.test.mjs` — proves the whole flow against an in-process mock Google (token/userinfo/drive/calendar), including expired-token auto-refresh and admin gating.

## How to reapply it
**1. Migration.** Two tables — a singleton token row and short-lived CSRF states:
```sql
CREATE TABLE IF NOT EXISTS google_tokens (
  id TEXT PRIMARY KEY DEFAULT 'default',   -- one connected account (key by user_id for per-user)
  access_token TEXT, refresh_token TEXT,
  expiry INTEGER,                          -- UNIX SECONDS
  scope TEXT, email TEXT, connected_at TEXT
);
CREATE TABLE IF NOT EXISTS google_oauth_state ( state TEXT PRIMARY KEY, created_at INTEGER NOT NULL );
```

**2. Config resolver** (env OR settings; overridable endpoints = testable; `null` = not configured):
```js
const GOOGLE_SCOPES = 'openid email https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/calendar.events';
async function googleConfig(env) {
  const s = await readSettings(env).catch(() => ({}));
  const id = env.GOOGLE_CLIENT_ID || s.google_client_id;
  const secret = env.GOOGLE_CLIENT_SECRET || s.google_client_secret;
  if (!id || !secret) return null;
  return { id, secret,
    authUrl:  env.GOOGLE_AUTH_URL  || s.google_auth_url  || 'https://accounts.google.com/o/oauth2/v2/auth',
    tokenUrl: env.GOOGLE_TOKEN_URL || s.google_token_url || 'https://oauth2.googleapis.com/token',
    apiBase:  env.GOOGLE_API_BASE  || s.google_api_base  || 'https://www.googleapis.com' };
}
```

**3. Connect** (admin, POST) — mint state, build the consent URL (`access_type=offline&prompt=consent` so a refresh_token is issued):
```js
const state = randomHex(16);
await env.DB.prepare('INSERT INTO google_oauth_state (state, created_at) VALUES (?, ?)').bind(state, now()).run();
const redirectUri = `${url.origin}/api/google/callback`;
const authUrl = `${cfg.authUrl}?client_id=${encodeURIComponent(cfg.id)}&redirect_uri=${encodeURIComponent(redirectUri)}`
  + `&response_type=code&scope=${encodeURIComponent(GOOGLE_SCOPES)}&access_type=offline&prompt=consent&state=${state}`;
return json({ url: authUrl });
```

**4. Callback** (PUBLIC GET — the redirect target; no cookie) — verify + single-use state, exchange, upsert:
```js
const rec = state && await env.DB.prepare('SELECT state, created_at FROM google_oauth_state WHERE state=?').bind(state).first();
if (!code || !rec || (now() - rec.created_at) > 900) return new Response('That connection attempt is invalid or expired. Start again.', { status: 400, headers: { 'content-type': 'text/plain' } });
await env.DB.prepare('DELETE FROM google_oauth_state WHERE state=?').bind(state).run();       // single use
const tok = await fetch(cfg.tokenUrl, { method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({ code, client_id: cfg.id, client_secret: cfg.secret, redirect_uri: redirectUri, grant_type: 'authorization_code' }) }).then(r => r.json()).catch(() => null);
if (!tok?.access_token) return new Response('Google connection failed.', { status: 400 });
let email = ''; try { email = (await fetch(`${cfg.apiBase}/oauth2/v2/userinfo`, { headers: { authorization: 'Bearer ' + tok.access_token } }).then(r => r.json()))?.email || ''; } catch {}
await env.DB.prepare("INSERT INTO google_tokens (id, access_token, refresh_token, expiry, scope, email, connected_at) VALUES ('default',?,?,?,?,?,?) "
  + "ON CONFLICT(id) DO UPDATE SET access_token=excluded.access_token, refresh_token=COALESCE(excluded.refresh_token, google_tokens.refresh_token), expiry=excluded.expiry, scope=excluded.scope, email=excluded.email, connected_at=excluded.connected_at")
  .bind(tok.access_token, tok.refresh_token || null, now() + (tok.expires_in || 3600), tok.scope || GOOGLE_SCOPES, email, iso()).run();
return Response.redirect(`${url.origin}/app/#connected=google`, 302);
```

**5. Fresh access token** — refresh 60s before expiry:
```js
async function googleAccessToken(env) {
  const cfg = await googleConfig(env); if (!cfg) return null;
  const row = await env.DB.prepare("SELECT * FROM google_tokens WHERE id='default'").first();
  if (!row) return null;
  if (row.expiry && row.expiry > now() + 60) return row.access_token;   // 60s skew guard
  if (!row.refresh_token) return row.access_token;
  const tok = await fetch(cfg.tokenUrl, { method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_id: cfg.id, client_secret: cfg.secret, refresh_token: row.refresh_token, grant_type: 'refresh_token' }) }).then(r => r.json()).catch(() => null);
  if (tok?.access_token) { await env.DB.prepare("UPDATE google_tokens SET access_token=?, expiry=? WHERE id='default'").bind(tok.access_token, now() + (tok.expires_in || 3600)).run(); return tok.access_token; }
  return row.access_token;
}
```

**6. Capability calls** — raw fetch with `Authorization: Bearer <accessToken>`:
list `${apiBase}/drive/v3/files?q=…&fields=files(id,name,mimeType,modifiedTime)`;
POST `${apiBase}/calendar/v3/calendars/primary/events` with a `{summary,start,end,attendees}` body.

**7. Routes.** `/api/google/callback` PUBLIC and in the pre-auth allowlist (above the
"require session" line); `/api/google/connect` + status/disconnect/drive/calendar admin-gated.

**8. Activate.** Set `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` (secret or settings). Register
the exact `${origin}/api/google/callback` as an authorized redirect URI in the Google Cloud console.

## Gotchas
- **refresh_token only on FIRST consent.** Google returns it only with
  `access_type=offline&prompt=consent`, and a subsequent connect without
  `prompt=consent` returns none — so the upsert MUST
  `COALESCE(excluded.refresh_token, existing)` or a re-connect wipes your stored refresh token.
- **State is single-use + TTL'd.** Insert on connect, delete on callback, reject if
  missing or older than 900s. The callback returns **plain text 400** (not JSON) on a
  bad/expired state — it's a browser redirect landing, not an API call.
- **The callback is PUBLIC.** Google redirects the user's browser to it with no
  session cookie, so it must be routed BEFORE the "require login" gate. Every other
  Google route (connect, status, disconnect, drive, calendar) is admin-gated.
- **Endpoints must be overridable.** Keeping `tokenUrl`/`apiBase`/`authUrl` in the
  config (env or settings) is what lets the proof point them at a mock HTTP server —
  don't hardcode `googleapis.com` inside the handlers.
- **Refresh 60s early.** `expiry > now()+60`, never `> now()` — clock skew plus request
  latency will otherwise hand you an already-dead token intermittently.
- **`expiry` is unix seconds** (`now() + expires_in`), not an ISO string — be consistent
  with your time helpers (`now()` = `Math.floor(Date.now()/1000)`).
- **Singleton by default** (`id='default'` = one connected account for the instance). For
  per-user Google connections, key the token row by `user_id` instead and resolve per session.
- **Unconfigured ⇒ 402, not 500.** When `googleConfig` returns `null`, the connect
  handler answers a purchase-shaped 402 ("isn't configured on this account yet…"), the
  feature-activation-gate pattern.
