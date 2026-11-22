#!/usr/bin/env python3
"""churn: weekly disk sweep. Moves disk churn to the Trash, never deletes.

usage: churn.py [--apply] [--growth] [--min-age-hours 24] [--log-max-mb 200]

Without --apply it only reports. With --apply each item goes through
/usr/bin/trash (Finder's "Put Back" works) and git worktree lists are pruned.

What it sweeps:
  worktrees   linked git worktrees that are clean, fully pushed, idle, past
              --min-age-hours, not protected, with no unique .env/db/key file
              and no built installer
  temp        leaked PyInstaller _MEI* dirs, solomon-reloc-* leftovers, stale
              Chrome code_sign_clone copies (none of them open)
  git-garbage tmp_pack_*/tmp_idx_* left by interrupted fetches (>24 h, not open)
  logs        *.log over --log-max-mb. Not held open: trashed. Held open: a
              gzip copy goes to the Trash and the live file is truncated.
              Crash loops are flagged with their top error line.
  growth      (--growth) top-level home folders vs last run; flags >2 GB jumps

Reports land in ~/Library/Logs/churn/<date>.md; manifests (to restore a
worktree: git -C <repo> worktree add <path> <branch|head>) in <date>.tsv.
"""
import bisect, datetime, glob, gzip, json, os, re, shutil, subprocess, sys, time

H = os.path.expanduser("~")
APPLY = "--apply" in sys.argv
GROWTH = "--growth" in sys.argv

def arg(name, default):
    if name in sys.argv:
        return float(sys.argv[sys.argv.index(name) + 1])
    return default

MIN_AGE = arg("--min-age-hours", 24) * 3600
LOG_MAX = arg("--log-max-mb", 200) * 1024 * 1024
NOW = time.time()
STAMP = datetime.datetime.now().strftime("%Y-%m-%d")
OUT = os.path.join(H, "Library", "Logs", "churn")

# Never touched. Extend with one path prefix per line in ~/.config/churn/keep.txt
PROTECTED = [
    "/Applications/", H + "/Applications/",
    H + "/solomon-integrate-wt/",            # live Solomon.app build checkout
    H + "/.codex/worktrees/dots-",           # Codex dots bots (LaunchAgent)
    H + "/solomon-prebench-state-",          # holds an older vault seal key
    H + "/Library/Application Support/",
    H + "/.solomon/",
]
keep_file = os.path.join(H, ".config", "churn", "keep.txt")
if os.path.exists(keep_file):
    PROTECTED += [os.path.expanduser(l.strip()) for l in open(keep_file) if l.strip() and not l.startswith("#")]

# Processes whose open files don't mean "in use" (indexers and walkers)
SCANNERS = {"du", "find", "mds", "mds_stores", "mdworker", "mdworker_shared", "fseventsd", "Spotlight"}
SECRET_RE = re.compile(r"(^\.env|^\.dev\.vars$|^secrets\.json$|^credentials\.json$|\.(db|sqlite|sqlite3|pem|key)$)")
SKIP_IGNORED = ("node_modules", "/dist/", "/build/", ".wrangler/", "__pycache__", ".test-runtime", "/venv/", "/.venv/")
INSTALLERS = ("*.deb", "*.dmg", "*.AppImage", "*.pkg", "*.msi")


def run(*cmd, cwd=None, timeout=600):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except Exception as e:
        return 1, str(e)

def free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return st.f_bavail * st.f_frsize / 1e9

def du_bytes(p):
    rc, out = run("du", "-sk", p, timeout=900)
    return int(out.split()[0]) * 1024 if rc == 0 and out else 0

def gb(n):
    return f"{n / 1e9:.1f} GB"

def protected(p):
    p2 = p.rstrip("/") + "/"
    return any(p2.startswith(x) or p == x.rstrip("/") for x in PROTECTED)


# ---- one lsof snapshot, taken before this script walks anything -------------
def open_paths():
    rc, out = run("lsof", "-n", "-Fpcn", timeout=300)
    paths, cmd = [], ""
    for line in out.splitlines():
        if line.startswith("c"):
            cmd = line[1:]
        elif line.startswith("n/") and cmd not in SCANNERS:
            paths.append(line[1:])
    paths.sort()
    return paths

OPEN = open_paths()

def in_use(p):
    """True when any non-scanner process has p or something under p open (incl. cwd)."""
    i = bisect.bisect_left(OPEN, p)
    return i < len(OPEN) and (OPEN[i] == p or OPEN[i].startswith(p.rstrip("/") + "/"))


# ---- worktrees --------------------------------------------------------------
def discover_repos():
    roots = [H + "/Projects", H + "/Projects/clients", H]
    repos = []
    for root in roots:
        try:
            names = os.listdir(root)
        except OSError:
            continue
        for n in names:
            d = os.path.join(root, n)
            if os.path.isdir(os.path.join(d, ".git")):  # a main checkout, not a linked worktree
                repos.append(d)
    return sorted(set(repos))

