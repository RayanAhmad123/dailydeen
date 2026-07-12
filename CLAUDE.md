# Daily Islamic Wisdom Video Generator

Automated pipeline that turns curated Islamic wisdom, history and fun-fact topics into 9:16 YouTube Shorts / TikTok videos with AI story illustrations, an elegant Islamic visual design, and a self-hosted Fish Speech voiceover. A continuing story ("The Lantern District", faceless silhouette cast) runs across episodes.

## Architecture

```
content/topics.json (curated topic bank, grounded facts)
  → scripts/fetch_topic.py     next unused topic         → work/topic.json
  → Claude (you)               script + hook             → work/script.json
  → Claude (you)               story beat + scene prompts→ work/scenes.json
  → scripts/generate_scenes.py Replicate flux-schnell    → public/scenes/<id>/
  → scripts/tts_fish.py        Fish Speech API (local)   → public/audio/<id>.wav
  → scripts/timestamps.py      Whisper word timings      → work/timings.json
  → scripts/build_props.py     assemble props            → src/videoData.json
  → npx remotion render        1080x1920 @ 30fps         → output/videos/<id>.mp4
  → scripts/finalize.py        state + story + metadata
  → scripts/upload_postpeer.py PostPeer → YouTube + TikTok (public) + registry → state/uploads.json
  ↺ scripts/analyze_performance.py (next run, step 0)     → work/strategy.json
```

Run the whole thing with the `/daily-video` slash command.

## Key facts

