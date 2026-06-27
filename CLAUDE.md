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
  → scripts/upload_youtube.py  YouTube upload + registry → state/uploads.json
  → scripts/upload_tiktok.py   TikTok (drafts until app audit)
  ↺ scripts/analyze_performance.py (next run, step 0)     → work/strategy.json
```

Run the whole thing with the `/daily-video` slash command.

## Key facts

- **TTS is ElevenLabs** (`scripts/tts_eleven.py`, `ELEVENLABS_API_KEY` in `~/.zshenv`, voice via `ELEVEN_VOICE_ID`/`ELEVEN_VOICE_NAME`). The hook is synthesized as its OWN segment with a more direct, energetic delivery (lower stability, higher style, speaker boost) and a small loudness boost, then concatenated with the body+CTA — so the opening line punches. Tune via `ELEVEN_HOOK_STABILITY`/`ELEVEN_HOOK_STYLE`/`ELEVEN_HOOK_GAIN_DB` (and `ELEVEN_BODY_*`). Fallback (ask the user first, never switch silently): self-hosted Fish Speech at `http://127.0.0.1:8080`, launched from `~/fish-speech/.venv` (MPS!) with s2-pro; clone ref `refs/reference_short.wav` (keep ≤7s).
- **Script structure** (retention): HOOK (≤12 words, curiosity loop) → BUILDUP → PAYOFF (best fact last) → CTA (≤8 words, rotate follow/save/comment). ~60-80 spoken words total. Voiceover = `hook ... body ... cta_spoken`; reference is visual-only. **Hook style (user preference): make hooks personal and direct — open with a question to the viewer: "Did you know…" / "Have you ever…" / "Ever wondered…" / "What if…". Vary the phrasing so they don't all read the same, but keep the personal-question form as the default.** The payoff must still fully deliver what the hook promises (intrigue, never clickbait).
- **Scene images**: Replicate flux-schnell (~$0.003/img), token in `~/.zshenv`. Story continuity via `story/bible.json` (cast, style, seed, hard rules) + `story/state.json` (episode, summary, threads — advanced by finalize.py only on success).
- **State**: `state/content.json` (`processed` topic ids + `last`). Never reuse a processed topic. (`state/last-hadith.json` is the legacy hadith-era state.)
- **Content rules**: scripts must stay within the topic's `facts` — no invented specifics; NEVER fabricate hadith or Quran quotes; "The Prophet Muhammad (peace be upon him)" phrasing; respectful hooks only, no clickbait.
- **Faith-first framing (user preference, non-negotiable)**: this is a *Daily Islamic Wisdom* channel — every script must anchor in a clear Islamic/spiritual angle (faith, gratitude to God, awe of His creation, prophetic character, knowledge as worship, mercy, good akhlaq). History/science topics (Golden Age, Night Sky, Arabic Origins) are vehicles for a spiritual lesson, NOT trivia for its own sake — the body and especially the payoff must tie the fact back to God/faith, not just "Muslims invented X". Pure linguistics/science-trivia topics that can't carry a spiritual lesson were removed from the bank; keep new additions on-theme.
- **Image rules** (non-negotiable): never depict or name the Prophet, any prophet, Allah, angels, or companions; all characters are faceless silhouettes ("solid black featureless silhouette, head completely dark" front-loaded in every prompt); never use negations in image prompts ("crescent-less" draws crescents); no text in images. `generate_scenes.py` enforces a blocklist.
- **Distribution**: YouTube via official API (`config/google_client_secret.json` + cached `state/yt_token.json`; unverified Google projects may force uploads private — publish from Studio). TikTok via Content Posting API — drafts only until TikTok audits the app (`TIKTOK_DIRECT_POST=1` after audit). Every upload is registered in `state/uploads.json`; `analyze_performance.py` scores them (retention-weighted, every 4th run explores) and the next run follows `work/strategy.json`.
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
