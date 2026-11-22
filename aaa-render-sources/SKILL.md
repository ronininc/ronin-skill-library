---
name: aaa-render-sources
description: >-
  The operator's AAA render resource pack — production-grade, OPEN sources to
  build and render with in Blender: Blender Studio open movies + production
  files (Charge, Sprite Fright, Spring… CC-BY 4.0), Blender source + official
  demo/splash scenes, Poly Haven (CC0 textures/HDRIs/models, API), ambientCG
  (CC0 PBR, API), Smithsonian Open Access 3D (CC0 museum scans, API), Kenney
  (CC0 stylized game kits), NASA 3D Resources (public-domain spacecraft/rovers),
  Sketchfab CC0-only (museum/heritage scans), Quaternius + Poly Pizza (stylized),
  USGS 3DEP + NOAA real-world terrain (public domain), OpenStreetMap buildings,
  and OpenMontage (AGPL agentic video-production system: explainers, trailers,
  documentary montage from real open footage) as the long-form video lane. Use WHENEVER a build or content piece needs photoreal or
  cinematic 3D: "AAA render", "make it look like a Blender Studio film",
  "real textures/materials", "HDRI lighting", "3D hero for the site", "render a
  product/scene", "skill pack for renders", or any Blender/EEVEE/Cycles task.
  When the operator says "I need skill packs for AAA renders" they mean MORE
  sources of THIS class — open licence, film/game-production quality,
  programmatically fetchable — not tutorials or paid marketplaces. Pairs with
  brag-reel (renders → ads), website-build-standard (3D heroes), and the
  Blender render paths in Solomon.
---

# AAA render sources

The bar is **Blender Studio film quality**: real PBR materials, real HDRI
light, real reference. Never placeholder grey-box, never AI texture slop when
a CC0 scan exists. Everything here was licence-checked on 2026-09-25.

## The pack

