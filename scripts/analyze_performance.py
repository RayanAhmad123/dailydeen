#!/usr/bin/env python3
"""Scan the YouTube channel's recent uploads and recommend what to make next.

Joins state/uploads.json (our videos + their category/hook_type) with
YouTube stats (views/likes/comments) and YouTube Analytics retention
(avg view %), scores each video, aggregates by category and hook type,
and writes work/strategy.json:

  { "videos": [...], "by_category": {...}, "by_hook_type": {...},
    "recommend_category": "...", "recommend_hook_type": "...", "note": "..." }

Scoring favors retention (the strongest algorithm signal) plus engagement
per view. With <2 days of data a video is reported but flagged immature.
Exploration: every 4th video intentionally tries the least-used category
so the loop keeps learning instead of overfitting early winners.
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from upload_youtube import get_credentials  # shared OAuth + token cache

from googleapiclient.discovery import build


def main():
    reg_path = ROOT / "state" / "uploads.json"
    if not reg_path.exists() or not json.loads(reg_path.read_text())["uploads"]:
        out = {"videos": [], "by_category": {}, "by_hook_type": {},
               "recommend_category": None, "recommend_hook_type": None,
               "note": "No uploads yet — no data to learn from. Pick freely."}
        (ROOT / "work").mkdir(exist_ok=True)
        (ROOT / "work" / "strategy.json").write_text(json.dumps(out, indent=2))
        print(out["note"])
        return

    uploads = json.loads(reg_path.read_text())["uploads"]
    creds = get_credentials()
    yt = build("youtube", "v3", credentials=creds)
    yta = build("youtubeAnalytics", "v2", credentials=creds)

    ids = [u["youtube_id"] for u in uploads]
    stats = {}
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="statistics", id=",".join(ids[i:i + 50])).execute()
        for item in r.get("items", []):
            stats[item["id"]] = item["statistics"]

    # Per-video average view percentage (retention proxy)
    today = datetime.now(timezone.utc).date().isoformat()
    retention = {}
    try:
        r = yta.reports().query(
            ids="channel==MINE", startDate="2026-01-01", endDate=today,
            metrics="averageViewPercentage,views",
            dimensions="video", filters=f"video=={','.join(ids[:200])}",
        ).execute()
        for row in r.get("rows", []) or []:
            retention[row[0]] = float(row[1])
    except Exception as e:
        print(f"(analytics API unavailable: {e}; scoring on engagement only)", file=sys.stderr)

    videos = []
    for u in uploads:
        s = stats.get(u["youtube_id"], {})
        views = int(s.get("viewCount", 0))
        likes = int(s.get("likeCount", 0))
        comments = int(s.get("commentCount", 0))
        ret = retention.get(u["youtube_id"])
        age_days = max((datetime.now(timezone.utc)
                        - datetime.fromisoformat(u["uploaded_at"])).days, 0)
        engagement = (likes + 2 * comments) / views if views else 0
        # retention dominates; engagement breaks ties; views give mild scale
        score = (ret or 50) / 100 * 0.7 + min(engagement * 10, 1) * 0.2 + min(views / 1000, 1) * 0.1
        videos.append({**u, "views": views, "likes": likes, "comments": comments,
                       "avg_view_pct": ret, "age_days": age_days,
                       "mature": age_days >= 2, "score": round(score, 4)})

    def aggregate(key):
        groups = {}
        for v in videos:
            if v[key]:
                groups.setdefault(v[key], []).append(v["score"])
        return {k: {"n": len(s), "avg_score": round(sum(s) / len(s), 4)}
                for k, s in groups.items()}

    by_cat = aggregate("category")
    by_hook = aggregate("hook_type")

    # Ayah era (2026-07-07 on): the levers are the verse THEME and, since the
    # 2026-09-13 A/B, the metadata LANGUAGE — category/hook_type are empty for
    # these uploads, so score them on their own fields. Theme falls back to the
    # bank for registrations that predate the field. Distribution duds (<20
    # views after 2 days) are excluded: they say nothing about the content.
    try:
        bank = {a["id"]: a for a in json.loads(
            (ROOT / "content" / "ayat.json").read_text())["ayat"]}
    except (OSError, ValueError, KeyError):
        bank = {}
    ayah = [v for v in videos if v["id"].startswith("ay_")]
    for v in ayah:
        v["theme"] = v.get("theme") or bank.get(v["id"], {}).get("theme", "")
        v["meta_lang"] = v.get("meta_lang") or "en"
    scored = [v for v in ayah if v["mature"] and v["views"] >= 20]

    def agg_ayah(key):
        groups = {}
        for v in scored:
            if v.get(key):
                groups.setdefault(v[key], []).append(v)
        return {k: {"n": len(g), "avg_score": round(sum(x["score"] for x in g) / len(g), 4),
                    "median_views": sorted(x["views"] for x in g)[len(g) // 2],
                    "like_rate": round(sum(x["likes"] for x in g) / max(sum(x["views"] for x in g), 1), 4)}
                for k, g in groups.items()}
    by_theme = agg_ayah("theme")
    by_lang = agg_ayah("meta_lang")
    duds = [v["id"] for v in ayah if v["mature"] and v["views"] < 20]

    mature = [v for v in videos if v["mature"]]
    note = ""
    if len(videos) % 4 == 3 and by_cat:
        # exploration turn: least-tried category
        rec_cat = min(by_cat, key=lambda k: by_cat[k]["n"])
        note = "Exploration turn — trying the least-used category to keep learning."
    elif mature and by_cat:
        rec_cat = max(by_cat, key=lambda k: by_cat[k]["avg_score"])
        note = "Exploiting the best-scoring category (retention-weighted)."
    else:
        rec_cat = None
        note = "Data too young (<2 days old) — rotate categories freely for now."
    rec_hook = max(by_hook, key=lambda k: by_hook[k]["avg_score"]) if mature and by_hook else None

    if ayah:
        # Ayah-only channel: the category/hook recommendation is meaningless
        # (those fields only exist on the retired silhouette format).
        rec_cat, rec_hook = "Ayah", None
        best = sorted(by_theme, key=lambda k: -by_theme[k]["avg_score"])
        note = (f"Ayah era: best themes (>=2 videos) "
                f"{[k for k in best if by_theme[k]['n'] >= 2][:5]}; "
                f"metadata language A/B: {by_lang}; distribution duds excluded: {duds}")
    out = {"videos": videos, "by_category": by_cat, "by_hook_type": by_hook,
           "by_theme": by_theme if ayah else {}, "by_meta_lang": by_lang if ayah else {},
           "ayah_duds": duds if ayah else [],
           "recommend_category": rec_cat, "recommend_hook_type": rec_hook, "note": note}
    (ROOT / "work" / "strategy.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"{len(videos)} uploads analyzed. Recommend category: {rec_cat or '(any)'}; "
          f"hook type: {rec_hook or '(rotate)'}\n{note}")
    if ayah:
        print("\nAyah themes (mature, non-dud):")
        for k in sorted(by_theme, key=lambda k: -by_theme[k]["median_views"]):
            d = by_theme[k]
            print(f"  {k:14} n={d['n']:2}  median {d['median_views']:5}  like {d['like_rate']:.1%}  score {d['avg_score']}")
        print(f"Metadata language: {by_lang}")


if __name__ == "__main__":
    main()
