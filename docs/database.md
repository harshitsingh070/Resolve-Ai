# Database — ResolveAI (SQLite + SQLAlchemy)
**Version:** 1.0 | **Date:** 2026-09-18 | **DB:** `backend/resolveai.db` (SQLite file)
**ORM:** SQLAlchemy 2.x | **Seed:** `backend/seed.py` (intentional `python seed.py`, not auto on startup)
**Spec sources:** `requirements.md:98-104`, `architecture.md:210-276`, `assumptions.md`

> One-sentence idea: **`customers 1—N bookings 1—N (actions, conversations, escalations)`** — PNR is the *API key* you type; `booking_id` is the *relational key* the DB joins on. Every chat turn and tool result is persisted for audit.

---

## 1. Why This DB?

- **Assignment says:** keep simple — SQLite, 5 tables max, no Postgres/Redis.
- **Data is tiny:** 3 customers + 4 bookings + handful of actions/conversations. SQLite file is enough, reviewer can open it with `sqlite3` or DB browser.
- **Audit matters:** every intent + policy check + tool + escalation must be traceable — so we store `conversations`, `actions`, `escalations` with timestamps.
- **No extra tables:** no `flights`, `inventory`, `payments` — rebooking is simulated in `actions.metadata`; refund is `REFUND_INITIATED` record.

---

## 2. ER Diagram — How Tables Connect

```
                        ┌─────────────┐
                        │  customers  │
                        ├─────────────┤
                        │ id PK       │◀─────────────┐
                        │ name        │               │ customer_id FK
                        │ loyalty_tier│               │
                        │ pnr UNIQUE  │               │
                        │ email       │               │
                        │ phone       │               │
                        └─────────────┘               │
                              │1                     │
                              │                      │
                              ▼                      │
                        ┌─────────────┐               │
                        │  bookings   │               │
                        ├─────────────┤               │
                        │ id PK       │               │
                        │ customer_id FK ─────────────┘
                        │ pnr UNIQUE  │  ← API key you type (SK4821X)
                        │ flight_number│
                        │ route       │
                        │ travel_date │
                        │ scheduled_departure │
                        │ status      │  Cancelled | Delayed | Unaffected
                        │ delay_hours │  NULL for Cancelled/Unaffected, 4/6 for Delayed
                        │ new_departure│  11:10 / 20:00
                        │ reason      │  "Operational reasons" or NULL
                        └──────┬──────┘
                               │1
               ┌───────────────┼────────────────┐
               │               │                │
               ▼               ▼                ▼
        ┌───────────┐  ┌──────────────┐ ┌──────────────┐
        │  actions  │  │conversations │ │ escalations  │
        ├───────────┤  ├──────────────┤ ├──────────────┤
        │ id PK     │  │ id PK        │ │ id PK        │
        │ booking_id│  │ booking_id   │ │ booking_id   │
        │ pnr IDX   │  │ pnr IDX      │ │ pnr IDX      │
        │ action_type│ │ role         │ │ reason       │
        │ status    │  │ message      │ │ requested_   │
        │ reason    │  │ intent JSON  │ │  action      │
        │ metadata  │  │ created_at   │ │ status       │
        │ created_at│  └──────────────┘ │ created_at   │
        └───────────┘                   └──────────────┘

  Legend:  ──▶ = Foreign Key (FK)  |  PK = Primary Key  |  UNIQUE/IDX = index
```

**In plain English:**

* **1 Customer → N Bookings** via `bookings.customer_id → customers.id`. Priya has 2 bookings (SK4821X + SK4821X-R).
* **1 Booking → N Actions / Conversations / Escalations** via `booking_id`. All audit rows hang off the booking they belong to.
* **`pnr TEXT IDX`** is duplicated on child tables for **fast `WHERE pnr = ?`** lookups from the API (you call `GET /api/actions/SK4821X`). The *true* relational join is still `booking_id`.

---

## 3. Tables — Column by Column (Beginner-Friendly)

### 3.1 `customers` — Who the traveler is

| Column | Type | Constraints | Example | Why |
|--------|------|-------------|---------|-----|
| `id` | INTEGER | PK, autoincrement | `1` | Internal row id (never shown to UI) |
| `name` | TEXT | NOT NULL | `Priya Nair` | Customer card left panel |
| `loyalty_tier` | TEXT | NOT NULL, `Gold | Silver | Platinum` | Policy SR-07 priority rebooking |
| `pnr` | TEXT | **UNIQUE**, NOT NULL, indexed | `SK4821X` | Booking Reference — *what user types* |
| `email` | TEXT | NOT NULL | `priya.nair@example.com` | Contact display |
| `phone` | TEXT | NOT NULL | `+91-98xxxxxx1` | Contact display |

