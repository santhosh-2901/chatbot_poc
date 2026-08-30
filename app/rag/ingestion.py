"""Load, split and index the financial knowledge base.

Run once (or after editing the documents):

    python scripts/build_index.py

Splitting is done on Markdown headings first, then by size, using the local
splitter in ``app.rag.splitter``. Heading-aware splitting matters more than it
sounds: it keeps "How much to hold" attached to "Emergency funds", so a chunk
retrieved in isolation still carries the context that makes it answerable, and
the heading gives the answer a citable section.

Alongside the FAISS index the chunks are written to ``chunks.json``. That file
is what makes the keyword fallback in ``retriever.py`` possible without any API
call — see the note there.
"""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.documents import Document

from app.config import PROJECT_ROOT
from app.rag.splitter import split_markdown

KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "financial_knowledge"
VECTORSTORE_DIR = PROJECT_ROOT / "vectorstore"
INDEX_DIR = VECTORSTORE_DIR / "faiss_index"
CHUNKS_FILE = VECTORSTORE_DIR / "chunks.json"

#: Large enough to hold a complete idea, small enough that a retrieved chunk is
#: mostly relevant rather than mostly padding.
CHUNK_SIZE = 900
CHUNK_OVERLAP = 120


class IngestionError(RuntimeError):
    """The knowledge base is missing or empty."""


def load_documents() -> list[Document]:
    """Read every Markdown file in the knowledge directory."""
    if not KNOWLEDGE_DIR.exists():
        raise IngestionError(f"Knowledge directory not found: {KNOWLEDGE_DIR}")

    documents: list[Document] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        if path.name.casefold() == "readme.md":
            continue  # scaffolding, not knowledge
        text = path.read_text(encoding="utf-8").strip()
        if text:
            documents.append(
                Document(page_content=text, metadata={"source": path.name})
            )

    if not documents:
        raise IngestionError(
            f"No knowledge documents in {KNOWLEDGE_DIR}. Expected Markdown files."
        )
    return documents


def split_documents(documents: list[Document]) -> list[Document]:
    """Split on headings, then on size, preserving the section title."""
    chunks: list[Document] = []
    for document in documents:
        chunks.extend(
            split_markdown(
                document.page_content,
                document.metadata,
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
            )
        )

    for position, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = position
    return chunks


def save_chunks(chunks: list[Document]) -> None:
    """Persist chunk text and metadata for the no-API keyword fallback."""
    VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
    payload = [
        {"text": chunk.page_content, "metadata": chunk.metadata} for chunk in chunks
    ]
    CHUNKS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_chunks() -> list[Document]:
    """Read the persisted chunks. Used by the fallback retriever."""
    if not CHUNKS_FILE.exists():
        raise IngestionError(
            f"{CHUNKS_FILE.name} not found. Run: python scripts/build_index.py"
        )
    payload = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    return [
        Document(page_content=row["text"], metadata=row["metadata"]) for row in payload
    ]


def build_index(verbose: bool = True) -> int:
    """Embed the knowledge base and write the FAISS index. Returns chunk count.

    Imported lazily so that the rest of the application — and the entire
    offline test suite — does not need faiss or a network connection.
    """
    from langchain_community.vectorstores import FAISS

    from app.llm import get_embeddings

    documents = load_documents()
    chunks = split_documents(documents)
    save_chunks(chunks)

    if verbose:
        print(f"{len(documents)} documents -> {len(chunks)} chunks")
        for path in sorted({c.metadata['source'] for c in chunks}):
            count = sum(1 for c in chunks if c.metadata["source"] == path)
            print(f"  {path:<24}{count:>3} chunks")
        print("\nembedding...")

    store = FAISS.from_documents(chunks, get_embeddings())
    INDEX_DIR.parent.mkdir(parents=True, exist_ok=True)
    store.save_local(str(INDEX_DIR))

    if verbose:
        print(f"index written to {INDEX_DIR}")
    return len(chunks)


def index_exists() -> bool:
    return (INDEX_DIR / "index.faiss").exists()
