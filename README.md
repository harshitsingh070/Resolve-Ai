# ResolveAI — Airline Customer-Facing Resolution Agent

**Live:** **https://resolve-ai-frontend-puce.vercel.app/** · **API Docs:** `https://<backend>.onrender.com/docs` (or `http://localhost:8000/docs` locally)

Policy-grounded agent for airline disruptions — understands customer intent (Groq), checks deterministic business rules (Python), executes allowed actions or escalates, and keeps full audit.

> **Principle:** `LLM understands and communicates. Deterministic Python enforces business rules.`

---

## Try It Live (no setup)

1. Open **https://resolve-ai-frontend-puce.vercel.app/**
2. Pick a scenario or type a PNR:
   * `SK4821X` — **Priya Nair** (Gold) · `SK-204 Delhi → Goa` · **CANCELLED** (Operational reasons) · Return `SK-204R Goa → Delhi Unaffected`
   * `TR1190B` — **Arvind Kulkarni** (Silver) · `SK-118 Mumbai → Bengaluru` · **Delayed 4h** → new `11:10`
   * `WL7742` — **Meher Kaur** (Platinum) · `SK-305 Delhi → Hyderabad` · **Delayed 6h** → new `20:00`
   * `XX9999` — unknown (shows friendly error)
3. Try these messages (paraphrases work too):
   * **Arvind 4h hotel:** `I need a hotel` / `I need accommodation` / `I need somewhere to stay` / `Can you arrange accommodation?` / `Can you provide a room?` → `✓ Meal ₹500 + ✓ Lounge` , `✕ Hotel — requires >5h (SR-04)`
   * **Meher 6h hotel:** `I need a hotel for the whole night` → `✓ Meal + ✓ Lounge + ✓ Hotel delayed hours only` (never full-night)
   * **Meher fare:** `waive my 2000 fare difference` / `I want a full-night hotel and waive 2000` → `Hotel delayed + ⚠ ₹2,000 → supervisor (>₹1,500 SR-06)` (`1500` allowed, `1500.01` escalates)
   * **Priya refund + upgrade:** `I am furious! I want full cash refund and free business upgrade for the trouble.` → `✓ Refund initiated (7 days, original method SR-05)` + `⚠ Upgrade escalated (SR-07, no extra for Gold)`
   * **Hello:** `hello` → `General inquiry` → still shows booking, no fake actions
4. **Refresh** `Ctrl+R` → chat, trace, actions, escalation stay (via `GET /api/session/{pnr}` read-only, no duplicate actions, no new Groq call)
5. **Switch PNR** via `PNR` dropdown (shows **Provided** + **Recently used**, filter-as-you-type) or scenario tabs — old trace/actions clear, new PNR loads only its data

**PNR dropdown:** header `PNR [ SK4821X ▼]` + centered `Find my booking` both show **Provided** (`SK4821X/TR1190B/WL7742/SK4821X-R`) + **Recently used** (last 6 from `localStorage`, persisted across refresh).

---

## What Happened / What’s Allowed (quick ref)

* **Cancellation (airline, Operational):** free rebook within 24h **OR** full refund (choice) → 7 days to original method only
* **Delay <3h:** meal ₹500
* **Delay =3h:** **unspecified** (no entitlement)
* **Delay >3h & ≤5h:** meal ₹500 + lounge
* **Delay >5h:** + hotel **delayed-hours only** (never full night)
* **Fare waiver:** agent ≤₹1,500 → supervisor if `>1500`
* **Loyalty Gold/Platinum:** priority rebooking only, no extra

Full table in `docs/policy-rules.md`.

---

## Tech Stack

* **Frontend:** React 19 + Vite 8 + TypeScript + Tailwind 4.3 (`@tailwindcss/vite`), `100vh` no page scroll — centered `1280px` portal (`Header 68px` + `Scenario tabs` + `YOUR FLIGHT` horizontal + `68% Chat / 32% Actions`, only chat scrolls)
* **Backend:** Python 3.12 + FastAPI 0.115 + Pydantic 2.11 + SQLAlchemy 2.0 + Groq `openai/gpt-oss-20b` (structured JSON, retry once → fallback)
* **DB:** SQLite `backend/resolveai.db` (`Customer 1—N Bookings 1—N Actions/Conversations/Escalations`, `conversations.decision_trace` persisted for refresh)
* **Tests:** pytest 8.3 — **99 passed** (policy / tools / intent / orchestrator / session / e2e)

