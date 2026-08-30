# AI Personal Finance Assistant

## End-to-End Technical Specification

**Project Type:** GenAI / RAG / Agentic Chatbot POC
**Domain:** FinTech / Personal Finance
**Primary Focus:** AI Finance Chatbot
**Deployment Goal:** Local / Free / No paid APIs
**Data Strategy:** Synthetic JSON data + local financial knowledge base

---

# 1. Project Overview

## 1.1 Problem Statement

People can see their transactions in banking or expense-management applications, but simply displaying transactions does not answer the questions users actually have:

* Where am I spending most of my money?
* Why did my spending increase?
* Which categories are consuming my income?
* Where can I reduce my expenses?
* Can I afford a particular purchase?
* How should I create a budget?
* What is an emergency fund?
* What does a financial term mean?
* How can I improve my monthly spending?

The goal of this project is to build an **AI Personal Finance Assistant** that allows users to interact with their financial data through natural language.

The chatbot combines:

1. User transaction data
2. Financial calculations and analysis
3. A curated financial knowledge base
4. Retrieval-Augmented Generation (RAG)
5. An LLM
6. Simple deterministic tools

The primary interface is the **chatbot**.

---

# 2. Product Vision

The application should feel like:

> **"An AI assistant that understands my spending and helps me make better financial decisions."**

It is NOT intended to be:

* A banking application
* A payment application
* An investment trading platform
* A financial advisor
* A real banking integration
* A system handling real customer financial accounts

This is a **FinTech GenAI demonstration / POC** using synthetic data.

---

# 3. Core User Experience

The website will have a minimal frontend.

## Main Screens

```text
┌──────────────────────────────────────────────┐
│        AI PERSONAL FINANCE ASSISTANT         │
├──────────────────────────────────────────────┤
│                                              │
│  Dashboard                                   │
│  ├── Monthly Income                          │
│  ├── Monthly Expenses                        │
│  ├── Top Spending Categories                 │
│  └── Recent Transactions                     │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │         AI FINANCE CHATBOT             │  │
│  │                                        │  │
│  │ User: Why did I overspend this month? │  │
│  │                                        │  │
│  │ AI: Your spending increased mainly    │  │
│  │ because of shopping and food...       │  │
│  │                                        │  │
│  └────────────────────────────────────────┘  │
│                                              │
└──────────────────────────────────────────────┘
```

The dashboard exists mainly to provide context.

**The chatbot is the main feature.**

---

# 4. Main Capabilities

The chatbot should support the following capabilities.

## 4.1 Transaction Understanding

The chatbot can analyze synthetic transaction data.

Example:

> "Where am I spending my money?"

The system calculates:

```text
Food          ₹8,500
Shopping      ₹7,200
Transport     ₹4,100
Subscriptions ₹2,300
Utilities     ₹6,000
Other         ₹5,900
```

---

## 4.2 Spending Analysis

Example:

> "Why did I spend more this month?"

The system compares:

```text
Current Month
        ↓
Previous Month
        ↓
Category Comparison
        ↓
Identify Significant Changes
        ↓
LLM Explanation
```

Example response:

> Your spending increased by ₹6,400 compared with last month. The largest increase came from shopping (+₹3,200), followed by food (+₹1,800).

The numerical calculation should be performed by code, not invented by the LLM.

---

# 5. Financial Decision Assistance

This is the key feature that differentiates the application from a simple expense tracker.

## Example

User:

> "Can I afford a ₹40,000 phone?"

The system retrieves:

```text
Monthly income
Monthly expenses
Current savings
Existing budget
Financial goals
Upcoming expenses
```

Then calculates an affordability assessment.

The LLM explains the result conversationally.

Example:

> Based on your current monthly cash flow, a ₹40,000 purchase would consume a significant portion of your available discretionary funds. You may want to postpone the purchase or allocate it across a planned savings goal.

The system should avoid presenting this as professional financial advice.

---

# 6. Budget Assistance

User:

> "Help me create a budget for next month."

The agent can analyze historical spending.

```text
Transaction Data
       ↓
Category Analysis
       ↓
Average Monthly Spending
       ↓
Identify Essential vs Discretionary
       ↓
Budget Recommendation
       ↓
LLM Explanation
```

Example:

