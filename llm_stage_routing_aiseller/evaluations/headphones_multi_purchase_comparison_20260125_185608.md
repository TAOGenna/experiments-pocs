# Comparison Report: Headphones Multi Purchase

**Date:** 2026-01-25 18:56:08

## 🏆 **ReAct wins**

---

## Overall Results

| Mode | Status | Score | Tokens | LLM Calls | Tool Calls |
|------|--------|-------|--------|-----------|------------|
| Stage-Routing | ❌ FAIL | 25% | **9,585** | 22 | 2 |
| ReAct | ✅ PASS | 100% | **33,549** | 16 | 0 |

**Token Efficiency:** Stage-Routing used **71% fewer tokens**

---

## Judge Analysis

### Stage-Routing

> The evaluation failed because the cart contained items that were not part of the expected outcomes, and the total amount was significantly higher than expected. Additionally, the checkout information did not match the expected details.

### ReAct

> The chatbot successfully added the correct items to the cart, calculated the total accurately, and confirmed the order with the correct checkout information. All expected outcomes were achieved without any discrepancies.

---

## Detailed Comparison

| Metric | Stage-Routing | ReAct |
|--------|---------------|-------|
| Cart Correct | ❌ | ✅ |
| Total Correct | ❌ | ✅ |
| Order Confirmed | ✅ | ✅ |
| Checkout Correct | ❌ | ✅ |
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
- **Cart Found:** Wireless Pro Headphones, Budget Wireless Earbuds, Gaming Headset RGB, Sport Earbuds Waterproof, Studio Monitor Headphones
- **Total Found:** 1716.0 PEN

### ReAct
- **Cart Found:** Sport Earbuds Waterproof, Studio Monitor Headphones, Budget Wireless Earbuds
- **Total Found:** 938 PEN

---

## Issues Noted

### Stage-Routing
- Cart contains items not specified in expected outcomes (Wireless Pro Headphones, Gaming Headset RGB).
- Total amount does not match expected total of 938.0 PEN.
- Checkout info does not match expected name, address, or payment method.

