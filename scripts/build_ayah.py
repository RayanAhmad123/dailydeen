#!/usr/bin/env python3
"""Assemble an AyahVideo: pick an ayah + a curated clip, copy the matching
recitation into public/, trim/rotate/mute the footage to 9:16 looped to the
recitation length, and write src/ayahData.json + upload metadata.

Footage, in order: the ayah's pre-rendered montage (cloud-assets release) ->
a raw clip from the local footage library -> in CI, existing montages re-cut
to length (reuse_montage), with a weekly alert until the real ones are uploaded.

The recitation is baked into the render (via the composition's <Audio>), so the
video posts directly with sound — no in-app audio step.

Run:  python3 scripts/build_ayah.py
Then: npx remotion render AyahVideo --props=src/ayahData.json --output=output/videos/<id>.mp4
"""
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_reflection import trim_clip, pick_clip  # shared footage helpers

# Hold after the recitation ends. Was 1.2s with the text fading out — an "it's
# over" signal that broke the Shorts loop (every replay counts as a view since
# 2025-03-31). Now a short breath, text stays up, and the loop restarts cleanly.
TAIL_SEC = 0.4  # keep in sync with build_montages.py
# CI fallback when an ayah has no pre-rendered montage (see reuse_montage).
REUSE_REST = 21         # skip montages whose own video went out in the last N runs
FADE_SEC = 1.0          # crossfade between chained montages (same as build_montages.py)
MAX_REUSE_SHOTS = 6     # montages chained at most for one long recitation
FOOTAGE_ALERT_DAYS = 7  # fail the run (-> email) at most once a week for the fallback
HASHTAGS = ["islam", "quran", "recitation", "islamicreminders", "muslim", "deen", "shorts"]
# Comments are the channel's untapped signal (2026-08-14 analysis: 0-3 comments
# per video despite 8-23% like rates) — every caption asks for a reply the viewer
# can give in one word (Ameen) or one tap (tag a friend). Picked deterministically
# per video id: upload_postpeer's idempotency keys on the exact caption text.
COMMENT_CTAS = [
    'Type "Ameen" if this touched your heart. 🤍',
    "Tag someone who needs this ayah today.",
    'Comment "Ameen" and send this to a friend.',
    "Tag a friend who should hear this recitation.",
]


def comment_cta(vid):
    import hashlib
    n = int(hashlib.md5(vid.encode()).hexdigest(), 16)
    return COMMENT_CTAS[n % len(COMMENT_CTAS)]


# --- Arabic-first metadata (A/B since 2026-09-13) -------------------------
# The 2026-09-13 analysis found ~75% of Ayah-era views come from Arabic-speaking
# countries (IQ, DZ, MA, EG, SY, SA) while every title/description/hashtag was
# English. AYAH_META_LANG picks the metadata language for this build:
#   "ab" (default) alternate ar/en by the bank position -> a clean A/B;
#   "ar" / "en"    force one. The choice is recorded in state/ayah.json
# (meta_lang) and in state/uploads.json so analyze_performance.py can score it.
HASHTAGS_AR = ["قرآن", "تلاوة", "القرآن_الكريم", "اسلام", "ياسر_الدوسري",
               "quran", "islam", "recitation", "shorts"]
COMMENT_CTAS_AR = [
    "اكتب آمين إذا لامست قلبك 🤍",
    "أرسلها لمن يحتاجها اليوم.",
    "من أي بلد تشاهد؟ اكتب في التعليقات.",
    "شارك الأجر: أرسلها لصديق.",
]
AR_TITLE_MAX = 100  # YouTube title limit
RECITER_AR = {"Yasser Al-Dosari": "ياسر الدوسري", "Minshawi": "محمد صديق المنشاوي"}
BASMALA_WORDS = 4  # "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ" prefixed to a surah's first ayah


def strip_tashkeel(s):
    import re
    return re.sub(r"[\u064B-\u065F\u0670\u06D6-\u06ED]", "", s)


