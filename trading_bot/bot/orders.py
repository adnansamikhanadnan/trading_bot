"""
Order orchestration layer: sits between the CLI and the API client.

Responsible for:
  - turning a validated OrderRequest into an API call
  - logging a human-readable request summary and response summary
  - normalizing the response into a simple result dict for the CLI to print
"""

import logging
from typing import Any, Dict

from .client import BinanceAPIError, BinanceFuturesClient, BinanceNetworkError
from .validators import OrderRequest

logger = logging.getLogger("trading_bot.orders")


class OrderExecutionError(Exception):
    """Raised when an order could not be placed, wrapping the root cause."""


def summarize_request(order: OrderRequest) -> str:
    parts = [
        f"symbol={order.symbol}",
        f"side={order.side}",
        f"type={order.order_type}",
        f"quantity={order.quantity}",
    ]
    if order.price is not None:
        parts.append(f"price={order.price}")
    if order.stop_price is not None:
        parts.append(f"stop_price={order.stop_price}")
    if order.order_type in ("LIMIT", "STOP_LIMIT"):
        parts.append(f"timeInForce={order.time_in_force}")
    return " | ".join(parts)


def summarize_response(response: Dict[str, Any]) -> str:
    fields = ["orderId", "status", "executedQty", "avgPrice", "origQty", "price"]
    present = {f: response.get(f) for f in fields if f in response}
    return " | ".join(f"{k}={v}" for k, v in present.items())


def place_order(client: BinanceFuturesClient, order: OrderRequest) -> Dict[str, Any]:
    """
    Place an order via the given client and return Binance's raw response.

    Raises OrderExecutionError (chaining the original exception) on any
    API or network failure, after logging the failure in detail.
    """
    logger.info("Placing order: %s", summarize_request(order))

    try:
        response = client.place_order(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            stop_price=order.stop_price,
            time_in_force=order.time_in_force,
        )
    except BinanceAPIError as exc:
        logger.error("Order rejected by Binance: %s", exc)
        raise OrderExecutionError(f"Order rejected by Binance: {exc.message} (code={exc.code})") from exc
    except BinanceNetworkError as exc:
        logger.error("Network failure while placing order: %s", exc)
        raise OrderExecutionError(f"Network failure while placing order: {exc}") from exc

    logger.info("Order placed successfully: %s", summarize_response(response))
    return response
