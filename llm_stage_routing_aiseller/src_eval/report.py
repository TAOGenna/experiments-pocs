"""
Markdown Report Generator for evaluation results.

Supports:
- Single scenario reports
- Comparison reports (stage-routing vs react)
- Multi-scenario batch reports (compact format)
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from src_eval.judge import EvaluationResult


def generate_report(
    result: EvaluationResult,
    mode: str,
    output_dir: str = "evaluations",
    filename: Optional[str] = None,
) -> str:
    """
    Generate a markdown report for an evaluation result.
    
    Args:
        result: The evaluation result
        mode: The mode used ("stage-routing" or "react")
        output_dir: Directory to save the report
        filename: Optional custom filename
        
    Returns:
        Path to the generated report
    """
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if filename is None:
        safe_name = result.scenario_name.lower().replace(" ", "_")
        filename = f"{safe_name}_{mode}_{timestamp}.md"
    
    filepath = output_path / filename
    
    # Build markdown content
    md = _build_markdown(result, mode, timestamp)
    
    # Write to file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)
    
    return str(filepath)


def generate_comparison_report(
    stage_result: EvaluationResult,
    react_result: EvaluationResult,
    output_dir: str = "evaluations",
) -> str:
    """
    Generate a comparison report for both modes.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = stage_result.scenario_name.lower().replace(" ", "_")
    filename = f"{safe_name}_comparison_{timestamp}.md"
    filepath = output_path / filename
    
    md = _build_comparison_markdown(stage_result, react_result, timestamp)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)
    
    return str(filepath)


def _build_markdown(result: EvaluationResult, mode: str, timestamp: str) -> str:
    """Build markdown content for a single result."""
    
    status_emoji = "✅" if result.passed else "❌"
    
    md = f"""# Evaluation Report: {result.scenario_name}

**Mode:** {mode}  
**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Status:** {status_emoji} {"PASSED" if result.passed else "FAILED"}  
**Score:** {result.score:.0%}

---

## Judge Analysis

> {result.judge_explanation}

---

## Results Summary

| Metric | Result |
|--------|--------|
| Cart Correct | {"✅" if result.cart_correct else "❌"} |
| Total Correct | {"✅" if result.total_correct else "❌"} |
| Order Confirmed | {"✅" if result.order_confirmed else "❌"} |
| Checkout Info Correct | {"✅" if result.checkout_correct else "❌"} |

### Expected vs Actual

| Field | Expected | Actual |
|-------|----------|--------|
| Cart Items | {", ".join(result.expected_cart)} | {", ".join(result.actual_cart) or "None"} |
| Total | {result.expected_total or "Any"} PEN | {result.actual_total or "Not found"} PEN |

---

## Usage Statistics

| Metric | Value |
|--------|-------|
| Total Tokens | **{result.total_tokens:,}** |
| LLM Calls | {result.total_llm_calls} |
| Tool/Search Calls | {result.total_tool_calls} |
| Conversation Turns | {result.total_turns} |
| Retries Needed | {result.total_retries} |

"""
    
    # Add issues if any
    if result.issues:
        md += """---

## Issues Noted

"""
        for issue in result.issues:
            md += f"- {issue}\n"
    
    return md


