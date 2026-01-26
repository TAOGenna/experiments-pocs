#!/usr/bin/env python3
"""
Catalog Seller Chatbot - Terminal Loop

This is the entry point that runs the chatbot in a terminal interface.
Supports two modes:
1. STAGE-ROUTING (default): Router → One Specialist → Memory Update
2. REACT: Single agent with giant prompt and tool loop

HOW THEY DIFFER:
- Stage-routing: Predictable, bounded execution per turn
- ReAct: Open-ended tool loops, unpredictable cost

Run with:
    python main.py              # Stage-routing mode (default)
    python main.py --react      # ReAct mode
    python main.py --mode react # Alternative syntax
    python main.py --color      # Enable colored output
"""

import argparse
import os
import sys

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Verify API key is set
if not os.getenv("OPENAI_API_KEY"):
    print("Error: OPENAI_API_KEY not set in environment or .env file")
    print("Please create a .env file with your API key:")
    print("  OPENAI_API_KEY=sk-your-key-here")
    sys.exit(1)

# Import colors module
from src.colors import (
    set_colors_enabled, bot_message, user_message, system_message,
    error_message, success_message, header, dim, bold,
    bot_label, user_label, customer_label, debug_label
)

# =============================================================================
# LANGSMITH TRACING SETUP
# =============================================================================

LANGSMITH_ENABLED = bool(
    os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true" 
    and os.getenv("LANGCHAIN_API_KEY")
)

if LANGSMITH_ENABLED:
    if not os.getenv("LANGCHAIN_PROJECT"):
        os.environ["LANGCHAIN_PROJECT"] = "catalog-chatbot-poc"
    print(f"LangSmith tracing enabled -> project: {os.getenv('LANGCHAIN_PROJECT')}")
else:
    print("LangSmith tracing disabled (set LANGCHAIN_TRACING_V2=true to enable)")


# =============================================================================
# STAGE-ROUTING MODE FUNCTIONS
# =============================================================================

def run_stage_routing_mode():
    """Run the chatbot in stage-routing mode."""
    from src.state import ConversationState, Stage
    from src.graph import run_turn
    from src.catalog import load_or_create_catalog
    
    print_header_stage_routing()
    
    # Ensure catalog exists
    load_or_create_catalog()
    
    # Initialize state
    state = ConversationState()
    
    # Initial greeting
    greeting = "Hello! Welcome to our store! I can help you find the perfect product.\n     What are you looking for today?"
    print(f"{bot_label()} {bot_message(greeting)}\n")
    
    # Update state for initial greeting
    state.last_assistant_response = "Hello! Welcome to our store! I can help you find the perfect product. What are you looking for today?"
    state.stage = Stage.DISCOVERY
    
    while True:
        try:
            user_input = input(f"{user_label()} ").strip()
            
            if user_input.lower() in ["exit", "quit", "bye", "salir"]:
                print(f"\n{bot_label()} {bot_message('Goodbye! Thanks for visiting our store.')}")
                print_session_stats_stage_routing(state)
                break
            
            if not user_input:
                continue
            
            # Run one turn
            state = run_turn(state, user_input)
            
            # Print bot response
            print(f"\n{bot_label()} {bot_message(state.last_assistant_response)}")
            
            # Print debug info
            print_debug_stage_routing(state)
            print()
            
        except KeyboardInterrupt:
            print(f"\n\n{error_message('Interrupted by user')}")
            print_session_stats_stage_routing(state)
            break
        except Exception as e:
            print(f"\n{error_message(f'Error: {e}')}")
            print("Please try again or type 'exit' to quit.\n")
            import traceback
            traceback.print_exc()


def print_header_stage_routing():
    """Print welcome header for stage-routing mode."""
    print("\n" + "=" * 60)
    print(header("CATALOG SELLER CHATBOT - STAGE ROUTING MODE"))
    print("=" * 60)
    print("This mode uses STAGE ROUTING with SPECIALISTS.")
    print("Each turn: Router -> One Specialist -> Memory Update")
    print("-" * 60)
    print(dim("Type 'exit' to quit and see session stats."))
    print("=" * 60 + "\n")


def print_debug_stage_routing(state):
    """Print debug info for stage-routing mode."""
    decision = state.router_decision
    stage = decision.stage.value if decision else state.stage.value
    need_search = decision.need_search if decision else False
    
    debug_text = (f"stage={stage}, need_search={need_search}, "
                  f"tokens={state.total_tokens}, llm_calls={state.total_llm_calls}, "
                  f"search_calls={state.total_search_calls}")
    print(f"\n{debug_label()} {system_message(debug_text)}")


