# Daily Hadith Video

Generates a daily 9:16 hadith video (YouTube Shorts / TikTok) with an elegant Islamic design and a self-hosted **Fish Speech** voiceover. Designed to be driven by **Claude Code**.

## One-time setup

**Easiest:** run the bundled script in Terminal — it does everything below (brew/npm/pip deps, slash command, git init, Fish Speech clone + s2-pro weights):

```bash
cd ~/Documents/Cowork/hadith-video
bash setup.sh
```

**Performance note:** the current official model (S2-Pro, 4B params) targets a 24GB GPU on Linux; on a Mac CPU it runs but may take minutes per clip. If too slow: request access to the gated, much smaller [fishaudio/s1-mini](https://huggingface.co/fishaudio/s1-mini) (0.5B), or host on a cloud GPU and point `FISH_SPEECH_URL` at it.

<details>
<summary>Manual steps (what setup.sh does)</summary>

### 1. Project deps

```bash
cd hadith-video
npm install
pip install requests ormsgpack openai-whisper
brew install ffmpeg   # for ffprobe + whisper
```

### 2. Fish Speech (self-hosted TTS)

Follow the official install guide: https://speech.fish.audio/install/

Short version (Apple Silicon works via MPS; Docker also available):

```bash
git clone https://github.com/fishaudio/fish-speech
cd fish-speech
pip install -e .
# download model weights per the install guide (e.g. OpenAudio S1-mini), then:
python -m tools.api_server --listen 0.0.0.0:8080 \
  --llama-checkpoint-path <path-to-weights> \
  --decoder-checkpoint-path <path-to-decoder>
```

The pipeline calls `POST /v1/tts` on `http://127.0.0.1:8080` (override with `FISH_SPEECH_URL`).
Verify it's up: `curl -s http://127.0.0.1:8080/v1/health` (or open the docs page at that port).

### 3. Claude Code slash command

```bash
mkdir -p .claude/commands
cp claude-setup/commands/daily-video.md .claude/commands/
```

### 4. Git

```bash
git init && git add -A && git commit -m "Initial hadith video pipeline"
```

</details>

## Daily use

Open the project in Claude Code and run:

```
/daily-video
```

Claude fetches the next hadith, writes the simplified script + hook, generates Fish Speech audio, times the words with Whisper, renders with Remotion, and saves video + upload metadata to `output/videos/`.

## Scheduling (optional)

Run automatically every morning at 07:00 via launchd:

```bash
cp launchd/com.rayan.daily-hadith.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.rayan.daily-hadith.plist
```

Requires the Fish Speech server to be running (start it at login, or add it as its own LaunchAgent). Logs go to `output/logs/`.

## Customizing the look

- Colors: `src/theme.ts`
- Fonts: `src/fonts.ts` (Cormorant Garamond + Inter via Google Fonts)
- Layout/animation: `src/components/`
- Live preview while editing: `npm run dev`

## Voice cloning (later)

`scripts/tts_fish.py` has a commented `references` field — add a 10–30s reference clip + transcript to clone a voice with Fish Speech.
