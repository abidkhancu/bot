"""
Binance exchange adapter (stub – NOT YET IMPLEMENTED).

This file exists so the project architecture supports a future live-trading
mode without breaking existing paper-trading code.

To activate Binance live trading you will need to:
1. Install ``python-binance`` (``pip install python-binance``).
2. Set ``BINANCE_API_KEY`` and ``BINANCE_API_SECRET`` in your ``.env``.
3. Set ``TRADING_MODE=binance``.
4. Implement the methods below.

WARNING: This adapter is NOT implemented and will raise
:class:`NotImplementedError` on every call.  Do NOT set
``TRADING_MODE=binance`` in production until the methods are implemented.
"""

from __future__ import annotations

from typing import Any

from exchange.base import BaseAdapter


class BinanceAdapter(BaseAdapter):
    """Future Binance Futures live-trading adapter (stub)."""

    def __init__(self) -> None:
        raise NotImplementedError(
            "BinanceAdapter is not yet implemented.  "
            "Use TRADING_MODE=paper for now."
        )

    def get_balance(self) -> dict[str, float]:
        raise NotImplementedError

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        leverage: int = 1,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def close_position(self, symbol: str, exit_price: float | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def get_open_positions(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_trade_history(self, limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError
