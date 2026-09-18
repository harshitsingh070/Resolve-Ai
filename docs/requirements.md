# Requirements — Airline Customer-Facing Resolution Agent
**Assignment 3 — Airline Disruption (ResolveAI)**
**Version:** 1.0 | **Date:** 2026-09-18 | **Source of Truth:** Assignment Document

> Principle: **"LLM understands and communicates. Deterministic backend logic enforces business rules."** LLM is never the final authority.

---

## 1. Business Problem

Build a **working, explainable, policy-grounded customer resolution agent** for airline disruptions — not a generic chatbot.

The agent must:
1. Understand customer intent (including frustrated/angry tone).
2. Retrieve customer profile + booking by PNR.
3. Use **ONLY** supplied customer, booking, and service-policy data.
4. Determine which actions are allowed via deterministic policy engine.
5. Execute allowed actions through backend tools.
6. Refuse or **escalate** actions outside its authority.
7. Ask only necessary questions.
8. Maintain conversation + action history.
9. Produce a clear **audit/decision trace** per turn.
10. Be demonstrable live to an interviewer within ~6 hours scope.

**No invention allowed:** No fabricated policies, customers, compensation, refund amounts, flight info, or business rules. Assignment document is absolute truth.

---

## 2. Source Data (Seed Truth)

### 2.1 Customers & Bookings

| PNR | Customer | Loyalty | Flight | Route | Date | Scheduled | Status | New Departure | History |
|-----|----------|---------|--------|-------|------|-----------|--------|---------------|---------|
| `SK4821X` | Priya Nair<br>priya.nair@example.com<br>+91-98xxxxxx1 | Gold | SK-204 | Delhi → Goa | Wed 23 Sep 2026 | 18:40 | **Cancelled** (Operational reasons) | — | 6 flights, 1 prior complaint (delayed baggage → voucher) |
| | *Return:* Goa → Delhi | | | Fri 25 Sep 2026 | 16:20 | **Unaffected** | — | |
| `TR1190B` | Arvind Kulkarni<br>arvind.kulkarni@example.com<br>+91-98xxxxxx2 | Silver | SK-118 | Mumbai → Bengaluru | Wed 23 Sep 2026 | 07:10 | **Delayed 4h** | 11:10 | 3 flights, no complaints |
| `WL7742` | Meher Kaur<br>meher.kaur@example.com<br>+91-98xxxxxx3 | Platinum | SK-305 | Delhi → Hyderabad | Wed 23 Sep 2026 | 14:00 | **Delayed 6h** | 20:00 | 10 flights, 1 prior complaint (overbooking → tier upgrade) |

> Only these 3 PNRs exist. Any other PNR = unknown.

### 2.2 Service Rules — Absolute Source of Truth

