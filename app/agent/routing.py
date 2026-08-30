"""Intent detection — the explicit step in spec section 20.

The spec puts intent detection before the routing branch, and it turns out to be
load-bearing rather than decorative.

Left to their own judgement, the flash-lite models answer "what is compound
interest?" from memory instead of calling ``search_financial_knowledge``. The
answer is usually correct, but it is ungrounded: it cannot be traced to the
curated library, and the retrieval pipeline becomes decorative. Three separate
models behaved identically, and no amount of prompt strengthening changed it,
so this is a property of the models rather than a wording problem.

Rather than depending on a judgement the model does not reliably make, a
concept question is detected here and the passages are retrieved before the
model is asked anything. The model still decides everything else — which
transaction tool to call, whether a question needs more than one. This pins
down only the case that was actually failing.

Deliberately keyword-based, not a model call. It must be free, instant and
testable offline, and its judgements are conservative: when unsure it retrieves,
because unnecessary context is far cheaper than an ungrounded answer.
"""

from __future__ import annotations

import re
from enum import Enum


class Intent(str, Enum):
    """What kind of question this is."""

    #: A general financial concept. Needs the knowledge base, not user data.
    KNOWLEDGE = "knowledge"
    #: About the user's own money. Needs the transaction tools.
    PERSONAL = "personal"
    #: Both — "how does my spending compare with the 50/30/20 rule?"
    MIXED = "mixed"
    #: Neither clearly. Let the model decide unaided.
    UNCLEAR = "unclear"


#: Phrasings that signal a request for an explanation rather than a figure.
DEFINITION_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bwhat(?:'s| is| are| does)\b",
        r"\bwhat do(?:es)? .* mean\b",
        r"\bexplain\b",
        r"\bdefine\b",
        r"\bdefinition of\b",
        r"\bhow do(?:es)? .*\bwork\b",
        r"\bmeaning of\b",
        r"\btell me about\b",
        r"\bdifference between\b",
        r"\bwhy (?:should|is it|do people)\b",
        r"\bhow much should\b",
        r"\bis it (?:better|good|wise|smart) to\b",
    )
)

#: Topics the knowledge base actually covers. Retrieval is only forced when the
#: library has something to say — otherwise the model answers unaided.
CONCEPT_TERMS = (
    "50/30/20", "50-30-20", "50 30 20",
    "emergency fund", "rainy day",
    "compound interest", "compounding", "rule of 72",
    "credit utilisation", "credit utilization", "credit score", "credit card",
    "credit history", "credit limit",
    "secured loan", "unsecured loan", "collateral", "emi", "equated monthly",
    "debt to income", "debt-to-income", "avalanche", "snowball", "refinanc",
    "fixed rate", "floating rate",
    "sinking fund", "savings rate", "pay yourself first", "lifestyle inflation",
    "zero-based", "zero based", "envelope budget", "budgeting method",
    "diversif", "inflation", "risk and return", "asset allocation",
    "mutual fund", "equity", "sip", "systematic investment",
    "interest rate", "principal", "liquid fund", "fixed deposit",
)

#: Signals the question is about this user rather than about a concept.
#: Note the absence of a bare "me": "tell me about sinking funds" is a request
#: for an explanation, not a question about the user's money.
PERSONAL_MARKERS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bmy\b", r"\bmine\b", r"\bi (?:spend|spent|earn|earned|save|saved|have|paid)\b",
        r"\bcan i\b", r"\bshould i\b", r"\bam i\b", r"\bdid i\b", r"\bdo i\b",
        r"\bafford\b",
        r"\bthis month\b", r"\blast month\b",
    )
)


def mentions_concept(message: str) -> bool:
    lowered = message.casefold()
    return any(term in lowered for term in CONCEPT_TERMS)


def asks_for_definition(message: str) -> bool:
    lowered = message.casefold()
    return any(pattern.search(lowered) for pattern in DEFINITION_PATTERNS)


def is_personal(message: str) -> bool:
    lowered = message.casefold()
    return any(pattern.search(lowered) for pattern in PERSONAL_MARKERS)


def detect_intent(message: str) -> Intent:
    """Classify a message.

    A concept term plus personal phrasing is MIXED — "how does my spending
    compare with the 50/30/20 rule?" needs the rule *and* the user's figures,
    and answering from either alone is wrong.
    """
    if not message or not message.strip():
        return Intent.UNCLEAR

    concept = mentions_concept(message)
    personal = is_personal(message)
    definition = asks_for_definition(message)

    if concept and personal:
        return Intent.MIXED
    if concept and definition:
        return Intent.KNOWLEDGE
    if concept:
        # A bare concept term with no other signal, e.g. "emergency fund".
        return Intent.KNOWLEDGE
    if personal:
        return Intent.PERSONAL
    return Intent.UNCLEAR


def needs_knowledge(message: str) -> bool:
    """Whether to retrieve reference material before answering."""
    return detect_intent(message) in (Intent.KNOWLEDGE, Intent.MIXED)
