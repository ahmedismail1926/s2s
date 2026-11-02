"""Local HTTP wrapper around kb.search_kb for the Phase 2 Node server."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

import kb


class Handler(BaseHTTPRequestHandler):
    """POST /search {query} -> {passages, kb_ms}."""

    def do_POST(self) -> None:
        """Serve one search request."""
        n = int(self.headers.get("content-length", 0))
        q = json.loads(self.rfile.read(n) or b"{}").get("query", "")
        passages, ms = kb.search_kb(q)
        body = json.dumps({"passages": passages, "kb_ms": ms}, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        """Silence default logging."""


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
