#!/usr/bin/env bash
# Start KB server, Phase 2 app and a cloudflared quick tunnel, print the webhook URL; Ctrl+C stops all.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p out
set -a; . ./.env; set +a

pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM

uv run python kb_server.py > out/kb_server.log 2>&1 & pids+=($!)
(cd phase2 && WS_PORT=3000 exec deno run -A app.js) > out/phase2_app.log 2>&1 & pids+=($!)
phase2/tools/cloudflared tunnel --url http://localhost:3000 > out/tunnel.log 2>&1 & pids+=($!)

for _ in $(seq 30); do
  url=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' out/tunnel.log | head -1 || true)
  [ -n "$url" ] && break
  sleep 1
done
echo "Webhook (paste in both jambonz webhooks): wss://${url#https://}/google-s2s"
echo "Logs in out/. Ctrl+C to stop."
wait
