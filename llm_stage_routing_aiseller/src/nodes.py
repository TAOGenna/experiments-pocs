"""
LangGraph node implementations for each stage specialist.

KEY DIFFERENCE FROM REACT:
- Each node does bounded, predictable work
- No open-ended tool loops
- Router decides which ONE node runs per turn
- State is explicit, not hidden in LLM context
"""

import json
import random
import uuid
from typing import Any

from langchain_openai import ChatOpenAI

from src.state import (
    ConversationState,
    Stage,
    NextAction,
    RouterDecision,
    Slots,
    CheckoutInfo,
)
from src.prompts import (
    ROUTER_MODEL,
    SPECIALIST_MODEL,
    ROUTER_SYSTEM_PROMPT,
    ROUTER_USER_TEMPLATE,
    GREETING_RESPONSES,
    DISCOVERY_SYSTEM_PROMPT,
    DISCOVERY_USER_TEMPLATE,
    QUERY_WRITER_SYSTEM_PROMPT,
    QUERY_WRITER_USER_TEMPLATE,
    PITCH_WRITER_SYSTEM_PROMPT,
    PITCH_WRITER_USER_TEMPLATE,
    PRODUCT_SELECTOR_SYSTEM_PROMPT,
    PRODUCT_SELECTOR_USER_TEMPLATE,
    CHECKOUT_SYSTEM_PROMPT,
    CHECKOUT_USER_TEMPLATE,
    CONFIRM_MESSAGE_TEMPLATE,
    SUPPORT_SYSTEM_PROMPT,
    SUPPORT_USER_TEMPLATE,
    MEMORY_UPDATE_SYSTEM_PROMPT,
    MEMORY_UPDATE_USER_TEMPLATE,
)
from src.tools import SearchQuery, product_search, get_products_by_ids
from src.cart_store import cart_store


# =============================================================================
# LLM HELPERS
# =============================================================================

def get_router_llm() -> ChatOpenAI:
    """Get the cheap model used for routing."""
    return ChatOpenAI(model=ROUTER_MODEL, temperature=0)


def get_specialist_llm() -> ChatOpenAI:
    """Get the model used for stage specialists."""
    return ChatOpenAI(model=SPECIALIST_MODEL, temperature=0.3)


def call_llm_json(llm: ChatOpenAI, system: str, user: str, state: ConversationState) -> tuple[dict, int]:
    """
    Call LLM and parse JSON response.
    Returns (parsed_dict, tokens_used).
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    
    response = llm.invoke(messages)
    
    # Extract token count if available
    tokens = 0
    if hasattr(response, "response_metadata"):
        usage = response.response_metadata.get("token_usage", {})
        tokens = usage.get("total_tokens", 0)
    
    # Parse JSON from response
    content = response.content.strip()
    # Handle markdown code blocks
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove first and last lines (code block markers)
        content = "\n".join(lines[1:-1])
    
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON from the response
        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            parsed = {}
    
    return parsed, tokens


def call_llm_text(llm: ChatOpenAI, system: str, user: str, state: ConversationState) -> tuple[str, int]:
    """
    Call LLM and return text response.
    Returns (text, tokens_used).
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    
    response = llm.invoke(messages)
    
    # Extract token count if available
    tokens = 0
    if hasattr(response, "response_metadata"):
        usage = response.response_metadata.get("token_usage", {})
        tokens = usage.get("total_tokens", 0)
    
    return response.content.strip(), tokens


# =============================================================================
# ROUTER NODE
# =============================================================================

def router_node(state: ConversationState) -> dict[str, Any]:
    """
    Router node - classifies user intent and picks a stage.
    
    This is a CHEAP LLM call that runs on every turn.
    It does NOT execute any tools or take actions.
    """
    llm = get_router_llm()
    
    # Build minimal context
    context = state.get_context_for_llm()
    user_prompt = ROUTER_USER_TEMPLATE.format(
        context=context,
        message=state.last_user_message
    )
    
    result, tokens = call_llm_json(llm, ROUTER_SYSTEM_PROMPT, user_prompt, state)
    
    # Parse router decision
    try:
        stage = Stage(result.get("stage", state.stage.value))
    except ValueError:
        stage = state.stage
    
    try:
        next_action = NextAction(result.get("next_action", "ASK_CLARIFY"))
    except ValueError:
        next_action = NextAction.ASK_CLARIFY
    
    decision = RouterDecision(
        stage=stage,
        need_search=result.get("need_search", False),
        slots_missing=result.get("slots_missing", []),
        next_action=next_action,
        escalate=result.get("escalate", False),
    )
    
    return {
        "router_decision": decision,
        "stage": stage,
        "total_tokens": state.total_tokens + tokens,
        "total_llm_calls": state.total_llm_calls + 1,
    }


