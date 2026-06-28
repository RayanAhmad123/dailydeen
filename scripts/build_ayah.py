#!/usr/bin/env python3
"""Assemble an AyahVideo: pick an ayah + a curated clip, copy the matching
recitation into public/, trim/rotate/mute the footage to 9:16 looped to the
recitation length, and write src/ayahData.json + upload metadata.

The recitation is baked into the render (via the composition's <Audio>), so the
video posts directly with sound — no in-app audio step.

Run:  python3 scripts/build_ayah.py
Then: npx remotion render AyahVideo --props=src/ayahData.json --output=output/videos/<id>.mp4
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_reflection import trim_clip, pick_clip  # shared footage helpers

TAIL_SEC = 1.2  # hold after the recitation ends
HASHTAGS = ["islam", "quran", "recitation", "islamicreminders", "muslim", "deen", "shorts"]


def load(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def main():
    ayat = load(ROOT / "content" / "ayat.json", {"ayat": []})["ayat"]
    if not ayat:
        raise SystemExit("content/ayat.json is empty — run scripts/fetch_ayat.py first.")
    footage = load(ROOT / "content" / "footage.json", {"clips": []})["clips"]
    state = load(ROOT / "state" / "ayah.json", {"used": [], "used_clips": [], "last": None})

    unused = [a for a in ayat if a["id"] not in set(state["used"])]
    ayah = (unused or ayat)[0]
    vid = ayah["id"]

    # Recitation -> public/ so the composition can play it
    src_audio = ROOT / "assets" / ayah["audio"]
    if not src_audio.exists():
        raise SystemExit(f"Recitation missing: {src_audio} — run scripts/fetch_ayat.py")
    pub_audio = ROOT / "public" / "recitation" / f"{vid}.mp3"
    pub_audio.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_audio, pub_audio)
    dur = round(float(ayah["durationSec"]) + TAIL_SEC, 2)

    clip = pick_clip(footage, ayah.get("theme"), set(state["used_clips"]))
    clip_rel = None
    if clip:
        clip_abs = ROOT / "assets" / "footage" / clip["src"]
        if clip_abs.exists():
            out = ROOT / "public" / "reflection" / f"{vid}.mp4"
            print(f"  footage {clip['src']}"
                  + (f" (rotate {clip['rotate']})" if clip.get("rotate") else "")
                  + f" -> {dur}s")
            trim_clip(clip_abs, clip.get("start", 0), float(clip.get("dur", dur)), dur, out, clip.get("rotate"))
            clip_rel = f"reflection/{vid}.mp4"

    props = {"id": vid, "arabic": ayah["arabic"], "translation": ayah["translation"],
             "reference": ayah["reference"], "clipFile": clip_rel,
             "audioFile": f"recitation/{vid}.mp3", "durationSec": dur}
    (ROOT / "src" / "ayahData.json").write_text(json.dumps(props, indent=2, ensure_ascii=False))

    hashtags = " ".join("#" + t for t in HASHTAGS)
    meta = {
        "title": f"{ayah['translation'][:60].rstrip('.,')} | {ayah['reference']}",
        "description": f"{ayah['translation']}\n\n{ayah['reference']} - recitation by {ayah.get('reciter','')}\n\n{hashtags}",
        "caption": f"{ayah['translation']} {ayah['reference']} {hashtags}"[:2200],
        "tags": HASHTAGS,
        "video": f"output/videos/{vid}.mp4",
    }
    out_dir = ROOT / "output" / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{vid}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    # Advance rotation
    if vid not in state["used"]:
        state["used"].append(vid)
    if clip and clip["id"] not in state["used_clips"]:
        state["used_clips"].append(clip["id"])
    state["last"] = vid
    (ROOT / "state").mkdir(exist_ok=True)
    (ROOT / "state" / "ayah.json").write_text(json.dumps(state, indent=2, ensure_ascii=False))

    print(f"Ayah video ready: id={vid}  {ayah['reference']}  ({dur}s, audio baked)")
    print(f"  {ayah['translation']}")
    print(f"  clip: {clip_rel or '(quote over themed background)'}")
    print(f"  render: npx remotion render AyahVideo --props=src/ayahData.json --output=output/videos/{vid}.mp4")


if __name__ == "__main__":
    main()
