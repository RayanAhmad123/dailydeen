#!/usr/bin/env python3
"""Fetch the recitation for the next unused ayah if the cloud-assets tarball
doesn't have it yet (bank topped up in git, release not re-uploaded).

Same source, parts and concat as fetch_ayat.py, so the result is identical to a
local top-up. Runs in CI right after the tarballs are unpacked; a no-op when
the audio is already there. Never fatal on its own: if the download fails,
build_ayah.py fails on the missing file exactly as it would have anyway.

Run: python3 scripts/ensure_recitations.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_ayat as F  # noqa: E402  (main() is guarded; importing has no side effects)


def main():
    bank = json.loads((F.ROOT / "content" / "ayat.json").read_text())["ayat"]
    state_p = F.ROOT / "state" / "ayah.json"
    used = set(json.loads(state_p.read_text()).get("used", [])) if state_p.exists() else set()
    nxt = next((a for a in bank if a["id"] not in used), None)
    if nxt is None:
        print("bank exhausted - nothing to fetch")
        return
    vid = nxt["id"]
    out_mp3 = F.ROOT / "assets" / nxt["audio"]
    if out_mp3.exists():
        print(f"{vid}: recitation present")
        return
    if vid not in F.ENTRIES:
        print(f"! {vid}: not in fetch_ayat.ENTRIES - can't fetch its audio")
        return
    try:
        F.REC_DIR.mkdir(parents=True, exist_ok=True)
        parts_dir = F.REC_DIR / "_parts"
        parts_dir.mkdir(exist_ok=True)
        parts = []
        for s, a in F.ENTRIES[vid][1]:
            part = parts_dir / f"{s:03d}{a:03d}.mp3"
            F.download(f"{s:03d}{a:03d}", part)
            parts.append(part)
        F.concat_audio(parts, out_mp3)
        got = F.duration(out_mp3)
        print(f"{vid}: fetched recitation ({got}s, bank says {nxt['durationSec']}s)")
    except Exception as e:  # build_ayah.py reports the missing file
        print(f"! {vid}: recitation download failed: {e}")


if __name__ == "__main__":
    main()
