"""Utility functions for interacting with the Binance Spot Testnet."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List

from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv


class BinanceClientError(RuntimeError):
    """Raised when there is an issue configuring or calling the Binance client."""


@lru_cache(maxsize=1)
def connect_client() -> Client:
    """Instantiate and cache a Binance client configured for the testnet."""
    load_dotenv()

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    base_url = os.getenv("BINANCE_TESTNET_URL", "https://testnet.binance.vision")

    if not api_key or not api_secret:
        raise BinanceClientError("Binance API credentials are not configured.")

    client = Client(api_key=api_key, api_secret=api_secret)
    client.API_URL = base_url.rstrip("/") + "/api"
    return client


def get_balance() -> List[Dict[str, Any]]:
    """Return the balances from the connected Binance account."""
    client = connect_client()

    try:
        account_info = client.get_account()
    except BinanceAPIException as exc:  # pragma: no cover - network interaction
        raise BinanceClientError(f"Failed to fetch account balance: {exc}") from exc

    balances = account_info.get("balances", [])
    return [balance for balance in balances if float(balance.get("free", 0)) > 0 or float(balance.get("locked", 0)) > 0]


def place_order(
    symbol: str,
    side: str,
    quantity: float,
    price: float | None = None,
    order_type: str = "MARKET",
) -> Dict[str, Any]:
    """Place a test order on the Binance Spot Testnet."""
    client = connect_client()
    normalized_type = order_type.upper()
    normalized_side = side.upper()

    if normalized_type == "LIMIT" and price is None:
        raise BinanceClientError("Limit orders require a price value.")

    order_params: Dict[str, Any] = {
        "symbol": symbol.upper(),
        "side": normalized_side,
        "type": normalized_type,
        "quantity": quantity,
    }

    if price is not None:
        order_params["price"] = price

    if normalized_type == "LIMIT":
        order_params.setdefault("timeInForce", Client.TIME_IN_FORCE_GTC)

    try:
        return client.create_test_order(**order_params)
    except BinanceAPIException as exc:  # pragma: no cover - network interaction
        raise BinanceClientError(f"Failed to place order: {exc}") from exc
