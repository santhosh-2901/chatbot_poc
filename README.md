# AI Personal Finance Assistant

A conversational layer over synthetic personal-finance data. The agent decides,
per question, whether an answer comes from the user's transactions, from
deterministic Python analysis, from a retrieved knowledge base, or from a
combination — and explains the result in natural language.

Full specification: [chat_bot_techincal.md](chat_bot_techincal.md)

## Setup from scratch

Everything below assumes you have just received a copy of this project and
nothing else. **Python 3.10 or newer** is required; it was built and tested on
3.12.

### 1. Get the code

```bash
git clone https://github.com/<user>/<repo>.git
cd <repo>
```

Or unzip the folder and `cd` into it.

### 2. Create a virtual environment

A venv keeps this project's packages separate from the rest of your system, so
nothing here can break anything else you have installed.

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell refuses with an execution-policy error, either use
`.venv\Scripts\activate.bat` from cmd, or allow scripts for this session:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt should now start with `(.venv)`. That is how you know it worked.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

Takes a few minutes — faiss, langchain and streamlit are not small.

### 4. Get a free API key

Sign in at **https://aistudio.google.com/apikey** and create a key. It is free
and needs no card.

### 5. Point the project at your key

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Open `.env` and paste your key after `GOOGLE_API_KEY=`. The file is gitignored,
so it will never be committed.

Check it worked — this lists the models your key can actually reach:

```bash
python scripts/list_models.py
```

### 6. Run it

```bash
streamlit run frontend/streamlit_app.py
```

Open http://localhost:8501. That is the whole app in one process.

The data and the search index are both committed, so there is nothing to
generate. (If you ever change them: `python scripts/generate_data.py` and
`python scripts/build_index.py`.)

### Other ways to run it

**Two processes**, the architecture in spec section 19 — the frontend talks to
the API over HTTP:

```bash
python scripts/run_app.py          # starts both: API on :8010, UI on :8501
```

or by hand, in two terminals:

```bash
uvicorn app.api.main:app --reload --port 8010
API_URL=http://127.0.0.1:8010 streamlit run frontend/streamlit_app.py
```

**Terminal only**, no browser:

```bash
python scripts/chat.py                          # interactive
python scripts/chat.py "why did I spend more?"  # one-shot
```

**No LLM at all** — the analysis engine answering the MVP questions on its own:

```bash
python scripts/demo_analysis.py
```

### If something goes wrong

| Symptom | Cause and fix |
|---|---|
| `GOOGLE_API_KEY is not set` | No `.env`, or the key line is blank |
| `404 ... no longer available` | Dead model id. Run `python scripts/list_models.py` and put a working one in `GEMINI_CHAT_MODELS` |
| Waits ~30s then a quota error | Free-tier quota spent. It resets daily; the app falls through its model chain automatically |
| `address already in use` | Something else holds the port. `python scripts/run_app.py` respects `API_PORT` and `UI_PORT` |
| `ModuleNotFoundError` | The venv is not active — look for `(.venv)` in your prompt |
| Chart or page errors | Run `python -m pytest` — 185 tests, no API key needed |

## Deploying it free

Streamlit Community Cloud hosts this at no cost, with no card.

**1. Push to GitHub** (the repo is ~1 MB):

