---
name: untrusted-preview-sandbox
description: >-
  Safely serve and preview UNTRUSTED HTML/JS — anything a model generated, a user uploaded, or a build
  scaffolded from a prompt — so the untrusted document can RUN in the viewer's browser without being able
  to read the host app's session cookie, make credentialed same-origin requests, or clickjack it. The
  core is an opaque-origin CSP sandbox (`Content-Security-Policy: sandbox allow-scripts`, deliberately NO
  allow-same-origin) plus `X-Content-Type-Options: nosniff` and `frame-ancestors 'none'`. It also solves
  the sharp tradeoff that an opaque origin BREAKS the untrusted app's own `localStorage` (reads return
  empty, `setItem` throws): host the preview on a SEPARATE origin that never receives the host cookie, so
  it's already cross-origin — then it can keep its own usable, isolated storage and you drop the sandbox
  there, authorizing the view with a SHORT-LIVED, resource-scoped token (carried in the URL, so minutes-
  long TTL, single resource, no API access) instead of the session cookie. Use WHENEVER a build renders
  content it doesn't fully control: "preview the generated site/app", "show the AI-generated HTML",
  "render user-uploaded HTML", "embed an untrusted snippet", "sandbox this iframe", "let them see it live
  but keep it isolated", or "why can't the preview save / why can it read my cookie". COMPLEMENTS
  spec-contract-scaffold-pipeline (whose generated artifact this previews), scoped-bearer-token /
  cf-identity (the session vs. the short-lived view token this contrasts), and worker-media-headers.
  Guardrail: NEVER add `allow-same-origin` to a sandbox that also has `allow-scripts` on your own origin —
  together they let the untrusted script escape the sandbox and touch your origin's cookies/storage.
---

# Untrusted Preview Sandbox — run generated/user HTML live, but isolated

## What it is / when to use / what it composes with
The pattern for the moment a build has to show HTML it didn't write — model-generated, user-uploaded, or
scaffolded from a prompt — as a **live, working** preview without exposing the surrounding app. Two layers:

1. **Opaque-origin CSP sandbox (default, safest).** Serve the untrusted document with
   `Content-Security-Policy: sandbox allow-scripts` (NO `allow-same-origin`) + `X-Content-Type-Options:
   nosniff`. Scripts run, but the document has an *opaque* origin: it can't read the host's session cookie
   or make credentialed same-origin requests. Add `frame-ancestors 'none'` so it can't be framed to
   clickjack the real app.
2. **Separate preview origin (when the preview must persist state).** The opaque origin also breaks the
   untrusted app's own `localStorage` (reads empty, `setItem` throws) — so a "working" preview isn't. Fix:
   host the preview on a **different origin** that never receives the host's cookie. There it's already
   cross-origin from your app (cookie unreachable), so you can drop the sandbox and let it keep its OWN
   isolated storage — and authorize the view with a **short-lived, resource-scoped token** in the URL,
   not the session cookie.

Use it for: prompt→app/site builder previews, "render this uploaded HTML", embedding third-party or
AI-authored snippets, any "see it live" where the content is not yours. Composes with
**spec-contract-scaffold-pipeline** (the generator whose output you preview), **scoped-bearer-token** and
**cf-identity** (the durable session this deliberately does NOT use for the preview), and
**worker-media-headers** (the header-setting discipline).

## Reference implementation (apps/appforge — a prompt→app builder; OPEN these)
- **The preview route + the two header sets** — `apps/appforge/backend/app/routers/builds.py:115-163`:
  authorize by a valid resource-scoped **token** OR an active session (126-135); then choose headers by
  origin (146-160):
  - **On the API origin (or no separate origin configured):** `Content-Security-Policy: sandbox
    allow-scripts` + `nosniff` — isolation over storage. The comment (141-145) spells out exactly why:
    the opaque origin protects the API but makes the app's storage non-functional.
  - **On the dedicated preview origin:** `Content-Security-Policy: frame-ancestors 'none'` + `nosniff` —
    no sandbox, because it's already cross-origin so cookies are unreachable and the app gets usable
    isolated storage; `frame-ancestors 'none'` still blocks clickjacking.
