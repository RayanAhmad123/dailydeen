# Voice-clone reference

Drop a reference voice here to clone it for the hadith voiceover:

- `reference.wav` — a clean 10–30s clip of the voice (mono or stereo, any sample rate)
- `reference.txt` — the EXACT words spoken in that clip, verbatim

Both are read by `scripts/tts_fish.py`. If `reference.wav` is absent, the
model's default voice is used. Override paths with `REF_AUDIO` / `REF_TEXT`.
