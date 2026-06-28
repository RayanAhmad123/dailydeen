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
TARGET_SEC = 15  # uniform short length (short-form retention; long enough to read a quote)
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


COVER = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
# Some clips are shot in portrait but stored as landscape with no rotation flag,
# so the scene is on its side — fix with a transpose before the cover-crop.
ROTATE = {"cw": "transpose=1,", "ccw": "transpose=2,", "180": "transpose=2,transpose=2,"}


def _encode(args, vf_in, dur, out_path):
    subprocess.run(["ffmpeg", "-y", *args, "-an", "-vf", vf_in, "-t", str(dur),
                    "-r", "30", "-c:v", "libx264", "-preset", "medium",
                    "-pix_fmt", "yuv420p", str(out_path)], check=True, capture_output=True)


def trim_clip(src_abs, start, avail, target, out_path, rotate=None):
    """Rotate (if needed) then crop-to-cover 9:16, mute, 30fps. If the clean
    shot is shorter than the target, loop it to fill (no mid-video hard cut)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    vf = ROTATE.get(rotate, "") + COVER
    if avail >= target:
        _encode(["-ss", str(start), "-i", str(src_abs)], vf, target, out_path)
    else:
        tmp = out_path.with_name("_seg_" + out_path.name)
        _encode(["-ss", str(start), "-i", str(src_abs)], vf, round(avail, 2), tmp)
        subprocess.run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(tmp),
                        "-t", str(target), "-c", "copy", str(out_path)],
                       check=True, capture_output=True)
        tmp.unlink(missing_ok=True)


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
    dur = TARGET_SEC
    if clip:
        src_abs = ROOT / "assets" / "footage" / clip["src"]
        if not src_abs.exists():
            print(f"  ! curated clip missing on disk: {src_abs} — rendering quote-only")
            clip = None
        else:
            avail = float(clip.get("dur", TARGET_SEC))
            out = ROOT / "public" / "reflection" / f"{vid}.mp4"
            print(f"  trimming {clip['src']} @ {clip.get('start', 0)}s -> {dur}s"
                  + (f"  (rotate {clip['rotate']})" if clip.get("rotate") else "")
                  + ("  (looped)" if avail < dur else "") + f"  {out.name}")
            trim_clip(src_abs, clip.get("start", 0), avail, dur, out, clip.get("rotate"))
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

    # Advance rotation state so the next run picks a fresh quote/clip
    if vid not in state["used_quotes"]:
        state["used_quotes"].append(vid)
    if clip and clip["id"] not in state["used_clips"]:
        state["used_clips"].append(clip["id"])
    state["last"] = vid
    (ROOT / "state").mkdir(exist_ok=True)
    (ROOT / "state" / "reflection.json").write_text(json.dumps(state, indent=2, ensure_ascii=False))

    print(f"Reflection ready: id={vid}")
    print(f"  quote : \"{q['text']}\"  ({q['source']})")
    print(f"  clip  : {clip_rel or '(none — quote over themed background)'}")
    print(f"  render: npx remotion render ReflectionVideo --props=src/reflectionData.json --output=output/videos/{vid}.mp4")


if __name__ == "__main__":
    main()
