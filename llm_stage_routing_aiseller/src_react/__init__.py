"""
ReAct Agent Implementation - Single Agent with Giant Prompt

This module implements a traditional ReAct agent approach for comparison
with the stage-routing specialist approach in src/.

KEY DIFFERENCES FROM STAGE-ROUTING:
- ONE giant prompt that handles all scenarios
- Open-ended tool loop (LLM decides when to stop)
- All logic packed into a single agent
- Unpredictable cost per turn (varies based on tool calls)
"""

# Lazy imports to avoid circular dependencies
__all__ = ["ReActAgent", "ReActState", "run_react_turn"]


def __getattr__(name):
    if name == "ReActAgent":
        from src_react.react_agent import ReActAgent
        return ReActAgent
    elif name == "ReActState":
        from src_react.state import ReActState
        return ReActState
    elif name == "run_react_turn":
        from src_react.react_agent import run_react_turn
        return run_react_turn
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
