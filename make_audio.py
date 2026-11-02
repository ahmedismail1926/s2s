"""Generate 14 SYNTHETIC Egyptian Arabic question WAVs (16 kHz mono) via Gemini TTS."""
import os
import time
import wave

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

import config


def tts_pcm(client: genai.Client, text: str) -> bytes:
    """Return 24 kHz 16-bit mono PCM for the text."""
    resp = client.models.generate_content(
        model=config.TTS_MODEL,
        contents="قُل بلهجة مصرية طبيعية: " + text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=config.TTS_VOICE))),
        ),
    )
    return resp.candidates[0].content.parts[0].inline_data.data


def resample(pcm: bytes, src: int, dst: int) -> bytes:
    """Linear-interpolation resample of int16 PCM."""
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    n = int(len(x) * dst / src)
    y = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    return y.astype(np.int16).tobytes()


def save_wav(path, pcm: bytes, rate: int) -> None:
    """Write mono 16-bit WAV."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)


def main() -> None:
    """Synthesize all questions to audio/qXX.wav."""
    load_dotenv()
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    config.AUDIO_DIR.mkdir(exist_ok=True)
    for i, q in enumerate(config.QUESTIONS, 1):
        if (config.AUDIO_DIR / f"q{i:02d}.wav").exists():
            continue
        for _ in range(5):
            try:
                pcm = resample(tts_pcm(client, q), 24000, config.IN_RATE)
                break
            except Exception as e:  # noqa: BLE001
                print(f"q{i:02d} retry: {str(e)[-900:]}")
                time.sleep(45)
        else:
            raise SystemExit(f"q{i:02d} failed after retries")
        time.sleep(21)
        save_wav(config.AUDIO_DIR / f"q{i:02d}.wav", pcm, config.IN_RATE)
        print(f"q{i:02d} {len(pcm)/2/config.IN_RATE:.2f}s SYNTHETIC")


if __name__ == "__main__":
    main()
