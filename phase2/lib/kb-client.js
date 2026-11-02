/** Calls the Python kb.py search_kb over local HTTP (kb_server.py) so Phase 1's KB code is reused. */
const KB_URL = process.env.KB_URL || 'http://127.0.0.1:8765/search';

async function searchKb(query) {
  const t0 = process.hrtime.bigint();
  const res = await fetch(KB_URL, {
    method: 'POST',
    headers: {'content-type': 'application/json'},
    body: JSON.stringify({query})
  });
  if (!res.ok) throw new Error(`kb_server HTTP ${res.status}`);
  const {passages, kb_ms} = await res.json();
  return {passages, kb_ms, http_ms: Number(process.hrtime.bigint() - t0) / 1e6};
}

module.exports = {searchKb};
