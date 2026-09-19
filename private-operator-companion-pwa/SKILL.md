---
name: private-operator-companion-pwa
description: >-
  A PRIVATE, installable, offline-capable mobile command app for the OPERATOR of a Cloudflare Worker + D1
  CRM — not a public page. The static app-shell is served ONLY to an authenticated staff session and the
  route 404s (never 401s) for everyone else so the surface's very EXISTENCE isn't disclosed; a service
  worker caches the shell for instant/offline load but NEVER caches /api/* (money/orders must always be
  live); it installs to the home screen via a webmanifest; it ships a labelled ?demo=1 example-data mode so
  it's showable with no live session; and it hosts an ON-DEVICE critical-event alarm (color "condition"
  code + WebAudio siren + haptic + native-Web-Speech voice brief and one-word voice APPROVE that POSTs to
  the existing governed endpoint). Use WHENEVER a build needs "an app to run the business from my phone",
  "a private operator/owner mobile dashboard", "install it to the home screen", "works offline", "don't
  let anyone else even find it", "wake me / sound an alarm when something breaks", "approve the fix by
  voice", or "a phone command surface for the CRM". It is a DELIVERY-SURFACE skill: it renders read-models
  and calls actions owned by OTHER skills — it COMPLEMENTS cf-identity (reuses its staff-session gate; do
  NOT rebuild auth), money-feed-health-monitor + order-pnl-fund-gate-fulfillment (the money/fulfillment
  "condition" rollup it displays), capital-leak-breaker (the alarm's approve-to-relive target — money
  stays never-auto, the phone is a client not a new authority), quick-capture-inbox (its capture screen),
  content-studio-publisher (where a capture is promoted), governed-operator-console (the desktop sibling
  of the same governance), and white-label-branding (theming). Guardrail: the shell hide-gate and the API
  fail-closed gate are TWO separate checks; the SW must never cache authenticated data; audio/voice need a
  user-gesture arm; every action still goes through its normal server-side re-validation.
---
# private-operator-companion-pwa — a hidden, offline, install-to-phone operator command app

## What it is / when to use
The mobile delivery surface for the person who RUNS the business: a small installable PWA that shows the
live "how are we doing" rollup, lets the operator triage and act, and physically gets their attention when
something critical happens (a capital leak auto-halts a flow) — all behind a staff session, and invisible
to anyone who isn't signed in. It owns no data model of its own; it is the phone-shaped front-end over
read-models and governed actions that already exist in the CRM. Reach for it when the deliverable is "give
the owner a private app for their phone" rather than another admin page in the desktop SPA.

**Composes with (do not duplicate):**
- **cf-identity** — the shell gate reuses `requireStaff`. This skill adds no auth of its own.
- **money-feed-health-monitor** / **order-pnl-fund-gate-fulfillment** — supply the single rollup endpoint
  the app polls (money in/out/net series, pending orders, fulfillment health, "condition"). This skill
  renders it; it does not compute it.
- **capital-leak-breaker** — the alarm surfaces its staged breakers and the voice/tap "approve" calls
  `breaker/resolve`. Money-never-auto is enforced server-side there, unchanged.
- **quick-capture-inbox** — the app's capture screen is that skill's mobile client.
- **content-studio-publisher** — a `content` capture is promoted into its queue from the app.
- **white-label-branding** — the shell CSS/manifest theme.

## Reference implementation (ronininc — read these; patterns only, no client data)
Static PWA under `public/companion/` + one gate in the Worker; the "Kingmaker" private operator app.
- **The hide-gate** — `worker/index.ts:164-172`. `/companion` and `/companion/*` run the Worker first;
  `requireStaff(request, env)` — if it returns a Response (no staff session) the route answers a **plain
  404** (`Not found`), NOT 401, so the surface's existence is not disclosed; only a staff session is served
  the shell via `env.ASSETS.fetch`. The comment states the contract: the installed PWA keeps working from
  its SW cache, and a lapsed session just 401s at the API. The manifest/SW/JS assets themselves load from
  `public/` normally — only the route that boots the app is gated.
- **Service worker** — `public/companion/sw.js:1-12`. `CACHE='ronin-companion-v1'`; `SHELL=[...]` the
  static app-shell files; `install` → `caches.open().addAll(SHELL)` + `skipWaiting()`; `activate` → delete
  every cache key ≠ current + `clients.claim()`; `fetch` → **early-return (network) for any `/api/*` path
  and any non-GET**, else cache-first (`caches.match || fetch`). The "never cache /api/*" line is the whole
  point — money data must always be live.
- **Manifest** — `public/companion/manifest.webmanifest:1-16`. `display:standalone`, `orientation:portrait`,
  `scope`/`start_url` = `/companion/`, maskable + apple-touch icons — installable to the home screen.
- **Client** — `public/companion/companion.js`:
  - **Demo mode** `:12` — `?demo=1` → `exampleData()` (`:197+`) renders a **labelled** example payload
    (`#demo-tag` shown) so the app demos with no live session; the 45s poll (`:230`) is disabled in demo.
  - **Alarm plumbing** `:16-24` — `arm()` lazily creates/resumes an `AudioContext` **on a user gesture**
    and vibrates; `siren()` synthesizes a rising square-wave klaxon via WebAudio (no audio file);
    `ackedSet()`/`setAcked()` persist acknowledged breaker ids in `localStorage` (`km_acked`) so the siren
    does NOT re-fire every poll for an already-seen leak.
  - **Voice** `:25-57` — native Web Speech only. `initVoice()` picks a *quality* TTS voice (a `GOOD` name
    regex, else a non-local voice) so it never uses a robotic default, and wires `SpeechRecognition`;
    `handleCommand()` answers "status / money / leaks / what needs work" by speaking the live rollup, and on
    "approve / go live / fix it" **POSTs `/api/admin/breaker/resolve` `{action:'approve'}`** for the staged
    breaker, then re-loads. Mic button is shown only where recognition exists (`:42`).
  - **Render** `:87-149` — maps `condition` (white/yellow/orange/red) to a CSS var + description, draws the
    money series and net line (rough.js), and renders the fulfillment-health pills + "CRM pack sold — start
    working" cards from the rollup.
  - **Data** `load()` `:190-195` — GET `/api/admin/store/feed` (credentials same-origin); on success render
    live + `loadCaps()`; on ANY failure → demo payload if `?demo=1` else `signIn()`. Poll every 45s only
    when the dashboard is visible and not in demo (`:230`).
  - **Tap actions** `:225-227` — approve/dismiss a breaker and mark a capture done, each a same-origin POST
    to the existing governed endpoint.

## How to reapply it
1. **Gate the shell route, don't invent auth.** Run the Worker first for `/<app>` and `/<app>/*`; call your
   existing staff gate; on no-session return a **404** (hide), else `env.ASSETS.fetch(request)`. Keep every
   `/api/*` action on its own fail-closed gate (401/403) — the shell hide and the API gate are separate.
2. **Service worker.** Cache a small explicit shell list; `skipWaiting()` + `clients.claim()`; on `activate`
   delete non-current caches; in `fetch` **return early for `/api/*` and non-GET** (always network), else
   cache-first. Bump the cache name whenever a shell asset changes or installed users get a stale app.
3. **Manifest.** `display:standalone`, portrait, `scope`/`start_url` at the app path, maskable icon — so
   Add-to-Home-Screen gives a real app window.
4. **Demo mode.** A `?demo=1` branch that renders a hard-coded, clearly **labelled** example payload and
   disables the live poll — lets you show the app (screenshots, a pitch) with no session and no live data.
5. **On-device alarm (optional but the point on mobile).** Arm audio/haptics on the first user tap
   (browsers block autoplay); synthesize the alert tone in WebAudio (no asset); dedupe alerts against a
   `localStorage` acked-set so a repeating poll doesn't re-alarm; render a color "condition" code so state
   is readable at a glance.
6. **Voice (optional).** Use native `speechSynthesis` (guard for a good voice) + `SpeechRecognition`; map a
   few intents to *speaking the live rollup* and to *calling an existing governed action*. Never let voice
   become a new authority — "approve" just fires the same endpoint a tap would.
7. **Poll, don't socket.** A ~45s `setInterval` while visible is plenty and cheap; skip it in demo.

## Gotchas (from the code)
- **404, not 401, for the shell.** A private operator surface should not announce itself. The route returns
  a plain-text 404 to a non-staff request; the *data* endpoints still return 401/403. Getting this backwards
  either leaks the app's existence or locks out the legit PWA after a session blip.
- **The SW must NEVER cache `/api/*`.** Caching money/orders would show an operator stale or wrong numbers —
  the exact failure a money app can't have. Only the static shell is cached; every data/action call is
  network-only and non-GET is skipped entirely.
- **Installed PWA outlives the session.** The shell loads from cache even when the login has lapsed; the
  client must treat an API 401 as "sign in again," not render cached-looking data. `load()`'s catch → sign-in
  is that contract.
- **Audio & speech need a user gesture.** `AudioContext` and speech are suspended until the operator taps
  (`arm()`), so wire the first alarm-arm to an explicit control; don't expect a siren on cold load.
- **Dedupe the alarm.** Without the `localStorage` acked-set the 45s poll re-fires the siren for the same
  unresolved leak every tick. Persist what's been acknowledged; clear it when the underlying event resolves.
- **Voice approval is still governed.** The spoken "approve" POSTs the same `breaker/resolve` the desktop
  uses; the server re-validates and money stays never-auto. The phone adds convenience, not authority.
- **Demo data must be unmistakable.** Show the `demo` tag and never let example numbers reach a path that
  looks live — an operator glancing at a red "condition" must know instantly whether it's real.
- **Ships as static assets.** The whole app is `public/<app>/` (html+js+css+sw+manifest) served by the assets
  service; the only server code is the one hide-gate. Keep it that way — no server rendering of the shell.
