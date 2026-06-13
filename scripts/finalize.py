#!/usr/bin/env python3
"""Update state and write upload metadata next to the rendered video."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HASHTAGS = "#islam #islamicwisdom #islamichistory #islamicfacts #goldenage #muslim #dailywisdom #shorts"


def main():
    script = json.loads((ROOT / "work" / "script.json").read_text())
    vid = script["id"]

    # Upload metadata — hook first (YouTube surfaces the first line in search/feeds)
    body = script.get("body") or script.get("simplified", "")
    meta = {
        "title": f"{script['title']} | Daily Islamic Wisdom",
        "description": f"{script['hook']}\n\n{body}\n\n{script['reference_display']}\n\n{HASHTAGS}",
        "tags": ["islam", "islamic wisdom", "islamic history", "islamic facts",
                 "golden age", "muslim", "daily wisdom", "shorts",
                 script["category"].lower()],
        "video": f"output/videos/{vid}.mp4",
    }
    out_dir = ROOT / "output" / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{vid}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    # State
    state_path = ROOT / "state" / "content.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"processed": []}
    if vid not in state["processed"]:
        state["processed"].append(vid)
    state["last"] = vid
    state_path.parent.mkdir(exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))

    # Advance the story only on a successful run
    scenes_spec = ROOT / "work" / "scenes.json"
    story_path = ROOT / "story" / "state.json"
    if scenes_spec.exists() and story_path.exists():
        spec = json.loads(scenes_spec.read_text())
        story = json.loads(story_path.read_text())
        story["episode"] = spec.get("episode", story.get("episode", 0) + 1)
        story["summary"] = spec.get("summary_after", story.get("summary", ""))
        story["open_threads"] = spec.get("open_threads", story.get("open_threads", []))
        story["last_topic"] = vid
        story_path.write_text(json.dumps(story, indent=2, ensure_ascii=False))
        print(f"Story advanced to episode {story['episode']}")

    print(f"Done. Video: output/videos/{vid}.mp4")
    print(f"Title: {meta['title']}")


if __name__ == "__main__":
    main()
