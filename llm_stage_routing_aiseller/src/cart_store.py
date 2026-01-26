"""
Cart Store - Global persistent cart manager.

This solves the cart persistence problem by providing a central store
that both Stage-Routing and ReAct architectures can use.

Instead of relying on LangGraph state passing (which can lose state),
all cart operations go through this store.

Usage:
    from src.cart_store import cart_store
    
    # Add item
    cart_store.add_item("p_001")
    
    # Get cart contents with details
    items = cart_store.get_cart_details()
    
    # Get total
    total = cart_store.get_total()
    
    # Clear (for new session)
    cart_store.clear()
"""

from dataclasses import dataclass, field
from typing import Optional

from src.catalog import CATALOG


@dataclass
class CartItem:
    """A single item in the cart."""
    product_id: str
    title: str
    price: float
    currency: str = "PEN"
    quantity: int = 1


class CartStore:
    """
    Singleton cart store for reliable cart persistence.
    
    This is the single source of truth for cart state.
    Both Stage-Routing nodes and ReAct tools use this.
    """
    
    _instance: Optional["CartStore"] = None
    
    def __new__(cls) -> "CartStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._items = {}  # product_id -> CartItem
            cls._instance._checkout_info = {
                "name": None,
                "address": None,
                "payment_method": None,
            }
        return cls._instance
    
    @property
    def items(self) -> dict[str, CartItem]:
        """Get all items in cart."""
        return self._items
    
    def add_item(self, product_id: str) -> dict:
        """
        Add a product to the cart.
        
        Args:
            product_id: The product ID (e.g., "p_001")
            
        Returns:
            Dict with success status and product details
        """
        # Find product in catalog
        product = None
        for p in CATALOG:
            if p["id"] == product_id:
                product = p
                break
        
        if not product:
            return {
                "success": False,
                "error": f"Product {product_id} not found in catalog"
            }
        
        if not product.get("in_stock", False):
            return {
                "success": False,
                "error": f"Product {product['title']} is out of stock"
            }
        
        # Add to cart (or increment quantity if already exists)
        if product_id in self._items:
            self._items[product_id].quantity += 1
        else:
            self._items[product_id] = CartItem(
                product_id=product_id,
                title=product["title"],
                price=product["price"],
                currency=product.get("currency", "PEN"),
                quantity=1,
            )
        
        return {
            "success": True,
            "product_id": product_id,
            "title": product["title"],
            "price": product["price"],
            "cart_count": len(self._items),
            "cart_total": self.get_total(),
            "message": f"Added {product['title']} to cart. Cart now has {len(self._items)} item(s), total: {self.get_total()} PEN"
        }
    
    def remove_item(self, product_id: str) -> dict:
        """
        Remove a product from the cart.
        
        Args:
            product_id: The product ID to remove
            
        Returns:
            Dict with success status
        """
        if product_id not in self._items:
            return {
                "success": False,
                "error": f"Product {product_id} not in cart"
            }
        
        item = self._items.pop(product_id)
        return {
            "success": True,
            "removed": item.title,
            "cart_count": len(self._items),
            "cart_total": self.get_total(),
            "message": f"Removed {item.title} from cart"
        }
    
    def get_cart(self) -> list[str]:
        """Get list of product IDs in cart."""
        return list(self._items.keys())
    
    def get_cart_details(self) -> list[dict]:
        """
        Get detailed cart contents.
        
        Returns:
            List of dicts with product details
        """
        return [
            {
                "product_id": item.product_id,
                "title": item.title,
                "price": item.price,
                "currency": item.currency,
                "quantity": item.quantity,
                "subtotal": item.price * item.quantity,
            }
            for item in self._items.values()
        ]
    
    def get_total(self) -> float:
        """Calculate cart total."""
        return sum(item.price * item.quantity for item in self._items.values())
    
    def get_cart_summary(self) -> str:
        """
        Get a human-readable cart summary.
        
        Returns:
            String summary of cart contents and total
        """
        if not self._items:
            return "Cart is empty"
        
        lines = []
        for item in self._items.values():
            if item.quantity > 1:
                lines.append(f"- {item.title} x{item.quantity}: {item.price * item.quantity} {item.currency}")
            else:
                lines.append(f"- {item.title}: {item.price} {item.currency}")
        
        lines.append(f"Total: {self.get_total()} PEN")
        return "\n".join(lines)
    
    def is_empty(self) -> bool:
        """Check if cart is empty."""
        return len(self._items) == 0
    
    def clear(self) -> dict:
        """
        Clear all items from cart.
        
        Returns:
            Confirmation dict
        """
        count = len(self._items)
        self._items = {}
        return {
            "success": True,
            "items_removed": count,
            "message": "Cart cleared"
        }
    
    # Checkout info management
    def set_checkout_info(
        self,
        name: Optional[str] = None,
        address: Optional[str] = None,
        payment_method: Optional[str] = None,
    ) -> dict:
        """
        Update checkout information.
        
        Args:
            name: Customer name
            address: Shipping address
            payment_method: Payment method (cash/card/transfer)
            
        Returns:
            Dict with current checkout state
        """
        if name:
            self._checkout_info["name"] = name
        if address:
            self._checkout_info["address"] = address
        if payment_method:
            # Normalize payment method
            pm_lower = payment_method.lower().strip()
            if pm_lower in ["transfer", "transferencia", "bank transfer", "bank_transfer", "wire", "wire transfer"]:
                self._checkout_info["payment_method"] = "transfer"
            elif pm_lower in ["card", "tarjeta", "credit card", "debit card", "credit", "debit"]:
                self._checkout_info["payment_method"] = "card"
            elif pm_lower in ["cash", "efectivo", "dinero", "money"]:
                self._checkout_info["payment_method"] = "cash"
            else:
                # Try to keep it if it looks valid
                if pm_lower in ["cash", "card", "transfer"]:
                    self._checkout_info["payment_method"] = pm_lower
                else:
                    return {
                        "success": False,
                        "error": f"Unknown payment method: {payment_method}. Use 'cash', 'card', or 'transfer'",
                        "current_info": self._checkout_info,
                    }
        
        return {
            "success": True,
            "current_info": self._checkout_info.copy(),
            "is_complete": self.is_checkout_complete(),
            "missing_fields": self.get_missing_checkout_fields(),
        }
    
    def get_checkout_info(self) -> dict:
        """Get current checkout information."""
        return {
            **self._checkout_info,
            "is_complete": self.is_checkout_complete(),
            "missing_fields": self.get_missing_checkout_fields(),
        }
    
    def is_checkout_complete(self) -> bool:
        """Check if all checkout fields are filled."""
        return all([
            self._checkout_info["name"],
            self._checkout_info["address"],
            self._checkout_info["payment_method"],
        ])
    
    def get_missing_checkout_fields(self) -> list[str]:
        """Get list of missing checkout fields."""
        missing = []
        if not self._checkout_info["name"]:
            missing.append("name")
        if not self._checkout_info["address"]:
            missing.append("address")
        if not self._checkout_info["payment_method"]:
            missing.append("payment_method")
        return missing
    
    def reset_checkout(self) -> None:
        """Reset checkout info (but keep cart)."""
        self._checkout_info = {
            "name": None,
            "address": None,
            "payment_method": None,
        }
    
    def full_reset(self) -> None:
        """
        Full reset - clear cart AND checkout info.
        Call this at the start of each evaluation scenario.
        """
        self._items = {}
        self._checkout_info = {
            "name": None,
            "address": None,
            "payment_method": None,
        }


# Global singleton instance
cart_store = CartStore()
