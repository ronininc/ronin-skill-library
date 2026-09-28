---
name: desktop-app-cache-media-recovery
description: >-
  Recover the ORIGINAL media assets a desktop messaging app already downloaded — voice notes,
  full-resolution photos, videos — straight from the app's on-disk cache, when all you were handed
  is a screen recording (which has NO audio track and only shows downscaled crops). It locates the
  app's local Media cache, dedupes the many-times-duplicated files by md5, and re-identifies each
  asset by matching duration (ffprobe) and file mtime to what's visible in the chat — so a client's
  "0:34" voice note and their 3840×5120 original photo come back as real files, not lossy captures.
  Use WHENEVER "the instructions came as a WhatsApp/Signal/Telegram screen recording", "the voice
  note isn't in the video / has no sound", "get the real photo not the crop from the recording",
  "pull what they actually sent me", or any task where the deliverable needs the client's authentic
  media but you only have a screengrab of the chat. COMPLEMENTS local-media-transcription-pipeline
  (hand the recovered .opus/.m4a to it for the actual transcript), screen-recording-ocr-text-recovery
  (recover the TYPED chat text off the same recording), and site-media-fetch (that pulls a business's
  PUBLIC/remote media with yt-dlp; THIS recovers privately-received media from a local app cache).
  Guardrails: read-only recovery of media on the operator's OWN machine that they already received —
  never a tool to reach into another person's device or account; treat every recovered file as
  client PII (gitignore, never commit). NOTE: no committed script exists yet — this is an unwired,
  proven command sequence; a future build should lift the commands below into a script.
---

# Desktop App Cache Media Recovery

Clients relay change requests as macOS screen recordings of a desktop chat (WhatsApp Desktop, etc.).
Two things are missing from that `.mov`: **the audio** (a screen recording does not capture system
sound, so voice notes are simply not in the file) and **full resolution** (the recording only shows
downscaled, cropped previews). Both the original voice notes and the original photos are already
sitting in the app's local cache — this recovers them, zero tokens, zero upload. It is the "get the
real bytes" step that feeds `local-media-transcription-pipeline` (audio → transcript) and pairs with
`screen-recording-ocr-text-recovery` (the typed lines).

## Reference — proven technique (UNWIRED; lift these exact commands)

Documented and executed at
`/Users/robbiebrown/.claude/projects/-Users-robbiebrown-Projects-TSS/memory/whatsapp-desktop-media-cache-extraction.md`.
It is a *technique*, not a committed script — the md5-named transcripts in `~/ronin-ingest/transcripts/`
are the evidence it ran. **Flag for any future build: turn the steps below into a real script; today
it ships as a runbook only.**

WhatsApp Desktop cache shape (genericize the app for Signal/Telegram — same md5+duration idea):

```
~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/Message/Media/<chat-jid>/x/y/<uuid>.{opus,jpg,mp4}
```

- **Group chats** end `<id>@g.us`; a 1:1 chat is a phone-number jid. Pick the chat folder by matching
  image **mtimes** to the message timestamps visible in the recording.
- **Dedupe** — files are duplicated many times across the tree: `md5 -r <dir> | sort | uniq -w32`
  (or `-d` to see the dupes) collapses to one copy per distinct asset.
- **Voice notes → match by duration** — `ffprobe -v error -show_entries format=duration -of csv=p=0 x.opus`
  and line it up against the `0:34`-style labels shown in the chat.
- **Photos → prefer the original** — the same folder holds the full-res sends (e.g. 3840×5120). Use
  those; NEVER a crop scaled out of the screen recording.
- **Transcribe the audio** — `ffmpeg -i x.opus -ar 16000 -ac 1 x.wav` then whisper-cli with `-l auto`
  (this is exactly the audio leg of `local-media-transcription-pipeline`).

## How to reapply — the recipe + THE INVARIANT

1. From the recording, read off the visible message timestamps and each voice note's `m:ss` label.
2. `md5 -r` the candidate `Media/<chat>` tree; `sort`/`uniq -w32` to the distinct assets.
3. For each distinct `.opus`/`.m4a`, `ffprobe` the duration and match it to a label; for photos,
   sort by mtime and match to the visible send order, keeping the highest-resolution original.
4. Copy the matched originals out to a working folder, then transcribe the audio.

**THE INVARIANT:** identity is re-established by intrinsic signal — **md5 for dedupe, duration for
voice, mtime + resolution for photos** — because the cache filenames are opaque UUIDs that carry no
ordering. Never trust filename order; always match on the content signal.

## Gotchas — real, from the field

- **The screen recording has no audio at all** — don't waste time trying to extract sound from the
  `.mov`; the voice note only exists in the cache. This is the whole reason the skill exists.
- **The recording filename hides a no-break space** — macOS names it like
  `Screen Recording … PM.mov` with a narrow NBSP; copy it with `find … -name '…'` / a glob, never a
  hand-typed path (the typed space won't match).
- **Massive duplication** — without the md5 dedupe you'll transcribe the same voice note many times.
- **Host `ffmpeg` may lack `drawtext`** and other filters — keep the recovery steps to plain
  extract/transcode; don't assume the full filter set.
- **Validation:** a recovery is proven when the recovered `.opus` durations match the chat labels and
  the photo dimensions exceed anything the recording could contain (proof it's the original, not a
  crop). Treat all recovered files as client PII: gitignore, never commit.
