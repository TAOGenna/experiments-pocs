"""
ReAct Agent - Single Agent with One Giant Prompt

This is the traditional ReAct approach where ONE agent handles everything.
The prompt is necessarily large because it must cover all scenarios.

KEY PROBLEMS THIS DEMONSTRATES:
1. Giant prompt that tries to do everything
2. Open-ended tool loop (unpredictable number of LLM calls)
3. No explicit state machine (agent must track state in context)
4. All logic packed into prompt engineering

Compare this to src/ where:
- Router picks ONE specialist per turn
- Each specialist has a focused, small prompt
- Bounded execution (no open-ended loops)
- Explicit state in code, not LLM context
"""

import json
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src_react.state import ReActState
from src_react.tools import REACT_TOOLS


# =============================================================================
# TOKEN TRACKING CALLBACK
# =============================================================================

class TokenTrackingCallback(BaseCallbackHandler):
    """Callback to track token usage across LLM calls."""
    
    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.llm_calls = 0
    
    def on_llm_end(self, response, **kwargs):
        """Called when LLM finishes. Extract token usage."""
        self.llm_calls += 1
        
        # Try to extract token usage from response
        if hasattr(response, "llm_output") and response.llm_output:
            usage = response.llm_output.get("token_usage", {})
            self.total_tokens += usage.get("total_tokens", 0)
            self.prompt_tokens += usage.get("prompt_tokens", 0)
            self.completion_tokens += usage.get("completion_tokens", 0)
        
        # Also check generations for usage info
        for gen_list in response.generations:
            for gen in gen_list:
                if hasattr(gen, "generation_info") and gen.generation_info:
                    usage = gen.generation_info.get("usage", {})
                    if usage and self.total_tokens == 0:
                        self.total_tokens += usage.get("total_tokens", 0)
                        self.prompt_tokens += usage.get("prompt_tokens", 0)
                        self.completion_tokens += usage.get("completion_tokens", 0)
    
    def reset(self):
        """Reset counters for a new turn."""
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.llm_calls = 0


# =============================================================================
# MODEL CONFIGURATION
# =============================================================================

# Using the same model as stage-routing for fair comparison
REACT_MODEL = "gpt-4o-mini"


# =============================================================================
# THE GIANT PROMPT
# =============================================================================
# This is the key difference: ONE prompt that must handle EVERYTHING.
# Compare this to the focused prompts in src/prompts.py
# =============================================================================

