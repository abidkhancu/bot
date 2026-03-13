"""
PaperInvest exchange adapter.

Wraps the :class:`~paper_trading.paperinvest_client.PaperInvestClient` with
the :class:`~exchange.base.BaseAdapter` interface so it can be used
interchangeably with future live-exchange adapters.
"""

from __future__ import annotations

from typing import Any

from exchange.base import BaseAdapter
from paper_trading.paperinvest_client import PaperInvestClient


class PaperInvestAdapter(BaseAdapter):
    """Exchange adapter backed by the PaperInvest paper-trading client.

    Args:
        client: Optional pre-configured :class:`PaperInvestClient`.
                A default instance is created when not supplied.
    """

    def __init__(self, client: PaperInvestClient | None = None) -> None:
        self._client = client or PaperInvestClient()

    def get_balance(self) -> dict[str, float]:
        return self._client.get_balance()

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
        return self._client.place_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def close_position(self, symbol: str, exit_price: float | None = None) -> dict[str, Any]:
        return self._client.close_position(symbol, exit_price)

    def get_open_positions(self) -> list[dict[str, Any]]:
        return self._client.get_open_positions()

    def get_trade_history(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._client.get_trade_history(limit=limit)