def print_session_stats_stage_routing(state):
    """Print session statistics for stage-routing mode."""
    print("\n" + "=" * 60)
    print(header("SESSION STATISTICS (Stage-Routing)"))
    print("=" * 60)
    print(f"  Total turns:        {bold(str(state.turn_id))}")
    print(f"  Total tokens:       {bold(str(state.total_tokens))}")
    print(f"  Total LLM calls:    {bold(str(state.total_llm_calls))}")
    print(f"  Total search calls: {bold(str(state.total_search_calls))}")
    if state.order_id:
        print(f"  Order completed:    {success_message(state.order_id)}")
    print("=" * 60)
    print(f"\n{dim('Thank you for using the Catalog Chatbot!')}")


# =============================================================================
# REACT MODE FUNCTIONS
# =============================================================================

def run_react_mode():
    """Run the chatbot in ReAct mode."""
    from src_react.state import ReActState
    from src_react.react_agent import run_react_turn
    from src.catalog import load_or_create_catalog
    
    print_header_react()
    
    # Ensure catalog exists
    load_or_create_catalog()
    
    # Initialize state
    state = ReActState()
    
    # Initial greeting (manual for first turn)
    initial_greeting = "Hello! Welcome to our store! I'm here to help you find the perfect product. What are you looking for today?"
    print(f"{bot_label()} {bot_message(initial_greeting)}\n")
    state.add_assistant_message(initial_greeting)
    
    while True:
        try:
            user_input = input(f"{user_label()} ").strip()
            
            if user_input.lower() in ["exit", "quit", "bye", "salir"]:
                print(f"\n{bot_label()} {bot_message('Goodbye! Thanks for visiting our store.')}")
                print_session_stats_react(state)
                break
            
            if not user_input:
                continue
            
            # Run one turn
            state = run_react_turn(state, user_input)
            
            # Print bot response (last message in history)
            last_response = state.messages[-1]["content"] if state.messages else "..."
            print(f"\n{bot_label()} {bot_message(last_response)}")
            
            # Print debug info
            print_debug_react(state)
            print()
            
        except KeyboardInterrupt:
            print(f"\n\n{error_message('Interrupted by user')}")
            print_session_stats_react(state)
            break
        except Exception as e:
            print(f"\n{error_message(f'Error: {e}')}")
            print("Please try again or type 'exit' to quit.\n")
            import traceback
            traceback.print_exc()


def print_header_react():
    """Print welcome header for ReAct mode."""
    print("\n" + "=" * 60)
    print(header("CATALOG SELLER CHATBOT - REACT MODE"))
    print("=" * 60)
    print("This mode uses a SINGLE REACT AGENT with GIANT PROMPT.")
    print("The agent decides when to use tools in an open loop.")
    print("-" * 60)
    print(dim("CONTRAST WITH STAGE-ROUTING:"))
    print(dim("  - One giant prompt vs. focused specialist prompts"))
    print(dim("  - Open-ended tool loop vs. bounded execution"))
    print(dim("  - Unpredictable cost vs. predictable per-turn cost"))
    print("-" * 60)
    print(dim("Type 'exit' to quit and see session stats."))
    print("=" * 60 + "\n")


def print_debug_react(state):
    """Print debug info for ReAct mode."""
    debug_text = (f"turn={state.turn_id}, "
                  f"tokens={state.total_tokens}, "
                  f"llm_calls={state.total_llm_calls}, "
                  f"tool_calls={state.total_tool_calls}, "
                  f"cart={len(state.cart)}")
    print(f"\n{debug_label()} {system_message(debug_text)}")


def print_session_stats_react(state):
    """Print session statistics for ReAct mode."""
    print("\n" + "=" * 60)
    print(header("SESSION STATISTICS (ReAct)"))
    print("=" * 60)
    print(f"  Total turns:        {bold(str(state.turn_id))}")
    print(f"  Total tokens:       {bold(str(state.total_tokens))}")
    print(f"  Total LLM calls:    {bold(str(state.total_llm_calls))}")
    print(f"  Total tool calls:   {bold(str(state.total_tool_calls))}")
    if state.cart:
        print(f"  Cart items:         {bold(str(len(state.cart)))}")
    if state.order_id:
        print(f"  Order completed:    {success_message(state.order_id)}")
    print("=" * 60)
    print(dim("\nNOTE: ReAct mode typically uses MORE tokens and LLM calls"))
    print(dim("      due to the giant prompt and open-ended tool loop."))
    print(dim("      Compare with stage-routing for the difference!"))


# =============================================================================
# EVALUATION MODE FUNCTIONS
# =============================================================================

