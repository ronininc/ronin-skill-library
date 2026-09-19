---
name: self-schedule-booking
description: >-
  A Calendly-style self-scheduler owned entirely by a Cloudflare Worker + D1 CRM
  — no Calendly/SavvyCal/Cal.com. A lead opens a public page carrying only an
  opaque 64-hex token (never PII in the URL), sees timezone-correct open slots
  computed against the CRM's already-booked meetings, and claims one; the Worker
  creates a Google Calendar event with a Meet link, race-safe. Use WHENEVER a
  client CRM must "let leads book a time themselves", "send a scheduling link",
  "book consults/appointments without a third-party scheduler", "put a booking
  page on the site", or "auto-create the calendar invite + video link." It
  COMPLEMENTS: google-oauth-connector (which owns the OAuth token mint/refresh —
  this skill only CALLS getGoogleAccessToken and never re-implements auth);
  pipeline-autopilot (which decides WHEN to send the link — this skill is the
  page + slot math + claim it invokes); crm-build-standard (the meetings/contacts
  tables). Do NOT rebuild OAuth here. Guardrails: the token is the only
  credential and carries no PII; the booking claim is a single conditional
  UPDATE guarded on status='proposed' so two simultaneous claims can't
  double-book; slots exclude everything already booked and never offer a time
  inside a near-term buffer.
---
# self-schedule-booking — sovereign Calendly on Worker + D1

## What it is / when to use
An opaque-token public scheduling page plus the server-side slot math and a
race-safe booking claim that creates a Google Calendar event + Meet link. It
turns a `meetings` row (status `proposed`) into a bookable link; the lead picks
a slot; the Worker books it and flips the row to `booked`. It also covers the
operator's one-click "book this meeting now" path from the admin CRM. Use it for
any consult/appointment booking a client CRM should own end-to-end.

**Composes with (do not duplicate):**
- **google-oauth-connector** — owns the Google connection (consent, token
  storage, refresh). This skill imports `getGoogleAccessToken(env)` and stops
  there. If Google isn't connected, this skill surfaces the honest error, not a
  fake success.
- **pipeline-autopilot** — decides *when* a booking link is prepared/sent. This
  skill is the destination page + `scheduleBook` claim it drives.
- **crm-build-standard** — supplies `contacts` and `meetings`.

## Reference implementation (ronininc — patterns only, no client data)
- `worker/autopilot.ts`
  - **L123–149** timezone slot math: `zonedTimestamp()` (two-pass wall-clock→epoch for any IANA tz, DST-correct), `isoWeekday()`, `slotLabel()`.
  - **L151–182** `openSlots()` — the core generator: pulls already-`booked` meetings, walks the window day-by-day resolving local Y-M-D per offset, skips slots inside the near-term buffer, off-days, and any that **overlap** an existing booking; returns `{start, label}[]` capped at `max`.
  - **L184–248** `createMeetEvent()` (Calendar event + `conferenceData.createRequest` → Meet link, `sendUpdates=all`), the in-thread Gmail send used to deliver the link, and `bookingToken()` (two concatenated uuids → 64 hex).
  - **L256–303** booking-link send (`ensureBookingToken`, `sendBookingFor`, `sendBookingByMeeting`).
  - **L314–377** the public self-schedule surface:
    - **L321–327** `meetingByToken()` — validates the token against `/^[a-f0-9]{64}$/i` **before** any query.
    - **L329–340** `scheduleInfo()` — returns booked-state or open slots for the token.
    - **L342–377** `scheduleBook()` — re-derives slots and rejects a `start` not in the current open set, creates the Meet event, then the **race-safe claim** (L366–372): `UPDATE meetings SET status='booked',... WHERE booking_token=? AND status='proposed'`; `if (!claim.meta.changes)` it lost the race → returns the already-booked result. Writes an activity + heartbeat on success.