**Row count:** exactly 3 (seed, locked).

### 3.2 `bookings` — What was booked and what happened

| Column | Type | Constraints | Example | Why |
|--------|------|-------------|---------|-----|
| `id` | INTEGER | PK | `1` | Internal |
| `customer_id` | INTEGER | FK → `customers.id`, NOT NULL | `1` → Priya | Links to owner |
| `pnr` | TEXT | **UNIQUE**, indexed | `SK4821X` | API lookup key |
| `flight_number` | TEXT | NOT NULL (`—` for return leg placeholder) | `SK-204` | Booking card |
| `route` | TEXT | NOT NULL | `Delhi → Goa` | Booking card |
| `travel_date` | TEXT (ISO `YYYY-MM-DD`) | NOT NULL | `2026-09-23` | Card + policy window check |
| `scheduled_departure` | TEXT (`HH:MM`) | NOT NULL | `18:40` | Card |
| `status` | TEXT | `Cancelled | Delayed | Unaffected`, NOT NULL | Drives policy |
| `delay_hours` | REAL | NULLABLE | `4`, `6`, or `NULL` | Policy engine input |
| `new_departure` | TEXT | NULLABLE | `11:10`, `20:00`, or `NULL` | Delayed flights |
| `reason` | TEXT | NULLABLE | `Operational reasons` or `NULL` | Cancellation reason (airline-caused?) |

**Row count:** exactly 4 (Priya has 2 — forward cancelled + return unaffected).

### 3.3 `actions` — What the agent *did* (audit)

| Column | Type | Constraints | Example | Why |
|--------|------|-------------|---------|-----|
| `id` | INTEGER | PK | `12` | Timeline order |
| `booking_id` | INTEGER | FK → `bookings.id`, NOT NULL, indexed | `3` → WL7742 | Owner booking |
| `pnr` | TEXT | indexed | `WL7742` | Fast `WHERE pnr` without join |
| `action_type` | TEXT | NOT NULL — enum: `MEAL_VOUCHER`, `LOUNGE_ACCESS`, `HOTEL`, `REFUND_INITIATED`, `REBOOKED` | `HOTEL` | What tool ran |
| `status` | TEXT | NOT NULL — `completed | blocked | failed` | Outcome |
| `reason` | TEXT | NULLABLE | `delay_over_5h` | Rule that triggered it |
| `metadata` | JSON (TEXT) | NULLABLE | `{"amount":500}`, `{"coverage":"delayed_hours_only"}`, `{"sla":"7 business days"}` | Extra facts for decision trace + UI |
| `created_at` | DATETIME | NOT NULL, default `now()` | `2026-09-18 09:41:12` | Action Log sort |

**Idempotency:** before INSERT, tools check `WHERE booking_id=? AND action_type=? AND status='completed'` → if found, return existing (no duplicate).

### 3.4 `conversations` — What was *said* (audit)

| Column | Type | Constraints | Example | Why |
|--------|------|-------------|---------|-----|
| `id` | INTEGER | PK | `45` | Chat order |
| `booking_id` | INTEGER | FK → `bookings.id`, NOT NULL, indexed | `1` | Owner |
| `pnr` | TEXT | indexed | `SK4821X` | Fast lookup |
| `role` | TEXT | `user | assistant`, NOT NULL | `user` | Bubble side |
| `message` | TEXT | NOT NULL | `I want hotel for tonight` | ChatWindow |
| `intent` | JSON (TEXT) | NULLABLE | `{"primary_intent":"hotel_request","sentiment":"frustrated"}` | Stored intent for trace |
| `decision_trace` | JSON (TEXT) | NULLABLE | `["Intent: Hotel accommodation","Policy: delay 4h → meal ₹500 ✓"]` | Persisted factual trace for refresh (assistant rows only, no Groq regeneration) |
| `created_at` | DATETIME | NOT NULL | `2026-09-18 09:40:00` | History sort |

**Kept:** every user + assistant turn. Intent + decision_trace stored on assistant rows (Phase 8.5, `conversations.decision_trace` added via `ensure_trace_column()` migration; old rows without trace return `[]`).

### 3.5 `escalations` — What needed a *human*

