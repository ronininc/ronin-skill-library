#!/usr/bin/env python3
"""fetch-asset — search and pull CC0 production assets for AAA renders.

  fetch-asset.py search polyhaven textures "rock"        [--limit 10]
  fetch-asset.py search polyhaven hdris "sunset"
  fetch-asset.py search polyhaven models "chair"
  fetch-asset.py search ambientcg Material "concrete"
  fetch-asset.py get polyhaven <id> --kind blend|gltf|hdri|maps [--res 2k] [--out assets/]
  fetch-asset.py get ambientcg <id> [--res 2K-JPG] [--out assets/]
  fetch-asset.py search smithsonian High "skull"          # CC0 museum scans (glb)
  fetch-asset.py get smithsonian <uuid|3d_package:uuid> [--res High|Medium|Low] [--out assets/]
  fetch-asset.py search kenney 3D "city"                  # CC0 stylized game kits
  fetch-asset.py get kenney <slug> [--out assets/]
  fetch-asset.py search nasa any "rover"                  # public-domain NASA models (no insignia!)
  fetch-asset.py get nasa "<folder name>" [--out assets/]
  fetch-asset.py search sketchfab cc0 "chair"             # CC0-only, most-liked first
  fetch-asset.py get sketchfab <uid> [--out assets/]      # needs SKETCHFAB_API_TOKEN (your own)
  fetch-asset.py search quaternius any "city"             # CC0 stylized packs (download is manual, itch.io)
  fetch-asset.py get quaternius <pack-slug>               # prints the itch.io link + logs licence
  fetch-asset.py terrain usgs --bbox W,S,E,N [--size 1024] [--name camelback] [--out assets/]
  fetch-asset.py terrain noaa --bbox W,S,E,N ...          # coast: land + seafloor in one grid

Every download writes/extends <out>/LICENSES.md (source, license, URL) so a
build always knows where each asset came from. Poly Haven files are md5-checked.
Default resolution is 2k: 4k/8k sets thrash an 8 GB machine in EEVEE/Cycles.
"""
import argparse, hashlib, io, json, os, re, sys, urllib.error, urllib.parse, urllib.request, zipfile

UA = {"User-Agent": "ronin-aaa-render-sources/1.0"}  # Poly Haven asks for a unique UA
# Smithsonian's and Kenney's firewalls reject non-browser user agents.
BROWSER = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
           "Accept": "application/json, text/html, */*"}
SI = "https://3d-api.si.edu/api/v1.0/content/file/search"
KENNEY = "https://kenney.nl/assets"
NASA_TREE = "https://api.github.com/repos/nasa/NASA-3D-Resources/git/trees/master?recursive=1"
NASA_RAW = "https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/"
SKF = "https://api.sketchfab.com/v3"
QUAT = "https://quaternius.com"
TERRAIN = {  # ArcGIS ImageServer exportImage: returns a cropped float DEM for any bbox, no key
    "usgs": ("https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage",
             "USGS 3DEP, **US public domain** (credit requested: \"U.S. Geological Survey\"; no USGS logo)"),
    "noaa": ("https://gis.ngdc.noaa.gov/arcgis/rest/services/DEM_mosaics/DEM_global_mosaic/ImageServer/exportImage",
             "NOAA NCEI DEM mosaic, **not subject to US copyright**; not for navigation"),
}
PH = "https://api.polyhaven.com"
ACG = "https://ambientcg.com/api/v2/full_json"


def get_json(url, headers=UA):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return json.load(r)


def get_text(url, headers=BROWSER):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def download(url, dest, md5=None, headers=UA):
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    if os.path.exists(dest) and (md5 is None or hashlib.md5(open(dest, "rb").read()).hexdigest() == md5):
        return dest, False
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=300) as r:
        data = r.read()
    if md5 and hashlib.md5(data).hexdigest() != md5:
        raise SystemExit(f"md5 mismatch for {url}")
    open(dest, "wb").write(data)
    return dest, True


def note_license(out, line):
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "LICENSES.md")
    old = open(path).read() if os.path.exists(path) else "# Asset licenses\n\n"
    if line not in old:
        open(path, "w").write(old + line + "\n")


