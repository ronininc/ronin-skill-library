---
name: churn
description: Weekly disk churn sweep for this Mac. Moves stale git worktrees, leaked temp folders, half-finished git downloads and runaway logs to the Trash (never deletes), flags crash-looping log writers and fast-growing folders, and can merge duplicate files into APFS clones. Use when the disk is filling up ("disk full", "free up space", "no space left", "clean up worktrees", "run churn"), for the weekly Tuesday 3 PM scheduled run, and whenever you finish work in a worktree you created.
---

# churn

The disk on this 8 GB / 460 GB Mac fills up from **churn**: agents create a git worktree per task (each with its own node_modules and builds) and never remove it, crash-looping services grow their logs without limit, and interrupted downloads leave temp files behind. TSS went from 37 to 89 worktrees in four days in October 2026, and free space dropped from 98 GB to 15 GB.

This skill sweeps the churn and keeps everything recoverable: items go through `/usr/bin/trash`, so Finder's **Put Back** works until the operator empties the Trash. Agents never empty the Trash and never `rm` anything.

## Run it

```bash
python3 ~/.Codex/skills/churn/scripts/churn.py --growth            # dry run: report only
python3 ~/.Codex/skills/churn/scripts/churn.py --growth --apply    # move to Trash, write the report
```

Options: `--min-age-hours 24` (worktree idle time), `--log-max-mb 200`.

The report goes to stdout and `~/Library/Logs/churn/<date>.md`. A manifest for restoring worktrees goes to `<date>.tsv`. `sizes.json` holds last week's folder sizes for the growth check.

Always dry-run first, read the report, then apply.

## What it moves, and the checks each item must pass

| Kind | Moved to Trash when |
|---|---|
| **Worktree** (linked, never a main checkout) | No uncommitted or untracked files. Every commit is on a remote. No process has a file or cwd inside it (one `lsof -Fpcn` snapshot, taken before anything is walked; indexers and walkers are ignored). No activity for 24 h (last commit and index mtime). No unique ignored `.env`, `.dev.vars`, `*.db`, `*.key` or `*.pem` that differs from the main checkout. No built installer (`.deb`, `.dmg`, `.AppImage`, `.pkg`) in `dist/`. Not protected. Afterwards: `git worktree prune`. |
| **Temp** | `$TMPDIR/_MEI*` (PyInstaller leaks), `solomon-reloc-*`, and stale Chrome `code_sign_clone.*` copies. Each must be older than 1 h and not open. |
| **Git garbage** | `.git/objects/pack/tmp_*` left by interrupted fetches, older than 24 h and not open. |
| **Log** | Any `*.log` over 200 MB. If nothing holds it open, it moves to the Trash. If a process holds it open, a gzip copy goes to the Trash and the file is truncated in place. Moving a held-open file frees nothing until its writer closes it. |

**Protected (never swept):**
- `/Applications`, `~/Applications`
- `~/solomon-integrate-wt` (the live Solomon build checkout)
- `~/.codex/worktrees/dots-*` (the Codex bots)
- `~/solomon-prebench-state-*` (may hold the only copy of an older vault seal key)
- `~/Library/Application Support`
- `~/.solomon`

To add more, put one path prefix per line in `~/.config/churn/keep.txt`.

## After the sweep: fix roots, don't just mop

- **"Needs a fix" lines are crash loops.** The sweep only removes the log. Spawn a separate task to fix the writer, with the error line, the log path, and "add rotation plus restart backoff". Example from 10-10: the lead engine's `no such column: runs.credit_refunded`.
- **"Grew more than 2 GB" lines** are new space hogs: knowledge-base downloads, iPhone backups, model pulls. Report them with a one-line recommendation. Never trash user data, app data, backups or the knowledge base. Those are the operator's call.
- **Kept worktrees** with uncommitted work or unpushed commits are someone's live work. List the counts; don't touch them.

## Duplicates (monthly, or when free space is under 20 GB)

Most duplicates are the same libraries, models and Electron builds copied into every worktree. Deleting one copy breaks that project. Instead, merge identical files into APFS clones: every path stays, and the bytes are stored once.

```bash
D=~/Library/Logs/churn
python3 ~/.Codex/skills/churn/scripts/dupes.py ~ /Applications /opt /Users/Shared > $D/dupes.json 2> $D/dupes.log   # ~20 min
python3 ~/.Codex/skills/churn/scripts/clonededupe.py $D/dupes.json $D/clone-journal.tsv                              # plan
python3 ~/.Codex/skills/churn/scripts/clonededupe.py $D/dupes.json $D/clone-journal.tsv --apply                      # do it
```

`clonededupe.py` byte-compares each file against its keeper right before swapping, and keeps the file's own mode, timestamps and xattrs. It skips files that are open, hard-linked, changed in the last 2 h, databases or logs, `.git`, and its protected roots: apps, app data, iPhone backups, the knowledge base, Messages, and system containers.

## Gotchas learned the hard way

- **`du` lies on APFS clones.** On 10-06, a Chrome clone folder read 31 GB but held 1.5 GB. A Trash that reads 66 GB freed 38 GB. Report `du` numbers as "up to", and measure real reclaim with `df` after the Trash is emptied.
- **Parse `lsof` with `-Fn`.** `awk '{print $NF}'` breaks on paths with spaces, such as `Google Chrome.app`.
- **Your own `du`, `find` or scan holds files open while it walks.** If a candidate looks busy only during a scan, recheck after the scan finishes.
- **Other programs can keep their data inside a folder through a link or a setting, with nothing open.** On 10-12 we found Ollama's model store had lived in `solomon-desktop`, through the `~/.ollama/models` link and `launchctl setenv OLLAMA_MODELS`. Trashing that folder wiped 13 GB of models once the Trash was emptied. Before moving any app-data folder, also run `find ~ -maxdepth 4 -type l -lname '*<folder>*'` and `launchctl getenv` for paths into it.
- **Apps can depend on each other.** On 10-10 the installed Kingmaker.app still ran on `/Applications/Solomon.app`'s engine. Never move an app or its data because it "looks unused"; check `ps` and `lsof` for every process that uses it. Apps are protected for that reason.

## When you finish work in a worktree you created

This is what prevents the churn. Once your branch is pushed (or merged) and nothing is running in it:

```bash
/usr/bin/trash <worktree-path> && git -C <main-repo> worktree prune
```

Don't leave sibling checkouts (`~/Projects/<repo>-<task>`) behind "for later". The branch keeps the work, and `git worktree add <path> <branch>` brings the folder back in seconds.