def meta_lang(state):
    # Decided 2026-10-28: Arabic-first won the 09-13..10-25 A/B (median 918 vs 623
    # YouTube views, ~1K reached 52% vs 23% of the time, ~21 videos per arm), so
    # it's the default. "ab" re-runs the alternation, "en" forces English.
    import os
    forced = os.environ.get("AYAH_META_LANG", "ar").lower()
    if forced in ("ar", "en"):
        return forced
    return "ar" if len(state.get("used", [])) % 2 == 0 else "en"


def arabic_ref(ayah):
    """'سورة الأنبياء: 87' from the bank's surahArabic + reference."""
    surah = strip_tashkeel(ayah.get("surahArabic") or "").replace("سورة", "").strip()
    surah = f"سورة {surah}" if surah else ""
    nums = ayah["reference"].split(":", 1)[1] if ":" in ayah["reference"] else ""
    return f"{surah}: {nums}".strip(": ")


def arabic_title(ayah):
    """﴿first words of the ayah﴾ | سورة X: N — trimmed to the YouTube limit."""
    words = ayah["arabic"].split()
    if strip_tashkeel(words[0]) == "بسم" and len(words) > BASMALA_WORDS + 2:
        words = words[BASMALA_WORDS:]  # title = the ayah itself, not the basmala
    ref = arabic_ref(ayah)
    for n in range(min(9, len(words)), 2, -1):
        head = " ".join(words[:n]) + ("…" if n < len(words) else "")
        title = f"﴿{head}﴾ | {ref}"
        if len(title) <= AR_TITLE_MAX:
            return title
    return f"﴿{words[0]}…﴾ | {ref}"[:AR_TITLE_MAX]


def build_meta(ayah, vid, lang):
    if lang == "ar":
        import hashlib
        cta = COMMENT_CTAS_AR[int(hashlib.md5(vid.encode()).hexdigest(), 16) % len(COMMENT_CTAS_AR)]
        tags = " ".join("#" + t for t in HASHTAGS_AR)
        ref_ar = arabic_ref(ayah)
        return {
            "title": arabic_title(ayah),
            "description": (f"{ayah['arabic']}\n\n{ref_ar} ({ayah['reference']})\n"
                            f"تلاوة: {RECITER_AR.get(ayah.get('reciter', ''), ayah.get('reciter', ''))}\n\n"
                            f"{ayah['translation']}\n\n"
                            f"{cta}\n\n{tags}"),
            "caption": f"{ayah['arabic']} {ref_ar} ({ayah['reference']}) {cta} {tags}"[:2200],
            "tags": HASHTAGS_AR,
        }
    hashtags = " ".join("#" + t for t in HASHTAGS)
    # Curated per-ayah title from the bank (the auto-fallback truncates mid-word,
    # which every manual run has had to fix — unattended runs need the curated one).
    title = ayah.get("title") or f"{ayah['translation'][:60].rstrip('.,')} | {ayah['reference']}"
    return {
        "title": title,
        "description": f"{ayah['translation']}\n\n{ayah['reference']} - recitation by {ayah.get('reciter','')}\n\n{comment_cta(vid)}\n\n{hashtags}",
        "caption": f"{ayah['translation']} {ayah['reference']} {comment_cta(vid)} {hashtags}"[:2200],
        "tags": HASHTAGS,
    }
SEGMENT_MIN_SEC = 25  # long multi-ayah passages get one-ayah-at-a-time display
TEXT_API = "https://api.alquran.cloud/v1/ayah/{s}:{a}/editions/quran-uthmani,en.sahih"


