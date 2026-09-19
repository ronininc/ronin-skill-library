---
name: ops-console
description: >-
  A one-screen admin "operations" surface for NON-TECHNICAL operators of a Cloudflare Worker + D1
  app: live status chips (system online/down, data fresh vs stale WITH an age in minutes, email
  connected/off) computed from a single /api/admin/system endpoint, plus one-tap ACTION buttons that
  each report their result inline — rebuild a queue, retrain models, download a JSON backup via an
  authed same-origin anchor, connect email (paste a provider key + From, send a test), and a
  three-state connect-Google OAuth control (not-activated / ready / connected). Use WHENEVER a build
  needs an operator control panel: "admin operations page", "system status dashboard", "is everything
  running / healthy", "connect email from the UI", "connect Google / OAuth from an admin panel",
  "download a backup", "a rebuild / retrain / run-a-job button", "settings + status for a
  non-technical client", or the ops tab of a portal. Full-stack (vanilla JS front end + Worker/D1
  endpoints). Pairs with vanilla-spa-shell (the tab it lives in), portal-design-system (chips +
  .sysAct rows), email-provider-honest-degrade (the email-config leg), google-oauth-connector (the
  three-state Google control), and feature-activation-gate (a not-activated capability shows as a
  disabled, "Contact Ronin to enable" chip — never a broken button). Guardrails: every status/action
  endpoint is admin-gated server-side; a not-activated integration degrades to a disabled control
  with honest copy; the backup rides the session cookie via a GET anchor (no token in the URL);
  actions disable-while-running and print success OR the real error, never a fake "done".
---

# Ops Console — a non-technical operator's status + actions panel

## What it is / when to use
The "is everything working, and here are the buttons" screen a client actually
uses to run the app: a row of live status chips + a column of one-tap actions,
each honest about success/failure and about not-yet-activated integrations. Use
it as the System/Operations tab of any Worker+D1 portal.

## Reference implementation
`~/Projects/clients/wavelygth` (patterns only, no client data):
- **portal/index.html L1621-1684** — the front end: `loadSystem()` (entry, L1622) fans out to `loadSysStatus()` (status chips, L1640-1651), `loadEmailCfg()` (L1652-1660), `loadGoogle()` (three-state, L1623-1631); action handlers for connect/disconnect Google (L1632-1639), save/test email (L1662-1672), rebuild queue (L1673-1677), retrain models (L1678-1683), turn-on-2FA shortcut (L1684).
- **portal/index.html L560-587** — the markup: Google connect/disconnect buttons + note, the connect-email panel, and the **"Run an action"** panel of `.sysAct` rows including the backup anchor.
- **portal/index.html L582** — the backup control: a plain authed anchor `<a class="ghost" href="/api/admin/backup" download>` (cookie-authed GET, no JS).
- **worker/index.js L2673-2687** — `handleSystemStatus(env)`: counts + `refresh_runs` age → `{up, pricing:{stale,last_refresh_min_ago}, email:{connected,from,source}, counts:{…}}`.
- **worker/index.js L2688-2714** — `handleEmailConfigGet/Set/Test` (the email leg; see `email-provider-honest-degrade`).
- **worker/index.js L2716-2730** — `handleBackup(env)`: SELECT * across a whitelist of durable tables → a `content-disposition: attachment` JSON download (excludes sessions/tokens/blobs).
- Routes: **L3236-3240** (`/api/admin/system`, `/api/admin/backup`, `/api/admin/email-config[/test]`), **L3207-3211** (`/api/google/connect`, `/api/admin/google[/disconnect]`), **L3156** (`/api/dialer/build`), **L3234** (`/api/admin/ml/retrain`) — all admin-gated.

## The patterns to copy

**Status chips from one endpoint (L1640-1651):**
```js
async function loadSysStatus() {
  const el = $('sysStatus');
  try {
    const d = await api('/api/admin/system');
    const chip = (ok,on,off) => `<span class="chip ${ok?'verified':'pending'}">${ok?on:off}</span>`;
    const age = d.pricing.last_refresh_min_ago;
    el.innerHTML = chip(d.up,'online','down') + ' '
      + chip(!d.pricing.stale, 'data fresh', 'data stale' + (age!=null?` (${age}m ago)`:'')) + ' '
      + chip(d.email.connected, 'email connected', 'email off')
      + `<div class="sym">${d.counts.investors} investors · ${d.counts.leads} leads · …</div>`;
  } catch (e) { el.textContent = e.message; }
}
```
Chips reuse `portal-design-system`'s `.chip.verified`/`.chip.pending`.