REACT_SYSTEM_PROMPT = """You are a friendly and helpful shopping assistant for an online catalog store.
Your job is to help customers find products, guide them through selection, and complete their purchase.

## PRODUCT CATALOG
We sell: shoes, headphones, backpacks, jackets, and watches.
All prices are in PEN (Peruvian Soles).

## YOUR TOOLS - YOU MUST ALWAYS USE THEM!
1. search_products - Search the catalog with filters (category, keywords, price range)
2. add_to_cart - Add ONE product to cart (call ONCE per product with product ID like "p_001")
3. remove_from_cart - Remove a product from cart
4. get_cart - Show current cart contents and total (no arguments needed)
5. update_checkout_info - Store name, address, and payment method
6. get_checkout_info - Check what checkout info has been collected
7. confirm_order - Finalize the order (no arguments - reads from stored cart/checkout)

## MANDATORY TOOL USAGE - THIS IS CRITICAL!

**NEVER respond without using tools when actions are needed!**

- User asks for products → MUST call search_products
- User selects a product → MUST call add_to_cart with the product_id
- User provides name/address/payment → MUST call update_checkout_info
- User confirms order → MUST call confirm_order
- User asks "what's in my cart" → MUST call get_cart

DO NOT just acknowledge actions - ACTUALLY CALL THE TOOLS!

## PRODUCT ID REFERENCE (memorize these for common requests)
Shoes:
- p_001: Running Shoes Pro X (299 PEN)
- p_004: Sprint Lite Running Shoes (199 PEN)
- p_002: Urban Walker Sneakers (189 PEN)

Backpacks:
- p_201: Laptop Backpack Pro (189 PEN)
- p_202: Hiking Backpack 40L (320 PEN)
- p_203: Urban Daily Backpack (129 PEN)
- p_207: Urban Commuter Backpack (189 PEN) ← NOTE: Different from Urban Daily!

Jackets:
- p_301: Rain Jacket Waterproof (280 PEN)
- p_302: Winter Down Jacket (550 PEN)

## PRODUCT SELECTION - EXACT MATCHING IS CRITICAL!

When user says a product name, match it EXACTLY:
- "Sprint Lite" → p_004 (NOT any other shoe)
- "Urban Commuter" → p_207 (NOT p_203 Urban Daily!)
- "Urban Daily" → p_203 (different product!)
- "Rain Jacket Waterproof" or "waterproof rain jacket" → p_301
- "first one", "second one" → use position from last search results

IMPORTANT: "Urban Commuter" and "Urban Daily" are DIFFERENT products!
- Urban Commuter Backpack (p_207) = 189 PEN, black, 22L
- Urban Daily Backpack (p_203) = 129 PEN, navy, 20L

## CHECKOUT INFO - USE EXACT CUSTOMER VALUES

When customer provides checkout info:
1. IMMEDIATELY call update_checkout_info with their EXACT values
2. Payment method mapping:
   * "transfer", "transferencia", "bank transfer" → payment_method="transfer"
   * "card", "tarjeta", "credit card" → payment_method="card"
   * "cash", "efectivo" → payment_method="cash"
3. DO NOT modify or guess - use EXACTLY what they said

Example: "Roberto Diaz, Calle Sol 890, transfer"
→ call update_checkout_info(name="Roberto Diaz", address="Calle Sol 890", payment_method="transfer")

## ORDER CONFIRMATION

When user says "yes", "confirm", "place order":
1. MUST call confirm_order tool (no arguments)
2. The tool returns order ID and details
3. Report the order ID to the user

## MULTI-CATEGORY SHOPPING

- Users can buy from MULTIPLE categories in ONE order
- Cart is PERSISTENT - items stay until removed or order confirmed
- When searching new category, existing cart items remain
- Example flow: add shoes → browse backpacks → add backpack → cart has BOTH

## RESPONSE FORMAT

- Be conversational and helpful
- Show prices in PEN
- Always mention product IDs when presenting options
- After adding to cart, call get_cart and mention the updated total

REMEMBER:
1. ALWAYS call tools - never just describe what you would do
2. Match product names EXACTLY to find correct product IDs
3. "Urban Commuter" ≠ "Urban Daily" - they are different products!
4. Use EXACT customer values for checkout info
5. Call confirm_order when user confirms (tool takes no arguments)"""


# =============================================================================
# AGENT SETUP
# =============================================================================

