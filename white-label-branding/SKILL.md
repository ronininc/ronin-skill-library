---
name: white-label-branding
description: >-
  Instance-wide reskin of a CSS-var-tokened app with NO rebuild and NO redeploy: three brand colors
  (primary / accent / background, plus a derived gradient) + a portal name + an uploaded logo,
  persisted server-side in a tiny app_settings key/value table, applied at runtime by overriding a
  handful of CSS custom properties on <html>, and swapped on BOTH the header crest AND the login
  card — the login screen themes BEFORE auth because it reads a PUBLIC settings endpoint. Includes a
  live-preview admin settings modal (color pickers update the page as you drag, logo upload with a
  size guard, name override, reset-to-default). Use WHENEVER a build must be re-skinnable per client
  / tenant / partner without a code change — trigger on "white-label it", "let the client pick their
  colors / upload their logo", "partner branding", "rebrand per customer", "make the portal theme
  editable", "change the accent color from an admin panel", or productizing one portal resold to many
  merchants. EXTENDS portal-design-system (it overrides that token system's --blue/--cyan/--ink) and
  pairs with cf-identity (admin-gated write) + vanilla-spa-shell (calls loadBranding() on boot).
  Guardrails: colors are hex-validated and the logo is a size-capped image data-URI, both server-side;
  the read endpoint is public but the write is admin-only; live preview is discarded on modal close
  unless saved.
---

# White-Label Branding — reskin the whole app from three colors + a logo, no rebuild

## What it is / when to use
Turns a CSS-var-tokened app (see `portal-design-system`) into a white-label
product: an admin sets primary/accent/bg colors, a portal name, and a logo; it
persists in D1 and re-themes the app — and the login card — at runtime by
overriding CSS variables. One portal, reskinned per client. Use whenever a build
is resold to multiple tenants/partners or the client wants to own the look.

## Reference implementation
`~/Projects/clients/wavelygth` (patterns only, no client data):
- **portal/index.html L2073-2100** — `DEFAULT_BRAND`, `applyBranding(s)` (overrides `--blue`/`--cyan`/`--ink` + rebuilds `--spectral`, swaps header + login crest), `loadBranding()` (GETs the public endpoint).
- **portal/index.html L2200-2244** — the admin settings modal: open/prefill, live-preview `input` listeners on the color pickers, logo upload (750 KB guard) + clear, save (PUT), reset.
- **portal/index.html L12-18** — the `:root` CSS-var tokens being overridden.
- Markup: header crest **L202-208**, login-card crest **L173-175**, settings modal **L659-680** (color inputs `setPrimary`/`setAccent`/`setBg`, `setName`, `logoInput`, `setLogoPrev`).
- **worker/index.js L432-475** — `BRAND_KEYS`, `readSettings()`, `handleSettingsGet()` (public), `handleSettingsUpdate()` (admin; hex + image + size validation, batched upsert/delete, audit).
- **worker/index.js L3095** — `GET /api/settings` (PUBLIC, before auth). **L3225** — `PUT /api/admin/settings` (admin-gated).
- **worker/migrations/0006_profile_branding.sql** — the `app_settings(key,value,updated_at)` table.

## The core trick — apply branding by overriding CSS vars (L2076-2096)
```js
const DEFAULT_BRAND = { brand_primary:'#5b8cff', brand_accent:'#38e6d0', brand_bg:'#05070a', portal_name:'AppName', logo_data:'' };
let BRAND = { ...DEFAULT_BRAND };
function applyBranding(s) {
  BRAND = { ...DEFAULT_BRAND, ...(s || {}) };
  const r = document.documentElement.style;
  r.setProperty('--blue', BRAND.brand_primary);
  r.setProperty('--cyan', BRAND.brand_accent);
  r.setProperty('--ink',  BRAND.brand_bg);
  r.setProperty('--spectral', `linear-gradient(90deg,${BRAND.brand_accent},${BRAND.brand_primary},var(--violet))`);
  const logo = (BRAND.logo_data || '').trim();
  for (const [nameId, logoId, defId, imgId] of [           // header crest AND login crest
    ['wordmarkName','crestLogo','crestDefault','crestLogoImg'],
    ['authWordmarkName','authCrestLogo','authCrestDefault','authCrestLogoImg'],
  ]) {
    const nm = $(nameId); if (nm) nm.textContent = BRAND.portal_name;
    const cl=$(logoId), cd=$(defId), img=$(imgId);
    if (cl && cd && img) { if (logo){ img.src=logo; cl.classList.remove('hidden'); cd.style.display='none'; }
                           else { cl.classList.add('hidden'); cd.style.display='flex'; } }
  }
}
async function loadBranding(){ try{ applyBranding((await api('/api/settings')).settings); } catch{ applyBranding(null); } }
```
Because it only sets a few custom properties, **every rule in the design system
that reads those vars re-colors for free** — no per-element restyling.

## The server side (worker/index.js L437-475)
- `BRAND_KEYS = ['brand_primary','brand_accent','brand_bg','portal_name','logo_data']` — the only writable keys.
- Validate on write: colors against `HEX_RE = /^#[0-9a-fA-F]{3,8}$/`; `portal_name` truncated to 60; `logo_data` must match `^data:image/(png|jpeg|jpg|gif|webp|svg\+xml);base64,` and be under `LOGO_MAX` (~1 MB); `null`/`''` deletes the key (→ falls back to default).
- Upsert via `INSERT … ON CONFLICT(key) DO UPDATE`, all in one `env.DB.batch()`, then `audit(env, me.id, 'settings_updated', null)`.
- `handleSettingsGet` returns `{settings:{…}}` and takes **no session** — that's what lets the login card theme itself.

## How to reapply it
1. Build on `portal-design-system` (or any app whose colors are CSS vars). Give the crest two states in markup — a default SVG/wordmark and a hidden `<img>` — on BOTH the header and the login card, with the id quads above.
2. Migration: `CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT NOT NULL);` (0006). It's shared with other settings consumers (e.g. `ops-console` email config) — additive, key/value.
3. Worker: add `readSettings`, `handleSettingsGet`, `handleSettingsUpdate` (L432-475) with the hex/image/size validation. Route `GET /api/settings` in the PUBLIC/pre-auth block; `PUT /api/admin/settings` admin-gated.
4. Front end: paste `applyBranding` + `loadBranding`; call `loadBranding()` at the very top of your auth init (`vanilla-spa-shell`'s `initAuth` does exactly this, L711) so the login screen is themed before sign-in.
5. Admin modal (L2200-2244): color `<input type=color>` pickers with `input` listeners that call `applyBranding({...BRAND, …})` for LIVE preview; a logo picker that reads the file to a data-URI with a client size guard; Save → `PUT` then `applyBranding(d.settings)`; **Close → `loadBranding()` to discard the unsaved preview**; Reset → PUT all-null.
6. Gate the ⚙ settings button to admins (`vanilla-spa-shell` reveals it in `enter()`).

## Gotchas
- **Public read is the whole point — but it's PUBLIC.** Only ever expose the brand keys through it; never fold private settings into the same `app_settings` read that `/api/settings` returns (the email API key, Google secrets, etc. are read by *other* handlers, never returned by `handleSettingsGet`). Keep the public getter to brand fields.
- **Live preview must be discarded on cancel.** The color `input` listeners mutate the live page immediately; if the admin closes without saving you must re-`loadBranding()` (L2211) or the page keeps the un-saved colors until reload.
- **`pendingLogo` tri-state:** `undefined` = unchanged (don't send), `''` = cleared (send to delete), string = new data-URI. Only include `logo_data` in the PUT when it's not `undefined` (L2201, L2231) — otherwise a color-only save would wipe the logo.
- **Validate colors AND the logo server-side.** The client guard (750 KB) is UX; the server cap (`LOGO_MAX`) and `HEX_RE` are the real gate — a bad hex string injected into a CSS var could break the theme, and an oversized/foreign data-URI must be rejected (`handleSettingsUpdate` returns `bad(...)`).
- **Two crests, one config.** Forgetting the login-card crest ids means the app themes but the login screen doesn't — the most common miss. Keep both rows in the `applyBranding` loop.
- **`--spectral` is derived, not stored.** It's rebuilt from accent+primary on every apply; don't try to persist a gradient string. `--violet` stays fixed as the third stop.
- **`readJson` cap must exceed the logo:** the update handler reads the body with a ~1.4 MB cap (L451) so a ~1 MB logo data-URI fits. If you tighten `readJson`, logos will 413.