# =============================================================================
# GREETING NODE
# =============================================================================

def greeting_node(state: ConversationState) -> dict[str, Any]:
    """
    Greeting node - simple response, no LLM needed.
    IMPORTANT: Preserves cart and checkout info in case of mid-conversation greeting.
    """
    response = random.choice(GREETING_RESPONSES)
    
    return {
        "last_assistant_response": response,
        "stage": Stage.DISCOVERY,  # Move to discovery after greeting
        "cart": list(state.cart),  # Preserve cart (in case user greets mid-conversation)
        "checkout": state.checkout,  # Preserve checkout info
        "slots": state.slots,  # Preserve slots
    }


# =============================================================================
# DISCOVERY NODE
# =============================================================================

def discovery_node(state: ConversationState) -> dict[str, Any]:
    """
    Discovery node - extract slots and ask ONE clarifying question.
    
    This specialist fills in user preferences.
    It does NOT call product_search.
    IMPORTANT: Preserves cart and checkout info.
    """
    llm = get_specialist_llm()
    
    user_prompt = DISCOVERY_USER_TEMPLATE.format(
        slots=state.slots.to_summary(),
        message=state.last_user_message
    )
    
    result, tokens = call_llm_json(llm, DISCOVERY_SYSTEM_PROMPT, user_prompt, state)
    
    # Update slots
    slot_updates = result.get("slot_updates", {})
    new_slots = Slots(
        category=slot_updates.get("category") or state.slots.category,
        keywords=(slot_updates.get("keywords") or []) + state.slots.keywords,
        budget_min=slot_updates.get("budget_min") or state.slots.budget_min,
        budget_max=slot_updates.get("budget_max") or state.slots.budget_max,
        color=slot_updates.get("color") or state.slots.color,
        size=slot_updates.get("size") or state.slots.size,
    )
    # Deduplicate keywords
    new_slots.keywords = list(set(new_slots.keywords))
    
    # Generate response
    question = result.get("question")
    if question:
        response = question
    else:
        # If no question, we have enough to search
        response = "Got it! Let me find some options for you..."
    
    # Determine next stage
    # If we have enough info (category or keywords), move to shortlist
    if new_slots.category or new_slots.keywords:
        next_stage = Stage.SHORTLIST
    else:
        next_stage = Stage.DISCOVERY
    
    return {
        "slots": new_slots,
        "last_assistant_response": response,
        "stage": next_stage,
        "cart": list(state.cart),  # CRITICAL: Preserve cart
        "checkout": state.checkout,  # Preserve checkout info
        "total_tokens": state.total_tokens + tokens,
        "total_llm_calls": state.total_llm_calls + 1,
    }


# =============================================================================
# SHORTLIST NODE
# =============================================================================

