---
name: screen-recording-ocr-text-recovery
description: >-
  Recover the TEXT that scrolled past in a screen recording — chat transcripts, terminal output,
  a document someone screen-recorded instead of copying — by sampling frames at a fixed cadence,
  OCR'ing each with tesseract, and deduping the overlapping lines back into one clean, ordered
  transcript. Frame-sampling (fps=1) beats scene-detection here because slow scrolling produces few
  "scenes" and undercounts, silently dropping half the text. Use WHENEVER "get the text out of this
  screen recording / screencap video", "they screen-recorded the chat instead of forwarding it",
  "read the messages/logs off this .mov", "OCR what scrolled by", or any time the only copy of some
  text is trapped in a video someone recorded off their screen. COMPLEMENTS
  desktop-app-cache-media-recovery (that recovers the app's original AUDIO + PHOTOS from cache; THIS
  recovers the typed lines off the recording itself — run both on the same .mov),
  local-media-transcription-pipeline (audio → text; THIS is pixels → text), and video-walkthrough
  (which PRODUCES captured-screen video; this READS one back). Guardrail: OCR is lossy — verify
  numbers, handles, and anything load-bearing against a second frame; recovered chat text is PII
  (gitignore, never commit). NOTE: proven ad-hoc command sequence, not yet a committed script — a
  future build should lift the pipeline below into one.
---

# Screen Recording → OCR Text Recovery

When the only copy of some text is a video of a screen — a client screen-records a chat instead of
forwarding it, someone captures a terminal or a doc scrolling by — the words are pixels, not
characters. This turns them back into text locally: sample frames, OCR them, dedupe. It is the
"typed text" counterpart to `desktop-app-cache-media-recovery` (which handles the same recording's
audio + original photos) and to `local-media-transcription-pipeline` (audio, not pixels).

## Reference — proven technique (UNWIRED; lift these exact commands)

Documented at
`/Users/robbiebrown/.Codex/projects/-Users-robbiebrown-Projects-TSS/memory/whatsapp-desktop-media-cache-extraction.md`
(the "Chat text" step). It is a runbook, not a committed script — **flag for a future build: script
this.** Core pipeline:

```
ffmpeg -i recording.mov -vf fps=1 frames/%05d.png     # 1 frame/sec — dense enough for scrolling
for f in frames/*.png; do tesseract "$f" - --psm 6; done > raw.txt
# then dedupe consecutive/overlapping lines back into one ordered transcript
```

## How to reapply — the recipe + THE INVARIANT

1. **Sample at a fixed cadence** (`-vf fps=1`, raise to `fps=2` for fast scrolling). Do NOT rely on
   `select='gt(scene,…)'` scene-detection: slow scrolling changes too little frame-to-frame, so it
   emits few scenes and **undercounts**, dropping lines. Fixed-cadence oversamples on purpose.
2. **OCR each frame** with tesseract (`--psm 6` treats the frame as a uniform block of text; pick the
   `-l` language to match the content).
3. **Dedupe** — because you oversample, the same line appears in many consecutive frames. Collapse
   consecutive duplicate/near-duplicate lines while PRESERVING order (a line that legitimately
   repeats later, after other lines, is kept). Order is carried by frame number, top-to-bottom.

**THE INVARIANT:** coverage comes from oversampling at a fixed cadence and *then* deduping — never
from trying to detect "when the screen changed." Losing a line is unrecoverable; a duplicate is free
to remove. Always err toward more frames.

## Gotchas — real, from the field

- **Scene-detect undercounts scrolling** — the single most important failure mode; use `fps=N`.
- **OCR is lossy on small/antialiased UI text** — verify numbers, @handles, prices, and any
  load-bearing token against a second frame or a higher `fps`; never assert an OCR'd digit as fact.
- **Overlap is the point** — a scrolling chat shows each line across several frames; the dedupe step
  is what turns that redundancy into a clean transcript, so tune dedupe, not the sample rate down.
- **Pair it** — run this alongside `desktop-app-cache-media-recovery` on the same `.mov`: OCR gives
  the typed messages, the cache gives the voice notes + full-res photos; together they reconstruct
  the whole conversation the recording only partially shows.
- **Validation:** spot-check a few recovered lines against the visible frames; the transcript is
  trustworthy when line order matches the on-screen scroll and no visible line is missing. Treat the
  output as PII — gitignore, never commit.