def load(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def make_segments(ayah):
    """Per-ayah display segments for long passages: authoritative text per ayah
    from api.alquran.cloud + timings from the cached recitation parts. Returns
    None (static full-text display) for short passages or on any failure."""
    if float(ayah["durationSec"]) < SEGMENT_MIN_SEC:
        return None
    m = re.fullmatch(r"Quran (\d+):(\d+)-(\d+)", ayah["reference"])
    if not m:
        return None
    s, a0, a1 = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        segments, t = [], 0.0
        for a in range(a0, a1 + 1):
            part = ROOT / "assets" / "recitations" / "_parts" / f"{s:03d}{a:03d}.mp3"
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(part)], capture_output=True, text=True, check=True)
            length = float(r.stdout.strip())
            with urllib.request.urlopen(TEXT_API.format(s=s, a=a), timeout=30) as resp:
                d = json.loads(resp.read().decode())["data"]
            ar = next(e["text"] for e in d if e["edition"]["identifier"] == "quran-uthmani")
            en = next(e["text"] for e in d if e["edition"]["identifier"] == "en.sahih")
            segments.append({"arabic": ar, "translation": en.replace("[", "").replace("]", ""),
                             "startSec": round(t, 2), "endSec": round(t + length, 2)})
            t += length
        # text accuracy is non-negotiable: joined segments must equal the bank entry
        if " ".join(x["arabic"] for x in segments) != ayah["arabic"]:
            raise ValueError("Arabic mismatch vs bank")
        if " ".join(x["translation"] for x in segments) != ayah["translation"]:
            raise ValueError("Translation mismatch vs bank")
        if abs(t - float(ayah["durationSec"])) > 0.2:
            raise ValueError(f"part durations {t:.2f}s != recitation {ayah['durationSec']}s")
        return segments
    except Exception as e:  # noqa: BLE001 — fall back to static display, never block the build
        print(f"  ! segments unavailable ({e}) — using static full-text display")
        return None


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def reuse_montage(vid, theme, dur, ayat, state, out):
    """CI fallback for an ayah with no pre-rendered montage (bank topped up in git,
    cloud-assets release not re-uploaded): re-cut montages that DO exist rather
    than post text on a blank background — 14 videos went out like that
    2026-10-15..10-28 before anyone noticed. Prefers the least-reused montage,
    the same theme, one whose own video is not recent, and one long enough to
    cover the recitation; otherwise chains the next best with the usual 1s
    crossfade. Writes `out` and returns the montage ids used ([] = nothing usable)."""
    pre_dir = ROOT / "assets" / "prerendered"
    if not pre_dir.exists():
        return []
    themes = {a["id"]: a.get("theme") for a in ayat}
    recent = set(state.get("used", [])[-REUSE_REST:])
    reuse = state.get("montage_reuse", {})
    cands = []
    for p in sorted(pre_dir.glob("*.mp4")):
        if p.name.startswith(".") or p.stem == vid:  # skip macOS ._ resource forks
            continue
        d = probe_duration(p)
        if d < 3:
            continue
        cands.append({"id": p.stem, "path": p, "dur": d})
    if not cands:
        return []

    def score(c):
        return (reuse.get(c["id"], 0) * 10
                + (0 if themes.get(c["id"]) == theme else 3)
                + (0 if c["dur"] >= dur else 2)
                + (5 if c["id"] in recent else 0))

    ranked = sorted(cands, key=lambda c: (score(c), c["id"]))
    chosen, total = [], 0.0
    for c in ranked:
        chosen.append(c)
        total = sum(x["dur"] for x in chosen) - FADE_SEC * (len(chosen) - 1)
        if total >= dur or len(chosen) == MAX_REUSE_SHOTS:
            break
    if total < dur - 0.05:
        raise RuntimeError(f"only {total:.1f}s of montages to reuse, need {dur}s")

    args = []
    for c in chosen:
        args += ["-i", str(c["path"])]
    if len(chosen) == 1:
        fc = "[0:v]fps=30,format=yuv420p[v]"
    else:
        fc = ";".join(f"[{i}:v]fps=30,format=yuv420p,settb=AVTB[v{i}]" for i in range(len(chosen)))
        prev, off = "[v0]", 0.0
        for i in range(1, len(chosen)):
            off += chosen[i - 1]["dur"] - FADE_SEC
            nxt = "[v]" if i == len(chosen) - 1 else f"[x{i}]"
            fc += f";{prev}[v{i}]xfade=transition=fade:duration={FADE_SEC}:offset={off:.3f}{nxt}"
            prev = nxt
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args, "-filter_complex", fc,
                    "-map", "[v]", "-an", "-t", str(dur), "-r", "30", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(out)],
                   check=True)
    got = probe_duration(out)
    if got < dur - 0.2:
        raise RuntimeError(f"reused footage is {got:.2f}s, need {dur}s")
    for c in chosen:
        reuse[c["id"]] = reuse.get(c["id"], 0) + 1
    state["montage_reuse"] = reuse
    return [c["id"] for c in chosen]


