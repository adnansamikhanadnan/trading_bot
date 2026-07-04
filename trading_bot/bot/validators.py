"""
Input validation for order requests.

Kept independent of the API layer so validation logic can be unit-tested
without any network access, and reused by both the CLI and any future
interfaces (e.g. a UI or REST wrapper).
"""

import re
from dataclasses import dataclass
from typing import Optional

SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,20}$")
VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_LIMIT"}


class ValidationError(ValueError):
    """Raised when user-supplied order parameters fail validation."""


@dataclass
class OrderRequest:
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"


def validate_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not SYMBOL_RE.match(symbol):
        raise ValidationError(
            f"Invalid symbol '{symbol}'. Expected format like 'BTCUSDT' "
            "(5-20 uppercase letters/digits)."
        )
    return symbol


def validate_side(side: str) -> str:
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValidationError(f"Invalid side '{side}'. Must be one of {sorted(VALID_SIDES)}.")
    return side


def validate_order_type(order_type: str) -> str:
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Invalid order type '{order_type}'. Must be one of {sorted(VALID_ORDER_TYPES)}."
        )
    return order_type


def validate_quantity(quantity) -> float:
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        raise ValidationError(f"Quantity must be a number, got '{quantity}'.")
    if quantity <= 0:
        raise ValidationError(f"Quantity must be greater than 0, got {quantity}.")
    return quantity


def validate_price(price, field_name: str = "price") -> float:
    try:
        price = float(price)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a number, got '{price}'.")
    if price <= 0:
        raise ValidationError(f"{field_name} must be greater than 0, got {price}.")
    return price


def build_order_request(
    symbol: str,
    side: str,
    order_type: str,
    quantity,
    price=None,
    stop_price=None,
    time_in_force: str = "GTC",
) -> OrderRequest:
    """
    Validate all fields and return a well-formed OrderRequest.

    Raises ValidationError on any invalid or missing field.
    """
    symbol = validate_symbol(symbol)
    side = validate_side(side)
    order_type = validate_order_type(order_type)
    quantity = validate_quantity(quantity)

    parsed_price = None
    parsed_stop_price = None

    if order_type == "LIMIT":
        if price is None:
            raise ValidationError("price is required for LIMIT orders.")
        parsed_price = validate_price(price, "price")

    elif order_type == "STOP_LIMIT":
        if price is None:
            raise ValidationError("price is required for STOP_LIMIT orders.")
        if stop_price is None:
            raise ValidationError("stop_price is required for STOP_LIMIT orders.")
        parsed_price = validate_price(price, "price")
        parsed_stop_price = validate_price(stop_price, "stop_price")

    elif order_type == "MARKET":
        if price is not None:
            raise ValidationError("price must not be provided for MARKET orders.")

    return OrderRequest(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=parsed_price,
        stop_price=parsed_stop_price,
        time_in_force=time_in_force.strip().upper() if time_in_force else "GTC",
    )
