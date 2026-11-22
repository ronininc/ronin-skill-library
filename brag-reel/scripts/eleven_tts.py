#!/usr/bin/env python3
"""ElevenLabs voiceover for brag-reel. Standard library only (no pip install).

Key: $ELEVENLABS_API_KEY, else the macOS keychain item `elevenlabs`:
    security add-generic-password -a "$USER" -s elevenlabs -w
The key is read at call time and never printed or written anywhere.

CLI:
    eleven_tts.py check                      # key present? plan, characters left
    eleven_tts.py voices                     # voices this account can use
    eleven_tts.py say "text" out.wav [--voice NAME|ID] [--prev "..."] [--next "..."]

As a module:
    from eleven_tts import synth
    synth(text, "out.wav", voice="Brian", prev="...", next_="...")

Beats rendered one at a time sound like separate takes unless each call gets the
neighbouring lines as previous_text / next_text — always pass them for a reel.
"""
import json, os, subprocess, sys, tempfile, urllib.request, urllib.error

API = "https://api.elevenlabs.io/v1"
MODEL = os.environ.get("ELEVEN_MODEL", "eleven_multilingual_v2")
DEFAULT_VOICE = os.environ.get("ELEVEN_VOICE", "Brian")
# Premade voices every account has; used when /voices can't be listed.
PREMADE = {
    "brian": "nPczCjzI2devNBz1zQrb",   # deep, resonant American narrator
    "george": "JBFqnCBsd6RMkjVDRZzb",  # warm British storyteller
    "daniel": "onwK4e9ZLuTAKqWW03F9",  # British news presenter
    "adam": "pNInz6obpgDQGcFmaJgB",
}
SETTINGS = {"stability": 0.45, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True}


class NoKey(RuntimeError):
    pass


def api_key():
    k = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if k:
        return k
    r = subprocess.run(["security", "find-generic-password", "-s", "elevenlabs", "-w"],
                       capture_output=True, text=True)
    k = r.stdout.strip()
    if r.returncode != 0 or not k:
        raise NoKey('no ElevenLabs key: run  security add-generic-password -a "$USER" -s elevenlabs -w')
    return k


def _req(path, body=None, accept="application/json"):
    req = urllib.request.Request(API + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"xi-api-key": api_key(), "Accept": accept,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"ElevenLabs {e.code} on {path.split('?')[0]}: {detail}") from None


def voices():
    return json.loads(_req("/voices")).get("voices", [])


def resolve_voice(v):
    if len(v) >= 20 and v.isalnum():
        return v
    try:
        for x in voices():
            if x.get("name", "").split(" ")[0].lower() == v.lower() or x.get("name", "").lower() == v.lower():
                return x["voice_id"]
    except RuntimeError:
        pass
    if v.lower() in PREMADE:
        return PREMADE[v.lower()]
    raise RuntimeError(f"voice '{v}' not found on this account")


def synth(text, out_wav, voice=DEFAULT_VOICE, prev=None, next_=None, settings=None):
    body = {"text": text, "model_id": MODEL, "voice_settings": settings or SETTINGS}
    if prev:
        body["previous_text"] = prev
    if next_:
        body["next_text"] = next_
    mp3 = _req(f"/text-to-speech/{resolve_voice(voice)}?output_format=mp3_44100_128", body, "audio/mpeg")
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3)
        tmp = f.name
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-ar", "48000", "-ac", "2", out_wav], check=True)
    finally:
        os.unlink(tmp)
    return out_wav


def check():
    s = json.loads(_req("/user/subscription"))
    used, limit = s.get("character_count", 0), s.get("character_limit", 0)
    return {"tier": s.get("tier"), "characters_left": limit - used, "limit": limit}


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if not a or a[0] == "check":
            print(json.dumps(check()))
        elif a[0] == "voices":
            for x in voices():
                print(f"{x['voice_id']}  {x.get('name')}  [{x.get('category')}]")
        elif a[0] == "say":
            opts = {"voice": DEFAULT_VOICE, "prev": None, "next_": None}
            text, out, rest = a[1], a[2], a[3:]
            for flag, key in (("--voice", "voice"), ("--prev", "prev"), ("--next", "next_")):
                if flag in rest:
                    opts[key] = rest[rest.index(flag) + 1]
            print(synth(text, out, **opts))
    except NoKey as e:
        print(e, file=sys.stderr)
        sys.exit(3)