```text
Income             ₹60,000

Recommended Budget

Housing            ₹15,000
Food                ₹7,000
Transport           ₹4,000
Utilities           ₹5,000
Shopping            ₹4,000
Subscriptions       ₹1,500
Savings             ₹10,000
Other               ₹3,500
```

---

# 7. Financial Knowledge Using RAG

RAG is used for **general financial knowledge**, not for transaction calculations.

Examples:

> "What is the 50/30/20 budgeting rule?"

> "What is an emergency fund?"

> "What is compound interest?"

> "What is the difference between a secured and unsecured loan?"

> "What does credit utilization mean?"

The knowledge base contains curated financial documents.

LangChain describes RAG as retrieving relevant external knowledge at query time and supplying that context to the LLM.

---

# 8. Combining User Data + RAG

This is one of the most important parts of the project.

The chatbot can combine:

```text
             USER QUESTION
                    │
                    ▼
               AI AGENT
              /         \
             /           \
            ▼             ▼
   Transaction Tools      RAG
            │              │
            ▼              ▼
     User Financial     Financial
          Data          Knowledge
            │              │
            └──────┬───────┘
                   ▼
              LLM RESPONSE
```

Example:

> "Based on my spending, how should I apply the 50/30/20 rule?"

The system uses:

**Transaction data**
→ user's actual spending

**RAG**
→ explanation of 50/30/20 framework

**Code**
→ calculate current percentages

**LLM**
→ explain the result naturally

This gives RAG a clear purpose.

---

# 9. Agent Responsibilities

The chatbot should not perform everything through free-form LLM reasoning.

Instead, the LLM acts as an **orchestrator**.

Possible tools:

```text
1. get_transactions()
2. calculate_monthly_summary()
3. compare_months()
4. analyze_category_spending()
5. calculate_budget()
6. affordability_check()
7. retrieve_financial_knowledge()
```

The agent decides which capability is required.

---

# 10. Tool Definitions

## Tool 1 — get_transactions

Purpose:

Retrieve transactions from local JSON data.

Input:

```json
{
  "month": "2026-08"
}
```

Output:

```json
{
  "transactions": [...]
}
```

---

## Tool 2 — calculate_monthly_summary

Purpose:

Calculate:

* Total income
* Total expenses
* Net cash flow
* Category totals

Example output:

```json
{
  "income": 60000,
  "expenses": 42500,
  "net": 17500
}
```

---

## Tool 3 — compare_months

Purpose:

Compare two months.

Example:

```json
{
  "current_month": "2026-08",
  "previous_month": "2026-07"
}
```

Output:

```json
{
  "expense_change": 6400,
  "percentage_change": 17.7,
  "largest_increase": {
    "category": "Shopping",
    "amount": 3200
  }
}
```

---

## Tool 4 — analyze_category_spending

Example:

> "How much did I spend on food?"

The tool returns the exact value.

---

## Tool 5 — affordability_check

Input:

```json
{
  "purchase_amount": 40000
}
```

The tool considers:

```text
Income
Expenses
Available cash flow
Savings
Budget
Upcoming obligations
```

Output:

```json
{
  "purchase_amount": 40000,
  "available_discretionary_amount": 17500,
  "status": "CAUTION"
}
```

The LLM then explains the result.

---

## Tool 6 — financial_knowledge_search

This invokes the RAG pipeline.

Example:

```text
User Question
     ↓
Embedding
     ↓
Vector Search
     ↓
Relevant Financial Documents
     ↓
LLM
```

---

# 11. Data Architecture

For the first version, **do not use a production database**.

Use local files.

```text
data/
│
├── users.json
│
├── transactions.json
│
├── budgets.json
│
└── financial_knowledge/
    ├── budgeting.md
    ├── saving.md
    ├── emergency_fund.md
    ├── credit.md
    ├── loans.md
    └── investing_basics.md
```

This keeps the project:

* Free
* Easy to understand
* Easy to test
* Easy to demonstrate
* Easy to deploy locally

---

# 12. Transaction Data

Example:

```json
{
  "transaction_id": "TXN001",
  "user_id": "USER001",
  "date": "2026-08-01",
  "merchant": "Amazon",
  "category": "Shopping",
  "type": "expense",
  "amount": 2500,
  "currency": "INR"
}
```

Example income:

