"""Configuration, read once from the environment.

Model ids are not guesses — they were verified against the live model list for
this key. Two traps worth recording, because both cost time:

* ``gemini-2.5-flash`` appears in the model list but returns 404 for keys
  created recently ("no longer available to new users").
* ``text-embedding-004``, the name most documentation still shows, does not
  exist on this API. The embedding models are ``gemini-embedding-*``.

Free-tier quota is per model per day, and it is small. ``gemini-3.6-flash``
allows twenty requests a day — roughly seven chatbot exchanges, since each one
costs two calls. The ``-flash-lite`` models carry a far larger allowance, which
is why one is the default here despite the full flash models being stronger.

Run ``python scripts/list_models.py`` to see what your key can actually reach.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

#: The fallback chain, tried in order. Quota is counted per model, so several
#: models on one key give several separate allowances — the cheapest form of
#: resilience available here. The lite models lead because their daily limits
#: are far larger; gemini-3.6-flash routes marginally better but allows only
#: twenty requests a day, so it sits last as a reserve.
#:
#: Add "groq:llama-3.3-70b-versatile" to bring in a genuinely independent
#: provider (needs GROQ_API_KEY and `pip install langchain-groq`). Entries whose
#: provider is unconfigured are skipped rather than failing the chain.
DEFAULT_CHAT_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.6-flash",
)
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"

#: The demo user. Multi-user support exists in the data layer; the UI picks one.
DEFAULT_USER_ID = "USER001"


class ConfigError(RuntimeError):
    """Something required is missing from the environment."""


def google_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        raise ConfigError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add a "
            "free key from https://aistudio.google.com/apikey"
        )
    return key


def chat_models() -> tuple[str, ...]:
    """The fallback chain, from GEMINI_CHAT_MODELS or the default."""
    configured = os.getenv("GEMINI_CHAT_MODELS", "").strip()
    if configured:
        specs = tuple(part.strip() for part in configured.split(",") if part.strip())
        if specs:
            return specs
    single = os.getenv("GEMINI_CHAT_MODEL", "").strip()
    if single:
        # A single override still gets the rest of the chain behind it, so
        # pinning a preferred model does not also discard the fallbacks.
        return (single,) + tuple(m for m in DEFAULT_CHAT_MODELS if m != single)
    return DEFAULT_CHAT_MODELS


def chat_model() -> str:
    """The preferred model — the head of the chain."""
    return chat_models()[0]


def groq_api_key() -> str:
    """Optional. Empty when Groq is not configured; the chain skips it."""
    return os.getenv("GROQ_API_KEY", "").strip()


def ollama_host() -> str:
    """Where a local Ollama server is listening."""
    return os.getenv("OLLAMA_HOST", "").strip() or "http://127.0.0.1:11434"


def embedding_model() -> str:
    return os.getenv("GEMINI_EMBEDDING_MODEL", "").strip() or DEFAULT_EMBEDDING_MODEL
