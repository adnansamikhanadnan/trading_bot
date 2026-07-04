"""
Thin wrapper around the Binance Futures (USDT-M) REST API.

Implemented with `requests` directly (no python-binance dependency) so the
signing/error-handling logic is fully visible and easy to audit. Only the
endpoints needed for this task are implemented:

  - GET  /fapi/v1/ping          (connectivity check)
  - GET  /fapi/v1/time          (server time, used for signing)
  - GET  /fapi/v2/account       (sanity check credentials)
  - POST /fapi/v1/order         (place an order)

All requests/responses/errors are logged for auditability.
"""

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger("trading_bot.client")

DEFAULT_TESTNET_BASE_URL = "https://testnet.binancefuture.com"
REQUEST_TIMEOUT_SECONDS = 10


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error response (non-2xx)."""

    def __init__(self, status_code: int, code: Optional[int], message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {status_code} (code={code}): {message}")


class BinanceNetworkError(Exception):
    """Raised for connection/timeout problems talking to Binance."""


class BinanceFuturesClient:
    """
    Minimal signed REST client for Binance Futures Testnet.

    Parameters
    ----------
    api_key, api_secret:
        Credentials generated from the Binance Futures Testnet UI.
    base_url:
        Defaults to the official testnet endpoint. Overridable for testing.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = DEFAULT_TESTNET_BASE_URL,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
    ):
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret must both be provided.")

        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Attach `timestamp` and HMAC-SHA256 `signature` to params."""
        params = dict(params)
        params["timestamp"] = int(time.time() * 1000)
        params.setdefault("recvWindow", 5000)
        query_string = urlencode(params, doseq=True)
        signature = hmac.new(self.api_secret, query_string.encode("utf-8"), hashlib.sha256).hexdigest()
        params["signature"] = signature
        return params

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        params = params or {}

        if signed:
            params = self._sign(params)

        # Never log secrets: strip signature/api key before logging.
        safe_params = {k: v for k, v in params.items() if k not in ("signature",)}
        logger.debug("API REQUEST %s %s params=%s", method, path, safe_params)

        try:
            response = self.session.request(
                method=method, url=url, params=params, timeout=self.timeout
            )
        except requests.exceptions.Timeout as exc:
            logger.error("API TIMEOUT %s %s: %s", method, path, exc)
            raise BinanceNetworkError(f"Request to {path} timed out after {self.timeout}s.") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("API CONNECTION ERROR %s %s: %s", method, path, exc)
            raise BinanceNetworkError(f"Could not connect to {self.base_url}: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("API REQUEST EXCEPTION %s %s: %s", method, path, exc)
            raise BinanceNetworkError(f"Network error calling {path}: {exc}") from exc

        logger.debug("API RESPONSE %s %s status=%s body=%s", method, path, response.status_code, response.text)

        if response.status_code >= 400:
            code = None
            message = response.text
            try:
                body = response.json()
                code = body.get("code")
                message = body.get("msg", message)
            except ValueError:
                pass  # non-JSON error body; fall back to raw text
            logger.error(
                "API ERROR %s %s -> status=%s code=%s msg=%s",
                method, path, response.status_code, code, message,
            )
            raise BinanceAPIError(response.status_code, code, message)

        try:
            return response.json()
        except ValueError as exc:
            logger.error("API returned non-JSON response body for %s %s", method, path)
            raise BinanceAPIError(response.status_code, None, "Non-JSON response from Binance") from exc

    # ------------------------------------------------------------------ #
    # Public endpoints
    # ------------------------------------------------------------------ #

    def ping(self) -> Dict[str, Any]:
        """GET /fapi/v1/ping — basic connectivity check."""
        return self._request("GET", "/fapi/v1/ping")

    def get_account(self) -> Dict[str, Any]:
        """GET /fapi/v2/account — verifies credentials and shows balances."""
        return self._request("GET", "/fapi/v2/account", signed=True)

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        """
        POST /fapi/v1/order — place a new order.

        `order_type` here is our internal type (MARKET / LIMIT / STOP_LIMIT);
        it is translated to Binance's own `type` + extra params below.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
        }

        if order_type == "MARKET":
            params["type"] = "MARKET"
        elif order_type == "LIMIT":
            params["type"] = "LIMIT"
            params["price"] = price
            params["timeInForce"] = time_in_force
        elif order_type == "STOP_LIMIT":
            # Binance Futures calls this order type "STOP" (stop-limit, as
            # opposed to "STOP_MARKET"): it needs both stopPrice and price.
            params["type"] = "STOP"
            params["price"] = price
            params["stopPrice"] = stop_price
            params["timeInForce"] = time_in_force
        else:
            raise ValueError(f"Unsupported order_type: {order_type}")

        return self._request("POST", "/fapi/v1/order", params=params, signed=True)
