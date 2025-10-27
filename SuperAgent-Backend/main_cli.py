"""Terminal interface for the SuperAgent v0.2 DEX autonomous trader."""
from __future__ import annotations

import os
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Optional

from dotenv import load_dotenv

from agent.qwen_agent import query_qwen
from dex.dex_connector import DexConnectorError, TokenDetails, get_balance, swap_tokens

load_dotenv()

BANNER = "SuperAgent v0.2 — DEX Autonomous Trader (Qwen-2.5-7B-Instruct)"

# Default token registry for Sepolia testnet. Values can be overridden via
# environment variables if desired.
TOKEN_REGISTRY: Dict[str, TokenDetails] = {
    "ETH": TokenDetails(
        symbol="ETH",
        address=None,
        decimals=18,
        router_fee=3000,
        wrapped_address=os.getenv(
            "WETH_ADDRESS", "0xDD13E55209Fd76AfE204dBda4007C227904f0a81"
        ),
    ),
    "WETH": TokenDetails(
        symbol="WETH",
        address=os.getenv("WETH_ADDRESS", "0xDD13E55209Fd76AfE204dBda4007C227904f0a81"),
        decimals=18,
        router_fee=3000,
    ),
    "USDC": TokenDetails(
        symbol="USDC",
        address=os.getenv("USDC_ADDRESS", "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"),
        decimals=6,
        router_fee=500,
    ),
    "DAI": TokenDetails(
        symbol="DAI",
        address=os.getenv("DAI_ADDRESS", "0x38E68A37F05A21E2C2dC6aAbC5e1E6aF3A3A7f81"),
        decimals=18,
        router_fee=3000,
    ),
}

TRADE_REGEX = re.compile(
    r"\b(?:trade|swap)\s+([0-9]*\.?[0-9]+)\s*(\w+)\s*(?:to|->)\s*(\w+)",
    re.IGNORECASE,
)

BALANCE_REGEX = re.compile(r"\b(balance|portfolio|holdings)\b", re.IGNORECASE)


class CommandParser:
    """Utility class that extracts trade and balance intents from text."""

    @staticmethod
    def parse_trade(text: str) -> Optional[Dict[str, str]]:
        if not text:
            return None
        match = TRADE_REGEX.search(text)
        if not match:
            return None
        amount, from_symbol, to_symbol = match.groups()
        return {
            "amount": amount,
            "from": from_symbol.upper(),
            "to": to_symbol.upper(),
        }

    @staticmethod
    def wants_balance(text: str) -> bool:
        if not text:
            return False
        return bool(BALANCE_REGEX.search(text))


def _resolve_token(symbol: str) -> TokenDetails:
    token = TOKEN_REGISTRY.get(symbol.upper())
    if not token:
        raise DexConnectorError(f"Token '{symbol}' is not configured")
    return token


def _confirm(prompt: str) -> bool:
    try:
        choice = input(f"{prompt} (y/n): ").strip().lower()
    except EOFError:
        return False
    return choice in {"y", "yes"}


def _format_decimal(value: Decimal) -> str:
    quantize_unit = Decimal("0.0001") if value < 1 else Decimal("0.01")
    return f"{value.quantize(quantize_unit, rounding=ROUND_HALF_UP)}"


def _handle_trade(command: Dict[str, str]) -> None:
    try:
        amount = Decimal(command["amount"])
    except (InvalidOperation, KeyError):
        print("Unable to determine trade amount from command.")
        return

    from_token = _resolve_token(command["from"])
    to_token = _resolve_token(command["to"])

    print(
        f"Confirm swap {command['amount']} {from_token.symbol} -> {to_token.symbol}?"
    )
    if not _confirm("Proceed"):
        print("Trade cancelled by user.")
        return

    try:
        result = swap_tokens(from_token, to_token, amount)
    except DexConnectorError as exc:
        print(f"Swap failed: {exc}")
        return

    print(
        "Tx submitted: {hash} ({url})".format(
            hash=result["tx_hash"],
            url=result["etherscan_url"],
        )
    )
    print(f"Gas used: {result['gas_used']} | Status: {result['status']}")


def _handle_balance() -> None:
    try:
        base_balance = get_balance()
    except DexConnectorError as exc:
        print(f"Unable to fetch ETH balance: {exc}")
        return

    print(
        f"ETH Balance: {_format_decimal(base_balance['formatted_balance'])} ETH"
    )

    for symbol, token in TOKEN_REGISTRY.items():
        if token.address is None:
            continue
        try:
            token_balance = get_balance(token.address)
        except DexConnectorError as exc:
            print(f"Unable to fetch {symbol} balance: {exc}")
            continue
        formatted = _format_decimal(token_balance["formatted_balance"])
        print(f"{symbol} Balance: {formatted} {symbol}")


def main() -> None:
    print(BANNER)
    while True:
        try:
            user_input = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession terminated.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit"}:
            print("Qwen: Session closed. Profits saved. Goodbye.")
            break

        try:
            response = query_qwen(user_input)
        except Exception as exc:  # pragma: no cover - network failure
            print(f"Qwen unavailable: {exc}")
            continue

        if response:
            print(f"Qwen: {response}")

        trade = CommandParser.parse_trade(response) or CommandParser.parse_trade(user_input)
        if trade:
            _handle_trade(trade)
            continue

        if CommandParser.wants_balance(response) or CommandParser.wants_balance(user_input):
            _handle_balance()
            continue


if __name__ == "__main__":
    main()
