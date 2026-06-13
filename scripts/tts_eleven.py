#!/usr/bin/env python3
"""Generate the voiceover via the ElevenLabs API.

Reads work/script.json (hook, body, cta_spoken) and writes public/audio/<id>.wav
(same contract as tts_fish.py, so the rest of the pipeline is unchanged).

Env:
  ELEVENLABS_API_KEY  (required)
  ELEVEN_VOICE_ID     voice to use; if unset, ELEVEN_VOICE_NAME (default "Max")
                      is looked up in your voice library
  ELEVEN_MODEL        default "eleven_multilingual_v2"
  ELEVEN_FORMAT       default "mp3_44100_128" (highest non-Pro tier format)

Deps: requests + ffmpeg (for mp3 -> wav).
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


def main():
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set (get one at elevenlabs.io -> Profile -> API Keys)")
    headers = {"xi-api-key": key}

    script = json.loads((ROOT / "work" / "script.json").read_text())
    body = script.get("body") or script["simplified"]
    outro = script.get("cta_spoken") or script.get("reference_spoken", "")
    full_text = f"{script['hook']} ... {body} ... {outro}"

    voice_id = resolve_voice_id(headers)
    model = os.environ.get("ELEVEN_MODEL", "eleven_multilingual_v2")
    fmt = os.environ.get("ELEVEN_FORMAT", "mp3_44100_128")

    r = requests.post(
        f"{API}/text-to-speech/{voice_id}",
        params={"output_format": fmt},
        headers=headers,
        json={
            "text": full_text,
            "model_id": model,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=120,
    )
    if not r.ok:
        sys.exit(f"ElevenLabs error {r.status_code}: {r.text[:300]}")

    out_dir = ROOT / "public" / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    mp3 = out_dir / f"{script['id']}.mp3"
    mp3.write_bytes(r.content)

    wav = out_dir / f"{script['id']}.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp3), "-ac", "1", "-ar", "44100", str(wav)],
        check=True, capture_output=True,
    )
    mp3.unlink()
    print(f"Audio written: {wav} ({wav.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