def search(args):
    kw = args.query.lower()
    if args.source == "polyhaven":
        d = get_json(f"{PH}/assets?type={args.type}")
        hits = [(k, v) for k, v in d.items()
                if kw in k.lower() or kw in v.get("name", "").lower()
                or any(kw in t.lower() for t in v.get("tags", []) + v.get("categories", []))]
        hits.sort(key=lambda kv: -kv[1].get("download_count", 0))  # most-used first
        for k, v in hits[: args.limit]:
            print(f"{k:40s} {v.get('name','')[:40]:40s} dl={v.get('download_count',0)}")
        print(f"-- {len(hits)} match(es) of {len(d)} {args.type}")
    elif args.source == "smithsonian":
        # One row per file; group to one line per model, listing the qualities on offer.
        q = {"q": args.query, "file_type": "glb", "rows": 200}
        rows = get_json(f"{SI}?{urllib.parse.urlencode(q)}", BROWSER).get("rows", [])
        models = {}
        for r in rows:
            c = r["content"]
            m = models.setdefault(c["model_url"], {"title": r["title"], "q": set()})
            m["q"].add(c["quality"])
        want = args.type.lower()
        shown = [(k, v) for k, v in models.items() if want in ("any", "all") or want in {x.lower() for x in v["q"]}]
        for k, v in shown[: args.limit]:
            print(f"{k.split(':')[-1]:38s} {v['title'][:44]:44s} {','.join(sorted(v['q']))}")
        print(f"-- {len(shown)} model(s) with {args.type} glb")
    elif args.source == "kenney":
        slugs, page = [], 1
        while page <= 20:
            try:
                html = get_text(f"{KENNEY}/category:{args.type}" + (f"/page:{page}" if page > 1 else ""))
            except urllib.error.HTTPError:
                if page == 1:
                    raise
                break  # Kenney answers 500, not an empty page, past the last page
            found = [x for x in dict.fromkeys(re.findall(r"kenney\.nl/assets/([a-z0-9-]+)", html)) if x not in slugs]
            if not found:
                break
            slugs += found
            page += 1
        hits = [x for x in slugs if all(w in x for w in args.query.lower().split())]
        for x in hits[: args.limit]:
            print(x)
        print(f"-- {len(hits)} match(es) of {len(slugs)} {args.type} kits")
    elif args.source == "nasa":
        folders = sorted({"/".join(t["path"].split("/")[:2]) for t in nasa_tree()
                          if t["path"].startswith("3D Models/") and t["path"].count("/") >= 2})
        hits = [f.split("/", 1)[1] for f in folders if all(w in f.lower() for w in kw.split())]
        for h in hits[: args.limit]:
            print(h)
        print(f"-- {len(hits)} match(es) of {len(folders)} NASA models")
    elif args.source == "sketchfab":
        # CC0 only, whatever `type` says: other CC licences carry attribution/SA/NC terms.
        q = urllib.parse.urlencode({"type": "models", "license": "cc0", "downloadable": "true",
                                    "q": args.query, "count": min(args.limit, 24), "sort_by": "-likeCount"})
        for m in get_json(f"{SKF}/search?{q}").get("results", []):
            print(f"{m['uid']}  {m['name'][:40]:40s} by {m['user']['username'][:20]:20s} faces={m.get('faceCount')} likes={m.get('likeCount')}")
    elif args.source == "quaternius":
        packs = sorted(set(re.findall(r"packs/([a-z0-9_-]+)\.html", get_text(QUAT + "/"))))
        hits = [x for x in packs if all(w in x for w in kw.split())]
        for x in hits[: args.limit]:
            print(x)
        print(f"-- {len(hits)} match(es) of {len(packs)} packs")
    else:
        q = urllib.parse.urlencode({"type": args.type, "q": args.query, "limit": args.limit, "sort": "Popular"})
        d = get_json(f"{ACG}?{q}")
        for a in d.get("foundAssets", []):
            print(f"{a['assetId']:40s} {a.get('displayCategory','')[:30]:30s} dl={a.get('downloadCount',0)}")
        print(f"-- {d.get('numberOfResults', 0)} match(es)")


