```yaml
name: universal-modder
description: "Mod a PC game the operator owns, from the idea to working in the real game and recorded. Router over 11 upstream skills: recon, reverse engineering, fal assets, asset pipeline, game automation, mashups, web research, field notes, showcase video, publishing."
path: ~/.claude/skills/universal-modder/SKILL.md
source: https://github.com/rehan-remade/universal-modder @ 6c02e77d9088ecb1a7d9970572d8ca5387e7cb9e (MIT)
date_added: 2026-10-07
category: game-modding
```
The top-level SKILL.md is a Ronin-authored router; `skills/`, `LICENSE` and `UPSTREAM_AGENTS.md` are byte-for-byte upstream. VENDORED.md lists what was not copied (the `um` CLI, `knowledge/`, docs, examples, the plugin hook and the fal MCP config) and the pinned `um` install line. Also shipped in TSS `.claude/skills/universal-modder/`, where Solomon's skill library puts every skill in the bundle on Godot first (ronininc/TSS#331).
