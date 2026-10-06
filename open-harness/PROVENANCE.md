```yaml
name: open-harness
description: "Run routine coding and agent work on free/open models through a local MIT-licensed harness (Hermes Agent, OpenCode) under Solomon's governance — own the weights, keep data private, demote Claude/Codex to hard tasks only. Trigger when Robbie wants $0 coding capacity or a Claude-independent execution path."
path: ~/workspace/skills/open-harness/SKILL.md
source: Instagram reel @tysn.dev https://www.instagram.com/reel/Dch57p_iA87/, distilled by Muse
date_added: 2026-10-05
category: solomon-capability
```
SKILL.md is the full text from the 2026-10-05 build order, unedited (plus a final newline); Muse's file at that path was not on the host. Also shipped in TSS `.claude/skills/open-harness/`, and wired to the Solomon Model Router in TSS `tools/model-router` (behavior spec: `docs/open-harness/behavior-spec.md`; `smr policy preset open-harness`, `smr task run`, `smr bench open-harness`).

Fact check, 2026-10-06, recorded here because the skill text is kept verbatim: FreeLLMAPI is not a closed service. github.com/tashfeenahmed/freellmapi is MIT and self-hosted (docker compose on 127.0.0.1:3001); by default it syncs a model catalog from freellmapi.co, which should be turned off to keep the no-telemetry rule. The router treats it as an untrusted aggregator either way: no request reaches it without a per-batch tap.
