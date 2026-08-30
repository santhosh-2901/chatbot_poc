"""The agent: a tool-calling ReAct loop over the finance tools.

LangChain 1.x supplies the loop through ``create_agent``, which compiles to a
LangGraph state graph. We are not hand-rolling a ReAct text parser — the model
emits structured tool calls and the runtime executes them. Small local models
need the text-parsing variant; a hosted model does not, and the structured path
fails far less often.

Conversation memory is a LangGraph checkpointer keyed by thread id, so a
follow-up like "what about last month?" resolves against what came before.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from app import config
from app.agent.prompts import system_prompt
from app.agent.routing import Intent, detect_intent, needs_knowledge
from app.llm import get_llm_chain
from app.rag import retriever
from app.tools import build_finance_tools


class RateLimitError(RuntimeError):
    """The free-tier quota for this model is exhausted.

    Worth its own type because the raw failure is a wall of nested tracebacks
    ending in a 429, and the actionable part — which model, how long to wait —
    is buried in the middle of it.
    """


def _as_rate_limit(exc: Exception, model: str) -> RateLimitError | None:
    """Translate a quota failure into something a user can act on."""
    text = str(exc)
    if "RESOURCE_EXHAUSTED" not in text and "429" not in text:
        return None

    delay = re.search(r"retryDelay['\"]?: ['\"]?(\d+)s", text) or re.search(
        r"retry in ([\d.]+)s", text
    )
    limit = re.search(r"quotaValue['\"]?: ['\"]?(\d+)", text) or re.search(
        r"limit: (\d+)", text
    )

    parts = [f"Free-tier quota exhausted for model {model!r}."]
    if limit:
        parts.append(f"The daily allowance is {limit.group(1)} requests.")
    if delay:
        parts.append(f"Retry in about {round(float(delay.group(1)))}s.")
    parts.append(
        "Each exchange costs at least two requests. Switch models with "
        "GEMINI_CHAT_MODEL in .env, or wait for the quota to reset."
    )
    return RateLimitError(" ".join(parts))


@dataclass(frozen=True)
class ChatResult:
    """One assistant turn, plus the evidence behind it."""

    response: str
    tools_used: tuple[str, ...]
    #: Raw tool payloads, kept so the API and tests can verify that a quoted
    #: figure actually appeared in a tool result.
    tool_results: tuple[dict[str, Any], ...]
    #: Which model actually answered. Not cosmetic — when the head of the chain
    #: is exhausted the reply comes from a different model, and both the UI and
    #: anyone debugging a bad answer need to know which.
    model: str = ""
    #: The detected intent (spec section 20).
    intent: str = Intent.UNCLEAR.value
    #: Knowledge-base sources retrieved before the model was asked. Separate
    #: from ``tools_used`` because the model did not choose these — the router
    #: did, and conflating the two would misreport what the model decided.
    sources: tuple[str, ...] = ()


def extract_text(message: BaseMessage) -> str:
    """Flatten a message's content to plain text.

    Current Gemini models return a list of content blocks rather than a string,
    so ``message.content`` cannot be used directly.
    """
    content = message.content
    if isinstance(content, str):
        return content

    parts: list[str] = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(part for part in parts if part).strip()


class FinanceAgent:
    """A conversational agent scoped to a single user."""

    def __init__(self, user_id: str | None = None, model: str | None = None) -> None:
        self.user_id = user_id or config.DEFAULT_USER_ID
        self.tools = build_finance_tools(self.user_id)
        self._prompt = system_prompt(self.user_id)

        chain = get_llm_chain((model,) if model else None)
        self.models = tuple(spec for spec, _ in chain)

        # One checkpointer shared across the chain, so a fallback model picks up
        # the same conversation rather than restarting it mid-thread.
        self._checkpointer = InMemorySaver()
        self._graphs = [
            (
                spec,
                create_agent(
                    model=llm,
                    tools=self.tools,
                    system_prompt=self._prompt,
                    checkpointer=self._checkpointer,
                ),
            )
            for spec, llm in chain
        ]

    @property
    def model(self) -> str:
        """The preferred model. What actually answered is on the result."""
        return self.models[0]

    def chat(self, message: str, thread_id: str = "default") -> ChatResult:
        """Send one message, falling through the chain if quota runs out.

        Only quota failures trigger a fallback. A malformed request or a bug in
        a tool would fail identically on every model, so retrying it three more
        times would just be slower.
        """
        if not message or not message.strip():
            raise ValueError("message cannot be empty")

        intent = detect_intent(message)
        prompt, sources = self._ground(message)

        exhausted: list[str] = []

        for spec, graph in self._graphs:
            try:
                state = graph.invoke(
                    {"messages": [{"role": "user", "content": prompt}]},
                    config={"configurable": {"thread_id": thread_id}},
                )
            except Exception as exc:
                quota = _as_rate_limit(exc, spec)
                if quota is None:
                    raise
                exhausted.append(spec)
                continue
            return self._summarize(
                state["messages"], model=spec, intent=intent.value, sources=sources
            )

        raise RateLimitError(
            "Every model in the chain is out of free-tier quota: "
            f"{', '.join(exhausted)}. Wait for the daily reset, or add a "
            "provider with GEMINI_CHAT_MODELS / GROQ_API_KEY in .env."
        )

    @staticmethod
    def _ground(message: str) -> tuple[str, tuple[str, ...]]:
        """Attach reference material when the question is conceptual.

        See ``app.agent.routing`` for why this is not left to the model: the
        available models answer concept questions from memory rather than
        calling the retrieval tool, which produces plausible but ungrounded
        answers. Retrieving first removes the choice.
        """
        if not needs_knowledge(message):
            return message, ()

        passages, _ = retriever.search(message, k=3)
        if not passages:
            return message, ()

        blocks = [f"[{p.source} - {p.section}]\n{p.text}" for p in passages]
        instructions = (
            "--- Reference material from the financial knowledge library ---\n"
            "Base any explanation of a financial concept on these passages and "
            "name the source file you used. Amounts appearing here are "
            "illustrative examples from the library, never this user's own "
            "figures - for those, call the transaction tools.\n\n"
        )
        grounded = f"{message}\n\n{instructions}" + "\n\n".join(blocks)
        return grounded, tuple(dict.fromkeys(p.source for p in passages))

    @staticmethod
    def _summarize(
        messages: list[BaseMessage],
        model: str = "",
        intent: str = Intent.UNCLEAR.value,
        sources: tuple[str, ...] = (),
    ) -> ChatResult:
        used: list[str] = []
        results: list[dict[str, Any]] = []

        for message in messages:
            if isinstance(message, AIMessage):
                for call in message.tool_calls or []:
                    used.append(call["name"])
            elif isinstance(message, ToolMessage):
                results.append(
                    {"tool": message.name, "content": message.content}
                )

        final = extract_text(messages[-1]) if messages else ""
        return ChatResult(
            response=final,
            tools_used=tuple(used),
            tool_results=tuple(results),
            model=model,
            intent=intent,
            sources=sources,
        )

    def reset(self, thread_id: str = "default") -> None:
        """Forget one conversation thread."""
        self._checkpointer.delete_thread(thread_id)


def build_agent(user_id: str | None = None, model: str | None = None) -> FinanceAgent:
    return FinanceAgent(user_id=user_id, model=model)
