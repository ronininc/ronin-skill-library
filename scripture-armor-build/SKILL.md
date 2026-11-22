---
name: scripture-armor-build
description: >-
  House rule for EVERY build: run Scripture Armor (ronininc/scripture-armor, installed at ~/scripture-armor
  with its vault daemon always on) as the security gate on the way out. Use this whenever work is about to
  SHIP or LEAVE THE MACHINE — opening or updating a PR, deploying (wrangler deploy, cf-deploy, Pages,
  "go live", "push it", "ship it"), cutting a release or zip, handing code to a client or another dev —
  and whenever OUTSIDE CODE comes IN: adding a dependency, script, installer, snippet or repo someone sent,
  or about to run anything downloaded ("run this script", "curl … | sh", "install this tool"). Also use it
  whenever DATA leaves the machine: a database export or D1 backup, a customer/member list, a CSV for a
  client, a secrets or .env handoff, an archive of a repo — those get SEALED with the armor first. Trigger on
  "scripture armor", "armor it", "seal this", "scan before we ship", "security check", "is this safe to run".
  Applies on top of the other build standards (website-build-standard, crm-build-standard, cf-deploy,
  service-business-website…): they decide what to build, this decides what may leave and what may come in.
---

# Scripture Armor — the build gate

**What it is (plain words first).** Scripture Armor is the house security layer: a *closed loop* around this
machine. Anything sealed by it becomes a package of unreadable glyphs that only this machine's vault can open,
and only after the owner approves (ChaCha20-Poly1305 encryption with a hybrid X25519 + ML-KEM key seal under the
glyph skin; the glyphs hide, the math locks). The vault records a fingerprint (hash) of everything that leaves; if
something comes back that doesn't match, it refuses it and logs it as a beacon. And **nothing gets sealed
unscanned**: its scanner checks code for risky behavior before it is wrapped.

For builds that means two gates — **scan what ships or comes in, seal what leaves** — plus a few hard lines.

Source: `ronininc/scripture-armor` (README = the doctrine; `FORMAT.md`; `SHIP-SHEET.md`). Installed copy:
`~/scripture-armor` (override with `SCRIPTURE_ARMOR_HOME`). Node ≥ 24 is required.

## 0. Preflight (once per session that ships)

```bash
node ~/scripture-armor/vaultd.mjs status
git -C ~/scripture-armor fetch -q && git -C ~/scripture-armor rev-list --count HEAD..origin/main   # 0 = up to date
```

- `"ok":true` = the vault daemon is up. Read `label` for this copy's name. If it isn't up, say so in one line —
  don't start, install, or restart it yourself.
- If the count is above 0, tell the owner the installed armor is behind (`git -C ~/scripture-armor log --oneline
  HEAD..origin/main` says by what) — don't pull, update or restart the daemon without a yes.
- `terms_accepted_by_owner: false` is the owner's business (see hard lines). Scanning and sealing still work.

## 1. Gate 1 — scan before it ships, and before outside code runs

```bash
node ~/.Codex/skills/scripture-armor-build/scripts/armor-scan.mjs            # what this branch changed (vs origin/main) + uncommitted + untracked
node ~/.Codex/skills/scripture-armor-build/scripts/armor-scan.mjs --base <ref>
node ~/.Codex/skills/scripture-armor-build/scripts/armor-scan.mjs <files or folders>
node ~/.Codex/skills/scripture-armor-build/scripts/armor-scan.mjs … --json
```

The helper runs the armor's own `scan.mjs` on every file, also scans the inline `<script>` blocks of HTML pages
(the scanner itself treats HTML as data), and gives one verdict. Exit `0` = clean, `1` = needs the owner.

**When:** before every PR, deploy, release or hand-off (scan the changes); and before running, installing or
vendoring anything that came from outside — a downloaded script, an installer, a repo or snippet someone sent,
a new dependency's source (scan the folder). Never run `curl … | sh`-style installs: download, scan, read, then
ask.

**Reading the result:**
- **NEEDS THE OWNER** (high / critical, an unscannable binary, or a scanner error) → don't ship and don't run it.
  Fix it, or explain each line to the owner in plain words and let them decide. A finding that is genuinely
  intended (e.g. a CLI that really shells out) is the owner's call, not yours.
- **Notes** (medium / low, and known over-matches) → mention them; not blocking.
- **Clean** → say so, with the honest scope (next point).
- Put one line in the PR description / wrap-up: `Scripture Armor scan: 17 checked (13 code, 4 data) — clean, 3 notes`.

