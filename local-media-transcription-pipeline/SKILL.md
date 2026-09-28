---
name: local-media-transcription-pipeline
description: >-
  Turn any pile of video/audio into text transcripts entirely ON THIS MACHINE — no upload, no
  cloud STT, zero per-minute cost — with a resumable ffmpeg → whisper.cpp (Metal) batch. ffmpeg
  strips a 16k mono WAV, whisper-cli (large-v3-turbo, quantized) writes a .txt + timestamped .json,
  and a done-file skip makes the whole run re-startable after a crash or a full disk. Use WHENEVER
  the task is "transcribe these recordings / calls / voice notes / videos", "get the text out of
  this .mov/.mp3/.m4a", "what did they say in this clip", "mine tool/OSS/name mentions from footage",
  or any ingest that must stay private (client PII, sales calls, voice memos) and never leave the box.
  COMPLEMENTS local-first-inference-ladder (that ladder is LLM reasoning/text-gen; THIS is speech→text
  and hands its transcripts to it) and feeds fact-preference-memory / any evidence store as grounded,
  timestamped source. Guardrail: whisper MANGLES proper nouns — never present an extracted name as
  clean; fuzzy-match to a known dictionary, keep the raw quote+timestamp as evidence, mark uncertain
  low-confidence for operator confirmation. Do NOT use for a screen recording with no audio track
  (use desktop-app-cache-media-recovery + screen-recording-ocr-text-recovery), nor for live/streaming
  STT (this is a batch of files at rest).
---

# Local Media Transcription Pipeline

Fully sovereign speech-to-text on an Apple-Silicon Mac (proven on M3 / 8 GB): drop media in a
folder, get `.txt` + timestamped `.json` transcripts out, nothing uploaded. It is the *audio* leg
of every private ingest — mining tool/OSS mentions from videos, transcribing sales calls, turning
voice notes into text. It composes with `local-first-inference-ladder` (send the transcript to the
ladder to summarize/extract) and with any memory/evidence store (the `.json` carries timestamps, so
every claim keeps a citable `raw quote @ mm:ss`).

## Reference implementation — lift the exact code

`/Users/robbiebrown/ronin-ingest/transcribe.sh` — a complete, working, resumable batch:

- **Model default & guard** — `transcribe.sh:7` (`ggml-large-v3-turbo-q5_0.bin`, overridable via
  `$WHISPER_MODEL`) and `transcribe.sh:12` (exit if the model file is missing).
- **Input glob (all common A/V extensions, case-insensitive)** — `transcribe.sh:14-16`
  (`shopt -s nullglob nocaseglob`; `.mp4 .mov .mkv .webm .m4v .avi .mp3 .wav .m4a .aac .flac .ogg`).
- **Safe output basename** — `transcribe.sh:26` (`tr ' /:' '___'` so spaces/slashes/colons in the
  source name can't break the output path).
- **Resumable skip (THE INVARIANT)** — `transcribe.sh:28` (`[[ -s "$txt" ]] && skip`): a non-empty
  transcript = done, so a re-run after a crash / disk-full / Ctrl-C picks up exactly where it stopped
  and never re-burns compute on finished files.
- **Audio extract** — `transcribe.sh:31`: `ffmpeg -v error -y -i "$f" -vn -ar 16000 -ac 1 "$wav"`
  (16 kHz mono WAV — whisper.cpp's native input; `-vn` drops video).
- **Transcribe** — `transcribe.sh:34`: `whisper-cli -m "$MODEL" -f "$wav" -otxt -oj -of "$out" -t 4`
  (`-otxt` plain text, `-oj` JSON with timestamps, `-t 4` threads).
- **Cleanup + word count** — `transcribe.sh:37-38` (delete the scratch WAV; `wc -w` for a cheap
  sanity signal that the file actually produced words).

One-off (no batch): `ffmpeg -v error -y -i IN -vn -ar 16000 -ac 1 out.wav` then
`whisper-cli -m MODEL -f out.wav -otxt -oj -of OUT -t 4`. Add `-l auto` when the language is unknown.

## How to reapply — the wiring

1. **Stack (all local):** `ffmpeg` for extraction; `whisper.cpp` (brew) giving the `whisper-cli`
   binary, Metal-accelerated. Do NOT reach for mlx-whisper / faster-whisper on a too-new Python
   (3.14 here has no reliable wheels) — the C++ binary sidesteps the Python problem entirely.
2. **Model:** `~/.cache/whisper.cpp/ggml-large-v3-turbo-q5_0.bin` (~574 MB) is the accuracy/RAM
   sweet spot for proper nouns on a tight box; `base`/`small.en` are lighter fallbacks.
3. **Layout:** `videos/` in, `transcripts/` out (`<safe>.txt` + `<safe>.json`), a scratch `work/`
   for the throwaway WAV, and `errors.log` / `whisper.log` for the two failure surfaces.
4. **Run:** drop files, run the script; it prints `[i/n]`, skips done, tallies `ok`/`fail`.
5. **THE INVARIANT again:** correctness of a re-run depends only on "non-empty `.txt` == done".
   Keep the WAV in scratch and delete it after success so a half-written WAV never masquerades as
   progress, and never treat an empty `.txt` as done.

## Gotchas — real, from the pipeline

- **Proper nouns are unreliable.** Measured failure: "Ollama" → "Alima". When harvesting names
  (tools, people, brands), fuzzy-match against a known dictionary, keep `raw quote + timestamp` as
  evidence, and mark anything uncertain low-confidence for the operator. Never invent a clean name.
- **Disk is the silent killer.** On an 8 GB / tight-disk box (seen at ~5.7 GB free), many/large
  videos can exhaust space mid-run; the resumable skip is what makes "clear space, re-run" safe.
- **whisper.cpp cold-start on Metal is slow after a rebuild** (first-run shader compile). For a
  batch it amortizes; for a latency-sensitive single call, warm it first.
- **Validation:** the run is proven by the emitted `transcripts/*.json` (timestamps present) and the
  per-file word count; a `fail` with an empty `.txt` means look in `whisper.log` / `errors.log`.
- **PII:** transcripts of calls/voice notes contain names, addresses, phones — write them to a
  gitignored location and never commit. (The sibling sales-call variant enforces exactly this.)
