#!/usr/bin/env python3
"""Update state and write upload metadata next to the rendered video."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HASHTAGS = "#hadith #islam #sahihbukhari #dailyhadith #prophetmuhammad #sunnah #islamicreminder #shorts"


def main():
    script = json.loads((ROOT / "work" / "script.json").read_text())
    n = script["hadith_no"]

    # Upload metadata
    meta = {
        "title": f"Sahih Bukhari #{n} — {script['chapter']} | Daily Hadith",
        "description": f"{script['simplified']}\n\n{script['reference_display']}\n\n{HASHTAGS}",
        "tags": ["hadith", "islam", "sahih bukhari", "daily hadith", "prophet muhammad",
                 "sunnah", "islamic reminder", "shorts", script["chapter"].lower()],
        "video": f"output/videos/hadith_{n}.mp4",
    }
    out_dir = ROOT / "output" / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"hadith_{n}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    # State
    state_path = ROOT / "state" / "last-hadith.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"processed": []}
    if str(n) not in state["processed"]:
        state["processed"].append(str(n))
    state["last"] = str(n)
    state_path.parent.mkdir(exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))

    print(f"Done. Video: output/videos/hadith_{n}.mp4")
    print(f"Title: {meta['title']}")


if __name__ == "__main__":
    main()
