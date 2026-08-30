"""Retrieval-augmented generation over the financial knowledge base.

RAG here answers *general* financial questions only. A user's own figures never
come from retrieval — they come from the analysis engine. Keeping that boundary
sharp is what stops the assistant explaining someone else's example numbers as
if they were yours.
"""

from app.rag.retriever import Passage, search

__all__ = ["Passage", "search"]