def run_evaluation_mode(scenario: str, mode: str, compare: bool, verbose: bool):
    """Run automated evaluation."""
    from src_eval.scenarios import SCENARIOS
    from src_eval.runner import run_evaluation, run_comparison, run_all_comparisons, run_selected_comparisons, RunConfig
    from src_eval.report import generate_report, generate_comparison_report, generate_multi_scenario_report
    
    # Handle "all" scenarios or comma-separated list
    if scenario == "all" or "," in scenario:
        if scenario == "all":
            scenario_ids = list(SCENARIOS.keys())
            print(f"\nRunning ALL {len(scenario_ids)} scenarios comparison...")
        else:
            # Parse comma-separated scenario IDs
            scenario_ids = [s.strip() for s in scenario.split(",")]
            invalid = [s for s in scenario_ids if s not in SCENARIOS]
            if invalid:
                print(f"{error_message(f'Unknown scenarios: {invalid}')}")
                print(f"Available: {list(SCENARIOS.keys())}")
                return
            print(f"\nRunning {len(scenario_ids)} scenarios comparison: {', '.join(scenario_ids)}...")
        
        results = run_selected_comparisons(scenario_ids, verbose=verbose)
        
        # Generate multi-scenario report
        report_path = generate_multi_scenario_report(results)
        print(f"\n{dim('Report saved to:')} {report_path}")
        
        # Print summary
        stage_passed = sum(1 for s, _ in results if s.passed)
        react_passed = sum(1 for _, r in results if r.passed)
        total = len(results)
        
        stage_tokens = sum(s.total_tokens for s, _ in results)
        react_tokens = sum(r.total_tokens for _, r in results)
        
        print("\n" + "="*70)
        print(header("FULL COMPARISON SUMMARY"))
        print("="*70)
        print(f"\n{'Mode':<16} {'Pass Rate':<15} {'Total Tokens':<15}")
        print("-"*70)
        
        stage_rate = f"{stage_passed}/{total} ({stage_passed/total*100:.0f}%)"
        react_rate = f"{react_passed}/{total} ({react_passed/total*100:.0f}%)"
        
        print(f"{'Stage-Routing':<16} {stage_rate:<15} {stage_tokens:,}")
        print(f"{'ReAct':<16} {react_rate:<15} {react_tokens:,}")
        print("-"*70)
        
        # Token comparison
        if react_tokens > 0 and stage_tokens > 0:
            if stage_tokens < react_tokens:
                savings = (1 - stage_tokens / react_tokens) * 100
                print(f"\n{success_message(f'Stage-Routing used {savings:.0f}% fewer tokens overall')}")
            else:
                extra = (stage_tokens / react_tokens - 1) * 100
                print(f"\n{system_message(f'ReAct used {extra:.0f}% fewer tokens overall')}")
        
        # Winner
        if stage_passed > react_passed:
            print(f"\n{success_message('🏆 Stage-Routing wins (higher pass rate)')}")
        elif react_passed > stage_passed:
            print(f"\n{success_message('🏆 ReAct wins (higher pass rate)')}")
        else:
            if stage_tokens < react_tokens:
                print(f"\n{success_message('🏆 Stage-Routing wins (same pass rate, more efficient)')}")
            else:
                print(f"\n{system_message('🤝 Tie')}")
        
        print("="*70)
        return
    
    if compare:
        # Run comparison between both modes
        print(f"\nRunning comparison evaluation for scenario: {scenario}")
        stage_result, react_result = run_comparison(scenario, verbose=verbose)
        
        # Generate comparison report
        report_path = generate_comparison_report(stage_result, react_result)
        print(f"\n{dim('Report saved to:')} {report_path}")
        
        # Print summary
        print("\n" + "="*70)
        print(header("COMPARISON SUMMARY"))
        print("="*70)
        print(f"\n{'Mode':<16} {'Status':<10} {'Score':<8} {'Tokens':<12} {'LLM Calls':<10}")
        print("-"*70)
        
        stage_status = success_message("PASSED") if stage_result.passed else error_message("FAILED")
        react_status = success_message("PASSED") if react_result.passed else error_message("FAILED")
        
        print(f"{'Stage-Routing':<16} {stage_status:<19} {stage_result.score:.0%}     {stage_result.total_tokens:<12,} {stage_result.total_llm_calls:<10}")
        print(f"{'ReAct':<16} {react_status:<19} {react_result.score:.0%}     {react_result.total_tokens:<12,} {react_result.total_llm_calls:<10}")
        print("-"*70)
        
        # Token comparison
        if react_result.total_tokens > 0 and stage_result.total_tokens > 0:
            if stage_result.total_tokens < react_result.total_tokens:
                savings = (1 - stage_result.total_tokens / react_result.total_tokens) * 100
                print(f"\n{success_message(f'Stage-Routing used {savings:.0f}% fewer tokens')}")
            else:
                extra = (stage_result.total_tokens / react_result.total_tokens - 1) * 100
                print(f"\n{system_message(f'ReAct used {extra:.0f}% fewer tokens')}")
        
        # Judge explanations
        print(f"\n{bold('Judge Analysis:')}")
        print(f"  Stage-Routing: {stage_result.judge_explanation}")
        print(f"  ReAct: {react_result.judge_explanation}")
        
        print("="*70)
    else:
        # Run single mode evaluation
        if scenario not in SCENARIOS:
            print(f"{error_message(f'Unknown scenario: {scenario}')}")
            print(f"Available scenarios: {list(SCENARIOS.keys())}")
            return
        
        print(f"\nRunning evaluation: {scenario} ({mode})")
        
        config = RunConfig(
            mode=mode,
            scenario=SCENARIOS[scenario],
            verbose=verbose,
        )
        result = run_evaluation(config)
        
        # Generate report
        report_path = generate_report(result, mode)
        print(f"\n{dim('Report saved to:')} {report_path}")
        
        # Print summary
        print("\n" + "="*60)
        print(header("EVALUATION SUMMARY"))
        print("="*60)
        status = success_message("PASSED") if result.passed else error_message("FAILED")
        print(f"Status: {status}")
        print(f"Score: {bold(f'{result.score:.0%}')}")
        print(f"\n{bold('Metrics:')}")
        print(f"  Cart Correct:    {'✅' if result.cart_correct else '❌'}")
        print(f"  Total Correct:   {'✅' if result.total_correct else '❌'}")
        print(f"  Order Confirmed: {'✅' if result.order_confirmed else '❌'}")
        print(f"\n{bold('Usage:')}")
        print(f"  Tokens:    {result.total_tokens:,}")
        print(f"  LLM Calls: {result.total_llm_calls}")
        print(f"  Tools:     {result.total_tool_calls}")
        print(f"\n{bold('Judge:')} {result.judge_explanation}")
        print("="*60)


