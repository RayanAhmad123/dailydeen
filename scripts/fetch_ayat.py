#!/usr/bin/env python3
"""Build the ayah bank for AyahVideos: fetch AUTHORITATIVE Arabic (Uthmani) +
Sahih International translation from AlQuran Cloud, and download the matching
recitation (everyayah.com, Husary murattal — widely redistributed) per ayah,
concatenated into assets/recitations/<id>.mp3.

Writes content/ayat.json. Re-run to add entries (idempotent per id; skips audio
already downloaded). Text accuracy is non-negotiable, so it always comes from the
API — never typed by hand.

Run: python3 scripts/fetch_ayat.py
"""
import json
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REC_DIR = ROOT / "assets" / "recitations"
RECITER = "Yasser_Ad-Dussary_128kbps"
RECITER_NAME = "Yasser Al-Dosari"
TEXT_API = "https://api.alquran.cloud/v1/ayah/{s}:{a}/editions/quran-uthmani,en.sahih"
AUDIO_URL = "https://everyayah.com/data/{rec}/{code}.mp3"

# id -> (theme, [(surah, ayah), ...])  — short, uplifting, well-known passages
ENTRIES = {
    "ay_ease":        ("hope",        [(94, 5), (94, 6)]),
    "ay_remember":    ("remembrance", [(2, 152)]),
    "ay_rest":        ("remembrance", [(13, 28)]),
    "ay_trust":       ("trust",       [(65, 3)]),
    "ay_ikhlas":      ("faith",       [(112, 1), (112, 2), (112, 3), (112, 4)]),
    "ay_kawthar":     ("gratitude",   [(108, 1), (108, 2), (108, 3)]),
    "ay_asr":         ("time",        [(103, 1), (103, 2), (103, 3)]),
    "ay_hope":        ("hope",        [(3, 139)]),
    # --- 2026-07-07 expansion (Ayah-only channel; keep passages short & famous) ---
    "ay_fatiha":      ("peace",       [(1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7)]),
    "ay_near":        ("nearness",    [(2, 186)]),
    "ay_patience":    ("consistency", [(2, 153)]),
    "ay_increase":    ("gratitude",   [(14, 7)]),
    "ay_purpose":     ("remembrance", [(51, 56)]),
    "ay_mercy":       ("hope",        [(39, 53)]),
    "ay_duha":        ("hope",        [(93, 3), (93, 4), (93, 5)]),
    "ay_kursi":       ("trust",       [(2, 255)]),
    # --- 2026-07-14 expansion (paired with the new Pexels footage: Kaaba/Haram,
    #     Kul Sharif, interiors, alpine nature) ---
    "ay_house":       ("pilgrimage",  [(106, 3), (106, 4)]),
    "ay_signs":       ("creation",    [(3, 190)]),
    "ay_dhikr":       ("remembrance", [(33, 41), (33, 42)]),
    "ay_falaq":       ("protection",  [(113, 1), (113, 2), (113, 3), (113, 4), (113, 5)]),
    "ay_unity":       ("unity",       [(49, 13)]),
    "ay_mountains":   ("creation",    [(78, 6), (78, 7)]),
    "ay_knowledge":   ("knowledge",   [(20, 114)]),
    "ay_names":       ("awe",         [(59, 24)]),
    "ay_favors":      ("gratitude",   [(16, 18)]),
}


def get_json(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_text(s, a):
    d = get_json(TEXT_API.format(s=s, a=a))["data"]
    ar = next(e["text"] for e in d if e["edition"]["identifier"] == "quran-uthmani")
    en = next(e["text"] for e in d if e["edition"]["identifier"] == "en.sahih")
    return ar, en


def download(code, dest):
    if dest.exists():
        return
    url = AUDIO_URL.format(rec=RECITER, code=code)
    urllib.request.urlretrieve(url, dest)


def concat_audio(parts, out_path):
    if len(parts) == 1:
        out_path.write_bytes(parts[0].read_bytes())
        return
    listf = out_path.with_suffix(".txt")
    listf.write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listf),
                    "-c", "copy", str(out_path)], check=True, capture_output=True)
    listf.unlink(missing_ok=True)


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return round(float(r.stdout.strip()), 2)


def main():
    REC_DIR.mkdir(parents=True, exist_ok=True)
    tmp = REC_DIR / "_parts"
    tmp.mkdir(exist_ok=True)
    # Rebuilds drop hand-curated fields — carry the per-ayah `title` (used by the
    # unattended upload for clean YouTube titles) over from the existing bank.
    bank_path = ROOT / "content" / "ayat.json"
    titles = {}
    if bank_path.exists():
        titles = {a["id"]: a["title"] for a in json.loads(bank_path.read_text())["ayat"]
                  if a.get("title")}
    bank = []
    for vid, (theme, refs) in ENTRIES.items():
        ar_parts, en_parts, audio_parts = [], [], []
        for s, a in refs:
            ar, en = fetch_text(s, a)
            ar_parts.append(ar)
            en_parts.append(en)
            code = f"{s:03d}{a:03d}"
            part = tmp / f"{code}.mp3"
            download(code, part)
            audio_parts.append(part)
        out_mp3 = REC_DIR / f"{vid}.mp3"
        concat_audio(audio_parts, out_mp3)
        surah = refs[0][0]
        ayat = [a for _, a in refs]
        ref = f"Quran {surah}:{ayat[0]}" + (f"-{ayat[-1]}" if len(ayat) > 1 else "")
        entry = {
            "id": vid, "reference": ref, "theme": theme,
            "arabic": " ".join(ar_parts),
            "translation": " ".join(en_parts).replace("[", "").replace("]", ""),
            "audio": f"recitations/{vid}.mp3",
            "reciter": RECITER_NAME,
            "durationSec": duration(out_mp3),
        }
        if vid in titles:
            entry["title"] = titles[vid]
        bank.append(entry)
        print(f"  {vid:<14} {ref:<14} {entry['durationSec']:>5}s  {entry['translation'][:48]}")

    (ROOT / "content" / "ayat.json").write_text(json.dumps(
        {"_readme": "Ayah bank for AyahVideos. Arabic (Uthmani) + Sahih International "
                    "translation are fetched verbatim from api.alquran.cloud — never hand-typed. "
                    "Audio is murattal from everyayah.com (reciter set by RECITER in fetch_ayat.py; "
                    "widely redistributed, small Content-ID risk on YouTube). Rebuild with scripts/fetch_ayat.py.",
         "ayat": bank}, indent=2, ensure_ascii=False))
    print(f"\n{len(bank)} ayat -> content/ayat.json ; audio in {REC_DIR}")


if __name__ == "__main__":
    main()
