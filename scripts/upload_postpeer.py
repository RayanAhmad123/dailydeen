#!/usr/bin/env python3
"""Post a rendered video to YouTube + TikTok via PostPeer (audited multi-platform
poster) — avoids our TikTok sandbox draft cap.

Flow: presigned media upload -> S3 PUT -> POST /v1/posts.
Reads work/script.json (id) + output/videos/<id>.meta.json (title/desc/caption/tags).

NOTE: PostPeer PUBLISHES DIRECTLY — its YouTube integration ignores privacyStatus
(posts public). To control timing use PP_WHEN (scheduledFor), not private staging.
For a private review copy, use scripts/upload_youtube.py instead.

Env:
  POSTPEER_API_KEY   required (in ~/.zshenv)
  PP_PLATFORMS       "youtube,tiktok" (default both)
  PP_YT_PRIVACY      youtube privacyStatus: public|unlisted|private (default public;
                     note PostPeer may publish public regardless)
  PP_TIKTOK_DRAFT    "0" -> publish public (default), "1" -> TikTok inbox draft
  PP_WHEN            "now" (default) or ISO time "2026-06-30T09:00:00" to schedule
  PP_TZ              timezone for scheduling (default "Europe/Stockholm")

Run: python3 scripts/upload_postpeer.py
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.postpeer.dev/v1"
ACCOUNTS = {  # PostPeer integration ids for DailyDeen
    "youtube": "6a418b7bc1a5dd7a836c3c5c",
    "tiktok": "6a418bc6c1a5dd7a836c3c73",
}


def headers(key):
    return {"x-access-key": key, "Content-Type": "application/json"}


def upload_media(key, video_path):
    """Presigned upload -> returns the public URL PostPeer can read."""
    r = requests.post(f"{API}/media/upload", headers=headers(key),
                      json={"filename": video_path.name, "mimeType": "video/mp4"}, timeout=60)
    r.raise_for_status()
    d = r.json().get("data", r.json())
    up, pub = d["uploadUrl"], d["publicUrl"]
    print(f"  uploading {video_path.name} ({video_path.stat().st_size // 1024} KB) to S3...")
    put = requests.put(up, data=video_path.read_bytes(),
                       headers={"Content-Type": "video/mp4"}, timeout=300)
    put.raise_for_status()
    return pub


def verify_by_media(key, public_url, tries=3):
    """After a 502/timeout, confirm whether the post actually landed by matching the
    unique uploaded media URL in recent posts. Returns the post dict or None."""
    import time
    for _ in range(tries):
        time.sleep(4)
        try:
            r = requests.get(f"{API}/posts?limit=15", headers=headers(key), timeout=30)
            for p in (r.json().get("posts") or r.json().get("data") or []):
                if public_url in [m.get("url") for m in (p.get("mediaItems") or [])]:
                    return {"success": True, "postId": p.get("postId"),
                            "platforms": p.get("platforms", [])}
        except requests.RequestException:
            pass
    return None


def main():
    key = os.environ.get("POSTPEER_API_KEY")
    if not key:
        sys.exit("POSTPEER_API_KEY not set (add it to ~/.zshenv)")

    script = json.loads((ROOT / "work" / "script.json").read_text())
    vid = script["id"]
    meta = json.loads((ROOT / "output" / "videos" / f"{vid}.meta.json").read_text())
    video = ROOT / "output" / "videos" / f"{vid}.mp4"
    if not video.exists():
        sys.exit(f"Video not found: {video}")

    want = os.environ.get("PP_PLATFORMS", "youtube,tiktok").split(",")
    yt_privacy = os.environ.get("PP_YT_PRIVACY", "public")
    tiktok_draft = os.environ.get("PP_TIKTOK_DRAFT", "0") == "1"
    when = os.environ.get("PP_WHEN", "now")

    public_url = upload_media(key, video)
    print(f"  media public URL: {public_url}")

    platforms = []
    if "youtube" in want:
        platforms.append({
            "platform": "youtube",
            "accountId": ACCOUNTS["youtube"],
            "platformSpecificData": {
                "title": meta["title"][:100],
                "description": meta["description"][:4900],
                "tags": meta.get("tags", [])[:15],
                "privacyStatus": yt_privacy,
            },
        })
    if "tiktok" in want:
        platforms.append({
            "platform": "tiktok",
            "accountId": ACCOUNTS["tiktok"],
            "platformSpecificData": {
                "privacyLevel": "SELF_ONLY" if tiktok_draft else "PUBLIC_TO_EVERYONE",
                "draft": tiktok_draft,
                "isAigc": False,
            },
        })

    body = {
        "content": meta.get("caption", meta["title"]),
        "platforms": platforms,
        "mediaItems": [{"type": "video", "url": public_url}],
    }
    if when == "now":
        body["publishNow"] = True
    else:
        body["scheduledFor"] = when
        body["timezone"] = os.environ.get("PP_TZ", "Europe/Stockholm")

    try:
        r = requests.post(f"{API}/posts", headers=headers(key), json=body, timeout=120)
        data = r.json() if r.content else {}
        ok = r.ok and data.get("success") is not False
        code = r.status_code
    except requests.RequestException as e:
        data, ok, code = {}, False, f"exc:{e}"

    if not ok:
        # A 502/timeout can be a gateway timeout where the post WAS created. Verify by
        # the unique media URL we just uploaded — NEVER blind-retry (that duplicated posts).
        print(f"  post returned {code}; verifying whether it landed (no blind retry)...")
        verified = verify_by_media(key, public_url)
        if verified:
            print("  -> it DID land; using the created post (no retry).")
            data, ok = verified, True
        else:
            sys.exit(f"PostPeer post failed ({code}) and not found on verify: "
                     f"{json.dumps(data)[:400]}. Re-run is safe (it self-verifies).")

    print(f"PostPeer post: {json.dumps(data)[:600]}")
    print(f"  platforms: {[p['platform'] for p in platforms]} | yt={yt_privacy} | "
          f"tiktok={'draft' if tiktok_draft else 'public'} | when={when}")

    # Register the YouTube post for the analytics feedback loop
    yt = next((p for p in data.get("platforms", []) if p.get("platform") == "youtube"
               and p.get("success")), None)
    if yt and "watch?v=" in (yt.get("platformPostUrl") or ""):
        ytid = yt["platformPostUrl"].split("watch?v=")[1].split("&")[0]
        reg_path = ROOT / "state" / "uploads.json"
        reg = json.loads(reg_path.read_text()) if reg_path.exists() else {"uploads": []}
        reg["uploads"].append({
            "id": vid, "youtube_id": ytid,
            "category": script.get("category", ""),
            "hook_type": script.get("hook_type", ""), "cta_type": script.get("cta_type", ""),
            "title": meta["title"], "via": "postpeer",
            "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        reg_path.write_text(json.dumps(reg, indent=2, ensure_ascii=False))
        print(f"  registered youtube {ytid} in state/uploads.json ({len(reg['uploads'])} uploads)")


if __name__ == "__main__":
    main()