| Source | What | Licence | Access |
|---|---|---|---|
| [Poly Haven](https://polyhaven.com) | 862 textures · 997 HDRIs · 521 models, 1k–8k, `.blend`/glTF/MaterialX | **CC0** — commercial OK, no credit needed | API `api.polyhaven.com` → `scripts/fetch-asset.py` |
| [ambientCG](https://ambientcg.com) | PBR materials, HDRIs, decals, models, 1K–8K JPG/PNG | **CC0 1.0** | API `ambientcg.com/api/v2/full_json` → `scripts/fetch-asset.py` |
| [Blender Studio films](https://studio.blender.org/films/) | 16 open movies 2006–2023 (Elephants Dream → Wing It!), Singularity 2026, Cowboi + Overgrown in dev | **CC-BY 4.0** (logos/trademarks excluded) | Films free; most production files **subscriber-only** |
| [Charge](https://studio.blender.org/projects/charge/) (2022) | 3-min action short, game-cinematic realism, interactive PBR workflow; Geometry Nodes muzzle flash / smoke & fire VFX; character sculpt + groom | CC-BY 4.0 | **Charge Material Asset Library – Freebie** is free; full library + shot files subscriber-only |
| [Blender demo files](https://www.blender.org/download/demo-files/) | Official splash scenes (Singularity 5.1, DOGWALK 4.5, Gold 4.2, Charge 3.4, Sprite Fright 3.0…) + Cycles/EEVEE demos (Classroom, Barcelona Pavillion, Lone Monk…) | Per file: CC-BY, CC-BY-SA, CC0; some "not specified" | Free download — **read the licence per file** |
| [Blender](https://projects.blender.org/blender/blender) | Source (GPL-2.0-or-later). Installed: **Blender 5.2.0 LTS** at `/Applications/Blender.app` | GPL covers the software only — "What you create with Blender is your sole property", incl. `.blend` files | `/Applications/Blender.app/Contents/MacOS/Blender -b` |
| [Smithsonian Open Access 3D](https://3d.si.edu) | Photogrammetry/CT scans of real objects: fossils, artifacts, aircraft, specimens. glb in Thumb/Low/Medium/High (Medium ≈ 150k tris + 2k texture), Draco-compressed | **CC0** for items marked CC0; the 3D API serves only Open Access files. Commercial OK, no attribution needed. No Smithsonian names/logos; third-party rights (trademark, publicity) are yours to clear; culturally sensitive items are excluded | API `3d-api.si.edu/api/v1.0/content/file/search` (needs a browser User-Agent) → `fetch-asset.py` |
| [Kenney](https://kenney.nl/assets/category:3D) | 53 stylized low-poly 3D kits (city, car, nature, space, furniture…), glb/fbx/obj | **CC0**: commercial OK; don't use the Kenney logo | Kit-page zip → `fetch-asset.py`. **Stylized tier**, not photoreal: layout, previs, blockout, stylized pieces |
| [NASA 3D Resources](https://github.com/nasa/NASA-3D-Resources) | 227 models: spacecraft, rovers, suits, asteroids (mostly glb, some .blend + textures), real-world scale; Perseverance ≈ 200k faces, 69 meshes | README: "free and without copyright". NASA guidelines: commercial use OK but **no NASA insignia/logotype/identifiers**, **no implied endorsement**, consent for identifiable people. Many textures carry logos or decals: paint them out before commercial use | GitHub repo → `fetch-asset.py` |
| [Sketchfab](https://sketchfab.com/features/free-3d-models) **CC0 only** | Heritage and museum scans (Smithsonian, noe-3d.at…), 28k–700k faces | **CC0**: commercial OK, no credit needed. Uploaders set the label themselves, so reject anything with brands, characters or copied designs even if marked CC0 | Search is public → `fetch-asset.py`. Download needs **your** `SKETCHFAB_API_TOKEN` (Settings → Password & API); the Download API guidelines require showing licence + author + "provided by Sketchfab" wherever used. Prefer institution uploaders |
| [Quaternius](https://quaternius.com) | 83 stylized packs (~2,000 models) incl. **animated characters** (men, women, knights, dinosaurs); mostly atlas-textured | FAQ: "All models are under the CC0 License", commercial, no credit needed | Pack index via `fetch-asset.py`; the download itself is **manual** (itch.io click-through). Stylized tier |
| [Poly Pizza](https://poly.pizza) | 10k+ low-poly models (many Google Poly re-uploads + Quaternius), OBJ/glTF | **Per model**: CC0 or CC-BY (e.g. a "Chair" by CMHT Oculus is CC-BY, so credit it). Read the label on each model page | API needs **your** key (401 without). Not wired into the fetcher: its docs need a login. Manual download. Stylized tier; get Quaternius models from the source |
| [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) | Real US terrain, down to **1 m lidar** (e.g. all of Phoenix) | "USGS-authored or produced data … U.S. Public Domain". Credit requested: "U.S. Geological Survey"; no USGS logo | `fetch-asset.py terrain usgs --bbox W,S,E,N` → float `.tif` + 16-bit heightmap PNG + real-size `.json`, **no key, no GDAL** |
| [NOAA NCEI DEMs](https://www.ncei.noaa.gov/products/bathymetry) | Coastal land + **seafloor** in one grid (La Jolla: −311 m canyon to +196 m) | "Not subject to copyright protection within the United States"; "not to be used for navigation" | `fetch-asset.py terrain noaa --bbox …` |
| [OpenStreetMap](https://www.openstreetmap.org) | Building footprints/heights, roads, landuse for real city blocks | ODbL. Renders, films and ads are **Produced Works**: any licence, credit "© OpenStreetMap" (+ openstreetmap.org/copyright). Recipients may request the underlying data. A distributed *database* must stay ODbL | Use the existing `overpass-query-hardening` + `osm-building-massing-layer` skills (Overpass → extruded massing) |
| [NVIDIA ORCA](https://developer.nvidia.com/orca) | Lumberyard Bistro only (1–2.8M tris, FBX) | Bistro **CC-BY 4.0** | Free download; heavy: 8 GB will struggle. Other ORCA scenes are non-commercial (see Rejected) |

**Licence rules for client work**
- CC0 (Poly Haven, ambientCG): use freely; logging the source is still required (the fetcher does it).
- CC-BY (Blender Studio, most splash files, Bistro): **credit the author** in the deliverable's credits/footer.
- CC-BY-SA splash files: derivatives of *the file* must stay CC-BY-SA — study them, don't ship them inside a client asset.
- "Not specified" licence → treat as reference only.
- Subscriber-only Blender Studio files: never redistribute.
- Blender Studio characters and the Blender logo are trademarks — don't put them in client ads.

## Fetching (tested)

```bash
F=~/.Codex/skills/aaa-render-sources/scripts/fetch-asset.py
python3 $F search polyhaven textures "rock"            # most-downloaded first
python3 $F search polyhaven hdris "sunset"
python3 $F search ambientcg Material "concrete"
python3 $F get polyhaven rocky_terrain_02 --kind blend --res 2k --out assets
python3 $F get polyhaven lilienstein --kind hdri --res 2k --out assets
python3 $F get ambientcg Concrete034 --res 2K-JPG --out assets
```
`--kind blend|gltf` also pulls every texture the file references (md5-checked);
`maps` pulls loose PBR maps. Each asset is appended to `<out>/LICENSES.md`.
Smithsonian and Kenney examples:
```bash
python3 $F search smithsonian High "skull"          # one line per model + qualities on offer
python3 $F get smithsonian 6bd320bc-25b0-4ef8-9654-a6bdeea28636 --res Medium --out assets
python3 $F search kenney 3D "city"
python3 $F get kenney city-kit-commercial --out assets
```
NASA and Sketchfab:
```bash
python3 $F search nasa any "rover"                    # folder names; use the exact name for get
python3 $F get nasa "Mars 2020 Perseverance Rover" --out assets
python3 $F search sketchfab cc0 "statue"              # CC0-only, most-liked first
SKETCHFAB_API_TOKEN=… python3 $F get sketchfab <uid> --out assets   # refuses non-CC0 models
```
Check file sizes before a NASA get (`gh api repos/nasa/NASA-3D-Resources/contents/3D%20Models/<name>`):
some folders are split multi-GB `.7z` archives.

Terrain (tested: Camelback Mountain 4.2 × 3.3 km, 441 m relief, rendered in 5.2):
```bash
python3 $F terrain usgs --bbox=-111.985,33.505,-111.940,33.535 --size 1024 --name camelback --out assets
python3 $F terrain noaa --bbox=-117.32,32.82,-117.26,32.87 --size 512 --name lajolla --out assets
```
`--size` is the long side; the short side follows the real aspect. In Blender:
grid sized `width_m × height_m` (work in km: divide everything by 1000), Displace
modifier with `_height16.png` (Non-Color, UV coords, Midlevel 0, Strength =
`relief_m`). One tiled PBR texture over kilometres shows a visible grid:
**blend 2–3 CC0 materials by slope/height with a large noise mask**, and take
the Displacement Scale on the material to 0 (the terrain already has relief).
USGS 1 m tiles are ~290 MB each, so use the `terrain` export (cropped server-side), not the tile downloads.

Scans and kits come in at arbitrary scale: normalise to real size on import.
Blender 5.2's glTF importer decodes Smithsonian's Draco files fine.

**Default 2k.** On the M3 / 8 GB machine, 4k sets in several materials swap;
8k only for a single hero close-up.

## Using Poly Haven materials in Blender — two traps, both hit in testing

1. **Texture `.blend` files are preview scenes**, not assets: a 90 m sphere +
   plane, their own camera 251 units away, an 8-light rig. Don't render them as
   they are or drop your camera in — **append only the material**.
2. **Displacement ships at Scale 1.0 m** with `displacement_method = DISPLACEMENT`,
   tuned for that 90 m preview. On a human-scale object it explodes into spikes.
   Rescale to the object:

```python
import bpy
with bpy.data.libraries.load(path_to_blend, link=False) as (src, dst):
    dst.materials = [m for m in src.materials if asset_id in m.lower()]
mat = bpy.data.materials[asset_id]
mat.displacement_method = "BOTH"                 # true displacement + bump detail
for n in mat.node_tree.nodes:
    if n.type == "DISPLACEMENT":
        n.inputs["Scale"].default_value = 0.05   # ~5 cm relief for 1–2 m objects
obj.data.materials.append(mat)
```

HDRI world:
```python
w = bpy.data.worlds.new("hdri"); scene.world = w; w.use_nodes = True
env = w.node_tree.nodes.new("ShaderNodeTexEnvironment")
env.image = bpy.data.images.load(hdr_path)
w.node_tree.links.new(env.outputs[0], w.node_tree.nodes["Background"].inputs[0])
```
In Blender 5.2 the engine id is `BLENDER_EEVEE` (EEVEE Next is just `BLENDER_EEVEE` now).

Always prove it: headless render a frame, look at it, and check that no image
is missing (`[i.filepath for i in bpy.data.images if i.source=='FILE' and not os.path.exists(bpy.path.abspath(i.filepath))]` is empty).

## Learning from the films (what to study, not copy)

- **Charge**: realism on an interactive PBR workflow; GN-driven VFX (muzzle
  flash, smoke & fire); game-cinematic camera and pacing. The template for
  "AAA action" looks.
- **Demo/splash files** are the fastest way to learn production lighting and
  shading: open one, read its world, light rig, colour management and render
  settings, then rebuild the approach with CC0 assets.
- Production breakdowns (subscriber) cover grooming, rigging and shot
  pipelines — describe the technique, don't lift the files.

## Growing the pack ("I need more skill packs")

A new source joins only if it passes all four:
1. **Open licence**, verified on the source's own licence page (CC0, CC-BY, or
   an OSI/FSF software licence). Record the exact wording and the date checked.
2. **Production quality**: film, game or scan grade, not hobby stock.
3. **Fetchable**: an API or stable direct URLs, so builds can pull it scripted.
4. **Runs on the machine**: works at 1k/2k in EEVEE on 8 GB, or is clearly
   marked heavy.

Add it to the table with licence and access, add a fetch mode to
`fetch-asset.py` if it has an API, and prove it with one headless render.
## Video production: OpenMontage (vetted 2026-09-25)

[calesthio/OpenMontage](https://github.com/calesthio/OpenMontage): an agentic
video studio with 12 pipelines (explainer, talking head, screen demo, cinematic
trailer, character animation, podcast, localization/dub, **documentary
montage from real open footage**…), 100+ tools, a scored provider layer with a
cost log, and a "Backlot" board that shows the production live. Python +
Remotion/HyperFrames + FFmpeg. About 61k stars.

**When to use which**
- `brag-reel`: short 10–35s social cuts from OUR footage or renders, fully local, deterministic.
- **OpenMontage**: longer or narrated pieces, multi-scene explainers and trailers,
  montage from open archives, dubbing. Its finished MP4s can then feed `brag-reel`
  as `clip` sources for the 9:16/16:9/1:1 cuts.

**Licence boundary (read before using it for a client)**
| Part | Licence | Rule |
|---|---|---|
| OpenMontage code | **AGPL-3.0** | Run it as a **separate local tool** (its own clone, e.g. `~/Projects/OpenMontage`). Videos it renders are ours: AGPL §2, output is covered only "if the output, given its content, constitutes a covered work". **Never copy its code into TSS, Solomon, the CRM or any Worker**: AGPL's network clause would force those private repos open. |
| Remotion (default renderer) | Remotion License | Free "for-profit organization with up to 3 employees", individuals, non-profits. **Bigger than 3 → buy a Company License** or use HyperFrames |
| HyperFrames (HeyGen) | Apache-2.0 | Free for any size |
| Piper TTS (free narration) | Voices licensed **per voice** | Check the voice's model card; use a commercial-OK voice, or Kokoro (the house default) |
| Pexels / Pixabay / Unsplash | Free commercial, no credit | NOT allowed: selling unaltered copies, implying endorsement by people/brands shown, using as a trademark; Pixabay: no recognisable brands/logos in commercial use |
| Archive.org footage | **No blanket licence** | "does not make guarantees as to the copyright status". Use only items with an explicit PD/CC0/CC-BY mark, and log it |
| NASA / Wikimedia footage | See NASA rules above; Wikimedia per file | No NASA insignia; Wikimedia CC-BY/BY-SA needs credit |
| Paid providers (ElevenLabs, Veo, Kling/fal.ai, OpenAI…) | Their ToS | **Spend = money gate**: approve each paid generation. OpenMontage shows cost per provider; keep keys out of prompts |

**On the M3 / 8 GB machine**: the zero-key path works (Piper + open footage +
Remotion/HyperFrames + FFmpeg). Local video generation (Wan 2.x, Hunyuan, LTX,
CogVideo) needs a real GPU: don't enable `VIDEO_GEN_LOCAL_ENABLED` here.
**Installed 2026-09-25** at `~/Projects/OpenMontage` (its own clone, outside
every private repo). Python 3.10 venv via `uv venv --python 3.10 .venv` (the
repo pins 3.10; system Python is 3.14), `uv pip install -r requirements.txt
piper-tts`, `remotion-composer` → `npm install`, `.env` copied from
`.env.example` with **no keys set**. GPU extras (`requirements-gpu.txt`,
PyTorch) deliberately skipped.

Proof: `.venv/bin/python render_demo.py focusflow-pitch` → 22.5 s, 1920×1080,
h264 + aac, 675 frames in **4 min 36 s** on the M3 (≈2.4 fps; budget long
pieces accordingly). `render_demo.py --list` shows the three zero-key demos.
The first render downloads Remotion's headless Chrome. npm's install-script
guard blocks esbuild's postinstall; rendering works anyway (esbuild's
darwin-arm64 binary ships as its own package).
Piper voice models are downloaded per voice: check each voice's licence
before a client job.

### Vetted and REJECTED for client work (checked 2026-09-25)
Fine to study for technique; never ship them or their renders in paid work.

| Source | Why it fails |
|---|---|
| Pixar **Kitchen Set** (OpenUSD) | Pixar EULA: "personal, non-commercial testing" only; no production, advertising or redistribution |
| Animal Logic / Netflix **ALab** (ASWF DPEL) | ASWF Digital Assets License: only "education, training, research, … benchmarking … product demonstrations" |
| Intel **4004 Moore Lane** (ASWF DPEL) | Same ASWF Digital Assets License |
| ORCA **UE4 Sun Temple** | CC BY-NC-SA 4.0 (non-commercial) |
| ORCA **Emerald Square** | CC BY-NC-SA 3.0 (non-commercial); also 10M tris |
| ORCA **SpeedTree** plants (8 species) | CC BY-NC-SA 3.0 (non-commercial) |
| Disney **Moana Island Scene** | Disney licence: "may only be used for research or software development (including benchmarking)". Also 45–131 GB |
| **Wikimedia Commons 3D** | Licence varies per file, but only untextured `.stl` is accepted: "cannot display colours or other modern material-rendering capabilities". Fails the quality bar |

Next leads (not vetted yet): Copernicus GLO-30 DEM (global terrain outside
the US), NASA/USGS Landsat + NAIP aerial imagery (real ground colour to drape
on terrain), Mixamo (rigged animation; Adobe terms, not open, so check first).