```bash
git add -A
git commit -m "AI Personal Finance Assistant"
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

**2. Create the app** at https://share.streamlit.io → *New app* → pick the repo
and branch, and set the main file to:

```
frontend/streamlit_app.py
```

**3. Add your key** under *Advanced settings → Secrets*:

```toml
GOOGLE_API_KEY = "your-key-here"
```

That's it. `.streamlit/secrets.toml.example` shows the full set of options.

### How one process works

Locally the app is two processes — Streamlit talking to FastAPI over HTTP.
Streamlit Cloud runs only one, so `frontend/client.py` provides a second client
that calls the very same FastAPI handler functions in-process instead. Selection
is automatic: `API_URL` set means HTTP, unset means direct. **Leave `API_URL`
unset when deploying.**

No backend logic is duplicated — both modes call the same functions, so they
cannot drift apart, and `tests/test_client.py` asserts they return the same data
and the same error statuses.

### Two things to know

**The FAISS index is committed on purpose.** `vectorstore/` is deliberately not
in `.gitignore`. At ~515 KB it costs nothing to commit, and without it a
deployed instance would rebuild the index on every cold start — spending
embedding quota and adding a minute before the first question can be answered.

**A public URL shares your quota.** Anyone who opens the link spends your free
tier, and it is small. For a project demo that is usually fine — the fallback
chain absorbs some of it — but don't post the link publicly.

### Other free options

| Platform | Notes |
|---|---|
| **Hugging Face Spaces** | Docker space can run both processes unchanged |
| **Render** | Free tier idles out; expect a ~50s cold start mid-demo |
| Railway, Fly.io | Trial credit only, not free ongoing |

## Stack

| Component | Choice |
|---|---|
| Agent | `langchain.agents.create_agent` (LangChain 1.x → LangGraph) |
| LLM | Gemini, with a four-model fallback chain |
| Embeddings | `gemini-embedding-001` |
| Vector store | FAISS, with a no-API keyword fallback |
| Backend | FastAPI |
| Frontend | Streamlit + Altair |
| Data | JSON + Markdown on disk |

The spec originally called for Ollama running local open models. We moved to
Gemini's free tier because tool-calling reliability is the load-bearing part of
this architecture and a hosted model is markedly better at it. The trade-off is
that the app is no longer fully local — acceptable here because all data is
synthetic.

## Phase status

All seven phases are complete.

| Phase | What |
|---|---|
| 1 | Synthetic data, schemas, loader |
| 2 | Deterministic analysis engine |
| 3 | RAG over the financial knowledge base |
| 4 | Gemini wiring and the fallback chain |
| 5 | Agent, tools, intent routing |
| 6 | `POST /chat` and the dashboard API |
| 7 | Streamlit dashboard and chat |

Phases 4 and 5 were pulled ahead of 3: tool routing was the riskiest assumption
in the design, so it was worth testing early rather than at the end.

## Tests

```bash
python -m pytest             # 174 offline tests, ~9s, no API calls
python -m pytest -m live     # 12 tests against the real model
```

The default run touches no network and costs no quota. The `live` tests cover
the one thing offline tests cannot: whether a question in English reaches the
function that answers it.

`tests/test_frontend.py` executes the real Streamlit page through `AppTest`, and
skips itself if the API is not running.

---

## Things worth knowing

### Free-tier quota is the real constraint

Quota is **per model, per day**, and it is small. `gemini-3.6-flash` allows
**20 requests a day** — about seven exchanges, since each costs at least two
calls.

Because the limit is per model, a chain of models on one key gives several
separate allowances. `app/config.py` defines four, tried in order, and
`FinanceAgent.chat` falls through on a quota error. Adding
`groq:llama-3.3-70b-versatile` to `GEMINI_CHAT_MODELS` brings in a genuinely
independent provider; entries whose provider is unconfigured are skipped rather
than failing the chain.

When quota does run out, the SDK retries silently with backoff, so a 429 looks
like a three-minute hang rather than an error. `app/agent/agent.py` translates
it into a `RateLimitError` naming the model and the wait.

### Verify model ids; don't trust documentation

```bash
python scripts/list_models.py
```

`gemini-2.5-flash` is still listed by the API but returns 404 for recently
created keys. `text-embedding-004`, the name most guides show, does not exist at
all.

### Retrieval is not left to the model

The flash-lite models answer "what is compound interest?" from memory instead of
calling the retrieval tool. The answer is usually correct but ungrounded — it
cannot be traced to the library, which makes the RAG pipeline decorative. Three
models behaved identically and prompt strengthening did not change it.

So intent detection happens first, in code — which is what spec section 20
specifies anyway. `app/agent/routing.py` classifies a message as `knowledge`,
`personal`, `mixed` or `unclear`, and retrieves passages before the model is
asked anything. The model still chooses every transaction tool; only the case
that was actually failing is pinned down.

It is keyword-based rather than a model call so it is free, instant, and
exhaustively testable offline — see `tests/test_routing.py`.

Because of this, `sources` and `tools_used` are reported separately everywhere:
the router retrieved the first, the model chose the second, and collapsing them
would misreport which part of the system made which decision.

### RAG degrades rather than failing

Embedding a query is a network request, and network requests fail. Behind FAISS
sits a TF-IDF keyword index built from `chunks.json`, needing no API at all. On
a corpus this small it finds the right document for every test question. The
tool reports `retrieval_method` so a degraded answer is visibly degraded.

### `langchain-text-splitters` is deliberately absent

Importing it executes an `__init__` that eagerly pulls in sentence-transformers,
torch, datasets and pyarrow. We use none of them, and on Windows the combination
segfaulted the interpreter alongside faiss, and added ~15s to every test run.
`app/rag/splitter.py` does the heading-then-size splitting we need in ~70 lines
and produces the same 40 chunks.

---

## Architecture

```
Streamlit ──HTTP──> FastAPI ──> intent detection ──> retrieve if conceptual
                                       │
                                       v
                              LangGraph ReAct loop
                                       │
              ┌────────────────────────┼────────────────────────┐
              v                        v                        v
      transaction tools         analysis tools            knowledge tool
      transactions.json         pure Python math          FAISS / keyword
              └────────────────────────┼────────────────────────┘
                                       v
                                Gemini (chain of 4)
