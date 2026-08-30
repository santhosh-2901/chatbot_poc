"""Talk to the finance assistant from the terminal.

Usage:
    python scripts/chat.py                 # interactive
    python scripts/chat.py "why did I spend more this month?"
    python scripts/chat.py --user USER002  # a different user

Shows which tools each answer relied on, so you can see the routing decision
rather than guessing at it.
"""

from __future__ import annotations

import argparse
import sys

import _bootstrap  # noqa: F401  # must precede any app import

from app import config
from app.agent import build_agent
from app.config import ConfigError

BANNER = """
AI Personal Finance Assistant
Type a question, or 'exit' to quit. Try:
  where am I spending the most?
  why did I spend more this month?
  can I afford a 40000 phone?
  what is an emergency fund?
  how can I reduce my spending?
"""


def force_utf8() -> None:
    """Make the console safe for the rupee sign.

    Windows terminals default to cp1252, which cannot encode U+20B9, so every
    answer containing an amount would otherwise die on a UnicodeEncodeError.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def answer(agent, message: str) -> None:
    result = agent.chat(message)
    print(f"\n{result.response}\n")

    # Retrieved sources and model-chosen tools are reported separately: the
    # router fetches the first, the model decides the second, and collapsing
    # them would misrepresent which part of the system made which choice.
    trace = [f"intent: {result.intent}"]
    if result.sources:
        trace.append(f"retrieved: {', '.join(result.sources)}")
    if result.tools_used:
        trace.append(f"tools: {', '.join(result.tools_used)}")
    if not result.sources and not result.tools_used:
        trace.append("no tools or sources")
    if result.model:
        trace.append(f"model: {result.model}")
    print(f"  [{' | '.join(trace)}]\n")


def main() -> int:
    force_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="*", help="ask once and exit")
    parser.add_argument("--user", default=config.DEFAULT_USER_ID)
    parser.add_argument("--model", default=None, help="override the chat model")
    args = parser.parse_args()

    try:
        agent = build_agent(user_id=args.user, model=args.model)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.question:
        answer(agent, " ".join(args.question))
        return 0

    print(BANNER)
    while True:
        try:
            message = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not message:
            continue
        if message.lower() in {"exit", "quit", ":q"}:
            return 0
        try:
            answer(agent, message)
        except Exception as exc:  # keep the session alive on a transient failure
            print(f"  [error: {type(exc).__name__}: {exc}]\n", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
