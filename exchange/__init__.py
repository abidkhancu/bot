"""
Exchange adapter package.

Provides a common interface for different trading backends.

Usage::

    from exchange import get_adapter
    adapter = get_adapter(mode="paper")   # or "binance"

Set ``TRADING_MODE=paper`` or ``TRADING_MODE=binance`` in your ``.env``.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exchange.base import BaseAdapter


def get_adapter(mode: str | None = None) -> "BaseAdapter":
    """Return the appropriate exchange adapter.

    Args:
        mode: ``"paper"`` or ``"binance"``.  Defaults to the ``TRADING_MODE``
              environment variable (fallback: ``"paper"``).

    Returns:
        An instance of the requested adapter.

    Raises:
        ValueError: For unknown *mode* values.
    """
    mode = (mode or os.getenv("TRADING_MODE", "paper")).lower()
    if mode == "paper":
        from exchange.paperinvest_adapter import PaperInvestAdapter
        return PaperInvestAdapter()
    if mode == "binance":
        from exchange.binance_adapter import BinanceAdapter
        return BinanceAdapter()
    raise ValueError(f"Unknown TRADING_MODE: {mode!r} – choose 'paper' or 'binance'")
