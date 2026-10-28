#!/usr/bin/env python3
"""Record public YouTube view counts for our uploads — no login needed.

Why: analyze_performance.py needs the Mac's YouTube OAuth token, so it never
runs in the daily cloud job — the 2026-09-13 metadata-language A/B went unread
for six weeks while views slid. This reads what anyone can see (the channel's
Shorts tab, plus the RSS feed for exact counts and likes on the latest 15) and
keeps per-video numbers in state/views.json, which the daily job commits:

  {"updated": "...Z",
   "videos": {"<registry id>": {"youtube_id": "...", "uploaded_at": "...",
              "views": 1234, "likes": 210, "views_7d": 1100, "checked": "...Z"}}}

`views_7d` is frozen on the first run that sees a video 7-10 days old, so videos
of different ages compare fairly; videos already older when the tracker started
fall back to their current total (Shorts get most views in week one). Counts of
1,000+ are rounded on the Shorts tab ("1.2K"); the feed gives exact numbers for
the newest 15.

Best-effort by design: any failure prints a warning and exits 0, so it can
never stop a post.

  python3 scripts/public_stats.py            # refresh state/views.json + summary
  python3 scripts/public_stats.py --report   # summary from state/views.json only
"""
import gzip
import json
import re
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANNEL_ID = "UCU1KnLLtieO2pooAGFiI4Ww"  # DailyDeen (@DailyDeen15)
SHORTS_URL = f"https://www.youtube.com/channel/{CHANNEL_ID}/shorts"
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
STATE = ROOT / "state" / "views.json"
HIT = 900  # "reached ~1K" — the Shorts tab rounds 1,000-1,099 to "1K"


def fetch(url, data=None, headers=None):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
         "Accept-Encoding": "gzip", "Cookie": "CONSENT=YES+1; SOCS=CAI"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    return body.decode("utf-8", errors="replace")


def parse_views(text):
    """'1.2K views' -> 1200, '51 views' -> 51, 'No views' -> 0."""
    m = re.match(r"\s*([\d.,]+)\s*([KM]?)", (text or "").replace(",", ""))
    if not m:
        return 0
    return int(float(m.group(1)) * {"": 1, "K": 1_000, "M": 1_000_000}[m.group(2)])


def walk(o, found, conts, path=()):
    if isinstance(o, dict):
        v = o.get("shortsLockupViewModel")
        if v:
            vid = (v.get("onTap", {}).get("innertubeCommand", {})
                   .get("reelWatchEndpoint", {}).get("videoId"))
            if not vid:
                m = re.search(r'"videoId":\s*"([\w-]{11})"', json.dumps(v))
                vid = m.group(1) if m else None
            meta = v.get("overlayMetadata", {})
            if vid and vid not in found:
                found[vid] = parse_views((meta.get("secondaryText") or {}).get("content", ""))
        if ("continuationCommand" in o and "token" in o["continuationCommand"]
                and "continuationItemRenderer" in path
                and ("richGridRenderer" in path or "appendContinuationItemsAction" in path)):
            conts.append(o["continuationCommand"]["token"])
        for k, val in o.items():
            walk(val, found, conts, path + (k,))
    elif isinstance(o, list):
        for val in o:
            walk(val, found, conts, path)


def shorts_tab_views(max_pages=30):
    page = fetch(SHORTS_URL)
    key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', page).group(1)
    ver = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', page).group(1)
    data = json.loads(re.search(r"ytInitialData\s*=\s*(\{.*?\});\s*</script>", page, re.S).group(1))
    found, conts = {}, []
    walk(data, found, conts)
    for _ in range(max_pages):
        if not conts:
            break
        body = json.dumps({"context": {"client": {"clientName": "WEB", "clientVersion": ver,
                                                  "hl": "en", "gl": "US"}},
                           "continuation": conts.pop()}).encode()
        d = json.loads(fetch(f"https://www.youtube.com/youtubei/v1/browse?key={key}&prettyPrint=false",
                             data=body, headers={"Content-Type": "application/json"}))
        conts = []
        walk(d, found, conts)
        time.sleep(1)
    return found


