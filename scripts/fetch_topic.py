#!/usr/bin/env python3
"""Pick the next unused topic from content/topics.json -> work/topic.json"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "content.json"
WORK = ROOT / "work"


def main():
    bank = json.loads((ROOT / "content" / "topics.json").read_text())["topics"]

    state = {"processed": [], "last": None}
    if STATE.exists():
        state = json.loads(STATE.read_text())
    processed = set(state.get("processed", []))
    unused = [t for t in bank if t["id"] not in processed]
    if not unused:
        print("Topic bank exhausted — add new topics to content/topics.json", file=sys.stderr)
        sys.exit(1)

    # Prefer the analytics-recommended category when a strategy exists
    pick = unused[0]
    strategy = WORK / "strategy.json"
    if strategy.exists():
        rec = json.loads(strategy.read_text()).get("recommend_category")
        preferred = [t for t in unused if rec and t["category"] == rec]
        if preferred:
            pick = preferred[0]
            print(f"(strategy: preferring category '{rec}')")

    WORK.mkdir(exist_ok=True)
    (WORK / "topic.json").write_text(json.dumps(pick, indent=2, ensure_ascii=False))
    print(f"Selected topic {pick['id']} — {pick['title']}")


if __name__ == "__main__":
    main()
