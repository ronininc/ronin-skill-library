---
name: brag-reel
description: >-
  Cut a short social AD / promo reel (10-35s MP4) for Instagram Reels, TikTok,
  YouTube or LinkedIn out of a screen recording, product screenshots, or photos
  — built on this machine with ffmpeg and ImageMagick only, no cloud service, no
  AI video model, no npm install. Use WHENEVER the user wants to "turn this
  recording into an ad", "make a promo/reel/brag video for my app/site/business",
  "cut an ad for Instagram/YouTube/LinkedIn", "make a launch video", "show off
  what we built", or drops a .mov/.mp4 and asks for marketing out of it. Produces
  one cut per platform (9:16, 16:9, 1:1) from ONE shared script, against a
  creative gate that refuses to ship an unreadable or dishonest reel. Do NOT use
  for long-form tutorials (use video-walkthrough) or generated footage (use
  movie-gen / media-generation-dispatch).
---

# brag-reel

A reel is a list of timed **scenes**. Build each scene as its own short MP4, then
join them. Text is never typed onto video directly — it is rendered to a
transparent PNG and overlaid.

## Host facts (check once, they decide the whole approach)

```bash
ffmpeg -hide_banner -filters | grep -E ' (drawtext|zoompan|xfade|overlay) '
```

On this Mac ffmpeg is built **without `drawtext`** (no libfreetype/fontconfig).
Do not write a `drawtext` filter — it will fail. Type comes from ImageMagick:

```bash
magick -size 1080x1920 xc:none -font '/System/Library/Fonts/Avenir Next.ttc' \
  -pointsize 62 -fill white -gravity southwest -annotate +92+250 'Your caption' cap.png
```

`-font` must be a **path**, not a family name — `magick`'s font config is broken
here and a bare name errors with `unable to read font`. Available faces live in
`/System/Library/Fonts/` (`Avenir Next.ttc`, `Helvetica.ttc`, `SFNS.ttf`). Python
`Pillow` is also installed if you need text metrics before laying out.

Render one card and **look at it** before building 20 scenes on a bad assumption.

## Workflow

Work in the session scratchpad; deliver finals where the user asked (default a
folder on `~/Desktop`).

### 1. Look at the source before writing a word
Screen recordings are large (2950x1628, 7+ min is normal). **Never decode the
whole file** — a `fps=,tile` contact sheet over a long recording stalls. Fast-seek
single frames (`-ss` BEFORE `-i`), in parallel batches:

```bash
for i in $(seq 0 35); do t=$((i*12+3))
  (ffmpeg -v error -y -ss $t -i src.mov -frames:v 1 -vf scale=1475:-2 -q:v 3 frames/f$(printf %03d $t).jpg) &
  (( i % 6 == 5 )) && wait; done; wait
ffmpeg -v error -y -pattern_type glob -i 'frames/f*.jpg' -vf "scale=480:-2,tile=6x6" -frames:v 1 contact.jpg
```

macOS screen-recording filenames contain a narrow no-break space before AM/PM, so
a typed path fails — resolve with `find ~/Desktop -name 'Screen Recording*.mov'`
and symlink to `src.mov`. (`ls` may be aliased to eza; use `/bin/ls`.)

### 2. Pick shots and crop them clean
Pull full-res frames at the chosen timestamps and `crop=w:h:x:y` each to just the
product surface. Always crop out:
- **browser chrome** (URL bar, extension icons) — draw your own window instead
- **third-party data**: prospect/lead names, deal values, emails, phone numbers
- **unflattering internal metrics** (low conversion, tiny counts) unless asked for
- loading states, empty screens, cursors mid-blur

Build a crop contact sheet and look at it before scripting.

### 3. Write the script — every line must be TRUE
Each caption describes something visible in the footage or on the user's own site.
Reuse the product's real headline and button text. No invented stats, customers,
or features. Shape that works (~20-24s):

```
hook (2-3s) -> 3-5 product beats (4s each) -> optional recap -> outro with name + URL
```

Prefer real footage for any beat where the product MOVES (a map pan, typing, a
build running). Motion is what stops the scroll; stills are for static screens.

### 4. The gate — apply it BEFORE rendering anything
Refuse to render, and fix the script, if any of these fail:

| Rule | Threshold |
|---|---|
| Total length | 10-35s; past 25s is already long for social |
| Scene minimum | 1.2s |
| **Readability** | each scene needs `0.9 + 0.26 x words` seconds — count every word on screen |
| Contrast | text/background >= 4.5:1; accent/background >= 3:1 |
| Fit | headline must fit the safe area (inset ~8.5% each side) in <= 3 lines |
| Honesty | at least one scene shows real product material |

