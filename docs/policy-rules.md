# Policy Rules — Quick Reference (for interviewer)

**Source:** Assignment Data Pack (authoritative). `policy_engine.py:1` is the single implementation.

| Delay | Meal ₹500 | Lounge | Hotel | Note |
|-------|-----------|--------|-------|------|
| `<3h` (2h, 2.99h) | ✓ | ✗ | ✗ | SR-02 |
| `=3h` | — | — | — | **Unspecified — no entitlement** (SR-02a) |
| `>3h and ≤5h` (3.01h, 4h, 5h) | ✓ | ✓ | ✗ | SR-03 |
| `>5h` (5.01h, 6h) | ✓ | ✓ | ✓ `delayed_hours_only` | SR-04 (not full night) |

* `None` (Cancelled/Unaffected) → no delay compensation.

| Scenario | Rule |
|----------|------|
| **Cancellation (airline, Operational reasons)** | Free rebook within 24h **OR** full refund (choice) → 7 days original method only (SR-01/05). `SK4821X` eligible. |
| **Fare waiver** | Agent ≤₹1,500 waive; `>1500` → supervisor (`1500.01` escalates, `2000` escalates per SR-06). |
| **Loyalty Gold/Platinum** | Priority rebooking only, **no extra** voucher/hotel/upgrade (SR-07). |
| **Unsupported** | Business upgrade, full-night hotel, alternate refund method → **escalate** (no invention). |

**Determinism:** `evaluate_delay`, `evaluate_cancellation`, `evaluate_fare_difference` are pure Python — tested without LLM (`pytest -v` 28 policy tests).
