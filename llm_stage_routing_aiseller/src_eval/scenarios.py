"""
Test scenarios for automated evaluation.

Each scenario defines:
- A script of customer intents/goals
- Expected outcomes (cart items, total, etc.)
- Evaluation criteria
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScenarioStep:
    """A single step in the customer journey."""
    intent: str  # What the customer wants to achieve
    example_message: str  # Example of what they might say
    required: bool = True  # Must this step succeed?
    max_retries: int = 3  # How many times to retry if bot doesn't understand


@dataclass
class ExpectedOutcome:
    """Expected result of the scenario."""
    cart_items: list[str]  # Product IDs or partial titles expected in cart
    total_price: Optional[float] = None  # Expected total (approximate)
    order_confirmed: bool = True  # Should order be confirmed?
    checkout_fields: dict = field(default_factory=dict)  # Expected checkout info


@dataclass
class Scenario:
    """A complete test scenario."""
    name: str
    description: str
    steps: list[ScenarioStep]
    expected: ExpectedOutcome
    
    def __post_init__(self):
        """Ensure scenario has an ID."""
        self.id = self.name.lower().replace(" ", "_")


# =============================================================================
# PREDEFINED SCENARIOS
# =============================================================================

SCENARIO_HEADPHONES_MULTI_PURCHASE = Scenario(
    name="Headphones Multi Purchase",
    description="Customer browses headphones and buys multiple items",
    steps=[
        ScenarioStep(
            intent="Ask what products are available",
            example_message="Hi, can you show me the kind of products you have?",
        ),
        ScenarioStep(
            intent="Request to see headphones specifically",
            example_message="Nice, show me some headphones please",
        ),
        ScenarioStep(
            intent="Select multiple products: Sport Earbuds Waterproof AND Studio Monitor Headphones",
            example_message="I would like to take both the Sport Earbuds Waterproof and the Studio Monitor Headphones",
        ),
        ScenarioStep(
            intent="Add another product: Budget Wireless Earbuds",
            example_message="Wait, I would also like to buy the Budget Wireless Earbuds",
        ),
        ScenarioStep(
            intent="Ask for cart total before providing personal info",
            example_message="Yes, but first can you tell me the total?",
        ),
        ScenarioStep(
            intent="Provide name and address",
            example_message="My name is Angel Guzman, address is Av Alejandro Bertello 8902",
        ),
        ScenarioStep(
            intent="Provide payment method",
            example_message="I will pay via transfer",
        ),
        ScenarioStep(
            intent="Confirm the order",
            example_message="Yes, confirm the order",
        ),
    ],
    expected=ExpectedOutcome(
        cart_items=["Sport Earbuds", "Studio Monitor", "Budget Wireless"],
        total_price=938.0,  # 199 + 650 + 89
        order_confirmed=True,
        checkout_fields={
            "name": "Angel Guzman",
            "address": "Alejandro Bertello",
            "payment_method": "transfer",
        },
    ),
)


SCENARIO_SIMPLE_SHOE_PURCHASE = Scenario(
    name="Simple Shoe Purchase",
    description="Customer buys a single pair of running shoes",
    steps=[
        ScenarioStep(
            intent="Ask for running shoes",
            example_message="Hi, I'm looking for some running shoes",
        ),
        ScenarioStep(
            intent="Select the first option",
            example_message="I'll take the first one",
        ),
        ScenarioStep(
            intent="Provide checkout info all at once",
            example_message="My name is Maria Lopez, address is Calle Lima 123, I'll pay with card",
        ),
        ScenarioStep(
            intent="Confirm order",
            example_message="Yes, confirm",
        ),
    ],
    expected=ExpectedOutcome(
        cart_items=["Running"],
        total_price=None,  # Any running shoe price is fine
        order_confirmed=True,
        checkout_fields={
            "name": "Maria Lopez",
            "payment_method": "card",
        },
    ),
)


SCENARIO_CATEGORY_SWITCH = Scenario(
    name="Category Switch",
    description="Customer starts with shoes but switches to backpacks",
    steps=[
        ScenarioStep(
            intent="Ask for shoes initially",
            example_message="Show me some shoes",
        ),
        ScenarioStep(
            intent="Change mind and ask for backpacks instead",
            example_message="Actually, show me backpacks instead",
        ),
        ScenarioStep(
            intent="Select a hiking backpack",
            example_message="I'll take the hiking backpack",
        ),
        ScenarioStep(
            intent="Complete checkout",
            example_message="Name: Carlos Ruiz, Address: Jr. Amazonas 456, Payment: cash",
        ),
        ScenarioStep(
            intent="Confirm",
            example_message="Confirm order",
        ),
    ],
    expected=ExpectedOutcome(
        cart_items=["Hiking", "Backpack"],
        order_confirmed=True,
        checkout_fields={
            "name": "Carlos Ruiz",
            "payment_method": "cash",
        },
    ),
)


# =============================================================================
# NEW EDGE CASE SCENARIOS
# =============================================================================

SCENARIO_VAGUE_REQUEST = Scenario(
    name="Vague Request Discovery",
    description="Customer starts with vague request, needs guided discovery",
    steps=[
        ScenarioStep(
            intent="Start with a vague request for a gift",
            example_message="Hi, I need something for a birthday gift, not sure what though",
        ),
        ScenarioStep(
            intent="When asked, show interest in technology/gadgets",
            example_message="Maybe something techy? They like music",
        ),
        ScenarioStep(
            intent="Ask to see options within a budget",
            example_message="What do you have under 200 soles?",
        ),
        ScenarioStep(
            intent="Select the Budget Wireless Earbuds",
            example_message="The budget wireless earbuds sound good, I'll take those",
        ),
        ScenarioStep(
            intent="Provide all checkout info",
            example_message="Name: Pedro Sanchez, Address: Av Los Olivos 234, Payment: card",
        ),
        ScenarioStep(
            intent="Confirm order",
            example_message="Yes, confirm",
        ),
    ],
    expected=ExpectedOutcome(
        cart_items=["Budget Wireless"],
        total_price=89.0,
        order_confirmed=True,
        checkout_fields={
            "name": "Pedro Sanchez",
            "payment_method": "card",
        },
    ),
)


SCENARIO_BUDGET_CONSTRAINT = Scenario(
    name="Budget Constraint",
    description="Customer has strict budget, wants cheapest options",
    steps=[
        ScenarioStep(
            intent="Ask for watches with budget constraint",
            example_message="Show me watches, but I only have 150 soles to spend",
        ),
        ScenarioStep(
            intent="Ask if there's anything cheaper",
            example_message="Is there anything cheaper? That's still over my budget",
        ),
        ScenarioStep(
            intent="Accept the cheapest option available or ask for alternatives",
            example_message="What's the cheapest thing you have in the store then?",
        ),
        ScenarioStep(
            intent="Select whatever cheap option is shown",
            example_message="Fine, I'll take that one",
        ),
        ScenarioStep(
            intent="Provide checkout info",
            example_message="Ana Torres, Jr. Union 567, cash payment",
        ),
        ScenarioStep(
            intent="Confirm",
            example_message="Confirm order",
        ),
    ],
    expected=ExpectedOutcome(
        cart_items=[],  # Flexible - any product they end up with
        total_price=None,  # Accept any price since user accepted it
        order_confirmed=True,
        checkout_fields={
            "name": "Ana Torres",
            "payment_method": "cash",
        },
    ),
)


SCENARIO_CHANGE_MIND_MID_CART = Scenario(
    name="Change Mind Mid Cart",
    description="Customer selects a product but changes mind before checkout",
    steps=[
        ScenarioStep(
            intent="Ask for jackets",
            example_message="Show me some jackets please",
        ),
        ScenarioStep(
            intent="Select the first jacket option",
            example_message="I'll take the first one",
        ),
        ScenarioStep(
            intent="Change mind and ask for a different one instead",
            example_message="Actually wait, I changed my mind. Can I see the other jackets again?",
        ),
        ScenarioStep(
            intent="Select a different jacket (the waterproof one)",
            example_message="I'll take the waterproof rain jacket instead",
        ),
        ScenarioStep(
            intent="Provide checkout info",
            example_message="Roberto Diaz, Calle Sol 890, transfer",
        ),
        ScenarioStep(
            intent="Confirm order",
            example_message="Yes, confirm please",
        ),
    ],
    expected=ExpectedOutcome(
        cart_items=["Rain Jacket", "Waterproof"],  # Should have the waterproof one
        order_confirmed=True,
        checkout_fields={
            "name": "Roberto Diaz",
            "payment_method": "transfer",
        },
    ),
)


SCENARIO_MULTI_CATEGORY_PURCHASE = Scenario(
    name="Multi Category Purchase",
    description="Customer buys from multiple categories in one session",
    steps=[
        ScenarioStep(
            intent="Ask for running shoes",
            example_message="I need some running shoes",
        ),
        ScenarioStep(
            intent="Select a running shoe",
            example_message="I'll take the Sprint Lite ones",
        ),
        ScenarioStep(
            intent="Also ask for a backpack",
            example_message="I also need a backpack, what do you have?",
        ),
        ScenarioStep(
            intent="Select a backpack",
            example_message="The urban commuter backpack looks good, add that too",
        ),
        ScenarioStep(
            intent="Ask for cart total",
            example_message="What's my total?",
        ),
        ScenarioStep(
            intent="Provide checkout info",
            example_message="Sofia Vargas, Av Brasil 1234, card",
        ),
        ScenarioStep(
            intent="Confirm order",
            example_message="Confirm",
        ),
    ],
    expected=ExpectedOutcome(
        cart_items=["Sprint Lite", "Urban Commuter"],
        total_price=388.0,  # 199 + 189
        order_confirmed=True,
        checkout_fields={
            "name": "Sofia Vargas",
            "payment_method": "card",
        },
    ),
)


SCENARIO_PRICE_INQUIRY_NO_PURCHASE = Scenario(
    name="Price Inquiry Only",
    description="Customer asks about prices but doesn't complete purchase",
    steps=[
        ScenarioStep(
            intent="Ask about watch prices",
            example_message="How much are your watches?",
        ),
        ScenarioStep(
            intent="Ask about a specific watch price",
            example_message="What about the smartwatch?",
        ),
        ScenarioStep(
            intent="Say it's too expensive and ask about headphones instead",
            example_message="That's too expensive. What about headphones, how much are those?",
        ),
        ScenarioStep(
            intent="Thank them and say you'll think about it",
            example_message="Thanks for the info, I'll think about it and come back later",
        ),
    ],
    expected=ExpectedOutcome(
        cart_items=[],  # No purchase
        total_price=None,
        order_confirmed=False,  # No order should be confirmed
        checkout_fields={},
    ),
)


# All available scenarios
SCENARIOS = {
    "headphones_multi": SCENARIO_HEADPHONES_MULTI_PURCHASE,
    "simple_shoe": SCENARIO_SIMPLE_SHOE_PURCHASE,
    "category_switch": SCENARIO_CATEGORY_SWITCH,
    "vague_request": SCENARIO_VAGUE_REQUEST,
    "budget_constraint": SCENARIO_BUDGET_CONSTRAINT,
    "change_mind": SCENARIO_CHANGE_MIND_MID_CART,
    "multi_category": SCENARIO_MULTI_CATEGORY_PURCHASE,
    "price_inquiry": SCENARIO_PRICE_INQUIRY_NO_PURCHASE,
}
