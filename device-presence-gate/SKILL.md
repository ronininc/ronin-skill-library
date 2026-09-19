---
name: device-presence-gate
description: >-
  Server-enforced PHYSICAL-POSSESSION gate: a protected endpoint refuses to serve unless a
  fresh (≤60s) heartbeat proves a REGISTERED Bluetooth device is connected and in range. The
  browser can only send that heartbeat while a live Web-Bluetooth GATT link is up, so presence
  is real, not client theater — the server checks heartbeat freshness AND device registration
  on every call. Use WHENEVER a build must gate an action on "the operator's phone/device is
  physically here" — a dialer that only hands out contacts while your phone is present, a
  kiosk/terminal that unlocks near a paired device, a "possession factor" or anti-walkaway
  lock, "prove the device is in range", "don't serve unless my phone is connected", or a second
  factor that is physical rather than identity. Full-stack (Cloudflare Worker + D1 + vanilla JS
  UI). Guardrails: default the gate ON but ALWAYS make it operator-toggleable, because
  Web Bluetooth is Chromium-only and iOS Safari cannot pair at all; the heartbeat interval must
  stay well under the TTL; and this proves a device is NEAR, not WHO holds it — pair with
  cf-identity for identity. Extends cf-identity (users/sessions) and is the browser half of
  hfp-dialer-companion (whose native bridge sends the same heartbeat).
---

# device-presence-gate — "serve only while a registered device is in range"

## What it is / when to use
A server-side gate that releases a protected capability only while a registered Bluetooth
device is provably present. The browser posts a presence heartbeat that it can only produce
while a Web-Bluetooth GATT link is live; a protected endpoint calls `presenceOk()` first and
returns 403 unless a fresh heartbeat from a device the user registered exists. Use for any
"my phone must be here" possession factor, anti-walkaway lock, or physical second factor.

## Reference implementation (extracted from — open before lifting)
Wavelygth build (`~/Projects/clients/wavelygth`), a Cloudflare Worker + D1 + single-file SPA:
- **Backend** `worker/index.js`
  - L2577-2642 — the whole gate: `PRESENCE_TTL_MS = 60000`, `MAX_PHONES = 2`,
    `dialerRequiresPresence()` (reads a setting, default ON), `userPhones()`,
    `handleDialerPhones()` (GET/POST/DELETE, caps at MAX_PHONES, upserts the BT binding with
    `COALESCE`), `handleDialerPresence()` (heartbeat — only counts for a registered
    `bt_device_id`, writes `presence_device`+`presence_at` onto the session row),
    `presenceOk(env, me, sessionId)` (the gate predicate), `handleDialerRequirePresence()`
    (admin toggle → `app_settings`).
  - L2451-2455 — the gate applied at the top of the protected handler:
    `if (!(await presenceOk(env, me, url.searchParams.get('session')))) return json({…, reason:'presence_required'}, 403);`
  - L3147-3157 — route wiring for `/api/dialer/{phones,presence,require-presence}`.
- **UI** `portal/index.html` L1510-1598 — `BT_OK = !!navigator.bluetooth`, `pairBluetooth()`
  (`requestDevice({acceptAllDevices:true})` → `gatt.connect()` → store `device.id`),
  `startHeartbeat()` (25s loop, reconnects gatt if dropped), `onBtDisconnect`,
  `presencePresent()`, `updatePresenceRow()`, `gateStart()` (disables Start until present),
  and the `reqPresence` toggle.
- **Schema** `worker/migrations/0010_dialer_presence.sql` — `user_phones` table +
  `ALTER TABLE call_sessions ADD COLUMN presence_device / presence_at`.
- **Proof** `worker/lib/_proof/dialer-presence.test.mjs` — real HTTP: gate ON blocks with no
  phone; ≤2 phones (3rd → 409); unregistered heartbeat → 403; registered heartbeat serves;
  removing the device closes the gate even with a fresh heartbeat; operator can toggle OFF/ON.

