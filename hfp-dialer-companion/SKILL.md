---
name: hfp-dialer-companion
description: >-
  A native Node bridge that pairs to a phone as a Bluetooth hands-free unit (HFP, car-kit role)
  and auto-dials the phone's OWN cellular SIM — NO third-party telephony service (no Twilio, no
  SIP) — with real answer-detection (auto-advance on ring-outs, PAUSE on a live answer for a
  human to classify), while doubling as the device-presence heartbeat that unlocks a server-side
  possession gate. Use WHENEVER a build needs hands-free auto-dialing through the operator's own
  phone rather than a paid voice API — "dial my list through my iPhone/Android", "auto-dial the
  SIM", "hands-free power dialer with no Twilio", "call node companion", "the web app can't drive
  Bluetooth calls / can't auto-dial on iOS", or "a local helper that dials and detects answers".
  Backend/native (standalone Node ESM package; Linux + BlueZ + oFono for the real radio, a mock
  radio for dev/proof). This is the NATIVE companion to device-presence-gate (it sends the same
  heartbeat) and it consumes a scoped Bearer token; the governed dialer ENGINE it feeds (daily
  queue, compliance, disposition→learning) already lives in crm-build-standard's power-dialer —
  this skill is ONLY the possession/HFP bridge, not the dialer engine. Guardrails: human-in-the-
  loop (pause on answer, operator classifies); compliance is SERVER-side (the bridge can only
  dial what the queue serves); data-minimized (only a bare number ever crosses to the phone);
  never predictive/robo/ringless/spoofed-caller-ID.
---

# hfp-dialer-companion — dial your own SIM over Bluetooth, no telephony vendor

## What it is / when to use
A tiny background app on the operator's own machine that links to their phone over Bluetooth
Hands-Free Profile (the "car kit" role), uses the phone as a dumb call node to place calls on
its **own cellular SIM**, detects whether each call rings out or is answered, and heartbeats
device-presence so the server gate stays open. Use when you want hands-free auto-dialing with
no third-party telephony and no per-minute cost. It is the native half of `device-presence-gate`
and feeds — never replaces — the governed power-dialer in `crm-build-standard`.

## Reference implementation (extracted from — open before lifting)
Wavelygth build (`~/Projects/clients/wavelygth/companion/`), a standalone Node ESM package
(`package.json`: `type:module`, `bin`, `optionalDependencies: dbus-next`, `proof` script):
- `index.mjs` — entry: env config (`COMPANION_TOKEN`, `PHONE_NUMBER`, `HFP_BACKEND`,
  `UI_PORT`, `RING_TIMEOUT_MS`), wires `ServerClient` + `makeHfp` + `DialerCompanion` + local UI.
- `lib/loop.mjs` — `DialerCompanion` state machine: `connectAndRegister()`, `startPresence()`
  (25s beat), `dialAndWatch()` (resolves `active` | `no_answer` on a ring timeout), `runOnce()`
  (pull next → strip number → dial → pause-on-answer for classification → disposition),
  `start()/stop()`, `resolvePause()`.
- `lib/server-client.mjs` — thin Bearer client (`registerPhone`, `presence`, `sessionStart/End`,
  `next`, `disposition`, `dnc`).
- `lib/hfp/index.mjs` — `makeHfp(kind)` backend factory (lazy-imports the real backend).
- `lib/hfp/ofono.mjs` — real radio: BlueZ + oFono over D-Bus (`org.ofono.Manager.GetModems` →
  find `Type='hfp'` modem → `VoiceCallManager.Dial(number,'default')` → watch `VoiceCall` State;
  `HangupAll()` to hang up; `STATE_MAP` maps oFono states to `dialing|ringing|active|ended`).
- `lib/hfp/mock.mjs` — simulated radio (`dialing → ringing → active|ended`) for dev + proof.
- Docs `README.md`, `SECURITY.md`, `docs/HFP_SETUP.md`; spec `docs/NATIVE_DIALER_COMPANION_SPEC.md`.
- **Proof** `companion/_proof/loop.test.mjs` — boots a local Worker + drives the whole loop
  against the mock radio: registers its device, its heartbeat satisfies the possession gate,
  it pulls the compliance-filtered list, auto-advances no-answers, pauses on answers, and every
  outcome lands on the server (8/8).