| Column | Type | Constraints | Example | Why |
|--------|------|-------------|---------|-----|
| `id` | INTEGER | PK | `3` | Order |
| `booking_id` | INTEGER | FK → `bookings.id`, NOT NULL | `3` | Owner |
| `pnr` | TEXT | indexed | `WL7742` | Fast lookup |
| `reason` | TEXT | NOT NULL | `fare_difference_exceeds_limit`, `upgrade_exception`, `refund_payment_method`, `legal_threat` | Why escalated |
| `requested_action` | TEXT | NOT NULL | `waive_2000`, `full_night_hotel`, `business_upgrade` | What user wanted |
| `status` | TEXT | NOT NULL — `pending | resolved` | `pending` | For supervisor queue (outside 6h scope) |
| `created_at` | DATETIME | NOT NULL | `2026-09-18 09:41:13` | Banner + log |

---

## 4. SQL DDL (What SQLite Actually Creates)

```sql
-- customers
CREATE TABLE customers (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  name         TEXT NOT NULL,
  loyalty_tier TEXT NOT NULL CHECK (loyalty_tier IN ('Gold','Silver','Platinum')),
  pnr          TEXT NOT NULL UNIQUE,
  email        TEXT NOT NULL,
  phone        TEXT NOT NULL
);

-- bookings
CREATE TABLE bookings (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id         INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  pnr                 TEXT NOT NULL UNIQUE,
  flight_number       TEXT NOT NULL,
  route               TEXT NOT NULL,
  travel_date         TEXT NOT NULL,  -- ISO YYYY-MM-DD
  scheduled_departure TEXT NOT NULL,  -- HH:MM
  status              TEXT NOT NULL CHECK (status IN ('Cancelled','Delayed','Unaffected')),
  delay_hours         REAL,           -- NULL or 4, 6
  new_departure       TEXT,           -- NULL or HH:MM
  reason              TEXT            -- "Operational reasons" or NULL
);
CREATE INDEX idx_bookings_customer_id ON bookings(customer_id);
CREATE INDEX idx_bookings_pnr ON bookings(pnr);

-- actions
CREATE TABLE actions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  booking_id  INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  pnr         TEXT NOT NULL,
  action_type TEXT NOT NULL CHECK (action_type IN ('MEAL_VOUCHER','LOUNGE_ACCESS','HOTEL','REFUND_INITIATED','REBOOKED')),
  status      TEXT NOT NULL CHECK (status IN ('completed','blocked','failed')),
  reason      TEXT,
  metadata    TEXT,  -- JSON
  created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_actions_booking_id ON actions(booking_id);
CREATE INDEX idx_actions_pnr ON actions(pnr);
CREATE UNIQUE INDEX uq_actions_once ON actions(booking_id, action_type) WHERE status='completed';
-- the partial unique index enforces idempotency at DB level too

-- conversations
CREATE TABLE conversations (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  pnr        TEXT NOT NULL,
  role       TEXT NOT NULL CHECK (role IN ('user','assistant')),
  message    TEXT NOT NULL,
  intent     TEXT,  -- JSON
  decision_trace TEXT,  -- JSON array, persisted factual trace (Phase 8.5)
  created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_conversations_booking_id ON conversations(booking_id);
CREATE INDEX idx_conversations_pnr ON conversations(pnr);

-- escalations
CREATE TABLE escalations (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  booking_id       INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  pnr              TEXT NOT NULL,
  reason           TEXT NOT NULL,
  requested_action TEXT NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('pending','resolved')),
  created_at       DATETIME NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_escalations_booking_id ON escalations(booking_id);
CREATE INDEX idx_escalations_pnr ON escalations(pnr);
```

**SQLAlchemy models** (`backend/app/models.py`) map 1:1 to above; Pydantic schemas (`schemas.py`) mirror them for API I/O.

---

## 5. Relationships — Cardinality & Why

| From → To | Cardinality | FK Column | Meaning |
|-----------|-------------|-----------|---------|
| `customers` → `bookings` | **1 — N** | `bookings.customer_id` | One traveler can have many PNRs. Seed: Priya has `SK4821X` + `SK4821X-R`. No extra table needed. |
| `bookings` → `actions` | **1 — N** | `actions.booking_id` | One booking accumulates many tool results over many turns (voucher, lounge, hotel, refund). |
| `bookings` → `conversations` | **1 — N** | `conversations.booking_id` | One booking has a full chat thread. |
| `bookings` → `escalations` | **1 — N** | `escalations.booking_id` | One booking can escalate multiple times (upgrade + fare waiver). |

