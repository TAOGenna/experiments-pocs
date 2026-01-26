"""
Tools for the ReAct agent.

These are the tools the agent can use during its reasoning loop.
Unlike the stage-routing approach where tools are called deterministically,
here the LLM decides when and how to use them.

IMPORTANT: All cart operations use the CartStore for reliable persistence.
"""

import json
import uuid
from typing import Optional

from langchain_core.tools import tool

from src.catalog import CATALOG
from src.cart_store import cart_store


@tool
def search_products(
    category: Optional[str] = None,
    keywords: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    color: Optional[str] = None,
    size: Optional[str] = None,
    limit: int = 5,
) -> str:
    """
    Search the product catalog with optional filters.
    
    Use this tool to find products based on user preferences.
    
    Args:
        category: Product category (shoes, headphones, backpacks, jackets, watches)
        keywords: Comma-separated keywords to search for (e.g., "running, lightweight")
        price_min: Minimum price in PEN
        price_max: Maximum price in PEN
        color: Preferred color
        size: Preferred size
        limit: Maximum number of products to return (default 5)
    
    Returns:
        JSON string with matching products
    """
    keyword_list = []
    if keywords:
        keyword_list = [k.strip().lower() for k in keywords.split(",")]
    
    results = []
    
    for product in CATALOG:
        # Filter: must be in stock
        if not product.get("in_stock", False):
            continue
        
        # Filter: category
        if category and product.get("category", "").lower() != category.lower():
            continue
        
        # Filter: price range
        price = product.get("price", 0)
        if price_min is not None and price < price_min:
            continue
        if price_max is not None and price > price_max:
            continue
        
        # Filter: color
        if color and product.get("color", "").lower() != color.lower():
            continue
        
        # Filter: size
        if size:
            sizes = [s.lower() for s in product.get("size", [])]
            if size.lower() not in sizes:
                continue
        
        # Calculate relevance score
        score = 0
        search_text = (
            product.get("title", "").lower() + " " +
            " ".join(product.get("tags", [])).lower() + " " +
            product.get("description", "").lower()
        )
        for kw in keyword_list:
            if kw in product.get("title", "").lower():
                score += 3
            if any(kw in tag.lower() for tag in product.get("tags", [])):
                score += 2
            if kw in search_text:
                score += 1
        
        results.append((score, product))
    
    # Sort by relevance
    results.sort(key=lambda x: -x[0])
    results = results[:limit]
    
    if not results:
        return json.dumps({"products": [], "message": "No products found matching your criteria"})
    
    # Format results
    products = []
    for _, p in results:
        products.append({
            "id": p["id"],
            "title": p["title"],
            "price": p["price"],
            "currency": p.get("currency", "PEN"),
            "brand": p.get("brand", ""),
            "color": p.get("color", ""),
            "sizes": p.get("size", []),
            "description": p.get("description", "")[:100],
        })
    
    return json.dumps({"products": products, "count": len(products)})


@tool
def add_to_cart(product_id: str) -> str:
    """
    Add a product to the shopping cart.
    
    Use this when the user wants to select/buy a specific product.
    IMPORTANT: Call this ONCE for EACH product the user wants to add.
    
    Args:
        product_id: The ID of the product to add (e.g., "p_001")
    
    Returns:
        Confirmation message with product details and current cart total
    """
    # Use CartStore for persistent storage
    result = cart_store.add_item(product_id)
    return json.dumps(result)


@tool
def remove_from_cart(product_id: str) -> str:
    """
    Remove a product from the shopping cart.
    
    Use this when the user wants to remove an item they previously added.
    
    Args:
        product_id: The ID of the product to remove
    
    Returns:
        Confirmation of removal and updated cart total
    """
    result = cart_store.remove_item(product_id)
    return json.dumps(result)


@tool
def get_cart() -> str:
    """
    Get the current cart contents with details and total.
    
    Use this to show the user what's in their cart.
    No arguments needed - returns the current cart state.
    
    Returns:
        Cart contents with product details and total
    """
    cart_details = cart_store.get_cart_details()
    cart_total = cart_store.get_total()
    
    if not cart_details:
        return json.dumps({
            "products": [],
            "total": 0,
            "count": 0,
            "message": "Cart is empty"
        })
    
    return json.dumps({
        "products": cart_details,
        "total": cart_total,
        "currency": "PEN",
        "count": len(cart_details),
        "summary": cart_store.get_cart_summary()
    })


@tool
def update_checkout_info(
    name: Optional[str] = None,
    address: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> str:
    """
    Update or collect checkout information.
    
    Use this to store shipping and payment details.
    IMPORTANT: Use EXACTLY what the customer provided - do not modify or guess!
    
    Args:
        name: Customer's full name (use EXACTLY what they said)
        address: Shipping address (use EXACTLY what they said)
        payment_method: Payment method - must be "cash", "card", or "transfer"
    
    Returns:
        Current checkout status and any missing fields
    """
    # Use CartStore for persistent storage with automatic normalization
    result = cart_store.set_checkout_info(
        name=name,
        address=address,
        payment_method=payment_method,
    )
    return json.dumps(result)


@tool
def get_checkout_info() -> str:
    """
    Get the current checkout information.
    
    Use this to check what shipping/payment info has been collected.
    
    Returns:
        Current checkout info and missing fields
    """
    info = cart_store.get_checkout_info()
    return json.dumps(info)


@tool
def confirm_order() -> str:
    """
    Confirm and create the final order.
    
    Use this ONLY when:
    1. Cart has items
    2. ALL checkout info is complete (name, address, payment_method)
    3. User explicitly confirms they want to place the order
    
    Returns:
        Order confirmation with order ID, or error if not ready
    """
    # Check if cart has items
    cart_items = cart_store.get_cart()
    if not cart_items:
        return json.dumps({
            "success": False,
            "error": "Cart is empty. Cannot confirm order."
        })
    
    # Check if checkout is complete
    checkout_info = cart_store.get_checkout_info()
    if not checkout_info.get("is_complete"):
        missing = checkout_info.get("missing_fields", [])
        return json.dumps({
            "success": False,
            "error": f"Checkout incomplete. Missing: {', '.join(missing)}"
        })
    
    # Generate order ID
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    # Get cart details for confirmation
    cart_details = cart_store.get_cart_details()
    cart_total = cart_store.get_total()
    
    # Build order response
    order = {
        "success": True,
        "order_id": order_id,
        "products": cart_details,
        "total": cart_total,
        "currency": "PEN",
        "shipping": {
            "name": checkout_info.get("name"),
            "address": checkout_info.get("address"),
        },
        "payment_method": checkout_info.get("payment_method"),
        "message": f"Order {order_id} confirmed! Thank you for your purchase."
    }
    
    # Clear cart and checkout for next order
    cart_store.full_reset()
    
    return json.dumps(order)


# List of all tools for the agent
REACT_TOOLS = [
    search_products,
    add_to_cart,
    remove_from_cart,
    get_cart,
    update_checkout_info,
    get_checkout_info,
    confirm_order,
]
