"""
Abstract base class for exchange adapters.

All adapters (PaperInvest, Binance, …) must implement this interface so the
rest of the bot can switch backends with a single configuration change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAdapter(ABC):
    """Abstract exchange adapter interface."""

    @abstractmethod
    def get_balance(self) -> dict[str, float]:
        """Return ``{"balance": float, "equity": float}``."""

    @abstractmethod
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
        """Place an order and return the order confirmation dict."""

    @abstractmethod
    def close_position(self, symbol: str, exit_price: float | None = None) -> dict[str, Any]:
        """Close the open position for *symbol*."""

    @abstractmethod
    def get_open_positions(self) -> list[dict[str, Any]]:
        """Return a list of open position dicts."""

    @abstractmethod
    def get_trade_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return closed trade history."""
