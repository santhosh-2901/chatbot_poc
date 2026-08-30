"""List the Gemini models this API key can actually reach.

Worth running before trusting any model id from documentation. Two examples
from building this project: ``gemini-2.5-flash`` is listed but returns 404 for
recently created keys, and ``text-embedding-004`` does not exist at all.

Usage:  python scripts/list_models.py
"""

from __future__ import annotations

import _bootstrap  # noqa: F401  # must precede any app import

from google import genai

from app import config


def main() -> None:
    client = genai.Client(api_key=config.google_api_key())

    chat: list[str] = []
    embedding: list[str] = []
    for model in client.models.list():
        actions = set(getattr(model, "supported_actions", []) or [])
        name = model.name.removeprefix("models/")
        if "generateContent" in actions:
            chat.append(name)
        if "embedContent" in actions:
            embedding.append(name)

    print(f"configured chat model:      {config.chat_model()}")
    print(f"configured embedding model: {config.embedding_model()}\n")

    print(f"chat models ({len(chat)}):")
    for name in chat:
        print(f"  {name}")

    print(f"\nembedding models ({len(embedding)}):")
    for name in embedding:
        print(f"  {name}")

    for label, configured, available in [
        ("chat", config.chat_model(), chat),
        ("embedding", config.embedding_model(), embedding),
    ]:
        if configured not in available:
            print(f"\nWARNING: configured {label} model {configured!r} is not listed.")


if __name__ == "__main__":
    main()