- Server side it depends on: `worker/index.js` L214-225 (`companionUser` — resolve a Bearer
  `wvc_…` token by its SHA-256 hash) and L3079-3113 (Bearer clients skip CSRF but are
  hard-scoped to `/api/dialer/*`, never token management, never admin).

## How to reapply it
1. **Server prerequisites** (three existing skills): mint/verify a scoped Bearer token
   (`scoped-bearer-token` — SHA-256 stored, shown once, path-scoped to the dialer, CSRF-exempt
   because it's not a cookie); the presence heartbeat endpoint (`device-presence-gate`); and the
   queue's `next` / `disposition` / `session` endpoints (`d1-work-queue` + the power-dialer
   engine in `crm-build-standard`). The bridge is a pure consumer of these HTTP endpoints.
2. **HFP backend contract.** An `EventEmitter` with `connect()`, `disconnect()`, `isConnected()`,
   `deviceId()`, `dial(number)`, `hangup()`, emitting `'connected'`/`'disconnected'` and a
   `'state'` event of `dialing|ringing|active|ended`. Ship two: `ofono` (real) and `mock` (dev).
   `makeHfp(kind)` picks and **lazy-imports** the real backend so the mock path needs no native
   deps. For a real Android or other-Linux target the same oFono contract applies.
3. **The loop** (`runOnce` per lead): `client.next(session)` → on 403 treat as
   `presence_or_forbidden` and idle; strip `lead.dial` to `[0-9+]` ONLY; `dialAndWatch` resolves
   `active` or `no_answer` (ring timeout); on `active` → set `paused`, await the operator's
   classification (`resolvePause(outcome)`), hangup, `disposition`; on `no_answer` → auto-advance
   with a `no_answer` disposition. Heartbeat presence every 25s while connected. Stop on
   `list_complete`.
4. **Local UI** on `127.0.0.1` only — current contact card + disposition buttons; never bind to
   `0.0.0.0`.
5. **Linux setup** (`docs/HFP_SETUP.md`): `apt install bluez ofono`; `bluetoothctl` pair + trust
   + connect the phone; confirm `GetModems` shows an `hfp`-type modem `Online`; optional systemd
   unit for boot. Mac operators run the bridge on a nearby Linux box (a Raspberry Pi).

## Gotchas
- **The radio is Linux-only.** Neither macOS nor Windows exposes a usable HFP Hands-Free API,
  and **Web Bluetooth cannot do HFP** (it's BLE/GATT-only) — plus iOS won't let an app auto-dial
  its SIM. That combination is exactly WHY this native bridge exists; don't try to fold it back
  into the browser. Mac users need a small Linux box (a $40 Pi is fine).
- **`dbus-next` is an `optionalDependency`, lazy-imported.** The mock path and the proof run with
  zero install; only the real `ofono` path needs it. Keep the import inside `connect()`.
- **Data minimization is load-bearing.** The loop strips the dial string to `[0-9+]` before it
  ever reaches the phone — no name, company, note, or CRM field crosses the Bluetooth link. The
  phone is a dumb modem; all data stays server-side over TLS. The daemon log prints the number
  only.
- **Set the pause resolver BEFORE emitting status** (see the loop comment) so a fast UI reply
  can't race ahead of the resolver and drop the classification.
- **Compliance is server-side truth.** The bridge can only dial what `/api/dialer/next` serves
  (consent + DNC + calling-hours + frequency cap all enforced there per
  `outbound-compliance-gate`). Do NOT re-implement compliance in the bridge, and never make it
  predictive / robo / ringless / caller-ID-spoofing.
- **The link is temporary.** Bring HFP up on Start, release on Stop/end (`hfp.disconnect()`).
  Losing range mid-run stops heartbeats → the server possession gate locks within its TTL, which
  is the intended safety behavior.
- **Token hygiene.** Scoped to `/api/dialer/*` (never its own management, never admin), SHA-256
  at rest, plaintext shown once, revocable. Keep `COMPANION_TOKEN` out of shell history (env file
  `chmod 600`).
- **Call audio (SCO) is a separate path from call control.** The companion only does control; for
  a talk path, use a headset/speaker on the box or talk on the phone directly.
- **TCPA/ATDS exposure is real** for any auto-dialer — keep the human in the loop and get a
  compliance sign-off on the list's consent basis before a live run.
