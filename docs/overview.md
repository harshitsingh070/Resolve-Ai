# ResolveAI — Project Overview

**Separate file as requested — contains 1–4 only (README remains for setup).**

---

## 1. Working Agent / Clickable Prototype

**Live:** **https://resolve-ai-frontend-puce.vercel.app/**  
**Local:** `http://localhost:5173` + `http://localhost:8000/docs`

**Seeded PNRs:**
* `SK4821X` Priya Nair Gold `SK-204 Delhi→Goa 23 Sep 18:40 Cancelled Operational` + return `SK-204R`
* `TR1190B` Arvind Kulkarni Silver `SK-118 Mumbai→Bengaluru 23 Sep 07:10 Delayed 4h new 11:10`
* `WL7742` Meher Kaur Platinum `SK-305 Delhi→Hyderabad 23 Sep 14:00 Delayed 6h new 20:00`

**60-sec demo:** `Arvind: I need a hotel` → meal+lounge, hotel blocked (>5h) · `Meher: full-night + waive 2000` → hotel delayed + escalated · `Priya: refund + business upgrade` → refund + escalated · `XX9999` → not found · `Ctrl+R` persists via `GET /api/session`.

---

## 2. Architecture and Process Flow

**Stack:** React 19 + Vite 8 + Tailwind 4.3 | Python 3.12 + FastAPI + SQLAlchemy + SQLite | Groq `openai/gpt-oss-20b` | pytest 99 | No Postgres/Redis/Docker/RAG

**Flow (10 steps):** `Customer → React (1280px,100vh) → FastAPI → Orchestrator → Groq intent → DB verified facts → Policy Engine (pure) → Authorization → Tools/Escalation (self-check idempotent) → Audit (conversations.decision_trace) → Groq response → Customer`

**State:** `RECEIVED → UNDERSTOOD → CONTEXT_LOADED → POLICY_EVALUATED → AUTHORIZED → EXECUTED/ESCALATED → AUDITED → RESPONDED`

**Files:** `app/main.py` (auto-seed if empty), `policies/policy_engine.py`, `agent/orchestrator.py`, `tools/*`, `models.py` 1—N, `routes/session.py` read-only refresh.

---

## 3. Inputs, Sources and Assumptions Used

**Source:** Assignment Data Pack only.

**Inputs — Customers/Bookings:** as above (3 customers, 4 bookings).

**Service rules:** Cancellation free rebook 24h OR refund 7d original; Delay <3 meal ₹500; =3 unspecified; >3 meal+lounge; >5 + hotel delayed-hours only; Fare waiver ≤1500 else supervisor; Gold/Platinum priority only.

**Assumptions (explicit):** Operational = airline-caused; Hotel delayed-hours = not overnight; Fare 2000 solely on authority limit; `delay_hours` from status string thresholds strict `>3`/`>5`; Prototype limits: rebook simulated, refund record-only, SQLite ephemeral auto-seed, no auth (PNR demo key), LLM retry once.

---

## 4. List of AI Tools Used and How They Were Used

| Tool | How |
|------|-----|
| **Groq API `openai/gpt-oss-20b` (runtime)** | Intent classification (`INTENT_PROMPT` → JSON) + grounded response (`RESPONSE_PROMPT` on verified `policy_result/actions/escalation`) — never decides policy |
| **Muse Spark via OpenCode (dev)** | Scaffolding, docs, tests, prompts under engineer review — policy kept deterministic Python, tools self-check, key never committed |

No RAG/vector DB/LangChain — data is 3 rows + 7 rules.