def shortlist_node(state: ConversationState) -> dict[str, Any]:
    """
    Shortlist node - bounded 3-step process:
    1. query_writer LLM → structured query
    2. product_search tool → results
    3. pitch_writer LLM → friendly message
    
    This is NOT a ReAct loop - the steps are fixed and predictable.
    IMPORTANT: Preserves cart when browsing new categories.
    """
    llm = get_specialist_llm()
    total_tokens = state.total_tokens
    llm_calls = state.total_llm_calls
    
    # Step 1: Generate search query - PASS USER MESSAGE for context
    query_prompt = QUERY_WRITER_USER_TEMPLATE.format(
        user_message=state.last_user_message,
        slots=state.slots.to_summary(),
        memory=state.memory_summary or "No previous context"
    )
    query_result, tokens1 = call_llm_json(llm, QUERY_WRITER_SYSTEM_PROMPT, query_prompt, state)
    total_tokens += tokens1
    llm_calls += 1
    
    # Build SearchQuery from LLM output - prioritize LLM's interpretation
    filters = query_result.get("filters", {})
    search_query = SearchQuery(
        category=query_result.get("category"),  # Use LLM's category first
        keywords=query_result.get("keywords", []) or state.slots.keywords,
        price_min=filters.get("price_min") or state.slots.budget_min,
        price_max=filters.get("price_max") or state.slots.budget_max,
        color=filters.get("color") or state.slots.color,
        size=filters.get("size") or state.slots.size,
        top_k=query_result.get("top_k", 5),
        sort=query_result.get("sort", "relevance"),
    )
    
    # Update slots with the new category if different
    new_slots = state.slots
    if query_result.get("category") and query_result.get("category") != state.slots.category:
        new_slots = Slots(
            category=query_result.get("category"),
            keywords=query_result.get("keywords", []),
            budget_min=state.slots.budget_min,
            budget_max=state.slots.budget_max,
            color=state.slots.color,
            size=state.slots.size,
        )
    
    # Step 2: Execute product search (deterministic, not a ReAct tool)
    products = product_search(search_query)
    search_calls = state.total_search_calls + 1
    
    if not products:
        # No products found - PRESERVE CART
        response = "I couldn't find any products matching your criteria. Could you try different preferences? Maybe a different price range or category?"
        return {
            "slots": new_slots,
            "last_assistant_response": response,
            "last_products": [],
            "cart": list(state.cart),  # CRITICAL: Preserve cart when browsing
            "checkout": state.checkout,  # Preserve checkout info
            "total_tokens": total_tokens,
            "total_llm_calls": llm_calls,
            "total_search_calls": search_calls,
            "stage": Stage.DISCOVERY,
        }
    
    # Step 3: Generate pitch message - include product IDs for selection
    products_text = "\n".join([
        f"- [{p.id}] {p.title} ({p.brand}): {p.price} {p.currency}, Color: {p.color}, Sizes: {', '.join(p.sizes) if p.sizes else 'N/A'}"
        for p in products
    ])
    
    pitch_prompt = PITCH_WRITER_USER_TEMPLATE.format(
        products=products_text,
        preferences=state.slots.to_summary()
    )
    response, tokens2 = call_llm_text(llm, PITCH_WRITER_SYSTEM_PROMPT, pitch_prompt, state)
    total_tokens += tokens2
    llm_calls += 1
    
    return {
        "slots": new_slots,
        "last_assistant_response": response,
        "last_products": [p.id for p in products],
        "cart": list(state.cart),  # CRITICAL: Preserve cart when browsing new categories
        "checkout": state.checkout,  # Preserve checkout info
        "total_tokens": total_tokens,
        "total_llm_calls": llm_calls,
        "total_search_calls": search_calls,
    }


# =============================================================================
# CHECKOUT NODE
# =============================================================================