def worktrees(repo):
    rc, txt = run("git", "-C", repo, "worktree", "list", "--porcelain")
    out = []
    for i, block in enumerate(b for b in txt.split("\n\n") if b.strip()):
        info = {}
        for line in block.splitlines():
            k, _, v = line.partition(" ")
            info[k] = v or True
        out.append({"path": info["worktree"], "main": i == 0, "locked": "locked" in info,
                    "branch": str(info.get("branch", "(detached)")).replace("refs/heads/", ""),
                    "head": info.get("HEAD", "")})
    return out

def unique_secrets(wt, main):
    rc, out = run("git", "-C", wt, "ls-files", "--others", "--ignored", "--exclude-standard",
                  "--directory", "--no-empty-directory")
    hits = []
    for rel in out.splitlines():
        if any(s in "/" + rel for s in SKIP_IGNORED):
            continue
        base = os.path.basename(rel.rstrip("/"))
        if not SECRET_RE.search(base):
            continue
        p, m = os.path.join(wt, rel), os.path.join(main, rel)
        if os.path.isdir(p):
            hits.append(rel)
        elif os.path.getsize(p) > 0:
            same = os.path.isfile(m) and run("cmp", "-s", p, m)[0] == 0
            if not same:
                hits.append(rel)
    return hits

def installers(wt):
    found = []
    for pat in INSTALLERS:
        for base in ("dist", "*/dist", "*/dist-*", "dist-*"):
            found += glob.glob(os.path.join(wt, base, pat))
    return found

def last_activity(wt):
    rc, ct = run("git", "-C", wt, "log", "-1", "--format=%ct")
    t = int(ct) if ct.isdigit() else 0
    rc, gd = run("git", "-C", wt, "rev-parse", "--absolute-git-dir")
    idx = os.path.join(gd, "index")
    if os.path.exists(idx):
        t = max(t, os.path.getmtime(idx))
    return t

def judge_worktree(repo, w):
    wt = w["path"]
    if w["main"]:
        return "main checkout"
    if not os.path.isdir(wt):
        return None  # already gone; prune handles it
    if protected(wt):
        return "protected"
    if w["locked"]:
        return "locked"
    if in_use(wt):
        return "in use by a running process"
    if NOW - last_activity(wt) < MIN_AGE:
        return "active recently"
    rc, st = run("git", "--no-optional-locks", "-C", wt, "status", "--porcelain", "--untracked-files=normal")
    if rc != 0:
        return "git status failed"
    if st:
        return f"{len(st.splitlines())} uncommitted/untracked"
    rc, unp = run("git", "-C", wt, "rev-list", "--count", "HEAD", "--not", "--remotes")
    if rc != 0 or unp != "0":
        return f"{unp} commits not on any remote"
    s = unique_secrets(wt, repo)
    if s:
        return "unique ignored files: " + ", ".join(s[:3])
    inst = installers(wt)
    if inst:
        return "holds a built installer: " + os.path.basename(inst[0])
    return ""


# ---- actions ----------------------------------------------------------------
TRASHED, KEPT, FLAGS, MANIFEST = [], {}, [], []

def trash(path, kind, note=""):
    size = du_bytes(path)
    if APPLY:
        rc, out = run("/usr/bin/trash", path)
        if os.path.exists(path):
            KEPT[f"{kind}: trash failed"] = KEPT.get(f"{kind}: trash failed", 0) + 1
            return False
    TRASHED.append((kind, path, size, note))
    return True

def sweep_worktrees():
    for repo in discover_repos():
        touched = False
        for w in worktrees(repo):
            why = judge_worktree(repo, w)
            if why is None:
                continue
            if why:
                if not w["main"]:
                    key = "worktree: " + re.sub(r"^\d+ ", "", why.split(":")[0])
                    KEPT[key] = KEPT.get(key, 0) + 1
                continue
            if trash(w["path"], "worktree", w["branch"]):
                MANIFEST.append((repo, w["path"], w["branch"], w["head"]))
                touched = True
        if touched and APPLY:
            run("git", "-C", repo, "worktree", "prune")

def sweep_temp():
    tdir = os.environ.get("CHURN_TMPDIR") or run("getconf", "DARWIN_USER_TEMP_DIR")[1]
    tdir = tdir.rstrip("/")
    xdir = os.path.join(os.path.dirname(tdir), "X", "com.google.Chrome.code_sign_clone")
    cands = glob.glob(tdir + "/_MEI*") + glob.glob(tdir + "/solomon-reloc-*") + glob.glob(xdir + "/code_sign_clone.*")
    for p in cands:
        if NOW - os.path.getmtime(p) > 3600 and not in_use(p):
            trash(p, "temp")

def sweep_git_garbage():
    for repo in discover_repos():
        for p in glob.glob(repo + "/.git/objects/pack/tmp_*"):
            if NOW - os.path.getmtime(p) > 86400 and not in_use(p):
                trash(p, "git-garbage", os.path.basename(repo))

def crash_signature(path):
    try:
        with open(path, "rb") as f:
            f.seek(max(0, os.path.getsize(path) - 65536))
            tail = f.read().decode("utf-8", "replace")
    except OSError:
        return ""
    errs = [l.strip() for l in tail.splitlines() if re.search(r"(Error|Exception|FATAL|failed)", l) and not l.strip().startswith("File ")]
    if len(errs) < 5:
        return ""
    top = max(set(errs), key=errs.count)
    return f"{errs.count(top)}x in last 64 KB: {top[:160]}"

