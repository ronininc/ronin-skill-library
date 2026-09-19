---
name: skill-harvest
description: >-
  Extract every reusable, sellable capability out of a finished build (or a whole portfolio of repos)
  into standalone SKILL.md files in the Ronin skill library — the repeatable strip→diff→author→verify
  pipeline, so each build auto-contributes and you never hand-grind it again. Use WHENEVER a build ships
  or you want to mine code into skills: "harvest skills from this", "strip this repo/build into skills",
  "extract the reusable IP", "add this build to the library", "run the harvest", "capture what we built",
  "turn my builds into a mix-and-match inventory", or as the CLOSING step of any build. Works on one repo
  or every repo you own. EFFICIENT BY DESIGN — it triages first (a repo that's merely an instance of an
  existing skill contributes nothing) and only deep-strips repos with genuinely net-new capability, always
  deduped against the current library so it never re-authors what you already have. Patterns/techniques
  only — never client data. Pairs with the composition index (recipes) it keeps up to date.
---

# Skill Harvest

The standing process that turns builds into owned, reusable skills — run it at the end of any build, or
across the whole portfolio. It never duplicates what's already in the library.

## The pipeline (six steps)
1. **Snapshot the library** — `ls ~/.claude/skills` for the exact current skill names. The diff is only as
   good as this snapshot; nothing already here gets re-authored.
2. **Inventory the target(s)** — one repo or all. Per repo get stack + size + last commit
   (`find … -name .git`; check `wrangler.*`, `worker/`, `public/admin`, source file count). Cheap and fast.
3. **Triage — the efficiency gate.** Most builds are INSTANCES of skills you already own (a restaurant
   site = website-build-standard + commerce-spine; a thin client Worker = cf-identity + cf-forms). Those
   yield NOTHING net-new — confirm-and-skip them in a batch (spot-check, don't deep-read). Only a repo with
   a novel subsystem (a new connector, a new engine, an unusual UI) earns a deep strip.
4. **Deep-strip + diff + author — in ONE pass per novel repo** (the efficiency win over running strip and
   author as two separate workflows). For each novel repo, an agent reads the subsystems, lists
   capabilities, marks each `net_new` vs the snapshot, and immediately writes a SKILL.md for every net-new
   one. Author-in-the-same-pass roughly halves the work.
5. **Verify on disk + regenerate the index** — never trust an agent's word: confirm each SKILL.md exists
   with real content (`wc -c`), then slot the new skills into the composition index recipes.
6. **Back up to the private GitHub repo** — the harvest isn't finished until the library is pushed. FIRST
   re-run a secret/PII scan over the new/changed SKILL.md files (grep for `sk-`/`sk-ant`, `AKIA`, `ghp_`,
   `-----BEGIN`, `xoxb-`, `AIza`, known client phones/emails, long hardcoded hex/base64) — pushing
   distributes the content even to a PRIVATE repo, so never push unscanned. Then, in `~/.claude/skills`:
   `git add -A && git commit -m "<what this harvest added>" && git push` — the remote `origin` is
   **github.com/ronininc/ronin-skill-library (PRIVATE)**. Prefix with `SOLOMON_GO=1` if the egress guard
   blocks the push. NO Claude/AI attribution in the commit message (house no-signature rule). The remote
   MUST stay private — never add or push to a public remote; client-derived patterns live here.

## How to run it (workflow template)
Fan out with the Workflow tool: **one agent per NOVEL repo** (deep-strip + author + verify), **one triage
agent** to confirm the thin instance-repos as a batch, and **one gap-scan agent** per big repo that was
already partly harvested ("what did we miss / what's new since?"). Give every agent: the library snapshot
(for dedup), the SKILL.md house format below, and the rule to author net-new ONLY. Cap the fan-out at the
novel repos — passing 40 thin site-instances would be pure waste, which is exactly what triage prevents.
Use `agentType: 'general-purpose'` so agents can Write.

Each authoring agent writes `~/.claude/skills/<kebab-name>/SKILL.md`:
```
---
name: <kebab-name>
description: >- <what it does + explicit "Use WHENEVER…" triggers + which existing skill it COMPLEMENTS>
---
# <Title>
- What it is / when to use / what it composes with
- Reference implementation — exact source file:line (so a future build lifts the proven code)
- How to reapply — migration/schema, handler(s), routes/cron wiring, UI
- Gotchas — real pitfalls from the code + any proof
```

## Rules (non-negotiable)
- **Patterns/techniques ONLY** — never copy or reference a client's data, names, keys, or records.
- **Complement, don't duplicate** — most new skills EXTEND an existing one; name it and capture only the delta.
- **Diff before you author** — snapshot the library first; a name that already exists is a signal you're about to duplicate, not extend.
- **Verify on disk** — the harvest isn't done until every claimed SKILL.md is confirmed present with content.
- **Flag disconnected code** — if a capability ships unwired in the source, the skill must say so and include the bindings it needs.
- **Respect the boundary** — personal repos (games) and the private Solomon/TSS system are NOT auto-harvested into the business/client-CRM inventory; surface them and let the operator decide, never dump them in.
- **Instances contribute nothing** — a repo built FROM the skills yields no new skills; confirm-and-skip.

## When to fire
- The closing step of ANY build ("we shipped X" → harvest X, then update the composition index).
- A portfolio sweep ("harvest every repo I have").
- Any "strip this into skills / capture the IP / grow the inventory" request.
