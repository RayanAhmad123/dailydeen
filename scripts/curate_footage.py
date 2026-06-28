#!/usr/bin/env python3
"""Curation pass over assets/footage/raw: split each clip into single-shot
segments (scene detection), drop too-short / mostly-black ones, and extract a
preview frame per candidate to assets/footage/curated/previews/.

Writes work/footage_candidates.json. A human (Claude) then reviews the preview
frames and writes the approved clips to content/footage.json with this shape:

  { "clips": [ {"id","src","start","dur","theme","tags"} ] }

where `src` is relative to assets/footage/ (e.g. "raw/madinah/clip1.mp4").

Run:  python3 scripts/curate_footage.py
"""
import json
import subprocess
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "assets" / "footage" / "raw"
PREV = ROOT / "assets" / "footage" / "curated" / "previews"
EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
SCENE_THRESH = 0.4
MIN_SEG = 4.0     # ignore shots shorter than this
MAX_SEG = 20.0    # cap candidate length
PAD = 0.4         # trim a beat off each cut to avoid transition frames


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", str(path)])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def scene_cuts(path):
    """Timestamps (s) where the shot changes."""
    r = run(["ffmpeg", "-i", str(path), "-filter:v",
             f"select='gt(scene,{SCENE_THRESH})',showinfo", "-an", "-f", "null", "-"])
    return sorted(float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr))


def is_black(path, t):
    """True if the frame at t is essentially black (skip dead footage)."""
    r = run(["ffmpeg", "-ss", str(t), "-i", str(path), "-frames:v", "1",
             "-vf", "blackframe=amount=98:threshold=32", "-an", "-f", "null", "-"])
    return "blackframe" in r.stderr


def segments(path, dur):
    cuts = [0.0] + scene_cuts(path) + [dur]
    segs = []
    for a, b in zip(cuts, cuts[1:]):
        a2, b2 = a + PAD, b - PAD
        if b2 - a2 >= MIN_SEG:
            segs.append((round(a2, 2), round(min(b2 - a2, MAX_SEG), 2)))
    if not segs and dur >= MIN_SEG:          # static clip, no cuts
        segs = [(0.0, round(min(dur, MAX_SEG), 2))]
    return segs


def main():
    if not RAW.exists() or not any(RAW.rglob("*")):
        print(f"No footage found in {RAW} — drop some clips there first.")
        return
    PREV.mkdir(parents=True, exist_ok=True)

    clips = [p for p in RAW.rglob("*") if p.suffix.lower() in EXTS]
    print(f"Scanning {len(clips)} clip(s)...")
    candidates = []
    cid = 0
    for clip in clips:
        rel = clip.relative_to(ROOT / "assets" / "footage").as_posix()
        dur = duration(clip)
        if dur < MIN_SEG:
            print(f"  skip (too short): {rel}")
            continue
        for start, seglen in segments(clip, dur):
            mid = start + seglen / 2
            if is_black(clip, mid):
                continue
            cid += 1
            name = f"cand{cid:03d}.jpg"
            run(["ffmpeg", "-y", "-ss", str(mid), "-i", str(clip), "-frames:v", "1",
                 "-vf", "scale=540:-1", "-q:v", "3", str(PREV / name)])
            cand = {"id": f"c{cid}", "src": rel, "start": start,
                    "dur": round(min(seglen, 18), 2),
                    "preview": f"curated/previews/{name}"}
            # DJI Action saves all footage as landscape with no rotation flag.
            # Clips dropped in a `vertical/` subfolder were filmed vertically -> rotate.
            if "vertical" in rel.lower():
                cand["rotate"] = "cw"  # verify direction visually during review
            candidates.append(cand)
            print(f"  candidate {rel}  start={start}s dur~{round(min(seglen,18),2)}s -> {name}")

    (ROOT / "work").mkdir(exist_ok=True)
    (ROOT / "work" / "footage_candidates.json").write_text(
        json.dumps({"candidates": candidates}, indent=2, ensure_ascii=False))
    print(f"\n{len(candidates)} candidate(s) -> work/footage_candidates.json")
    print(f"Preview frames in {PREV}")
    print("Next: Claude reviews the previews and writes approved clips to content/footage.json")


if __name__ == "__main__":
    main()
