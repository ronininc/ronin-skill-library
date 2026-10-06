```yaml
name: skill-matchmaker
description: "Inventory a codebase (languages, frameworks, APIs, external services, engines) and match that inventory against the installed skill index and public skill marketplaces, then report what is missing, what is duplicated, and which candidates pass a license check. Use when pointed at a repo and asked what skills it needs, when auditing the skill index for gaps or duplicates, or before authoring a new skill (\"does one already exist?\"). Reports only; never installs anything without an explicit yes."
path: ~/workspace/skills/skill-matchmaker/SKILL.md
source: authored in-house in the claude.ai chat "App Remake Belt skill" (2026-10-03/04); no third-party code
date_added: 2026-10-06
category: solomon-self-extension
```
SKILL.md is byte-for-byte the copy shipped in TSS `.claude/skills/skill-matchmaker/` (TSS#286, commit cfcde75a4). Reports only: it never installs a skill without an explicit yes.
