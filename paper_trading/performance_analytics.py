"""
Performance analytics for the paper trading module.

Computes standard trading performance metrics from the closed-trade history
stored in the SQLite portfolio database.

Metrics
-------
* Total Trades
* Win Rate
* Profit Factor
* Sharpe Ratio (annualised, assuming daily returns)
* Max Drawdown
* Average Trade PnL
* Expectancy
"""

from __future__ import annotations

import logging
import math
from typing import Any

from paper_trading.portfolio_manager import PortfolioManager

logger = logging.getLogger(__name__)


class PerformanceAnalytics:
    """Calculate trading performance metrics from historical trade data.

    Args:
        portfolio_manager: An initialised :class:`~paper_trading.portfolio_manager.PortfolioManager`.
    """

    def __init__(self, portfolio_manager: PortfolioManager) -> None:
        self._pm = portfolio_manager

    def compute(self) -> dict[str, Any]:
        """Compute all performance metrics.

        Returns:
            Dict containing all metrics.  Values are ``None`` when insufficient
            data is available.
        """
        trades = self._pm.get_trade_history(limit=10_000)
        closed = [t for t in trades if t.get("status") == "CLOSED" and t.get("pnl") is not None]
        portfolio = self._pm.get_portfolio()

        if not closed:
            return self._empty_metrics(portfolio)

        pnls = [float(t["pnl"]) for t in closed]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        total_trades = len(closed)
        win_count = len(wins)
        loss_count = len(losses)

        win_rate = (win_count / total_trades * 100) if total_trades else 0.0

        total_profit = sum(wins)
        total_loss = abs(sum(losses))

        profit_factor = (
            round(total_profit / total_loss, 4) if total_loss > 0 else None
        )

        avg_win = (total_profit / win_count) if win_count else 0.0
        avg_loss = (total_loss / loss_count) if loss_count else 0.0

        expectancy = (
            (win_rate / 100) * avg_win - (1 - win_rate / 100) * avg_loss
        )

        avg_trade = sum(pnls) / total_trades

        sharpe = self._sharpe(pnls)
        max_dd = portfolio.get("max_drawdown_pct", 0.0)

        return {
            "total_trades": total_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe,
            "max_drawdown_pct": round(max_dd, 4),
            "avg_trade_pnl": round(avg_trade, 4),
            "avg_win": round(avg_win, 4),
            "avg_loss": round(avg_loss, 4),
            "expectancy": round(expectancy, 4),
            "total_realized_pnl": round(sum(pnls), 4),
            "balance": portfolio.get("balance"),
            "equity": portfolio.get("equity"),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sharpe(pnls: list[float], risk_free: float = 0.0) -> float | None:
        """Annualised Sharpe Ratio from a list of per-trade returns.

        Args:
            pnls:      List of per-trade PnL values.
            risk_free: Annual risk-free rate (default 0).

        Returns:
            Annualised Sharpe ratio, or ``None`` if insufficient data.
        """
        if len(pnls) < 2:
            return None
        n = len(pnls)
        mean = sum(pnls) / n
        variance = sum((p - mean) ** 2 for p in pnls) / (n - 1)
        std = math.sqrt(variance)
        if std == 0:
            return None
        # Annualise using 365 trading days (crypto markets run 24/7)
        return round((mean - risk_free) / std * math.sqrt(365), 4)

    @staticmethod
    def _empty_metrics(portfolio: dict[str, Any]) -> dict[str, Any]:
        return {
            "total_trades": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate_pct": 0.0,
            "profit_factor": None,
            "sharpe_ratio": None,
            "max_drawdown_pct": 0.0,
            "avg_trade_pnl": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "expectancy": 0.0,
            "total_realized_pnl": 0.0,
            "balance": portfolio.get("balance"),
            "equity": portfolio.get("equity"),
        }
