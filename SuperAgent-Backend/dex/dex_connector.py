"""Utilities for interacting with Uniswap v3 on the Sepolia testnet."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.contract.contract import Contract
from web3.exceptions import ContractLogicError
from web3.middleware import geth_poa_middleware

load_dotenv()

# Cache the Web3 instance to avoid repeatedly instantiating the provider.
_WEB3: Optional[Web3] = None


ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# Minimal ABI containing the exactInputSingle function we need for swaps.
UNISWAP_ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "internalType": "struct ISwapRouter.ExactInputSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    }
]


@dataclass
class TokenDetails:
    """Describes a token supported by the CLI."""

    symbol: str
    address: Optional[str]
    decimals: int
    router_fee: int = 3000
    wrapped_address: Optional[str] = None


class DexConnectorError(RuntimeError):
    """Generic error raised for Web3 or contract failures."""


def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise DexConnectorError(f"Environment variable {name} is required")
    return value


def connect_web3() -> Web3:
    """Instantiate and cache a Web3 HTTP provider using the configured URL."""

    global _WEB3
    if _WEB3 is not None:
        return _WEB3

    provider_url = _get_env("WEB3_PROVIDER")
    web3 = Web3(Web3.HTTPProvider(provider_url))
    if not web3.is_connected():
        raise DexConnectorError("Failed to connect to Web3 provider")

    # Sepolia uses a PoA consensus, so the Geth middleware is required to build
    # correct block headers.
    web3.middleware_onion.inject(geth_poa_middleware, layer=0)

    _WEB3 = web3
    return web3


def _get_wallet() -> LocalAccount:
    private_key = _get_env("WALLET_PRIVATE_KEY")
    try:
        account: LocalAccount = Account.from_key(private_key)
    except ValueError as exc:  # pragma: no cover - invalid key
        raise DexConnectorError("Invalid wallet private key provided") from exc
    return account


def _get_router(web3: Web3) -> Contract:
    router_address = _get_env("UNISWAP_ROUTER")
    return web3.eth.contract(address=Web3.to_checksum_address(router_address), abi=UNISWAP_ROUTER_ABI)


def _coerce_token(token: Any) -> TokenDetails:
    if isinstance(token, TokenDetails):
        return token
    if isinstance(token, dict):
        return TokenDetails(
            symbol=token.get("symbol", ""),
            address=token.get("address"),
            decimals=int(token.get("decimals", 18)),
            router_fee=int(token.get("router_fee", 3000)),
            wrapped_address=token.get("wrapped_address"),
        )
    raise DexConnectorError("Token metadata must be a TokenDetails instance or dict")


def get_balance(token_address: Optional[str] = None) -> Dict[str, Any]:
    """Return the formatted balance for the configured wallet."""

    web3 = connect_web3()
    wallet_address = _get_env("WALLET_ADDRESS")
    checksum_wallet = Web3.to_checksum_address(wallet_address)

    if not token_address:
        balance_wei = web3.eth.get_balance(checksum_wallet)
        balance = Decimal(str(web3.from_wei(balance_wei, "ether")))
        return {
            "symbol": "ETH",
            "raw_balance": balance_wei,
            "formatted_balance": balance,
        }

    contract = web3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
    decimals = contract.functions.decimals().call()
    symbol = contract.functions.symbol().call()
    raw_balance = contract.functions.balanceOf(checksum_wallet).call()
    formatted = Decimal(raw_balance) / Decimal(10**decimals)
    return {
        "symbol": symbol,
        "raw_balance": raw_balance,
        "formatted_balance": formatted,
    }


def _ensure_allowance(
    web3: Web3,
    token: TokenDetails,
    owner: str,
    spender: str,
    amount: int,
    account: LocalAccount,
) -> None:
    """Approve the router to spend `amount` of `token` if necessary."""

    if token.address is None:
        return  # Native ETH does not require approval.

    contract = web3.eth.contract(address=Web3.to_checksum_address(token.address), abi=ERC20_ABI)
    current_allowance = contract.functions.allowance(owner, spender).call()
    if current_allowance >= amount:
        return

    nonce = web3.eth.get_transaction_count(owner)
    gas_price = web3.eth.gas_price
    tx = contract.functions.approve(spender, amount).build_transaction(
        {
            "from": owner,
            "nonce": nonce,
            "gasPrice": gas_price,
            "chainId": int(_get_env("CHAIN_ID")),
        }
    )
    gas_estimate = contract.functions.approve(spender, amount).estimate_gas(tx)
    tx["gas"] = int(gas_estimate * Decimal("1.2"))
    signed = account.sign_transaction(tx)
    tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)
    web3.eth.wait_for_transaction_receipt(tx_hash)


def swap_tokens(from_token: Any, to_token: Any, amount_in_eth: Decimal) -> Dict[str, Any]:
    """Execute a swap through Uniswap v3 and return the transaction details."""

    web3 = connect_web3()
    account = _get_wallet()
    router = _get_router(web3)
    chain_id = int(_get_env("CHAIN_ID"))

    sender = account.address
    checksum_sender = Web3.to_checksum_address(sender)

    input_token = _coerce_token(from_token)
    output_token = _coerce_token(to_token)

    if amount_in_eth <= 0:
        raise DexConnectorError("Amount to swap must be greater than zero")

    value = 0
    token_in_address: str

    if input_token.address is None:
        amount_in_units = int(Web3.to_wei(amount_in_eth, "ether"))
        if amount_in_units <= 0:
            raise DexConnectorError("Amount resolves to zero wei; increase the trade size")
        wrapped = input_token.wrapped_address or os.getenv("WETH_ADDRESS")
        if not wrapped:
            raise DexConnectorError("Wrapped token address required for native swaps")
        token_in_address = Web3.to_checksum_address(wrapped)
        value = amount_in_units
    else:
        token_in_address = Web3.to_checksum_address(input_token.address)
        scale = Decimal(10**input_token.decimals)
        amount_in_units = int((amount_in_eth * scale).to_integral_value(rounding=ROUND_DOWN))
        if amount_in_units <= 0:
            raise DexConnectorError("Amount resolves to zero in token units; increase trade size")

    token_out_address = Web3.to_checksum_address(output_token.address)
    router_address = Web3.to_checksum_address(_get_env("UNISWAP_ROUTER"))

    _ensure_allowance(web3, input_token, checksum_sender, router_address, amount_in_units, account)

    params = {
        "tokenIn": token_in_address,
        "tokenOut": token_out_address,
        "fee": int(input_token.router_fee),
        "recipient": checksum_sender,
        "deadline": int(time.time()) + 600,
        "amountIn": amount_in_units,
        # For simplicity the CLI uses a zero slippage guard. Users can repeat
        # the swap with a larger amountOutMinimum if necessary.
        "amountOutMinimum": 0,
        "sqrtPriceLimitX96": 0,
    }

    base_tx = {
        "from": checksum_sender,
        "value": value,
        "nonce": web3.eth.get_transaction_count(checksum_sender),
        "gasPrice": web3.eth.gas_price,
        "chainId": chain_id,
    }

    try:
        gas_estimate = router.functions.exactInputSingle(params).estimate_gas(base_tx)
    except ContractLogicError as exc:
        raise DexConnectorError(f"Gas estimation failed: {exc}") from exc

    base_tx["gas"] = int(Decimal(gas_estimate) * Decimal("1.2"))

    unsigned_tx = router.functions.exactInputSingle(params).build_transaction(base_tx)
    signed_tx = account.sign_transaction(unsigned_tx)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)

    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    etherscan_url = f"https://sepolia.etherscan.io/tx/{tx_hash.hex()}"

    return {
        "tx_hash": tx_hash.hex(),
        "etherscan_url": etherscan_url,
        "gas_used": receipt.gasUsed,
        "status": receipt.status,
        "raw_receipt": dict(receipt),
    }