```

### The analysis engine

`app/analysis/` is the source of truth for every figure the assistant states.
Nothing in it knows an LLM exists.

| Function | Answers |
|---|---|
| `summarize_month` | Where is my money going? |
| `analyze_category` | How much did I spend on food? |
| `compare_months` | Why did I spend more this month? |
| `budget_status` | Am I over budget? |
| `recommend_budget` | Help me plan next month |
| `affordability_check` | Can I afford this? |

Results are Pydantic models, deliberately verbose — shares, rankings, deltas and
counts are all precomputed. A field the model needs but cannot find is an
invitation to do mental arithmetic, which is what section 25 of the spec forbids.

**Budgets are built on the median, not the mean.** A mean-based budget is
dragged upward by exactly the bad month the user wants to correct, and it hands
fixed costs like rent headroom they cannot use.

**Affordability verdicts are decided in code, including the reasons.** The
`reasons` list is generated by Python; the model turns those statements into
prose. It does not get to decide whether something is affordable.

### API

| Endpoint | Purpose |
|---|---|
| `GET /health` | Status and the configured model chain |
| `GET /users` | Available users |
| `GET /dashboard/{user_id}` | Everything one screen needs, in one request |
| `POST /chat` | `{response, tools_used, sources, intent, model}` |
| `POST /chat/reset` | Forget a conversation thread |

Agents are cached per user so conversation memory survives between turns.

## The dataset

Two users, six months (2026-03 to 2026-08), 510 transactions. `USER001` is the
demo subject; `USER002` exists so multi-user filtering and irregular income are
actually exercised.

| Month | Income | Expenses | Net |
|---|---:|---:|---:|
| 2026-03 | 60,000 | 34,300 | 25,700 |
| 2026-04 | 60,000 | 36,800 | 23,200 |
| 2026-05 | 60,000 | 35,200 | 24,800 |
| 2026-06 | 60,000 | 38,200 | 21,800 |
| 2026-07 | 60,000 | 36,100 | 23,900 |
| 2026-08 | 60,000 | **42,500** | 17,500 |

August is deliberately the outlier: +6,400 (+17.7%) over July, driven by
Shopping (+3,200) and Food (+1,800). Those are the exact figures the spec quotes,
and `tests/test_data.py` fails if they ever move — so the demo script and the
data cannot silently drift apart.

Other properties the data was built to support:

- July stays inside budget, August breaches Food and Shopping — a clean
  before/after for the comparison question.
- `USER001`'s emergency fund covers ~1.5 months of expenses against a 6-month
  guideline, giving the combined RAG + transaction demo something real to say.
- Two known upcoming expenses so the affordability check has obligations to weigh.

## Layout

```
app/
  models/       schemas.py (data contracts) · analysis.py (result contracts)
  services/     data_loader.py (only reader of data/*.json) · transaction_service.py
  analysis/     summary · comparison · budget · affordability · utils
  rag/          ingestion · splitter · retriever (FAISS + keyword fallback)
  tools/        finance_tools.py · knowledge_tool.py
  agent/        agent.py · prompts.py · routing.py (intent detection)
  api/          main.py (FastAPI)
  config.py     env, model chain, verified defaults
  llm.py        the only module that imports a provider SDK
data/           users · transactions · budgets · financial_knowledge/*.md
vectorstore/    faiss_index/ · chunks.json
frontend/       streamlit_app.py
scripts/        generate_data · build_index · chat · demo_analysis · list_models · run_app
tests/          data · analysis · tools · rag · routing · api · frontend · agent_live
```

## Design rules

**Python owns arithmetic.** The LLM explains numbers; it never produces them.
Every figure in a response traces to a tool return value (spec section 25).

**Money is `int`.** Whole rupees. Floats would quietly break the exact-total
guarantees the tests rely on.

**Categories are a closed set.** An unexpected category fails at load rather
than reaching the model as something to invent an explanation for.

**Tools are bound to one user.** `build_finance_tools(user_id)` closes over the
id rather than exposing it as an argument. A model that can pass an arbitrary
`user_id` can read someone else's finances by hallucinating one, and no prompt
reliably prevents that.

**Tool failures return, they don't raise.** An invalid month comes back as an
`error` dict naming the valid months, so the model corrects itself on the next
turn instead of the conversation dying on a stack trace.

**Not financial advice.** Responses are informational analysis of synthetic
data (spec section 26).
