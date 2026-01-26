"""
ConversationState - The explicit state object for the chatbot.

This is a key difference from ReAct: we maintain explicit state in code,
not just in the LLM's context window. This gives us:
- Predictable state transitions
- Minimal context sent to LLM (just summaries)
- Easy debugging and logging
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Stage(str, Enum):
    """
    Explicit stages in the conversation flow.
    Each stage has a dedicated specialist node.
    """
    GREETING = "GREETING"
    DISCOVERY = "DISCOVERY"      # Slot filling - collect preferences
    SHORTLIST = "SHORTLIST"      # Search + show product options
    CHECKOUT = "CHECKOUT"        # Collect shipping/payment info
    CONFIRM = "CONFIRM"          # Final confirmation
    SUPPORT = "SUPPORT"          # Fallback for complaints/out-of-scope


class NextAction(str, Enum):
    """Router's decision on what action to take."""
    ASK_CLARIFY = "ASK_CLARIFY"
    SHOW_OPTIONS = "SHOW_OPTIONS"
    COLLECT_CHECKOUT = "COLLECT_CHECKOUT"
    CONFIRM_ORDER = "CONFIRM_ORDER"
    HANDLE_SUPPORT = "HANDLE_SUPPORT"


@dataclass
class Slots:
    """
    User preferences extracted during DISCOVERY stage.
    These drive the product search in SHORTLIST.
    """
    category: Optional[str] = None      # e.g., "shoes", "headphones"
    keywords: list[str] = field(default_factory=list)  # e.g., ["running", "lightweight"]
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    color: Optional[str] = None
    size: Optional[str] = None

    def to_summary(self) -> str:
        """Compact summary for LLM context."""
        parts = []
        if self.category:
            parts.append(f"category={self.category}")
        if self.keywords:
            parts.append(f"keywords={','.join(self.keywords)}")
        if self.budget_min is not None or self.budget_max is not None:
            budget = f"{self.budget_min or 0}-{self.budget_max or '∞'}"
            parts.append(f"budget={budget}")
        if self.color:
            parts.append(f"color={self.color}")
        if self.size:
            parts.append(f"size={self.size}")
        return "; ".join(parts) if parts else "none filled"

    def missing_required(self) -> list[str]:
        """Return list of missing required slots for search."""
        missing = []
        # At minimum, we need category or keywords to do a meaningful search
        if not self.category and not self.keywords:
            missing.append("category or keywords")
        return missing


@dataclass
class CheckoutInfo:
    """Shipping and payment info collected in CHECKOUT stage."""
    name: Optional[str] = None
    address: Optional[str] = None
    payment_method: Optional[str] = None  # "cash", "card", "transfer"

    def to_summary(self) -> str:
        """Compact summary for LLM context."""
        parts = []
        if self.name:
            parts.append(f"name={self.name}")
        if self.address:
            parts.append(f"address={self.address}")
        if self.payment_method:
            parts.append(f"payment={self.payment_method}")
        return "; ".join(parts) if parts else "none filled"

    def missing_required(self) -> list[str]:
        """Return list of missing required fields."""
        missing = []
        if not self.name:
            missing.append("name")
        if not self.address:
            missing.append("address")
        if not self.payment_method:
            missing.append("payment_method")
        return missing

    def is_complete(self) -> bool:
        """Check if all required fields are filled."""
        return bool(self.name and self.address and self.payment_method)


@dataclass
class RouterDecision:
    """
    Structured output from the Router LLM.
    This determines which specialist handles the turn.
    """
    stage: Stage
    need_search: bool = False
    slots_missing: list[str] = field(default_factory=list)
    next_action: NextAction = NextAction.ASK_CLARIFY
    escalate: bool = False  # POC: always False, but exists for extension


@dataclass
class ConversationState:
    """
    The complete conversation state.
    
    This is passed through LangGraph and updated by each node.
    Only minimal summaries are sent to LLMs, not the full state.
    """
    # Current stage in the flow
    stage: Stage = Stage.GREETING
    
    # User preferences for product search
    slots: Slots = field(default_factory=Slots)
    
    # Shopping cart (list of product IDs)
    cart: list[str] = field(default_factory=list)
    
    # Last shown product IDs (for "I'll take the second one" type references)
    last_products: list[str] = field(default_factory=list)
    
    # Checkout information
    checkout: CheckoutInfo = field(default_factory=CheckoutInfo)
    
    # Rolling memory summary - kept short (5-10 lines)
    memory_summary: str = ""
    
    # Turn counter
    turn_id: int = 0
    
    # Last user message (for processing)
    last_user_message: str = ""
    
    # Last assistant response (for display)
    last_assistant_response: str = ""
    
    # Router's decision for this turn
    router_decision: Optional[RouterDecision] = None
    
    # Order ID if confirmed
    order_id: Optional[str] = None
    
    # Session stats for logging
    total_tokens: int = 0
    total_llm_calls: int = 0
    total_search_calls: int = 0

    def get_context_for_llm(self) -> str:
        """
        Build minimal context string for LLM calls.
        This is much smaller than sending full conversation history.
        """
        lines = [
            f"Stage: {self.stage.value}",
            f"Slots: {self.slots.to_summary()}",
            f"Cart: {len(self.cart)} items",
            f"Checkout: {self.checkout.to_summary()}",
        ]
        if self.memory_summary:
            lines.append(f"Summary: {self.memory_summary}")
        if self.last_products:
            lines.append(f"Last shown products: {', '.join(self.last_products[:5])}")
        return "\n".join(lines)
