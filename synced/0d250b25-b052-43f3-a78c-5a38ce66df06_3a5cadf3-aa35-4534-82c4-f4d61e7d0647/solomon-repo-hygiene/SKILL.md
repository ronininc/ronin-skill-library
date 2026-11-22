---
name: solomon-repo-hygiene
description: >-
  Keep the Solomon / TSS repository clean-clone healthy — never commit generated artifacts, keep
  the working tree buildable from a fresh clone with no manual repair, and protect Priority 1
  (Repository Integrity). Use this whenever you are committing, staging, reviewing a diff, opening
  a PR, adding a .gitignore entry, or investigating why a clean clone fails to install/build/package
  in the ronininc/TSS repo. Trigger on "commit this", "open a PR", "why did a generated file get
  committed", "clean up the repo", "clean-install failing", "what should be gitignored", or "does
  this change keep the clone reproducible". Repository integrity always takes precedence over
  feature velocity — a committed build artifact can silently break every other engineer's clone.
---

# Solomon Repo Hygiene

Priority 1 of the August 2 flagship is Repository Integrity: every clean clone must install,
restore dependencies, build without manual intervention, pass governance proofs, package, and
launch. The fastest way to break that for everyone is to commit a generated artifact or a local
runtime file. This skill exists to make each commit preserve a reproducible clone.

The proof that backs this is `npm run solomon:validate:clean-install`; treat this skill as the
human discipline that keeps that proof green.

## Never commit generated artifacts

These are build outputs, local runtime state, or secrets — they must never enter a commit. If any
are staged, unstage them and add to `.gitignore`:

```
node_modules/
dist/
build/
desktop/dist/
desktop/build/
.test-runtime/
runtime/
data/
db/
*.db
*.sqlite
*.env
*.log
# installer + release outputs
*.exe
*.msi
Solomon-Setup-*
solomon-build.json
solomon-release-metadata.json
ronininc_solomon_*_cloudflare_deploy.zip
release zip files and release metadata
```

This mirrors the repo's own Repository Rules. Evidence media from the verifier skills
(`.test-runtime/evidence/…`) also stays out — it lives under `.test-runtime/`, which is already
excluded.

## Pre-commit checklist

Before every commit:

1. `git status` and `git diff --staged --stat` — scan for anything in the never-commit list.
2. Confirm no large binaries snuck in: `git diff --staged --stat` size column, and
   `git ls-files -s | ` review for unexpected paths. A multi-MB blob in a diff is almost always a
   mistaken artifact.
3. Confirm no secrets: no `*.env`, no API keys, no tokens, no signing certs.
4. If you touched build/scripts, mentally verify a **fresh clone** would still build: did you add a
   file that only exists locally (under `runtime/`, `data/`, `.test-runtime/`) that the code now
   depends on? If so, the clean-install proof will fail. Move it into tracked source or generate it
   at build time.
5. Run (or plan to run) `npm run solomon:validate:clean-install` for anything touching
   build/packaging/deps.

## If a generated file was already committed

1. Remove it from tracking without deleting locally: `git rm --cached <path>`.
2. Add the pattern to `.gitignore`.
3. Commit the removal. For secrets or large blobs already in history, flag to the operator that
   history rewriting (git filter-repo / BFG) and secret rotation may be needed — do not rewrite
   shared history unilaterally.

## PR discipline (Solomon doctrine)

- Every branch/PR should move at least one flagship priority forward (Repository Integrity, Native
  Voice, Persistent Project Twins, Interactive Build Trees, Production Hardening). State which in
  the PR description.
- A PR that adds a capability should also add or update its proof (see `solomon-proof-authoring`)
  and, if it changes a README claim, sync the status (`solomon-readme-sync`). A capability with no
  proof cannot be claimed.
- Keep diffs reviewable: no bundled artifacts, no reformat-the-world noise mixed with logic.

## Clean-clone integrity check (do this to reproduce a report)

To verify the tree truly builds from scratch:

```bash
git clone <repo> /tmp/tss-cleanclone && cd /tmp/tss-cleanclone
npm install && npm --prefix server install && npm --prefix app install
npm run build:server && npm run build:app
npm run solomon:validate:clean-install
```

If this fails on a fresh clone but works in your working tree, something the build needs is
untracked (or something committed shouldn't be). That gap is the bug — fix it at the source, and
never "make it work" by committing the generated output.

## Reporting

State clean-clone status plainly: `CLEAN-CLONE: PASS` or `CLEAN-CLONE: FAIL (<reason>: e.g. build
depends on untracked runtime/config.json)`. If you unstaged or untracked artifacts, list exactly
what and why, so the operator can see the tree is protected rather than trusting it silently.
