"""
Evaluation Runner - Executes scenarios against both chatbot modes.
"""

from dataclasses import dataclass
from typing import Literal

from src_eval.scenarios import Scenario
from src_eval.judge import JudgeLLM, ConversationTurn, EvaluationResult
from src.colors import (
    bot_message as format_bot_msg, customer_label, bot_label, header, dim,
    success_message, error_message, system_message
)


@dataclass
class RunConfig:
    """Configuration for a single evaluation run."""
    mode: Literal["stage-routing", "react"]
    scenario: Scenario
    verbose: bool = False


def run_evaluation(config: RunConfig) -> EvaluationResult:
    """
    Run a complete evaluation of a scenario against a chatbot mode.
    
    Args:
        config: Run configuration with mode and scenario
        
    Returns:
        EvaluationResult with all details
    """
    # CRITICAL: Reset CartStore at the start of each scenario
    # This ensures each evaluation starts with a clean slate
    from src.cart_store import cart_store
    cart_store.full_reset()
    
    judge = JudgeLLM()
    conversation: list[ConversationTurn] = []
    
    # Initialize the appropriate chatbot
    if config.mode == "stage-routing":
        from src.state import ConversationState, Stage
        from src.graph import run_turn
        from src.catalog import load_or_create_catalog
        
        load_or_create_catalog()
        state = ConversationState()
        state.stage = Stage.DISCOVERY
        
        # Initial bot greeting
        initial_greeting = "Hello! Welcome to our store! I can help you find the perfect product. What are you looking for today?"
        state.last_assistant_response = initial_greeting
        current_bot_msg = initial_greeting
        
        def get_bot_response(user_message: str) -> str:
            nonlocal state
            state = run_turn(state, user_message)
            return state.last_assistant_response
        
    else:  # react mode
        from src_react.state import ReActState
        from src_react.react_agent import run_react_turn
        from src.catalog import load_or_create_catalog
        
        load_or_create_catalog()
        state = ReActState()
        
        # Initial bot greeting
        initial_greeting = "Hello! Welcome to our store! I'm here to help you find the perfect product. What are you looking for today?"
        state.add_assistant_message(initial_greeting)
        current_bot_msg = initial_greeting
        
        def get_bot_response(user_message: str) -> str:
            nonlocal state
            state = run_react_turn(state, user_message)
            return state.messages[-1]["content"] if state.messages else ""
    
    if config.verbose:
        print(f"\n{'='*60}")
        print(header(f"Running: {config.scenario.name} ({config.mode})"))
        print(f"{'='*60}")
        print(f"\n{bot_label()} {format_bot_msg(current_bot_msg)}\n")
    
    # Execute each step in the scenario
    turn_number = 0
    
    for step_idx, step in enumerate(config.scenario.steps):
        attempt = 0
        step_success = False
        
        while attempt < step.max_retries and not step_success:
            attempt += 1
            turn_number += 1
            
            # Generate customer message
            customer_message = judge.generate_customer_message(
                step=step,
                conversation_history=conversation,
                bot_message=current_bot_msg,
                attempt=attempt,
            )
            
            if config.verbose:
                retry_tag = f" {dim(f'(retry #{attempt})')}" if attempt > 1 else ""
                print(f"{customer_label()}{retry_tag} {customer_message}")
            
            # Get bot response
            current_bot_msg = get_bot_response(customer_message)
            
            if config.verbose:
                print(f"{bot_label()} {format_bot_msg(current_bot_msg)}\n")
            
            # Record the turn
            turn = ConversationTurn(
                turn_number=turn_number,
                customer_message=customer_message,
                bot_response=current_bot_msg,
                step_intent=step.intent,
                attempt=attempt,
            )
            conversation.append(turn)
            
            # Check if step was successful
            step_success, notes = judge.check_step_success(
                step=step,
                bot_response=current_bot_msg,
                conversation_history=conversation,
            )
            
            if config.verbose and not step_success and attempt < step.max_retries:
                print(f"  {system_message(f'[Step not successful: {notes}. Retrying...]')}\n")
        
        if not step_success and step.required:
            if config.verbose:
                print(f"  {error_message(f'[Step failed after {attempt} attempts. Moving on...]')}\n")
    
    # Evaluate the final outcome
    result = judge.evaluate_outcome(
        scenario=config.scenario,
        conversation=conversation,
        final_bot_message=current_bot_msg,
    )
    
    # Extract token/call stats from the chatbot state
    if config.mode == "stage-routing":
        result.total_tokens = state.total_tokens
        result.total_llm_calls = state.total_llm_calls
        result.total_tool_calls = state.total_search_calls  # search calls in stage-routing
    else:  # react mode
        result.total_tokens = state.total_tokens
        result.total_llm_calls = state.total_llm_calls
        result.total_tool_calls = state.total_tool_calls
    
    if config.verbose:
        print(f"\n{'='*60}")
        status = success_message("PASSED") if result.passed else error_message("FAILED")
        print(f"EVALUATION RESULT: {status}")
        print(f"Score: {result.score:.0%}")
        print(f"Tokens: {result.total_tokens} | LLM Calls: {result.total_llm_calls} | Tool Calls: {result.total_tool_calls}")
        print(f"{'='*60}")
    
    return result


