#!/usr/bin/env python3
"""Post a rendered video to YouTube + TikTok via PostPeer (audited multi-platform
poster) — avoids our TikTok sandbox draft cap.

Flow: presigned media upload -> S3 PUT -> POST /v1/posts.
Reads work/script.json (id) + output/videos/<id>.meta.json (title/desc/caption/tags).

NOTE: PostPeer PUBLISHES DIRECTLY — its YouTube integration ignores privacyStatus
(posts public). To control timing use PP_WHEN (scheduledFor), not private staging.
For a private review copy, use scripts/upload_youtube.py instead.

QUOTA SPLIT: neither platform can be posted whenever the run happens to fire.
PostPeer's YouTube leg draws on PostPeer's OWN Google project quota — 100 video
uploads/day shared across ALL PostPeer users, resetting at midnight Pacific
(07:00 UTC in summer) and draining within hours (a 13:35 UTC attempt on
2026-08-02 429'd). PostPeer's TikTok app has its own daily active-user cap that
resets at 00:00 UTC and is likewise drained within hours: the 04:26 UTC slot was
safe until 2026-08-26, then failed 7 days straight with
"reached_active_user_cap" (08-27..09-02) — silently, because TikTok settles
ASYNCHRONOUSLY (see await_terminal below).

So each leg is now timed to its own quota reset, whatever time the run fires:
tt_publish_when() posts TikTok immediately only inside the first hour after
00:00 UTC and otherwise hands it to PostPeer's scheduler for the next 00:05 UTC;
yt_publish_when() does the same against the Pacific-midnight reset. Ids that
publish after the run ends are back-filled into state/uploads.json by the NEXT
run's reconcile pass, which also reports legs that failed after the fact.
Platform-level failures land in work/postpeer_result.json for the workflow's
alert step (this script stays exit-0 on leg failures so state still advances).

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


def already_posted_platforms(key, caption):
    """Platforms already ATTEMPTED for this exact caption — in ANY status.
    Critical: PostPeer marks TikTok PROCESSING_DOWNLOAD timeouts as 'failed' even
    though TikTok often still publishes them. So a 'failed' attempt may be live —
    never re-post it. We under-post rather than risk a duplicate; genuine failures
    are re-posted MANUALLY after checking the platform, not by re-running this."""
    done = set()
    try:
        r = requests.get(f"{API}/posts?limit=40", headers=headers(key), timeout=30)
        for p in (r.json().get("posts") or r.json().get("data") or []):
            if (p.get("content") or "").strip() == caption.strip():
                for pl in (p.get("platforms") or []):
                    if pl.get("platform"):
                        done.add(pl.get("platform"))  # any status counts as attempted
    except requests.RequestException:
        pass
    return done


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


def yt_publish_when(now_utc):
    """'now' inside the first 2h after a Pacific-midnight quota reset, else an
    ISO-Z scheduledFor ~10 min after the next reset (see QUOTA SPLIT above)."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    pt = now_utc.astimezone(ZoneInfo("America/Los_Angeles"))
    reset = pt.replace(hour=0, minute=0, second=0, microsecond=0)
    if pt - reset < timedelta(hours=2):
        return "now"
    nxt = (pt + timedelta(days=1)).replace(hour=0, minute=10, second=0, microsecond=0)
    return nxt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tt_publish_when(now_utc):
    """'now' inside the first hour after TikTok's 00:00 UTC cap reset, else an
    ISO-Z scheduledFor 00:05 UTC on the next reset (see QUOTA SPLIT above)."""
    from datetime import timedelta
    if now_utc.hour < 1:
        return "now"
    nxt = (now_utc + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
    return nxt.strftime("%Y-%m-%dT%H:%M:%SZ")


def await_terminal(key, watch, timeout=300, interval=20):
    """Wait for publishNow posts to SETTLE, and return {postId: platforms}.

    PostPeer answers a publishNow create with status 'pending' and success:true
    per platform — the real outcome lands asynchronously (TikTok's
    reached_active_user_cap arrives ~2 min later). Without this poll the run
    reports a success it never had: that is how 7 days of TikTok posts were lost
    unnoticed in 2026-08. Posts still pending at the timeout are left out; the
    next run's reconcile pass reports them.
    """
    import time
    watch = set(watch)
    settled = {}
    deadline = time.monotonic() + timeout
    while watch and time.monotonic() < deadline:
        time.sleep(interval)
        try:
            r = requests.get(f"{API}/posts?limit=15", headers=headers(key), timeout=30)
            posts = {p.get("postId"): p for p in
                     (r.json().get("posts") or r.json().get("data") or [])}
        except requests.RequestException:
            continue
        for pid in list(watch):
            plats = (posts.get(pid) or {}).get("platforms") or []
            if plats and all(x.get("status") in ("published", "failed") for x in plats):
                settled[pid] = plats
                watch.discard(pid)
    for pid in watch:
        print(f"  post {pid}: still pending after {timeout}s — the next run's "
              f"reconcile pass will report its outcome")
    return settled


def leg_outcomes(data, requested):
    """Normalize per-platform outcomes from a create-response (success bool) or a
    GET-shaped post (status string) into {platform, success, url, error} dicts."""
    out = []
    plats = data.get("platforms") or []
    for want in requested:
        e = next((p for p in plats if p.get("platform") == want), {})
        ok = bool(e.get("success") is True or e.get("platformPostUrl")
                  or e.get("status") in ("published", "scheduled"))
        out.append({"platform": want, "success": ok,
                    "url": e.get("platformPostUrl"),
                    "error": (e.get("error") or e.get("errorMessage") or "")[:300]})
    return out


def bank_titles():
    """vid -> curated video title, reconstructed exactly like build_ayah.py."""
    try:
        bank = json.loads((ROOT / "content" / "ayat.json").read_text())
        ayat = bank.get("ayat", bank if isinstance(bank, list) else [])
        return {a["id"]: (a.get("title") or f"{a['translation'][:60].rstrip('.,')} | {a['reference']}")
                for a in ayat if a.get("id")}
    except Exception:
        return {}


def register_youtube(reg, vid, ytid, title, uploaded_at=None, script=None):
    script = script or {}
    reg["uploads"].append({
        "id": vid, "youtube_id": ytid,
        "category": script.get("category", ""),
        "hook_type": script.get("hook_type", ""), "cta_type": script.get("cta_type", ""),
        "title": title, "via": "postpeer",
        "uploaded_at": uploaded_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })


def reconcile_registry(key):
    """Back-fill state/uploads.json with YouTube ids that published AFTER their
    run ended (the daily YouTube leg is a PostPeer-scheduled post now), and
    return problems: failed YouTube legs with no live copy and no pending retry,
    a video that ended up published more than once, or a TikTok leg that failed
    after its own run had finished watching it (the scheduled-leg case)."""
    reg_path = ROOT / "state" / "uploads.json"
    reg = json.loads(reg_path.read_text()) if reg_path.exists() else {"uploads": []}
    known_ids = {u.get("youtube_id") for u in reg["uploads"]}
    known_vids = {u.get("id") for u in reg["uploads"]}
    try:
        r = requests.get(f"{API}/posts?limit=40", headers=headers(key), timeout=30)
        posts = r.json().get("posts") or r.json().get("data") or []
    except requests.RequestException as e:
        print(f"  reconcile: could not list posts ({e}) — skipping")
        return []
    titles = bank_titles()
    problems = []
    state = {}  # vid -> {"published": [(ytid, at)], "pending": bool, "failed": bool}
    for p in posts:
        media = (p.get("mediaItems") or [{}])[0].get("url") or ""
        vid = media.rsplit("/", 1)[-1].removesuffix(".mp4")
        if not vid:
            continue
        for pl in (p.get("platforms") or []):
            if pl.get("platform") != "youtube":
                continue
            s = state.setdefault(vid, {"published": [], "pending": False, "failed": False})
            url = pl.get("platformPostUrl") or ""
            if "watch?v=" in url:
                ytid = url.split("watch?v=")[1].split("&")[0]
                s["published"].append((ytid, pl.get("publishedAt")))
            elif pl.get("status") == "failed":
                s["failed"] = True
            else:  # scheduled / pending / processing — a retry is in flight
                s["pending"] = True

    def settled_since_last_run(p):
        """True if this post's status changed since roughly the previous daily
        run — so a failure is reported ONCE, not on every run for two days."""
        try:
            dt = datetime.fromisoformat((p.get("updatedAt") or "").replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return False
        return (datetime.now(timezone.utc) - dt).total_seconds() < 26 * 3600

    # TikTok legs settle asynchronously and a SCHEDULED one settles long after
    # its run ended, so await_terminal can't see it — catch it here instead.
    # PostPeer also marks TikTok PROCESSING_DOWNLOAD timeouts 'failed' when the
    # video did publish, so this only alerts: never auto-repost (see docstring).
    for p in posts:
        if not settled_since_last_run(p):
            continue
        media = (p.get("mediaItems") or [{}])[0].get("url") or ""
        vid = media.rsplit("/", 1)[-1].removesuffix(".mp4")
        for pl in (p.get("platforms") or []):
            if pl.get("platform") == "tiktok" and pl.get("status") == "failed":
                problems.append({"platform": "tiktok", "success": False,
                                 "error": f"{vid}: TikTok leg failed after its run "
                                          f"({(pl.get('errorMessage') or 'no message')[:120]}) "
                                          f"— check TikTok before any manual re-post"})

    def recent(at):  # PostPeer keeps records forever; only alert on fresh events
        try:
            dt = datetime.fromisoformat((at or "").replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - dt).total_seconds() < 48 * 3600
        except (ValueError, TypeError):  # unparsable or naive timestamp
            return False

    added = 0
    for vid, s in state.items():
        new = [(yt, at) for yt, at in s["published"] if yt not in known_ids]
        if vid not in known_vids:
            # First registered copy is canonical; register exactly one.
            for ytid, at in new[:1]:
                try:
                    at_norm = datetime.fromisoformat(at.replace("Z", "+00:00")) \
                        .isoformat(timespec="seconds")
                except (ValueError, AttributeError):
                    at_norm = None
                register_youtube(reg, vid, ytid, titles.get(vid, vid), at_norm)
                known_ids.add(ytid)
                known_vids.add(vid)
                added += 1
            new = new[1:]
        if any(recent(at) for _, at in new):
            # An extra live copy beyond the registered one, published in the last
            # 48h (older records may already be handled in Studio — PostPeer's
            # post list is immutable, so we can't see deletions).
            problems.append({"platform": "youtube", "success": False,
                             "error": f"{vid}: extra YouTube copy published — delete it "
                                      f"in Studio (keep the id in state/uploads.json)"})
        if s["failed"] and not s["published"] and not s["pending"] and vid not in known_vids:
            problems.append({"platform": "youtube", "success": False,
                             "error": f"{vid}: YouTube leg failed and no retry is scheduled "
                                      f"— re-post manually (see docstring)"})
    if added:
        reg_path.write_text(json.dumps(reg, indent=2, ensure_ascii=False))
        print(f"  reconcile: registered {added} YouTube upload(s) that published after their run")
    return problems


def main():
    key = os.environ.get("POSTPEER_API_KEY")
    if not key:
        sys.exit("POSTPEER_API_KEY not set (add it to ~/.zshenv)")

    problems = reconcile_registry(key)

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
    caption = meta.get("caption", meta["title"])

    # IDEMPOTENCY: never publish a platform that already has this caption posted.
    # (PostPeer 502s can be gateway timeouts that still publish — this makes re-runs safe.)
    done = already_posted_platforms(key, caption)
    want = [p for p in want if p not in done]
    if done:
        print(f"  already ATTEMPTED on {sorted(done)} for this caption — skipping "
              f"(a PostPeer 'failed' may still be live on-platform; verify manually before any re-post)")
    result_path = ROOT / "work" / "postpeer_result.json"
    if not want:
        print("Nothing to post — every requested platform was already attempted for this caption. Done.")
        result_path.write_text(json.dumps({"legs": [], "problems": problems}, indent=2))
        return

    # One post per leg: the two platforms need different publish times (QUOTA
    # SPLIT above), and separate media URLs keep verify_by_media unambiguous.
    if when != "now":
        legs_plan = [(want, when, os.environ.get("PP_TZ", "Europe/Stockholm"))]
    else:
        now_utc = datetime.now(timezone.utc)
        legs_plan = []
        if "tiktok" in want:
            legs_plan.append((["tiktok"], tt_publish_when(now_utc), "UTC"))
        if "youtube" in want:
            legs_plan.append((["youtube"], yt_publish_when(now_utc), "UTC"))

    results = []
    pending = {}   # postId -> [indices into results] for publishNow legs
    for leg_platforms, leg_when, leg_tz in legs_plan:
        public_url = upload_media(key, video)
        print(f"  media public URL: {public_url}")

        platforms = []
        if "youtube" in leg_platforms:
            # PostPeer's YouTube branch accepts ONLY `title` for BOTH publishNow and
            # scheduled posts (description/tags/privacyStatus are rejected as additional
            # properties → 400). The top-level `content` (caption) becomes the description
            # and it publishes public by default. (publishNow was tightened to match the
            # scheduled schema — verified 2026-07-09; previously publishNow took the full
            # field set.)
            platforms.append({
                "platform": "youtube",
                "accountId": ACCOUNTS["youtube"],
                "platformSpecificData": {"title": meta["title"][:100]},
            })
        if "tiktok" in leg_platforms:
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
            "content": caption,
            "platforms": platforms,
            "mediaItems": [{"type": "video", "url": public_url}],
        }
        if leg_when == "now":
            body["publishNow"] = True
        else:
            body["scheduledFor"] = leg_when
            body["timezone"] = leg_tz

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
            # (A post that exists but whose platform leg failed — e.g. a YouTube 429 — also
            # lands here: verify finds it and leg_outcomes reports the failure.)
            print(f"  post returned {code}; verifying whether it landed (no blind retry)...")
            verified = verify_by_media(key, public_url)
            if verified:
                print("  -> it DID land; using the created post (no retry).")
                data = verified
            else:
                sys.exit(f"PostPeer post failed ({code}) and not found on verify: "
                         f"{json.dumps(data)[:400]}. Re-run is safe (it self-verifies).")

        print(f"PostPeer post: {json.dumps(data)[:600]}")
        print(f"  platforms: {leg_platforms} | yt={yt_privacy} | "
              f"tiktok={'draft' if tiktok_draft else 'public'} | when={leg_when}")
        for o in leg_outcomes(data, leg_platforms):
            o["when"] = leg_when
            results.append(o)
        # A publishNow leg's reported success is provisional — the platform
        # settles asynchronously. Collect it for the await_terminal pass below.
        if leg_when == "now" and data.get("postId"):
            pending[data["postId"]] = list(range(len(results) - len(leg_platforms),
                                                 len(results)))

        # Register an immediately-published YouTube leg for the analytics feedback
        # loop (a scheduled leg is registered by the next run's reconcile pass).
        yt = next((p for p in data.get("platforms", []) if p.get("platform") == "youtube"
                   and p.get("success")), None)
        if yt and "watch?v=" in (yt.get("platformPostUrl") or ""):
            ytid = yt["platformPostUrl"].split("watch?v=")[1].split("&")[0]
            reg_path = ROOT / "state" / "uploads.json"
            reg = json.loads(reg_path.read_text()) if reg_path.exists() else {"uploads": []}
            register_youtube(reg, vid, ytid, meta["title"], script=script)
            reg_path.write_text(json.dumps(reg, indent=2, ensure_ascii=False))
            print(f"  registered youtube {ytid} in state/uploads.json ({len(reg['uploads'])} uploads)")

    if pending:
        print(f"  waiting for {len(pending)} immediate post(s) to settle on-platform...")
        for pid, plats in await_terminal(key, pending).items():
            for i in pending[pid]:
                final = leg_outcomes({"platforms": plats}, [results[i]["platform"]])[0]
                final["when"] = results[i]["when"]
                if final["success"] != results[i]["success"]:
                    print(f"  {final['platform']}: settled as "
                          f"{'published' if final['success'] else 'FAILED'}"
                          f"{' — ' + final['error'] if final['error'] else ''}")
                results[i] = final

    result_path.write_text(json.dumps({"legs": results, "problems": problems}, indent=2))
    failed = [r for r in results if not r["success"]] + problems
    if failed:
        print(f"  WARNING: {len(failed)} publish problem(s) — recorded in work/postpeer_result.json "
              f"(the workflow alerts on this after committing state)")


if __name__ == "__main__":
    main()