def list_scenarios():
    """List available evaluation scenarios."""
    from src_eval.scenarios import SCENARIOS
    
    print("\nAvailable evaluation scenarios:")
    print("-" * 40)
    for scenario_id, scenario in SCENARIOS.items():
        print(f"  {scenario_id}:")
        print(f"    {scenario.description}")
        print(f"    Steps: {len(scenario.steps)}")
        print()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Catalog Seller Chatbot - Compare Stage-Routing vs ReAct",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                          # Interactive stage-routing mode
    python main.py --react                  # Interactive ReAct mode
    python main.py --color                  # Enable colored output
    python main.py --eval --compare         # Run evaluation (compare both modes)
    python main.py --eval --scenario all    # Run ALL scenarios comparison
    python main.py --eval --mode react      # Evaluate only ReAct mode
    python main.py --eval --scenario simple_shoe  # Run specific scenario
    python main.py --list-scenarios         # List available scenarios

MODES:
  stage-routing: Router picks ONE specialist per turn (predictable)
  react: Single agent with giant prompt (flexible)

EVALUATION:
  Automated testing using an LLM judge that follows test scripts.
  Results are saved as markdown reports in the 'evaluations/' folder.
"""
    )
    
    # Mode selection
    parser.add_argument(
        "--react",
        action="store_true",
        help="Run in ReAct mode instead of stage-routing"
    )
    
    parser.add_argument(
        "--mode",
        choices=["stage-routing", "react"],
        default="stage-routing",
        help="Choose the mode to run (default: stage-routing)"
    )
    
    # Display options
    parser.add_argument(
        "--color",
        action="store_true",
        help="Enable colored terminal output"
    )
    
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored terminal output"
    )
    
    # Evaluation options
    parser.add_argument(
        "--eval",
        action="store_true",
        help="Run automated evaluation instead of interactive mode"
    )
    
    parser.add_argument(
        "--scenario",
        default="headphones_multi",
        help="Evaluation scenario to run (default: headphones_multi). Use 'all' to run all scenarios."
    )
    
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare both modes on the same scenario"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed conversation during evaluation"
    )
    
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List available evaluation scenarios"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Handle color settings
    # Default: colors enabled unless --no-color is specified
    if args.no_color:
        set_colors_enabled(False)
    elif args.color:
        set_colors_enabled(True)
    # else: keep default (enabled)
    
    # List scenarios
    if args.list_scenarios:
        list_scenarios()
        return
    
    # Evaluation mode
    if args.eval:
        mode = "react" if args.react else args.mode
        run_evaluation_mode(
            scenario=args.scenario,
            mode=mode,
            compare=args.compare or (not args.react and args.mode == "stage-routing"),
            verbose=args.verbose,
        )
        return
    
    # Interactive mode
    if args.react or args.mode == "react":
        run_react_mode()
    else:
        run_stage_routing_mode()


if __name__ == "__main__":
    main()