```json
{
  "transaction_id": "TXN010",
  "user_id": "USER001",
  "date": "2026-08-01",
  "merchant": "Salary",
  "category": "Income",
  "type": "income",
  "amount": 60000,
  "currency": "INR"
}
```

---

# 13. Why JSON Instead of Database?

For the POC:

```text
JSON
 ↓
Python
 ↓
Financial calculation tools
 ↓
Agent
```

A database would add infrastructure without providing significant value at this stage.

Later, JSON can be replaced with:

```text
SQLite
   ↓
PostgreSQL
   ↓
Production financial database
```

The tool interfaces remain largely the same.

---

# 14. RAG Architecture

The RAG pipeline will use local financial knowledge.

```text
Financial Documents
        │
        ▼
Document Loader
        │
        ▼
Text Splitter
        │
        ▼
Embedding Model
        │
        ▼
Vector Store
        │
        ▼
Retriever
        │
        ▼
Relevant Context
        │
        ▼
LLM
        │
        ▼
Answer
```

LangChain's current retrieval architecture supports document loaders, text splitters, embeddings, vector stores and retrievers as modular components.

---

# 15. Vector Store

For the POC, use:

**FAISS**

Reason:

* Local
* Free
* No server required
* Easy to reproduce
* Good enough for a small knowledge base

No managed vector database is required.

---

# 16. Embeddings

Use the Gemini embedding model through `langchain-google-genai`.

Candidate:

```text
Embedding Model:
text-embedding-004
```

The same free API key covers chat and embeddings, so the RAG pipeline needs no
local model server at all.

The exact model can be changed without changing the overall architecture.

---

# 17. LLM

Use **Gemini** through the free Google AI Studio tier.

Candidate:

```text
LLM:
gemini-2.5-flash
```

Reason: tool selection is the load-bearing step in this architecture (section
37). A large hosted model follows tool schemas far more reliably than a small
local one, and unreliable tool routing would undermine the whole design.

LangChain provides a dedicated integration through `langchain-google-genai`.

Therefore:

```text
Application
     ↓
LangChain
     ↓
langchain-google-genai
     ↓
Gemini
```

A free API key is required. No paid API and no OpenAI key is used.

The model is reached through a small factory function, so switching to a local
Ollama model later is a configuration change rather than a rewrite.

---

# 18. Proposed Technology Stack

## Frontend

```text
Streamlit
```

Reason:

The frontend is intentionally low priority.

We want to spend most of the effort on the chatbot and backend.

---

## Backend

```text
Python
FastAPI
```

FastAPI exposes the chatbot backend and financial tools.

---

## Agent Framework

```text
LangChain
```

LangChain will handle:

* LLM integration
* Prompting
* Tool definitions
* Retrieval
* Agent orchestration

---

## LLM Runtime

```text
Google AI Studio (Gemini API, free tier)
```

---

## LLM

Initial candidate:

```text
gemini-2.5-flash
```

---

## Embeddings

```text
Gemini Embeddings
```

---

## Vector Store

```text
FAISS
```

---

## Data

```text
JSON
Markdown
```

---

# 19. High-Level Architecture

```text
                         ┌─────────────────────┐
                         │      USER           │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │     STREAMLIT       │
                         │       CHAT UI       │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │       FASTAPI       │
                         │      BACKEND        │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   LANGCHAIN AGENT   │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────┼────────────────────┐
              │                     │                    │
              ▼                     ▼                    ▼
      ┌──────────────┐      ┌──────────────┐     ┌──────────────┐
      │ Transaction  │      │ Financial    │     │     RAG      │
      │    Tools     │      │ Calculation  │     │   Retriever  │
      └──────┬───────┘      └──────┬───────┘     └──────┬───────┘
             │                     │                    │
             ▼                     ▼                    ▼
      transactions.json       Python Logic        FAISS Index
                                                       │
                                                       ▼
                                               Financial Documents
                                                       │
                                                       ▼
                                                   Embeddings
                                                       │
                                                       ▼
                                                Gemini Embeddings

                                    │
                                    ▼
                              ┌──────────────┐
                              │    Gemini    │
                              │     LLM      │
                              └──────┬───────┘
                                     │
                                     ▼
                              Final Response
```

---

# 20. Chatbot Decision Flow

When a user sends a message:

