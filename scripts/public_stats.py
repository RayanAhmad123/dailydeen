#!/usr/bin/env python3
"""Record public YouTube view counts for our uploads — no login needed.

Why: analyze_performance.py needs the Mac's YouTube OAuth token, so it never
runs in the daily cloud job — the 2026-09-13 metadata-language A/B went unread
for six weeks while views slid. This reads what anyone can see (the channel's
Shorts tab, plus exact counts and likes for recent uploads) and keeps per-video
numbers in state/views.json, which the daily job commits:

  {"updated": "...Z",
   "videos": {"<registry id>": {"youtube_id": "...", "uploaded_at": "...",
              "views": 1234, "likes": 210, "views_7d": 1100, "checked": "...Z"}}}

`views_7d` is frozen on the first run that sees a video 7-10 days old, so videos
of different ages compare fairly; videos already older when the tracker started
fall back to their current total (Shorts get most views in week one). Counts of
1,000+ are rounded on the Shorts tab ("1.2K"). Exact numbers + likes come from
the RSS feed (newest 15), or — when YouTube 404s the feed for GitHub's runner IPs,
which was 4 of 5 runs in late Oct — from the innertube /next endpoint per video,
the same API family the Shorts-tab paging already uses from CI.

Duplicate check: PostPeer once double-published a single post (2026-07-19, two
YouTube copies 6s apart). The old workflow step looked for that in the RSS feed
right after the upload, but the YouTube leg is scheduled for ~08:10 UTC, hours
after the run, and the feed usually 404s in CI, so it never saw anything. Now
the next day's run looks at the newest Shorts on the tab: two with the same
title is a duplicate. Each one is reported once (`dup_alerted` in the state
file) via work/stats_alerts.json, which the workflow turns into a failed run
(-> GitHub email) after the state commit.

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
ALERTS = ROOT / "work" / "stats_alerts.json"
EXACT_DAYS = 15     # exact counts via /next for uploads this recent when the feed is down
DUP_NEWEST = 12     # how many of the newest Shorts the duplicate check compares


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
            if vid and vid not in found:  # tab order = newest first
                found[vid] = {"views": parse_views((meta.get("secondaryText") or {}).get("content", "")),
                              "title": " ".join(((meta.get("primaryText") or {})
                                                 .get("content") or "").split())}
        if ("continuationCommand" in o and "token" in o["continuationCommand"]
                and "continuationItemRenderer" in path
                and ("richGridRenderer" in path or "appendContinuationItemsAction" in path)):
            conts.append(o["continuationCommand"]["token"])
        for k, val in o.items():
            walk(val, found, conts, path + (k,))
    elif isinstance(o, list):
        for val in o:
            walk(val, found, conts, path)


def innertube(endpoint, payload, api):
    body = json.dumps({"context": {"client": {"clientName": "WEB", "clientVersion": api["ver"],
                                              "hl": "en", "gl": "US"}}, **payload}).encode()
    return fetch(f"https://www.youtube.com/youtubei/v1/{endpoint}?key={api['key']}&prettyPrint=false",
                 data=body, headers={"Content-Type": "application/json"})


def shorts_tab_views(max_pages=30):
    """{youtube_id: {"views", "title"}} for every Short (newest first) + the
    innertube key/version the page carries, for later /next calls."""
    page = fetch(SHORTS_URL)
    api = {"key": re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', page).group(1),
           "ver": re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', page).group(1)}
    data = json.loads(re.search(r"ytInitialData\s*=\s*(\{.*?\});\s*</script>", page, re.S).group(1))
    found, conts = {}, []
    walk(data, found, conts)
    for _ in range(max_pages):
        if not conts:
            break
        d = json.loads(innertube("browse", {"continuation": conts.pop()}, api))
        conts = []
        walk(d, found, conts)
        time.sleep(1)
    return found, api


def feed_stats(tries=3):
    """Exact views + likes for the newest 15 uploads (public RSS). YouTube 404s
    this URL for datacenter IPs on and off, so give it a few tries."""
    for n in range(tries):
        try:
            xml = fetch(FEED_URL)
            break
        except Exception:  # noqa: BLE001
            if n == tries - 1:
                raise
            time.sleep(10 * (n + 1))
    out = {}
    for e in xml.split("<entry>")[1:]:
        vid = re.search(r"<yt:videoId>([^<]+)", e)
        views = re.search(r'views="(\d+)"', e)
        likes = re.search(r'starRating count="(\d+)"', e)
        if vid and views:
            out[vid.group(1)] = {"views": int(views.group(1)),
                                 "likes": int(likes.group(1)) if likes else None}
    return out


def next_stats(ids, api):
    """Exact views + likes per video from innertube /next (what the watch page
    loads). Fallback for when the feed is unreachable; skips any id that fails."""
    out = {}
    for yid in ids:
        try:
            d = innertube("next", {"videoId": yid}, api)
        except Exception:  # noqa: BLE001
            continue
        views = re.search(r'"viewCount":\{"simpleText":"([\d,]+) views?"', d)
        likes = re.search(r"along with ([\d,]+) other", d)
        if views:
            out[yid] = {"views": int(views.group(1).replace(",", "")),
                        "likes": int(likes.group(1).replace(",", "")) if likes else None}
        time.sleep(0.5)
    return out


def duplicate_alerts(tab, state):
    """Two of the newest Shorts with the same title = a platform double-publish.
    Returns new alert strings and records the ids so each is reported once."""
    newest = list(tab.items())[:DUP_NEWEST]
    by_title = {}
    for yid, t in newest:
        if t.get("title"):
            by_title.setdefault(t["title"], []).append(yid)
    alerted = set(state.get("dup_alerted", []))
    alerts = []
    for title, ids in by_title.items():
        if len(ids) > 1 and not set(ids) <= alerted:
            alerts.append(f"DUPLICATE UPLOAD: '{title}' is on the channel {len(ids)}x "
                          f"({', '.join(ids)}). Delete the extra copy in YouTube Studio (keep "
                          f"the id registered in state/uploads.json) and check TikTok too.")
            alerted |= set(ids)
    state["dup_alerted"] = sorted(alerted)[-50:]
    return alerts


def refresh():
    uploads = json.loads((ROOT / "state" / "uploads.json").read_text())["uploads"]
    state = json.loads(STATE.read_text()) if STATE.exists() else {"videos": {}}
    now = datetime.now(timezone.utc)
    tab, api = shorts_tab_views()
    alerts = duplicate_alerts(tab, state)
    for a in alerts:
        print(a)
    source = "feed"
    try:
        feed = feed_stats()
    except Exception as e:  # noqa: BLE001 — the feed 404s datacenter IPs at times
        recent_ids = [u["youtube_id"] for u in uploads if u.get("youtube_id") and u.get("uploaded_at")
                      and now - datetime.fromisoformat(u["uploaded_at"]) < timedelta(days=EXACT_DAYS)]
        feed = next_stats(recent_ids[-15:], api)
        source = "watch data"
        print(f"(feed unavailable: {e}; exact counts for {len(feed)}/{len(recent_ids[-15:])} "
              f"recent uploads from the watch data instead)")
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
                    "views": feed.get(yid, {}).get("views",
                                                   tab.get(yid, {}).get("views", rec.get("views", 0))),
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
    if ALERTS.parent.exists():  # written after the state so an alert can't repeat
        ALERTS.write_text(json.dumps({"alerts": alerts}, indent=1, ensure_ascii=False))
    print(f"public stats: {seen} registered videos found ({len(tab)} on the Shorts tab, "
          f"{len(feed)} exact from the {source}) -> state/views.json")
    return state


def report(state):
    asof = datetime.fromisoformat(state["updated"].replace("Z", "+00:00"))
    allv = [v for v in state.get("videos", {}).values() if v.get("uploaded_at")]
    young = [v for v in allv
             if timedelta(days=2) <= asof - datetime.fromisoformat(v["uploaded_at"]) < timedelta(days=7)]
    vids = [v for v in allv if asof - datetime.fromisoformat(v["uploaded_at"]) >= timedelta(days=7)]
    if not vids:
        print("no videos 7+ days old yet")
        return
    vids.sort(key=lambda v: v["uploaded_at"])

    def line(label, group, what="7-day views"):
        if not group:
            return
        vals = [v.get("views_7d", v["views"]) for v in group]
        hits = sum(1 for x in vals if x >= HIT) / len(vals)
        print(f"  {label:<26} n={len(vals):3}  median {what} {int(statistics.median(vals)):5}"
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
    young.sort(key=lambda v: v["uploaded_at"])
    line("2-7 days old", young, what="views so far")


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
