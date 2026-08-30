"""Markdown-aware chunking.

Written here rather than taken from ``langchain_text_splitters`` for a concrete
reason: importing that package executes its ``__init__``, which eagerly imports
``sentence_transformers`` and pulls in torch, datasets, sklearn and pyarrow. We
use none of those, and on this machine the combination segfaults the
interpreter once loaded alongside the rest of the stack. It also added roughly
fifteen seconds to every test run.

The splitting this project needs is narrow — headings, then size — so the
dependency was buying very little. Doing it directly costs about seventy lines
and removes an entire native toolchain from the import graph.

Chunks carry ``title`` and ``section`` so a retrieved passage can be cited.
"""

from __future__ import annotations

import re

from langchain_core.documents import Document

HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def _split_sections(text: str) -> list[tuple[str, str, str]]:
    """Break Markdown into ``(title, section, body)`` triples.

    ``title`` is the most recent ``#`` heading, ``section`` the most recent
    ``##``. Headings stay in the body: a chunk that has lost its heading reads
    like an assertion from nowhere, and the heading is often the clearest
    statement of what the passage is about.
    """
    sections: list[tuple[str, str, str]] = []
    title = ""
    section = ""
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append((title, section, body))
        buffer.clear()

    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            level, heading = len(match.group(1)), match.group(2)
            if level <= 2:
                flush()
                if level == 1:
                    title, section = heading, ""
                else:
                    section = heading
        buffer.append(line)

    flush()
    return sections


def _pack(paragraphs: list[str], chunk_size: int, overlap: int) -> list[str]:
    """Greedily pack paragraphs into chunks, carrying an overlap between them.

    The overlap is taken as whole trailing paragraphs rather than a fixed slice
    of characters, so a chunk never begins mid-sentence.
    """
    chunks: list[str] = []
    current: list[str] = []
    length = 0

    for paragraph in paragraphs:
        addition = len(paragraph) + (2 if current else 0)

        if current and length + addition > chunk_size:
            chunks.append("\n\n".join(current))

            carried: list[str] = []
            carried_length = 0
            for previous in reversed(current):
                if carried_length + len(previous) > overlap:
                    break
                carried.insert(0, previous)
                carried_length += len(previous) + 2

            current = carried
            length = carried_length

        current.append(paragraph)
        length += addition

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _hard_split(paragraph: str, chunk_size: int) -> list[str]:
    """Break a single oversized paragraph on sentence boundaries."""
    if len(paragraph) <= chunk_size:
        return [paragraph]

    pieces: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
        if current and len(current) + len(sentence) + 1 > chunk_size:
            pieces.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current.strip())
    return pieces


def split_markdown(
    text: str,
    metadata: dict,
    chunk_size: int = 900,
    chunk_overlap: int = 120,
) -> list[Document]:
    """Split one Markdown document into retrievable chunks."""
    documents: list[Document] = []

    for title, section, body in _split_sections(text):
        paragraphs: list[str] = []
        for block in re.split(r"\n\s*\n", body):
            block = block.strip()
            if block:
                paragraphs.extend(_hard_split(block, chunk_size))

        for chunk in _pack(paragraphs, chunk_size, chunk_overlap):
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={**metadata, "title": title, "section": section},
                )
            )

    return documents
