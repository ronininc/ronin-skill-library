#!/usr/bin/env python3
"""Collapse identical files into APFS clones. Every path keeps its name,
content, mode, timestamps and xattrs; the bytes are stored once.

usage: clonededupe.py dupes.json journal.tsv [--apply]
Without --apply it only prints the plan.
"""
import ctypes, ctypes.util, json, os, subprocess, sys, time, filecmp, fcntl, struct

DUPES, JOURNAL = sys.argv[1], sys.argv[2]
APPLY = "--apply" in sys.argv
H = os.path.expanduser("~")
PROTECTED = (  # never modified; may serve as the keeper
    "/Applications/", "/opt/", "/Library/",
    H + "/solomon-integrate-wt/",
    H + "/Library/Application Support/solomon-desktop/",
    H + "/Library/Application Support/Claude/",
    H + "/Applications/",                          # Kingmaker.app
    H + "/Library/Application Support/sol-ghost/",  # Kingmaker data
    H + "/Library/Application Support/MobileSync/", # iPhone backups
    H + "/.solomon/",                              # knowledge base
    H + "/.Trash/",
    H + "/Library/Messages/",
    H + "/Library/Daemon Containers/",
)
SKIP_PARTS = ("/.git/",)
SKIP_EXT = (".db", ".sqlite", ".sqlite3", "-wal", "-shm", ".log", ".raw", ".qcow2", ".lock")
RECENT = 2 * 3600

libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
libc.clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
libc.listxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]
libc.getxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
libc.setxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
libc.removexattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
NOFOLLOW = 1

def xattrs(path):
    b = path.encode()
    n = libc.listxattr(b, None, 0, NOFOLLOW)
    if n <= 0:
        return {}
    buf = ctypes.create_string_buffer(n)
    libc.listxattr(b, buf, n, NOFOLLOW)
    out = {}
    for name in buf.raw[:n].split(b"\0"):
        if not name:
            continue
        sz = libc.getxattr(b, name, None, 0, 0, NOFOLLOW)
        if sz < 0:
            continue
        v = ctypes.create_string_buffer(max(sz, 1))
        libc.getxattr(b, name, v, sz, 0, NOFOLLOW)
        out[name] = v.raw[:sz]
    return out

def set_xattrs(path, want):
    b = path.encode()
    for name in xattrs(path):
        libc.removexattr(b, name, NOFOLLOW)
    for name, val in want.items():
        libc.setxattr(b, name, val, len(val), 0, NOFOLLOW)

def phys(p):
    fd = os.open(p, os.O_RDONLY)
    try:
        return struct.unpack("Iqq", fcntl.fcntl(fd, 49, struct.pack("Iqq", 0, 0, 0)))[2]
    finally:
        os.close(fd)

def protected(p):
    return p.startswith(PROTECTED)

def eligible(p, now):
    if protected(p) or any(s in p for s in SKIP_PARTS) or p.endswith(SKIP_EXT):
        return "protected/skip-type"
    try:
        st = os.lstat(p)
    except OSError:
        return "gone"
    if st.st_nlink > 1:
        return "hardlinked"
    if now - st.st_mtime < RECENT:
        return "recently-modified"
    return None

# one lsof snapshot of every open regular file
open_files = set()
try:
    out = subprocess.run(["lsof", "-n", "-P", "-Fn"], capture_output=True, text=True, timeout=180).stdout
    open_files = {l[1:] for l in out.splitlines() if l.startswith("n/")}
except Exception as e:
    print("lsof failed, refusing to apply:", e, file=sys.stderr)
    if APPLY:
        sys.exit(1)

groups = [g for g in json.load(open(DUPES)) if not any("/.Trash/" in p for p in g["paths"])]
now = time.time()
plan, skipped = [], {}
for g in groups:
    fams = [f for f in g["clone_families"] if all(os.path.exists(p) for p in f)]
    if len(fams) < 2:
        continue
    # keeper family: one containing a protected path, else the largest
    fams.sort(key=lambda f: (not any(protected(p) for p in f), -len(f)))
    keeper = fams[0][0]
    for fam in fams[1:]:
        reasons = [eligible(p, now) or ("open" if p in open_files else None) for p in fam]
        bad = [r for r in reasons if r]
        if bad:  # the family's blocks stay referenced unless every member moves
            for r in bad:
                skipped[r] = skipped.get(r, 0) + 1
            continue
        for p in fam:
            plan.append((g["size"], keeper, p))

fam_bytes = {}
for size, keeper, p in plan:
    fam_bytes[(keeper, phys(p))] = size
print(f"plan: {len(plan)} files to turn into clones, ~{sum(fam_bytes.values())/1e9:.2f} GB freed")
print("skipped families by reason:", skipped)
if not APPLY:
    sys.exit(0)

done = failed = 0
with open(JOURNAL, "a") as j:
    for size, keeper, p in plan:
        tmp = p + ".clonededupe-tmp"
        try:
            if p in open_files or not filecmp.cmp(keeper, p, shallow=False):
                failed += 1
                j.write(f"SKIP-MISMATCH\t{keeper}\t{p}\n")
                continue
            st = os.lstat(p)
            xa = xattrs(p)
            if libc.clonefile(keeper.encode(), tmp.encode(), NOFOLLOW) != 0:
                raise OSError(ctypes.get_errno(), "clonefile failed")
            set_xattrs(tmp, xa)
            os.chmod(tmp, st.st_mode & 0o7777)
            os.utime(tmp, ns=(st.st_atime_ns, st.st_mtime_ns))
            if st.st_flags:
                os.chflags(tmp, st.st_flags)
            os.rename(tmp, p)
            done += 1
            j.write(f"CLONED\t{keeper}\t{p}\t{size}\n")
        except Exception as e:
            failed += 1
            j.write(f"ERROR\t{keeper}\t{p}\t{e}\n")
            try:
                os.unlink(tmp)
            except OSError:
                pass
print(f"cloned {done}, skipped/failed {failed}; journal {JOURNAL}")