def get_polyhaven(args):
    files = get_json(f"{PH}/files/{args.id}")
    base = os.path.join(args.out, args.id)
    got = []
    if args.kind == "hdri":
        f = files["hdri"][args.res]["hdr"]
        got.append(download(f["url"], os.path.join(base, os.path.basename(f["url"])), f["md5"]))
    elif args.kind in ("blend", "gltf"):
        entry = files[args.kind][args.res][args.kind]
        got.append(download(entry["url"], os.path.join(base, os.path.basename(entry["url"])), entry["md5"]))
        for rel, f in entry.get("include", {}).items():  # textures the scene file references
            got.append(download(f["url"], os.path.join(base, rel), f["md5"]))
    else:  # loose PBR maps, jpg where offered (small), else first format
        for mapname in ("Diffuse", "nor_gl", "Rough", "arm", "AO", "Displacement", "metal", "Metal"):
            if mapname in files and args.res in files[mapname]:
                fmts = files[mapname][args.res]
                f = fmts.get("jpg") or fmts.get("png") or next(iter(fmts.values()))
                got.append(download(f["url"], os.path.join(base, os.path.basename(f["url"])), f["md5"]))
    note_license(args.out, f"- `{args.id}` — Poly Haven, **CC0** — https://polyhaven.com/a/{args.id}")
    return got


def get_ambientcg(args):
    q = urllib.parse.urlencode({"id": args.id, "include": "downloadData"})
    d = get_json(f"{ACG}?{q}")
    if not d.get("foundAssets"):
        raise SystemExit(f"ambientCG: no asset {args.id}")
    dl = d["foundAssets"][0]["downloadFolders"]["default"]["downloadFiletypeCategories"]["zip"]["downloads"]
    pick = next((x for x in dl if x["attribute"] == args.res), None)
    if not pick:
        raise SystemExit(f"ambientCG {args.id}: no {args.res}; have {[x['attribute'] for x in dl]}")
    base = os.path.join(args.out, args.id)
    with urllib.request.urlopen(urllib.request.Request(pick["downloadLink"], headers=UA), timeout=300) as r:
        zipfile.ZipFile(io.BytesIO(r.read())).extractall(base)
    note_license(args.out, f"- `{args.id}` — ambientCG, **CC0 1.0** — https://ambientcg.com/view?id={args.id}")
    return [(os.path.join(base, n), True) for n in sorted(os.listdir(base))]


def get_smithsonian(args):
    uuid = args.id.split(":")[-1]
    q = {"model_url": uuid, "file_type": "glb", "rows": 50}
    rows = get_json(f"{SI}?{urllib.parse.urlencode(q)}", BROWSER).get("rows", [])
    if not rows:
        raise SystemExit(f"smithsonian: no glb files for {uuid}")
    by_q = {r["content"]["quality"].lower(): r for r in rows}
    pick = by_q.get(args.res.lower())
    if not pick:
        raise SystemExit(f"smithsonian {uuid}: no {args.res}; have {sorted(by_q)}")
    uri = pick["content"]["uri"]
    base = os.path.join(args.out, uuid)
    got = [download(uri, os.path.join(base, os.path.basename(uri)), headers=BROWSER)]
    # The 3D API serves only Open Access files; the FAQ still says: CC0 covers copyright
    # only — no Smithsonian names/trademarks, and third-party rights remain yours to clear.
    note_license(args.out, f"- `{uuid}` \"{pick['title']}\" — Smithsonian Open Access, **CC0** "
                           f"(no SI trademarks) — {uri}")
    return got


def get_kenney(args):
    html = get_text(f"{KENNEY}/{args.id}")
    m = re.search(r"https://kenney\.nl/media/[^\"' ]+\.zip", html)
    if not m:
        raise SystemExit(f"kenney: no zip on {KENNEY}/{args.id}")
    base = os.path.join(args.out, args.id)
    with urllib.request.urlopen(urllib.request.Request(m.group(0), headers=BROWSER), timeout=300) as r:
        zipfile.ZipFile(io.BytesIO(r.read())).extractall(base)
    note_license(args.out, f"- `{args.id}` — Kenney, **CC0** (don't use the Kenney logo) — {KENNEY}/{args.id}")
    n = sum(len(f) for _, _, f in os.walk(base))
    return [(base + f"/ ({n} files)", True)]


