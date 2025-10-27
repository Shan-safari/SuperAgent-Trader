"""Trading endpoints for Binance Testnet interactions."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trading.binance_client import (
    BinanceClientError,
    get_balance,
    place_order,
)

router = APIRouter()


class OrderRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol, e.g. BTCUSDT")
    side: str = Field(..., description="BUY or SELL")
    quantity: float = Field(..., gt=0, description="Amount to trade")
    price: float | None = Field(
        default=None, description="Optional price when placing limit orders"
    )
    order_type: str = Field(
        default="MARKET", description="Order type, defaults to MARKET"
    )


@router.get("/balance")
def read_balance() -> Dict[str, Any]:
    """Return the account balance from Binance Testnet."""
    try:
        balances = get_balance()
        return {"balances": balances}
    except BinanceClientError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/order")
def create_order(request: OrderRequest) -> Dict[str, Any]:
    """Place a test order through Binance Testnet."""
    try:
        result = place_order(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            order_type=request.order_type,
        )
        return {"status": "success", "order": result}
    except BinanceClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
