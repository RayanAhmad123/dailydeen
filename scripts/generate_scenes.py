#!/usr/bin/env python3
"""Generate scene illustrations for the current video via Replicate flux-schnell.

Reads work/scenes.json:
  { "hadith_no": "1", "episode": 1, "beat": "...",
    "scenes": [ {"prompt": "..."}, ... ] }

Writes public/scenes/hadith_<N>/scene_<i>.jpg and work/scenes_out.json.

Every prompt gets the story bible's style string appended and is checked
against a blocklist so no prompt can request a depiction of the Prophet,
other prophets, God, angels, or companions. Cast must be faceless silhouettes.

Env: REPLICATE_API_TOKEN (required). Cost: ~$0.003/image (flux-schnell).
"""
import json, os, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
MODEL_URL = "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"

# Safety net: image prompts must never reference religious figures.
# The real control is the prompt-writing rules in story/bible.json; this
# catches mistakes. Word-boundary-ish matching on lowercase.
BLOCKLIST = [
    "muhammad", "mohammed", "mustafa", "rasul", "prophet", "messenger",
    "allah", " god", "god ", "divine being", "deity", "lord ",
    "angel", "jibril", "gabriel", "mikail", "israfil",
    "moses", "musa ", "jesus", "isa ", "abraham", "ibrahim", "noah", "nuh ",
    "adam ", "yusuf ", "joseph", "solomon", "sulayman", "david", "dawud",
    "companion", "sahaba", "caliph", "khalifa", "imam ",
    "revelation", "quran", "koran",
]


def check_prompt(prompt: str) -> None:
    low = f" {prompt.lower()} "
    hits = [w for w in BLOCKLIST if w.strip() and w in low]
    if hits:
        sys.exit(f"BLOCKED: scene prompt contains forbidden terms {hits}:\n  {prompt}")


def generate(prompt: str, seed: int, token: str) -> bytes:
    # Retry on rate limits / transient server errors with backoff
    for attempt in range(7):
        r = requests.post(
            MODEL_URL,
            headers={"Authorization": f"Bearer {token}", "Prefer": "wait=60"},
            json={"input": {
                "prompt": prompt,
                "aspect_ratio": "9:16",
                "output_format": "jpg",
                "output_quality": 90,
                "num_outputs": 1,
                "megapixels": "1",
                "seed": seed,
            }},
            timeout=120,
        )
        if r.status_code == 429 or r.status_code >= 500:
            wait = min(15 * (2 ** attempt), 120)
            print(f"  HTTP {r.status_code}, retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        break
    r.raise_for_status()
    pred = r.json()

    # Poll if not finished despite Prefer: wait
    while pred["status"] not in ("succeeded", "failed", "canceled"):
        time.sleep(2)
        pr = requests.get(
            pred["urls"]["get"], headers={"Authorization": f"Bearer {token}"}, timeout=30
        )
        pr.raise_for_status()
        pred = pr.json()

    if pred["status"] != "succeeded":
        sys.exit(f"Replicate prediction {pred['status']}: {pred.get('error')}")

    out = pred["output"]
    url = out[0] if isinstance(out, list) else out
    img = requests.get(url, timeout=60)
    img.raise_for_status()
    return img.content


def main():
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        sys.exit("REPLICATE_API_TOKEN is not set. Get one at replicate.com/account/api-tokens")

    bible = json.loads((ROOT / "story" / "bible.json").read_text())
    scenes_spec = json.loads((ROOT / "work" / "scenes.json").read_text())
    vid = scenes_spec["id"]
    seed = int(bible.get("seed", 7341))
    style = bible["style"]

    out_dir = ROOT / "public" / "scenes" / vid
    out_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for i, scene in enumerate(scenes_spec["scenes"]):
        full_prompt = f"{scene['prompt']}, {style}"
        check_prompt(full_prompt)
        print(f"[{i + 1}/{len(scenes_spec['scenes'])}] generating: {scene['prompt'][:80]}...")
        img = generate(full_prompt, seed + i, token)
        path = out_dir / f"scene_{i}.jpg"
        path.write_bytes(img)
        files.append(f"scenes/{vid}/scene_{i}.jpg")
        print(f"  -> {path} ({len(img) / 1024:.0f} KB)")

    (ROOT / "work" / "scenes_out.json").write_text(json.dumps({"scenes": files}, indent=2))
    print(f"{len(files)} scenes written; work/scenes_out.json updated")


if __name__ == "__main__":
    main()