If a scene fails readability, **cut words — do not add seconds.**

### 5. Build the scenes
Per scene, produce one MP4 at the target size. A still:

```bash
ffmpeg -v error -y -loop 1 -t 4 -r 30 -i shot.jpg \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p" \
  -c:v libx264 -crf 20 -preset veryfast s1.mp4
```

Slow push or drift, without `zoompan` (it is very slow at these sizes — pre-scale
and slide a constant-size crop window instead):

```bash
ffmpeg -v error -y -loop 1 -t 4 -r 30 -i shot.jpg -vf \
 "scale=1242:2208:force_original_aspect_ratio=increase,crop=1080:1920:x='(iw-1080)*(t/4)':y='(ih-1920)/2',format=yuv420p" \
 -c:v libx264 -crf 20 -preset veryfast s2.mp4
```

Overlay the text PNG, fading it in so it does not pop:

```bash
ffmpeg -v error -y -i s2.mp4 -i cap.png -filter_complex \
  "[1]format=rgba,fade=t=in:st=0:d=0.5:alpha=1[c];[0][c]overlay=0:0" \
  -c:v libx264 -crf 20 -preset veryfast s2_cap.mp4
```

A photo under a caption needs a scrim or the text will fail contrast — draw a
bottom-weighted gradient into the PNG rather than darkening the whole frame.

### 6. Join, score, and finish

```bash
# crossfade a pair; offset = (first clip duration - transition)
ffmpeg -v error -y -i s1.mp4 -i s2_cap.mp4 -filter_complex \
  "[0][1]xfade=transition=fade:duration=0.3:offset=2.1,format=yuv420p" \
  -c:v libx264 -crf 20 -preset veryfast reel.mp4

# music: loop, fade in and out, limit
ffmpeg -v error -y -i reel.mp4 -stream_loop -1 -i bed.m4a -filter_complex \
  "[1:a]atrim=0:DUR,volume=-16dB,afade=t=in:st=0:d=0.8,afade=t=out:st=$(echo DUR-1.6|bc):d=1.6,alimiter=limit=0.95[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 160k -shortest -movflags +faststart final.mp4
```

Then **bake the poster over frame 0**. An MP4 has no poster attribute and every
platform regenerates its own thumbnail from frame 0, so this is the only reliable
way to control the idle image:

```bash
ffmpeg -v error -y -ss 6.4 -i final.mp4 -frames:v 1 -q:v 2 poster.jpg
ffmpeg -v error -y -i final.mp4 -i poster.jpg -filter_complex \
  "[0:v][1:v]overlay=0:0:enable='eq(n,0)'[v]" -map "[v]" -map 0:a? \
  -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p -c:a copy \
  -movflags +faststart baked.mp4 && mv baked.mp4 final.mp4
```

Pick the poster timestamp at a **settled** beat — text fully in, before it leaves.

### 7. One script, three cuts
Only framing changes; copy stays identical.

| Platform | Size | Watch for |
|---|---|---|
| Reels / TikTok / Shorts | 1080x1920 | the default; most headroom for type |
| YouTube | 1920x1080 | a tall screenshot must shrink hard or the caption leaves the safe area |
| LinkedIn | 1080x1080 | crop the sides of wide screens, never the title |

### 8. Verify before you deliver
Sample frames from **every cut** mid-scene and look at them: screenshot visible,
titles not covered, captions inside the safe area. A command that exited 0 is not
a reel that looks right.

```bash
for t in 1.9 6.4 11.8 18.6; do ffmpeg -v error -ss $t -i final.mp4 -frames:v 1 -vf scale=360:-1 chk_$t.png -y; done
```

## Speed and contention
Encoding competes with everything else on an 8 GB Mac. Before timing anything,
check nothing else is using it (`pgrep -fl ffmpeg` — a Playwright recording or
another session's render will triple your wall time and make a fast command look
broken). Render cuts **sequentially**, and prefer fewer ffmpeg invocations over
many: each scene is a process, and a 20-scene reel spawns a lot of them.

If a reel needs re-cutting often, the fast shape is one process that writes every
frame into a single ffmpeg pipe (rasterise SVG with `sharp`, pipe raw RGB) rather
than one ffmpeg invocation per scene — but build that only if the user asks for it.

## Deliver
Final MP4s + poster JPGs to the user's folder (default `~/Desktop/<Name> Ad/`),
plus the shot crops so any line can be re-cut. Send the MP4s with SendUserFile.
Offer ready-to-paste post copy per platform, and state plainly what was cropped
out and why.
