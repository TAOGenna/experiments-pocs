"""
Judge LLM - Simulates a customer following a script.

The judge:
1. Follows a predefined script of customer intents
2. Adapts messages based on bot responses
3. Retries if the bot doesn't understand (up to max_retries)
4. Moves on if stuck after retries
5. Evaluates the final outcome
"""

import json
from dataclasses import dataclass, field
from typing import Optional

from langchain_openai import ChatOpenAI

from src_eval.scenarios import Scenario, ScenarioStep, ExpectedOutcome


JUDGE_MODEL = "gpt-4o-mini"


@dataclass
class StepResult:
    """Result of a single step attempt."""
    step_index: int
    intent: str
    customer_message: str
    bot_response: str
    attempt: int
    success: bool
    notes: str = ""


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    turn_number: int
    customer_message: str
    bot_response: str
    step_intent: str
    attempt: int


@dataclass 
class EvaluationResult:
    """Final evaluation of the scenario."""
    scenario_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    
    # Detailed checks
    cart_correct: bool
    total_correct: bool
    order_confirmed: bool
    checkout_correct: bool
    
    # Details
    actual_cart: list[str]
    expected_cart: list[str]
    actual_total: Optional[float]
    expected_total: Optional[float]
    
    # Judge explanation (2 sentences)
    judge_explanation: str = ""
    
    # Conversation data
    turns: list[ConversationTurn] = field(default_factory=list)
    
    # Issues encountered
    issues: list[str] = field(default_factory=list)
    
    # Stats
    total_turns: int = 0
    total_retries: int = 0
    
    # Token and LLM call tracking
    total_tokens: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0


CUSTOMER_SYSTEM_PROMPT = """You are simulating a customer in a shopping chatbot conversation.
You must follow a script of intents and use the EXAMPLE MESSAGE as your primary guide.

YOUR ROLE:
- You are a customer trying to buy products
- Follow the given intent for each step
- Use the EXAMPLE MESSAGE as your primary template

CURRENT INTENT: {intent}
EXAMPLE MESSAGE: {example}

CONVERSATION SO FAR:
{conversation}

BOT'S LAST MESSAGE:
{bot_message}

CRITICAL RULES:
1. For PRODUCT SELECTION: Use the EXACT product name from the EXAMPLE MESSAGE
   - If example says "Urban Commuter backpack", say "Urban Commuter" not "Urban Daily"
   - If example says "Sprint Lite", say "Sprint Lite" not just "running shoes"
   - PRESERVE the exact product names - they map to specific product IDs!

2. For CHECKOUT INFO: Use the EXACT name, address, and payment from the EXAMPLE MESSAGE
   - If example says "Roberto Diaz, Calle Sol 890, transfer", use THOSE EXACT values
   - DO NOT make up different names, addresses, or payment methods!
   - Payment method MUST match: transfer/card/cash as specified in example

3. For general browsing/questions: You may adapt the wording slightly

4. If this is a retry (attempt > 1), rephrase more clearly but KEEP the same product names and checkout info

5. Keep messages concise (1-2 sentences)

Output ONLY the customer's message, nothing else."""


EVALUATOR_SYSTEM_PROMPT = """You are evaluating a shopping chatbot conversation.
Analyze the conversation and determine if the expected outcomes were achieved.

EXPECTED OUTCOMES:
- Cart should contain: {expected_cart}
- Expected total: {expected_total}
- Order should be confirmed: {order_confirmed}
- Checkout info should include: {checkout_fields}

IMPORTANT EVALUATION RULES:
1. If expected cart is EMPTY or "none", then cart_correct=true if NO items were added
2. If expected total is "Any amount" or null, then total_correct=true regardless of amount
3. If order_confirmed expectation is FALSE, then order_confirmed=true if NO order was placed
4. For "no purchase" scenarios (empty cart expected, order not expected), all checks pass if the bot simply provided information without completing a purchase
5. Payment method must EXACTLY match what the customer specified (cash/card/transfer)

CONVERSATION:
{conversation}

FINAL BOT MESSAGE:
{final_message}

Analyze and return JSON:
{{
  "cart_items_found": ["list of product names/IDs mentioned as in cart or in order"],
  "total_mentioned": number or null,
  "order_id_found": "order ID if mentioned, else null",
  "checkout_info_found": {{
    "name": "name if mentioned",
    "address": "address if mentioned", 
    "payment_method": "payment method if mentioned"
  }},
  "cart_correct": true/false (true if cart matches expected, OR if expected is empty and no cart),
  "total_correct": true/false (true if total matches, OR if expected is "Any amount"),
  "order_confirmed": true/false (matches expectation - false expected means true if NO order),
  "checkout_correct": true/false,
  "issues": ["list of any issues or problems noted"],
  "overall_passed": true/false,
  "explanation": "A brief 2-sentence explanation of why this evaluation passed or failed. Focus on the key factors."
}}

Be thorough but fair. Minor variations in wording are acceptable."""


