# Demo Script — 15-Minute Defence

**Goal:** Show policy-grounded agent, not chatbot.

## 0–2m: Problem
Airline disruption needs explainable agent: understand intent → check verified booking → enforce deterministic policy → execute or escalate → audit.

## 2–4m: Architecture (one slide)
`React → FastAPI → Orchestrator → Groq (intent) → DB (facts) → Policy Engine (pure) → Authorization → Tools/Escalation → Audit → Groq (response)` — LLM never decides policy.

## 4–6m: DB + Policy
`backend/resolveai.db` `Customer 1—N Bookings` (Priya 2). `policy_engine.py` truth table (<3 meal, =3 unspecified, >3 meal+lounge, >5 hotel). `pytest 80+` without LLM.

## 6–11m: Live Demo (3 scenarios)
1. **Priya SK4821X Cancelled** → `POST /api/chat` `refund + upgrade` → `REFUND_INITIATED` + `upgrade_exception escalated` (Gold no extra) → `GET /api/session` shows same after refresh.
2. **Arvind TR1190B Delayed 4h** → `Need hotel accommodation` (try paraphrases `somewhere to stay`, `place to stay`, `provide a room`) → `MEAL_VOUCHER + LOUNGE`, `HOTEL blocked (>5h SR-04)` — trace `Hotel accommodation`.
3. **Meher WL7742 Delayed 6h** → `full-night hotel and waive 2000` → `MEAL+LOUNGE+HOTEL delayed_hours_only` + `fare 2000 escalated (>1500 SR-06)` — full-night not granted.

Show `Decision trace` (Intent + Verified facts + Policy + Authority + Actions + Escalation) and `Action Log`.

## 11–13m: AI Safety
Groq = intent + wording, Python = truth. Tools self-check (`issue_meal_voucher` checks `delay>3`), `GROQ_API_KEY` server-only, `decision_trace` persisted on `conversations.decision_trace` for refresh (no Groq re-run).

## 13–15m: Tradeoffs & Q&A
SQLite file (simple, reviewer can open), no RAG (3 rows + 7 rules, no corpus — would use RAG for 100+ policy docs). Scaling: Postgres + queue + inventory API. 25 Qs in `requirements.md:88`.
