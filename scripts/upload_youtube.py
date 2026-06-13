#!/usr/bin/env python3
"""Upload the latest rendered video to YouTube as a Short.

Reads work/script.json for the id and output/videos/<id>.meta.json for
title/description/tags, uploads output/videos/<id>.mp4, and records the
upload in state/uploads.json (the registry the analytics step reads).

Setup (one-time):
  1. Google Cloud console -> create project -> enable "YouTube Data API v3"
     and "YouTube Analytics API".
  2. OAuth consent screen: External, add yourself as test user.
  3. Credentials -> Create OAuth client ID -> Desktop app -> download JSON
     to config/google_client_secret.json (or set GOOGLE_CLIENT_SECRET).
  4. First run opens a browser for consent; the token is cached in
     state/yt_token.json.

Note: until the Google project passes verification, API uploads may be
locked private by YouTube — publish manually from YouTube Studio.
Env: YT_PRIVACY (public|unlisted|private, default public)
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# oauthlib refuses http:// redirects by default, but Google's desktop-flow
# uses http://localhost which is fine. Allow it before importing oauthlib.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
TOKEN_PATH = ROOT / "state" / "yt_token.json"
CLIENT_SECRET = Path(os.environ.get("GOOGLE_CLIENT_SECRET", ROOT / "config" / "google_client_secret.json"))


def get_credentials() -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    if not creds or not creds.valid:
        if not CLIENT_SECRET.exists():
            sys.exit(f"Missing OAuth client secret at {CLIENT_SECRET}.\n"
                     "Create one in Google Cloud console (Desktop app) — see this script's docstring.")
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
        # Paste-in flow: avoids the local-server-callback class of bugs
        # (stale tabs, CSRF state mismatches, redirect-URI port conflicts).
        flow.redirect_uri = "http://localhost"
        auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
        print(f"\n>>> Open this URL in your browser to authorize:\n{auth_url}\n", flush=True)
        print(
            "After granting access, your browser will show a 'This site can't be reached'\n"
            "error on a 'http://localhost/?code=...&state=...' URL. Copy that FULL URL\n"
            "from the address bar and save it to /tmp/oauth_response.txt — I'm waiting.\n",
            flush=True,
        )
        resp_path = Path("/tmp/oauth_response.txt")
        resp_path.unlink(missing_ok=True)
        while not resp_path.exists():
            time.sleep(2)
        redirect_url = resp_path.read_text().strip()
        resp_path.unlink(missing_ok=True)
        # Extract the code ourselves and skip state validation — a stale
        # browser tab's URL can carry a different state than this run's,
        # and the CSRF protection isn't load-bearing in a one-shot local
        # interactive consent on the user's own machine.
        qs = parse_qs(urlparse(redirect_url).query)
        if "code" not in qs:
            sys.exit(f"No 'code' in pasted URL: {redirect_url[:200]}")
        flow.fetch_token(code=qs["code"][0])
        creds = flow.credentials
        TOKEN_PATH.parent.mkdir(exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def main():
    script = json.loads((ROOT / "work" / "script.json").read_text())
    vid = script["id"]
    meta = json.loads((ROOT / "output" / "videos" / f"{vid}.meta.json").read_text())
    video_path = ROOT / "output" / "videos" / f"{vid}.mp4"
    if not video_path.exists():
        sys.exit(f"Video not found: {video_path}")

    yt = build("youtube", "v3", credentials=get_credentials())

    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta["description"][:4900],
            "tags": meta["tags"][:30],
            "categoryId": "27",  # Education
        },
        "status": {
            "privacyStatus": os.environ.get("YT_PRIVACY", "public"),
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  upload {int(status.progress() * 100)}%")
    youtube_id = response["id"]
    print(f"Uploaded: https://youtube.com/shorts/{youtube_id}")
    print(f"Privacy: {response['status']['privacyStatus']}")

    # Registry for the analytics feedback loop
    reg_path = ROOT / "state" / "uploads.json"
    reg = json.loads(reg_path.read_text()) if reg_path.exists() else {"uploads": []}
    reg["uploads"].append({
        "id": vid,
        "youtube_id": youtube_id,
        "category": script["category"],
        "hook_type": script.get("hook_type", ""),
        "cta_type": script.get("cta_type", ""),
        "title": meta["title"],
        "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    reg_path.write_text(json.dumps(reg, indent=2, ensure_ascii=False))
    print(f"Registered in state/uploads.json ({len(reg['uploads'])} uploads)")


if __name__ == "__main__":
    main()
