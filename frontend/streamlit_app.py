"""Streamlit frontend (spec section 29, Phase 7).

The chatbot is the product; the dashboard exists to give it context (spec
section 3). The layout reflects that — chat takes the wider column and the
charts sit beside it.

All data comes from the backend, matching the architecture in spec section 19.
The frontend holds no business logic: it renders what the backend returns and
sends messages back. That separation is why the golden numbers cannot drift
between the two.

It reaches that backend one of two ways, chosen by whether ``API_URL`` is set —
over HTTP against a running server, or by calling the same handlers in-process.
See ``frontend/client.py``. The second mode is what makes a single-process host
like Streamlit Community Cloud possible without duplicating any logic.

Locally, two processes:

    uvicorn app.api.main:app --reload --port 8010
    API_URL=http://127.0.0.1:8010 streamlit run frontend/streamlit_app.py

Or one:

    streamlit run frontend/streamlit_app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

# The repo root must be importable before anything under `app` or `frontend` is
# imported: Streamlit puts the script's own directory on sys.path, not the root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_secrets() -> None:
    """Copy Streamlit secrets into the environment.

    Must run before `app.config` is imported, since that reads the environment
    at import time. On Streamlit Cloud the key lives in the app's secrets rather
    than in a .env file, which is never committed.
    """
    for key in ("GOOGLE_API_KEY", "GEMINI_CHAT_MODELS", "GEMINI_CHAT_MODEL",
                "GEMINI_EMBEDDING_MODEL", "GROQ_API_KEY", "API_URL"):
        if os.environ.get(key):
            continue
        try:
            if key in st.secrets:
                os.environ[key] = str(st.secrets[key])
        except Exception:
            # No secrets file at all — normal when running locally from .env.
            return


load_secrets()

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402

from frontend.client import ClientError, get_client  # noqa: E402

# Palette from the data-viz reference instance, validated for light surface
# #fcfcfb: categorical slots 1 and 2, plus reserved status colours. Status is
# never reused as a series colour.
BLUE = "#2a78d6"
ORANGE = "#eb6834"
CRITICAL = "#d03b3b"
GOOD = "#0ca30c"
INK = "#0b0b0b"
INK_MUTED = "#52514e"
GRID = "#e6e5e1"
SURFACE = "#fcfcfb"

st.set_page_config(
    page_title="AI Personal Finance Assistant",
    page_icon="₹",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
    <style>
      .stApp {{ background: {SURFACE}; }}
      .kpi {{
        background: #ffffff;
        border: 1px solid {GRID};
        border-radius: 10px;
        padding: 14px 16px;
        height: 100%;
      }}
      .kpi-label {{
        font-size: 0.75rem; text-transform: uppercase; letter-spacing: .06em;
        color: {INK_MUTED}; margin-bottom: 6px;
      }}
      .kpi-value {{ font-size: 1.6rem; font-weight: 600; color: {INK}; line-height: 1.1; }}
      .kpi-delta {{ font-size: 0.8rem; color: {INK_MUTED}; margin-top: 4px; }}
      .trace {{
        font-size: 0.75rem; color: {INK_MUTED};
        border-left: 2px solid {GRID}; padding-left: 8px; margin-top: 6px;
      }}
      .disclaimer {{ font-size: 0.75rem; color: {INK_MUTED}; margin-top: 12px; }}
      div[data-testid="stMetricValue"] {{ font-size: 1.5rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

@st.cache_resource
def backend():
    """One client for the session.

    ``cache_resource``, not ``cache_data``: in direct mode this object owns the
    agent, and the agent owns the conversation memory. Rebuilding it on every
    Streamlit rerun would reset the conversation after each message.
    """
    return get_client()


@st.cache_data(ttl=60)
def fetch_users() -> list[dict]:
    return backend().users()


@st.cache_data(ttl=60)
def fetch_dashboard(user_id: str, month: str | None) -> dict:
    return backend().dashboard(user_id, month)


@st.cache_data(ttl=60)
def fetch_trend(user_id: str, months: tuple[str, ...]) -> pd.DataFrame:
    """Income and expenses per month, for the trend chart."""
    rows = []
    for month in months:
        data = fetch_dashboard(user_id, month)
        rows.append({"month": month, "series": "Income", "amount": data["income"]})
        rows.append({"month": month, "series": "Expenses", "amount": data["expenses"]})
    return pd.DataFrame(rows)


def rupees(amount: float) -> str:
    return f"₹{amount:,.0f}"


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def category_chart(categories: list[dict]) -> alt.Chart:
    """Spending by category — magnitude, so one hue, ranked high to low.

    Over-budget categories take the reserved 'critical' status colour rather
    than a second series hue, and are also marked in the tooltip and the
    legend: status is never carried by colour alone.
    """
    frame = pd.DataFrame(categories)
    frame["state"] = frame["over_budget"].map(
        {True: "Over budget", False: "Within budget"}
    )
    frame["label"] = frame["amount"].map(rupees)

    base = alt.Chart(frame).encode(
        y=alt.Y("category:N", sort="-x", title=None,
                axis=alt.Axis(labelColor=INK, labelFontSize=12, domain=False, ticks=False)),
        x=alt.X("amount:Q", title=None,
                axis=alt.Axis(grid=True, gridColor=GRID, labelColor=INK_MUTED,
                              format=",.0f", tickCount=4, domain=False)),
    )

    bars = base.mark_bar(height=16, cornerRadiusEnd=4).encode(
        color=alt.Color(
            "state:N",
            scale=alt.Scale(
                domain=["Within budget", "Over budget"], range=[BLUE, CRITICAL]
            ),
            legend=alt.Legend(title=None, orient="top", labelColor=INK_MUTED),
        ),
        tooltip=[
            alt.Tooltip("category:N", title="Category"),
            alt.Tooltip("amount:Q", title="Spent", format=",.0f"),
            alt.Tooltip("budgeted:Q", title="Budget", format=",.0f"),
            alt.Tooltip("share_of_expenses:Q", title="Share %", format=".1f"),
            alt.Tooltip("state:N", title="Status"),
        ],
    )

    # Direct labels: the reader should not have to trace a bar back to an axis.
    labels = base.mark_text(
        align="left", dx=6, color=INK_MUTED, fontSize=11
    ).encode(text="label:N")

    return (bars + labels).properties(height=max(200, 34 * len(frame)))


def trend_chart(frame: pd.DataFrame) -> alt.Chart:
    """Income against expenses over time — two distinct series, so categorical."""
    base = alt.Chart(frame).encode(
        x=alt.X("month:N", title=None,
                axis=alt.Axis(labelColor=INK_MUTED, domain=False, ticks=False, labelAngle=0)),
        y=alt.Y("amount:Q", title=None,
                axis=alt.Axis(grid=True, gridColor=GRID, labelColor=INK_MUTED,
                              format=",.0f", tickCount=4, domain=False)),
        color=alt.Color(
            "series:N",
            scale=alt.Scale(domain=["Income", "Expenses"], range=[BLUE, ORANGE]),
            legend=alt.Legend(title=None, orient="top", labelColor=INK_MUTED),
        ),
    )
    line = base.mark_line(strokeWidth=2)
    points = base.mark_point(size=80, filled=True, stroke=SURFACE, strokeWidth=2).encode(
        tooltip=[
            alt.Tooltip("month:N", title="Month"),
            alt.Tooltip("series:N", title=None),
            alt.Tooltip("amount:Q", title="Amount", format=",.0f"),
        ]
    )
    return (line + points).properties(height=240)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def kpi(column, label: str, value: str, delta: str = "") -> None:
    column.markdown(
        f'<div class="kpi"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-delta">{delta}&nbsp;</div></div>',
        unsafe_allow_html=True,
    )


EXAMPLES = [
    "Where am I spending the most money?",
    "Why did I spend more this month?",
    "Can I afford a 40,000 phone?",
    "What is an emergency fund?",
    "How does my spending compare with the 50/30/20 rule?",
    "How can I reduce my spending?",
]


def main() -> None:
    try:
        users = fetch_users()
    except ClientError as exc:
        st.error(f"Backend unavailable: {exc.detail}")
        if backend().mode == "http":
            st.info(
                "Start the API with:\n\n"
                "```\nuvicorn app.api.main:app --reload --port 8010\n```\n\n"
                "Or unset `API_URL` to run everything in this process."
            )
        st.stop()

    # ---- sidebar -----------------------------------------------------------
    with st.sidebar:
        st.subheader("Account")
        labels = {u["user_id"]: f"{u['name']} ({u['user_id']})" for u in users}
        user_id = st.selectbox(
            "User", list(labels), format_func=labels.get, label_visibility="collapsed"
        )

        data = fetch_dashboard(user_id, None)
        months = data["available_months"]
        month = st.selectbox("Month", months[::-1], index=0)
        if month != data["month"]:
            data = fetch_dashboard(user_id, month)

        st.divider()
        st.caption("Try asking")
        for example in EXAMPLES:
            if st.button(example, width="stretch", key=f"ex-{example}"):
                st.session_state.pending = example

        st.divider()
        if st.button("Clear conversation", width="stretch"):
            try:
                backend().reset(user_id)
            except ClientError:
                pass  # nothing to forget yet
            st.session_state.messages = []
            st.rerun()

    st.title("AI Personal Finance Assistant")
    st.caption(f"{data['name']} · {data['month']} · synthetic data")

    # ---- KPI row -----------------------------------------------------------
    columns = st.columns(4)
    kpi(columns[0], "Income", rupees(data["income"]))

    change = data["expense_change"]
    delta = ""
    if change is not None:
        direction = "up" if change > 0 else "down"
        delta = f"{direction} {rupees(abs(change))} vs {data['previous_month']}"
    kpi(columns[1], "Expenses", rupees(data["expenses"]), delta)

    kpi(columns[2], "Net", rupees(data["net"]), f"{data['savings_rate']:.1f}% saved")
    kpi(columns[3], "Savings balance", rupees(data["savings_balance"]))

    if data["breached_categories"]:
        st.warning(
            "Over budget in " + ", ".join(data["breached_categories"]),
            icon="⚠️",
        )

    st.write("")
    left, right = st.columns([5, 6], gap="large")

    # ---- dashboard ---------------------------------------------------------
    with left:
        st.subheader("Spending by category")
        st.altair_chart(category_chart(data["categories"]), width="stretch")

        st.subheader("Income and expenses")
        st.altair_chart(
            trend_chart(fetch_trend(user_id, tuple(months))), width="stretch"
        )

        with st.expander("Recent transactions"):
            st.dataframe(
                pd.DataFrame(data["recent_transactions"]),
                width="stretch",
                hide_index=True,
            )

    # ---- chat --------------------------------------------------------------
    with right:
        st.subheader("Ask about your money")

        if "messages" not in st.session_state:
            st.session_state.messages = []

        for entry in st.session_state.messages:
            with st.chat_message(entry["role"]):
                st.markdown(entry["content"])
                if entry.get("trace"):
                    st.markdown(
                        f'<div class="trace">{entry["trace"]}</div>',
                        unsafe_allow_html=True,
                    )

        question = st.chat_input("e.g. why did I spend more this month?")
        if st.session_state.get("pending"):
            question = st.session_state.pop("pending")

        if question:
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                payload = None
                try:
                    with st.spinner("Thinking..."):
                        payload = backend().chat(user_id, question)
                except ClientError as exc:
                    # 429 is the one worth distinguishing: the request was fine,
                    # the free-tier quota was not there.
                    icon = "⏳" if exc.status == 429 else "⚠️"
                    st.error(exc.detail, icon=icon)

                if payload is not None:
                    st.markdown(payload["response"])

                    # Provenance, kept honest: sources were retrieved by the
                    # router, tools were chosen by the model. Shown separately.
                    parts = [f"intent: {payload['intent']}"]
                    if payload["sources"]:
                        parts.append("sources: " + ", ".join(payload["sources"]))
                    if payload["tools_used"]:
                        parts.append("tools: " + ", ".join(payload["tools_used"]))
                    parts.append(f"model: {payload['model']}")
                    trace = " &nbsp;·&nbsp; ".join(parts)

                    st.markdown(f'<div class="trace">{trace}</div>', unsafe_allow_html=True)
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": payload["response"],
                            "trace": trace,
                        }
                    )

        st.markdown(
            '<div class="disclaimer">Informational analysis of synthetic data. '
            "Not professional financial advice.</div>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