def sweep_logs():
    roots = [H + "/RoninApps", H + "/Library/Logs", H + "/Library/Application Support/sol-ghost",
             H + "/Library/Application Support/solomon-desktop"] + discover_repos()
    seen = set()
    for root in roots:
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in ("node_modules", ".git", "venv", ".venv", "churn")]
            if dp.count("/") - root.count("/") > 5:
                dns[:] = []
            for fn in fns:
                if not fn.endswith(".log"):
                    continue
                p = os.path.join(dp, fn)
                try:
                    size = os.path.getsize(p)
                except OSError:
                    continue
                if size < LOG_MAX or p in seen:
                    continue
                seen.add(p)
                sig = crash_signature(p)
                if sig:
                    FLAGS.append(f"Crash loop writing `{p.replace(H, '~')}` ({gb(size)}): {sig}")
                if not in_use(p):
                    trash(p, "log", sig and "crash loop")
                    continue
                # Held open: keep the content in the Trash as gzip, then truncate in place.
                if APPLY:
                    gz = os.path.join(os.path.dirname(p), f"{fn}.{STAMP}.gz")
                    with open(p, "rb") as src, gzip.open(gz, "wb") as dst:
                        shutil.copyfileobj(src, dst, 8 << 20)
                    run("/usr/bin/trash", gz)
                    with open(p, "r+b") as f:
                        f.truncate(0)
                TRASHED.append(("log", p, size, "held open: gzip copy trashed, file truncated"))

def growth():
    path = os.path.join(OUT, "sizes.json")
    prev = json.load(open(path)) if os.path.exists(path) else {}
    cur = {}
    for n in os.listdir(H):
        p = os.path.join(H, n)
        if os.path.isdir(p) and not os.path.islink(p) and n != ".Trash":
            cur[n] = du_bytes(p)
    for n in ("Library/Application Support", "Library/Caches", "Projects"):
        for c in os.listdir(os.path.join(H, n)):
            p = os.path.join(H, n, c)
            if os.path.isdir(p) and not os.path.islink(p):
                cur[f"{n}/{c}"] = du_bytes(p)
    rows = []
    for k, v in cur.items():
        d = v - prev.get(k, v)
        if d > 2e9:
            rows.append((d, k, v))
    if APPLY:
        json.dump(cur, open(path, "w"))
    return sorted(rows, reverse=True), sorted(((v, k) for k, v in cur.items() if "/" not in k), reverse=True)[:8]


# ---- main -------------------------------------------------------------------
def main():
    os.makedirs(OUT, exist_ok=True)
    before = free_gb()
    sweep_temp()
    sweep_git_garbage()
    sweep_worktrees()
    sweep_logs()
    grew, biggest = growth() if GROWTH else ([], [])
    total = sum(t[2] for t in TRASHED)

    by_kind = {}
    for kind, p, size, note in TRASHED:
        n, s = by_kind.get(kind, (0, 0))
        by_kind[kind] = (n + 1, s + size)
    L = [f"# Churn sweep {STAMP}{'' if APPLY else ' (dry run: nothing moved)'}", "",
         f"Free space: {before:.1f} GB. {'Moved' if APPLY else 'Would move'} {len(TRASHED)} items to the Trash, "
         f"up to {gb(total)} by `du` (clones share blocks, so emptying the Trash frees less).", ""]
    if by_kind:
        L += ["| Kind | Items | Up to |", "|---|---|---|"]
        L += [f"| {k} | {n} | {gb(s)} |" for k, (n, s) in sorted(by_kind.items(), key=lambda x: -x[1][1])]
        L.append("")
    if FLAGS:
        L += ["## Needs a fix (the sweep only treats the symptom)", ""] + [f"- {f}" for f in FLAGS] + [""]
    if grew:
        L += ["## Grew more than 2 GB since last week", ""] + [f"- `~/{k}`: +{gb(d)} (now {gb(v)})" for d, k, v in grew] + [""]
    if biggest:
        L += ["## Biggest folders in home", ""] + [f"- `~/{k}`: {gb(v)}" for v, k in biggest] + [""]
    if KEPT:
        L += ["## Kept, and why", ""] + [f"- {k}: {n}" for k, n in sorted(KEPT.items(), key=lambda x: -x[1])] + [""]
    if TRASHED:
        L += ["## Items", ""] + [f"- {k}: `{p.replace(H, '~')}`" + (f" ({n})" if n else "") for k, p, s, n in TRASHED] + [""]
    L.append("Empty the Trash to get the space back. Until then Finder's Put Back restores anything; "
             "a restored worktree also needs `git worktree repair` in its repo.")
    report = "\n".join(L)
    if APPLY:
        open(os.path.join(OUT, f"{STAMP}.md"), "w").write(report + "\n")
        with open(os.path.join(OUT, f"{STAMP}.tsv"), "a") as f:
            for row in MANIFEST:
                f.write("\t".join(row) + "\n")
    print(report)

if __name__ == "__main__":
    main()
