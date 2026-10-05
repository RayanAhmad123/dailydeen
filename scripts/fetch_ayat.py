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
    # --- 2026-07-27 expansion (per the performance analysis: prefer 10-16s single
    #     ayat — they beat >16s on views/retention/subs — with emotional titles) ---
    "ay_soul":        ("peace",       [(89, 27), (89, 28), (89, 29), (89, 30)]),
    "ay_rahmah":      ("mercy",       [(21, 107)]),
    "ay_hear":        ("reassurance", [(20, 46)]),
    "ay_strive":      ("guidance",    [(29, 69)]),
    "ay_forgive":     ("forgiveness", [(4, 110)]),
    "ay_test":        ("purpose",     [(67, 2)]),
    "ay_humble":      ("character",   [(25, 63)]),
    "ay_protector":   ("trust",       [(3, 150)]),
    "ay_longing":     ("devotion",    [(94, 7), (94, 8)]),
    "ay_with":        ("reassurance", [(16, 128)]),
    # --- 2026-08-09 expansion (bank ran dry 08-08; same recipe: short, famous,
    #     uplifting — prefer 10-16s single ayat per the performance analysis) ---
    "ay_tin":         ("creation",    [(95, 4)]),
    "ay_salam":       ("peace",       [(36, 58)]),
    "ay_favor":       ("gratitude",   [(55, 13)]),
    "ay_rahman":      ("mercy",       [(55, 1), (55, 2), (55, 3), (55, 4)]),
    "ay_closer":      ("nearness",    [(50, 16)]),
    "ay_return":      ("patience",    [(2, 156)]),
    "ay_reward":      ("character",   [(55, 60)]),
    "ay_istighfar":   ("forgiveness", [(71, 10), (71, 11)]),
    "ay_parents":     ("character",   [(17, 24)]),
    "ay_salawat":     ("devotion",    [(33, 56)]),
    "ay_goodlife":    ("hope",        [(16, 97)]),
    "ay_hearts":      ("guidance",    [(3, 8)]),
    # --- 2026-08-14 expansion (per that day's 39-video analysis: theme beats
    #     duration — first/second-person divine promises & comfort and existential
    #     questions win; nature-sign trivia flops; length is NOT a constraint) ---
    "ay_callme":      ("nearness",    [(40, 60)]),
    "ay_sharh":       ("hope",        [(94, 1), (94, 2), (94, 3), (94, 4)]),
    "ay_guide":       ("reassurance", [(26, 62)]),
    "ay_promise":     ("patience",    [(30, 60)]),
    "ay_wakil":       ("trust",       [(3, 173)]),
    "ay_provision":   ("trust",       [(11, 6)]),
    "ay_atom":        ("purpose",     [(99, 7), (99, 8)]),
    "ay_mulk":        ("awe",         [(67, 1)]),
    "ay_qadr":        ("awe",         [(97, 1), (97, 2), (97, 3), (97, 4), (97, 5)]),
    "ay_nas":         ("protection",  [(114, 1), (114, 2), (114, 3), (114, 4), (114, 5), (114, 6)]),
    "ay_repel":       ("character",   [(41, 34)]),
    "ay_race":        ("hope",        [(3, 133)]),
    # --- 2026-08-26 expansion (re-curated after the 08-24 patch was lost; same
    #     brief: first-person divine promises/comfort + existential questions per
    #     the 08-14 analysis; no abstract nature-sign themes. Full translations
    #     reviewed before inclusion — no legal/contextual passages.) ---
    "ay_iam":         ("faith",       [(20, 14)]),
    "ay_found":       ("reassurance", [(93, 6), (93, 7), (93, 8)]),
    "ay_heart":       ("trust",       [(64, 11)]),
    "ay_wadud":       ("forgiveness", [(11, 90)]),
    "ay_bounty":      ("provision",   [(2, 268)]),
    "ay_account":     ("patience",    [(39, 10)]),
    "ay_servants":    ("forgiveness", [(15, 49)]),
    "ay_why":         ("purpose",     [(23, 115)]),
    "ay_neglected":   ("purpose",     [(75, 36)]),
    "ay_graves":      ("reflection",  [(102, 1), (102, 2)]),
    "ay_taste":       ("reflection",  [(3, 185)]),
    "ay_play":        ("reflection",  [(29, 64)]),
    # --- 2026-09-13 expansion (bank hit 0/71; per that day's 64-video analysis:
    #     full short surahs + dhikr lead, first-person promises/duas of the
    #     prophets and existential questions hold ~1k, third-person
    #     "He is with you" reassurance and nature-sign themes trail) ---
    "ay_kafirun":     ("faith",       [(109, 1), (109, 2), (109, 3), (109, 4), (109, 5), (109, 6)]),
    "ay_nasr":        ("gratitude",   [(110, 1), (110, 2), (110, 3)]),
    "ay_alaq":        ("knowledge",   [(96, 1), (96, 2), (96, 3), (96, 4), (96, 5)]),
    "ay_fil":         ("awe",         [(105, 1), (105, 2), (105, 3), (105, 4), (105, 5)]),
    "ay_hashr":       ("awe",         [(59, 22), (59, 23)]),
    "ay_yunus":       ("forgiveness", [(21, 87)]),
    "ay_ayyub":       ("hope",        [(21, 83)]),
    "ay_musa":        ("hope",        [(20, 25), (20, 26), (20, 27), (20, 28)]),
    "ay_need":        ("hope",        [(28, 24)]),
    "ay_complain":    ("patience",    [(12, 86)]),
    "ay_relief":      ("hope",        [(12, 87)]),
    "ay_cave":        ("hope",        [(18, 10)]),
    "ay_cure":        ("trust",       [(26, 78), (26, 79), (26, 80)]),
    "ay_support":     ("hope",        [(47, 7)]),
    "ay_decree":      ("trust",       [(9, 51)]),
    "ay_sufficient":  ("trust",       [(9, 129)]),
    "ay_nofear":      ("hope",        [(10, 62)]),
    "ay_healing":     ("mercy",       [(17, 82)]),
    "ay_respond":     ("hope",        [(27, 62)]),
    "ay_perish":      ("reflection",  [(55, 26), (55, 27)]),
    "ay_tried":       ("reflection",  [(29, 2), (29, 3)]),
    "ay_adornment":   ("reflection",  [(18, 46)]),
    "ay_be":          ("awe",         [(36, 82)]),
    "ay_greater":     ("remembrance", [(29, 45)]),
    "ay_spouses":     ("mercy",       [(30, 21)]),
    "ay_living":      ("devotion",    [(6, 162), (6, 163)]),
    "ay_tidings":     ("hope",        [(41, 30)]),
    "ay_owner":       ("awe",         [(3, 26)]),
    "ay_hereafter":   ("reflection",  [(87, 16), (87, 17)]),
    "ay_forgiver":    ("forgiveness", [(20, 82)]),
    "ay_guardian":    ("awe",         [(15, 9)]),
    # --- 2026-10-06 expansion (bank down to 9/102, dry ~10-15; same brief as
    #     09-13: full short surahs + dhikr lead, first-person duas of the prophets
    #     and existential questions hold; few third-person reassurances, no
    #     nature-sign themes. Full translations reviewed before inclusion; order
    #     interleaves formats so consecutive days differ.) ---
    "ay_adam":        ("forgiveness", [(7, 23)]),
    "ay_deceived":    ("purpose",     [(82, 6), (82, 7), (82, 8)]),
    "ay_qariah":      ("reflection",  [(101, 1), (101, 2), (101, 3), (101, 4), (101, 5), (101, 6),
                                       (101, 7), (101, 8), (101, 9), (101, 10), (101, 11)]),
    "ay_eyes":        ("reassurance", [(52, 48)]),
    "ay_wherever":    ("awe",         [(2, 115)]),
    "ay_zakariya":    ("hope",        [(21, 89)]),
    "ay_twoways":     ("purpose",     [(90, 8), (90, 9), (90, 10)]),
    "ay_maun":        ("character",   [(107, 1), (107, 2), (107, 3), (107, 4), (107, 5), (107, 6), (107, 7)]),
    "ay_dunya":       ("hope",        [(2, 201)]),
    "ay_needallah":   ("faith",       [(35, 15)]),
    "ay_ala":         ("remembrance", [(87, 1), (87, 2), (87, 3)]),
    "ay_sulayman":    ("gratitude",   [(27, 19)]),
    "ay_purify":      ("character",   [(91, 7), (91, 8), (91, 9), (91, 10)]),
    "ay_adiyat":      ("reflection",  [(100, 1), (100, 2), (100, 3), (100, 4), (100, 5), (100, 6),
                                       (100, 7), (100, 8), (100, 9), (100, 10), (100, 11)]),
    "ay_easeway":     ("hope",        [(92, 5), (92, 6), (92, 7)]),
    "ay_ink":         ("awe",         [(18, 109)]),
    "ay_ibrahim":     ("devotion",    [(14, 40), (14, 41)]),
    "ay_laboring":    ("purpose",     [(84, 6)]),
    "ay_luqman":      ("character",   [(31, 17)]),
    "ay_comfort":     ("mercy",       [(25, 74)]),
    "ay_knows":       ("awe",         [(67, 13), (67, 14)]),
    "ay_anxious":     ("reflection",  [(70, 19), (70, 20), (70, 21), (70, 22), (70, 23)]),
    "ay_yusuf":       ("trust",       [(12, 101)]),
    "ay_devote":      ("remembrance", [(73, 8)]),
    "ay_tomorrow":    ("reflection",  [(59, 18)]),
    "ay_love":        ("devotion",    [(3, 31)]),
    "ay_entrance":    ("trust",       [(17, 80)]),
    "ay_turnaway":    ("remembrance", [(20, 124)]),
    "ay_accept":      ("devotion",    [(2, 127)]),
    "ay_forgivemercy": ("forgiveness", [(23, 118)]),
}

