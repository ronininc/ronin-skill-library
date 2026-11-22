# Repo Access & PR Flow

The driver needs to read files, run proofs, and (with approval) commit + open a PR. Proofs require a
real clone with Node — reading alone is not enough to produce verified results. Pick the highest-
capability path available and state which one you're on.

## Path A — local clone in a mounted folder (preferred, enables verification)

If a working folder is connected, use `bash` directly. If the repo isn't there yet, request a folder
(`request_cowork_directory`) and clone into it.

```bash
cd <mounted-folder>
git clone https://github.com/ronininc/TSS.git   # or use existing clone
cd TSS
npm install && npm --prefix server install && npm --prefix app install
npm run build:server && npm run build:app
```

Now every `solomon:*` proof runs for real, and git is available for branching/committing.

Note: the isolated shell may not have network/credentials for github.com (a bare clone can fail with
an HTTP 403 from the proxy). If so, the clone must live in the user's own environment/folder where
their git credentials apply; drive it there, or have the operator clone once and mount it.

## Path B — GitHub MCP tools (if connected)

If GitHub MCP tools are available this session, use them to read files, create a branch, commit files,
and open the PR without shell git. (As of this skill's authoring the GitHub connector was NOT connected
in-session — verify before relying on it. If unconnected, suggest connecting it, or use Path A.)

## Path C — authenticated browser only (read/plan, cannot verify)

The authenticated browser tab can read repo files via raw URLs
(`https://github.com/ronininc/TSS/raw/<branch>/<path>`) and inspect the live site. It cannot run
proofs or commit. On this path you can build the worklist and read code, but you must report proof
statuses as UNVERIFIED — do not claim PASS you didn't run.

## Branch + commit discipline

Follow `solomon-repo-hygiene`. One coherent change per branch/PR.

```bash
git checkout -b proof/persona-router-invariance
# add ONLY source + package.json; never .test-runtime/, dist/, runtime/, media, secrets
git add scripts/solomon-persona-router-invariance-proof.ts package.json
git status && git diff --staged --stat   # verify no artifacts snuck in
git commit -m "proof: add persona-router invariance proof (closes README blocker)"
```

## Opening the PR (approval required before push)

Pushing and opening a PR are side-effectful — get an explicit operator yes first, then:

- **With `gh` CLI (Path A, if installed & authed):**
  ```bash
  git push -u origin proof/persona-router-invariance
  gh pr create --title "Add Persona Router invariance proof" \
    --body "Closes the README blocker 'Persona Router invariance proof is missing'. Advances Priority 1 (repository integrity / governance proofs). Proof runs via solomon:persona-router-invariance-proof; report at .test-runtime/proofs/persona-router-invariance-proof.json. Verified it fails when the invariant is broken."
  ```
- **With GitHub MCP tools (Path B):** create the branch/commit/PR through those tools with the same
  title/body.
- **Browser only (Path C):** you cannot open a PR programmatically; hand the operator the branch name,
  file diffs, and a ready-to-paste PR title/body.

## PR body checklist (Solomon doctrine)

Every PR should state: which flagship priority it advances; which proof backs it (and that the proof
was seen to pass AND to fail when broken); that no generated artifacts are included; and the truthful
status change it enables in the README (linking `solomon-readme-sync`). A PR that adds a capability
without a proof is incomplete — say so rather than merging optimistically.
