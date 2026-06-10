# Daily Hadith Video Generator

Automated pipeline that turns Sahih Bukhari hadiths into 9:16 YouTube Shorts / TikTok videos with an elegant Islamic visual design and a self-hosted Fish Speech voiceover.

## Architecture

```
Google Sheet (hadith list)
  → scripts/fetch_hadith.py     next unprocessed hadith → work/hadith.json
  → Claude (you)                simplify + hook         → work/script.json
  → scripts/tts_fish.py         Fish Speech API (local) → public/audio/hadith_<N>.wav
  → scripts/timestamps.py       Whisper word timings    → work/timings.json
  → scripts/build_props.py      assemble props          → src/videoData.json
  → npx remotion render         1080x1920 @ 30fps       → output/videos/hadith_<N>.mp4
  → scripts/finalize.py         state + upload metadata
```

Run the whole thing with the `/daily-video` slash command (see `claude-setup/commands/`, copy to `.claude/commands/` once).

## Key facts

- **TTS is Fish Speech, self-hosted.** Server expected at `http://127.0.0.1:8080` (`FISH_SPEECH_URL` to override). Never silently substitute another TTS engine — ask the user first.
- **State** lives in `state/last-hadith.json` (`processed` array + `last`). Never reprocess a hadith in `processed`.
- **Content rules**: simplification must preserve exact theological meaning, no interpretation/commentary added, respectful hooks only, "The Prophet Muhammad (peace be upon him)" phrasing.
- **Visual design** (src/): elegant minimal Islamic theme — deep emerald/navy gradient, subtle 8-pointed-star geometry, gold (#c9a85c) accents, Cormorant Garamond serif, karaoke word highlighting. Colors centralized in `src/theme.ts`.
- `work/` is scratch space (gitignored). `src/videoData.json` is overwritten each run; a sample is committed so Remotion Studio always opens.

## Development

- Preview: `npm run dev` (Remotion Studio)
- Test render with sample data: `npx remotion render HadithVideo --output=output/test.mp4`
- Python deps: `requests ormsgpack openai-whisper` ; `ffprobe` (ffmpeg) required by build_props.py

## Don'ts

- Don't change hadith text meaning, ever.
- Don't commit rendered videos or audio (gitignored).
- Don't mark a hadith processed if the render failed.
