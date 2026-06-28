#!/usr/bin/env python3
"""Assemble a ReflectionVideo: pick a quote + a curated clip, trim/crop/mute the
clip to a 9:16 silent file, and write src/reflectionData.json + upload metadata.

Footage is optional: with no curated clips yet it renders the quote over the
themed background so the format can be previewed. Quran recitation is NOT baked
in — it's added from the platform audio library at post time.

Run:  python3 scripts/build_reflection.py
Then: npx remotion render ReflectionVideo --props=src/reflectionData.json --output=output/videos/<id>.mp4
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DUR_MIN, DUR_MAX = 16, 20
HASHTAG_BASE = ["islam", "islamicreminders", "muslim", "quran", "deen", "shorts"]


def load(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def pick_quote(quotes, used):
    unused = [q for q in quotes if q["id"] not in used]
    return (unused or quotes)[0]


def pick_clip(clips, theme, used):
    if not clips:
        return None
    pools = [
        [c for c in clips if c.get("theme") == theme and c["id"] not in used],
        [c for c in clips if c["id"] not in used],
        [c for c in clips if c.get("theme") == theme],
        clips,
    ]
    for pool in pools:
        if pool:
            return pool[0]
    return None


def trim_clip(src_abs, start, dur, out_path):
    """Crop-to-cover 9:16, mute, 30fps, fixed duration."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-t", str(dur), "-i", str(src_abs),
        "-an",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
        "-r", "30", "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def main():
    quotes = load(ROOT / "content" / "quotes.json", {"quotes": []})["quotes"]
    if not quotes:
        raise SystemExit("content/quotes.json has no quotes.")
    footage = load(ROOT / "content" / "footage.json", {"clips": []})["clips"]
    state = load(ROOT / "state" / "reflection.json",
                 {"used_quotes": [], "used_clips": [], "last": None})

    q = pick_quote(quotes, set(state["used_quotes"]))
    vid = q["id"]
    clip = pick_clip(footage, q.get("theme"), set(state["used_clips"]))

    clip_rel = None
    dur = DUR_MAX
    if clip:
        src_abs = ROOT / "assets" / "footage" / clip["src"]
        if not src_abs.exists():
            print(f"  ! curated clip missing on disk: {src_abs} — rendering quote-only")
            clip = None
        else:
            dur = max(DUR_MIN, min(DUR_MAX, int(clip.get("dur", DUR_MAX))))
            out = ROOT / "public" / "reflection" / f"{vid}.mp4"
            print(f"  trimming {clip['src']} @ {clip.get('start', 0)}s for {dur}s -> {out.name}")
            trim_clip(src_abs, clip.get("start", 0), dur, out)
            clip_rel = f"reflection/{vid}.mp4"

    props = {"id": vid, "quote": q["text"], "source": q["source"],
             "clipFile": clip_rel, "durationSec": dur}
    (ROOT / "src" / "reflectionData.json").write_text(
        json.dumps(props, indent=2, ensure_ascii=False))

    # Upload metadata (same shape the upload scripts expect)
    raw_tags = HASHTAG_BASE + ([q["theme"]] if q.get("theme") else [])
    tags = list(dict.fromkeys(raw_tags))  # de-dup, order-preserving
    hashtags = " ".join("#" + t for t in tags)
    title_short = q["text"].rstrip(".")[:70]
    meta = {
        "title": f"{title_short} | Daily Islamic Reminders",
        "description": f"\"{q['text']}\"\n\n{q['source']}\n\n{hashtags}",
        "caption": f"\"{q['text']}\" - {q['source']} {hashtags}"[:2200],
        "tags": tags,
        "video": f"output/videos/{vid}.mp4",
        "needs_audio": "Add a Quran recitation from the app's audio library before posting.",
    }
    out_dir = ROOT / "output" / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{vid}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    print(f"Reflection ready: id={vid}")
    print(f"  quote : \"{q['text']}\"  ({q['source']})")
    print(f"  clip  : {clip_rel or '(none — quote over themed background)'}")
    print(f"  render: npx remotion render ReflectionVideo --props=src/reflectionData.json --output=output/videos/{vid}.mp4")


if __name__ == "__main__":
    main()
