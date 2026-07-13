#!/usr/bin/env python3
"""Pre-render the footage montages the unattended daily run uses.

Reads content/montages.json (hand-planned shot lists over content/footage.json
clips) and renders assets/prerendered/<id>.mp4 — 1080x1920 cover-crop, 30fps,
muted, 1s crossfades, sized to the ayah's recitation length + 1.2s tail (same
math as build_ayah.py). Frame-review the outputs, then upload them (plus the
recitations) to the `cloud-assets` GitHub release:

  python3 scripts/build_montages.py            # all montages for unused ayat
  python3 scripts/build_montages.py ay_kursi   # just one
  gh release upload cloud-assets assets/prerendered/*.mp4 --clobber

Needs local footage (assets/footage/) — run on the machine that has the DJI
library, NOT in CI. CI only downloads the finished files.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAIL_SEC = 1.2   # keep in sync with build_ayah.py
FADE = 1.0
COVER = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
ROTATE = {"cw": "transpose=1", "ccw": "transpose=2", "180": "transpose=2,transpose=2"}


def main():
    ayat = {a["id"]: a for a in json.loads((ROOT / "content" / "ayat.json").read_text())["ayat"]}
    clips = {c["id"]: c for c in json.loads((ROOT / "content" / "footage.json").read_text())["clips"]}
    montages = json.loads((ROOT / "content" / "montages.json").read_text())["montages"]
    only = set(sys.argv[1:])
    out_dir = ROOT / "assets" / "prerendered"
    out_dir.mkdir(parents=True, exist_ok=True)

    for m in montages:
        vid = m["id"]
        if only and vid not in only:
            continue
        if vid not in ayat:
            print(f"! {vid}: not in ayat bank — skipped")
            continue
        target = round(float(ayat[vid]["durationSec"]) + TAIL_SEC, 2)

        args, chains, durs = [], [], []
        for i, shot in enumerate(m["shots"]):
            c = clips[shot["clip"]]
            take = float(shot["take"])
            if take > float(c["dur"]) + 0.01:
                raise SystemExit(f"{vid}: shot {c['id']} take {take}s exceeds clean dur {c['dur']}s")
            speed = float(shot.get("speed", 1.0))
            args += ["-ss", str(c.get("start", 0)), "-t", str(take), "-i",
                     str(ROOT / "assets" / "footage" / c["src"])]
            parts = []
            if c.get("rotate") in ROTATE:
                parts.append(ROTATE[c["rotate"]])
            if speed != 1.0:
                parts.append(f"setpts={speed:.4f}*PTS")
            parts += [COVER, "fps=30"]
            chains.append(f"[{i}:v]{','.join(parts)}[v{i}]")
            durs.append(take * speed)

        total = sum(durs) - FADE * (len(durs) - 1)
        if total < target - 0.05:
            raise SystemExit(f"{vid}: shots give {total:.2f}s < target {target}s — extend a take/speed")

        if len(durs) == 1:
            fc = chains[0].replace("[v0]", "[v]")
        else:
            fc, prev, off = ";".join(chains), "[v0]", 0.0
            for i in range(1, len(durs)):
                off += durs[i - 1] - FADE
                nxt = "[v]" if i == len(durs) - 1 else f"[x{i}]"
                fc += f";{prev}[v{i}]xfade=transition=fade:duration={FADE}:offset={off:.4f}{nxt}"
                prev = nxt

        out = out_dir / f"{vid}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", *args, "-filter_complex", fc,
                        "-map", "[v]", "-an", "-t", str(target), "-r", "30",
                        "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
                        str(out)], check=True)
        got = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                    "-of", "csv=p=0", str(out)], capture_output=True, text=True,
                                   check=True).stdout.strip())
        assert abs(got - target) < 0.15, f"{vid}: rendered {got:.2f}s != target {target}s"
        print(f"  {vid}: {got:.2f}s ({len(durs)} shot{'s' if len(durs) > 1 else ''}) -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
