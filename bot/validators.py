"""
Input validators for CLI arguments.
All validators raise ValueError with actionable messages on bad input.
"""

from __future__ import annotations
from decimal import Decimal, InvalidOperation
from typing import Optional


VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_LIMIT", "TWAP"}

# Binance symbol conventions
MIN_QUANTITY = Decimal("0.001")
MAX_QUANTITY = Decimal("1_000_000")


class ValidationError(ValueError):
    """Raised when user input fails validation."""


def validate_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValidationError("Symbol cannot be empty.")
    if not symbol.isalnum():
        raise ValidationError(f"Symbol '{symbol}' must be alphanumeric (e.g. BTCUSDT).")
    if len(symbol) < 5 or len(symbol) > 12:
        raise ValidationError(f"Symbol '{symbol}' looks invalid — expected 5–12 chars (e.g. BTCUSDT).")
    return symbol


def validate_side(side: str) -> str:
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValidationError(
            f"Side must be one of {sorted(VALID_SIDES)}, got '{side}'."
        )
    return side


def validate_order_type(order_type: str) -> str:
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Order type must be one of {sorted(VALID_ORDER_TYPES)}, got '{order_type}'."
        )
    return order_type


def validate_quantity(quantity: str | float) -> Decimal:
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValidationError(f"Quantity '{quantity}' is not a valid number.")
    if qty <= 0:
        raise ValidationError(f"Quantity must be positive, got {qty}.")
    if qty < MIN_QUANTITY:
        raise ValidationError(f"Quantity {qty} is below minimum allowed ({MIN_QUANTITY}).")
    if qty > MAX_QUANTITY:
        raise ValidationError(f"Quantity {qty} exceeds maximum allowed ({MAX_QUANTITY}).")
    return qty


def validate_price(price: Optional[str | float], *, required: bool = False) -> Optional[Decimal]:
    if price is None or str(price).strip() == "":
        if required:
            raise ValidationError("Price is required for this order type.")
        return None
    try:
        p = Decimal(str(price))
    except InvalidOperation:
        raise ValidationError(f"Price '{price}' is not a valid number.")
    if p <= 0:
        raise ValidationError(f"Price must be positive, got {p}.")
    return p


def validate_twap_slices(slices: int) -> int:
    if not isinstance(slices, int) or slices < 2:
        raise ValidationError("TWAP slices must be an integer >= 2.")
    if slices > 20:
        raise ValidationError("TWAP slices capped at 20 to avoid excessive API calls.")
    return slices


def validate_twap_interval(interval: int) -> int:
    if not isinstance(interval, int) or interval < 1:
        raise ValidationError("TWAP interval must be >= 1 second.")
    if interval > 300:
        raise ValidationError("TWAP interval capped at 300 seconds.")
    return interval


def validate_order_params(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: Optional[str | float] = None,
    stop_price: Optional[str | float] = None,
    twap_slices: Optional[int] = None,
    twap_interval: Optional[int] = None,
) -> dict:
    """
    Validate all order parameters together and return a clean, typed dict.
    Raises ValidationError with a clear message on the first failure.
    """
    result: dict = {}
    result["symbol"] = validate_symbol(symbol)
    result["side"] = validate_side(side)
    result["order_type"] = validate_order_type(order_type)
    result["quantity"] = validate_quantity(quantity)

    if result["order_type"] == "LIMIT":
        result["price"] = validate_price(price, required=True)

    elif result["order_type"] == "STOP_LIMIT":
        result["price"] = validate_price(price, required=True)
        result["stop_price"] = validate_price(stop_price, required=True)

    elif result["order_type"] == "TWAP":
        result["price"] = validate_price(price)  # optional price hint
        result["twap_slices"] = validate_twap_slices(twap_slices or 5)
        result["twap_interval"] = validate_twap_interval(twap_interval or 10)

    return result
