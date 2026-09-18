# API Contract — ResolveAI (FastAPI)
**Version:** 1.0 | **Date:** 2026-09-18 | **Base URL:** `http://localhost:8000` (dev) | `https://<render-app>.onrender.com` (prod)
**Spec sources:** `requirements.md:89-96`, `architecture.md:602-643`, `database.md`
**Interactive docs (when backend running):** `http://localhost:8000/docs` (Swagger) + `/redoc`

> All data is **PNR-centric** (you type `SK4821X`). No auth token in v1 — PNR is the key. `GROQ_API_KEY` never appears in requests.

---

## 1. At-a-Glance — All APIs (Frozen)

| # | Method | Path | File | Purpose | Used By |
|---|--------|------|------|---------|---------|
| 1 | `POST` | `/api/chat` | `routes/chat.py` | **Main agent turn** — intent → policy → tools → audit → grounded response | ChatWindow Send |
| 2 | `GET` | `/api/customers/{pnr}` | `routes/customers.py` | Customer card | Left panel on PNR change |
| 3 | `GET` | `/api/bookings/{pnr}` | `routes/bookings.py` | Booking card (supports `?include_return=true` for Priya's return leg) | Left panel |
| 4 | `GET` | `/api/actions/{pnr}` | `routes/bookings.py` | Action Log timeline | Right panel |
| 5 | `GET` | `/api/conversations/{pnr}` | `routes/chat.py` | Full chat history | ChatWindow history |
| 6 | `GET` | `/api/health` | `main.py` | Health check | Deployment / frontend "backend unreachable" check |

**Common headers:** `Content-Type: application/json` for POST. No custom headers. CORS enabled for `http://localhost:5173` (Vite).

---

## 2. Conventions

### 2.1 Base & Errors

| Item | Value |
|------|-------|
| **Content-Type** | `application/json` |
| **Success** | `200 OK` with JSON body |
| **Not found** | `404` + `{"detail":"...","code":"PNR_NOT_FOUND"}` |
| **Validation** | `422` + FastAPI/Pydantic `{"detail":[{"loc":["body","pnr"],"msg":"Field required"}]}` |
| **Server / Groq fail** | `500` + `{"detail":"Agent failed: ...","code":"AGENT_ERROR"}` (still returns `decision_trace` if policy reached) |
| **Timestamps** | ISO `YYYY-MM-DDTHH:MM:SSZ` (UTC) |
| **PNR format** | 6–8 chars `A-Z0-9 + '-R'` (e.g., `SK4821X`, `SK4821X-R`); case-insensitive, trimmed, uppercased server-side |

### 2.2 Error Envelope (All Endpoints)

```json
// 404 example
{
  "detail": "Booking not found for PNR 'XX9999'. Try SK4821X, TR1190B, or WL7742.",
  "code": "PNR_NOT_FOUND"
}
// codes: PNR_NOT_FOUND, CUSTOMER_NOT_FOUND, VALIDATION_ERROR, AGENT_ERROR
```

---

## 3. Schemas — Shared Shapes (Pydantic → TS)

### 3.1 `CustomerOut` — `schemas.py` + `types/index.ts`

```json
{
  "id": 1,
  "name": "Priya Nair",
  "loyalty_tier": "Gold",
  "pnr": "SK4821X",
  "email": "priya.nair@example.com",
  "phone": "+91-98xxxxxx1"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `loyalty_tier` | `"Gold" \| "Silver" \| "Platinum"` | SR-07 priority only |

### 3.2 `BookingOut`

```json
{
  "id": 1,
  "customer_id": 1,
  "pnr": "SK4821X",
  "flight_number": "SK-204",
  "route": "Delhi → Goa",
  "travel_date": "2026-09-23",
  "scheduled_departure": "18:40",
  "status": "Cancelled",
  "delay_hours": null,
  "new_departure": null,
  "reason": "Operational reasons"
}
```

| Field | Values |
|-------|--------|
| `status` | `Cancelled \| Delayed \| Unaffected` |
| `delay_hours` | `number \| null` (4 for TR1190B, 6 for WL7742) |
| `reason` | `"Operational reasons" \| null` |

### 3.3 `ActionOut`

```json
{
  "id": 12,
  "booking_id": 3,
  "pnr": "WL7742",
  "action_type": "HOTEL",
  "status": "completed",
  "reason": "delay_over_5h",
  "metadata": {"coverage": "delayed_hours_only"},
  "created_at": "2026-09-18T09:41:12Z"
}
```

| `action_type` | `metadata` example |
|---------------|--------------------|
| `MEAL_VOUCHER` | `{"amount":500}` |
| `LOUNGE_ACCESS` | `{}` |
| `HOTEL` | `{"coverage":"delayed_hours_only"}` |
| `REFUND_INITIATED` | `{"sla":"7 business days","method":"original"}` |
| `REBOOKED` | `{"window":"24h","note":"simulated — no inventory API"}` |

### 3.4 `EscalationOut`

```json
{
  "id": 3,
  "booking_id": 3,
  "pnr": "WL7742",
  "reason": "fare_difference_exceeds_limit",
  "requested_action": "waive_2000",
  "status": "pending",
  "created_at": "2026-09-18T09:41:13Z"
}
```

`reason` enum: `upgrade_exception`, `fare_difference_exceeds_limit`, `full_night_hotel`, `refund_payment_method`, `legal_threat`, `compensation_beyond_policy`, ...

### 3.5 `IntentOut` (Groq structured output, validated by Pydantic)

```json
{
  "primary_intent": "hotel_request",
  "secondary_intents": ["fare_waiver_request"],
  "sentiment": "frustrated",
  "requested_exception": true,
  "entities": {
    "amount": 2000,
    "hotel_type": "full_night",
    "refund_method": null,
    "upgrade_class": null
  }
}
```

`primary_intent` enum: `refund_request | rebooking_request | meal_voucher_request | lounge_request | hotel_request | fare_waiver_request | booking_inquiry | upgrade_request | complaint | unknown`
`sentiment`: `neutral | frustrated | angry | legal_threat` (→ immediate escalate if `legal_threat`)

### 3.6 `DecisionTrace` (string facts, not chain-of-thought)

```json
[
  "Intent: hotel_request + fare_waiver_request (frustrated)",
  "Verified facts: WL7742, Meher Kaur (Platinum), SK-305 Delayed 6h, new departure 20:00",
  "Policy: SR-03 delay_over_3h → meal ₹500 ✓, lounge ✓",
  "Policy: SR-04 delay_over_5h → hotel delayed_hours_only ✓, full-night ✗",
  "Authority: SR-06 fare diff ₹2,000 > limit ₹1,500 → requires supervisor",
  "Actions: MEAL_VOUCHER issued, LOUNGE_ACCESS granted, HOTEL delayed-hours created",
  "Escalation: fare waiver → pending supervisor"
]
```

---

## 4. `POST /api/chat` — Main Loop (Locked)

### 4.1 Request

```http
POST /api/chat
Content-Type: application/json

{
  "pnr": "WL7742",
  "message": "I want a full night hotel and waive ₹2000 for rebooking"
}
```

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `pnr` | string | **Yes** (or empty → `ask_for_pnr`) | Trimmed, uppercased; `SK4821X`, `TR1190B`, `WL7742`, `SK4821X-R` |
| `message` | string | **Yes** | 1–2000 chars, trimmed; empty → 422 |

**Empty PNR (ask-for-PNR flow):**

```json
{ "pnr": "", "message": "my flight was cancelled" }
→ 200 { "ask_for_pnr": true, "response": "I can help. Please share your PNR (e.g., SK4821X, TR1190B, WL7742).", ... }
```

### 4.2 Response (200)

```json
{
  "response": "I understand this is frustrating. For your 6-hour delay (SK-305, 14:00→20:00) you are eligible for: ₹500 meal voucher, lounge access, and hotel covering the delayed-hours only (not a full night). The ₹2,000 fare difference exceeds my ₹1,500 limit, so I've escalated that part to a supervisor and will keep you posted.",
  "intent": {
    "primary_intent": "hotel_request",
    "secondary_intents": ["fare_waiver_request"],
    "sentiment": "frustrated",
    "requested_exception": true,
    "entities": {"amount": 2000, "hotel_type": "full_night", "refund_method": null, "upgrade_class": null}
  },
  "actions": [
    {"id": 10, "booking_id": 4, "pnr": "WL7742", "action_type": "MEAL_VOUCHER", "status": "completed", "reason": "delay_over_3h", "metadata": {"amount": 500}, "created_at": "2026-09-18T09:41:12Z"},
    {"id": 11, "booking_id": 4, "pnr": "WL7742", "action_type": "LOUNGE_ACCESS", "status": "completed", "reason": "delay_over_3h", "metadata": {}, "created_at": "2026-09-18T09:41:12Z"},
    {"id": 12, "booking_id": 4, "pnr": "WL7742", "action_type": "HOTEL", "status": "completed", "reason": "delay_over_5h", "metadata": {"coverage": "delayed_hours_only"}, "created_at": "2026-09-18T09:41:12Z"}
  ],
  "escalation": {
    "id": 3, "booking_id": 4, "pnr": "WL7742",
    "reason": "fare_difference_exceeds_limit",
    "requested_action": "waive_2000",
    "status": "pending",
    "created_at": "2026-09-18T09:41:13Z"
  },
  "decision_trace": [
    "Intent: hotel_request + fare_waiver_request (frustrated)",
    "Verified facts: WL7742, Meher Kaur (Platinum), SK-305 Delayed 6h (14:00→20:00)",
    "Policy: SR-03 delay_over_3h → meal ₹500 ✓, lounge ✓",
    "Policy: SR-04 delay_over_5h → hotel delayed_hours_only ✓, full-night ✗",
    "Authority: SR-06 fare diff ₹2,000 > limit ₹1,500 → requires_supervisor → escalation",
    "Actions: MEAL_VOUCHER issued, LOUNGE_ACCESS granted, HOTEL delayed-hours created",
    "Escalation: fare waiver → pending supervisor"
  ],
  "booking": {
    "id": 4, "customer_id": 3, "pnr": "WL7742",
    "flight_number": "SK-305", "route": "Delhi → Hyderabad",
    "travel_date": "2026-09-23", "scheduled_departure": "14:00",
    "status": "Delayed", "delay_hours": 6, "new_departure": "20:00", "reason": null
  },
  "customer": {
    "id": 3, "name": "Meher Kaur", "loyalty_tier": "Platinum",
    "pnr": "WL7742", "email": "meher.kaur@example.com", "phone": "+91-98xxxxxx3"
  }
}
```

| Field | Type | Notes |
|-------|------|-------|
| `response` | string | Grounded, empathetic — **only from verified PolicyResult/AuthorizationResult** |
| `intent` | `IntentOut` | Structured understanding |
| `actions` | `ActionOut[]` | Executed this turn (plus `GET /api/actions` for full history) |
| `escalation` | `EscalationOut \| null` | Set if any escalation created this turn |
| `decision_trace` | `string[]` | Interview trace — facts → rules → actions → escalation |
| `booking` + `customer` | objects | For right/left panel refresh |

**Other response shapes:**

| Situation | `response` start | `actions` | `escalation` | `decision_trace` includes |
|-----------|------------------|-----------|--------------|---------------------------|
| **Unknown PNR** `XX9999` | `"I couldn't find that booking..."` | `[]` | `null` | `Verified facts: PNR not found` |
| **No PNR** `pnr=""` | `"Please share your PNR..."` | `[]` | `null` | `Ask for PNR` |
| **Arvind 4h hotel denied** | `"Hotel requires delay over 5h..."` | `[MEAL_VOUCHER, LOUNGE]` | `null` | `Policy: hotel ✗ (4h < 5h)` |
| **Priya refund ok + upgrade escalated** | `"Your refund is initiated..."` | `[REFUND_INITIATED]` | `{reason: upgrade_exception}` | `Policy: SR-01 refund ✓` |
| **Legal threat** | `"Escalating immediately..."` | `[]` | `{reason: legal_threat, status: pending}` | `Sentiment: legal_threat → immediate escalation` |

### 4.3 Status Codes for POST /api/chat

| Code | When | Body |
|------|------|------|
| 200 | Success, unknown PNR, ask-for-PNR, policy blocked, or escalated — all still 200 with `response` + `decision_trace` | As above |
| 422 | Missing `pnr` or `message`, empty message, `message` >2000 | `{"detail":[...]}` |
| 500 | Groq timeout after retry, DB error | `{"detail":"Agent failed: ...","code":"AGENT_ERROR"}` |

### 4.4 cURL / PowerShell Examples (POST /api/chat)

```powershell
# PowerShell — Priya refund + upgrade (S-01)
curl -Method POST http://localhost:8000/api/chat `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"pnr":"SK4821X","message":"I am furious! I want full cash refund and free business upgrade for the trouble."}'

# PowerShell — Arvind 4h hotel (S-02, hotel denied)
curl -Method POST http://localhost:8000/api/chat `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"pnr":"TR1190B","message":"I may miss my meeting, need hotel accommodation"}'

# PowerShell — Meher 6h full-night + 2000 waiver (S-03, escalate)
curl -Method POST http://localhost:8000/api/chat `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"pnr":"WL7742","message":"Give me full night hotel and waive my 2000 fare difference"}'

# bash (same)
curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" \
  -d '{"pnr":"WL7742","message":"I need somewhere to stay and rebook higher fare"}'

# Empty PNR → ask-for-PNR
curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" \
  -d '{"pnr":"","message":"my flight is delayed"}'

# Unknown PNR → friendly 200 (not 404 for chat — keeps conversation going)
curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" \
  -d '{"pnr":"XX9999","message":"hello"}'
```

---

## 5. `GET /api/customers/{pnr}`

```http
GET /api/customers/SK4821X
```

**200 — Found:**

```json
{"id":1,"name":"Priya Nair","loyalty_tier":"Gold","pnr":"SK4821X","email":"priya.nair@example.com","phone":"+91-98xxxxxx1"}
```

**404 — Not found:**

```json
{"detail":"Customer not found for PNR 'XX9999'.","code":"PNR_NOT_FOUND"}
```

**Used by:** `CustomerCard.tsx` on `selectedPnr` change.

```powershell
curl http://localhost:8000/api/customers/SK4821X
curl http://localhost:8000/api/customers/WL7742
```

---

## 6. `GET /api/bookings/{pnr}`

```http
GET /api/bookings/SK4821X
GET /api/bookings/SK4821X-R   # Priya's return leg (1—N demo)
```

**200 — Found (single booking for this PNR):**

```json
{"id":1,"customer_id":1,"pnr":"SK4821X","flight_number":"SK-204","route":"Delhi → Goa","travel_date":"2026-09-23","scheduled_departure":"18:40","status":"Cancelled","delay_hours":null,"new_departure":null,"reason":"Operational reasons"}
```

**404 — Not found:** same envelope.

**Optional query (recommended to implement):**

```http
GET /api/bookings/SK4821X?include_return=true
→ 200 [
     {"pnr":"SK4821X", ... status:"Cancelled"},
     {"pnr":"SK4821X-R", ... status:"Unaffected"}
   ]
# If not implemented, just call GET twice for the two PNRs — also acceptable for 6h scope.
```

```powershell
curl http://localhost:8000/api/bookings/TR1190B
curl http://localhost:8000/api/bookings/WL7742
```

---

## 7. `GET /api/actions/{pnr}`

```http
GET /api/actions/WL7742
```

**200 — Always 200 (empty array if none yet):**

```json
[
  {"id":10,"booking_id":4,"pnr":"WL7742","action_type":"MEAL_VOUCHER","status":"completed","reason":"delay_over_3h","metadata":{"amount":500},"created_at":"2026-09-18T09:41:12Z"},
  {"id":11,"booking_id":4,"pnr":"WL7742","action_type":"LOUNGE_ACCESS","status":"completed","reason":"delay_over_3h","metadata":{},"created_at":"2026-09-18T09:41:12Z"},
  {"id":12,"booking_id":4,"pnr":"WL7742","action_type":"HOTEL","status":"completed","reason":"delay_over_5h","metadata":{"coverage":"delayed_hours_only"},"created_at":"2026-09-18T09:41:12Z"}
]
```

**Unknown PNR:** `404 PNR_NOT_FOUND` (or `200 []` — choose one, but be consistent; recommended: `404` for GET, `200` with message for POST chat).

**Polling:** frontend calls this after each `POST /api/chat` and on PNR change to refresh `ActionLog.tsx`.

```powershell
curl http://localhost:8000/api/actions/SK4821X
curl http://localhost:8000/api/actions/TR1190B | ConvertFrom-Json | Format-Table action_type,status
```

---

## 8. `GET /api/conversations/{pnr}`

```http
GET /api/conversations/WL7742
```

**200 — Ordered by `created_at ASC`:**

```json
[
  {"id":40,"booking_id":4,"pnr":"WL7742","role":"user","message":"I want full-night hotel","intent":null,"created_at":"2026-09-18T09:40:00Z"},
  {"id":41,"booking_id":4,"pnr":"WL7742","role":"assistant","message":"Hotel covers delayed-hours only...","intent":{"primary_intent":"hotel_request","sentiment":"frustrated"},"created_at":"2026-09-18T09:41:12Z"}
]
```

**404 / 200 []:** same choice as §7.

```powershell
curl http://localhost:8000/api/conversations/SK4821X
```

---

## 9. `GET /api/health` (Optional but Recommended)

```http
GET /api/health
→ 200 {"status":"ok","db":"connected","groq":"configured"}
```

**For:** Render health checks + frontend "Backend unreachable" banner.

If not implemented, frontend can `GET /docs` or `GET /api/customers/SK4821X` as probe.

---

## 10. Frontend Call Order (How UI Uses These)

```
User picks PNR "WL7742"
   │
   ├─ GET /api/customers/WL7742   ──▶  CustomerCard
   ├─ GET /api/bookings/WL7742    ──▶  BookingCard
   ├─ GET /api/actions/WL7742     ──▶  ActionLog
   └─ GET /api/conversations/WL7742 ──▶ ChatWindow history
                (4 in parallel, Promise.all)

User clicks Send "waive 2000"
   │
   └─ POST /api/chat {pnr:"WL7742", message:"waive 2000"}
        ◀─ {response, intent, actions, escalation, decision_trace, booking, customer}
             │
             ├─ append to messages[]
             ├─ setDecisionTrace(decision_trace)
             ├─ setActions(prev + actions)   // or refetch GET /api/actions
             └─ if escalation → show EscalationBanner
```

---

## 11. Validation & Security Notes

| Rule | Enforcement |
|------|-------------|
| `pnr` missing/empty on `POST /chat` | Return `ask_for_pnr` 200 (not 422) — keeps chat flowing |
| `message` empty / >2000 | `422` — Pydantic `field_validator` |
| Unknown PNR on `GET` | `404 PNR_NOT_FOUND` |
| Unknown PNR on `POST /chat` | `200` with `"I couldn't find that booking..."` — still conversational |
| `GROQ_API_KEY` | Never in request/response, never in frontend `fetch`, only `backend/.env` → `config.py` |
| Prompt injection ("ignore policy") | Intent still `upgrade_request` → Policy says ❌ → `response` denies — policy overrides |
| Idempotency | `POST /chat` twice with same `pnr+message` does **not** duplicate `actions` (tool + DB partial unique) |

---

## 12. Quick Test Matrix (What Interviewer Will Try)

| Try | Expected API Result |
|-----|---------------------|
| `POST /chat` Priya refund | `actions=[REFUND_INITIATED]`, `escalation=null`, trace `SR-01 refund ✓` |
| `POST /chat` Priya upgrade | `actions=[]` or with refund, `escalation={reason: upgrade_exception}`, trace `no policy → escalate` |
| `POST /chat` Arvind hotel (4h) | `actions=[MEAL_VOUCHER, LOUNGE]`, no HOTEL, trace `hotel ✗ 4h < 5h` |
| `POST /chat` Meher hotel (6h) | `actions=[MEAL, LOUNGE, HOTEL(delayed_hours_only)]`, `escalation=null` for hotel alone |
| `POST /chat` Meher waive 2000 | `actions` as above, `escalation={fare_difference_exceeds_limit}` |
| `POST /chat` paraphrase "need somewhere to stay" | Same as `hotel_request` → same `decision_trace` — proves deterministic |
| `POST /chat` `"sue you!"` | `escalation={legal_threat, pending}` immediate |
| `GET /customers/XX9999` | `404 PNR_NOT_FOUND` |
| `GET /actions/SK4821X` after reset | `[]` (seed has no actions) |

---

## 13. PowerShell Sanity Script (After `uvicorn` Up)

```powershell
$BASE="http://localhost:8000"
# Health
Invoke-RestMethod "$BASE/api/health" -ErrorAction SilentlyContinue | Format-List

# Customers & bookings
Invoke-RestMethod "$BASE/api/customers/SK4821X" | Format-List
Invoke-RestMethod "$BASE/api/bookings/TR1190B" | Format-List
Invoke-RestMethod "$BASE/api/bookings/WL7742" | Format-List

# Chat — full Meher scenario
Invoke-RestMethod -Method POST "$BASE/api/chat" -ContentType "application/json" `
  -Body '{"pnr":"WL7742","message":"I want full night hotel and waive 2000 fare difference"}' |
  Select-Object -ExpandProperty decision_trace | ForEach-Object { $_ }

# Verify persistence
Invoke-RestMethod "$BASE/api/actions/WL7742" | Format-Table action_type,status
Invoke-RestMethod "$BASE/api/conversations/WL7742" | Select-Object role,message | Format-Table -Wrap
```

---

> **Single rule to remember:** `POST /api/chat` is the only endpoint that *does* things; the four `GET`s only *show* things. Trace, intent, and escalation always come back together in the chat response.

