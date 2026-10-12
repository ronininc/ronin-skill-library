# Briefing Animation

Generate validated pickup briefing character loops from structured page directions. Character animation for content.

## When to use
Creating animated character briefings for content — reels, presentations, PWA onboarding. Takes an avatar image and page specs, outputs a character animation loop.

## Commands
Run via `muse.exec`:
- `pickup-briefing-animation --request <path_to_json>` — generate from JSON request

The JSON request contains:
- `avatar_image` — path to the character/avatar image
- Ordered page specifications — each page's directions

## Rules
- Input JSON must be valid. The tool validates before generating.
- Output goes to the content engine for use in reels and presentations.
- Keep avatar images in the noir brand style.