def _build_comparison_markdown(
    stage_result: EvaluationResult,
    react_result: EvaluationResult,
    timestamp: str,
) -> str:
    """Build comparison markdown for both modes."""
    
    stage_emoji = "✅" if stage_result.passed else "❌"
    react_emoji = "✅" if react_result.passed else "❌"
    
    # Determine winner
    if stage_result.passed and not react_result.passed:
        winner = "🏆 **Stage-Routing wins**"
    elif react_result.passed and not stage_result.passed:
        winner = "🏆 **ReAct wins**"
    elif stage_result.passed and react_result.passed:
        # Both passed - compare efficiency
        if stage_result.total_tokens < react_result.total_tokens:
            winner = "🏆 **Stage-Routing wins** (more efficient)"
        elif react_result.total_tokens < stage_result.total_tokens:
            winner = "🏆 **ReAct wins** (more efficient)"
        else:
            winner = "🤝 **Tie** - Both passed with similar efficiency"
    else:
        winner = "❌ **Both failed**"
    
    # Token efficiency
    if react_result.total_tokens > 0:
        token_ratio = stage_result.total_tokens / react_result.total_tokens
        if token_ratio < 1:
            token_comparison = f"Stage-Routing used **{(1-token_ratio)*100:.0f}% fewer tokens**"
        else:
            token_comparison = f"ReAct used **{(token_ratio-1)*100:.0f}% fewer tokens**"
    else:
        token_comparison = "Unable to compare (missing data)"
    
    md = f"""# Comparison Report: {stage_result.scenario_name}

**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## {winner}

---

## Overall Results

| Mode | Status | Score | Tokens | LLM Calls | Tool Calls |
|------|--------|-------|--------|-----------|------------|
| Stage-Routing | {stage_emoji} {"PASS" if stage_result.passed else "FAIL"} | {stage_result.score:.0%} | **{stage_result.total_tokens:,}** | {stage_result.total_llm_calls} | {stage_result.total_tool_calls} |
| ReAct | {react_emoji} {"PASS" if react_result.passed else "FAIL"} | {react_result.score:.0%} | **{react_result.total_tokens:,}** | {react_result.total_llm_calls} | {react_result.total_tool_calls} |

**Token Efficiency:** {token_comparison}

---

## Judge Analysis

### Stage-Routing

> {stage_result.judge_explanation}

### ReAct

> {react_result.judge_explanation}

---

## Detailed Comparison

| Metric | Stage-Routing | ReAct |
|--------|---------------|-------|
| Cart Correct | {"✅" if stage_result.cart_correct else "❌"} | {"✅" if react_result.cart_correct else "❌"} |
| Total Correct | {"✅" if stage_result.total_correct else "❌"} | {"✅" if react_result.total_correct else "❌"} |
| Order Confirmed | {"✅" if stage_result.order_confirmed else "❌"} | {"✅" if react_result.order_confirmed else "❌"} |
| Checkout Correct | {"✅" if stage_result.checkout_correct else "❌"} | {"✅" if react_result.checkout_correct else "❌"} |
| Turns | {stage_result.total_turns} | {react_result.total_turns} |
| Retries | {stage_result.total_retries} | {react_result.total_retries} |

---

## Expected Outcome

- **Cart Items:** {", ".join(stage_result.expected_cart)}
- **Total:** {stage_result.expected_total or "Any"} PEN
- **Order Confirmed:** Yes

---

## Actual Results

### Stage-Routing
- **Cart Found:** {", ".join(stage_result.actual_cart) or "None"}
- **Total Found:** {stage_result.actual_total or "Not mentioned"} PEN

### ReAct
- **Cart Found:** {", ".join(react_result.actual_cart) or "None"}
- **Total Found:** {react_result.actual_total or "Not mentioned"} PEN

"""
    
    # Add issues if any
    if stage_result.issues or react_result.issues:
        md += """---

## Issues Noted

"""
        if stage_result.issues:
            md += "### Stage-Routing\n"
            for issue in stage_result.issues:
                md += f"- {issue}\n"
            md += "\n"
        
        if react_result.issues:
            md += "### ReAct\n"
            for issue in react_result.issues:
                md += f"- {issue}\n"
    
    return md


# =============================================================================
# MULTI-SCENARIO BATCH REPORT
# =============================================================================