**What the scan is and isn't.** It is a pattern scan for *risky behavior*: code run from strings (`eval`,
`new Function`, `vm`), shell commands built from strings, pipe-to-shell downloads, hidden persistence
(cron/launchd/systemd), camera/mic/screen access, removal resistance. It is **not** a full vulnerability audit —
no SQL injection, XSS, auth or business-logic checks — so never call a build "secure" because the scan is clean.
The armor's own doctrine: *the scanner's verdict is evidence, not a gate on meaning.*

**Known over-match (handled by the helper):** the scanner runs every language's rules on every file, and its
Python `eval/exec(` rule also fires on JavaScript method calls like `regex.exec(…)` and `db.exec(…)`. The helper
shows those as notes with the reason instead of blocking; anything touching `child_process`/`spawn`/`shell`
keeps its full severity. (Upstream fix belongs in `scan.mjs`'s `src-py-eval-exec` pattern.)

## 2. Gate 2 — seal what leaves the machine

**Seal before it leaves:** database exports and D1 backups, customer / member / lead lists, anything with
personal data, CSVs or spreadsheets for a client, `.env` / keys / tokens being handed to another machine or
person, archives of a client repo, logs with customer data.

```bash
node ~/scripture-armor/armor.mjs wrap <file> --to mac-self              # → <file>.scripture
node ~/scripture-armor/armor.mjs wrap-repo <dir> --to mac-self          # → <dir>.scripture-repo/
node ~/scripture-armor/armor.mjs verify <dir>.scripture-repo            # checks every package, opens nothing
node ~/scripture-armor/armor.mjs inspect <file>.scripture               # frame, signature, scan verdict — opens nothing
```

- `mac-self` is this Mac's own entry in the address book (sealed to the loop's own vault). Another recipient must
  already be trusted (`armor.mjs trust <label> <block>`, done by the owner with the pairing code compared
  out-of-band) — never add trust yourself.
- `wrap` scans first and **refuses** to seal code with a critical finding (it writes a sealed scan report
  instead). That refusal is the gate working; report it, don't work around it.
- Sealing does **not** remove the original. Remove plaintext copies *you* created (an export you just pulled), and
  never commit a plaintext export or secret — commit or send the `.scripture` package. Don't delete files you
  didn't create; ask.
- A `.scripture` package is safe to store or send anywhere: it is inert outside the loop.

**Opening a sealed package** goes only through the vault daemon, and the **owner approves on this machine**:
`armor.mjs unwrap-repo … --into <dir>` (or the daemon's `unwrap`) prints `pending approval: <canary>`; the owner
runs `node ~/scripture-armor/vaultd.mjs approve --id <request-id>` within the window (120 s default). You may
start the request and tell the owner what's waiting; you never approve it.

## 3. Hard lines (never, even if asked mid-task — send the owner to do it)

- **Never accept the activation terms** — not by typing `ACCEPT` into `launch.mjs`, not via the daemon's
  `accept-terms`. The armor's terms say agents are presented them too; that is a request for the owner's
  decision, not something an agent signs. Show the owner, let them accept.
- **Never approve a vault request** (`vaultd.mjs approve`), never batch-approve, never script approvals.
- **Never read, print, copy or move** `~/.scripture-armor/identity.json` (it *is* the vault — whoever holds it
  holds every package). For this copy's name use `vaultd.mjs status`, not the file.
- **Never edit** `registry.json`, `addressbook.json`, `vaultd.log`, `log-segments/` or anything else in
  `~/.scripture-armor/` by hand. Use the CLI; it keeps the integrity tags and the testimony chain.
- **Never install, update, restart or reconfigure** the daemon / LaunchDaemon without the owner's yes.

## 4. Honest limits on this Mac (say them; don't paper over them)

- **Compiled binaries can't be scanned here** — Ghidra isn't installed, and the binary scan fails closed. The
  helper reports them as "needs the owner". (Fix: install Ghidra and set `SCRIPTURE_GHIDRA_HOME`.)
- **No activation cells** (running untrusted code in a sealed sandbox) — cells need Linux namespaces or a KVM host;
  macOS has neither. Untrusted code is scanned and read, not "safely run".
- The source scan reads `.js .mjs .cjs .ts .tsx .jsx`, shell scripts and Python (plus HTML inline scripts via the
  helper). Other files are data: they're sealable, not judged.
- Cleartext frames by design: a package shows its canary, dates and fingerprints (and, for a sealed repo, the
  folder structure). Content is sealed; structure is visible.

## 5. Talking about it

Write armor results the way the armor's own terms are written: **simple words first, the technical detail in
parentheses right after** — e.g. "Sealed the customer export so only this Mac can open it (ChaCha20-Poly1305,
sealed to `mac-self`)." Report what was scanned, what blocked, what was sealed, and what still waits on the owner.
