"""
Simple state for the ReAct agent.

Unlike the stage-routing approach, the ReAct agent doesn't have explicit stages.
State is simpler - we just track what we know and let the LLM figure out what to do.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReActState:
    """
    Minimal state for ReAct agent.
    
    Unlike ConversationState in src/, this doesn't have explicit stages.
    The agent decides what to do based on the conversation history and tools.
    """
    # Conversation history (full history, unlike rolling summary in stage-routing)
    messages: list[dict] = field(default_factory=list)
    
    # Shopping cart (list of product IDs)
    cart: list[str] = field(default_factory=list)
    
    # Last shown products (for reference)
    last_products: list[dict] = field(default_factory=list)
    
    # Collected user preferences (slots)
    preferences: dict = field(default_factory=dict)
    
    # Checkout information
    checkout_info: dict = field(default_factory=dict)
    
    # Order ID if confirmed
    order_id: Optional[str] = None
    
    # Turn counter
    turn_id: int = 0
    
    # Session stats
    total_tokens: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    
    def add_user_message(self, message: str) -> None:
        """Add a user message to history."""
        self.messages.append({"role": "user", "content": message})
    
    def add_assistant_message(self, message: str) -> None:
        """Add an assistant message to history."""
        self.messages.append({"role": "assistant", "content": message})
    
    def get_conversation_history(self) -> list[dict]:
        """Get full conversation history for LLM context."""
        return self.messages.copy()
    
    def get_state_summary(self) -> str:
        """Get current state summary for tool context."""
        parts = []
        
        if self.preferences:
            prefs = ", ".join(f"{k}={v}" for k, v in self.preferences.items() if v)
            if prefs:
                parts.append(f"User preferences: {prefs}")
        
        if self.cart:
            parts.append(f"Cart: {len(self.cart)} item(s) - {', '.join(self.cart)}")
        
        if self.checkout_info:
            checkout = ", ".join(f"{k}={v}" for k, v in self.checkout_info.items() if v)
            if checkout:
                parts.append(f"Checkout info: {checkout}")
        
        if self.order_id:
            parts.append(f"Order confirmed: {self.order_id}")
        
        return "\n".join(parts) if parts else "No state collected yet"
