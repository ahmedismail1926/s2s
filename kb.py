"""BM25 knowledge-base search with Arabic normalization and per-call timing."""
import json
import re
import time

from rank_bm25 import BM25Okapi

import config

_DIAC = re.compile(r"[ؐ-ًؚ-ٰٟـ]")
_PUNCT = re.compile(r"[^\w\s]")


def normalize(text: str) -> str:
    """Strip diacritics and normalize alef, ya and ta marbuta."""
    text = _DIAC.sub("", text)
    text = re.sub("[إأآٱ]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه")
    return _PUNCT.sub(" ", text).lower()


def tokenize(text: str) -> list[str]:
    """Normalize and split on whitespace."""
    return normalize(text).split()


_DOCS: list[dict] = json.loads(config.KB_PATH.read_text(encoding="utf-8"))
_BM25 = BM25Okapi([tokenize(d["title"] + " " + d["text"]) for d in _DOCS])


def search_kb(query: str) -> tuple[list[str], float]:
    """Return top-k passages and the call duration in ms."""
    t0 = time.perf_counter()
    scores = _BM25.get_scores(tokenize(query))
    order = sorted(range(len(_DOCS)), key=lambda i: -scores[i])[: config.TOP_K]
    passages = [_DOCS[i]["text"] for i in order if scores[i] > 0]
    return passages, (time.perf_counter() - t0) * 1000


if __name__ == "__main__":
    for q in config.QUESTIONS[:2]:
        p, ms = search_kb(q)
        print(f"{ms:.3f} ms | {q} -> {p[0] if p else None}")
