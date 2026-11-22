# A/V Evidence Capture — Screen Recording With Audio

Every engine verification requires one continuous screen recording that also captures audio
(system audio + microphone narration). This reference gives concrete, copy-pasteable commands
per OS, plus how to hash and register the artifact. Prefer ffmpeg for a uniform, scriptable
result; native recorders are listed as fallbacks.

Save recordings under a gitignored evidence path, e.g.
`.test-runtime/evidence/<engine>/<engine>-<timestamp>.mp4`. Never commit media into the repo
(see the repo's Repository Rules — `.test-runtime/`, `runtime/`, `data/`, and media are excluded).

## 0. Confirm ffmpeg + list devices first

```bash
ffmpeg -version   # if missing: macOS `brew install ffmpeg`, Debian/Ubuntu `apt install ffmpeg`, Windows `winget install Gyan.FFmpeg`
```

Audio+screen capture needs the right device names/indices, which are host-specific. Enumerate them:

- **macOS:** `ffmpeg -f avfoundation -list_devices true -i ""`  → note the screen index and the
  microphone index (e.g. `1:0` = screen 1, audio 0). System audio needs a loopback device such as
  BlackHole or Loopback; without one you capture mic only (still acceptable — the narration track).
- **Windows:** `ffmpeg -list_devices true -f dshow -i dummy`  → note the audio device name; screen
  uses `gdigrab`. System audio via a "Stereo Mix" or virtual-audio device; else mic only.
- **Linux:** screen via `x11grab` on `$DISPLAY`; audio via PulseAudio — list sinks with
  `pactl list short sources`.

## 1. macOS (avfoundation)

Screen + microphone (replace indices from the device list; `1` = screen, `:0` = mic):

```bash
ffmpeg -f avfoundation -framerate 30 -i "1:0" \
  -c:v libx264 -pix_fmt yuv420p -preset veryfast \
  -c:a aac -b:a 160k \
  ".test-runtime/evidence/<engine>/<engine>-$(date +%Y%m%dT%H%M%S).mp4"
```

Screen + system audio + mic (requires an aggregate device that mixes BlackHole + mic; create it in
Audio MIDI Setup, then use its index). Native fallback: `Cmd+Shift+5` → Options → select a
microphone → Record; QuickTime "New Screen Recording" with an audio source also works.

## 2. Windows (gdigrab + dshow)

```bat
ffmpeg -f gdigrab -framerate 30 -i desktop ^
  -f dshow -i audio="Microphone (Your Device Name)" ^
  -c:v libx264 -pix_fmt yuv420p -preset veryfast -c:a aac -b:a 160k ^
  .test-runtime\evidence\<engine>\<engine>-%DATE:~-4%%DATE:~4,2%%DATE:~7,2%.mp4
```

To include system audio, add a second `-f dshow -i audio="Stereo Mix (...)"` and mix with
`-filter_complex amix=inputs=2`. Native fallback: **Xbox Game Bar** (`Win+G` → Capture, with mic
enabled) or **OBS Studio** with Display Capture + Audio Input + Desktop Audio sources.

## 3. Linux (x11grab + PulseAudio)

```bash
ffmpeg -f x11grab -framerate 30 -i "$DISPLAY" \
  -f pulse -i default \
  -c:v libx264 -pix_fmt yuv420p -preset veryfast -c:a aac -b:a 160k \
  ".test-runtime/evidence/<engine>/<engine>-$(date +%Y%m%dT%H%M%S).mp4"
```

Headless CI has no display/audio device → capture is `UNSUPPORTED`; mark the engine DEFERRED for
A/V evidence honestly rather than faking a recording.

## 4. Verify the recording actually has an audio track

A silent recording is capture-state `FAILED`. Confirm an audio stream exists and has content:

```bash
ffprobe -v error -show_streams -select_streams a -of json "<file>" | grep codec_type   # expect "audio"
# quick loudness sanity check (should not be near-silence):
ffmpeg -i "<file>" -af volumedetect -f null - 2>&1 | grep mean_volume
```

If there is no audio stream, or `mean_volume` is effectively silence, the capture FAILED — redo it.

## 5. Hash + register the evidence

Compute the audit hash and write an evidence record that attaches to the Project Twin:

```bash
FILE=".test-runtime/evidence/<engine>/<engine>-<timestamp>.mp4"
SHA=$(sha256sum "$FILE" | awk '{print $1}')   # macOS: shasum -a 256 "$FILE"
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$FILE")
cat > "${FILE%.mp4}.evidence.json" <<JSON
{
  "engine": "<engine>",
  "file": "$FILE",
  "sha256": "$SHA",
  "durationSec": $DUR,
  "captureState": "CAPTURED",
  "capturedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "hasAudio": true,
  "checklistItemsShown": ["<item 1>", "<item 2>"]
}
JSON
```

Then attach this record to the engine's Project Twin the same way screenshot evidence is attached,
so the recording lives with the Twin and appears in the Activity Timeline / export summary.

## 6. Capture-state truthfulness

- `CAPTURED` — file exists, has a real audio track with content, shows the checklist.
- `FAILED` — attempted but no/empty audio, corrupt, or missing checklist items. Redo, don't report.
- `UNSUPPORTED` — environment can't record (headless, no audio device). Engine → DEFERRED for A/V.
- `NOT_CAPTURED` — not attempted. Engine is UNVERIFIED until captured.

The recording is evidence, and evidence in Solomon is never fabricated. Report exactly what the
capture-state is; only `CAPTURED` supports an engine VERIFIED verdict.
