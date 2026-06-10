#!/bin/bash
# One-time setup for the Daily Hadith Video pipeline (macOS).
# Run from the project folder:  bash setup.sh
set -e
cd "$(dirname "$0")"

echo "=== 1/6 Homebrew packages (ffmpeg) ==="
if ! command -v brew >/dev/null; then
  echo "Homebrew not found — install it first: https://brew.sh"; exit 1
fi
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg

echo "=== 2/6 Node dependencies (Remotion) ==="
npm install --no-audit --no-fund

echo "=== 3/6 Python dependencies ==="
python3 -m pip install --upgrade requests ormsgpack openai-whisper huggingface_hub

echo "=== 4/6 Claude Code slash command ==="
mkdir -p .claude/commands
cp claude-setup/commands/daily-video.md .claude/commands/

echo "=== 5/6 Git repo ==="
if [ ! -d .git ]; then
  git init -q && git add -A && git commit -qm "Initial hadith video pipeline"
  echo "git repo initialized"
fi

echo "=== 6/6 Fish Speech (self-hosted TTS) ==="
# Official current model line (Fish Audio S2) targets Linux + 24GB GPU,
# but ships CPU installs. We set it up natively with the CPU extra.
# NOTE: S2-Pro is a 4B model — on CPU it will be SLOW (possibly minutes
# per clip). See README "Fish Speech alternatives" if that's unacceptable.
FS_DIR="$HOME/fish-speech"
if [ ! -d "$FS_DIR" ]; then
  git clone https://github.com/fishaudio/fish-speech "$FS_DIR"
fi
cd "$FS_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[cpu]
mkdir -p checkpoints
if [ ! -d checkpoints/s2-pro ]; then
  echo "Downloading s2-pro weights (~several GB)..."
  hf download fishaudio/s2-pro --local-dir checkpoints/s2-pro
fi
deactivate
cd - >/dev/null

cat <<'EOF'

==========================================================
Setup complete.

Start the Fish Speech server (keep it running):

  cd ~/fish-speech && source .venv/bin/activate
  python tools/api_server.py \
    --llama-checkpoint-path checkpoints/s2-pro \
    --decoder-checkpoint-path checkpoints/s2-pro/codec.pth \
    --listen 0.0.0.0:8080

Verify:   curl http://127.0.0.1:8080/v1/health
Then in Claude Code:   /daily-video
==========================================================
EOF