**Why `pnr` duplicated on children?** API is PNR-centric (`GET /api/actions/SK4821X`). `WHERE pnr=?` avoids a JOIN to `bookings` for every panel refresh — fast, simple, still correct because FK `booking_id` is the *truth*.

**Why not `pnr FK → customers.pnr`?** `pnr` is not a PK in `customers`; true relational join must be numeric `booking_id`. This was a review fix (`requirements.md:98-104`, `architecture.md:248-252`).

---

## 6. Seed Data — Exact Rows (Frozen)

### 6.1 `customers` (3 rows)

| id | name | loyalty_tier | pnr | email | phone |
|----|------|--------------|-----|-------|-------|
| 1 | Priya Nair | Gold | SK4821X | priya.nair@example.com | +91-98xxxxxx1 |
| 2 | Arvind Kulkarni | Silver | TR1190B | arvind.kulkarni@example.com | +91-98xxxxxx2 |
| 3 | Meher Kaur | Platinum | WL7742 | meher.kaur@example.com | +91-98xxxxxx3 |

### 6.2 `bookings` (4 rows)

| id | customer_id → | pnr | flight_number | route | travel_date | scheduled_departure | status | delay_hours | new_departure | reason |
|----|---------------|-----|---------------|-------|-------------|---------------------|--------|-------------|---------------|--------|
| 1 | 1 (Priya) | SK4821X | SK-204 | Delhi → Goa | 2026-09-23 | 18:40 | Cancelled | NULL | NULL | Operational reasons |
| 2 | 1 (Priya) | SK4821X-R | — | Goa → Delhi | 2026-09-25 | 16:20 | Unaffected | NULL | NULL | — |
| 3 | 2 (Arvind) | TR1190B | SK-118 | Mumbai → Bengaluru | 2026-09-23 | 07:10 | Delayed | 4 | 11:10 | — |
| 4 | 3 (Meher) | WL7742 | SK-305 | Delhi → Hyderabad | 2026-09-23 | 14:00 | Delayed | 6 | 20:00 | — |

> Priya's return leg (`SK4821X-R`) is a *second booking* for the same customer — clean `1—N` without a flights table (architecture.md:254-267). If you prefer 3 bookings only, collapse the return into `bookings.metadata` — but the `1—N` form above is recommended.

### 6.3 `actions` / `conversations` / `escalations` — Initially Empty

Seed does **not** pre-create actions or chats. They grow as you demo:

| Scenario | After conversation, you will see in `actions` |
|----------|-----------------------------------------------|
| Priya `SK4821X` — "full refund" + "business upgrade" | `REFUND_INITIATED(completed)` + `escalations(upgrade_exception, pending)` |
| Arvind `TR1190B` — "hotel please" | `MEAL_VOUCHER(completed)`, `LOUNGE_ACCESS(completed)` — no HOTEL |
| Meher `WL7742` — "full-night hotel + waive 2000" | `MEAL_VOUCHER`, `LOUNGE_ACCESS`, `HOTEL(delayed_hours_only)` + `escalations(fare_difference_exceeds_limit, pending)` |

---

## 7. How Common Queries Work (API → SQL)

| User Action | API Call | SQL Behind It |
|-------------|----------|---------------|
| Open `SK4821X` | `GET /api/customers/SK4821X` | `SELECT * FROM customers WHERE pnr='SK4821X'` |
| Show booking | `GET /api/bookings/SK4821X` | `SELECT * FROM bookings WHERE pnr='SK4821X'` |
| Send chat | `POST /api/chat {pnr, message}` | `SELECT * FROM bookings WHERE pnr=?` → `INSERT INTO conversations (user)` → policy → `INSERT INTO actions/escalations` → `INSERT INTO conversations (assistant)` → return |
| Refresh Action Log | `GET /api/actions/WL7742` | `SELECT * FROM actions WHERE pnr='WL7742' ORDER BY created_at` |
| Refresh chat | `GET /api/conversations/WL7742` | `SELECT * FROM conversations WHERE pnr='WL7742' ORDER BY created_at` |
| Check idempotency | (inside tool) | `SELECT * FROM actions WHERE booking_id=? AND action_type=? AND status='completed'` → if found, return existing |

---

## 8. Seed Script — How & When to Run

