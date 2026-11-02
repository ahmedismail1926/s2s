"""Run PASSES x 14 queries one at a time with retries; log raw records to out/raw.jsonl."""
import argparse
import asyncio
import json
import os
import time

from dotenv import load_dotenv
from google import genai

import agent
import config
from make_audio import save_wav


async def attempt_loop(client, wav) -> tuple[dict, bytes]:
    """Run a query with backoff on quota/transient errors; log every attempt."""
    attempts = []
    for n in range(config.MAX_RETRIES + 1):
        rec, pcm = await agent.run_query(client, wav)
        attempts.append({"attempt": n + 1, "outcome": rec["outcome"], "error": rec.get("error")})
        if rec["outcome"] in ("ok", "error", "no_audio") or (rec["outcome"] == "model_rejected" and n > len(config.MODELS)):
            break
        await asyncio.sleep(config.BACKOFF_S * 2 ** n if rec["outcome"] == "quota_429_503" else 1)
    rec["attempts"] = attempts
    return rec, pcm


async def main() -> None:
    """Execute all passes sequentially."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--vad-ms", default="200", help="silence_duration_ms or 'default'")
    ap.add_argument("--tag", default="vad200")
    args = ap.parse_args()
    config.VAD_SILENCE_MS = None if args.vad_ms == "default" else int(args.vad_ms)
    config.RAW_NAME = f"raw_{args.tag}.jsonl"
    load_dotenv()
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    config.OUT_DIR.mkdir(exist_ok=True)
    with open(config.OUT_DIR / config.RAW_NAME, "a", encoding="utf-8") as log:
        for p in range(1, config.PASSES + 1):
            for wav in sorted(config.AUDIO_DIR.glob("q*.wav")):
                rec, pcm = await attempt_loop(client, wav)
                rec.update(pass_no=p, query=wav.stem, ts=time.time())
                if pcm and p == 1:
                    save_wav(config.OUT_DIR / f"{wav.stem}.wav", pcm, config.OUT_RATE)
                log.write(json.dumps(rec, ensure_ascii=False) + "\n"); log.flush()
                print(p, wav.stem, rec["outcome"], len(rec["attempts"]), "attempts")
                await asyncio.sleep(config.GAP_S)


if __name__ == "__main__":
    asyncio.run(main())