**Action button = disable → call → report inline (L1673-1677):**
```js
$('btnRebuild').addEventListener('click', async () => {
  const b = $('btnRebuild'); b.disabled = true;
  try { const d = await api('/api/dialer/build', { method:'POST', body:'{}' });
        $('sysActMsg').textContent = `Rebuilt — ${d.queued} queued.`; }
  catch (e) { $('sysActMsg').textContent = e.message; }        // real error, never a fake "done"
  finally { b.disabled = false; }
});
```

**Three-state OAuth control (L1623-1631)** — the reusable UX for any
`feature-activation-gate`-wrapped integration:
- `!configured` → chip "not activated", **button disabled**, note "Contact Ronin to activate" (the capability isn't sold/enabled on this account).
- `configured && !connected` → "ready to connect", Connect button live.
- `connected` → "connected as …", show Disconnect.

**Backup via authed anchor (L582):** `<a href="/api/admin/backup" download>` — the
session cookie authorizes the GET, so no token ends up in the URL or history, and
no JS/blob is needed.

## How to reapply it
1. Put it in an admin-only tab (`vanilla-spa-shell` reveals it in `enter()`; the tab's loader is `loadSystem()`).
2. Backend: implement `GET /api/admin/system` returning `{up, <freshness>:{stale,age_min}, email:{connected}, counts:{…}}`, admin-gated. Add whatever action endpoints you need (`POST` jobs) and a `GET …/backup` that streams a `content-disposition: attachment` JSON snapshot of a WHITELIST of durable tables (exclude sessions, tokens, and large blobs).
3. Front end: one `loadX()` that fans out to per-panel loaders; render chips with the `chip(ok,on,off)` helper; wire each action button with the disable→call→`finally re-enable` + inline-message pattern.
4. Email + Google legs: compose `email-provider-honest-degrade` (config get/set/test) and `google-oauth-connector` (connect/callback/status) — this console is just their operator UI. Wrap paid integrations in `feature-activation-gate` and render the not-activated state as a disabled control.
5. Style with `portal-design-system` (`.sysAct` rows, `.chip`, `.ghost`/`.cta`, `.note`/`.sym`, `.err`).

## Gotchas
- **Show an AGE, not just stale/fresh.** `last_refresh_min_ago` turns "stale" into "stale (42m ago)" — an operator needs to know *how* stale to decide whether to act. Compute it server-side from your job/telemetry table (here `refresh_runs`), not from a guess.
- **Not-activated ≠ error ≠ off.** Three distinct states. A capability that Ronin hasn't enabled shows a **disabled** button with "Contact Ronin to enable" (honest 402-shaped copy), NOT a live button that then fails, and NOT the same as "activated but not yet connected". Conflating these is the classic ops-panel bug.
- **Every action reports the REAL result inline.** Success prints specifics (`${d.queued} queued`, the retrain AUC); failure prints `e.message` from the thrown `api()` error. Never a bare "Done." that hides a failure — that violates the no-fake-success rule.
- **Disable the button while it runs** (`b.disabled=true` … `finally b.disabled=false`) so an operator can't double-fire a rebuild/retrain.
- **Backup is a GET anchor on purpose.** Don't fetch-then-blob it — the sandbox/CSP can block script-driven downloads, and a query-string token would leak into history. The cookie-authed `<a download>` is the robust path. Server sets `content-disposition: attachment; filename=…`.
- **Backup excludes the transient + the heavy.** Whitelist durable business tables only; never dump `sessions`/auth tokens (security) or uploaded file-chunk blobs (size). State that in the payload `note`.
- **Email config is locked when set by a secret.** If the provider key comes from a Worker secret, the save form hides/refuses (`locked:true`, 409) so the UI can't fight the secret — surface "set by a Worker secret" instead (see `email-provider-honest-degrade`).
- **All of it is admin-gated server-side.** The chips/buttons hiding for non-admins is UX only; the endpoints must each enforce admin (routes at L3207-3240 do). Never trust the client's tab visibility as authorization.