def feed_stats():
    """Exact views + likes for the newest 15 uploads (public RSS)."""
    out = {}
    for e in fetch(FEED_URL).split("<entry>")[1:]:
        vid = re.search(r"<yt:videoId>([^<]+)", e)
        views = re.search(r'views="(\d+)"', e)
        likes = re.search(r'starRating count="(\d+)"', e)
        if vid and views:
            out[vid.group(1)] = {"views": int(views.group(1)),
                                 "likes": int(likes.group(1)) if likes else None}
    return out


def refresh():
    uploads = json.loads((ROOT / "state" / "uploads.json").read_text())["uploads"]
    state = json.loads(STATE.read_text()) if STATE.exists() else {"videos": {}}
    now = datetime.now(timezone.utc)
    tab = shorts_tab_views()
    try:
        feed = feed_stats()
    except Exception as e:  # noqa: BLE001 — the feed 404s datacenter IPs at times
        print(f"(feed unavailable: {e}; using the rounded Shorts-tab counts only)")
        feed = {}
    if not tab and not feed:
        raise RuntimeError("no view counts found on the Shorts tab or the feed")
    seen = 0
    for u in uploads:
        yid = u.get("youtube_id")
        if not yid or (yid not in tab and yid not in feed):
            continue
        seen += 1
        rec = state["videos"].setdefault(u["id"], {})
        rec.update({"youtube_id": yid, "uploaded_at": u.get("uploaded_at"),
                    "meta_lang": u.get("meta_lang") or rec.get("meta_lang"),
                    "theme": u.get("theme") or rec.get("theme"),
                    "views": feed.get(yid, {}).get("views", tab.get(yid, rec.get("views", 0))),
                    "checked": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
        if feed.get(yid, {}).get("likes") is not None:
            rec["likes"] = feed[yid]["likes"]
        try:
            age = now - datetime.fromisoformat(u["uploaded_at"])
        except (KeyError, ValueError):
            age = timedelta(0)
        if "views_7d" not in rec and timedelta(days=7) <= age < timedelta(days=10):
            rec["views_7d"] = rec["views"]
    state["updated"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False, sort_keys=True))
    print(f"public stats: {seen} registered videos found ({len(tab)} on the Shorts tab, "
          f"{len(feed)} in the feed) -> state/views.json")
    return state


def report(state):
    asof = datetime.fromisoformat(state["updated"].replace("Z", "+00:00"))
    vids = [v for v in state.get("videos", {}).values()
            if v.get("uploaded_at") and asof - datetime.fromisoformat(v["uploaded_at"]) >= timedelta(days=7)]
    if not vids:
        print("no videos 7+ days old yet")
        return
    vids.sort(key=lambda v: v["uploaded_at"])

    def line(label, group):
        if not group:
            return
        vals = [v.get("views_7d", v["views"]) for v in group]
        hits = sum(1 for x in vals if x >= HIT) / len(vals)
        print(f"  {label:<26} n={len(vals):3}  median 7-day views {int(statistics.median(vals)):5}"
              f"  reached ~1K {hits:4.0%}")

    print("YouTube views per video (7-day count; current total for videos older than the tracker):")
    last = datetime.fromisoformat(vids[-1]["uploaded_at"])
    for weeks_back in (6, 4, 2):  # three consecutive two-week windows, oldest first
        start, end = last - timedelta(weeks=weeks_back), last - timedelta(weeks=weeks_back - 2)
        group = [v for v in vids if start < datetime.fromisoformat(v["uploaded_at"]) <= end]
        line(f"{start:%d %b} - {end:%d %b}", group)
    recent = [v for v in vids if datetime.fromisoformat(v["uploaded_at"]) > last - timedelta(weeks=6)]
    for lang in ("ar", "en"):
        line(f"last 6 weeks, meta {lang}", [v for v in recent if v.get("meta_lang") == lang])


def main():
    try:
        if "--report" in sys.argv:
            report(json.loads(STATE.read_text()))
            return
        report(refresh())
    except Exception as e:  # noqa: BLE001 — never fail the daily job
        print(f"WARNING: public stats skipped ({e})")


if __name__ == "__main__":
    main()
