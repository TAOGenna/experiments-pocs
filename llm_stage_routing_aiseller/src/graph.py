"""
LangGraph wiring - the state machine that orchestrates the chatbot.

KEY ARCHITECTURAL DECISION:
This uses a StateGraph with explicit stage routing, NOT a ReAct agent.

Flow per turn:
1. User message → update state
2. Router node → classify intent, pick stage
3. Conditional edge → route to ONE specialist
4. Specialist node → do bounded work, update state
5. Memory update node → keep summary short
6. END → return to terminal loop for next user message

This is predictable: each turn is Router → ONE Specialist → Memory Update.
No open-ended tool loops.
"""

from typing import Annotated, Literal
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END

from src.state import ConversationState, Stage, Slots, CheckoutInfo
from src.nodes import (
    router_node,
    greeting_node,
    discovery_node,
    shortlist_node,
    checkout_node,
    confirm_node,
    support_node,
    memory_update_node,
)


# =============================================================================
# LANGGRAPH STATE TYPE
# We need to define this for LangGraph's type system
# =============================================================================

class GraphState(TypedDict, total=False):
    """
    LangGraph state type.
    
    This mirrors ConversationState but as a TypedDict for LangGraph.
    """
    stage: Stage
    slots: Slots
    cart: list[str]
    last_products: list[str]
    checkout: CheckoutInfo
    memory_summary: str
    turn_id: int
    last_user_message: str
    last_assistant_response: str
    router_decision: dict
    order_id: str | None
    total_tokens: int
    total_llm_calls: int
    total_search_calls: int


# =============================================================================
# ROUTING FUNCTION
# =============================================================================

def route_by_stage(state: ConversationState) -> str:
    """
    Route to the appropriate specialist based on router's decision.
    
    This is the conditional edge function that picks ONE specialist.
    """
    if state.router_decision is None:
        return "greeting"
    
    stage = state.router_decision.stage
    
    if stage == Stage.GREETING:
        return "greeting"
    elif stage == Stage.DISCOVERY:
        return "discovery"
    elif stage == Stage.SHORTLIST:
        return "shortlist"
    elif stage == Stage.CHECKOUT:
        return "checkout"
    elif stage == Stage.CONFIRM:
        return "confirm"
    elif stage == Stage.SUPPORT:
        return "support"
    else:
        return "support"  # Fallback


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def build_graph() -> StateGraph:
    """
    Build the LangGraph state machine.
    
    Graph structure:
        router → conditional → [greeting|discovery|shortlist|checkout|confirm|support]
                                    ↓
                              memory_update
                                    ↓
                                   END
    """
    # Create state graph
    # We use a factory function to create fresh ConversationState
    graph = StateGraph(ConversationState)
    
    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("greeting", greeting_node)
    graph.add_node("discovery", discovery_node)
    graph.add_node("shortlist", shortlist_node)
    graph.add_node("checkout", checkout_node)
    graph.add_node("confirm", confirm_node)
    graph.add_node("support", support_node)
    graph.add_node("memory_update", memory_update_node)
    
    # Set entry point
    graph.set_entry_point("router")
    
    # Add conditional edges from router to specialists
    graph.add_conditional_edges(
        "router",
        route_by_stage,
        {
            "greeting": "greeting",
            "discovery": "discovery",
            "shortlist": "shortlist",
            "checkout": "checkout",
            "confirm": "confirm",
            "support": "support",
        }
    )
    
    # All specialists go to memory_update
    for node in ["greeting", "discovery", "shortlist", "checkout", "confirm", "support"]:
        graph.add_edge(node, "memory_update")
    
    # Memory update goes to END (return to terminal loop)
    graph.add_edge("memory_update", END)
    
    return graph


def compile_graph():
    """
    Compile the graph for execution.
    """
    graph = build_graph()
    return graph.compile()


# Create the compiled graph (singleton)
chatbot_graph = compile_graph()


def run_turn(state: ConversationState, user_message: str) -> ConversationState:
    """
    Run one turn of the conversation.
    
    This is the main entry point called by the terminal loop.
    
    Args:
        state: Current conversation state
        user_message: User's input
        
    Returns:
        Updated conversation state with assistant response
    """
    # Update state with user message
    state.last_user_message = user_message
    
    # ==========================================================================
    # LANGSMITH TRACING CONFIG
    # ==========================================================================
    # When LANGCHAIN_TRACING_V2=true, all LLM calls are traced automatically.
    # We add run_name and tags to make traces easier to navigate in LangSmith.
    # ==========================================================================
    config = {
        "run_name": f"turn-{state.turn_id}-{state.stage.value}",
        "tags": ["catalog-chatbot", f"stage:{state.stage.value}", f"turn:{state.turn_id}"],
        "metadata": {
            "turn_id": state.turn_id,
            "stage": state.stage.value,
            "user_message_preview": user_message[:50] if user_message else "",
            "cart_size": len(state.cart),
            "slots_filled": state.slots.to_summary(),
        }
    }
    
    # Run the graph for one turn
    # The graph will: router → specialist → memory_update → END
    result = chatbot_graph.invoke(state, config=config)
    
    # The result is the updated state
    # LangGraph returns a dict, so we need to update our state object
    if isinstance(result, dict):
        # Update state from result dict
        for key, value in result.items():
            if hasattr(state, key) and value is not None:
                setattr(state, key, value)
    
    return state
