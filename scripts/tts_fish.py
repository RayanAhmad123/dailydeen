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

# Optional voice-clone reference. Drop a 10-30s clip + its exact transcript:
#   refs/reference.wav   (the audio)
#   refs/reference.txt   (the words spoken in it, verbatim)
# Override paths with REF_AUDIO / REF_TEXT env vars. If the audio file is
# missing, the model's default voice is used.
REF_AUDIO = Path(os.environ.get("REF_AUDIO", ROOT / "refs" / "reference.wav"))
REF_TEXT = Path(os.environ.get("REF_TEXT", ROOT / "refs" / "reference.txt"))


def load_reference():
    """Return a [{audio, text}] list for voice cloning, or [] if no reference."""
    if not REF_AUDIO.exists():
        return []
    audio_bytes = REF_AUDIO.read_bytes()
    text = REF_TEXT.read_text().strip() if REF_TEXT.exists() else ""
    if not text:
        print(f"WARNING: {REF_AUDIO.name} found but no transcript at "
              f"{REF_TEXT}; cloning works best with the exact transcript.",
              file=sys.stderr)
    print(f"Voice cloning from {REF_AUDIO} ({len(audio_bytes)/1024:.0f} KB)", file=sys.stderr)
    return [{"audio": audio_bytes, "text": text}]


def synthesize(text: str) -> bytes:
    references = load_reference()
    payload = {
        "text": text,
        "format": "wav",
        "normalize": True,
        "streaming": False,
        "references": references,
    }
    url = f"{BASE_URL}/v1/tts"

    # References carry raw audio bytes, which only round-trip cleanly via
    # msgpack. Refuse to silently drop the chosen voice on the JSON fallback.
    if references and ormsgpack is None:
        sys.exit("ormsgpack is required for voice cloning (pip install ormsgpack).")

    # Preferred: msgpack (fish-speech's native API encoding)
    if ormsgpack is not None:
        r = requests.post(
            url,
            data=ormsgpack.packb(payload),
            headers={"Content-Type": "application/msgpack"},
            timeout=2400,
        )
        if r.ok:
            return r.content
        print(f"msgpack request failed ({r.status_code}), trying JSON...", file=sys.stderr)

    r = requests.post(url, json=payload, timeout=2400)
    r.raise_for_status()
    return r.content


def main():
    script = json.loads((ROOT / "work" / "script.json").read_text())
    body = script.get("body") or script["simplified"]
    outro = script.get("cta_spoken") or script.get("reference_spoken", "")
    full_text = f"{script['hook']} ... {body} ... {outro}"

    audio = synthesize(full_text)

    out_dir = ROOT / "public" / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{script['id']}.wav"
    out.write_bytes(audio)
    print(f"Audio written: {out} ({len(audio)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
