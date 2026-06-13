#!/usr/bin/env python3
"""Upload the latest rendered video to TikTok via the Content Posting API.

IMPORTANT platform constraint: unaudited TikTok developer apps can only
send videos to the user's INBOX/DRAFTS — finish posting in the TikTok app
(caption is prefilled). After TikTok audits your app, set
TIKTOK_DIRECT_POST=1 for full auto-publish.

Setup (one-time):
  1. developers.tiktok.com -> create app -> add Login Kit + Content Posting
     API products -> set redirect URI to https://oauth.pstmn.io/v1/callback
  2. Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in ~/.zshenv
  3. First run prints an auth URL; you log in with the sandbox target
     account, paste the redirect URL back; the script caches the token
     pair in state/tiktok_token.json (refreshes automatically thereafter).

Reads work/script.json for the id and the meta.json for the caption.
"""
import json, os, sys, time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://open.tiktokapis.com/v2"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TOKEN_PATH = ROOT / "state" / "tiktok_token.json"
REDIRECT_URI = os.environ.get(
    "TIKTOK_REDIRECT_URI", "https://oauth.pstmn.io/v1/callback"
)
SCOPES = "user.info.basic,video.upload,video.publish"


def get_access_token() -> str:
    """Return a fresh access token, refreshing or running the paste-in
    consent flow if needed. Caches both tokens in state/tiktok_token.json."""
    client_key = os.environ.get("TIKTOK_CLIENT_KEY")
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET")
    if not client_key or not client_secret:
        sys.exit("TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET not set in ~/.zshenv")

    cache = json.loads(TOKEN_PATH.read_text()) if TOKEN_PATH.exists() else {}

    # Refresh if we have a refresh token (TikTok refresh tokens last ~1 year)
    if cache.get("refresh_token") and time.time() > cache.get("expires_at", 0) - 60:
        r = requests.post(
            TOKEN_URL,
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": cache["refresh_token"],
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if r.ok and "access_token" in r.json():
            d = r.json()
            cache.update({
                "access_token": d["access_token"],
                "refresh_token": d.get("refresh_token", cache["refresh_token"]),
                "expires_at": time.time() + d.get("expires_in", 3600),
            })
            TOKEN_PATH.parent.mkdir(exist_ok=True)
            TOKEN_PATH.write_text(json.dumps(cache, indent=2))
            return cache["access_token"]
        print(f"  refresh failed ({r.status_code}); falling back to consent", file=sys.stderr)

    if cache.get("access_token") and time.time() < cache.get("expires_at", 0):
        return cache["access_token"]

    # First-run: paste-in OAuth consent
    auth_params = {
        "client_key": client_key,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": "wisdom",
    }
    auth_url = f"{AUTH_URL}?{urlencode(auth_params)}"
    print("\n>>> Open this URL in your browser, log in as the SANDBOX TARGET", flush=True)
    print(f"    user account, and approve access:\n{auth_url}\n", flush=True)
    print(
        f"After approval the browser lands on '{REDIRECT_URI}?code=...&state=...'.\n"
        "Copy that full URL and save it to /tmp/tiktok_oauth.txt — I'm waiting.\n",
        flush=True,
    )
    resp_path = Path("/tmp/tiktok_oauth.txt")
    resp_path.unlink(missing_ok=True)
    while not resp_path.exists():
        time.sleep(2)
    qs = parse_qs(urlparse(resp_path.read_text().strip()).query)
    resp_path.unlink(missing_ok=True)
    code = qs.get("code", [None])[0]
    if not code:
        sys.exit(f"No code in pasted URL. Got params: {list(qs.keys())}")

    r = requests.post(
        TOKEN_URL,
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if not r.ok:
        sys.exit(f"Token exchange failed ({r.status_code}): {r.text[:400]}")
    d = r.json()
    if "access_token" not in d:
        sys.exit(f"Token exchange returned: {json.dumps(d)[:400]}")
    cache = {
        "access_token": d["access_token"],
        "refresh_token": d.get("refresh_token"),
        "expires_at": time.time() + d.get("expires_in", 3600),
        "open_id": d.get("open_id"),
    }
    TOKEN_PATH.parent.mkdir(exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(cache, indent=2))
    print(f"Token cached at {TOKEN_PATH}", file=sys.stderr)
    return cache["access_token"]


def main():
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    script = json.loads((ROOT / "work" / "script.json").read_text())
    vid = script["id"]
    meta = json.loads((ROOT / "output" / "videos" / f"{vid}.meta.json").read_text())
    video_path = ROOT / "output" / "videos" / f"{vid}.mp4"
    size = video_path.stat().st_size

    direct = os.environ.get("TIKTOK_DIRECT_POST") == "1"
    # Caption: title + hashtags (TikTok pulls hashtags from the caption text)
    hashtags = " ".join(t for t in meta["description"].split() if t.startswith("#"))
    caption = f"{meta['title'].split('|')[0].strip()} {hashtags}"[:2200]

    if direct:
        init_url = f"{API}/post/publish/video/init/"
        body = {
            "post_info": {
                "title": caption,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_comment": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            },
        }
    else:
        init_url = f"{API}/post/publish/inbox/video/init/"
        body = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            },
        }

    r = requests.post(init_url, headers={**headers, "Content-Type": "application/json"},
                      json=body, timeout=60)
    data = r.json()
    if r.status_code != 200 or data.get("error", {}).get("code") not in (None, "ok"):
        sys.exit(f"TikTok init failed ({r.status_code}): {json.dumps(data)[:400]}")

    upload_url = data["data"]["upload_url"]
    with open(video_path, "rb") as f:
        up = requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Range": f"bytes 0-{size - 1}/{size}",
            },
            data=f, timeout=600,
        )
    if up.status_code not in (200, 201):
        sys.exit(f"TikTok upload failed ({up.status_code}): {up.text[:300]}")

    mode = "posted publicly" if direct else "sent to your TikTok inbox/drafts — open the TikTok app to finish posting"
    print(f"TikTok: video {mode}.")
    if not direct:
        print(f"Suggested caption (paste in app):\n{caption}")


if __name__ == "__main__":
    main()