def footage_warning(vid, used_ids, state):
    """Record why this video's footage is a stand-in; raise the alert at most once
    per FOOTAGE_ALERT_DAYS (a no-footage video always alerts). The workflow fails
    AFTER the state commit when work/build_warnings.json says alert, so the run
    still advances and GitHub emails the owner."""
    from datetime import date
    today = date.today()
    last = state.get("footage_alert_last")
    due = (not used_ids) or last is None or (today - date.fromisoformat(last)).days >= FOOTAGE_ALERT_DAYS
    if used_ids:
        msg = (f"{vid}: no pre-rendered montage in the cloud-assets release, so it reused "
               f"{', '.join(used_ids)}. Build this batch's montages on the Mac "
               f"(scripts/build_montages.py) and re-upload prerendered.tar.gz.")
    else:
        msg = (f"{vid}: no montage and none to reuse — rendered WITHOUT footage. "
               f"Re-upload prerendered.tar.gz to the cloud-assets release.")
    if due:
        state["footage_alert_last"] = today.isoformat()
    (ROOT / "work").mkdir(exist_ok=True)
    (ROOT / "work" / "build_warnings.json").write_text(json.dumps(
        {"warnings": [msg], "alert": due}, indent=2, ensure_ascii=False))
    print(f"  ! {msg}" + ("" if due else " (alert already sent this week)"))