| Question | Answer |
|----------|--------|
| **File** | `backend/seed.py` |
| **When to run** | Intentionally, when you want a **clean demo**: `python seed.py` (or `python -m app.seed --reset` if implemented with flag). **Not on every server restart.** |
| **Normal startup** | `uvicorn app.main:app` → `Base.metadata.create_all()` only creates missing tables. Existing `actions`/`conversations`/`escalations` are **kept**. |
| **What seed does** | Deletes seed customers/bookings and re-inserts the 3+4 rows above. Optionally warns/clears child audit rows if `--reset` (to avoid orphans). Idempotent — safe to run repeatedly. |
| **Production note** | SQLite file `resolveai.db` lives next to `seed.py`. On ephemeral hosts (Render) it may reset on deploy — see `assumptions.md` L-03; locally it's permanent. |

**Verify seed worked:**

```powershell
# PowerShell (Windows)
python backend/seed.py
sqlite3 backend/resolveai.db "SELECT pnr, flight_number, status, delay_hours FROM bookings;"
# Expected: 4 rows as in §6.2

sqlite3 backend/resolveai.db "SELECT pnr, count(*) FROM bookings GROUP BY pnr;"
# Each PNR unique — sanity check
```

---

## 9. Indexes & Constraints — Why They Exist

| Index/Constraint | Purpose | What It Prevents |
|------------------|---------|------------------|
| `customers.pnr UNIQUE` | API key integrity | Duplicate PNR |
| `bookings.pnr UNIQUE` | API key integrity | Duplicate booking |
| `idx_*_pnr` | Fast `WHERE pnr=?` | Slow panel refresh |
| `idx_*_booking_id` | Fast joins + FK lookups | Slow audit queries |
| `CHECK (status IN ...)` | Data validity | Typo statuses |
| `CHECK (loyalty_tier IN ...)` | Data validity | Invalid tier |
| `uq_actions_once` partial unique | Idempotency at DB level | Duplicate voucher/ refund if tool retried |
| `ON DELETE CASCADE` | Cleanup on reset | Orphan `actions` after `seed --reset` |

---

## 10. How to Inspect the DB (No Code Needed)

**Option A — `sqlite3` CLI (Windows):**

```powershell
sqlite3 backend/resolveai.db
.tables
.schema customers
SELECT * FROM customers;
SELECT pnr, action_type, status, metadata FROM actions ORDER BY created_at;
SELECT pnr, reason, requested_action, status FROM escalations;
SELECT pnr, role, substr(message,1,60) FROM conversations ORDER BY created_at;
```

**Option B — VS Code extension:** "SQLite Viewer" → open `resolveai.db`.

**Option C — API (after running backend):**

```powershell
curl http://localhost:8000/api/customers/SK4821X
curl http://localhost:8000/api/bookings/WL7742
curl http://localhost:8000/api/actions/WL7742
```

---

## 11. Decisions & Tradeoffs (Interview-Ready Answers)

| Question | Answer |
|----------|--------|
| **Why not Postgres?** | 3 customers + 4 bookings — no scale need. SQLite is file-based, zero-setup, reviewer opens it in seconds. Would switch to Postgres/Turso only if deploy proved file loss (assumptions.md L-03). |
| **Why duplicate `pnr` on children?** | API is PNR-centric; avoids JOIN on every panel read. `booking_id` remains the true FK — not denormalization for its own sake, just read convenience. |
| **Why not a `flights` table?** | No inventory needed for 6h demo — route/flight/status live on `bookings`. Adding `flights` would require joins with no interview value. Rebooking simulated in `actions.metadata`. |
| **How to prevent duplicate refunds?** | Two layers: (1) tool checks before INSERT (app), (2) partial unique index `uq_actions_once` (DB) — both enforce idempotency. |
| **How to handle Priya's return flight?** | As second booking `SK4821X-R` for same `customer_id=1` — demonstrates `1—N` naturally. Alternative (collapse into metadata) works but hides the relation. |

---

## 12. Glossary (For Non-Engineers)

| Term | Means |
|------|-------|
| **PK** | Primary Key — unique row id (`id` autoincrement) |
| **FK** | Foreign Key — points to another table's PK (`booking_id → bookings.id`) |
| **UNIQUE** | No two rows can have same value |
| **IDX** | Index — speeds up `WHERE pnr = ?` |
| **PNR** | Passenger Name Record / Booking Reference — the 7-char code you type (`SK4821X`) |
| **Seed** | Initial data inserted via `seed.py` |

---

> **Next:** After reading this, run `python backend/seed.py` then `sqlite3 backend/resolveai.db "SELECT * FROM customers;"` to see the truth the agent will enforce.