- **TTS is ElevenLabs** (`scripts/tts_eleven.py`, `ELEVENLABS_API_KEY` in `~/.zshenv`, voice via `ELEVEN_VOICE_ID`/`ELEVEN_VOICE_NAME`). The hook is synthesized as its OWN segment with a more direct, energetic delivery (lower stability, higher style, speaker boost) and a small loudness boost, then concatenated with the body+CTA — so the opening line punches. Tune via `ELEVEN_HOOK_STABILITY`/`ELEVEN_HOOK_STYLE`/`ELEVEN_HOOK_GAIN_DB` (and `ELEVEN_BODY_*`). Fallback (ask the user first, never switch silently): self-hosted Fish Speech at `http://127.0.0.1:8080`, launched from `~/fish-speech/.venv` (MPS!) with s2-pro; clone ref `refs/reference_short.wav` (keep ≤7s).
- **Script structure** (retention): HOOK (≤12 words, curiosity loop) → PAYOFF (best fact, fast) → CTA (≤6 words, rotate save/follow). **Target ~16-20s / ~35-45 spoken words total — SHORT.** Channel data (379-video analysis, 2026-06): 16-20s videos average ~1,250 views vs ~520 for >40s; the old ~60-80-word/30s+ format underperformed comparable content ~2x. Cut buildup to one tight sentence; lead with the hook, land the payoff, get out. Voiceover = `hook ... body ... cta_spoken`; reference is visual-only. **Hook style (user preference): make hooks personal and direct — open with a question to the viewer: "Did you know…" / "Have you ever…" / "Ever wondered…" / "What if…". Vary the phrasing so they don't all read the same, but keep the personal-question form as the default.** The payoff must still fully deliver what the hook promises (intrigue, never clickbait).
- **Scene images**: Replicate flux-schnell (~$0.003/img), token in `~/.zshenv`. Story continuity via `story/bible.json` (cast, style, seed, hard rules) + `story/state.json` (episode, summary, threads — advanced by finalize.py only on success).
- **State**: `state/content.json` (`processed` topic ids + `last`). Never reuse a processed topic. (`state/last-hadith.json` is the legacy hadith-era state.)
- **Content rules**: scripts must stay within the topic's `facts` — no invented specifics; NEVER fabricate hadith or Quran quotes; "The Prophet Muhammad (peace be upon him)" phrasing; respectful hooks only, no clickbait.
- **Faith-first framing (user preference, non-negotiable)**: this is a *Daily Islamic Wisdom* channel — every script must anchor in a clear Islamic/spiritual angle (faith, gratitude to God, awe of His creation, prophetic character, knowledge as worship, mercy, good akhlaq). History/science topics (Golden Age, Night Sky, Arabic Origins) are vehicles for a spiritual lesson, NOT trivia for its own sake — the body and especially the payoff must tie the fact back to God/faith, not just "Muslims invented X". Pure linguistics/science-trivia topics that can't carry a spiritual lesson were removed from the bank; keep new additions on-theme.
- **Image rules** (non-negotiable): never depict or name the Prophet, any prophet, Allah, angels, or companions; all characters are faceless silhouettes ("solid black featureless silhouette, head completely dark" front-loaded in every prompt); never use negations in image prompts ("crescent-less" draws crescents); no text in images. `generate_scenes.py` enforces a blocklist.
- **Format cadence (user preference)**: **AYAH-ONLY as of 2026-07-07** — every "next video" is an Ayah video (footage + ayah + recitation). The silhouette `/daily-video` format is retired for now (Ayah was by far the best-performing format in the channel analysis). Ayah videos use `scripts/fetch_ayat.py` (once) → `scripts/build_ayah.py` → render `AyahVideo`, published via PostPeer. Long multi-ayah passages (≥25s, e.g. ay_fatiha) get **per-ayah segments** automatically: one ayah on screen at a time, synced to the recitation via `assets/recitations/_parts/` durations, text re-fetched per ayah from the API and verified against the bank. A single long ayah (ay_kursi, 55s) can't be segmented — add a font auto-fit before running it. `state/cadence.json` is `rule: "ayah only"` (the old 3:1 silhouette:ayah rotation and `silhouettes_since_ayah` counter are frozen/unused; restore them only if the user reinstates silhouettes). **Reciter/voice: Yasser Al-Dosari** (`Yasser_Ad-Dussary_128kbps` on everyayah.com), set via `RECITER`/`RECITER_NAME` in `scripts/fetch_ayat.py` (changed from Minshawi 2026-07-07). To change the reciter, edit those two constants, delete `assets/recitations/_parts/*` and `assets/recitations/ay_*.mp3` (else cached audio is reused), then re-run `fetch_ayat.py`. Note: only per-ayah reciters on everyayah.com work (Al-Luhaidan is surah-only there, so unavailable).
- **Distribution**: **PostPeer** (`scripts/upload_postpeer.py`, `POSTPEER_API_KEY` in `~/.zshenv`) is the primary path — one call posts to YouTube + TikTok, publishing PUBLIC directly (it ignores YouTube privacyStatus) with the caption, and avoids the TikTok sandbox draft cap. Schedule with `PP_WHEN=<ISO time>`. Account IDs + flow in the PostPeer memory. Every upload registers the YouTube id in `state/uploads.json`; `analyze_performance.py` scores them (retention-weighted, every 4th run explores) and the next run follows `work/strategy.json`. Legacy/fallback: `scripts/upload_youtube.py` (official API, honors privacy — use for a PRIVATE review copy); `scripts/upload_tiktok.py` (old sandbox Content Posting API, drafts-only + per-day cap — superseded by PostPeer).
- **Visual design** (src/): elegant Islamic theme — emerald/navy, gold (#c9a85c), Cormorant Garamond, karaoke word highlighting, spring animations, Ken Burns scene layer, progress bar, outro CTA. Colors in `src/theme.ts`.
- `work/` is scratch (gitignored). `src/videoData.json` is overwritten each run; a sample is committed so Remotion Studio always opens.

## Development

- Preview: `npm run dev` (Remotion Studio)
- Test render with sample data: `npx remotion render HadithVideo --output=output/test.mp4`
- Python deps: `requests ormsgpack openai-whisper` ; `ffprobe` (ffmpeg) required

## Don'ts

- Don't invent facts, hadiths, or Quran quotes, ever.
- Don't commit rendered videos, audio, or generated scene images (gitignored).
- Don't mark a topic processed if the render failed.

## Project journal

This project is journaled in an Obsidian vault note:
`~/Documents/Triad Solutions/ProjectVault/01 Projects/hadith-video/hadith-video.md`

- **At the start of every session, read that note** for context (goal, next action, log).
- **After completing significant work** (a feature done, a decision made, a blocker hit),
  append a dated entry under `## 🗒️ Log` — 1-3 bullets: what was done and why. Group
  bullets under a `### YYYY-MM-DD` heading (create it if today's isn't there yet).
- **Keep the frontmatter current:** update `next-action` to the single most important
  next step, and `status` (active / on-hold / done) if it changed.
- **Never rewrite or delete existing log entries** — only append.
- **Don't log trivial changes** (typos, formatting).