No Postgres, Redis, Docker, RAG, LangChain — intentionally simple.

---

## Run Locally (Windows PowerShell)

```powershell
# 1. Clone
git clone https://github.com/harshitsingh070/Resolve-Ai.git
cd ResolveAI

# 2. Backend http://localhost:8000  (http://localhost:8000/docs)
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # set GROQ_API_KEY from https://console.groq.com/keys
python seed.py           # 3 customers + 4 bookings (Priya has 2)
python -m uvicorn app.main:app --reload --port 8000

# 3. Frontend http://localhost:5173  (new terminal)
cd frontend
npm install
npm run dev              # VITE_API_URL defaults to http://localhost:8000
# or: $env:VITE_API_URL="https://<your-backend>.onrender.com"; npm run dev
```

**Env (`backend/.env`):**
```
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-20b
DATABASE_URL=sqlite:///./resolveai.db
```

**Verify:**
```powershell
Invoke-RestMethod http://localhost:8000/api/health
Invoke-RestMethod http://localhost:8000/api/customers/SK4821X
$body=@{pnr="TR1190B";message="Need hotel accommodation"} | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/api/chat -Method POST -ContentType "application/json" -Body $body
```

---

## API (see `docs/api-contract.md` + `http://localhost:8000/docs`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/chat` | `{pnr, message}` → `{response, intent, actions, escalation, decision_trace, booking, customer}` |
| `GET` | `/api/session/{pnr}` | Hydrate after refresh (single read-only) |
| `GET` | `/api/customers/{pnr}` | Customer card |
| `GET` | `/api/bookings/{pnr}` (`?include_return=true`) | Booking card (Priya return) |
| `GET` | `/api/actions/{pnr}` | Action log |
| `GET` | `/api/conversations/{pnr}` | Chat history |
| `GET` | `/api/health` | `ok` |

`SK4821X-R` (Priya return) resolves via `booking.customer_id`; `XX9999` → `404` (chat stays `200` with friendly message).

---

## Tests

```powershell
cd backend
.\venv\Scripts\python -m pytest tests -v   # 99 passed
```

Covers: `2h meal, 3h unspecified, 4h meal+lounge, 6h hotel, 1500/1500.01/2000, cancellation, hotel coverage, refund alternate, PNR isolation, refresh idempotency, hotel paraphrases (11), session persistence, e2e Priya/Arvind/Meher`.

---

## Deployment (Vercel + Render, free tier)

* **Frontend (Vercel):** import `frontend` as Vite → Build `npm run build` → Output `dist` → Env `VITE_API_URL=https://<backend>.onrender.com` → Deploy (live at **https://resolve-ai-frontend-puce.vercel.app/**)
* **Backend (Render):** `backend` → Build `pip install -r requirements.txt` (uses `runtime.txt` `python-3.12.10`) → Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT` → Env `GROQ_API_KEY`, `GROQ_MODEL`, `DATABASE_URL` → Health `GET /api/health` → first request auto-seeds if DB empty (free tier ephemeral FS, no Shell needed)

Details + SQLite persistence note in `docs/deployment.md`.

---

## Project Structure

```
ResolveAI/
├── backend/app/{main,config,database,models,schemas,routes/{chat,customers,bookings,session},agent/{orchestrator,intent,prompts},policies/policy_engine,tools/*}
├── backend/seed.py, requirements.txt, runtime.txt, resolveai.db
├── frontend/src/{App, components/*, services/api, types}
├── docs/{requirements,architecture,database,api-contract,assumptions,policy-rules,demo-script,deployment}
└── .env.example, .gitignore
```

---

## Interview Defence (25 Qs in `docs/requirements.md`)

Why Groq? Why deterministic engine? Hallucination prevention? Escalation? Why SQLite? RAG avoided? Scaling? Idempotency?

**Agent vs Chatbot:** Chatbot generates text; agent does `intent → verified facts → policy → authorization → tool → audit → grounded response` with `decision_trace` persisted on `conversations.decision_trace`.

---

## License

Assignment prototype — not for production without auth, payments, inventory integration.