| ID | Rule | Definition |
|----|------|------------|
| SR-01 | Cancellation Rebooking | If flight cancelled by airline → entitled to **free rebooking on next available flight within 24 hours** OR full refund (customer's choice). |
| SR-02 | Delay < 3 Hours | No compensation rule provided. |
| SR-03 | Delay > 3 Hours | → ₹500 meal voucher + lounge access |
| SR-04 | Delay > 5 Hours | → Meal voucher + lounge access + **hotel accommodation covering ONLY the delayed hours** (NOT full night) |
| SR-05 | Refund Processing | Airline-caused cancellations → full refund within **7 business days** to **original payment method only**. |
| SR-06 | Fare Difference | **Core rule (explicit):** Agent **cannot waive fare difference >₹1,500** without supervisor approval. **Context sentence from assignment:** "If a customer voluntarily chooses to rebook on a higher-fare flight and the disruption is NOT airline-caused → customer must pay the fare difference." See `assumptions.md` §2.3 for how this interacts with Meher's airline-caused delay scenario (₹2,000 waiver still requires escalation via the explicit authority limit alone). |
| SR-07 | Loyalty Tier | Gold/Platinum → **priority rebooking** (first access to next-available seats). **NO additional compensation** beyond standard policy due to tier. |

---

## 3. Functional Requirements

### 3.1 Core Agent Workflow
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | Receive customer message via `POST /api/chat` with `{pnr, message}`. | Must |
| FR-02 | Identify PNR/customer. If PNR missing → ask **only the minimum necessary question** (e.g., "Please share your PNR"). | Must |
| FR-03 | Retrieve customer + booking via deterministic lookup (`get_customer`, `get_booking`). Never hallucinate data. | Must |
| FR-04 | Extract structured intent via Groq: `{primary_intent, secondary_intents, sentiment, requested_exception, entities}`. | Must |
| FR-05 | Retrieve verified booking facts (status, delay_hours, scheduled/new departure). | Must |
| FR-06 | Run deterministic policy engine (`evaluate_delay`, `evaluate_cancellation`, `evaluate_fare_difference`). | Must |
| FR-07 | Determine allowed / prohibited / escalation-required actions. | Must |
| FR-08 | Execute **only** authorized tools. Tools must self-enforce authorization (defense-in-depth). | Must |
| FR-09 | Record every action in `actions` table + every turn in `conversations` table. | Must |
| FR-10 | Generate customer-friendly response via Groq using **only VERIFIED decision context** (never raw LLM judgment). | Must |
| FR-11 | Return `{response, intent, actions, escalation, decision_trace, booking}`. `decision_trace` = concise factual rules/facts/actions (no internal CoT). | Must |

### 3.2 Tool Requirements
| Tool | Purpose | Authorization Check |
|------|---------|---------------------|
| `get_customer(pnr)` | Fetch customer row | Always allowed |
| `get_booking(pnr)` | Fetch booking row | Always allowed |
| `evaluate_delay_compensation(pnr)` | Returns `{meal_voucher, meal_amount, lounge, hotel, hotel_coverage}` | Read-only |
| `evaluate_cancellation(pnr)` | Returns `{eligible_for_free_rebooking, rebooking_window_hours, eligible_for_full_refund}` | Read-only |
| `evaluate_fare_difference(amount)` | Returns `{fare_difference, agent_limit:1500, agent_can_waive, requires_supervisor}` | Read-only |
| `rebook_next_available(pnr)` | Simulated rebook within 24h | Only if airline-cancelled |
| `issue_meal_voucher(pnr)` | Creates MEAL_VOUCHER action | Only if delay>3h |
| `grant_lounge_access(pnr)` | Creates LOUNGE_ACCESS action | Only if delay>3h |
| `create_hotel_request(pnr, coverage)` | Creates HOTEL action | Only if delay>5h; coverage=`delayed_hours_only` |
| `initiate_refund(pnr)` | Creates REFUND_INITIATED action | Only if airline-cancelled; to original method only |
| `escalate_to_human(pnr, reason, requested_action)` | Creates escalations row | Always allowed when needed |
| `get_action_history(pnr)` | Returns actions list | Always allowed |

### 3.3 API Requirements
| Endpoint | Method | Request | Response |
|----------|--------|---------|----------|
| `/api/chat` | POST | `{pnr: string, message: string}` | `{response: string, intent: object, actions: array, escalation: object|null, decision_trace: array, booking: object}` |
| `/api/customers/{pnr}` | GET | — | Customer object or 404 |
| `/api/bookings/{pnr}` | GET | — | Booking object or 404 |
| `/api/actions/{pnr}` | GET | — | Action history array |
| `/api/conversations/{pnr}` | GET | — | Conversation history array |

### 3.4 Database Requirements (SQLite + SQLAlchemy)
**Tables (clean relational design — PNR exposed via API, not as FK):**
- `customers(id PK, name, loyalty_tier, pnr UNIQUE, email, phone)`
- `bookings(id PK, customer_id FK → customers.id, pnr UNIQUE, flight_number, route, travel_date, scheduled_departure, status, delay_hours nullable, new_departure nullable, reason nullable)`
- `actions(id PK, booking_id FK → bookings.id, pnr TEXT indexed, action_type enum, status enum, reason, metadata JSON, created_at)`
- `conversations(id PK, booking_id FK → bookings.id, pnr TEXT indexed, role enum[user,assistant], message, intent JSON nullable, created_at)`
- `escalations(id PK, booking_id FK → bookings.id, pnr TEXT indexed, reason, requested_action, status enum[pending,resolved], created_at)`

> Note: `pnr` is duplicated as indexed TEXT for fast lookup/API convenience, but the true FK is `booking_id`. Either `pnr FK → customers.pnr` is acceptable for a 6-hour scope if implemented consistently — the `booking_id FK` form above is preferred for cleaner relations.

Constraints: Keep schema simple. No unnecessary tables. Seed exactly 3 rows per customers/bookings as per source data.

### 3.5 Frontend Requirements (React + Vite + TS + Tailwind)
**Layout (3-panel):**
- **Left Sidebar:** Customer Card (Name, Tier badge, PNR, Contact) + Booking Card (Flight, Route, Date, Status badge, Delay/New Departure)
- **Center:** Conversation thread (user/assistant bubbles) + Input box + Send button + PNR selector (SK4821X/TR1190B/WL7742)
- **Right/Bottom Panel:** Decision Trace (Intent, Verified Facts ✓/✗, Policy Evaluation ✓/✗, Authority ✓/⚠) + Action Log (timeline with ✓ executed / ⚠ escalation) + Escalation Banner when present

**UX Requirements:**
- Professional, not robotic tone. Empathetic but factual.
- Clearly distinguish facts / policy decisions / executed actions / escalations (color + icons).
- Loading states, empty states ("Select a customer to start"), error states.
- Never expose API keys, internal CoT, or raw tool payloads.

---

## 4. Business Rules — Deterministic Enforcement

### 4.1 Policy Engine Function Contracts
```python
evaluate_delay(delay_hours: float) -> {
  meal_voucher: bool,
  meal_voucher_amount: int | None, # 500 if true
  lounge_access: bool,
  hotel: bool,
  hotel_coverage: "delayed_hours_only" | None
}
# truth table:
# <3h  → {false, None, false, false, None}
# 4h   → {true, 500, true, false, None}
# 6h   → {true, 500, true, true, "delayed_hours_only"}

evaluate_cancellation(booking) -> {
  eligible_for_free_rebooking: bool, # true if status==Cancelled + airline-caused
  rebooking_window_hours: int | None, # 24 if true
  eligible_for_full_refund: bool
}

evaluate_fare_difference(amount: int) -> {
  fare_difference: int,
  agent_limit: 1500,
  agent_can_waive: bool, # amount <=1500
  requires_supervisor: bool # amount >1500
}
```

**Critical:** These functions are pure Python. LLM prompts must NOT contain hidden policy logic.

### 4.2 Allowed vs Prohibited Action Matrix

| Action | Allowed? | Condition | On Violation |
|--------|:--------:|-----------|--------------|
| Rebook next available within 24h (free) | ✅ | Airline-caused cancellation (R-01) | — |
| Full refund | ✅ | Airline-caused cancellation | Block + escalate if non-airline |
| Meal voucher ₹500 | ✅ | Delay >3h | Deny with explanation |
| Lounge access | ✅ | Delay >3h | Deny with explanation |
| Hotel (delayed-hours only) | ✅ | Delay >5h | Deny; explain hotel requires >5h |
| Show own booking/flight status | ✅ | Always | — |
| Waive fare diff ≤₹1500 | ✅ | Within limit | — |
| Waive fare diff >₹1500 (e.g., ₹2000) | ❌ | Exceeds limit | **Escalate to supervisor** |
| Free business-class upgrade "for trouble" | ❌ | No policy exists | Deny; escalate if insists |
| Full-night hotel when only delayed-hours covered | ❌ | Policy ≠ full night | **Reject per policy** (not escalate unless exception demanded beyond policy) |
| Refund to non-original payment method | ❌ | SR-05 | **Escalate** |
| Compensation beyond stated amounts | ❌ | Any | **Escalate** |
| Exceptions for non-airline-caused disruption | ❌ | Any | **Escalate** |
| Threats / legal action / formal complaint | ❌ | Any | **Escalate immediately** |
| Fabricating approval | ❌ | Never | Forbidden |

Tool self-check: e.g., `initiate_refund()` must verify `booking.status==Cancelled` before writing action.

---

## 5. Mandatory Scenarios — Expected Reasoning

### Scenario 1 — Priya Nair (SK4821X, Cancelled)
**Customer says:** Furious, wants (1) full cash refund (2) free business-class upgrade on return "for trouble."
- **Verified facts:** `status=Cancelled`, `reason=Operational` → airline-caused.
- **Policy:** `evaluate_cancellation → {eligible_for_free_rebooking:true, eligible_for_full_refund:true}`
- **Action 1 — Refund:** ✅ Allowed → `initiate_refund(SK4821X)` → `REFUND_INITIATED` (7 business days, original method).
- **Action 2 — Upgrade:** ❌ No rule. Loyalty SR-07 explicitly says **no extra compensation** for Gold. Must NOT invent. Respond empathetically: "I understand frustration... policy offers rebook OR refund; no upgrade benefit exists." If insists → `escalate_to_human(reason: upgrade_exception)`.

### Scenario 2 — Arvind Kulkarni (TR1190B, Delayed 4h)
**Customer says:** Frustrated, may miss meeting, requests hotel accommodation.
- **Verified facts:** `delay_hours=4`
- **Policy:** `evaluate_delay(4) → {meal:true(500), lounge:true, hotel:false}`
- **Actions:** `issue_meal_voucher` + `grant_lounge_access` → SUCCESS. `create_hotel_request` → **BLOCKED**. Response must **explain policy**: "Delay over 3h gives meal+lounge; hotel requires over 5h, your delay is 4h so not eligible." Not just "Request denied."

### Scenario 3 — Meher Kaur (WL7742, Delayed 6h, Platinum)
**Customer says:** (1) Full-night hotel instead of delayed-hours (2) Rebook higher-fare, waive ₹2000 difference.
- **Verified facts:** `delay_hours=6`
- **Policy:** `evaluate_delay(6) → {meal:true(500), lounge:true, hotel:true(delayed_hours_only)}`
- **Actions:** Issue meal + lounge + hotel(delayed_hours_only).
- **Request 1 — Full-night hotel:** ❌ Reject per SR-04: "Hotel covers delayed-hours portion only, not full night."
- **Request 2 — Fare waiver ₹2000:** `evaluate_fare_difference(2000) → {agent_limit:1500, can_waive:false, requires_supervisor:true}` → **Escalate to supervisor**. Must NOT auto-approve. Response: "₹2,000 exceeds agent authority of ₹1,500 → escalating to supervisor."

---

## 6. Edge Cases

| # | Case | Handling |
|---|------|----------|
| EC-01 | Unknown PNR (e.g., XX9999) | `get_customer` null → "I couldn't find that booking. Please provide correct PNR." No policy eval. |
| EC-02 | PNR exists but asks about another booking | Respond only with own booking; "I can only access data for PNR {pnr}." No cross-PNR leak. |
| EC-03 | Unsupported compensation (upgrade) | No tool; "Available information/policies do not provide that. Options are..." Escalate if insists. |
| EC-04 | Unauthorized fare waiver (>1500) | `requires_supervisor:true` → escalate. |
| EC-05 | Full-night hotel vs delayed-hours | Enforce `coverage=delayed_hours_only`; deny full-night with explanation. |
| EC-06 | Refund to alternate payment method | Block → escalate (`refund_payment_method`). |
| EC-07 | Threats / legal action / formal complaint | Immediate escalation; `sentiment:legal_threat` auto-triggers. |
| EC-08 | Unrelated question ("baggage allowance for Indigo?") | "Available information/policies do not provide that. I can help with your booking per provided rules." No hallucination. |
| EC-09 | Changes request mid-conversation | Re-evaluate policy fresh each turn; history preserved in `conversations`. |
| EC-10 | "What actions have been taken?" | Call `get_action_history(pnr)` and render. |
| EC-11 | Tool failure / Groq timeout | Return error + `decision_trace`; frontend shows retry + escalation. Tools must be idempotent (check existing actions). |
| EC-12 | LLM invalid JSON / hallucinates tool | Orchestrator validates via Pydantic → **retry once** → if still invalid → ask clarification / safe fallback. No elaborate NLP fallback (6-hour scope). |

---

## 7. Non-Functional Requirements

| ID | Requirement | How Verified |
|----|-------------|--------------|
| NFR-01 | Policy-grounded — LLM responses grounded only in verified backend facts & deterministic policy results; business authz must never depend solely on LLM output | Code review: LLM only receives `policy_result` string; tests without LLM pass |
| NFR-02 | Auditability — every turn traceable | `conversations` + `actions` + `escalations` + `decision_trace` in API response |
| NFR-03 | Security — GROQ_API_KEY server-only | `.env` + `.gitignore` + `.env.example`; frontend never sees key (verify Network tab) |
| NFR-04 | Testability without LLM | `pytest` for policy engine mocks zero LLM calls |
| NFR-05 | Determinism — paraphrase same intent → same policy | Intent extraction robust to wording; policy pure function |
| NFR-06 | Responsive demo experience — optimize for low-latency interaction where practical; no strict latency SLA is assumed because prototype depends on external LLM API (Groq) + network | Groq `llama-3.1-8b-instant` / `llama-3.3-70b-versatile`; FastAPI async; no p95 guarantee claimed |
| NFR-07 | Simplicity & scope — no over-engineering | No Postgres, Redis, Docker, K8s, VectorDB, RAG, LangChain unless justified |
| NFR-08 | Production-quality code | Small functions, clear naming, Pydantic, type hints, error handling |
| NFR-09 | Idempotency | Duplicate `issue_meal_voucher` for same PNR returns existing, not duplicate row |

---

## 8. Technology Stack (Prescribed)

- **Frontend:** React + Vite + TypeScript (if practical) + Tailwind CSS
- **Backend:** Python + FastAPI + Pydantic
- **Database:** SQLite + SQLAlchemy
- **LLM:** Groq API (model with structured output/tool-calling; e.g., `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`)
- **Environment:** Windows + PowerShell + VS Code

**Do NOT introduce** PostgreSQL, Redis, Docker, Kubernetes, microservices, vector DB, RAG, LangChain, complex cloud infra without specific reason. Assignment data is small & deterministic.

---

## 9. Project Structure (Target)

```
ResolveAI/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── routes/
│   │   │   ├── chat.py
│   │   │   ├── customers.py
│   │   │   └── bookings.py
│   │   ├── agent/
│   │   │   ├── orchestrator.py
│   │   │   ├── intent.py
│   │   │   └── prompts.py
│   │   ├── policies/
│   │   │   └── policy_engine.py
│   │   └── tools/
│   │       ├── customer_tools.py
│   │       ├── booking_tools.py
│   │       ├── compensation_tools.py
│   │       ├── refund_tools.py
│   │       └── escalation_tools.py
│   ├── seed.py
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── types/
│   │   └── App.tsx
│   └── package.json
├── docs/
│   ├── requirements.md   ← this file
│   ├── architecture.md
│   ├── policy-rules.md
│   ├── demo-script.md
│   └── assumptions.md
├── README.md
├── .gitignore
└── .env.example
```

---

## 10. Testing Requirements

### 10.1 Policy Engine Unit Tests (Must pass without LLM)
- Cancellation: airline cancellation → `eligible_for_full_refund:true`, `eligible_for_free_rebooking:true`
- Delay 2h → `{meal:false, lounge:false, hotel:false}`
- Delay 4h → `{meal:true(500), lounge:true, hotel:false}`
- Delay 6h → `{meal:true(500), lounge:true, hotel:true(delayed_hours_only)}`
- Fare diff ₹1000 → `agent_can_waive:true`
- Fare diff ₹1500 → `agent_can_waive:true` (at limit)
- Fare diff ₹2000 → `agent_can_waive:false, requires_supervisor:true`
- Authority: unsupported upgrade → escalate
- Full-night hotel when only delayed-hours → reject
- Refund to non-original method → escalate

### 10.2 Integration / E2E Tests
- Chat flow for S-01, S-02, S-03 (request → intent → policy → tool → trace → DB row)
- Unknown PNR, legal threat, alternate refund method, paraphrased intents

---

## 11. Observability / Audit

Every interaction records: `timestamp, pnr, customer, user_message, detected_intent, verified_booking_facts, policy_rules_triggered, actions_executed, escalation, final_response`.

**Example trace:**
```json
{
  "pnr": "WL7742",
  "intent": "hotel_request",
  "delay_hours": 6,
  "policy_results": ["delay_over_3_hours", "delay_over_5_hours"],
  "actions": ["MEAL_VOUCHER_500", "LOUNGE_ACCESS", "HOTEL_DELAYED_HOURS"],
  "escalation": null,
  "hotel_coverage": "delayed_hours_only",
  "fare_waiver": {"amount": 2000, "requires_supervisor": true}
}
```

Never expose internal chain-of-thought. Provide concise factual decision trace only.

---

## 12. Security & AI Safety

- `GROQ_API_KEY` in `backend/.env` (ignored) + `.env.example` with placeholder.
- Tools enforce authorization; LLM cannot bypass.
- **Prompt design:** Never ask LLM "Should we give ₹2000?" Instead: `System: Policy result = fare diff 2000 > limit 1500 → escalation required. Communicate this.` Then LLM verbalizes.
- Separate responsibilities: LLM (intent, sentiment, response generation) vs Python (lookup, policy, authz, execution, audit).

---

## 13. Success Criteria (Final Gate)

- [ ] React frontend works (Vite+Tailwind)
- [ ] FastAPI backend works
- [ ] SQLite works; exact 3 customers/bookings seeded
- [ ] Policy engine independent & tested
- [ ] Groq intent + response works
- [ ] Orchestrator: message→intent→context→policy→authz→tool→audit→response
- [ ] Tools enforce authz; unauthorized blocked/escalated
- [ ] Refund flow (airline cancellation) works
- [ ] Rebooking simulated correctly (24h window)
- [ ] Delay compensation (meal/lounge/hotel) per hours works
- [ ] ₹1,500 authority limit enforced
- [ ] Conversation + action history persisted
- [ ] Decision trace per turn
- [ ] All 3 scenarios pass + edge cases handled
- [ ] Tests pass
- [ ] README + docs/ complete
- [ ] PPT 10 slides + 15-min defence prepared
- [ ] GitHub clean, no secrets, reviewer can run (`pip install`, `seed.py`, `uvicorn`, `npm run dev`)

---

## 14. Assumptions & Constraints

> Full breakdown in `docs/assumptions.md` (3 sections: Explicit Rules / Reasonable Interpretations / Prototype Limitations). Summary here:

1. **Assignment source of truth vs engineering spec:** The assignment document is authoritative. This file is the derived engineering spec — do not modify requirements to ease implementation.
2. **Reasonable interpretations (marked as such):** See `assumptions.md` §2 for: "Operational reasons" = airline-caused, hotel "delayed-hours only" interpretation, fare-difference interaction for Meher, delay_hours derivation.
3. **Prototype limitations (explicit):** See `assumptions.md` §3 for: simulated rebooking (no inventory), no payment gateway, SQLite persistence caveat, LLM fallback scope.

**Rule:** Ambiguity = explicit assumption, not invented rule.

---

## 15. Interview Defence — Key Questions Prepared For

1. Why LLM? 2. Why Groq? 3. Why not LLM for policy? 4. Hallucination prevention? 5. Business rule enforcement? 6. Unsupported requests? 7. Escalation? 8. Why SQLite? 9. Scaling? 10. Concurrent requests? 11. Securing customer data? 12. Auth in production? 13. Real airline API? 14. Tool failures? 15. Idempotency? 16. Monitoring? 17. Agent accuracy eval? 18. Invalid tool request? 19. Unauthorized refunds? 20. Why deterministic engine? 21. Prod changes? 22. Why avoid RAG? 23. When would RAG help? 24. Chatbot vs agent? 25. Where is agentic behavior?

---

**Next:** Phase 1 — Architecture (system diagram, ER, request flow, policy signatures, tool contracts, prompt design, tradeoffs). Awaiting approval.

