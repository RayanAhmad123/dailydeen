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
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_reflection import trim_clip, pick_clip  # shared footage helpers

TAIL_SEC = 1.2  # hold after the recitation ends
HASHTAGS = ["islam", "quran", "recitation", "islamicreminders", "muslim", "deen", "shorts"]
SEGMENT_MIN_SEC = 25  # long multi-ayah passages get one-ayah-at-a-time display
TEXT_API = "https://api.alquran.cloud/v1/ayah/{s}:{a}/editions/quran-uthmani,en.sahih"


def load(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def make_segments(ayah):
    """Per-ayah display segments for long passages: authoritative text per ayah
    from api.alquran.cloud + timings from the cached recitation parts. Returns
    None (static full-text display) for short passages or on any failure."""
    if float(ayah["durationSec"]) < SEGMENT_MIN_SEC:
        return None
    m = re.fullmatch(r"Quran (\d+):(\d+)-(\d+)", ayah["reference"])
    if not m:
        return None
    s, a0, a1 = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        segments, t = [], 0.0
        for a in range(a0, a1 + 1):
            part = ROOT / "assets" / "recitations" / "_parts" / f"{s:03d}{a:03d}.mp3"
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(part)], capture_output=True, text=True, check=True)
            length = float(r.stdout.strip())
            with urllib.request.urlopen(TEXT_API.format(s=s, a=a), timeout=30) as resp:
                d = json.loads(resp.read().decode())["data"]
            ar = next(e["text"] for e in d if e["edition"]["identifier"] == "quran-uthmani")
            en = next(e["text"] for e in d if e["edition"]["identifier"] == "en.sahih")
            segments.append({"arabic": ar, "translation": en.replace("[", "").replace("]", ""),
                             "startSec": round(t, 2), "endSec": round(t + length, 2)})
            t += length
        # text accuracy is non-negotiable: joined segments must equal the bank entry
        if " ".join(x["arabic"] for x in segments) != ayah["arabic"]:
            raise ValueError("Arabic mismatch vs bank")
        if " ".join(x["translation"] for x in segments) != ayah["translation"]:
            raise ValueError("Translation mismatch vs bank")
        if abs(t - float(ayah["durationSec"])) > 0.2:
            raise ValueError(f"part durations {t:.2f}s != recitation {ayah['durationSec']}s")
        return segments
    except Exception as e:  # noqa: BLE001 — fall back to static display, never block the build
        print(f"  ! segments unavailable ({e}) — using static full-text display")
        return None


def main():
    ayat = load(ROOT / "content" / "ayat.json", {"ayat": []})["ayat"]
    if not ayat:
        raise SystemExit("content/ayat.json is empty — run scripts/fetch_ayat.py first.")
    footage = load(ROOT / "content" / "footage.json", {"clips": []})["clips"]
    state = load(ROOT / "state" / "ayah.json", {"used": [], "used_clips": [], "last": None})

    unused = [a for a in ayat if a["id"] not in set(state["used"])]
    if not unused:
        raise SystemExit(
            "AYAH BANK EXHAUSTED — every entry in content/ayat.json is used. "
            "Add new ayat (fetch_ayat.py), pre-render their montages "
            "(scripts/build_montages.py) and update the cloud-assets release."
        )
    ayah = unused[0]
    vid = ayah["id"]

    # Recitation -> public/ so the composition can play it
    src_audio = ROOT / "assets" / ayah["audio"]
    if not src_audio.exists():
        raise SystemExit(f"Recitation missing: {src_audio} — run scripts/fetch_ayat.py")
    pub_audio = ROOT / "public" / "recitation" / f"{vid}.mp3"
    pub_audio.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_audio, pub_audio)
    dur = round(float(ayah["durationSec"]) + TAIL_SEC, 2)

    # Pre-rendered montage (built + frame-reviewed via scripts/build_montages.py,
    # shipped in the cloud-assets release) takes priority — this is what the
    # unattended GitHub Actions run uses. Falls back to live footage trimming.
    clip = None
    clip_rel = None
    pre = ROOT / "assets" / "prerendered" / f"{vid}.mp4"
    if pre.exists():
        out = ROOT / "public" / "reflection" / f"{vid}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pre, out)
        clip_rel = f"reflection/{vid}.mp4"
        print(f"  footage: prerendered montage {pre.name}")
    else:
        clip = pick_clip(footage, ayah.get("theme"), set(state["used_clips"]))
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
    segments = make_segments(ayah)
    if segments:
        props["segments"] = segments
        print(f"  {len(segments)} per-ayah segments (long passage — one ayah at a time)")
    (ROOT / "src" / "ayahData.json").write_text(json.dumps(props, indent=2, ensure_ascii=False))

    hashtags = " ".join("#" + t for t in HASHTAGS)
    # Curated per-ayah title from the bank (the auto-fallback truncates mid-word,
    # which every manual run has had to fix — unattended runs need the curated one).
    title = ayah.get("title") or f"{ayah['translation'][:60].rstrip('.,')} | {ayah['reference']}"
    meta = {
        "title": title,
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

    # Cadence bookkeeping + the id handoff upload_postpeer.py reads
    cad_p = ROOT / "state" / "cadence.json"
    cad = load(cad_p, {})
    cad["last_format"] = "ayah"
    cad["last_id"] = vid
    cad_p.write_text(json.dumps(cad, indent=2, ensure_ascii=False))
    (ROOT / "work").mkdir(exist_ok=True)
    (ROOT / "work" / "script.json").write_text(json.dumps({"id": vid}))

    print(f"Ayah video ready: id={vid}  {ayah['reference']}  ({dur}s, audio baked)")
    print(f"  {ayah['translation']}")
    print(f"  clip: {clip_rel or '(quote over themed background)'}")
    print(f"  render: npx remotion render AyahVideo --props=src/ayahData.json --output=output/videos/{vid}.mp4")


if __name__ == "__main__":
    main()
