"""Retrieval over the financial knowledge base, with a fallback.

Semantic search through FAISS is the primary path. Behind it sits a keyword
retriever that needs no API call at all.

The fallback exists because embedding a query is a network request, and a
network request is a thing that fails — quota, connectivity, an outage mid-demo.
Without it, "what is an emergency fund?" would break for a reason that has
nothing to do with the knowledge base. With it, the answer degrades from
semantic matching to keyword matching, which on a corpus this small and this
well-titled is very nearly as good.

The fallback reads ``chunks.json``, written at index time, so it works even
when FAISS itself cannot be loaded.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from langchain_core.documents import Document

from app.rag import ingestion

#: Words carrying no topical signal. Deliberately short — an aggressive list
#: would strip terms like "rate" or "fund" that genuinely matter here.
STOPWORDS = frozenset(
    """a an and are as at be but by can do does for from had has have how i if in
    is it its me my of on or should that the their them there these this to was
    what when where which who why will with would you your about into over""".split()
)

TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Passage:
    """One retrieved chunk, with enough metadata to cite it."""

    text: str
    source: str
    section: str
    score: float

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "source": self.source,
            "section": self.section,
            "score": round(self.score, 4),
        }


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.casefold()) if t not in STOPWORDS and len(t) > 1]


class KeywordIndex:
    """A small TF-IDF index over the chunks. No dependencies, no network.

    Not a replacement for embeddings — it cannot match "rainy day money" to
    "emergency fund". It is a floor, not a ceiling: enough that a demo survives
    an outage.
    """

    def __init__(self, chunks: list[Document]) -> None:
        self.chunks = chunks
        self.tokens = [tokenize(c.page_content) for c in chunks]
        self.counts = [Counter(t) for t in self.tokens]

        document_frequency: Counter[str] = Counter()
        for tokens in self.tokens:
            document_frequency.update(set(tokens))

        total = max(len(chunks), 1)
        self.idf = {
            term: math.log(1 + total / (1 + frequency))
            for term, frequency in document_frequency.items()
        }

    def search(self, query: str, k: int = 4) -> list[Passage]:
        terms = tokenize(query)
        if not terms:
            return []

        scored: list[tuple[float, Document]] = []
        for counts, chunk in zip(self.counts, self.chunks):
            if not counts:
                continue
            length = sum(counts.values())
            score = sum(
                (counts[term] / length) * self.idf.get(term, 0.0) for term in terms
            )
            # A heading match is a strong signal on a corpus organised by topic.
            heading = f"{chunk.metadata.get('title', '')} {chunk.metadata.get('section', '')}"
            heading_terms = set(tokenize(heading))
            score += 0.15 * sum(1 for term in terms if term in heading_terms)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda pair: -pair[0])
        return [_as_passage(chunk, score) for score, chunk in scored[:k]]


def _as_passage(chunk: Document, score: float) -> Passage:
    return Passage(
        text=chunk.page_content.strip(),
        source=chunk.metadata.get("source", "unknown"),
        section=chunk.metadata.get("section") or chunk.metadata.get("title", ""),
        score=score,
    )


@lru_cache(maxsize=1)
def _keyword_index() -> KeywordIndex:
    return KeywordIndex(ingestion.load_chunks())


@lru_cache(maxsize=1)
def _vector_store():
    """Load the FAISS index. Raises if it is missing or unreadable."""
    from langchain_community.vectorstores import FAISS

    from app.llm import get_embeddings

    if not ingestion.index_exists():
        raise ingestion.IngestionError(
            "No FAISS index found. Run: python scripts/build_index.py"
        )
    return FAISS.load_local(
        str(ingestion.INDEX_DIR),
        get_embeddings(),
        # The index is generated locally by build_index.py and never downloaded,
        # so deserialising it is safe here.
        allow_dangerous_deserialization=True,
    )


def search(query: str, k: int = 4) -> tuple[list[Passage], str]:
    """Find passages relevant to a query.

    Returns the passages and the method that produced them, ``"semantic"`` or
    ``"keyword"``. The caller surfaces that, so a degraded answer is visibly
    degraded rather than quietly worse.
    """
    if not query or not query.strip():
        return [], "none"

    try:
        store = _vector_store()
        hits = store.similarity_search_with_score(query, k=k)
        # FAISS returns L2 distance, where smaller is closer. Invert it so that
        # a larger score means a better match, consistent with the keyword path.
        passages = [
            _as_passage(document, 1.0 / (1.0 + float(distance)))
            for document, distance in hits
        ]
        if passages:
            return passages, "semantic"
    except Exception:
        # Any failure here — missing index, exhausted quota, no connectivity —
        # is a reason to degrade, not to fail the request.
        pass

    return _keyword_index().search(query, k), "keyword"


def clear_cache() -> None:
    """Drop cached indexes. Call after rebuilding."""
    _keyword_index.cache_clear()
    _vector_store.cache_clear()
