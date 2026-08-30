"""FastAPI backend (spec section 29, Phase 6).

Exposes the agent and the analysis engine over HTTP so the Streamlit frontend
holds no business logic of its own.

Agents are cached per user. Building one constructs a graph per model in the
fallback chain and reads the dataset, which is wasteful per request and — more
importantly — would discard conversation memory between turns.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import config
from app.agent import FinanceAgent
from app.agent.agent import RateLimitError
from app.analysis import budget_status, compare_months, summarize_month
from app.llm import ProviderError
from app.services import transaction_service as tx
from app.services.data_loader import DataError, load_users
from app.services.transaction_service import UnknownMonthError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Personal Finance Assistant",
    description="Conversational analysis over synthetic personal-finance data.",
    version="1.0.0",
)

# The Streamlit frontend is a separate origin. Wide open is fine for a local
# POC and would not be acceptable in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_agents: dict[str, FinanceAgent] = {}


def get_agent(user_id: str) -> FinanceAgent:
    """One long-lived agent per user, so conversation memory survives."""
    if user_id not in _agents:
        try:
            _agents[user_id] = FinanceAgent(user_id)
        except DataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ProviderError, config.ConfigError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _agents[user_id]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    user_id: str = Field(default=config.DEFAULT_USER_ID)
    message: str = Field(min_length=1, max_length=2000)
    #: Conversation key. Distinct threads keep separate histories.
    thread_id: str = Field(default="default")


class ChatResponse(BaseModel):
    response: str
    #: Tools the model chose to call.
    tools_used: list[str]
    #: Knowledge-base files retrieved by the router before the model ran.
    #: Separate from tools_used because the model did not choose these.
    sources: list[str]
    intent: str
    model: str


class CategoryRow(BaseModel):
    category: str
    amount: int
    share_of_expenses: float
    budgeted: int | None = None
    over_budget: bool = False


class TransactionRow(BaseModel):
    date: str
    merchant: str
    category: str
    type: str
    amount: int


class Dashboard(BaseModel):
    """Everything the dashboard needs, in one request."""

    user_id: str
    name: str
    currency: str
    month: str
    available_months: list[str]
    income: int
    expenses: int
    net: int
    savings_rate: float
    previous_month: str | None
    expense_change: int | None
    percentage_change: float | None
    categories: list[CategoryRow]
    recent_transactions: list[TransactionRow]
    total_budgeted: int | None
    breached_categories: list[str]
    savings_balance: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "models": list(config.chat_models())}


@app.get("/users")
def users() -> list[dict]:
    return [
        {
            "user_id": user.user_id,
            "name": user.name,
            "currency": user.currency,
            "monthly_income": user.monthly_income,
        }
        for user in load_users()
    ]


@app.get("/months/{user_id}")
def months(user_id: str) -> dict:
    try:
        return {"months": list(tx.available_months(user_id))}
    except DataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/dashboard/{user_id}", response_model=Dashboard)
def dashboard(user_id: str, month: str | None = None) -> Dashboard:
    """Aggregate view for the dashboard.

    One endpoint rather than five, because the frontend renders a single screen
    and five round trips would only add latency and partial-failure states.
    """
    try:
        from app.services.data_loader import get_user

        user = get_user(user_id)
        resolved = tx.resolve_month(user_id, month)
        summary = summarize_month(user_id, resolved)
    except UnknownMonthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Budget is optional: a user may not have set one.
    budgeted: dict[str, int] = {}
    total_budgeted = None
    breached: list[str] = []
    try:
        status = budget_status(user_id, resolved)
        budgeted = {line.category.value: line.budgeted for line in status.lines}
        total_budgeted = status.total_budgeted
        breached = [c.value for c in status.breached_categories]
    except DataError:
        pass

    # A comparison needs a preceding month, which the earliest month lacks.
    previous = None
    expense_change = None
    percentage_change = None
    try:
        comparison = compare_months(user_id, resolved)
        previous = comparison.previous_month
        expense_change = comparison.expense_change
        percentage_change = comparison.percentage_change
    except (DataError, ValueError):
        pass

    return Dashboard(
        user_id=user_id,
        name=user.name,
        currency=user.currency,
        month=resolved,
        available_months=list(tx.available_months(user_id)),
        income=summary.income,
        expenses=summary.expenses,
        net=summary.net,
        savings_rate=summary.savings_rate,
        previous_month=previous,
        expense_change=expense_change,
        percentage_change=percentage_change,
        categories=[
            CategoryRow(
                category=c.category.value,
                amount=c.amount,
                share_of_expenses=c.share_of_expenses,
                budgeted=budgeted.get(c.category.value),
                over_budget=c.category.value in breached,
            )
            for c in summary.categories
        ],
        recent_transactions=[
            TransactionRow(
                date=t.date.isoformat(),
                merchant=t.merchant,
                category=t.category.value,
                type=t.type.value,
                amount=t.amount,
            )
            for t in tx.recent_transactions(user_id, limit=12)
        ],
        total_budgeted=total_budgeted,
        breached_categories=breached,
        savings_balance=user.savings_balance,
    )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    agent = get_agent(request.user_id)
    try:
        result = agent.chat(request.message, thread_id=request.thread_id)
    except RateLimitError as exc:
        # 429 rather than 500: the request was valid, the quota was not there.
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("chat failed")
        raise HTTPException(
            status_code=500, detail=f"{type(exc).__name__}: {exc}"
        ) from exc

    return ChatResponse(
        response=result.response,
        tools_used=list(result.tools_used),
        sources=list(result.sources),
        intent=result.intent,
        model=result.model,
    )


@app.post("/chat/reset")
def reset(user_id: str = config.DEFAULT_USER_ID, thread_id: str = "default") -> dict:
    """Forget one conversation thread."""
    get_agent(user_id).reset(thread_id)
    return {"status": "reset", "user_id": user_id, "thread_id": thread_id}