class ReActAgent:
    """
    ReAct agent that uses a single prompt and tool loop.
    
    This contrasts with the stage-routing approach where:
    - Router picks ONE specialist per turn
    - Each specialist has bounded execution
    - No open-ended tool loops
    """
    
    def __init__(self):
        """Initialize the ReAct agent with tools."""
        # Token tracking callback
        self.token_callback = TokenTrackingCallback()
        
        self.llm = ChatOpenAI(
            model=REACT_MODEL, 
            temperature=0.3,
            callbacks=[self.token_callback],
        )
        
        # Create prompt template with system message
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", REACT_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # Create the ReAct agent using langgraph prebuilt
        # This creates an agent that can use tools in a loop
        self.agent = create_react_agent(
            self.llm,
            REACT_TOOLS,
            prompt=self.prompt,
        )
    
    def run(self, user_input: str, state: ReActState) -> tuple[str, dict]:
        """
        Run one turn of the conversation.
        
        This is the key difference from stage-routing:
        - Here, the agent can call multiple tools in a loop
        - The number of LLM calls is unpredictable
        - All decision-making is in the prompt + tool loop
        
        Args:
            user_input: The user's message
            state: Current conversation state
            
        Returns:
            Tuple of (response_text, usage_stats)
        """
        # Reset token tracking for this turn
        self.token_callback.reset()
        
        # Build message history for context
        messages = []
        
        for msg in state.messages:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))
        
        # Add state context to the user message
        state_context = self._build_state_context(state)
        full_message = f"{user_input}\n\n[Current state: {state_context}]"
        messages.append(HumanMessage(content=full_message))
        
        try:
            # Run the agent
            result = self.agent.invoke({"messages": messages})
            
            # Extract the final response
            response = ""
            tool_calls = 0
            
            for msg in result.get("messages", []):
                if hasattr(msg, "content") and msg.content:
                    # Count different message types
                    if isinstance(msg, AIMessage):
                        if msg.content and not hasattr(msg, "tool_calls"):
                            response = msg.content
                        elif hasattr(msg, "tool_calls") and msg.tool_calls:
                            tool_calls += len(msg.tool_calls)
            
            # If no response found, use the last AI message
            if not response:
                for msg in reversed(result.get("messages", [])):
                    if isinstance(msg, AIMessage) and msg.content:
                        response = msg.content
                        break
            
            if not response:
                response = "I'm sorry, I couldn't process that. Could you try again?"
            
            # Get stats from callback
            stats = {
                "llm_calls": self.token_callback.llm_calls or 1,
                "tool_calls": tool_calls,
                "tokens": self.token_callback.total_tokens,
            }
            
            return response, stats
            
        except Exception as e:
            return f"I encountered an error: {str(e)}. Please try again.", {
                "llm_calls": 1,
                "tool_calls": 0,
                "tokens": 0,
            }
    
    def _build_state_context(self, state: ReActState) -> str:
        """Build a context string from current state using CartStore."""
        from src.cart_store import cart_store
        
        parts = []
        
        # Get cart from CartStore (single source of truth)
        cart_summary = cart_store.get_cart_summary()
        if cart_summary != "Cart is empty":
            parts.append(f"Cart: {cart_summary}")
        
        # Get checkout info from CartStore
        checkout_info = cart_store.get_checkout_info()
        checkout_parts = []
        if checkout_info.get("name"):
            checkout_parts.append(f"name={checkout_info['name']}")
        if checkout_info.get("address"):
            checkout_parts.append(f"address={checkout_info['address']}")
        if checkout_info.get("payment_method"):
            checkout_parts.append(f"payment={checkout_info['payment_method']}")
        if checkout_parts:
            parts.append(f"Checkout: {', '.join(checkout_parts)}")
        
        if state.preferences:
            prefs = ", ".join(f"{k}={v}" for k, v in state.preferences.items() if v)
            if prefs:
                parts.append(f"Preferences: {prefs}")
        
        return "; ".join(parts) if parts else "No state yet"


# =============================================================================
# AGENT RUNNER
# =============================================================================

# Singleton agent instance
_react_agent: ReActAgent | None = None


def get_react_agent() -> ReActAgent:
    """Get or create the ReAct agent singleton."""
    global _react_agent
    if _react_agent is None:
        _react_agent = ReActAgent()
    return _react_agent


def run_react_turn(state: ReActState, user_message: str) -> ReActState:
    """
    Run one turn of the ReAct agent.
    
    This is comparable to run_turn() in src/graph.py, but:
    - Uses an open-ended tool loop instead of bounded execution
    - All logic is in the single giant prompt
    - Number of LLM calls is unpredictable
    
    Cart state is now handled by CartStore, not by parsing responses.
    
    Args:
        state: Current conversation state
        user_message: User's input
        
    Returns:
        Updated state with assistant response
    """
    agent = get_react_agent()
    
    # Add user message to history
    state.add_user_message(user_message)
    
    # Run the agent
    response, stats = agent.run(user_message, state)
    
    # Update state
    state.add_assistant_message(response)
    state.turn_id += 1
    state.total_llm_calls += stats.get("llm_calls", 1)
    state.total_tool_calls += stats.get("tool_calls", 0)
    state.total_tokens += stats.get("tokens", 0)
    
    # Sync state with CartStore (single source of truth)
    # This keeps state.cart in sync for compatibility
    from src.cart_store import cart_store
    state.cart = cart_store.get_cart()
    
    checkout_info = cart_store.get_checkout_info()
    state.checkout_info = {
        "name": checkout_info.get("name"),
        "address": checkout_info.get("address"),
        "payment_method": checkout_info.get("payment_method"),
    }
    
    # Detect order confirmation from response
    if "ORD-" in response:
        import re
        match = re.search(r'ORD-[A-Z0-9]+', response)
        if match:
            state.order_id = match.group()
    
    return state
