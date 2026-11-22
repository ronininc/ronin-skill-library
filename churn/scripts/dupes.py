#!/usr/bin/env python3
"""Find duplicate files >= MIN_MB across roots. Read-only.

Stages: group by size -> partial hash (head+tail 1 MB) -> full blake2b.
Hard links (same inode) are collapsed. APFS clones are detected via
F_LOG2PHYS (same physical start block) and reported separately, since
deleting a clone frees nothing.
"""
import fcntl, hashlib, json, os, stat, struct, sys
from collections import defaultdict

MIN = int(os.environ.get("MIN_MB", "10")) * 1024 * 1024
ROOTS = sys.argv[1:]
SKIP_DIRS = {
    os.path.expanduser("~/.local/share/containers"),  # VM disk images
    "/private/var/folders",
}
SKIP_NAMES = {".Trash", ".Spotlight-V100", ".fseventsd", ".DocumentRevisions-V100"}
F_LOG2PHYS = 49

def phys(path):
    try:
        fd = os.open(path, os.O_RDONLY)
        try:
            out = fcntl.fcntl(fd, F_LOG2PHYS, struct.pack("Iqq", 0, 0, 0))
            return struct.unpack("Iqq", out)[2]
        finally:
            os.close(fd)
    except OSError:
        return None

def partial(path, size):
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        h.update(f.read(1 << 20))
        if size > 2 << 20:
            f.seek(-(1 << 20), 2)
            h.update(f.read(1 << 20))
    return h.hexdigest()

def full(path):
    h = hashlib.blake2b(digest_size=20)
    with open(path, "rb") as f:
        while chunk := f.read(8 << 20):
            h.update(chunk)
    return h.hexdigest()

by_size = defaultdict(list)
seen_inodes = set()
scanned = 0
for root in ROOTS:
    for dp, dns, fns in os.walk(root, onerror=lambda e: None):
        if dp in SKIP_DIRS:
            dns[:] = []
            continue
        dns[:] = [d for d in dns if d not in SKIP_NAMES and os.path.join(dp, d) not in SKIP_DIRS]
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode) or st.st_size < MIN:
                continue
            key = (st.st_dev, st.st_ino)
            if key in seen_inodes:
                continue
            seen_inodes.add(key)
            by_size[st.st_size].append(p)
            scanned += 1

print(f"scanned {scanned} files >= {MIN>>20} MB", file=sys.stderr)

groups = []
for size, paths in by_size.items():
    if len(paths) < 2:
        continue
    by_part = defaultdict(list)
    for p in paths:
        try:
            by_part[partial(p, size)].append(p)
        except OSError:
            pass
    for ps in by_part.values():
        if len(ps) < 2:
            continue
        by_full = defaultdict(list)
        for p in ps:
            try:
                by_full[full(p)].append(p)
            except OSError:
                pass
        for digest, same in by_full.items():
            if len(same) < 2:
                continue
            # split into clone families (same physical start block)
            fam = defaultdict(list)
            for p in same:
                fam[phys(p) or id(p)].append(p)
            distinct = len(fam)  # copies that actually occupy their own blocks
            groups.append({
                "size": size,
                "digest": digest,
                "paths": sorted(same),
                "clone_families": [sorted(v) for v in fam.values()],
                "reclaimable": size * (distinct - 1),
            })

groups.sort(key=lambda g: g["reclaimable"], reverse=True)
json.dump(groups, sys.stdout, indent=1)
tot = sum(g["reclaimable"] for g in groups)
logical = sum(g["size"] * (len(g["paths"]) - 1) for g in groups)
print(f"groups={len(groups)} reclaimable={tot/1e9:.2f} GB "
      f"(logical dup bytes {logical/1e9:.2f} GB; difference = APFS clones)", file=sys.stderr)
