#!/usr/bin/env python3
"""Assemble src/videoData.json from script.json + timings.json + audio duration."""
import json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def normalize(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def main():
    work = ROOT / "work"
    script = json.loads((work / "script.json").read_text())
    timings = json.loads((work / "timings.json").read_text())

    n = script["hadith_no"]
    audio_file = ROOT / "public" / "audio" / f"hadith_{n}.wav"
    duration = audio_duration(audio_file)

    # Split timed words into hook / body / reference by word counts of the script parts
    hook_count = len(script["hook"].split())
    ref_count = len(script["reference_spoken"].split())
    hook_words = timings[:hook_count]
    ref_words = timings[len(timings) - ref_count:] if ref_count < len(timings) else []
    body_words = timings[hook_count: len(timings) - ref_count]

    data = {
        "hadithNo": int(n) if str(n).isdigit() else n,
        "chapter": script["chapter"],
        "hook": {"text": script["hook"], "words": hook_words},
        "body": {"words": body_words},
        "reference": {
            "text": script["reference_display"],
            "startSec": ref_words[0]["start"] if ref_words else max(duration - 3, 0),
        },
        "audioFile": f"audio/hadith_{n}.wav",
        "durationSec": round(duration, 2),
    }

    (ROOT / "src" / "videoData.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"videoData.json written ({duration:.1f}s, {len(timings)} words)")


if __name__ == "__main__":
    main()
