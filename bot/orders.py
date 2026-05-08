"""
Order placement logic.

Each function builds the correct Binance API payload and delegates
to BinanceClient.place_order(). TWAP is implemented as a sequence
of small market orders with configurable slice count and interval.
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Optional, Callable

from .client import BinanceClient
from .logging_config import get_logger

logger = get_logger("orders")


def _decimal_to_str(value: Decimal) -> str:
    """Format Decimal without scientific notation."""
    return format(value, "f")


def place_market_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    dry_run: bool = False,
) -> dict:
    """
    Place a MARKET order on Binance Futures.
    Returns the raw API response dict.
    """
    params = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": _decimal_to_str(quantity),
    }
    logger.info(
        "Placing MARKET order",
        extra={"symbol": symbol, "side": side, "quantity": str(quantity), "dry_run": dry_run},
    )

    if dry_run:
        return _dry_run_response(params)

    response = client.place_order(**params)
    logger.info("MARKET order placed", extra={"orderId": response.get("orderId"), "status": response.get("status")})
    return response


def place_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    time_in_force: str = "GTC",
    dry_run: bool = False,
) -> dict:
    """
    Place a LIMIT order on Binance Futures.
    time_in_force: GTC (Good Till Cancelled), IOC, FOK
    """
    params = {
        "symbol": symbol,
        "side": side,
        "type": "LIMIT",
        "quantity": _decimal_to_str(quantity),
        "price": _decimal_to_str(price),
        "timeInForce": time_in_force,
    }
    logger.info(
        "Placing LIMIT order",
        extra={
            "symbol": symbol, "side": side,
            "quantity": str(quantity), "price": str(price),
            "timeInForce": time_in_force, "dry_run": dry_run,
        },
    )

    if dry_run:
        return _dry_run_response(params)

    response = client.place_order(**params)
    logger.info("LIMIT order placed", extra={"orderId": response.get("orderId"), "status": response.get("status")})
    return response


def place_stop_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    stop_price: Decimal,
    time_in_force: str = "GTC",
    dry_run: bool = False,
) -> dict:
    """
    Place a STOP_MARKET / STOP order (stop-limit) on Binance Futures.
    Binance Futures uses type=STOP for stop-limit orders.
    """
    params = {
        "symbol": symbol,
        "side": side,
        "type": "STOP_MARKET",
        "algoType": "CONDITIONAL",
        "orderType": "STOP_MARKET",
        "quantity": _decimal_to_str(quantity),
        "triggerPrice": _decimal_to_str(stop_price),
    }
    logger.info(
        "Placing STOP_LIMIT order",
        extra={
            "symbol": symbol, "side": side,
            "quantity": str(quantity), "price": str(price),
            "stopPrice": str(stop_price), "dry_run": dry_run,
        },
    )

    if dry_run:
        return _dry_run_response(params)

    response = client.place_algo_order(**params)
    logger.info(
        "STOP_LIMIT order placed",
        extra={"orderId": response.get("orderId"), "status": response.get("status")},
    )
    return response


def place_twap_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    total_quantity: Decimal,
    slices: int,
    interval_seconds: int,
    price_hint: Optional[Decimal] = None,
    dry_run: bool = False,
    progress_callback: Optional[Callable[[int, int, dict], None]] = None,
) -> list[dict]:
    """
    TWAP (Time-Weighted Average Price) order: splits total_quantity into
    `slices` equal child market orders placed `interval_seconds` apart.

    Args:
        progress_callback: called after each slice with (slice_index, total_slices, response)
    Returns:
        List of individual slice responses.
    """
    slice_qty = (total_quantity / slices).quantize(Decimal("0.001"))
    # Adjust last slice for rounding
    last_slice_qty = total_quantity - slice_qty * (slices - 1)

    logger.info(
        "Starting TWAP order",
        extra={
            "symbol": symbol, "side": side,
            "total_quantity": str(total_quantity),
            "slices": slices,
            "slice_qty": str(slice_qty),
            "interval_seconds": interval_seconds,
            "dry_run": dry_run,
        },
    )

    responses = []
    for i in range(slices):
        qty = last_slice_qty if i == slices - 1 else slice_qty
        logger.debug(f"TWAP slice {i+1}/{slices}", extra={"qty": str(qty)})

        if dry_run:
            resp = _dry_run_response({
                "symbol": symbol, "side": side, "type": "MARKET",
                "quantity": _decimal_to_str(qty), "_twap_slice": f"{i+1}/{slices}",
            })
        else:
            resp = client.place_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=_decimal_to_str(qty),
            )

        resp["_twap_slice"] = f"{i + 1}/{slices}"
        responses.append(resp)

        if progress_callback:
            progress_callback(i + 1, slices, resp)

        if i < slices - 1:
            time.sleep(interval_seconds)

    logger.info(
        "TWAP order complete",
        extra={"slices_executed": len(responses), "symbol": symbol},
    )
    return responses


# ------------------------------------------------------------------
# Dry-run helper
# ------------------------------------------------------------------

def _dry_run_response(params: dict) -> dict:
    """Return a simulated response for dry-run mode."""
    return {
        "orderId": 0,
        "symbol": params.get("symbol", ""),
        "status": "DRY_RUN",
        "side": params.get("side", ""),
        "type": params.get("type", ""),
        "origQty": params.get("quantity", "0"),
        "executedQty": "0",
        "avgPrice": "0",
        "price": params.get("price", "0"),
        "_dry_run": True,
    }