```text
                   USER MESSAGE
                        │
                        ▼
                 Intent Detection
                        │
          ┌─────────────┼─────────────┐
          │             │             │
          ▼             ▼             ▼
    Transaction      Financial      General
      Query          Analysis      Knowledge
          │             │             │
          ▼             ▼             ▼
     Tool Call       Tool Calls       RAG
          │             │             │
          └─────────────┼─────────────┘
                        ▼
                       LLM
                        │
                        ▼
                  Final Answer
```

---

# 21. Example Conversation 1

### User

> Where am I spending the most money?

### Agent

Calls:

```text
analyze_category_spending()
```

### Tool

Returns:

```text
Housing: ₹15,000
Food: ₹8,500
Shopping: ₹7,200
Transport: ₹4,100
Utilities: ₹6,000
```

### LLM

Responds:

> Housing is your largest expense at ₹15,000, followed by food at ₹8,500 and shopping at ₹7,200.

---

# 22. Example Conversation 2

### User

> Why did I spend more this month?

Agent:

```text
compare_months()
        ↓
category analysis
        ↓
LLM explanation
```

Response:

> Your expenses increased by ₹6,400 compared with July. Shopping contributed the largest increase, followed by food.

---

# 23. Example Conversation 3

### User

> What is an emergency fund?

Agent:

```text
financial_knowledge_search()
        ↓
FAISS
        ↓
Relevant document
        ↓
LLM
```

Response:

> An emergency fund is money set aside to cover unexpected expenses such as medical costs, urgent repairs, or temporary loss of income.

---

# 24. Example Conversation 4 — Combined RAG + User Data

### User

> How does my spending compare with the 50/30/20 rule?

System:

```text
                    USER QUESTION
                         │
                         ▼
                     AI AGENT
                    /         \
                   /           \
                  ▼             ▼
        Transaction Tool        RAG
                  │              │
                  ▼              ▼
          Actual spending    50/30/20
                              knowledge
                  │              │
                  └──────┬───────┘
                         ▼
                       LLM
                         │
                         ▼
                    Explanation
```

This is one of the strongest demonstrations of the system.

---

# 25. Financial Calculations Must Not Be Done by the LLM

This is an important architectural rule.

Do NOT ask the LLM:

> "Calculate my total expenses."

Instead:

```text
JSON
 ↓
Python calculation
 ↓
Exact result
 ↓
LLM explanation
```

For example:

```python
total_expenses = sum(
    transaction["amount"]
    for transaction in transactions
    if transaction["type"] == "expense"
)
```

The LLM explains the result but does not become the source of truth for arithmetic.

---

# 26. Guardrails

Because this is a financial application, the chatbot should not behave like a licensed financial advisor.

The system should clearly distinguish:

### Allowed

```text
Financial education
Budget analysis
Spending analysis
Historical transaction analysis
General financial concepts
Budget suggestions
Affordability calculations
```

### Avoid

```text
Guaranteed investment returns
Personalized securities trading recommendations
Guaranteed financial outcomes
High-risk investment instructions
Claims of professional financial advice
```

Example:

> "Based on the transaction data provided, this purchase appears to place pressure on your monthly discretionary budget. This is an informational assessment, not professional financial advice."

---

# 27. Data Privacy for POC

All data is synthetic.

```text
NO:
- Real bank accounts
- Real credit cards
- Real customer information
- Bank APIs
- Payment APIs
- Financial institution credentials
```

All user data lives locally in JSON files. There is no bank, payment or
credential integration of any kind.

Model inference is the one exception: prompts are sent to the Gemini API. Free
tier usage may be used by the provider for product improvement, so this is not a
private-by-default deployment. That is acceptable here precisely because the
data is synthetic — no real person's finances are ever transmitted.

If a fully local deployment is needed later, the LLM factory can point at a
local Ollama model without any other change.

---

# 28. Project Directory Structure

```text
ai-finance-assistant/
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   └── chat.py
│   │
│   ├── agent/
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   └── state.py
│   │
│   ├── tools/
│   │   ├── transaction_tools.py
│   │   ├── analysis_tools.py
│   │   ├── budget_tools.py
│   │   └── knowledge_tool.py
│   │
│   ├── rag/
│   │   ├── ingestion.py
│   │   ├── retriever.py
│   │   └── vectorstore.py
│   │
│   ├── models/
│   │   └── schemas.py
│   │
│   └── services/
│       └── transaction_service.py
│
├── data/
│   ├── users.json
│   ├── transactions.json
│   ├── budgets.json
│   │
│   └── financial_knowledge/
│       ├── budgeting.md
│       ├── emergency_fund.md
│       ├── credit.md
│       ├── loans.md
│       └── investing_basics.md
│
├── vectorstore/
│   └── faiss_index/
│
├── frontend/
│   └── streamlit_app.py
│
├── tests/
│   ├── test_transactions.py
│   ├── test_tools.py
│   ├── test_rag.py
│   └── test_chatbot.py
│
├── requirements.txt
├── .env.example
└── README.md
```

