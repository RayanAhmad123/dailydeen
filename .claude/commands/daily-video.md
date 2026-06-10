---
description: Run the full daily hadith video pipeline
---

Run the daily hadith video pipeline from start to finish:

1. **Fetch**: `python3 scripts/fetch_hadith.py` — selects the next hadith into `work/hadith.json`. If it exits 1, report that all hadiths are processed and stop.

2. **Write the script**: Read `work/hadith.json`. Then write `work/script.json` with these fields:
   - `hadith_no`, `chapter`, `source` — copied from hadith.json
   - `simplified` — the hadith rewritten in clear, simple English (8th-grade level). Preserve the EXACT theological meaning. Remove the "Narrated by..." chain — give the teaching directly. Use "The Prophet Muhammad (peace be upon him)" instead of "Allah's Apostle". 2–4 sentences, natural as a voiceover. No added interpretation or commentary.
   - `hook` — one respectful attention-grabbing sentence, max 10 words. Rotate styles across days (question / bold statement / curiosity). No clickbait.
   - `reference_spoken` — e.g. "Sahih Bukhari, Hadith number 52, chapter of Belief"
   - `reference_display` — e.g. "Sahih al-Bukhari · Hadith 52"

3. **TTS**: Ensure the Fish Speech server is reachable (default `http://127.0.0.1:8080`, override with `FISH_SPEECH_URL`). Then `python3 scripts/tts_fish.py`. If the server is down, tell the user how to start it (see README) and stop — do NOT fall back to another TTS without asking.

4. **Timestamps**: `python3 scripts/timestamps.py`

5. **Props**: `python3 scripts/build_props.py`

6. **Render**: `npm install` if node_modules is missing, then:
   `npx remotion render HadithVideo --props=src/videoData.json --output=output/videos/hadith_<N>.mp4`

7. **Finalize**: `python3 scripts/finalize.py` — updates state and writes upload metadata.

8. **Report**: hadith number + chapter, the hook and simplified text, video path, and the upload title/description.

If a step fails, diagnose and fix it before moving on; only skip with a clear explanation.
