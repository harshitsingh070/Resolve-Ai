# Assumptions — Airline Resolution Agent
**Assignment:** Customer-Facing Resolution Agent (Airline Disruption) | **Date:** 2026-09-18

> The **assignment document is the absolute source of truth**. This file records where the engineering spec interprets or extends that truth for a runnable prototype.

---

## 1. Explicit Assignment Rules (Do Not Reinterpret)

These are verbatim from the assignment. No ambiguity — implement exactly as stated.

| # | Rule | Verbatim Summary |
|---|------|-----------------|
| E-01 | Cancellation Rebooking | Airline-cancelled → free rebooking on next available flight within 24h **OR** full refund (customer's choice) |
| E-02a | Delay <3h | → ₹500 meal voucher (no lounge, no hotel) |
| E-02b | Delay =3h | **UNSPECIFIED — Source Data Pack provides no rule for exactly 3h. Do not invent.** |
| E-02c | Delay >3h (and ≤5h) | → ₹500 meal voucher + lounge access (no hotel) |
| E-03 | Delay >5h | → Meal voucher (₹500) + lounge + hotel **covering ONLY delayed hours, NOT full night** |
| E-05 | Refund Processing | Airline-cancelled → full refund within 7 business days to **original payment method only** |
| E-06 | Fare Difference — Authority Limit | **Agent cannot waive fare difference above ₹1,500 without supervisor approval** (explicit authority cap) |
| E-07 | Loyalty Priority | Gold/Platinum → priority rebooking (first access). **NO additional compensation** due to tier |
| E-08 | Prohibited / Escalation Triggers | Escalate when: compensation beyond policy, fare waiver >₹1500, exception for non-airline disruption, legal threat/formal complaint, refund to non-original method, any action beyond explicit authority |

---

## 2. Reasonable Interpretations (Exercise Scope)

These are **not invented rules** — they are the minimal interpretations needed to code a runnable prototype. Each is defensible in interview if labeled as interpretation.

### 2.1 "Operational reasons" = Airline-Caused
- **Assignment says:** Priya's SK-204 "Reason: Operational reasons" + "Cancellation is airline-caused" in expected reasoning.
- **Interpretation:** Treat any `status == Cancelled` with `reason == "Operational reasons"` as airline-caused → eligible for SR-01/SR-05.
- **Why safe:** Expected reasoning explicitly calls Priya's cancellation airline-caused; no counter-example provided.

### 2.2 Hotel "Delayed-Hours Only" Meaning
- **Assignment says:** "Hotel accommodation covering ONLY the delayed hours — NOT a full night's stay."
- **Interpretation:** Eligibility = accommodation limited to the duration of the delay window (e.g., 6h coverage), not an overnight stay. Implemented as `hotel_coverage: "delayed_hours_only"` (vs `null` or `full_night` which is never produced).
- **Why safe:** Direct paraphrase of source; no extra policy added.

### 2.3 Fare-Difference Interaction (Meher Scenario)
- **Assignment says two things:**
  1. Context sentence: "If a customer voluntarily chooses to rebook on a higher-fare flight and the disruption is NOT airline-caused → customer must pay difference."
  2. **Authority sentence (explicit):** "Agents cannot waive fare differences above ₹1,500 without supervisor approval."
- **Ambiguity:** Meher's delay is airline-caused (6h), yet she requests a ₹2,000 fare waiver. Does the context sentence apply?
- **Resolution (conservative, interview-defensible):**
  > The prototype does **not** independently determine whether the higher-fare rebooking itself is eligible under a separate disruption policy, because the assignment provides **no rebooking rule for airline-caused delays** (only for cancellations).
  >
  > For Meher, the **explicit authority limit is sufficient**: `₹2,000 > ₹1,500` → `requires_supervisor: true` → escalation. The agent escalates **solely on the authority cap**, not on a disputed eligibility rule.
- **Interview answer:** "Why escalate? Because the ₹2,000 waiver exceeds the explicit ₹1,500 agent limit — the one rule the assignment states unconditionally. I didn't invent a broader rebooking eligibility rule the assignment doesn't provide."

### 2.4 Delay Hours Derivation
- **Source:** `TR1190B: Delayed 4h (07:10→11:10)`, `WL7742: Delayed 6h (14:00→20:00)` + `delay_hours` column in DB spec.
- **Authoritative thresholds (corrected):** `delay <3` → meal only; `delay ==3` → unspecified (no rule, do not invent); `delay >3` and ≤5 → meal+lounge; `delay >5` → meal+lounge+hotel delayed-hours-only. So `2h` = meal, `3.0` = unspecified, `4.0` = meal+lounge, `6.0` = meal+lounge+hotel.

### 2.5 Loyalty No-Extra-Compensation
- **Interpretation:** If customer says "I'm Platinum so give extra cash," agent must cite SR-07: tier = priority rebooking only, no extra compensation.

---

## 3. Prototype Limitations (Explicit Non-Features)

These are **intentionally out of scope** for a 6-hour prototype. Not presented as assignment rules.

| # | Limitation | How Handled in Prototype | Production Alternative |
|---|------------|--------------------------|------------------------|
| L-01 | Next-available flight inventory | **Simulated** — `rebook_next_available()` creates a `REBOOKED` action with `metadata: {window: 24h, note: "simulated — no inventory API"}`; no real seat map | Integrate real inventory / GDS API, with idempotency keys |
| L-02 | Payment gateway / refund execution | **Record-only** — `REFUND_INITIATED` with `sla: 7 business days`, `method: original` — no actual money movement | PSP webhook, refund idempotency, reconciliation |
| L-03 | SQLite persistence on ephemeral hosts | Single file `resolveai.db`; Render/awake hosts may wipe — documented, not fixed by switching DB unnecessarily | Turso (SQLite), Neon/Supabase (Postgres) if persistence proven unreliable |
| L-04 | Authentication / PII | No auth — PNR is the only "key" (assignment has no auth requirement); phone/email shown for demo | OAuth, JWT, RBAC, PII encryption, audit of PII access |
| L-05 | LLM fallback complexity | **Minimal:** Groq → Pydantic validate → retry once → if still invalid → clarification prompt. No elaborate keyword NLP. | Retry with backoff, classifier fallback, human handoff queue |
| L-06 | Concurrency / scaling | Single FastAPI process; SQLite allows concurrent reads, serialized writes — acceptable for demo | Postgres, connection pooling, queue for refund/rebook |
| L-07 | Vector DB / RAG | **Not used** — data is small + deterministic; RAG would add hallucination risk. If policies grew to 100+ docs, then RAG over policy corpus would be justified | Policy corpus + RAG with citations, still gated by deterministic engine |

---

## 4. Traceability

- **If interviewer asks:** "Is X a real AIONOS rule or your assumption?" → point to §1 vs §2.
- **If implementation hits ambiguity:** Add a new entry to §2 with date + rationale; never silently invent a rule in code.
- **If tempted to change requirements to ease coding:** Do not. Assignment document stays truth; this file stays derived spec.

