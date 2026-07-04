#!/usr/bin/env python3
"""
CLI entry point for the simplified Binance Futures Testnet trading bot.

Examples
--------
Market order (buy 0.01 BTCUSDT):
    python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

Limit order (sell 0.01 BTCUSDT at 65000):
    python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.01 --price 65000

Stop-limit order (bonus):
    python cli.py --symbol BTCUSDT --side SELL --type STOP_LIMIT --quantity 0.01 \\
        --price 64000 --stop-price 64500

Credentials are read from the BINANCE_API_KEY / BINANCE_API_SECRET
environment variables (see README.md), or can be passed explicitly with
--api-key / --api-secret for local testing only.
"""

import argparse
import os
import sys

from bot.client import BinanceAPIError, BinanceFuturesClient, BinanceNetworkError, DEFAULT_TESTNET_BASE_URL
from bot.logging_config import setup_logging
from bot.orders import OrderExecutionError, place_order, summarize_request, summarize_response
from bot.validators import ValidationError, build_order_request


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Place MARKET / LIMIT / STOP_LIMIT orders on Binance Futures Testnet (USDT-M).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--symbol", required=True, help="Trading pair, e.g. BTCUSDT")
    parser.add_argument("--side", required=True, choices=["BUY", "SELL", "buy", "sell"], help="Order side")
    parser.add_argument(
        "--type",
        dest="order_type",
        required=True,
        choices=["MARKET", "LIMIT", "STOP_LIMIT", "market", "limit", "stop_limit"],
        help="Order type",
    )
    parser.add_argument("--quantity", required=True, help="Order quantity (base asset units)")
    parser.add_argument("--price", default=None, help="Limit price (required for LIMIT / STOP_LIMIT)")
    parser.add_argument(
        "--stop-price", dest="stop_price", default=None, help="Stop trigger price (required for STOP_LIMIT)"
    )
    parser.add_argument(
        "--time-in-force", dest="time_in_force", default="GTC", help="Time in force for LIMIT/STOP_LIMIT orders"
    )
    parser.add_argument(
        "--base-url", default=DEFAULT_TESTNET_BASE_URL, help="Binance Futures API base URL"
    )
    parser.add_argument(
        "--api-key", default=os.environ.get("BINANCE_API_KEY"), help="API key (defaults to BINANCE_API_KEY env var)"
    )
    parser.add_argument(
        "--api-secret",
        default=os.environ.get("BINANCE_API_SECRET"),
        help="API secret (defaults to BINANCE_API_SECRET env var)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log verbosity (file log always captures DEBUG)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the order without sending it to Binance",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logger = setup_logging(args.log_level)

    # --- 1. Validate input -------------------------------------------------
    try:
        order = build_order_request(
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            price=args.price,
            stop_price=args.stop_price,
            time_in_force=args.time_in_force,
        )
    except ValidationError as exc:
        logger.error("Input validation failed: %s", exc)
        print(f"❌ Invalid input: {exc}")
        return 2

    print("Order request:")
    print(f"  {summarize_request(order)}")

    if args.dry_run:
        print("✅ Dry run only — no request sent to Binance.")
        return 0

    # --- 2. Check credentials ----------------------------------------------
    if not args.api_key or not args.api_secret:
        logger.error("Missing API credentials.")
        print(
            "❌ Missing API credentials. Set BINANCE_API_KEY / BINANCE_API_SECRET "
            "environment variables, or pass --api-key / --api-secret."
        )
        return 2

    # --- 3. Place the order --------------------------------------------------
    client = BinanceFuturesClient(
        api_key=args.api_key, api_secret=args.api_secret, base_url=args.base_url
    )

    try:
        response = place_order(client, order)
    except OrderExecutionError as exc:
        print(f"❌ Order failed: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 - final safety net, logged below
        logger.exception("Unexpected error while placing order")
        print(f"❌ Unexpected error: {exc}")
        return 1

    print("Order response:")
    print(f"  {summarize_response(response)}")
    print("✅ Order placed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