def nasa_tree():
    return get_json(NASA_TREE, {"User-Agent": UA["User-Agent"], "Accept": "application/vnd.github+json"})["tree"]


def get_nasa(args):
    prefix = f"3D Models/{args.id}/"
    files = [t for t in nasa_tree() if t["type"] == "blob" and t["path"].startswith(prefix)]
    if not files:
        raise SystemExit(f"nasa: no folder '{args.id}' (use search nasa any <word>)")
    base = os.path.join(args.out, "nasa", args.id)
    got = [download(NASA_RAW + urllib.parse.quote(t["path"]), os.path.join(base, t["path"][len(prefix):]))
           for t in files]
    note_license(args.out, f"- `{args.id}` — NASA 3D Resources, **no US copyright** — NO NASA insignia/logotype, "
                           f"no implied endorsement; check textures for logos — "
                           f"https://github.com/nasa/NASA-3D-Resources/tree/master/{urllib.parse.quote(prefix)}")
    return got


def get_sketchfab(args):
    meta = get_json(f"{SKF}/models/{args.id}")
    lic = (meta.get("license") or {}).get("label", "")
    if "CC0" not in lic:
        raise SystemExit(f"sketchfab {args.id}: licence is '{lic}', not CC0 — not in the pack")
    token = os.environ.get("SKETCHFAB_API_TOKEN")
    if not token:
        raise SystemExit("sketchfab downloads need YOUR token: set SKETCHFAB_API_TOKEN "
                         "(sketchfab.com → Settings → Password & API). Or download by hand: " + meta["viewerUrl"])
    dl = get_json(f"{SKF}/models/{args.id}/download", {**UA, "Authorization": f"Token {token}"})
    pick = dl.get("glb") or dl.get("gltf")
    base = os.path.join(args.out, "sketchfab", args.id)
    with urllib.request.urlopen(urllib.request.Request(pick["url"], headers=UA), timeout=300) as r:
        data = r.read()
    if "gltf" in dl and pick is dl["gltf"]:
        zipfile.ZipFile(io.BytesIO(data)).extractall(base)
    else:
        os.makedirs(base, exist_ok=True)
        open(os.path.join(base, f"{args.id}.glb"), "wb").write(data)
    # Download API guidelines: licence + author credit must follow the asset everywhere.
    note_license(args.out, f"- `{args.id}` \"{meta['name']}\" by {meta['user']['username']} — Sketchfab, **CC0** "
                           f"(provided by Sketchfab; check for third-party brands/characters) — {meta['viewerUrl']}")
    return [(base, True)]


def get_quaternius(args):
    html = get_text(f"{QUAT}/packs/{args.id}.html")
    m = re.search(r"https://quaternius\.itch\.io/[a-z0-9-]+", html)
    link = m.group(0) if m else f"{QUAT}/packs/{args.id}.html"
    note_license(args.out, f"- `{args.id}` — Quaternius, **CC0** — {link}")
    print(f"Quaternius packs download through itch.io (free, click-through; not scriptable): {link}")
    return []


