# s2s — Egyptian Arabic speech-to-speech demo (Gemini Live)

A voice agent that answers spoken Egyptian Arabic questions from a small knowledge base (`kb.json`, BM25 search) using the Gemini Live API.

- **Phase 1** (Python): a latency/cost benchmark over 14 synthetic audio questions.
- **Phase 2** (`phase2/`): a jambonz phone agent that uses the same knowledge base.

## Setup

Requires Python 3.12+ with [uv](https://docs.astral.sh/uv/). Phase 2 also needs [Deno](https://deno.com/) (or Node 18+).

```bash
uv sync
cd phase2 && npm install && cd ..
```

### API key (required)

The demo needs **your own** Google Gemini API key. You can get one at https://aistudio.google.com/apikey.

```bash
cp .env.example .env
# then edit .env and set:
GOOGLE_API_KEY=your_key_here
```

`.env` is in `.gitignore`, so keep it that way and never commit it.

## Run

**Phase 1: benchmark**
```bash
uv run python make_audio.py     # generates audio/q01..q14.wav (Gemini TTS)
uv run python bench.py          # options: --vad-ms 200|default  --tag NAME
uv run python report.py         # writes the results to out/
```

**Phase 2: phone agent**
1. Download the [cloudflared](https://github.com/cloudflare/cloudflared/releases) binary to `phase2/tools/cloudflared` and make it executable (`chmod +x`).
2. Run `./run_phase2.sh`. It prints a `wss://…/google-s2s` URL.
3. In your jambonz account, paste that URL into the application's webhooks.

Settings (models, retries, paths) are in `config.py`.