def checkout_node(state: ConversationState) -> dict[str, Any]:
    """
    Checkout node - collect shipping and payment info.
    
    Uses LLM to parse product selection, then uses CartStore for reliable persistence.
    Also handles checkout info via CartStore.
    """
    llm = get_specialist_llm()
    total_tokens = state.total_tokens
    llm_calls = state.total_llm_calls
    
    # Product selection via LLM - bounded, predictable step
    newly_added_products = []
    
    if state.last_products:
        # Get product details for LLM context
        products_info = get_products_by_ids(state.last_products)
        
        # Format available products for LLM
        available_products = "\n".join([
            f"- [{p['id']}] {p['title']} ({p.get('brand', '')}) - {p.get('price', 0)} PEN"
            for p in products_info
        ])
        
        # Use LLM to parse which products user wants
        selector_system = PRODUCT_SELECTOR_SYSTEM_PROMPT.format(
            available_products=available_products
        )
        selector_user = PRODUCT_SELECTOR_USER_TEMPLATE.format(
            message=state.last_user_message
        )
        
        selection_result, tokens1 = call_llm_json(llm, selector_system, selector_user, state)
        total_tokens += tokens1
        llm_calls += 1
        
        # Add selected products to cart via CartStore (persistent!)
        selected_ids = selection_result.get("selected_product_ids", [])
        for pid in selected_ids:
            if pid in state.last_products:
                # Use CartStore for reliable persistence
                result = cart_store.add_item(pid)
                if result.get("success") and pid not in newly_added_products:
                    newly_added_products.append(pid)
    
    # Get cart from CartStore (single source of truth)
    cart_items = cart_store.get_cart()
    cart_details = cart_store.get_cart_details()
    cart_total = cart_store.get_total()
    
    # Build cart description for LLM
    cart_desc = "None selected"
    if cart_details:
        cart_desc = ", ".join([f"{item['title']} ({item['product_id']}) - {item['price']} PEN" for item in cart_details])
        cart_desc += f" | Total: {cart_total} PEN"
    
    # Get existing checkout info from CartStore
    checkout_info = cart_store.get_checkout_info()
    existing_checkout = f"name={checkout_info.get('name') or 'not provided'}; address={checkout_info.get('address') or 'not provided'}; payment={checkout_info.get('payment_method') or 'not provided'}"
    
    user_prompt = CHECKOUT_USER_TEMPLATE.format(
        checkout=existing_checkout,
        cart=cart_desc,
        message=state.last_user_message
    )
    
    result, tokens2 = call_llm_json(llm, CHECKOUT_SYSTEM_PROMPT, user_prompt, state)
    total_tokens += tokens2
    llm_calls += 1
    
    # Update checkout info via CartStore (persistent!)
    updates = result.get("checkout_updates", {})
    if any([updates.get("name"), updates.get("address"), updates.get("payment_method")]):
        cart_store.set_checkout_info(
            name=updates.get("name"),
            address=updates.get("address"),
            payment_method=updates.get("payment_method"),
        )
    
    # Get updated checkout info
    checkout_info = cart_store.get_checkout_info()
    is_complete = checkout_info.get("is_complete", False)
    missing_fields = checkout_info.get("missing_fields", [])
    
    # Also update state.checkout for compatibility
    new_checkout = CheckoutInfo(
        name=checkout_info.get("name"),
        address=checkout_info.get("address"),
        payment_method=checkout_info.get("payment_method"),
    )
    
    # Generate response
    question = result.get("question")
    
    # Determine next stage
    next_stage = Stage.CHECKOUT
    
    if is_complete and cart_items:
        response = "Perfect! I have all the information. Let me confirm your order..."
        next_stage = Stage.CONFIRM
    elif not cart_items:
        # No products selected yet
        response = "Great choice! To complete your order, I'll need some information. Could you please provide your name?"
        next_stage = Stage.CHECKOUT
    elif newly_added_products:
        # Just added products - acknowledge and ask for missing checkout info
        added_names = [p['title'] for p in get_products_by_ids(newly_added_products)]
        if missing_fields:
            if len(added_names) == 1:
                response = f"Great! I've added {added_names[0]} to your cart (total: {cart_total} PEN). Could you please provide your {missing_fields[0]}?"
            else:
                response = f"Great! I've added {', '.join(added_names)} to your cart (total: {cart_total} PEN). Could you please provide your {missing_fields[0]}?"
        else:
            response = f"Added {', '.join(added_names)} to your cart. Let me confirm your order..."
            next_stage = Stage.CONFIRM
    elif question:
        response = question
    else:
        # Fallback: ask for missing field
        if missing_fields:
            response = f"Could you please provide your {missing_fields[0]}?"
        else:
            response = "Let me confirm your order..."
            next_stage = Stage.CONFIRM
    
    return {
        "cart": cart_items,  # Sync state.cart with CartStore
        "checkout": new_checkout,
        "last_assistant_response": response,
        "stage": next_stage,
        "slots": state.slots,  # Preserve slots
        "last_products": state.last_products,  # Preserve for potential further selections
        "total_tokens": total_tokens,
        "total_llm_calls": llm_calls,
    }


# =============================================================================
# CONFIRM NODE
# =============================================================================

