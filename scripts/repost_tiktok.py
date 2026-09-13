#!/usr/bin/env python3
"""Re-post TikTok legs that genuinely failed on PostPeer, spread one per day.

PostPeer keeps the media URL of every post, so a lost TikTok leg is a TikTok-only
re-post of the SAME media + caption — no re-render. Each re-post is scheduled
into TikTok's fresh-quota window (00:00-01:00 UTC, see upload_postpeer.py QUOTA
SPLIT) on consecutive days, 15 min after the daily run's own 00:05 slot, so the
backlog never competes with the day's video or drains the cap in one go.

SAFETY (tiktok-posting-protocol): a PostPeer 'failed' TikTok leg may still be live
(download timeouts are marked failed after TikTok published). ALWAYS check the
account first and pass only the ids that are really missing. Run with --dry-run
to see the plan; without it the posts are created.

  python3 scripts/repost_tiktok.py --start 2026-09-14 ay_atom ay_mulk ...
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from upload_postpeer import ACCOUNTS, API, headers  # noqa: E402

SLOT_UTC = (0, 20)  # 00:20 UTC — inside the fresh window, after the daily 00:05 leg


def failed_tiktok_posts(key):
    r = requests.get(f"{API}/posts?limit=60", headers=headers(key), timeout=30)
    r.raise_for_status()
    out = {}
    for p in r.json().get("posts") or []:
        media = (p.get("mediaItems") or [{}])[0].get("url") or ""
        vid = media.rsplit("/", 1)[-1].removesuffix(".mp4")
        for pl in p.get("platforms") or []:
            if pl.get("platform") == "tiktok" and pl.get("status") == "failed":
                out.setdefault(vid, {"url": media, "caption": p.get("content") or "",
                                     "error": pl.get("errorMessage") or ""})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--start", required=True, help="first day (UTC date) to post")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    key = os.environ.get("POSTPEER_API_KEY") or sys.exit("POSTPEER_API_KEY not set")

    failed = failed_tiktok_posts(key)
    day = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    for vid in args.ids:
        if vid not in failed:
            print(f"  {vid}: no failed TikTok leg on PostPeer — skipped")
            continue
        when = day.replace(hour=SLOT_UTC[0], minute=SLOT_UTC[1]).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = {
            "content": failed[vid]["caption"],
            "platforms": [{"platform": "tiktok", "accountId": ACCOUNTS["tiktok"],
                           "platformSpecificData": {"privacyLevel": "PUBLIC_TO_EVERYONE",
                                                    "draft": False, "isAigc": False}}],
            "mediaItems": [{"type": "video", "url": failed[vid]["url"]}],
            "scheduledFor": when, "timezone": "UTC",
        }
        print(f"  {vid}: {when}  ({failed[vid]['error'][:50]})")
        day += timedelta(days=1)
        if args.dry_run:
            continue
        r = requests.post(f"{API}/posts", headers=headers(key), json=body, timeout=120)
        d = r.json() if r.content else {}
        print(f"     -> {r.status_code} postId={d.get('postId')} "
              f"{[(p.get('platform'), p.get('status') or p.get('success')) for p in d.get('platforms', [])]}")
        if not (r.ok and d.get("success") is not False):
            sys.exit(f"PostPeer refused {vid}: {json.dumps(d)[:300]} — stopping (nothing after this was scheduled)")


if __name__ == "__main__":
    main()