- `worker/business-apps.ts` **L96–135** `bookMeeting()` — the admin one-click variant (operator books a specific meeting directly).
- `migrations/0020_autopilot.sql` **L50–55** — `meetings` ALTERs (`booking_token`, `booking_sent_at`, `duration_min`) + **partial UNIQUE index** `WHERE booking_token IS NOT NULL`.
- `worker/index.ts` **L51–56** — public routes: `GET /api/schedule?t=` (open slots) and `POST /api/schedule?t=` (claim), the POST guarded by `sameOrigin`.
- `public/schedule/index.html` + `public/schedule/schedule.js` — the standalone page (noindex, reads `?t=`, groups slots by day, disables all slots while claiming, refreshes on "no longer available").
- `public/admin/admin.js` **L1578–1591** — the booking-queue card (Send link / Copy link / booked+Meet states).

## How to reapply it
**1. Migration.** On your `meetings` table add `booking_token TEXT`, `booking_sent_at INTEGER`, `duration_min INTEGER`, and a **partial unique index**:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_meetings_booking_token
  ON meetings(booking_token) WHERE booking_token IS NOT NULL;
```

**2. Token.** `const bookingToken = () => `${uid().replace(/-/g,'')}${uid().replace(/-/g,'')}`;` → 64 hex. Gate every read with `if (!/^[a-f0-9]{64}$/i.test(token)) return null;` **before** touching D1.

**3. Slot math.** Port `zonedTimestamp` (the DST-safe wall-clock→epoch two-pass) and `openSlots`: fetch booked intervals once, then for each day in the window build candidate starts at the interval step, dropping any that are before `now()+buffer`, on a non-bookable weekday, or that overlap a booked interval.

**4. Public endpoints.** `GET /api/schedule?t=` → validate token → `scheduleInfo` (booked payload or `{slots}`). `POST /api/schedule?t=` → **require same-origin**, re-derive slots, reject a `start` not in the set, create the event, then claim:
```ts
const claim = await env.DB.prepare(
  "UPDATE meetings SET status='booked',starts_at=?,ends_at=?,google_event_id=?,meet_url=?,updated_at=? WHERE booking_token=? AND status='proposed'"
).bind(start, end, eventId, meetUrl, now(), token).run();
if (!claim.meta.changes) { /* lost the race — return the existing booking */ }
```

**5. Calendar event.** Import `getGoogleAccessToken` from your google-oauth-connector build. POST to `.../calendars/primary/events?conferenceDataVersion=1&sendUpdates=all` with a `conferenceData.createRequest` (type `hangoutsMeet`); read the video `entryPoint.uri` (fallback `hangoutLink`) for the Meet URL.

**6. The page.** A static, `noindex` HTML+JS page that reads `?t=`, `GET`s slots, renders day-grouped buttons, and on click `POST`s `{start}` with `credentials:'same-origin'`. Disable all slot buttons during the request; on an "available" error, reload slots (someone took it).

**7. Deliver the link.** Send `${BASE}/schedule/?t=${token}` however the CRM messages leads (in-thread Gmail reply here) — that send belongs to governed-email-outreach / pipeline-autopilot, not this skill.

## Gotchas
- **Validate the token shape before the DB call.** The regex gate stops malformed-token probing from ever reaching D1.
- **Never put PII in the URL.** The token is the whole address; name/email live only in the row it points to. The page is `noindex,nofollow`.
- **The claim is the double-book guard.** Do the `WHERE ... status='proposed'` conditional UPDATE and branch on `meta.changes` — do NOT "read then write", which races. If it created a Calendar event but lost the claim race, you have a stray event; the reference accepts that trade (rare) and returns the winning booking. If that matters, delete the loser's event on `changes===0`.
- **Slots must exclude your own bookings.** `openSlots` overlaps candidates against existing `booked` meetings; without that the page offers times you're already busy.
- **DST is real — don't add 3600×hours.** Use the `Intl.DateTimeFormat` two-pass `zonedTimestamp`; naive UTC offset math books the wrong hour twice a year.
- **Near-term buffer.** Never offer a slot inside the next ~2h (`BOOKING_BUFFER_SEC`) — leads shouldn't book a call five minutes out.
- **Re-derive slots on the POST.** Validate the submitted `start` against a freshly-computed open set, not a trusted client value — otherwise a stale/forged `start` books an off-hours or double slot.
- **Google not connected = honest failure.** If `getGoogleAccessToken` throws or the Calendar API rejects, return the real error (502), never a "booked" the calendar never received.