def confirm_node(state: ConversationState) -> dict[str, Any]:
    """
    Confirm node - generate order confirmation.
    
    Creates order ID and summary message with total.
    Uses CartStore as the single source of truth.
    """
    # Generate order ID
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    # Get cart and checkout from CartStore (single source of truth)
    cart_details = cart_store.get_cart_details()
    cart_total = cart_store.get_total()
    checkout_info = cart_store.get_checkout_info()
    
    items_text = "\n".join([
        f"  • {item['title']} - {item['price']} {item['currency']}"
        for item in cart_details
    ]) if cart_details else "  • Your selected product"
    
    # Add total to items
    if cart_details:
        items_text += f"\n  ─────────────\n  Total: {cart_total} PEN"
    
    # Get checkout info from CartStore (properly normalized payment method)
    name = checkout_info.get("name") or state.checkout.name or "Customer"
    address = checkout_info.get("address") or state.checkout.address or "Address pending"
    payment_method = checkout_info.get("payment_method") or state.checkout.payment_method or "To be confirmed"
    
    # Format confirmation message
    response = CONFIRM_MESSAGE_TEMPLATE.format(
        order_id=order_id,
        items=items_text,
        name=name,
        address=address,
        payment_method=payment_method,
    )
    
    # Clear CartStore for next order
    cart_store.full_reset()
    
    return {
        "order_id": order_id,
        "last_assistant_response": response,
        "stage": Stage.GREETING,  # Reset for new conversation
        # Reset state for new order
        "cart": [],
        "slots": Slots(),
        "checkout": CheckoutInfo(),
    }


# =============================================================================
# SUPPORT NODE
# =============================================================================

def support_node(state: ConversationState) -> dict[str, Any]:
    """
    Support node - handle out-of-scope queries and cart inquiries.
    Uses CartStore as the single source of truth for cart.
    """
    llm = get_specialist_llm()
    
    # Get cart from CartStore (single source of truth)
    cart_desc = cart_store.get_cart_summary()
    
    user_prompt = SUPPORT_USER_TEMPLATE.format(
        context=state.get_context_for_llm(),
        cart=cart_desc,
        message=state.last_user_message
    )
    
    response, tokens = call_llm_text(llm, SUPPORT_SYSTEM_PROMPT, user_prompt, state)
    
    # Sync state.cart with CartStore
    cart_items = cart_store.get_cart()
    
    return {
        "last_assistant_response": response,
        "cart": cart_items,  # Sync with CartStore
        "checkout": state.checkout,  # Preserve checkout info
        "slots": state.slots,  # Preserve slots
        "last_products": state.last_products,  # Preserve last shown products
        "total_tokens": state.total_tokens + tokens,
        "total_llm_calls": state.total_llm_calls + 1,
    }


# =============================================================================
# MEMORY UPDATE NODE
# =============================================================================

def memory_update_node(state: ConversationState) -> dict[str, Any]:
    """
    Memory update node - keep rolling summary short.
    
    This runs after each specialist to maintain concise context.
    """
    # For very short conversations, just append
    if state.turn_id < 3 or not state.memory_summary:
        new_summary = f"{state.memory_summary}\nTurn {state.turn_id}: User asked about {state.slots.category or 'products'}. "
        if state.cart:
            new_summary += f"Cart has {len(state.cart)} item(s). "
        return {
            "memory_summary": new_summary.strip()[-500:],  # Keep it bounded
            "turn_id": state.turn_id + 1,
        }
    
    # For longer conversations, use LLM to summarize
    llm = get_router_llm()  # Use cheap model
    
    user_prompt = MEMORY_UPDATE_USER_TEMPLATE.format(
        previous_summary=state.memory_summary,
        user_message=state.last_user_message,
        assistant_response=state.last_assistant_response[:200],  # Truncate
    )
    
    new_summary, tokens = call_llm_text(llm, MEMORY_UPDATE_SYSTEM_PROMPT, user_prompt, state)
    
    return {
        "memory_summary": new_summary[:500],  # Keep bounded
        "turn_id": state.turn_id + 1,
        "total_tokens": state.total_tokens + tokens,
        "total_llm_calls": state.total_llm_calls + 1,
    }