## How to reapply it
1. **Migration.** Add a devices table and two columns on the row that represents an active
   "session" of the gated activity:
   ```sql
   CREATE TABLE IF NOT EXISTS user_devices (
     id TEXT PRIMARY KEY, user_id TEXT NOT NULL, label TEXT,
     bt_device_id TEXT,        -- Web Bluetooth device id (opaque, per-origin)
     bt_device_name TEXT, is_primary INTEGER NOT NULL DEFAULT 0, added_at TEXT NOT NULL
   );
   CREATE INDEX IF NOT EXISTS ix_user_devices_user ON user_devices(user_id);
   ALTER TABLE work_sessions ADD COLUMN presence_device TEXT;
   ALTER TABLE work_sessions ADD COLUMN presence_at     TEXT;   -- ISO timestamp of last heartbeat
   ```
2. **Backend helpers.** `PRESENCE_TTL_MS = 60000`; `requiresPresence(env)` reads a settings key
   default ON; `userDevices(env, userId)`; a device CRUD handler that caps registrations and
   upserts the BT binding with `COALESCE(?, bt_device_id)`; a heartbeat handler that rejects
   (`403 unregistered_device`) any `bt_device_id` not in the user's set and otherwise stamps
   `presence_device`+`presence_at` on the session; and the gate:
   ```js
   async function presenceOk(env, me, sessionId) {
     if (!(await requiresPresence(env))) return true;      // operator disabled it
     if (!sessionId) return false;
     const s = await env.DB.prepare('SELECT presence_device, presence_at FROM work_sessions WHERE id=? AND user_id=?')
       .bind(sessionId, me.id).first().catch(() => null);
     if (!s || !s.presence_at || Date.now() - Date.parse(s.presence_at) > PRESENCE_TTL_MS) return false;
     const devs = await userDevices(env, me.id);
     return devs.some((d) => d.bt_device_id && d.bt_device_id === s.presence_device);
   }
   ```
   Call it at the TOP of every protected handler and 403 with `{reason:'presence_required'}`.
3. **Routes.** GET/POST/DELETE devices, POST heartbeat, POST require-presence (admin-only).
4. **UI.** Feature-detect `navigator.bluetooth`. Pair with
   `navigator.bluetooth.requestDevice({acceptAllDevices:true, optionalServices:[]})`, call
   `device.gatt.connect()`, persist `device.id` as `bt_device_id`. Run a heartbeat every ~25s
   that reconnects gatt if `!gatt.connected`, POSTs the heartbeat, and flips the UI/gate on the
   result; listen for `gattserverdisconnected` to close the gate immediately. Keep the primary
   action button disabled until `presencePresent()`.

## Gotchas
- **Web Bluetooth is Chromium-only.** Desktop/Android Chrome/Edge have it; **iOS Safari has no
  `navigator.bluetooth` at all**. The gate MUST be operator-toggleable or iOS users are locked
  out entirely — default ON, let the operator turn it OFF and fall back to a manual flow.
- **The device id is opaque and per-ORIGIN** — it's stable for the same site, is NOT the MAC,
  and can't be compared across origins. Bind it once at pairing; never try to derive it.
- **Heartbeat interval < TTL, with margin.** 25s beat against a 60s TTL. If the beat approaches
  the TTL the gate flickers closed between beats.
- **It's a real server check, not client UI state.** The predicate is
  `now - presence_at ≤ TTL` AND the device is still registered. Removing the device closes the
  gate even with a fresh heartbeat (the proof asserts exactly this). Don't shortcut it to a
  client boolean.
- **Reject unregistered devices explicitly** (`403 unregistered_device`) — a heartbeat from a
  random paired gadget must not open the gate.
- **`gatt.connect()` can silently fail.** Re-attempt connect() each beat and only report present
  when the heartbeat POST actually succeeds; treat a throw as "not present".
- **Possession ≠ identity.** This proves a registered device is physically near, not who is
  holding it. Layer cf-identity for the who.
