# ResolveAI — Airline Customer-Facing Resolution Agent

**Assignment 3 — Airline Disruption** · Policy-grounded agent that understands customer intent, checks deterministic business rules, executes allowed actions, and escalates the rest.

> **Principle:** `LLM understands and communicates. Deterministic Python enforces business rules.`

![Stack](https://img.shields.io/badge/Frontend-React%20%2B%20Vite%20%2B%20Tailwind-blue) ![Backend](https://img.shields.io/badge/Backend-FastAPI%20%2B%20SQLite-green) ![LLM](https://img.shields.io/badge/LLM-Groq%20openai%2Fgpt--oss--20b-orange)

---

## Live Demo (local)

* **Frontend:** `http://localhost:5173` (Vite)
* **Backend:** `http://localhost:8000` (`/docs` for Swagger)
* **3 PNRs:** `SK4821X` Priya (Cancelled Gold), `TR1190B` Arvind (Delayed 4h Silver), `WL7742` Meher (Delayed 6h Platinum)

---

## Tech Stack

* **Frontend:** React 19 + Vite 8 + TypeScript + Tailwind 4.3 (`@tailwindcss/vite`)
* **Backend:** Python 3.12 + FastAPI 0.115 + Pydantic 2.11 + SQLAlchemy 2.0
* **DB:** SQLite (`backend/resolveai.db`, file-based, zero-setup)
* **LLM:** Groq API (`openai/gpt-oss-20b`, structured JSON, `temperature 0.1/0.3`)
* **Tests:** pytest 8.3 (99 tests)

**No** Postgres, Redis, Docker, RAG, LangChain — intentionally simple for 6-hour scope.

---

## Quick Start (Windows PowerShell)

```powershell
# 1. Clone
git clone https://github.com/harshitsingh070/Resolve-Ai.git
cd ResolveAI

# 2. Backend
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # set GROQ_API_KEY from https://console.groq.com/keys
python seed.py           # 3 customers + 4 bookings (Priya has 2)
python -m uvicorn app.main:app --reload --port 8000
# -> http://localhost:8000/docs

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev              # -> http://localhost:5173 (VITE_API_URL=http://localhost:8000)
```

**Env (`backend/.env`):**
```
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-20b
DATABASE_URL=sqlite:///./resolveai.db
```

---

## Architecture (v1.1 locked)

```
Customer → React (centered 1280px, 100vh) → FastAPI → Orchestrator → Groq (intent) → DB (verified facts) → Policy Engine (pure Python) → Authorization → Tools/Escalation → Audit → Groq (response) → Customer
```

* **Policy Engine** (`app/policies/policy_engine.py`): `evaluate_delay` (<3 meal, =3 unspecified, >3 meal+lounge, >5 hotel delayed), `evaluate_cancellation` (Cancelled+Operational → refund/rebook 24h 7d original), `evaluate_fare_difference` (≤1500 waive, >1500 escalate).
* **Tools** self-check + idempotent (`booking_id+action_type`).
* **DB** `Customer 1—N Bookings 1—N Actions/Conversations/Escalations` (`booking_id FK` + `pnr IDX`).
* **Session** `GET /api/session/{pnr}` persists `decision_trace` on `conversations.decision_trace` (read-only refresh, no Groq re-run).
* Docs: `docs/requirements.md`, `architecture.md`, `database.md`, `api-contract.md`, `assumptions.md`.

---

## API (per `docs/api-contract.md`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | `{pnr, message}` → `{response, intent, actions, escalation, decision_trace, booking, customer}` |
| `GET` | `/api/session/{pnr}` | Hydrate after refresh (customer, booking, messages, trace, actions, escalation) |
| `GET` | `/api/customers/{pnr}` | Customer card |
| `GET` | `/api/bookings/{pnr}` | Booking card (`?include_return=true` for Priya) |
| `GET` | `/api/actions/{pnr}` | Action log |
| `GET` | `/api/conversations/{pnr}` | Chat history |
| `GET` | `/api/health` | `ok` |

**PPNR handling:** `SK4821X-R` (Priya return) resolves via `booking.customer_id`; `XX9999` → `404`.

---

## Policy Rules (from `docs/policy-rules.md`)

* **Cancellation (airline):** free rebook within 24h **OR** full refund (customer choice), 7 days original method.
* **Delay <3h:** meal ₹500
* **Delay =3h:** **unspecified** (no entitlement)
* **Delay >3h:** meal ₹500 + lounge
* **Delay >5h:** + hotel delayed-hours only (not full night)
* **Fare waiver:** agent ≤₹1,500, `>1500` → supervisor (`1500.01` escalates)
* **Loyalty Gold/Platinum:** priority rebooking only, no extra compensation.

---

## Demo Script (3 mandatory scenarios)

**Priya `SK4821X` Cancelled:** `"I am furious! I want full cash refund and free business upgrade for the trouble."` → `REFUND_INITIATED` + `upgrade_exception escalated` (Gold no extra).
**Arvind `TR1190B` Delayed 4h:** `"I need a hotel"` (or `somewhere to stay`, `place to stay`, `provide a room`) → `MEAL_VOUCHER` + `LOUNGE_ACCESS`, `HOTEL blocked (>5h SR-04)`.
**Meher `WL7742` Delayed 6h:** `"I want a full-night hotel and waive 2000"` → `MEAL+LOUNGE+HOTEL delayed_hours_only` + `fare 2000 escalated (>1500 SR-06)` (full-night not granted).

See `docs/demo-script.md` for 15-min defence.

---

## Tests

```powershell
cd backend
.\venv\Scripts\python -m pytest tests -v   # 99 passed
.\venv\Scripts\python -m pytest tests/test_policy_engine.py -v
.\venv\Scripts\python -m pytest tests/test_e2e_scenarios.py -v
```

Covers: `2h meal, 3h unspecified, 4h meal+lounge, 6h hotel, 1500/1500.01/2000, cancellation, hotel coverage, refund alternate, PNR isolation, refresh idempotency, hotel paraphrases (11), session persistence`.

---

## Frontend UX

* **Minimal Enterprise Airline** `#F8FAFC` + `#2563EB`, Inter, centered `760px` portal (header `68px`, scenario tabs `Priya·Cancellation` subtle, booking `YOUR FLIGHT` + `PASSENGER`, chat `YOU blue / ASSISTANT slate` with `Checking booking…`, right `RESOLUTION ✓/⚠/✕` + `Details ▸` + `ACTIONS & STATUS`).
* **PNR dropdown** with `Provided` + `Recently used` (localStorage, filter-as-you-type).
* **Refresh:** `GET /api/session/{pnr}` restores `messages/trace/actions/escalation` without Groq/tool re-run.
* **Mobile:** stacks `Customer → Booking → Chat → Resolution`.

---

## Deployment

* **Frontend:** Vercel (`VITE_API_URL` → Render URL)
* **Backend:** Render/Fly (`uvicorn app.main:app`, `PORT 8000`, SQLite file; ephemeral FS may reset — see `assumptions.md L-03`, locally persistent)
* No Docker/K8s needed.

---

## Project Structure

```
ResolveAI/
├── backend/app/{main,config,database,models,schemas,routes/{chat,customers,bookings,session},agent/{orchestrator,intent,prompts},policies/policy_engine,tools/*}
├── backend/seed.py, requirements.txt, resolveai.db
├── frontend/src/{App, components/*, services/api, types}
├── docs/{requirements,architecture,database,api-contract,assumptions,policy-rules,demo-script}
├── .env.example, .gitignore, README.md
```

---

## Interview Defence (25 Qs in `docs/requirements.md:88`)

Why Groq? Why deterministic engine? Hallucination prevention? Escalation? SQLite? RAG avoided? Scaling? Idempotency?

**Agent vs Chatbot:** Chatbot generates text; agent does `intent → verified facts → policy → authorization → tool → audit → grounded response` with `decision_trace`.

---

## License

Assignment prototype — not for production without auth, payments, inventory integration.

