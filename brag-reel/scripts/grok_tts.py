#!/usr/bin/env python3
"""Grok (xAI) voiceover for brag-reel, plus a local Whisper listen-back. Standard library only.

Key: $XAI_API_KEY, else the macOS keychain item `xai`:
    security add-generic-password -a "$USER" -s xai -w
Read at call time; never printed, logged or written to disk. Do not pull it out of
another app's encrypted store (OpenWhispr keeps its own copy) — ask the user instead.

CLI:
    grok_tts.py check                         # key present? (exit 3 = no key)
    grok_tts.py say "text" out.wav [--voice leo]
    grok_tts.py listen out.wav                # local whisper.cpp transcript of a line

Voices: leo (authoritative, male) · rex (professional, male) · sal (neutral, male)
        eve (energetic, female; xAI default) · ara (warm, female)
"""
import json, os, re, subprocess, sys, tempfile, urllib.error, urllib.request

API = "https://api.x.ai/v1/tts"
VOICE = os.environ.get("GROK_VOICE", "leo")
WHISPER = os.environ.get("WHISPER_CLI", "/opt/homebrew/bin/whisper-cli")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", os.path.expanduser("~/Hermes/whisper.cpp/models/ggml-base.en.bin"))


class NoKey(RuntimeError):
    pass


def api_key():
    k = os.environ.get("XAI_API_KEY", "").strip()
    if k:
        return k
    r = subprocess.run(["security", "find-generic-password", "-s", "xai", "-w"], capture_output=True, text=True)
    k = r.stdout.strip()
    if r.returncode != 0 or not k:
        raise NoKey('no xAI key: run  security add-generic-password -a "$USER" -s xai -w')
    return k


def synth(text, out_wav, voice=VOICE, prev=None, next_=None, language="en"):
    """prev/next_ are accepted for parity with other engines; Grok TTS takes no context."""
    body = json.dumps({"text": text, "voice_id": voice, "language": language}).encode()
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            audio = r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"xAI TTS {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(audio)
        tmp = f.name
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-ar", "48000", "-ac", "2", out_wav], check=True)
    finally:
        os.unlink(tmp)
    return out_wav


def listen(wav):
    """Transcribe a rendered line locally so a mispronounced word is caught before the mix."""
    with tempfile.TemporaryDirectory() as d:
        mono = f"{d}/in.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-ar", "16000", "-ac", "1", mono], check=True)
        out = subprocess.run([WHISPER, "-m", WHISPER_MODEL, "-f", mono, "-nt", "-np", "-t", "4"],
                             capture_output=True, text=True).stdout
    return " ".join(out.split())


def _words(s):
    return re.findall(r"[a-z0-9']+", s.lower().replace("’", "'"))


def match(script, heard):
    """Share of script words Whisper heard (order-free). Brand names may legitimately miss."""
    want, got = _words(script), set(_words(heard))
    return sum(w in got for w in want) / max(1, len(want))


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if not a or a[0] == "check":
            api_key()
            print("xai key: present")
        elif a[0] == "say":
            v = a[a.index("--voice") + 1] if "--voice" in a else VOICE
            print(synth(a[1], a[2], voice=v))
        elif a[0] == "listen":
            print(listen(a[1]))
    except NoKey as e:
        print(e, file=sys.stderr)
        sys.exit(3)