def generate_multi_scenario_report(
    results: list[tuple[EvaluationResult, EvaluationResult]],
    output_dir: str = "evaluations",
) -> str:
    """
    Generate a compact report for multiple scenario comparisons.
    
    Args:
        results: List of (stage_result, react_result) tuples
        output_dir: Directory to save the report
        
    Returns:
        Path to the generated report
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"full_comparison_{timestamp}.md"
    filepath = output_path / filename
    
    md = _build_multi_scenario_markdown(results, timestamp)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)
    
    return str(filepath)


def _build_multi_scenario_markdown(
    results: list[tuple[EvaluationResult, EvaluationResult]],
    timestamp: str,
) -> str:
    """Build compact markdown for multiple scenario comparison."""
    
    # Calculate totals
    stage_passed = sum(1 for s, _ in results if s.passed)
    react_passed = sum(1 for _, r in results if r.passed)
    total_scenarios = len(results)
    
    stage_total_tokens = sum(s.total_tokens for s, _ in results)
    react_total_tokens = sum(r.total_tokens for _, r in results)
    
    stage_total_llm_calls = sum(s.total_llm_calls for s, _ in results)
    react_total_llm_calls = sum(r.total_llm_calls for _, r in results)
    
    # Determine overall winner
    if stage_passed > react_passed:
        winner = "🏆 **Stage-Routing wins overall** (higher pass rate)"
    elif react_passed > stage_passed:
        winner = "🏆 **ReAct wins overall** (higher pass rate)"
    elif stage_passed == react_passed:
        if stage_total_tokens < react_total_tokens:
            winner = "🏆 **Stage-Routing wins overall** (same pass rate, more efficient)"
        elif react_total_tokens < stage_total_tokens:
            winner = "🏆 **ReAct wins overall** (same pass rate, more efficient)"
        else:
            winner = "🤝 **Tie** - Same pass rate and efficiency"
    
    # Token efficiency
    if react_total_tokens > 0:
        token_ratio = stage_total_tokens / react_total_tokens
        if token_ratio < 1:
            token_eff = f"Stage-Routing used **{(1-token_ratio)*100:.0f}% fewer tokens** overall"
        else:
            token_eff = f"ReAct used **{(token_ratio-1)*100:.0f}% fewer tokens** overall"
    else:
        token_eff = "Unable to compare tokens"
    
    md = f"""# Full Evaluation Report: All Scenarios

**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Scenarios Run:** {total_scenarios}

## {winner}

---

## Summary

| Metric | Stage-Routing | ReAct |
|--------|---------------|-------|
| **Pass Rate** | {stage_passed}/{total_scenarios} ({stage_passed/total_scenarios*100:.0f}%) | {react_passed}/{total_scenarios} ({react_passed/total_scenarios*100:.0f}%) |
| **Total Tokens** | {stage_total_tokens:,} | {react_total_tokens:,} |
| **Total LLM Calls** | {stage_total_llm_calls} | {react_total_llm_calls} |

**{token_eff}**

---

## Scenario Results

| Scenario | Stage-Routing | ReAct | Winner |
|----------|---------------|-------|--------|
"""
    
    # Add each scenario row
    for stage_result, react_result in results:
        stage_status = "✅" if stage_result.passed else "❌"
        react_status = "✅" if react_result.passed else "❌"
        
        # Determine scenario winner
        if stage_result.passed and not react_result.passed:
            scenario_winner = "Stage-Routing"
        elif react_result.passed and not stage_result.passed:
            scenario_winner = "ReAct"
        elif stage_result.passed and react_result.passed:
            if stage_result.total_tokens < react_result.total_tokens:
                scenario_winner = "Stage-Routing ⚡"
            else:
                scenario_winner = "Tie"
        else:
            scenario_winner = "Both failed"
        
        md += f"| {stage_result.scenario_name} | {stage_status} {stage_result.total_tokens:,} tok | {react_status} {react_result.total_tokens:,} tok | {scenario_winner} |\n"
    
    md += """
---

## Detailed Results

"""
    
    # Add brief details for each scenario
    for i, (stage_result, react_result) in enumerate(results, 1):
        stage_emoji = "✅" if stage_result.passed else "❌"
        react_emoji = "✅" if react_result.passed else "❌"
        
        md += f"""### {i}. {stage_result.scenario_name}

| Check | Stage-Routing | ReAct |
|-------|---------------|-------|
| Cart | {"✅" if stage_result.cart_correct else "❌"} | {"✅" if react_result.cart_correct else "❌"} |
| Total | {"✅" if stage_result.total_correct else "❌"} | {"✅" if react_result.total_correct else "❌"} |
| Order | {"✅" if stage_result.order_confirmed else "❌"} | {"✅" if react_result.order_confirmed else "❌"} |
| Checkout | {"✅" if stage_result.checkout_correct else "❌"} | {"✅" if react_result.checkout_correct else "❌"} |

"""
        
        # Add issues if any failures
        if not stage_result.passed and stage_result.issues:
            md += f"**Stage-Routing Issues:** {'; '.join(stage_result.issues[:2])}\n\n"
        if not react_result.passed and react_result.issues:
            md += f"**ReAct Issues:** {'; '.join(react_result.issues[:2])}\n\n"
    
    return md
