## Cursor prompt

Build a **self-contained POC** (not production) of a “catalog seller chatbot” that runs in a **terminal loop** (user types, bot replies). The goal is to demonstrate **stage routing + stage specialists** to avoid a giant ReAct prompt. Use **LangGraph** as the orchestration/state machine. Use a **local JSON file** as the product catalog and implement a `product_search` tool that searches that JSON.

### High-level behavior
The assistant should guide a user from greeting → discovering needs → showing product options → checkout info → order confirmation. This is a POC, so we can keep checkout simple (collect name + address + payment method).

### Constraints (important)
- Do **NOT** implement an open-ended ReAct agent loop.
- Each user turn must do:
  1) **Router** LLM call (cheap) that returns strict JSON
  2) **Exactly one** stage specialist path (bounded). The only exception: in SHORTLIST stage, it’s okay to do `query_writer` LLM → `product_search` tool → `pitch_writer` LLM (still bounded).
- Keep prompts small and stage-specific.
- Maintain an explicit `ConversationState` object (in code) and send only minimal context to the model (state summary + last user message).
- Implement basic “rolling memory summary” that stays short (e.g., 5–10 lines), updated after each turn.
- Provide simple logging: tokens used per call if available, and which stage ran.

### Tech stack
- Python 3.11+
- `langgraph`, `langchain` (or `langchain-openai` depending on setup)
- Optional: `langsmith` tracing if env vars present, but code must run without it.
- Use `.env` for API keys (don’t hardcode).
- LLM provider: assume OpenAI-compatible chat model; default model names can be placeholders (e.g., `"gpt-4o-mini"` for router, `"gpt-4o-mini"` or `"gpt-4o"` for writer). Make it easy to change via constants.

### Repo layout
Create:
- `README.md` with setup + run instructions
- `pyproject.toml` (or `requirements.txt`) minimal dependencies
- `main.py` to run the terminal chat loop
- `catalog.json` mock product catalog created by the code if missing
- `src/` package (optional) for graph/state/tools/prompts

### Mock catalog
Create a small JSON catalog (20–40 items) if `catalog.json` doesn’t exist.
Each product should have:
```json
{
  "id": "p_001",
  "title": "Running Shoes X",
  "category": "shoes",
  "brand": "Acme",
  "price": 199.0,
  "currency": "PEN",
  "color": "black",
  "size": ["40","41","42"],
  "tags": ["running","sport"],
  "in_stock": true,
  "description": "..."
}
```
Include 3–5 categories (shoes, headphones, backpacks, jackets, etc.), varied price ranges.

### State machine stages
Use these stages (enum strings):
- `GREETING`
- `DISCOVERY` (slot filling)
- `SHORTLIST` (search + show options)
- `CHECKOUT` (collect shipping/payment)
- `CONFIRM` (final confirmation + “order created”)
- `SUPPORT` (fallback for complaints / out-of-scope)

State object must include:
- `stage`
- `slots`: `category`, `keywords`, `budget_min`, `budget_max`, `color`, `size`, etc.
- `cart`: list of product ids
- `last_products`: last shown product ids
- `checkout`: `name`, `address`, `payment_method`
- `memory_summary`: short string
- `turn_id`

### Routing logic (Router LLM)
Implement a router node that takes:
- last user message
- current `stage`
- compact slot summary (current filled vs missing)
- compact memory summary

Router outputs STRICT JSON matching this schema:
```json
{
  "stage": "DISCOVERY|SHORTLIST|CHECKOUT|CONFIRM|SUPPORT|GREETING",
  "need_search": true|false,
  "slots_missing": ["budget_max","color", "..."],
  "next_action": "ASK_CLARIFY|SHOW_OPTIONS|COLLECT_CHECKOUT|CONFIRM_ORDER|HANDLE_SUPPORT",
  "escalate": false
}
```
For this POC, `escalate` can exist but do nothing (keep always false unless you want to route to a stronger model for SUPPORT).

Router prompt must:
- be short
- include stage definitions
- include a few examples
- enforce “JSON only”

### Stage specialists
Implement each as a LangGraph node.

#### GREETING node (no LLM or small LLM)
If conversation starts or user says hi, respond with a short greeting + ask what they’re looking for.

#### DISCOVERY specialist (slot filler)
Goal: fill slots enough to do search. It must output JSON:
```json
{
  "slot_updates": {...},
  "question": "string or null"
}
```
Rules:
- If key slot missing (category/keywords or budget), ask exactly ONE question.
- Do not call product_search here.
- Update state with extracted info.

#### SHORTLIST specialist
Steps:
1) `query_writer` LLM produces a structured query JSON:
```json
{
  "category": "string|null",
  "keywords": ["..."],
  "filters": {"price_min": 0, "price_max": 200, "color": "black", "size": "42"},
  "top_k": 5,
  "sort": "relevance|price_asc|price_desc"
}
```
2) `product_search(query)` searches `catalog.json`:
   - Filter by in_stock
   - Apply price range and attribute filters when present
   - Do simple relevance scoring: keyword match in title/tags/description (e.g., count matches)
   - Return top_k products with fields needed for display (id,title,price,brand,color,sizes,short_desc)
3) `pitch_writer` LLM creates a WhatsApp-style message (but in terminal) presenting 3–5 options with bullet points + a question (“Which one do you like?”). Keep it concise.

Also update:
- `last_products` = returned product ids
- optionally add chosen product to `cart` if user indicates selection later

#### CHECKOUT specialist
Extract checkout info from user message into JSON:
```json
{
  "checkout_updates": {"name": "...", "address": "...", "payment_method": "cash|card|transfer"},
  "question": "string or null"
}
```
If missing any required field, ask exactly one question.
When complete, move to CONFIRM.

#### CONFIRM specialist
If user confirms, simulate order creation:
- generate `order_id` (e.g. uuid4 short)
- print a confirmation message with order summary (selected product + checkout info)
- reset stage to GREETING or end conversation.

#### SUPPORT specialist
Short helpful response: ask user to rephrase or indicate they want a human.

### Graph wiring (LangGraph)
- Use a single `StateGraph(ConversationState)` with nodes:
  - `router`
  - `greeting`
  - `discovery`
  - `shortlist`
  - `checkout`
  - `confirm`
  - `support`
  - `memory_update` (optional node to keep summary short)
- Conditional edges from `router` to the stage node based on `route.stage`.
- After each stage node, go to `memory_update`, then back to `router` for next user message (or end).

### Terminal loop
- Start with empty state, stage=GREETING.
- Repeatedly:
  - read input
  - run graph for one “turn” (router + one specialist)
  - print assistant reply
  - show debug line: `[stage=..., need_search=..., tokens=...]`
- Add `exit` command to quit.

### Evaluation hooks (POC-level)
Add simple counters:
- total tokens (if available)
- number of product_search calls
- number of LLM calls
Print totals on exit.

### Deliverables
- working code that runs with `python main.py`
- clear README
- all prompts in one place (e.g., `prompts.py`) for easy editing
- code should be readable, small, and heavily commented to explain why this is not ReAct and how the routing/state differs.

Start coding now, generating the full file contents.

---

If Cursor asks for model/provider specifics, assume OpenAI-compatible and use environment variable `OPENAI_API_KEY`. If LangSmith is used, guard it behind env vars so it doesn’t break execution.
