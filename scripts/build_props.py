#!/usr/bin/env python3
"""Assemble src/videoData.json from script.json + timings.json + audio duration."""
import difflib, json, subprocess
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


def correct_spelling(timings: list, script_text: str) -> list:
    """Whisper occasionally misspells on-screen words ("Sahib Bukhari",
    "Al-Jubber" for al-jabr) and may merge/split tokens. Rebuild the word
    list so it is EXACTLY the script's words, anchored to Whisper's times:
    equal blocks map 1:1; replace blocks spread the block's time span evenly
    over the script words; script words Whisper missed get interpolated
    times; extra Whisper tokens are dropped."""
    script_words = script_text.split()
    sm = difflib.SequenceMatcher(
        a=[normalize(w["word"]) for w in timings],
        b=[normalize(w) for w in script_words],
        autojunk=False,
    )
    out = []
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op == "equal":
            for k in range(b1 - b0):
                out.append({**timings[a0 + k], "word": script_words[b0 + k]})
        elif op == "replace":
            span_start = timings[a0]["start"]
            span_end = timings[a1 - 1]["end"]
            n = b1 - b0
            step = (span_end - span_start) / n
            for k in range(n):
                out.append({
                    "word": script_words[b0 + k],
                    "start": round(span_start + k * step, 3),
                    "end": round(span_start + (k + 1) * step, 3),
                })
        elif op == "insert":
            prev_end = out[-1]["end"] if out else 0.0
            next_start = timings[a0]["start"] if a0 < len(timings) else prev_end + 0.3
            n = b1 - b0
            step = max(next_start - prev_end, 0.06 * n) / n
            for k in range(n):
                out.append({
                    "word": script_words[b0 + k],
                    "start": round(prev_end + k * step, 3),
                    "end": round(prev_end + (k + 1) * step, 3),
                })
        # "delete": extra Whisper tokens — skip them
    return out


def main():
    work = ROOT / "work"
    script = json.loads((work / "script.json").read_text())
    timings = json.loads((work / "timings.json").read_text())

    body_text = script.get("body") or script.get("simplified", "")
    outro_text = script.get("cta_spoken") or script.get("reference_spoken", "")
    spoken = f"{script['hook']} {body_text} {outro_text}".strip()
    timings = correct_spelling(timings, spoken)

    vid = script["id"]
    audio_file = ROOT / "public" / "audio" / f"{vid}.wav"
    duration = audio_duration(audio_file)

    # Split timed words into hook / body / outro (CTA) by word counts of the script parts
    hook_count = len(script["hook"].split())
    outro_spoken = script.get("cta_spoken") or script.get("reference_spoken", "")
    ref_count = len(outro_spoken.split())
    hook_words = timings[:hook_count]
    ref_words = timings[len(timings) - ref_count:] if ref_count < len(timings) else []
    # CTA words stay in the karaoke captions; the reference card timing keys off CTA start
    body_words = timings[hook_count:]

    data = {
        "id": vid,
        "category": script["category"],
        "hook": {"text": script["hook"], "words": hook_words},
        "body": {"words": body_words},
        "reference": {
            "text": script["reference_display"],
            "startSec": ref_words[0]["start"] if ref_words else max(duration - 3, 0),
        },
        "audioFile": f"audio/{vid}.wav",
        "durationSec": round(duration, 2),
    }

    # AI story illustrations, if generate_scenes.py ran
    scenes_out = work / "scenes_out.json"
    if scenes_out.exists():
        data["scenes"] = json.loads(scenes_out.read_text())["scenes"]

    (ROOT / "src" / "videoData.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"videoData.json written ({duration:.1f}s, {len(timings)} words)")


if __name__ == "__main__":
    main()
