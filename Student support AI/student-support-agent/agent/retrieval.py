"""Policy retrieval: split the handbook into chunks (one per '## [ID] Title' section) and return
only the few most relevant chunks for a query - never the whole document."""
import re
from dataclasses import dataclass

import config
from agent.textsearch import BM25, tokenize

MIN_SCORE = 1.5          # below this the policy is considered "not covering" the question
MIN_MATCHED_TERMS = 2    # at least 2 distinct query terms must appear in the chunk (1 if query is 1 word)
STRONG_SINGLE_TERM = 2.8  # one very distinctive term (e.g. "attendance") is enough


@dataclass
class Chunk:
    id: str
    title: str
    text: str


_cache = {"mtime": None, "chunks": [], "bm25": None}


def _load():
    path = config.HANDBOOK_FILE
    mtime = path.stat().st_mtime
    if _cache["mtime"] == mtime:
        return
    raw = path.read_text(encoding="utf-8")
    chunks = []
    for m in re.finditer(r"^## \[([A-Z0-9\-]+)\] (.+?)\n(.*?)(?=^## |\Z)", raw, re.S | re.M):
        chunks.append(Chunk(m.group(1), m.group(2).strip(), m.group(3).strip()))
    _cache.update(mtime=mtime, chunks=chunks,
                  bm25=BM25([f"{c.title} {c.title} {c.text}" for c in chunks]))  # title counted twice = boost


def all_chunks():
    _load()
    return _cache["chunks"]


def search(query: str, k: int = None):
    """Return up to k relevant chunks as dicts {id,title,text,score}. Empty list = nothing relevant."""
    k = k or config.TOP_K_CHUNKS
    _load()
    need = 1 if len(set(tokenize(query))) <= 1 else MIN_MATCHED_TERMS
    scored = [(s, m, c) for (s, m), c in zip(_cache["bm25"].scores(query), _cache["chunks"])]
    scored = [x for x in scored if x[0] >= MIN_SCORE and (x[1] >= need or x[0] >= STRONG_SINGLE_TERM)]
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return []
    top = scored[0][0]
    keep = [x for x in scored if x[0] >= 0.45 * top][:k]   # drop weak tail results
    return [{"id": c.id, "title": c.title, "text": c.text, "score": round(s, 2)} for s, _, c in keep]
