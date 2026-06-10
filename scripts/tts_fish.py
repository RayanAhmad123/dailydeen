#!/usr/bin/env python3
"""Generate voiceover via a self-hosted Fish Speech API server.

Reads work/script.json (hook, simplified, reference_spoken) and writes
public/audio/hadith_<N>.wav.

Requires the Fish Speech API server running locally, e.g.:
  python -m tools.api_server --listen 0.0.0.0:8080 ...
Configure with env var FISH_SPEECH_URL (default http://127.0.0.1:8080).

Deps: pip install requests ormsgpack
"""
import json, os, sys
from pathlib import Path

import requests

try:
    import ormsgpack
except ImportError:
    ormsgpack = None

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("FISH_SPEECH_URL", "http://127.0.0.1:8080")


def synthesize(text: str) -> bytes:
    payload = {
        "text": text,
        "format": "wav",
        "normalize": True,
        "streaming": False,
        # For voice cloning later: add "references": [{"audio": <bytes>, "text": "..."}]
    }
    url = f"{BASE_URL}/v1/tts"

    # Preferred: msgpack (fish-speech's native API encoding)
    if ormsgpack is not None:
        r = requests.post(
            url,
            data=ormsgpack.packb(payload),
            headers={"Content-Type": "application/msgpack"},
            timeout=600,
        )
        if r.ok:
            return r.content
        print(f"msgpack request failed ({r.status_code}), trying JSON...", file=sys.stderr)

    r = requests.post(url, json=payload, timeout=600)
    r.raise_for_status()
    return r.content


def main():
    script = json.loads((ROOT / "work" / "script.json").read_text())
    full_text = f"{script['hook']} ... {script['simplified']} ... {script['reference_spoken']}"

    audio = synthesize(full_text)

    out_dir = ROOT / "public" / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"hadith_{script['hadith_no']}.wav"
    out.write_bytes(audio)
    print(f"Audio written: {out} ({len(audio)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
