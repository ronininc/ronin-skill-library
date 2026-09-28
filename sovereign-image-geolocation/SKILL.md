---
name: sovereign-image-geolocation
description: >-
  Read the BACKGROUND of a photo — signs, storefronts, street names, building numbers, architecture,
  terrain — with a LOCAL vision model, resolve it to a real-world place, geocode it for free, and drop
  it as a PLACED lead on the map. The whole pipeline is sovereign and free: the vision model runs on a
  local Ollama (a localhost cost-guard refuses a paid remote host), geocoding uses free OSM Nominatim
  at a polite 1 req/sec, and the ONLY thing that leaves the machine is the final {name, location, lat,
  lng} to the operator's own CRM. It NEVER identifies the person in the photo — location only, by
  construction (the prompt forbids describing anyone). A drop-folder inbox watches for images and moves
  each to done/ after processing, leaving transient failures to retry. Use WHENEVER a build needs
  "where was this photo taken", "geolocate this image", "turn photos into map pins / placed leads",
  "read the location off a storefront pic", "a watch-folder that geolocates whatever I drop in", or any
  image→place intake that must stay private and off paid APIs. COMPLEMENTS residential-edge-relay (it
  IS a claim/push relay — the local vision + geocode is exactly what the edge can't do),
  geospatial-scene-projector / offline-osm-basemap-map (which RENDER the placed point), and
  open-data-signal-discovery (another placed-lead source). Guardrails: LOCATION ONLY, never identify a
  person; assert the model host is localhost so vision stays free; honest misses ("unknown" / no
  geocode) are dropped cleanly, never guessed; Nominatim politeness (1 req/sec, identifying UA).
---
# Sovereign Image Geolocation

## What it is / when to use / what it composes with
A privacy-forward "GeoSpy method" done sovereignly: instead of a paid face/scene API, a LOCAL vision
model looks only at the *surroundings* of an image and names the most specific place it can; that
place is geocoded for free and posted as a map pin. It is deliberately the opposite of person-
tracking — the prompt refuses to describe or identify anyone, so the output is a location, not a
who. Reach for it as a placed-lead intake or a "where is this" utility that never touches a cloud STT/
vision bill and never leaks the image.

**Composes with:** `residential-edge-relay` (this is one of its relays — the edge can't run a vision
model or reach a LAN Ollama, so the home box does it and pushes a placed lead), `geospatial-scene-
projector` and `offline-osm-basemap-map` (which draw the resulting point), and `open-data-signal-
discovery` (a sibling source of placed leads). The local-vision half shares the sovereignty doctrine
of `local-first-inference-ladder` and `local-media-transcription-pipeline`.

## Reference implementation — exact source (lift the proven code)
`~/ronin-osint/geospy-relay.py`:
- **Cost-guard (keeps it free):** `assert_free()` refuses to run if the Ollama host isn't localhost
  — `geospy-relay.py:41-44`.
- **The location-only prompt (the privacy invariant, in words):** `PROMPT` — "Look ONLY at the
  background… Do NOT describe or identify any person" — `geospy-relay.py:32-38`.
- **Local vision call + honest-miss handling:** `describe_location(img_bytes)` posts the image
  (base64) to the local model, and returns '' on "unknown"/"cannot"/"can't"/"no …" —
  `geospy-relay.py:47-59`.
- **Free geocoding, polite:** `geocode(place)` → OSM Nominatim, one result, identifying UA, honest
  `None` on a miss — `geospy-relay.py:62-78`; the caller sleeps 1.1s after each geocode
  (`geospy-relay.py:108`).
- **Placed-lead push:** `post_lead(name, location, lat, lng, source)` — bearer POST to the CRM —
  `geospy-relay.py:81-86`.
- **Drop-folder pipeline + retry semantics:** `process(path)` — read → describe → geocode → post →
  move to done/; a transient model/post error LEAVES the file in the inbox to retry, a clean "no
  location" moves it to done — `geospy-relay.py:89-122`; `_move_done()` `:125-130`; `scan_once()`
  watches the inbox `:133-141`.
- **The lead's name = the place the model read** (first comma-segment, trimmed) —
  `geospy-relay.py:114-115`.

## How to reapply — the wiring + THE INVARIANT
1. **Inbox → done drop-folder:** watch a directory for known image extensions; after a terminal
   outcome move the file to `done/`; on a transient error leave it for the next pass
   (`geospy-relay.py:133-141`,`101-102`,`119-121`). This makes the whole thing crash-safe and
   re-runnable.
2. **Local vision, temperature 0, location-only prompt** (`geospy-relay.py:50`,`32-38`). Swap the
   model via env; keep the "surroundings only, never a person" wording verbatim.
3. **Geocode free + polite** (Nominatim, 1 req/sec, identifying UA) and treat a non-geocoding place
   as an honest miss, not a guess (`geospy-relay.py:62-78`,`108-112`).
4. **Push a placed lead** `{name, location, lat, lng, source:"photo:<file>"}` to the operator's own
   endpoint (this is the residential-edge-relay push).

**THE INVARIANT:** the model reads the SCENE, never the subject — the output is a place, and the
person is never identified or described. Free by construction: vision is localhost (asserted), the
only egress is a place + coordinates to the operator's own CRM. An unreadable or un-geocodable image
is dropped honestly, never invented.

## Gotchas — real pitfalls from the code + how it's validated
- **The privacy line is the prompt.** If you loosen the wording to "describe the image," you've built
  a person-tracker. Keep it location-only (`geospy-relay.py:32-38`); the cost-guard and the
  no-person prompt are the two non-negotiables.
- **Small vision models hallucinate places.** Temperature 0 and an "answer 'unknown' if unsure"
  escape hatch cut this; the miss-detector treats "cannot"/"unknown"/"no …" as no-location
  (`geospy-relay.py:57`). Still a CANDIDATE pin — an operator confirms before acting.
- **Nominatim will ban a hammer.** One request/second and an identifying UA are required
  (`geospy-relay.py:66`,`108`); geocoding failures return `None`, not an exception.
- **Transient vs terminal matters.** A model timeout must leave the file to retry; a genuine "no
  place readable" must move it to done, or the inbox jams on one bad image
  (`geospy-relay.py:100-105`,`119-121`).
- **HEIC/format support** depends on the local decoder; unusual formats may silently read as bytes
  the model can't use — validate a sample end-to-end with `--once`.
- **It's host-bound + arm-gated** like every residential relay: the CRM endpoint must exist and
  accept the token, and the feature is live only while the watcher runs.
