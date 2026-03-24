"""
Trade logger – appends every paper trade to a CSV file.

Log fields (columns)
--------------------
timestamp, symbol, side, entry_price, exit_price, quantity, leverage,
stop_loss, take_profit, pnl, trade_duration, order_id, status
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone
from typing import Any

from paper_trading.config import TRADE_LOG_CSV

logger = logging.getLogger(__name__)

# CSV column order
_COLUMNS = [
    "timestamp",
    "symbol",
    "side",
    "entry_price",
    "exit_price",
    "quantity",
    "leverage",
    "stop_loss",
    "take_profit",
    "pnl",
    "trade_duration",
    "order_id",
    "status",
]


class TradeLogger:
    """Append-only CSV logger for paper trades.

    Args:
        csv_path: Destination CSV file.  Defaults to ``TRADE_LOG_CSV``.
    """

    def __init__(self, csv_path: str = TRADE_LOG_CSV) -> None:
        self._path = csv_path
        os.makedirs(os.path.dirname(csv_path) if os.path.dirname(csv_path) else ".", exist_ok=True)
        self._ensure_header()

    def _ensure_header(self) -> None:
        """Write the CSV header row if the file does not yet exist."""
        if not os.path.exists(self._path):
            with open(self._path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=_COLUMNS)
                writer.writeheader()

    def log_open(self, order: dict[str, Any]) -> None:
        """Log a newly opened trade.

        Args:
            order: Order dict returned by the client / executor.
        """
        row = {
            "timestamp": order.get("opened_at", datetime.now(timezone.utc).isoformat()),
            "symbol": order.get("symbol", ""),
            "side": order.get("side", ""),
            "entry_price": order.get("entry_price", ""),
            "exit_price": "",
            "quantity": order.get("quantity", ""),
            "leverage": order.get("leverage", ""),
            "stop_loss": order.get("stop_loss", ""),
            "take_profit": order.get("take_profit", ""),
            "pnl": "",
            "trade_duration": "",
            "order_id": order.get("order_id", ""),
            "status": "OPEN",
        }
        self._write(row)

    def log_close(self, close_result: dict[str, Any]) -> None:
        """Log a closed trade.

        Args:
            close_result: Close confirmation dict from the client.
        """
        row = {
            "timestamp": close_result.get(
                "closed_at", datetime.now(timezone.utc).isoformat()
            ),
            "symbol": close_result.get("symbol", ""),
            "side": close_result.get("side", ""),
            "entry_price": close_result.get("entry_price", ""),
            "exit_price": close_result.get("exit_price", ""),
            "quantity": close_result.get("quantity", ""),
            "leverage": close_result.get("leverage", ""),
            "stop_loss": close_result.get("stop_loss", ""),
            "take_profit": close_result.get("take_profit", ""),
            "pnl": close_result.get("pnl", ""),
            "trade_duration": close_result.get("trade_duration", ""),
            "order_id": close_result.get("order_id", ""),
            "status": "CLOSED",
        }
        self._write(row)

    def _write(self, row: dict[str, Any]) -> None:
        try:
            with open(self._path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=_COLUMNS, extrasaction="ignore")
                writer.writerow(row)
        except OSError as exc:
            logger.error("TradeLogger: failed to write to %s: %s", self._path, exc)