# Curated YouTube titles for entries added from 2026-09-13 on (earlier titles
# live in content/ayat.json and are carried over on rebuild). Quoted direct
# speech / questions per the performance analyses.
TITLES = {
    "ay_kafirun":    "\"For You Is Your Religion, and for Me Is Mine\" | Quran 109:1-6",
    "ay_nasr":       "When the Victory of Allah Has Come | Quran 110:1-3",
    "ay_alaq":       "\"Read in the Name of Your Lord\" | Quran 96:1-5",
    "ay_fil":        "The Army of the Elephant | Quran 105:1-5",
    "ay_hashr":      "He Is Allah, the Creator, the Inventor | Quran 59:22-23",
    "ay_yunus":      "\"There Is No Deity Except You; Exalted Are You\" | Quran 21:87",
    "ay_ayyub":      "\"Adversity Has Touched Me, and You Are the Most Merciful\" | Quran 21:83",
    "ay_musa":       "\"My Lord, Expand for Me My Chest\" | Quran 20:25-28",
    "ay_need":       "\"My Lord, I Am in Need of Whatever Good You Send Down\" | Quran 28:24",
    "ay_complain":   "\"I Only Complain of My Grief to Allah\" | Quran 12:86",
    "ay_relief":     "\"Do Not Despair of Relief From Allah\" | Quran 12:87",
    "ay_cave":       "\"Our Lord, Grant Us Mercy From Yourself\" | Quran 18:10",
    "ay_cure":       "\"When I Am Ill, It Is He Who Cures Me\" | Quran 26:78-80",
    "ay_support":    "\"If You Support Allah, He Will Support You\" | Quran 47:7",
    "ay_decree":     "\"Nothing Will Strike Us Except What Allah Has Decreed\" | Quran 9:51",
    "ay_sufficient": "\"Sufficient for Me Is Allah\" | Quran 9:129",
    "ay_nofear":     "No Fear Upon Them, Nor Will They Grieve | Quran 10:62",
    "ay_healing":    "A Healing and Mercy for the Believers | Quran 17:82",
    "ay_respond":    "Who Responds to the Desperate One When He Calls? | Quran 27:62",
    "ay_perish":     "Everyone on Earth Will Perish | Quran 55:26-27",
    "ay_tried":      "Do People Think They Will Not Be Tested? | Quran 29:2-3",
    "ay_adornment":  "Wealth and Children Are Only Adornment | Quran 18:46",
    "ay_be":         "\"Be,\" and It Is | Quran 36:82",
    "ay_greater":    "The Remembrance of Allah Is Greater | Quran 29:45",
    "ay_spouses":    "He Placed Between You Affection and Mercy | Quran 30:21",
    "ay_living":     "\"My Living and My Dying Are for Allah\" | Quran 6:162-163",
    "ay_tidings":    "\"Do Not Fear and Do Not Grieve\" | Quran 41:30",
    "ay_owner":      "\"O Allah, Owner of Sovereignty\" | Quran 3:26",
    "ay_hereafter":  "The Hereafter Is Better and More Enduring | Quran 87:16-17",
    "ay_forgiver":   "\"I Am the Perpetual Forgiver\" | Quran 20:82",
    "ay_guardian":   "\"We Will Be Its Guardian\" | Quran 15:9",
    # 2026-10-06 expansion
    "ay_adam":         "\"Our Lord, We Have Wronged Ourselves\" | Quran 7:23",
    "ay_deceived":     "What Has Deceived You Concerning Your Lord, the Generous? | Quran 82:6-8",
    "ay_qariah":       "The Striking Calamity - What Is the Striking Calamity? | Quran 101:1-11",
    "ay_eyes":         "\"Indeed, You Are in Our Eyes\" | Quran 52:48",
    "ay_wherever":     "Wherever You Turn, There Is the Face of Allah | Quran 2:115",
    "ay_zakariya":     "\"My Lord, Do Not Leave Me Alone\" | Quran 21:89",
    "ay_twoways":      "Have We Not Shown Him the Two Ways? | Quran 90:8-10",
    "ay_maun":         "Have You Seen the One Who Denies the Recompense? | Quran 107:1-7",
    "ay_dunya":        "\"Our Lord, Give Us in This World That Which Is Good\" | Quran 2:201",
    "ay_needallah":    "O Mankind, You Are Those in Need of Allah | Quran 35:15",
    "ay_ala":          "\"Exalt the Name of Your Lord, the Most High\" | Quran 87:1-3",
    "ay_sulayman":     "\"My Lord, Enable Me to Be Grateful for Your Favor\" | Quran 27:19",
    "ay_purify":       "He Has Succeeded Who Purifies It | Quran 91:7-10",
    "ay_adiyat":       "\"Indeed Mankind, to His Lord, Is Ungrateful\" | Quran 100:1-11",
    "ay_easeway":      "\"We Will Ease Him Toward Ease\" | Quran 92:5-7",
    "ay_ink":          "If the Sea Were Ink for the Words of My Lord | Quran 18:109",
    "ay_ibrahim":      "\"My Lord, Make Me an Establisher of Prayer\" | Quran 14:40-41",
    "ay_laboring":     "You Are Laboring Toward Your Lord | Quran 84:6",
    "ay_luqman":       "\"O My Son, Establish Prayer\" | Quran 31:17",
    "ay_comfort":      "\"Grant Us Comfort to Our Eyes\" | Quran 25:74",
    "ay_knows":        "Does He Who Created Not Know? | Quran 67:13-14",
    "ay_anxious":      "Mankind Was Created Anxious | Quran 70:19-23",
    "ay_yusuf":        "\"You Are My Protector in This World and the Hereafter\" | Quran 12:101",
    "ay_devote":       "\"Remember the Name of Your Lord\" | Quran 73:8",
    "ay_tomorrow":     "Let Every Soul Look to What It Has Put Forth for Tomorrow | Quran 59:18",
    "ay_love":         "\"If You Should Love Allah, Then Follow Me\" | Quran 3:31",
    "ay_entrance":     "\"My Lord, Cause Me to Enter a Sound Entrance\" | Quran 17:80",
    "ay_turnaway":     "Whoever Turns Away From My Remembrance | Quran 20:124",
    "ay_accept":       "\"Our Lord, Accept This From Us\" | Quran 2:127",
    "ay_forgivemercy": "\"My Lord, Forgive and Have Mercy\" | Quran 23:118",
}


def get_json(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_text(s, a):
    d = get_json(TEXT_API.format(s=s, a=a))["data"]
    ar = next(e["text"] for e in d if e["edition"]["identifier"] == "quran-uthmani")
    en = next(e["text"] for e in d if e["edition"]["identifier"] == "en.sahih")
    return ar, en, d[0]["surah"]["name"]


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
        surah_ar = ""
        for s, a in refs:
            ar, en, surah_ar = fetch_text(s, a)
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
            # Arabic surah name (API, e.g. "سُورَةُ الأَنبِيَاءِ") for the Arabic-first
            # metadata mode in build_ayah.py — the audience is ~75% Arabic-speaking.
            "surahArabic": surah_ar,
        }
        if vid in titles or vid in TITLES:
            entry["title"] = titles.get(vid) or TITLES[vid]
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
