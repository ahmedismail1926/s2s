# Google Speech-to-Speech Example

Example jambonz application showcasing voice AI built on Google's Gemini Live API. Two routes are included:

| Route | Endpoint | Auth |
|---|---|---|
| **Gemini Developer API** | `wss://your-server/google-s2s` | API key from [Google AI Studio](https://aistudio.google.com/apikey) |
| **Vertex AI Live API** | `wss://your-server/vertex-s2s` | OAuth (service-account JSON) |

Both routes share the same agent logic (`weather-shared.js`) — they differ only in endpoint and auth.

## Prerequisites
- Node.js v18+
- A Jambonz account
- One of:
  - A Gemini API key (AI Studio), OR
  - A Google Cloud project with Vertex AI enabled + a service-account JSON key with `roles/aiplatform.user`

## Install

```bash
npm install
```

## Run

### Gemini Developer API route (`/google-s2s`)

Required env var:

```bash
GEMINI_API_KEY=AIza... npm start
```

Optional:

| Var | Default |
|---|---|
| `GEMINI_MODEL` | `models/gemini-3.1-flash-live-preview` |

### Vertex AI Live API route (`/vertex-s2s`)

Required env var:

```bash
GOOGLE_SERVICE_ACCOUNT_KEY_PATH=/abs/path/to/sa-key.json npm start
```

Optional:

| Var | Default |
|---|---|
| `VERTEX_PROJECT_ID` | `project_id` field inside the JSON |
| `VERTEX_LOCATION` | `us-central1` |
| `VERTEX_MODEL` | `gemini-live-2.5-flash-native-audio` |

The Vertex route mints a fresh OAuth access token (`ya29.…`) from the service-account JSON each session. mod_google_s2s detects the `ya29.` prefix and sends it as `Authorization: Bearer …` on the WebSocket upgrade.

### Both routes at once

Set both env vars — each route handles its own endpoint independently:

```bash
GEMINI_API_KEY=AIza... \
GOOGLE_SERVICE_ACCOUNT_KEY_PATH=/abs/path/to/sa-key.json \
npm start
```

## Configuring Jambonz application

Point your Jambonz application's WebSocket URL at the route you want:

```
wss://your-server/google-s2s     # Gemini Developer
wss://your-server/vertex-s2s     # Vertex AI
```

## How it works

When a call comes in:

1. The app answers the call.
2. Mints credential (API key passthrough for Gemini, or OAuth token from JSON for Vertex).
3. Runs the `llm` verb, which tells feature-server / FreeSWITCH to open a WebSocket to Google.
4. Sends a `setup` payload with system instruction + tools (weather function).
5. Gemini greets the caller; conversation flows bidirectionally.

## Function calling

The example wires a `get_weather` tool. When the model invokes it, `weather-shared.js` calls the weather utility and returns the result back into the conversation.

## MCP server tools (optional)

Run the MCP server in a separate terminal:

```bash
MCP_SERVER_PORT=3001 npm run mcp-server
```

Then start the app with `MCP_SERVER_URL` pointing at it:

```bash
GEMINI_API_KEY=AIza... \
MCP_SERVER_URL='http://localhost:3001/sse' \
npm start
```

When `MCP_SERVER_URL` is set, the built-in `get_weather` tool is replaced by tools advertised from the MCP server.

## Secrets

- Never commit your API key or service-account JSON.
- Source credentials only from env vars; the routes refuse to run if env is missing.
- For production, store the service-account JSON outside the repo and reference its path via `GOOGLE_SERVICE_ACCOUNT_KEY_PATH`.

## Additional resources

- [Jambonz documentation](https://docs.jambonz.org/)
- [Gemini Live API (AI Studio)](https://ai.google.dev/api/live)
- [Vertex AI Live API](https://cloud.google.com/vertex-ai/generative-ai/docs/live-api)
- [Vertex AI service-account setup](https://cloud.google.com/vertex-ai/docs/authentication)