---

# 29. Development Phases

## Phase 1 — Synthetic Data

Create:

```text
users.json
transactions.json
budgets.json
```

Generate realistic transaction history for several months.

---

## Phase 2 — Financial Analysis Engine

Implement deterministic functions:

```text
get_transactions()
calculate_total_income()
calculate_total_expenses()
calculate_category_spending()
compare_months()
calculate_cash_flow()
affordability_check()
```

Test these independently.

---

## Phase 3 — RAG

Create financial knowledge documents.

Note on splitting: langchain-text-splitters eagerly imports sentence-transformers,
torch, datasets and pyarrow. None are needed, and on Windows the combination
crashes the interpreter alongside faiss. app/rag/splitter.py replaces it.

Note on resilience: a query embedding is a network call, so the retriever falls
back to a local TF-IDF keyword index built at ingestion time. Retrieval degrades
rather than failing.

Build:

```text
Documents
 ↓
Chunking
 ↓
Embeddings
 ↓
FAISS
 ↓
Retriever
```

Test questions such as:

```text
What is an emergency fund?
What is 50/30/20?
What is compound interest?
What is credit utilization?
```

---

## Phase 4 — LLM

Get a free API key from Google AI Studio and set `GOOGLE_API_KEY`.

Connect:

```text
LangChain
    ↓
ChatGoogleGenerativeAI
    ↓
Gemini API
```

Wrap this in a `get_llm()` factory rather than constructing the model inline, so
the provider stays swappable.

Verify tool calling works end to end before building the agent on top of it.

---

## Phase 5 — Agent

Intent detection (section 20) runs first, in code. The available models answer
concept questions from memory rather than calling the retrieval tool, which
produces plausible but ungrounded answers; detecting a concept question and
retrieving before the model is asked removes the choice. The model still selects
every transaction tool itself.

Create the finance agent with tools:

```text
transaction tools
analysis tools
budget tools
RAG tool
```

The agent chooses the appropriate tool based on the user question.

---

## Phase 6 — Chatbot API

Create:

```text
POST /chat
```

Input:

```json
{
  "user_id": "USER001",
  "message": "Why did I overspend this month?"
}
```

Output:

```json
{
  "response": "Your spending increased mainly because...",
  "tools_used": [
    "compare_months"
  ]
}
```

---

## Phase 7 — Minimal Frontend

Create only what is necessary:

```text
Dashboard
    +
Chat interface
```

Do NOT spend significant time on:

* Complex animations
* Authentication
* Payment UI
* Mobile responsiveness
* Fancy dashboards

The **chatbot is the product focus**.

---

# 30. Testing Strategy

Test three categories.

## A. Deterministic Tests

```text
Total expense calculation
Category totals
Monthly comparison
Budget calculation
Affordability calculation
```

These must produce exact results.

---

## B. RAG Tests

Questions should retrieve the correct document.

Example:

```text
Question:
"What is an emergency fund?"

Expected:
emergency_fund.md
```

---

## C. Agent Tests

Example:

```text
"What did I spend on food?"
        ↓
analyze_category_spending()

"What is compound interest?"
        ↓
RAG

"Why did I spend more this month?"
        ↓
compare_months()

"Can I afford a ₹40,000 phone?"
        ↓
affordability_check()
```

---

# 31. Important Architectural Principle

The project should follow:

> **LLM for language and reasoning.
> Python tools for deterministic calculations.
> RAG for external financial knowledge.
> JSON for synthetic user data.**

This separation makes the system easier to test and reduces hallucinations.

---

# 32. What We Are NOT Building

To keep the scope controlled, Version 1 will NOT include:

```text
❌ Real bank integration
❌ Real payment processing
❌ Investment trading
❌ Stock recommendations
❌ Credit score integration
❌ Paid APIs
❌ OpenAI API
❌ Cloud database
❌ Production authentication
❌ Complex frontend
```