def run_all_scenarios(
    mode: Literal["stage-routing", "react"],
    verbose: bool = False,
) -> list[EvaluationResult]:
    """
    Run all predefined scenarios against a mode.
    
    Returns:
        List of EvaluationResults
    """
    from src_eval.scenarios import SCENARIOS
    
    results = []
    for scenario_id, scenario in SCENARIOS.items():
        config = RunConfig(
            mode=mode,
            scenario=scenario,
            verbose=verbose,
        )
        result = run_evaluation(config)
        results.append(result)
    
    return results


def run_comparison(
    scenario_id: str = "headphones_multi",
    verbose: bool = True,
) -> tuple[EvaluationResult, EvaluationResult]:
    """
    Run the same scenario on both modes for comparison.
    
    Returns:
        Tuple of (stage_routing_result, react_result)
    """
    from src_eval.scenarios import SCENARIOS
    
    scenario = SCENARIOS.get(scenario_id)
    if not scenario:
        raise ValueError(f"Unknown scenario: {scenario_id}. Available: {list(SCENARIOS.keys())}")
    
    # Run stage-routing
    print("\n" + "="*70)
    print("STAGE-ROUTING MODE")
    print("="*70)
    stage_result = run_evaluation(RunConfig(
        mode="stage-routing",
        scenario=scenario,
        verbose=verbose,
    ))
    
    # Run react
    print("\n" + "="*70)
    print("REACT MODE")
    print("="*70)
    react_result = run_evaluation(RunConfig(
        mode="react",
        scenario=scenario,
        verbose=verbose,
    ))
    
    return stage_result, react_result


def run_all_comparisons(
    verbose: bool = False,
) -> list[tuple[EvaluationResult, EvaluationResult]]:
    """
    Run all scenarios comparing both modes.
    
    Args:
        verbose: Whether to print detailed conversation output
        
    Returns:
        List of (stage_result, react_result) tuples for each scenario
    """
    from src_eval.scenarios import SCENARIOS
    return run_selected_comparisons(list(SCENARIOS.keys()), verbose=verbose)


def run_selected_comparisons(
    scenario_ids: list[str],
    verbose: bool = False,
) -> list[tuple[EvaluationResult, EvaluationResult]]:
    """
    Run selected scenarios comparing both modes.
    
    Args:
        scenario_ids: List of scenario IDs to run
        verbose: Whether to print detailed conversation output
        
    Returns:
        List of (stage_result, react_result) tuples for each scenario
    """
    from src_eval.scenarios import SCENARIOS
    
    results = []
    total = len(scenario_ids)
    
    for i, scenario_id in enumerate(scenario_ids, 1):
        scenario = SCENARIOS[scenario_id]
        
        print(f"\n{'='*70}")
        print(f"SCENARIO {i}/{total}: {scenario.name}")
        print(f"{'='*70}")
        
        # Run stage-routing
        print(f"\n--- Stage-Routing ---")
        stage_result = run_evaluation(RunConfig(
            mode="stage-routing",
            scenario=scenario,
            verbose=verbose,
        ))
        
        # Run react
        print(f"\n--- ReAct ---")
        react_result = run_evaluation(RunConfig(
            mode="react",
            scenario=scenario,
            verbose=verbose,
        ))
        
        # Brief status
        stage_status = "✅ PASS" if stage_result.passed else "❌ FAIL"
        react_status = "✅ PASS" if react_result.passed else "❌ FAIL"
        print(f"\n[Stage-Routing: {stage_status} | ReAct: {react_status}]")
        
        results.append((stage_result, react_result))
    
    return results
