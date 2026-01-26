# Comparison Report: Headphones Multi Purchase

**Date:** 2026-01-25 19:06:15

## 🏆 **Stage-Routing wins** (more efficient)

---

## Overall Results

| Mode | Status | Score | Tokens | LLM Calls | Tool Calls |
|------|--------|-------|--------|-----------|------------|
| Stage-Routing | ✅ PASS | 100% | **10,944** | 26 | 2 |
| ReAct | ✅ PASS | 100% | **29,594** | 15 | 0 |

**Token Efficiency:** Stage-Routing used **63% fewer tokens**

---

## Judge Analysis

### Stage-Routing

> The chatbot successfully added the correct items to the cart, confirmed the order, and provided accurate checkout information. All expected outcomes were achieved, including the correct total and order confirmation.

### ReAct

> The chatbot successfully added the correct items to the cart, calculated the total accurately, and confirmed the order with the correct checkout information. All expected outcomes were achieved without any discrepancies.

---

## Detailed Comparison

| Metric | Stage-Routing | ReAct |
|--------|---------------|-------|
| Cart Correct | ✅ | ✅ |
| Total Correct | ✅ | ✅ |
| Order Confirmed | ✅ | ✅ |
| Checkout Correct | ✅ | ✅ |
| Turns | 8 | 8 |
| Retries | 0 | 0 |

---

## Expected Outcome

- **Cart Items:** Sport Earbuds, Studio Monitor, Budget Wireless
- **Total:** 938.0 PEN
- **Order Confirmed:** Yes

---

## Actual Results

### Stage-Routing
- **Cart Found:** Budget Wireless Earbuds, Sport Earbuds Waterproof, Studio Monitor Headphones
- **Total Found:** 938.0 PEN

### ReAct
- **Cart Found:** Sport Earbuds Waterproof, Studio Monitor Headphones, Budget Wireless Earbuds
- **Total Found:** 938 PEN

---

## Fix Applied (vs Previous Run)

**Previous failure:** Stage-Routing scored 25% with cart containing 5 items (Wireless Pro, Budget Wireless, Gaming Headset, Sport Earbuds, Studio Monitor) and total of 1716 PEN instead of the expected 3 items and 938 PEN.

**Root cause:** The `checkout_node` used naive string matching for product selection:
- `"both" in user_msg_lower` triggered adding ALL products from `last_products` (all 5 headphones shown)
- Word matching (`if word in user_msg_lower`) was too aggressive — any word >3 chars from product titles would match

**Solution:** Replaced naive string matching with an LLM-based product selector:
1. Added `PRODUCT_SELECTOR_SYSTEM_PROMPT` — a focused prompt that parses which specific products the user explicitly requested
2. Updated `checkout_node` to call this LLM instead of doing regex/string matching

**Trade-off:** Added ~1,400 tokens per checkout turn, but achieved 100% accuracy while still using 63% fewer tokens than ReAct.