def main():
    ayat = load(ROOT / "content" / "ayat.json", {"ayat": []})["ayat"]
    if not ayat:
        raise SystemExit("content/ayat.json is empty — run scripts/fetch_ayat.py first.")
    footage = load(ROOT / "content" / "footage.json", {"clips": []})["clips"]
    state = load(ROOT / "state" / "ayah.json", {"used": [], "used_clips": [], "last": None})
    (ROOT / "work" / "build_warnings.json").unlink(missing_ok=True)  # only this run's warnings

    unused = [a for a in ayat if a["id"] not in set(state["used"])]
    if not unused:
        raise SystemExit(
            "AYAH BANK EXHAUSTED — every entry in content/ayat.json is used. "
            "Add new ayat (fetch_ayat.py), pre-render their montages "
            "(scripts/build_montages.py) and update the cloud-assets release."
        )
    ayah = unused[0]
    vid = ayah["id"]

    # Recitation -> public/ so the composition can play it
    src_audio = ROOT / "assets" / ayah["audio"]
    if not src_audio.exists():
        raise SystemExit(f"Recitation missing: {src_audio} — run scripts/fetch_ayat.py")
    pub_audio = ROOT / "public" / "recitation" / f"{vid}.mp3"
    pub_audio.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_audio, pub_audio)
    dur = round(float(ayah["durationSec"]) + TAIL_SEC, 2)

    # Pre-rendered montage (built + frame-reviewed via scripts/build_montages.py,
    # shipped in the cloud-assets release) takes priority — this is what the
    # unattended GitHub Actions run uses. Falls back to live footage trimming.
    clip = None
    clip_rel = None
    pre = ROOT / "assets" / "prerendered" / f"{vid}.mp4"
    if pre.exists():
        out = ROOT / "public" / "reflection" / f"{vid}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pre, out)
        clip_rel = f"reflection/{vid}.mp4"
        print(f"  footage: prerendered montage {pre.name}")
    else:
        out = ROOT / "public" / "reflection" / f"{vid}.mp4"
        clip = pick_clip(footage, ayah.get("theme"), set(state["used_clips"]))
        clip_abs = ROOT / "assets" / "footage" / clip["src"] if clip else None
        if clip and clip_abs.exists():  # local run with the footage library
            print(f"  footage {clip['src']}"
                  + (f" (rotate {clip['rotate']})" if clip.get("rotate") else "")
                  + f" -> {dur}s")
            trim_clip(clip_abs, clip.get("start", 0), float(clip.get("dur", dur)), dur, out, clip.get("rotate"))
            clip_rel = f"reflection/{vid}.mp4"
        else:  # CI: no montage shipped for this ayah — reuse existing ones
            clip = None
            try:
                reused = reuse_montage(vid, ayah.get("theme"), dur, ayat, state, out)
            except Exception as e:  # noqa: BLE001 — never block the post over footage
                print(f"  ! montage reuse failed: {e}")
                reused = []
            if reused:
                clip_rel = f"reflection/{vid}.mp4"
                state.setdefault("reused_footage", {})[vid] = reused
                print(f"  footage: reused montage(s) {', '.join(reused)} -> {dur}s")
            footage_warning(vid, reused, state)

    lang = meta_lang(state)
    props = {"id": vid, "arabic": ayah["arabic"], "translation": ayah["translation"],
             "reference": ayah["reference"], "clipFile": clip_rel,
             "audioFile": f"recitation/{vid}.mp3", "durationSec": dur,
             "lang": lang}  # picks the on-screen CTA language
    segments = make_segments(ayah)
    if segments:
        props["segments"] = segments
        print(f"  {len(segments)} per-ayah segments (long passage — one ayah at a time)")
    (ROOT / "src" / "ayahData.json").write_text(json.dumps(props, indent=2, ensure_ascii=False))

    meta = {**build_meta(ayah, vid, lang), "meta_lang": lang,
            "video": f"output/videos/{vid}.mp4"}
    print(f"  metadata language: {lang}  title: {meta['title']}")
    out_dir = ROOT / "output" / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{vid}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    # Advance rotation
    if vid not in state["used"]:
        state["used"].append(vid)
    if clip and clip["id"] not in state["used_clips"]:
        state["used_clips"].append(clip["id"])
    state["last"] = vid
    state.setdefault("meta_lang", {})[vid] = lang  # read back by the uploader's reconcile pass
    (ROOT / "state").mkdir(exist_ok=True)
    (ROOT / "state" / "ayah.json").write_text(json.dumps(state, indent=2, ensure_ascii=False))

    # Cadence bookkeeping + the id handoff upload_postpeer.py reads
    cad_p = ROOT / "state" / "cadence.json"
    cad = load(cad_p, {})
    cad["last_format"] = "ayah"
    cad["last_id"] = vid
    cad_p.write_text(json.dumps(cad, indent=2, ensure_ascii=False))
    (ROOT / "work").mkdir(exist_ok=True)
    # id handoff + the fields upload_postpeer.py registers for the analytics loop
    (ROOT / "work" / "script.json").write_text(json.dumps(
        {"id": vid, "category": "Ayah", "theme": ayah.get("theme", ""), "meta_lang": lang}))

    print(f"Ayah video ready: id={vid}  {ayah['reference']}  ({dur}s, audio baked)")
    print(f"  {ayah['translation']}")
    print(f"  clip: {clip_rel or '(NO FOOTAGE — text over the plain background)'}")
    print(f"  render: npx remotion render AyahVideo --props=src/ayahData.json --output=output/videos/{vid}.mp4")


if __name__ == "__main__":
    main()
