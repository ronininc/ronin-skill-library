---
name: vanilla-spa-shell
description: >-
  The zero-dependency single-file SPA backbone for a gated portal/CRM/admin app: an api() fetch
  wrapper (JSON, same-origin cookies, HTTP error attached to the throw, toast), a tab/view router
  that shows one <section> and lazy-loads its data, a role/clearance-gated nav reveal (enter(user)
  un-hides only the tabs a role may see, then routes to a landing view), URL-hash deep-linking
  (#invite=/#reset=/#connected=google), a multi-mode auth card (login / accept-invite / forgot /
  reset / signup / first-run bootstrap, with an inline MFA step-up), and XSS-safe esc()/money()/
  fmtBytes()/bufToB64() utilities. Use WHENEVER you are hand-building a no-framework front end for
  a logged-in app — trigger on "vanilla JS SPA", "no React/framework front end", "single-file
  portal/dashboard", "tab router without a library", "role-gated tabs", "wire the login card to
  the Worker", "add #invite/#reset deep links", or as the front-end spine every other frontend
  skill (vanilla-svg-charts, ops-console, white-label-branding) plugs into. Pairs with cf-identity
  (the /api/auth/* + /api/me backend) and clearance-rbac (richer than role gating); style it with
  portal-design-system. No build step, CSP-tight (no inline handlers), mobile-tuned.
---

# Vanilla SPA Shell — the no-framework backbone of a gated portal

## What it is / when to use
The reusable skeleton every hand-rolled portal reuses: one `api()` helper, a
tab→view router, a role-gated nav reveal, hash-token auth modes, and a few
XSS-safe formatters. No framework, no bundler. Use it as the front-end spine of
any cf-identity-backed app; rename the view list and the rest carries over.

## Reference implementation
`~/Projects/clients/wavelygth/portal/index.html` (patterns only, no client data):
- **L684-701** — top-level helpers: `$`, `money`/`money2`, `KINDS`, `PALETTE`, module state (`ME`, `PORTFOLIOS`, `CURRENT`), and the two you always lift: `api()` (L692-697) + `toast()` (L698-701).
- **L704-708** — hash-token parse: `#invite=<hex>` / `#reset=<hex>`, plus `bootstrapMode`/`signupMode` flags.
- **L710-742** — `initAuth()`: theme the login card first (`loadBranding()`), probe `/api/health` for first-run, set the auth card copy per mode, then try `/api/me` and `enter()` if already signed in.
- **L744-820** — the `#authForm` submit handler (one form, six modes) + `forgotLink` (anti-enumeration) + `signupToggle`.
- **L822-825** — logout.
- **L827-860** — `enter(user)`: hide auth / show app, set header, and the **role gate** — admin reveals all tabs + the ⚙ settings button; `agent` hides investor tabs and lands on the dialer; everyone else gets onboarding. Honors a landing view from the URL hash.
- **L863-876** — the **tab router**: `#tabs` click delegates, toggles `.on`, shows the one matching `#view-<v>` section, and lazy-loads that view's data.
- Utilities elsewhere in the file: `esc()` **L1965** (HTML-escape), `fmtBytes()` **L1969-1975**, `bufToB64()` **L1976-1979** (base64 in 0x8000 windows).

## The pieces to copy

**api() — the one fetch wrapper every call goes through (L692-697):**
```js
async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { 'content-type': 'application/json' }, credentials: 'same-origin', ...opts });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(d.error || 'Something went wrong.'); e.status = r.status; e.body = d; throw e; }
  return d;
}
```
`credentials:'same-origin'` sends the cf-identity session cookie; a non-2xx
throws an `Error` carrying `.status` + `.body` so callers can branch (e.g. a 401
with `mfa_required`, a 402 from `feature-activation-gate`). Callers pattern:
`try { const d = await api(...) } catch(e){ $('err').textContent = e.message }`.

**esc() — mandatory before any innerHTML (L1965):**
```js
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
```
Every value interpolated into a template-literal `innerHTML` runs through `esc()`.

**Role-gated reveal (shape of enter(), L827-860):** start with all privileged tabs
`.hidden` in the markup; on login, `classList.remove('hidden')` only those the
role may use, then click the landing tab.

**Tab router (L863-876):**
```js
$('tabs').addEventListener('click', (ev) => {
  const b = ev.target.closest('.tab'); if (!b) return;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('on', t === b));
  VIEWS.forEach(v => $('view-'+v).classList.toggle('hidden', v !== b.dataset.view));
  LOADERS[b.dataset.view]?.();   // lazy-load this view's data on entry
});
```

## How to reapply it
1. Style the page with `portal-design-system` (it supplies `.tab`/`.on`/`.hidden`/`.toast`/`.panel`).
2. Markup: one `<div id="authView">` (the auth card) + one `<div id="appView" class="hidden">` holding `<div class="tabs" id="tabs">` of `.tab[data-view="…"]` buttons (privileged ones start `.hidden`) and one `<section id="view-<v>" class="hidden">` per view.
3. Paste the helpers (`$`, `api`, `toast`, `esc`, `money`, `fmtBytes`) and module state.
4. Write `enter(user)` to reveal tabs per `user.role`/clearance and click a default tab; write the `#tabs` router with a per-view loader map.
5. If using invite/reset/OAuth-return links, add the hash parsing (L704-708) and the auth-mode branches (L744-820) — the backend is cf-identity's `/api/auth/*`.
6. Call `initAuth()` last (see `initAuth()` at the very end of the file, `initAuth();`).
7. Backend expectation: a Worker exposing `/api/me` → `{user:{name,role,…}}`, `/api/auth/*`, and your `/api/<view>` data endpoints. cf-identity provides all of the auth side.

## Gotchas
- **CSP-tight by design:** all handlers are `addEventListener` in the script, never `onclick=` attributes — so a strict `Content-Security-Policy` (see `worker-media-headers`) won't block them. Don't reintroduce inline handlers.
- **`.hidden` is the single visibility mechanism** and uses `!important` (from the design system). Toggle the class; don't set `style.display`.
- **MFA is a login *sub-state*, not a route:** a `401 {mfa_required:true}` reveals the code field and asks the user to resubmit the SAME form with `code` — the login handler bypasses `api()` and reads the raw response to catch that 401 body (L769-779). Keep that raw-fetch branch.
- **Anti-enumeration is a UI contract too:** the forgot-password path shows the identical "if that email has an account…" message whether or not the request succeeded, and swallows the error (L788-796). Never surface a different message for unknown emails.
- **Deep-link allowlist:** the hash→landing-tab jump only honors a fixed allowlist of view names and re-checks the tab isn't `.hidden` before clicking (L855-859) — so a crafted `#admin` can't reveal a tab the role can't see. Keep the allowlist + the not-hidden check.
- **`history.replaceState` after consuming a token** (invite/reset/`connected=google`) so the one-time hash token isn't left in the URL/history (L757, L760, L852).
- **Router is markup-driven:** the view list is hard-coded in two spots (the `enter()` deep-link allowlist and the router's `.forEach`). When you add a view, update both, or the section won't hide/show.
