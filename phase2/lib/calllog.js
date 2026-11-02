/**
 * Server-side per-call timestamp log (out/phase2_calls.jsonl).
 * These timestamps are taken on THIS server only: they exclude the caller's
 * network and audio-device delay and jambonz media-path latency.
 */
const fs = require('fs');
const path = require('path');

const LOG_PATH = process.env.PHASE2_LOG || path.join(__dirname, '..', '..', 'out', 'phase2_calls.jsonl');

function logEvent(rec) {
  fs.mkdirSync(path.dirname(LOG_PATH), {recursive: true});
  const t_ms = Date.now();
  fs.appendFileSync(LOG_PATH, JSON.stringify({t_ms, t_iso: new Date(t_ms).toISOString(), ...rec}) + '\n');
}

module.exports = {logEvent, LOG_PATH};
