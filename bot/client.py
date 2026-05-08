"""
Binance Futures Testnet REST client.

Responsibilities:
- HMAC-SHA256 request signing
- Timestamping (with server-time sync)
- Automatic retry with exponential back-off on transient errors
- Structured logging of every request and response
- Unified error parsing into BinanceAPIError
"""

from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .logging_config import get_logger

logger = get_logger("client")

BASE_URL = "https://testnet.binancefuture.com"

# How many ms the local clock may drift vs Binance server time before we re-sync.
CLOCK_DRIFT_THRESHOLD_MS = 1_000


class BinanceAPIError(Exception):
    """Wraps a Binance API error response."""

    def __init__(self, code: int, message: str, status_code: int = 0):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(f"[Binance {code}] {message}")


class BinanceClient:
    """
    Thin wrapper around the Binance Futures Testnet REST API.
    Separate from order logic so it can be swapped / mocked independently.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = BASE_URL,
        recv_window: int = 5_000,
        timeout: int = 10,
    ):
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret must not be empty.")

        self._api_key = api_key
        self._api_secret = api_secret.encode()
        self.base_url = base_url.rstrip("/")
        self.recv_window = recv_window
        self.timeout = timeout

        # Session with retry logic (retries on 429 / 5xx, not on 4xx)
        self._session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        self._session.headers.update({"X-MBX-APIKEY": self._api_key})

        # Cache server-time offset to stay in sync
        self._time_offset_ms: int = 0
        self._sync_server_time()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_server_time(self) -> int:
        """Return current Binance server time in ms."""
        data = self._request("GET", "/fapi/v1/time", signed=False)
        return data["serverTime"]

    def get_account_info(self) -> dict:
        return self._request("GET", "/fapi/v2/account", signed=True)

    def get_exchange_info(self, symbol: Optional[str] = None) -> dict:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/exchangeInfo", params=params, signed=False)

    def place_order(self, **params) -> dict:
        """
        Place a futures order.
        Caller is responsible for building correct params for each order type.
        """
        return self._request("POST", "/fapi/v1/order", params=params, signed=True)
    
    def place_algo_order(self, **params) -> dict:
        """Place a stop order via the Algo Order API endpoint."""
        return self._request("POST", "/fapi/v1/algoOrder", params=params, signed=True)

    def get_order(self, symbol: str, order_id: int) -> dict:
        return self._request(
            "GET", "/fapi/v1/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        return self._request(
            "DELETE", "/fapi/v1/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _sync_server_time(self) -> None:
        try:
            server_ms = self.get_server_time()
            local_ms = int(time.time() * 1000)
            self._time_offset_ms = server_ms - local_ms
            logger.debug("Server time sync", extra={"offset_ms": self._time_offset_ms})
        except Exception as exc:
            logger.warning("Server time sync failed; using local time", extra={"error": str(exc)})
            self._time_offset_ms = 0

    def _timestamp(self) -> int:
        return int(time.time() * 1000) + self._time_offset_ms

    def _sign(self, query_string: str) -> str:
        return hmac.new(self._api_secret, query_string.encode(), hashlib.sha256).hexdigest()

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        signed: bool = False,
    ) -> Any:
        params = {k: v for k, v in (params or {}).items() if v is not None}

        if signed:
            params["timestamp"] = self._timestamp()
            params["recvWindow"] = self.recv_window
            query_string = urllib.parse.urlencode(params)
            params["signature"] = self._sign(query_string)

        url = f"{self.base_url}{path}"

        # Structured request log (no secrets logged)
        safe_params = {k: v for k, v in params.items() if k != "signature"}
        logger.debug(
            "API request",
            extra={"method": method, "path": path, "params": safe_params},
        )

        try:
            if method == "GET":
                resp = self._session.get(url, params=params, timeout=self.timeout)
            elif method == "POST":
                resp = self._session.post(url, params=params, timeout=self.timeout)
            elif method == "DELETE":
                resp = self._session.delete(url, params=params, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network connection error", extra={"error": str(exc)})
            raise ConnectionError(f"Cannot reach {self.base_url}. Check your internet connection.") from exc
        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out", extra={"error": str(exc)})
            raise TimeoutError(f"Request to {path} timed out after {self.timeout}s.") from exc

        logger.debug(
            "API response",
            extra={"status_code": resp.status_code, "path": path},
        )

        try:
            data = resp.json()
        except Exception:
            logger.error("Non-JSON response", extra={"body": resp.text[:500]})
            resp.raise_for_status()
            return {}

        if resp.status_code != 200 or (isinstance(data, dict) and "code" in data and data["code"] != 200):
            code = data.get("code", resp.status_code)
            msg = data.get("msg", resp.text)
            logger.error("API error", extra={"code": code, "api_message": msg})
            raise BinanceAPIError(code=code, message=msg, status_code=resp.status_code)

        return data
