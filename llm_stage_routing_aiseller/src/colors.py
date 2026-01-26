"""
Terminal colors for pretty output.

Provides ANSI color codes for terminal output.
Can be disabled for environments that don't support colors.
"""

# ANSI color codes
class Colors:
    # Reset
    RESET = "\033[0m"
    
    # Regular colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright/Bold colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # Styles
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"


# Global flag to enable/disable colors
_colors_enabled = True


def set_colors_enabled(enabled: bool) -> None:
    """Enable or disable colored output."""
    global _colors_enabled
    _colors_enabled = enabled


def is_colors_enabled() -> bool:
    """Check if colors are enabled."""
    return _colors_enabled


def colorize(text: str, color: str) -> str:
    """Apply color to text if colors are enabled."""
    if _colors_enabled:
        return f"{color}{text}{Colors.RESET}"
    return text


# Convenience functions for common uses
def bot_message(text: str) -> str:
    """Format a bot message (cyan/blue)."""
    return colorize(text, Colors.CYAN)


def user_message(text: str) -> str:
    """Format a user/customer message (green)."""
    return colorize(text, Colors.GREEN)


def system_message(text: str) -> str:
    """Format a system/debug message (yellow)."""
    return colorize(text, Colors.YELLOW)


def error_message(text: str) -> str:
    """Format an error message (red)."""
    return colorize(text, Colors.RED)


def success_message(text: str) -> str:
    """Format a success message (bright green)."""
    return colorize(text, Colors.BRIGHT_GREEN)


def header(text: str) -> str:
    """Format a header (bold magenta)."""
    return colorize(text, Colors.BOLD + Colors.MAGENTA)


def dim(text: str) -> str:
    """Format dimmed text."""
    return colorize(text, Colors.DIM)


def bold(text: str) -> str:
    """Format bold text."""
    return colorize(text, Colors.BOLD)


# Labels with colors
def bot_label() -> str:
    """Get the colored 'Bot:' label."""
    return colorize("Bot:", Colors.BOLD + Colors.CYAN)


def user_label() -> str:
    """Get the colored 'You:' label."""
    return colorize("You:", Colors.BOLD + Colors.GREEN)


def customer_label() -> str:
    """Get the colored 'Customer:' label."""
    return colorize("Customer:", Colors.BOLD + Colors.GREEN)


def debug_label() -> str:
    """Get the colored '[DEBUG]' label."""
    return colorize("[DEBUG]", Colors.YELLOW)
