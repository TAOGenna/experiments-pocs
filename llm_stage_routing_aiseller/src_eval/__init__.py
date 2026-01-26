"""
Automated Evaluation System for Catalog Seller Chatbot

This module provides tools to automatically evaluate the chatbot using
an LLM "judge" that follows a predefined script and evaluates the results.
"""

from src_eval.judge import JudgeLLM
from src_eval.scenarios import Scenario, SCENARIOS
from src_eval.runner import run_evaluation
from src_eval.report import generate_report

__all__ = ["JudgeLLM", "Scenario", "SCENARIOS", "run_evaluation", "generate_report"]
