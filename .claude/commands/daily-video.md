---
description: Run the full daily Islamic wisdom video pipeline
---

Run the daily Islamic wisdom video pipeline from start to finish:

0. **Learn from the channel**: if `state/uploads.json` has uploads and YouTube auth is set up (`state/yt_token.json` or `config/google_client_secret.json` exists), run `python3 scripts/analyze_performance.py` — it scores past videos (retention-weighted) and writes `work/strategy.json` with a recommended category and hook type. Read it and follow the recommendation in steps 1-2 (the picker auto-prefers the category; you apply the hook type). If auth isn't set up, skip with a note.

1. **Pick topic**: `python3 scripts/fetch_topic.py` — selects the next unused topic into `work/topic.json` (prefers the strategy's category when one exists). If it exits 1, the bank is empty: append 10 new topics to `content/topics.json` first (verifiable facts only, same structure, never reuse ids), then rerun. Rotate categories.

2. **Write the script**: Read `work/topic.json`. Then write `work/script.json` following the retention structure HOOK → BUILDUP → PAYOFF → CTA. Total spoken length ~60-80 words (~25-35s). Fields:
   - `id`, `category`, `title` — copied from topic.json
   - `hook` — max 12 words, must open a curiosity loop that only the payoff closes. ROTATE hook types across days (track which you used recently by reading the previous `work/script.json` style if present, else vary): (a) intriguing question, (b) bold claim ("The world's oldest university was founded by a woman."), (c) contrarian ("Everyone thinks X. The real story is better."), (d) mistake/myth correction, (e) list tease ("Three everyday words are secretly Arabic."), (f) story tease ("In 859, a woman spent her entire inheritance on one idea."). Respectful always; intrigue, never clickbait — the payoff must fully deliver what the hook promises.
   - `body` — buildup + payoff, 2–4 sentences, 8th-grade English. The buildup escalates the loop (context, stakes, a "but here's the part most people miss" turn where natural); the payoff resolves it with the most satisfying fact LAST. STAY WITHIN the topic's `facts` — never add specifics (dates, numbers, names, quotes) not in them. NEVER fabricate hadith or Quran quotes; attribute teachings only as the facts do. Use "The Prophet Muhammad (peace be upon him)" when he is mentioned.
   - `cta_spoken` — max 8 words, spoken in the final seconds. Rotate: follow-for-future-value ("Follow for one piece of wisdom every day."), save ("Save this one for later."), comment prompt ("Which fact surprised you? Tell me below."). Keep it soft and warm, one CTA only.
   - `reference_display` — shown on screen, e.g. "Islamic Golden Age · 859 CE" or "Islamic Teaching · Gratitude"
   The voiceover is assembled as `hook ... body ... cta_spoken` (the reference is visual-only).

3. **Story scenes**: Read `story/bible.json` and `story/state.json`. Write the next episode beat — an everyday-life story moment for the recurring cast (Salim, Tariq, Noor) that echoes the topic's theme and continues `state.summary` and its open threads. Then write `work/scenes.json`:
   - `id`, `episode` (state episode + 1)
   - `beat` — 2-3 sentence story beat
   - `summary_after` — updated running summary (carries to the next episode)
   - `open_threads` — story threads to pick up later
   - `scenes` — 4 objects `{"prompt": "..."}`: visual moments of the beat, in order. Every prompt MUST start character descriptions with "a solid black featureless silhouette figure, entire head and face completely dark like a paper cutout shadow" plus the bible `visual` description, and follow EVERY rule in `bible.rules` — never depict or name the Prophet, any prophet, Allah, angels, or companions. NEVER use negations in prompts ("no X" / "X-less" makes the model draw X); describe what SHOULD be there instead.
   Then ensure `REPLICATE_API_TOKEN` is set (it is in `~/.zshenv`); run `python3 scripts/generate_scenes.py`. If a prompt is BLOCKED, rewrite it and rerun. View the generated images and verify: characters are true silhouettes (no faces), no artifacts; regenerate fixed prompts if not.

4. **TTS**: If `ELEVENLABS_API_KEY` is set (check `~/.zshenv`), run `python3 scripts/tts_eleven.py` (primary engine — voice via `ELEVEN_VOICE_ID`/`ELEVEN_VOICE_NAME`). If the key is missing or the call fails, tell the user and ask before falling back to local Fish Speech (`python3 scripts/tts_fish.py`, server at `http://127.0.0.1:8080`, clone ref `refs/reference_short.wav` via `REF_AUDIO`/`REF_TEXT`; keep references ≤7s). Never switch engines silently.

5. **Timestamps**: `python3 scripts/timestamps.py`

6. **Props**: `python3 scripts/build_props.py`

7. **Render**: `npm install` if node_modules is missing, then:
   `npx remotion render HadithVideo --props=src/videoData.json --output=output/videos/<id>.mp4`

8. **Finalize**: `python3 scripts/finalize.py` — updates state, advances the story, writes upload metadata.

9. **Upload — YouTube**: `python3 scripts/upload_youtube.py` (uses `output/videos/<id>.meta.json`; registers the upload in `state/uploads.json` for the feedback loop). If OAuth isn't configured yet, give the user the setup steps from the script's docstring and skip. If YouTube locks the video private (unverified API project), tell the user to publish it in YouTube Studio.

10. **Upload — TikTok**: `python3 scripts/upload_tiktok.py` (sends to TikTok inbox/drafts with a suggested caption unless `TIKTOK_DIRECT_POST=1`). If `TIKTOK_ACCESS_TOKEN` is missing, note it and skip.

11. **Report**: topic + category (and why the strategy chose it, if it did), the hook and body, the episode beat, video path, upload links/status for both platforms, and the title/description used.

If a step fails, diagnose and fix it before moving on; only skip with a clear explanation.
