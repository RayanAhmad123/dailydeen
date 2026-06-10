#!/usr/bin/env python3
"""Fetch the next unprocessed hadith from the Google Sheet -> work/hadith.json"""
import csv, io, json, sys, urllib.request
from pathlib import Path

SHEET_ID = "1koVJukz58zo-bknRGu_Zz9XKCG5jIZmzDz49sTm5oWU"
GID = "1086741586"
URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "last-hadith.json"
WORK = ROOT / "work"


def main():
    raw = urllib.request.urlopen(URL, timeout=30).read().decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(raw)))

    state = {"processed": []}
    if STATE.exists():
        state = json.loads(STATE.read_text())
    processed = set(state.get("processed", []))

    for row in rows:
        no = (row.get("hadith_no") or "").strip()
        status = (row.get("Status") or "").strip().lower()
        text = (row.get("text_en") or "").strip()
        if not no or not text or status == "done" or no in processed:
            continue
        WORK.mkdir(exist_ok=True)
        out = {
            "hadith_no": no,
            "chapter": (row.get("chapter") or "").strip(),
            "source": (row.get("source") or "Sahih Bukhari").strip(),
            "text_en": text,
        }
        (WORK / "hadith.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
        print(f"Selected hadith {no} — {out['chapter']}")
        return

    print("No unprocessed hadith found.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
