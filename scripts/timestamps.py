#!/usr/bin/env python3
"""Word-level timestamps with Whisper -> work/timings.json

Deps: pip install openai-whisper  (or use whisper.cpp / mlx-whisper on Apple Silicon)
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    script = json.loads((ROOT / "work" / "script.json").read_text())
    audio_path = ROOT / "public" / "audio" / f"hadith_{script['hadith_no']}.wav"

    import whisper

    model = whisper.load_model("base.en")
    result = model.transcribe(str(audio_path), word_timestamps=True, language="en", fp16=False)

    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": round(w["start"], 3),
                "end": round(w["end"], 3),
            })

    if not words:
        print("Whisper returned no words", file=sys.stderr)
        sys.exit(1)

    (ROOT / "work" / "timings.json").write_text(json.dumps(words, indent=2))
    print(f"{len(words)} words timed, audio ends at {words[-1]['end']}s")


if __name__ == "__main__":
    main()