class JudgeLLM:
    """
    LLM-based judge that simulates a customer and evaluates outcomes.
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(model=JUDGE_MODEL, temperature=0.3)
        self.evaluator_llm = ChatOpenAI(model=JUDGE_MODEL, temperature=0)
    
    def generate_customer_message(
        self,
        step: ScenarioStep,
        conversation_history: list[ConversationTurn],
        bot_message: str,
        attempt: int,
    ) -> str:
        """
        Generate a customer message for the current step.
        
        Args:
            step: Current scenario step with intent
            conversation_history: Previous turns
            bot_message: Bot's last response
            attempt: Which attempt this is (1, 2, 3...)
            
        Returns:
            Customer message string
        """
        # Format conversation history
        conv_text = ""
        for turn in conversation_history:
            conv_text += f"Customer: {turn.customer_message}\n"
            conv_text += f"Bot: {turn.bot_response}\n\n"
        
        if not conv_text:
            conv_text = "(This is the start of the conversation)"
        
        # Add retry context to example if needed
        example = step.example_message
        if attempt > 1:
            example = f"(RETRY #{attempt}) {example} - Please rephrase more clearly"
        
        prompt = CUSTOMER_SYSTEM_PROMPT.format(
            intent=step.intent,
            example=example,
            conversation=conv_text,
            bot_message=bot_message or "(No previous message - you start)",
        )
        
        response = self.llm.invoke([{"role": "user", "content": prompt}])
        return response.content.strip()
    
    def check_step_success(
        self,
        step: ScenarioStep,
        bot_response: str,
        conversation_history: list[ConversationTurn],
    ) -> tuple[bool, str]:
        """
        Check if the bot's response indicates the step was understood.
        
        Returns:
            Tuple of (success, notes)
        """
        # Simple heuristic checks based on intent keywords
        intent_lower = step.intent.lower()
        response_lower = bot_response.lower()
        
        # Check for error indicators
        error_phrases = [
            "i don't understand",
            "could you clarify",
            "i'm not sure what you mean",
            "please try again",
        ]
        for phrase in error_phrases:
            if phrase in response_lower:
                return False, f"Bot indicated confusion: '{phrase}'"
        
        # Check for relevant content based on intent
        if "show" in intent_lower or "products" in intent_lower:
            # Should show products or categories
            if any(cat in response_lower for cat in ["shoes", "headphones", "backpacks", "jackets", "watches"]):
                return True, "Bot showed products/categories"
            if "price" in response_lower or "pen" in response_lower:
                return True, "Bot showed products with prices"
        
        if "select" in intent_lower or "take" in intent_lower or "buy" in intent_lower:
            # Should acknowledge selection or move to checkout
            if any(word in response_lower for word in ["cart", "added", "selected", "name", "checkout"]):
                return True, "Bot acknowledged selection"
        
        if "total" in intent_lower or "cart" in intent_lower:
            # Should show total or cart contents
            if "pen" in response_lower or "total" in response_lower or any(char.isdigit() for char in response_lower):
                return True, "Bot showed total/cart info"
        
        if "name" in intent_lower or "address" in intent_lower or "payment" in intent_lower:
            # Should acknowledge checkout info
            if any(word in response_lower for word in ["payment", "address", "confirm", "order"]):
                return True, "Bot processing checkout info"
        
        if "confirm" in intent_lower:
            # Should confirm order
            if "order" in response_lower and ("confirm" in response_lower or "ord-" in response_lower):
                return True, "Bot confirmed order"
        
        # Default: assume success if no obvious failure
        return True, "No obvious failure detected"
    
    def evaluate_outcome(
        self,
        scenario: Scenario,
        conversation: list[ConversationTurn],
        final_bot_message: str,
    ) -> EvaluationResult:
        """
        Evaluate the final outcome of the conversation.
        """
        # Build conversation text
        conv_text = ""
        for turn in conversation:
            conv_text += f"Customer: {turn.customer_message}\n"
            conv_text += f"Bot: {turn.bot_response}\n\n"
        
        expected = scenario.expected
        
        # Use LLM to analyze
        prompt = EVALUATOR_SYSTEM_PROMPT.format(
            expected_cart=", ".join(expected.cart_items),
            expected_total=expected.total_price or "Any amount",
            order_confirmed=expected.order_confirmed,
            checkout_fields=json.dumps(expected.checkout_fields),
            conversation=conv_text,
            final_message=final_bot_message,
        )
        
        response = self.evaluator_llm.invoke([{"role": "user", "content": prompt}])
        
        # Parse JSON response
        try:
            # Extract JSON from response
            content = response.content.strip()
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            result = json.loads(content)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            result = {
                "cart_items_found": [],
                "total_mentioned": None,
                "order_id_found": None,
                "checkout_info_found": {},
                "cart_correct": False,
                "total_correct": False,
                "order_confirmed": False,
                "checkout_correct": False,
                "issues": ["Failed to parse evaluation response"],
                "overall_passed": False,
                "explanation": "Evaluation failed due to parsing error.",
            }
        
        # Calculate score
        checks = [
            result.get("cart_correct", False),
            result.get("total_correct", False),
            result.get("order_confirmed", False),
            result.get("checkout_correct", False),
        ]
        score = sum(1 for c in checks if c) / len(checks)
        
        # Count retries
        total_retries = sum(1 for t in conversation if t.attempt > 1)
        
        return EvaluationResult(
            scenario_name=scenario.name,
            passed=result.get("overall_passed", False),
            score=score,
            cart_correct=result.get("cart_correct", False),
            total_correct=result.get("total_correct", False),
            order_confirmed=result.get("order_confirmed", False),
            checkout_correct=result.get("checkout_correct", False),
            actual_cart=result.get("cart_items_found", []),
            expected_cart=expected.cart_items,
            actual_total=result.get("total_mentioned"),
            expected_total=expected.total_price,
            judge_explanation=result.get("explanation", ""),
            turns=conversation,
            issues=result.get("issues", []),
            total_turns=len(conversation),
            total_retries=total_retries,
        )
