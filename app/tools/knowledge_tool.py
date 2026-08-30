"""The RAG tool.

Deliberately separate from the finance tools, because it answers a different
kind of question. The finance tools read *this user's* records. This one reads a
curated library of general financial education and knows nothing about anyone's
money.

Keeping that boundary explicit in the description is what stops the model
answering "how much should I have saved?" from the knowledge base — the library
contains a worked example using 40,000 a month, and a model that blurs the two
will happily present that example as the user's own position.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool

from app.rag import retriever


@tool
def search_financial_knowledge(query: str) -> dict:
    """Search a library of general financial education and return relevant
    passages with their sources.

    Covers: budgeting methods including the 50/30/20 rule, zero-based and
    envelope budgeting; savings rate and sinking funds; emergency funds, how
    large they should be and where to hold them; credit scores, credit
    utilisation and credit card interest; loans, secured versus unsecured, EMI
    and repayment strategies; investing basics, compound interest, risk,
    diversification and inflation.

    Use this whenever the user asks what something means or how something
    works: what is an emergency fund, how does the 50/30/20 rule work, what is
    compound interest, what is credit utilisation, what is the difference
    between a secured and an unsecured loan.

    This tool knows NOTHING about the user's own money. It returns general
    guidance only. Any figure appearing in a passage is an illustrative example
    from the library, never this user's actual position — never present one as
    though it were. For the user's real numbers use the transaction tools, and
    when a question needs both, call both.

    Args:
        query: The concept to look up, in natural language.
    """
    passages, method = retriever.search(query, k=4)

    if not passages:
        return {
            "query": query,
            "found": 0,
            "passages": [],
            "note": "Nothing relevant in the knowledge base. Say so rather than guessing.",
        }

    return {
        "query": query,
        "found": len(passages),
        #: "keyword" means semantic search was unavailable and this is a
        #: degraded result — worth knowing when an answer looks thin.
        "retrieval_method": method,
        "passages": [passage.as_dict() for passage in passages],
        "note": (
            "General educational content. Contains no information about this "
            "user's finances; any amounts shown are illustrative examples."
        ),
    }


def build_knowledge_tools() -> list[BaseTool]:
    return [search_financial_knowledge]
