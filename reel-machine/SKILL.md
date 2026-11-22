---
name: reel-machine
description: Turn one topic into a finished 9:16 short-form reel (Reels/TikTok/Shorts) for $0 on the operator's Mac — local-LLM script under the headline doctrine, an approval gate bound to the script's hash, Kokoro narration, captions from the approved words, footage from the business's own media library (else generated cards), ffmpeg assembly, a hash-chained Intent→Evidence→Governance→Decision→Authorization→Audit ledger per stage, then docked into the CRM's Clipper review → Content Studio draft. Clean-room rebuild of MoneyPrinterTurbo (MIT, harry0703) with every paid API (Kimi, ElevenLabs, MiniMax, Pexels, edge-tts…) left off. Use for "make a reel about X", "short-form video for a client", "reels as a service", "faceless video", "turn this topic into a TikTok", or the Content Studio reel lane. Never posts; never renders an unapproved script; never clones a voice.
---

# Reel Machine

Lives in the CRM repo at `tools/reel-machine/` (ronininc/ronininc-crm). Read its `README.md` and `AUDIT.md` first.

## The loop

1. `node tools/reel-machine/reel.mjs new "<topic>" [--client "<business>"]` — the local writer (Ollama, loopback only)
   drafts 5–9 lines with footage terms; the doctrine checks it and sends failures back to the writer (≤3 drafts).
   Or the operator writes it: `--file script.json`.
2. **Show the operator the script.** Only their word approves it:
   `reel.mjs approve <job> --by <their name> --said "<their words>"`. An agent can never approve a reel that can go out.
   Any edit after approval voids it (the approval is the script's sha256).
3. `reel.mjs render <job>` — Kokoro (`af_heart`) per line → captions from the approved text, timed per voiced line, with
   whisper as the check (≥85% of words heard) → footage from `REEL_LIBRARY` (else a generated card) → 1080x1920 MP4.
4. The operator watches it. Then `reel.mjs dock <job>` → Clipper review in the CRM → approve → Content Studio draft.
   Nothing posts until they schedule it there.

## Hard rules

- $0: no paid TTS, LLM, stock or video API. `reel.mjs providers` lists what ships disabled and why. Turning one on needs
  the operator's tap for that service by name.
- Voice: `af_heart` (Solomon's approved Kokoro voice, the only pack installed). No cloning without explicit say-so.
- Business media only: libraries in `~/Library`, hidden folders, or outside home are refused.
- Headline doctrine: explainable outcomes (no guarantees; a number carries its reason), comparisons against closed
  flagships only, no emails/phone numbers.
- A `--sandbox` job is watermarked "SANDBOX · NOT FOR POSTING" and can never dock. Never present one as finished work.
- No library media = generated title cards: honest but plain. Say so; ask for B-roll before calling it client-ready.

## Selling it

Short-form video as a service for local businesses (per reel or monthly retainer): their footage, their approved words,
an audit trail per reel, no software for them to install. See `AUDIT.md` for the upstream pain points it fixes.
