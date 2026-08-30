"""Model factories and the fallback chain.

Everything that needs a model goes through here. No other module imports a
provider SDK, so swapping or adding a provider touches this file alone.

**Why a chain.** Free-tier quota is counted per model per day, not per key. A
chain of several models therefore multiplies the usable allowance without a
second signup — when one is exhausted the next is untouched. Groq is included
automatically if ``GROQ_API_KEY`` is set and ``langchain-groq`` is installed,
which adds a genuinely independent provider rather than another slice of the
same quota.

The fallback is applied in ``app.agent.agent``, not with LangChain's
``.with_fallbacks()``: that returns a ``RunnableWithFallbacks``, which has no
``bind_tools`` and so cannot drive a tool-calling agent.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app import config


class ProviderError(RuntimeError):
    """A model spec names a provider that is unavailable."""


def _build_gemini(model: str) -> BaseChatModel:
    """Build a Gemini chat model.

    ``temperature`` is deliberately unset: several current Gemini models use
    fixed sampling defaults and warn when it is passed. Determinism here comes
    from the tools, not the sampler.

    ``max_retries`` is held low on purpose. The SDK's default is to retry a 429
    with backoff and no output, which turns "out of free quota" into a
    three-minute silent stall instead of an error the caller can act on.
    """
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=config.google_api_key(),
        max_retries=2,
        timeout=60,
    )


def _build_groq(model: str) -> BaseChatModel:
    """Build a Groq chat model, if the optional dependency is present."""
    try:
        from langchain_groq import ChatGroq
    except ImportError as exc:
        raise ProviderError(
            "Groq is configured but langchain-groq is not installed. "
            "Run: pip install langchain-groq"
        ) from exc

    key = config.groq_api_key()
    if not key:
        raise ProviderError("Groq is configured but GROQ_API_KEY is not set.")
    return ChatGroq(model=model, api_key=key, temperature=0, max_retries=2)


def _build_ollama(model: str) -> BaseChatModel:
    """Build a local Ollama chat model.

    The only provider here with no quota and no network dependency, which makes
    it the right last link in the chain: whatever else has failed, this still
    answers. It is last rather than first because a small local model routes
    tools markedly worse than a hosted one — see the note in ``app.config``.

    The model must advertise the ``tools`` capability. Llama 3.0 does not;
    llama3.2 and qwen3 do. ``ollama show <model>`` lists it.
    """
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:
        raise ProviderError(
            "Ollama is configured but langchain-ollama is not installed. "
            "Run: pip install langchain-ollama"
        ) from exc

    return ChatOllama(
        model=model,
        base_url=config.ollama_host(),
        temperature=0,
        # A local model on CPU is slow; the default would give up too early.
        client_kwargs={"timeout": 180},
    )


BUILDERS = {
    "gemini": _build_gemini,
    "groq": _build_groq,
    "ollama": _build_ollama,
}


def parse_spec(spec: str) -> tuple[str, str]:
    """Split ``provider:model`` into its parts, defaulting to Gemini.

    ``"gemini-3.5-flash-lite"`` -> ``("gemini", "gemini-3.5-flash-lite")``
    ``"groq:llama-3.3-70b-versatile"`` -> ``("groq", "llama-3.3-70b-versatile")``
    """
    spec = spec.strip()
    if ":" in spec:
        provider, _, model = spec.partition(":")
        provider = provider.strip().casefold()
        if provider not in BUILDERS:
            raise ProviderError(
                f"Unknown provider {provider!r} in {spec!r}. "
                f"Known providers: {', '.join(BUILDERS)}."
            )
        return provider, model.strip()
    return "gemini", spec


@lru_cache(maxsize=8)
def get_llm(model: str | None = None) -> BaseChatModel:
    """One chat model, by spec. Defaults to the head of the chain."""
    provider, name = parse_spec(model or config.chat_model())
    return BUILDERS[provider](name)


def get_llm_chain(models: tuple[str, ...] | None = None) -> list[tuple[str, BaseChatModel]]:
    """The ordered fallback chain as ``(spec, model)`` pairs.

    Specs that cannot be built — a provider whose key is missing, say — are
    skipped rather than raised, so an optional Groq entry in the chain costs
    nothing when it is not configured. The first entry is never skipped
    silently: if nothing at all can be built, that is a real error.
    """
    specs = models or config.chat_models()
    chain: list[tuple[str, BaseChatModel]] = []
    problems: list[str] = []

    for spec in specs:
        try:
            chain.append((spec, get_llm(spec)))
        except (ProviderError, config.ConfigError) as exc:
            problems.append(f"{spec}: {exc}")

    if not chain:
        detail = "\n  ".join(problems) or "no models configured"
        raise ProviderError(f"No usable chat model.\n  {detail}")
    return chain


@lru_cache(maxsize=4)
def get_embeddings(model: str | None = None) -> GoogleGenerativeAIEmbeddings:
    """The embedding model backing the knowledge base."""
    return GoogleGenerativeAIEmbeddings(
        model=f"models/{model or config.embedding_model()}",
        google_api_key=config.google_api_key(),
    )
