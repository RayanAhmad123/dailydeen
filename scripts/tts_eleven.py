#!/usr/bin/env python3
"""Generate the voiceover via the ElevenLabs API.

Reads work/script.json (hook, body, cta_spoken) and writes public/audio/<id>.wav
(same contract as tts_fish.py, so the rest of the pipeline is unchanged).

The HOOK is synthesized as its own segment with a more direct, energetic
delivery (lower stability, higher style, speaker boost) and a small loudness
boost, then concatenated with the body+CTA segment. This makes the opening
line punch so it grabs the viewer in the first second. Tune via env vars below.

Env:
  ELEVENLABS_API_KEY  (required)
  ELEVEN_VOICE_ID     voice to use; if unset, ELEVEN_VOICE_NAME (default "Max")
                      is looked up in your voice library
  ELEVEN_MODEL        default "eleven_multilingual_v2"
  ELEVEN_FORMAT       default "mp3_44100_128" (highest non-Pro tier format)

  Hook delivery (the "loud, direct" opener):
  ELEVEN_HOOK_STABILITY   default 0.30  (lower = more dynamic/punchy)
  ELEVEN_HOOK_STYLE       default 0.55  (higher = more emphatic)
  ELEVEN_HOOK_GAIN_DB     default 3.0   (extra loudness on the hook, dB)
  Body/CTA delivery (calm, clear):
  ELEVEN_BODY_STABILITY   default 0.50
  ELEVEN_BODY_STYLE       default 0.0
  ELEVEN_HOOK_PAUSE       default 0.35  (silence between hook and body, sec)

Deps: requests + ffmpeg (for mp3 -> wav, gain, concat).
"""
import json, os, subprocess, sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.elevenlabs.io/v1"


def resolve_voice_id(headers: dict) -> str:
    if os.environ.get("ELEVEN_VOICE_ID"):
        return os.environ["ELEVEN_VOICE_ID"]
    wanted = os.environ.get("ELEVEN_VOICE_NAME", "Max").lower()
    r = requests.get(f"{API}/voices", headers=headers, timeout=30)
    r.raise_for_status()
    voices = r.json()["voices"]
    for v in voices:
        if wanted in v["name"].lower():
            print(f"Using voice: {v['name']} ({v['voice_id']})", file=sys.stderr)
            return v["voice_id"]
    names = ", ".join(v["name"] for v in voices) or "(none)"
    sys.exit(f"No voice matching '{wanted}' in your library. Available: {names}\n"
             f"Set ELEVEN_VOICE_ID or ELEVEN_VOICE_NAME.")


def synth(text: str, voice_id: str, model: str, fmt: str,
          headers: dict, settings: dict, out_mp3: Path) -> None:
    """Synthesize one segment to an mp3 file."""
    r = requests.post(
        f"{API}/text-to-speech/{voice_id}",
        params={"output_format": fmt},
        headers=headers,
        json={"text": text, "model_id": model, "voice_settings": settings},
        timeout=120,
    )
    if not r.ok:
        sys.exit(f"ElevenLabs error {r.status_code}: {r.text[:300]}")
    out_mp3.write_bytes(r.content)


def main():
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set (get one at elevenlabs.io -> Profile -> API Keys)")
    headers = {"xi-api-key": key}

    script = json.loads((ROOT / "work" / "script.json").read_text())
    hook = script["hook"].strip()
    body = (script.get("body") or script["simplified"]).strip()
    outro = (script.get("cta_spoken") or script.get("reference_spoken", "")).strip()
    # Controlled pause before the CTA via ElevenLabs <break> (works on v2/v3;
    # keep <=3s and sparse to avoid audio instability). Tune with ELEVEN_CTA_BREAK.
    cta_break = os.environ.get("ELEVEN_CTA_BREAK", "0.6")
    body_text = f'{body} <break time="{cta_break}s" /> {outro}' if outro else body

    voice_id = resolve_voice_id(headers)
    model = os.environ.get("ELEVEN_MODEL", "eleven_multilingual_v2")
    fmt = os.environ.get("ELEVEN_FORMAT", "mp3_44100_128")

    def fenv(name: str, default: float) -> float:
        try:
            return float(os.environ.get(name, default))
        except ValueError:
            return default

    hook_settings = {
        "stability": fenv("ELEVEN_HOOK_STABILITY", 0.30),
        "similarity_boost": 0.75,
        "style": fenv("ELEVEN_HOOK_STYLE", 0.55),
        "use_speaker_boost": True,
    }
    body_settings = {
        "stability": fenv("ELEVEN_BODY_STABILITY", 0.50),
        "similarity_boost": 0.75,
        "style": fenv("ELEVEN_BODY_STYLE", 0.0),
        "use_speaker_boost": True,
    }
    gain_db = fenv("ELEVEN_HOOK_GAIN_DB", 3.0)
    pause = fenv("ELEVEN_HOOK_PAUSE", 0.35)

    out_dir = ROOT / "public" / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    vid = script["id"]

    hook_mp3 = out_dir / f"{vid}.hook.mp3"
    body_mp3 = out_dir / f"{vid}.body.mp3"
    hook_wav = out_dir / f"{vid}.hook.wav"
    body_wav = out_dir / f"{vid}.body.wav"
    sil_wav = out_dir / f"{vid}.sil.wav"
    wav = out_dir / f"{vid}.wav"

    try:
        synth(hook, voice_id, model, fmt, headers, hook_settings, hook_mp3)
        synth(body_text, voice_id, model, fmt, headers, body_settings, body_mp3)

        # Hook: apply gain, then a soft limiter to stop the boost from clipping.
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(hook_mp3),
             "-af", f"volume={gain_db}dB,alimiter=limit=0.97",
             "-ac", "1", "-ar", "44100", str(hook_wav)],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(body_mp3),
             "-ac", "1", "-ar", "44100", str(body_wav)],
            check=True, capture_output=True,
        )
        # Short silence to recreate the natural hook->body pause.
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi",
             "-i", f"anullsrc=r=44100:cl=mono", "-t", str(pause), str(sil_wav)],
            check=True, capture_output=True,
        )
        # Concatenate hook + silence + body into the final mono wav.
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(hook_wav), "-i", str(sil_wav), "-i", str(body_wav),
             "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1",
             "-ac", "1", "-ar", "44100", str(wav)],
            check=True, capture_output=True,
        )
    finally:
        for f in (hook_mp3, body_mp3, hook_wav, body_wav, sil_wav):
            f.unlink(missing_ok=True)

    print(f"Audio written: {wav} ({wav.stat().st_size / 1024:.0f} KB) "
          f"[hook: stability={hook_settings['stability']}, style={hook_settings['style']}, +{gain_db}dB]")


if __name__ == "__main__":
    main()