def write_png16(path, a):
    """Minimal 16-bit greyscale PNG writer (no PIL/GDAL on this machine)."""
    import struct, zlib
    h, w = a.shape
    raw = b"".join(b"\x00" + a[y].astype(">u2").tobytes() for y in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 16, 0, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def terrain(args):
    import math
    import numpy as np, tifffile
    w, s_, e, n = (float(v) for v in args.bbox.split(","))
    url, lic = TERRAIN[args.source]
    lat = math.radians((s_ + n) / 2)                     # ground size, not web-mercator size
    width_m, height_m = (e - w) * 111320 * math.cos(lat), (n - s_) * 110540
    # --size is the long side; the short side follows the real aspect, or the server stretches the grid.
    px_w = args.size if width_m >= height_m else max(2, round(args.size * width_m / height_m))
    px_h = args.size if height_m > width_m else max(2, round(args.size * height_m / width_m))
    q = urllib.parse.urlencode({"bbox": f"{w},{s_},{e},{n}", "bboxSR": 4326, "imageSR": 3857,
                                "size": f"{px_w},{px_h}", "format": "tiff", "pixelType": "F32",
                                "interpolation": "RSP_BilinearInterpolation", "f": "image"})
    name = args.name or f"{args.source}_{w:.3f}_{s_:.3f}"
    base = os.path.join(args.out, "terrain")
    tif, _ = download(f"{url}?{q}", os.path.join(base, name + ".tif"), headers=BROWSER)
    a = tifffile.imread(tif).astype("float64")
    a[~np.isfinite(a) | (a < -12000)] = np.nan          # NoData -> nan
    lo, hi = float(np.nanmin(a)), float(np.nanmax(a))
    a = np.nan_to_num(a, nan=lo)
    write_png16(os.path.join(base, name + "_height16.png"), np.round((a - lo) / max(hi - lo, 1e-6) * 65535))
    meta = {"source": args.source, "bbox": [w, s_, e, n], "px": [int(a.shape[1]), int(a.shape[0])],
            "width_m": round(width_m, 1), "height_m": round(height_m, 1),
            "min_m": round(lo, 2), "max_m": round(hi, 2), "relief_m": round(hi - lo, 2),
            "blender": "plane sized width_m x height_m (or scaled down uniformly), Displace modifier "
                       "with _height16.png (Non-Color), Strength = relief_m in the same units, Midlevel 0"}
    json.dump(meta, open(os.path.join(base, name + ".json"), "w"), indent=1)
    note_license(args.out, f"- terrain `{name}` {args.bbox} — {lic}")
    print(json.dumps(meta, indent=1))
    return [(os.path.join(base, name + x), True) for x in (".tif", "_height16.png", ".json")]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("source", choices=["polyhaven", "ambientcg", "smithsonian", "kenney", "nasa", "sketchfab", "quaternius"])
    s.add_argument("type", help="polyhaven: textures|hdris|models; ambientcg: Material|HDRI|3DModel|Decal|Atlas; "
                                "smithsonian: High|Medium|Low|any; kenney: 3D|2D|Textures|Audio; nasa: any; sketchfab: cc0")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=10)
    g = sub.add_parser("get")
    g.add_argument("source", choices=["polyhaven", "ambientcg", "smithsonian", "kenney", "nasa", "sketchfab", "quaternius"])
    g.add_argument("id")
    g.add_argument("--kind", default="blend", choices=["blend", "gltf", "hdri", "maps"])
    g.add_argument("--res", default=None, help="polyhaven: 1k|2k|4k|8k (default 2k); ambientcg: 2K-JPG etc.")
    g.add_argument("--out", default="assets")
    t = sub.add_parser("terrain")
    t.add_argument("source", choices=list(TERRAIN))
    t.add_argument("--bbox", required=True, help="W,S,E,N in degrees (lon,lat,lon,lat)")
    t.add_argument("--size", type=int, default=1024)
    t.add_argument("--name")
    t.add_argument("--out", default="assets")
    a = p.parse_args()
    if a.cmd == "search":
        return search(a)
    if a.cmd == "terrain":
        terrain(a)
        return print(f"-- license logged in {os.path.join(a.out, 'LICENSES.md')}")
    a.res = a.res or {"polyhaven": "2k", "ambientcg": "2K-JPG", "smithsonian": "Medium"}.get(a.source)
    got = {"polyhaven": get_polyhaven, "ambientcg": get_ambientcg,
           "smithsonian": get_smithsonian, "kenney": get_kenney,
           "nasa": get_nasa, "sketchfab": get_sketchfab, "quaternius": get_quaternius}[a.source](a)
    for path, new in got:
        print(("+ " if new else "= ") + path)
    print(f"-- {len(got)} file(s); license logged in {os.path.join(a.out, 'LICENSES.md')}")


if __name__ == "__main__":
    sys.exit(main())
