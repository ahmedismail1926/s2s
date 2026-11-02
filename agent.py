"""One Gemini Live S2S turn: stream a WAV, serve search_kb, record timings and usage."""
import asyncio
import time
import wave

from google import genai
from google.genai import types

import config
import kb

SEARCH_KB = {
    "name": "search_kb",
    "description": "Search the company knowledge base and return the top 3 passages.",
    "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING", "description": "search query in Arabic"}},
                   "required": ["query"]},
}
_model_idx = 0


def live_config() -> types.LiveConnectConfig:
    """Build the Live session config."""
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=config.SYSTEM_PROMPT,
        tools=[{"function_declarations": [SEARCH_KB]}],
        output_audio_transcription=types.AudioTranscriptionConfig(),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=None if config.VAD_SILENCE_MS is None else types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(silence_duration_ms=config.VAD_SILENCE_MS)),
    )


def read_pcm(path) -> bytes:
    """Read 16 kHz mono PCM from a WAV."""
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == config.IN_RATE and w.getnchannels() == 1
        return w.readframes(w.getnframes())


async def stream(session, pcm: bytes, rec: dict) -> None:
    """Send audio at real-time pace, mark end of speech, then 300 ms of silence."""
    step = int(config.IN_RATE * config.CHUNK_MS / 1000) * 2
    blob = lambda b: types.Blob(data=b, mime_type=f"audio/pcm;rate={config.IN_RATE}")
    t0 = time.perf_counter()
    n = 0
    for i in range(0, len(pcm), step):
        n += 1
        await session.send_realtime_input(audio=blob(pcm[i:i + step]))
        await asyncio.sleep(max(0.0, t0 + n * config.CHUNK_MS / 1000 - time.perf_counter()))
    rec["t_end_speech"] = time.perf_counter()
    sil = bytes(step)
    for k in range(config.SILENCE_MS // config.CHUNK_MS):
        await session.send_realtime_input(audio=blob(sil))
        await asyncio.sleep(max(0.0, rec["t_end_speech"] + (k + 1) * config.CHUNK_MS / 1000 - time.perf_counter()))
    k = config.SILENCE_MS // config.CHUNK_MS
    while "t_turn_complete" not in rec and time.perf_counter() - rec["t_end_speech"] < config.TURN_TIMEOUT_S:
        k += 1  # keep the mic stream alive with silence, as a real telephony stream would
        await session.send_realtime_input(audio=blob(sil))
        await asyncio.sleep(max(0.0, rec["t_end_speech"] + k * config.CHUNK_MS / 1000 - time.perf_counter()))


async def receive(session, rec: dict, audio: bytearray) -> None:
    """Handle tool calls, collect audio, timestamps, transcripts and usage until turn_complete."""
    out_tr, in_tr = [], []
    done = False
    while not done:
      async for msg in session.receive():
          now = time.perf_counter()
          if msg.usage_metadata:
              rec["usage"] = msg.usage_metadata.model_dump(exclude_none=True)
          if msg.tool_call:
              rec.setdefault("t_tool_call", now)
              resps = []
              for fc in msg.tool_call.function_calls:
                  passages, ms = kb.search_kb((fc.args or {}).get("query", ""))
                  rec.setdefault("kb_calls", []).append({"query": (fc.args or {}).get("query"), "kb_ms": ms, "hits": len(passages)})
                  resps.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"passages": passages}))
              await session.send_tool_response(function_responses=resps)
              rec["t_tool_resp"] = time.perf_counter()
          sc = msg.server_content
          if not sc:
              continue
          if sc.model_turn:
              for p in sc.model_turn.parts:
                  if p.inline_data and p.inline_data.data:
                      rec.setdefault("t_first_audio", now)
                      audio.extend(p.inline_data.data)
          if sc.output_transcription and sc.output_transcription.text:
              out_tr.append(sc.output_transcription.text)
          if sc.input_transcription and sc.input_transcription.text:
              in_tr.append(sc.input_transcription.text)
          if sc.turn_complete:
              if "t_first_audio" in rec or "t_tool_call" not in rec:
                  rec["t_turn_complete"] = now
                  done = True
                  break
    rec["transcript_out"], rec["transcript_in"] = "".join(out_tr), "".join(in_tr)


def classify(exc: Exception) -> str:
    """Map an exception to an outcome label."""
    s = str(exc)
    if any(k in s for k in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "quota")):
        return "quota_429_503"
    if any(k in s.lower() for k in ("not found", "404", "not supported", "is not")) and "model" in s.lower():
        return "model_rejected"
    return "error"


async def run_query(client: genai.Client, wav_path) -> tuple[dict, bytes]:
    """Run one turn on the current model; returns (record, agent PCM at 24 kHz)."""
    global _model_idx
    pcm = read_pcm(wav_path)
    rec: dict = {"model": config.MODELS[_model_idx], "audio_in_s": len(pcm) / 2 / config.IN_RATE}
    audio = bytearray()
    try:
        async with client.aio.live.connect(model=rec["model"], config=live_config()) as session:
            rx = asyncio.create_task(receive(session, rec, audio))
            await stream(session, pcm, rec)
            await asyncio.wait_for(rx, config.TURN_TIMEOUT_S)
        rec["outcome"] = "ok" if "t_first_audio" in rec else "no_audio"
    except Exception as e:  # noqa: BLE001
        rec["outcome"], rec["error"] = classify(e), f"{type(e).__name__}: {str(e)[:300]}"
        if rec["outcome"] == "model_rejected" and _model_idx + 1 < len(config.MODELS):
            _model_idx += 1
    rec["audio_out_s"] = len(audio) / 2 / config.OUT_RATE
    return rec, bytes(audio)


async def one_shot(path: str) -> None:
    """Run a single query and print a compact summary (no key printed)."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    rec, _ = await run_query(genai.Client(api_key=os.environ["GOOGLE_API_KEY"]), path)
    e = rec.get("t_end_speech")
    print({k: (round(v - e, 3) if k.startswith("t_") and e and k != "t_end_speech" else v)
           for k, v in rec.items() if k != "t_end_speech" and k != "usage"}, rec.get("usage"))


if __name__ == "__main__":
    import sys
    asyncio.run(one_shot(sys.argv[1]))