- **Detecting the separate origin** — `_served_on_dedicated_preview_origin(request)` (24-33): compares the
  request host to the configured preview host; only that host drops the sandbox.
- **The short-lived, resource-scoped view token** — `apps/appforge/backend/app/auth.py`:
  `issue_preview_token(build_id, subscriber_id, ttl_seconds=120)` (76-90) mints a token with a DISTINCT
  issuer, a ~2-minute TTL, and the single resource id — the comment (77-81) notes it rides in the URL
  query string (logged / in history, CWE-598), so the TTL is deliberately short and it grants ONLY viewing
  that one resource, no API access. `verify_preview_token` (93-102) checks the issuer AND that the token's
  resource id matches the one being viewed, returning the owner id or `None`.
- **Client hand-off** — `apps/appforge/frontend/index.html:138-143`: fetch the token, then open the
  preview on the separate origin as `…/preview?t=<token>`; with no separate origin, let the ordinary
  cookie-authed relative link open it.
- **Serving the static artifact** — `apps/appforge/backend/app/forge/sandbox.py:12-13`: the preview IS the
  generated `index.html`; a container app would need a Docker sandbox — the note (1-6) explicitly rejects
  WebContainers (a commercial-license trap for a paid product) rather than reaching for it silently.

## How to reapply (in a CLIENT build)
1. **Default every untrusted render to the opaque sandbox.** Return the HTML with `Content-Security-Policy:
   sandbox allow-scripts`, `X-Content-Type-Options: nosniff`, and `frame-ancestors 'none'`. This is the
   safe floor even if you never add a second origin.
2. **If the preview must persist/read state, add a separate origin.** Serve previews from a distinct host
   (a different subdomain/domain, or Cloudflare a separate Worker route) that your app's session cookie is
   NOT scoped to. Detect "am I on the preview origin?" by host and only there drop the sandbox.
3. **Authorize the preview with a scoped token, not the session.** On the cookieless origin, mint a
   short-lived (minutes) token bound to the one resource + owner, with a distinct issuer and no API scope;
   pass it in the URL; verify issuer + resource-match on the way in. Keep the durable session
   (`cf-identity` / `scoped-bearer-token`) for the real app only.
4. **Never let the untrusted content reach a credentialed API.** Because it's opaque-origin or truly
   cross-origin, same-origin credentialed fetch is off the table; also don't proxy its outbound calls
   through an authed endpoint.

## Gotchas
- **`allow-scripts` + `allow-same-origin` on your own origin = no sandbox at all.** Together they let the
  framed script reach back into your origin (cookies, storage, DOM). If you need scripts AND same-origin
  storage, that's the signal to move to the *separate origin*, not to add `allow-same-origin`.
- **Opaque origin silently breaks the previewed app.** `localStorage`/`sessionStorage`/IndexedDB throw or
  read empty under an opaque origin — a CRUD preview looks alive but can't save. Decide up front: isolation
  (sandbox, no storage) or working storage (separate origin). Don't ship a preview that claims to save but
  can't.
- **The view token lands in logs and history (CWE-598).** A URL-borne token is unavoidable for a top-level
  cross-origin navigation, so bound the damage: very short TTL, single resource, no API access, distinct
  issuer so it can never be replayed as a session.
- **Keep `frame-ancestors 'none'` even without the sandbox.** On the separate origin you drop `sandbox
  allow-scripts`, but the preview could still be framed by an attacker page to clickjack — keep
  `frame-ancestors 'none'`.
- **`nosniff` always.** Without `X-Content-Type-Options: nosniff` a browser may sniff the untrusted body
  into a more dangerous type; set it on every untrusted response.
- **Don't reach for WebContainers to "just run it."** For a commercial/paid build it's a licensing trap;
  use a real container sandbox or the static-preview path instead (see `sandbox.py` note).