---

# 33. MVP Scope

The minimum working product should support these five questions:

### 1.

> "Where am I spending the most?"

→ Transaction analysis

### 2.

> "Why did I spend more this month?"

→ Month comparison

### 3.

> "Can I afford a ₹40,000 purchase?"

→ Affordability tool

### 4.

> "What is the 50/30/20 rule?"

→ RAG

### 5.

> "How can I reduce my spending based on my transactions?"

→ Transaction analysis + LLM reasoning + financial knowledge

If these five work reliably, we have a strong POC.

---

# 34. Final System

```text
                         ┌─────────────────┐
                         │      USER       │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  FINANCE CHAT   │
                         │      BOT        │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   AI AGENT /    │
                         │   ORCHESTRATOR  │
                         └────────┬────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼                   ▼                   ▼
       ┌────────────┐      ┌────────────┐      ┌────────────┐
       │ Transaction│      │ Financial  │      │    RAG     │
       │   Tools    │      │  Analysis  │      │    Tool    │
       └─────┬──────┘      └──────┬─────┘      └──────┬─────┘
             │                    │                   │
             ▼                    ▼                   ▼
       transactions.json      Python Logic       FAISS
                                                     │
                                                     ▼
                                             Financial Knowledge
                                                     │
                                                     ▼
                                                  Embeddings
                                                     │
             ┌───────────────────────────────────────┘
             │
             ▼
       ┌─────────────────┐
       │      LLM        │
       │     Gemini      │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │ Natural Language│
       │    Response     │
       └─────────────────┘
```

---

# 35. Final Project Positioning

The project should be presented as:

> **AI Personal Finance Assistant — an agentic GenAI application that combines user transaction analysis, deterministic financial tools, and RAG-based financial knowledge to provide conversational, personalized financial insights.**

The key engineering story is:

```text
                ┌─────────────────────┐
                │     USER DATA       │
                │     JSON / Local     │
                └──────────┬──────────┘
                           │
                           ▼
                    Financial Tools
                           │
                           │
                           ├─────────────┐
                           │             │
                           ▼             ▼
                    Exact Analysis      RAG
                           │             │
                           │             ▼
                           │       Financial Knowledge
                           │             │
                           └──────┬──────┘
                                  ▼
                             AI AGENT
                                  │
                                  ▼
                              LOCAL LLM
                                  │
                                  ▼
                             CHATBOT
```

**The central idea is not "a chatbot that reads transactions."**

It is:

> **A conversational financial intelligence layer that can inspect a user's spending, perform deterministic analysis, retrieve trusted financial knowledge, and explain the results in natural language.**

---

# 36. Initial Technology Decision

| Component       | Choice                       |
| --------------- | ---------------------------- |
| Language        | Python                       |
| Frontend        | Streamlit                    |
| Backend         | FastAPI                      |
| Agent framework | LangChain + LangGraph        |
| Agent style     | `bind_tools()` ReAct loop    |
| LLM runtime     | Google AI Studio (free tier) |
| LLM             | gemini-2.5-flash             |
| Embeddings      | Gemini embeddings            |
| Vector store    | FAISS                        |
| User data       | JSON                         |
| Knowledge base  | Markdown                     |
| Database        | None initially               |
| External APIs   | Gemini API only              |
| Model fallback  | Chain of 4; quota is per model |
| Paid APIs       | None                         |
| OpenAI API      | None                         |
| Cloud services  | None beyond the Gemini API   |
| Primary feature | AI Finance Chatbot           |

The architecture intentionally keeps infrastructure minimal while still demonstrating the important GenAI engineering concepts: **tool calling, RAG, agent orchestration, structured data, deterministic computation, conversational state, and guardrails.**

---

# 37. Success Criteria

The POC is considered successful when a user can open the website and naturally ask:

> "Where am I spending my money?"

> "Why did my expenses increase?"

> "Can I afford this purchase?"

> "How can I reduce my spending?"

> "What is an emergency fund?"

> "How does the 50/30/20 rule apply to me?"

And the system can correctly determine whether it should use:

```text
Transaction Data
       OR
Financial Calculation
       OR
RAG
       OR
A combination of them
```

and return a grounded, understandable response.

**This decision-making layer is the core of the project.**
