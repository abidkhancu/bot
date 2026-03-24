"""
Paper Trade Executor.

Bridges the signal engine and the PaperInvest client.  For each signal it:

1. Validates the signal (strength, confidence, direction).
2. Checks risk management rules (position limits, daily loss cap).
3. Sizes the position using the 1%-risk formula.
4. Sends the order to the PaperInvest client.
5. Persists the trade in the portfolio DB and CSV log.

Signal flow
-----------
Signal Engine → PaperTradeExecutor → TradeValidator
                                   → RiskManager
                                   → PaperInvestClient
                                   → PortfolioManager (persist)
                                   → TradeLogger (CSV)
"""

from __future__ import annotations

import logging
from typing import Any

from paper_trading.config import (
    DEFAULT_LEVERAGE,
    MAX_OPEN_TRADES,
    MAX_RISK_PER_TRADE,
    MIN_CONFIDENCE,
    MIN_SCORE,
)
from paper_trading.paperinvest_client import PaperInvestClient
from paper_trading.portfolio_manager import PortfolioManager
from paper_trading.trade_logger import TradeLogger

logger = logging.getLogger(__name__)

# Signals that trigger a BUY order
_LONG_SIGNALS = {"LONG", "STRONG LONG"}
# Signals that trigger a SELL/SHORT order
_SHORT_SIGNALS = {"SHORT", "STRONG SHORT"}
# Signals that trigger a position close
_CLOSE_SIGNALS = {"NO TRADE"}


class PaperTradeExecutor:
    """Execute paper trades based on signal engine output.

    Args:
        client:    :class:`~paper_trading.paperinvest_client.PaperInvestClient` instance.
        portfolio: :class:`~paper_trading.portfolio_manager.PortfolioManager` instance.
        trade_log: :class:`~paper_trading.trade_logger.TradeLogger` instance.
    """

    def __init__(
        self,
        client: PaperInvestClient | None = None,
        portfolio: PortfolioManager | None = None,
        trade_log: TradeLogger | None = None,
    ) -> None:
        self._client = client or PaperInvestClient()
        self._pm = portfolio or PortfolioManager()
        self._log = trade_log or TradeLogger()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_signal(self, signal_result: dict[str, Any]) -> dict[str, Any]:
        """Process one signal result from the signal engine.

        Args:
            signal_result: The dict returned by :func:`~crypto_signal_bot.main.run_analysis`.

        Returns:
            Action dict describing what was done (action, reason, order, …).
        """
        symbol = signal_result.get("pair", "")
        signal = signal_result.get("signal", "NO TRADE")
        confidence = signal_result.get("confidence", 0)
        score = signal_result.get("score", 0)
        entry = signal_result.get("entry")
        stop_loss = signal_result.get("stop_loss")
        take_profit = signal_result.get("take_profit")

        logger.info(
            "PaperTradeExecutor: processing %s signal for %s (score=%d, conf=%d%%)",
            signal, symbol, score, confidence,
        )

        # ----------------------------------------------------------
        # Step 1: Validate signal
        # ----------------------------------------------------------
        validation = self._validate(signal, score, confidence)
        if not validation["valid"]:
            return {"action": "SKIP", "reason": validation["reason"], "symbol": symbol}

        # ----------------------------------------------------------
        # Step 2: Risk management checks
        # ----------------------------------------------------------
        if self._pm.is_daily_loss_limit_hit():
            return {
                "action": "SKIP",
                "reason": "Daily loss limit reached – no new trades today",
                "symbol": symbol,
            }

        # ----------------------------------------------------------
        # Step 3: Handle CLOSE signals (NO TRADE while a position exists)
        # ----------------------------------------------------------
        if signal in _CLOSE_SIGNALS:
            if self._pm.has_open_position(symbol):
                return self._close(symbol, entry)
            return {"action": "SKIP", "reason": "No signal – no open position", "symbol": symbol}

        # ----------------------------------------------------------
        # Step 4: Check max open trades
        # ----------------------------------------------------------
        if self._pm.count_open_positions() >= MAX_OPEN_TRADES:
            return {
                "action": "SKIP",
                "reason": f"Max open trades ({MAX_OPEN_TRADES}) reached",
                "symbol": symbol,
            }

        # ----------------------------------------------------------
        # Step 5: Skip if already in a position for this symbol
        # ----------------------------------------------------------
        if self._pm.has_open_position(symbol):
            return {
                "action": "SKIP",
                "reason": f"Position already open for {symbol}",
                "symbol": symbol,
            }

        # ----------------------------------------------------------
        # Step 6: Position sizing
        # ----------------------------------------------------------
        balance_info = self._client.get_balance()
        account_balance = balance_info.get("balance", 0.0)

        if entry is None or stop_loss is None:
            return {"action": "SKIP", "reason": "No entry/stop-loss from signal", "symbol": symbol}

        sl_distance = abs(entry - stop_loss)
        if sl_distance == 0:
            return {"action": "SKIP", "reason": "Stop-loss distance is zero", "symbol": symbol}

        # position_size = (balance * risk_per_trade) / sl_distance
        position_size = (account_balance * MAX_RISK_PER_TRADE) / sl_distance

        if position_size <= 0:
            return {"action": "SKIP", "reason": "Computed position size ≤ 0", "symbol": symbol}

        # ----------------------------------------------------------
        # Step 7: Determine side and place order
        # ----------------------------------------------------------
        side = "BUY" if signal in _LONG_SIGNALS else "SELL"

        try:
            order = self._client.place_order(
                symbol=symbol,
                side=side,
                quantity=round(position_size, 6),
                entry_price=entry,
                leverage=DEFAULT_LEVERAGE,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("PaperTradeExecutor: place_order failed: %s", exc)
            return {"action": "ERROR", "reason": str(exc), "symbol": symbol}

        # ----------------------------------------------------------
        # Step 8: Persist
        # ----------------------------------------------------------
        self._pm.open_position(order)
        self._log.log_open(order)

        # Refresh balance in DB
        bal = self._client.get_balance()
        self._pm.update_balance(bal["balance"], bal["equity"])

        logger.info(
            "PaperTradeExecutor: %s %s opened – order_id=%s size=%.4f @ %.4f",
            side, symbol, order.get("order_id"), position_size, entry,
        )

        return {
            "action": "OPEN",
            "side": side,
            "symbol": symbol,
            "order": order,
        }

    def close_signal(self, symbol: str, exit_price: float | None = None) -> dict[str, Any]:
        """Manually close an open position.

        Args:
            symbol:     Trading pair.
            exit_price: Price at which to close (simulation).

        Returns:
            Action dict.
        """
        return self._close(symbol, exit_price)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate(self, signal: str, score: int, confidence: int) -> dict[str, Any]:
        """Validate signal quality before execution.

        Args:
            signal:     Signal string from engine.
            score:      Numeric score.
            confidence: Confidence percentage.

        Returns:
            Dict with ``valid`` bool and ``reason`` string.
        """
        if signal == "NO TRADE":
            return {"valid": True, "reason": ""}  # handled separately

        if abs(score) < MIN_SCORE:
            return {
                "valid": False,
                "reason": f"Score |{score}| < min {MIN_SCORE}",
            }
        if confidence < MIN_CONFIDENCE:
            return {
                "valid": False,
                "reason": f"Confidence {confidence}% < min {MIN_CONFIDENCE}%",
            }
        if signal not in _LONG_SIGNALS | _SHORT_SIGNALS:
            return {
                "valid": False,
                "reason": f"Unknown signal: {signal}",
            }
        return {"valid": True, "reason": ""}

    def _close(self, symbol: str, exit_price: float | None) -> dict[str, Any]:
        """Close an open position and update records.

        Args:
            symbol:     Trading pair.
            exit_price: Closing price.

        Returns:
            Action dict.
        """
        try:
            result = self._client.close_position(symbol, exit_price)
        except Exception as exc:  # noqa: BLE001
            logger.error("PaperTradeExecutor: close_position failed: %s", exc)
            return {"action": "ERROR", "reason": str(exc), "symbol": symbol}

        if result.get("status") == "NOT_FOUND":
            return {"action": "SKIP", "reason": "No open position found", "symbol": symbol}

        pnl = result.get("pnl", 0.0)
        order_id = result.get("order_id", "")
        won = pnl > 0

        self._pm.close_position(order_id, exit_price or result.get("exit_price", 0.0), pnl)
        self._pm.record_realized_pnl(pnl, won)

        result["trade_duration"] = ""  # duration computed by PortfolioManager
        self._log.log_close(result)

        bal = self._client.get_balance()
        self._pm.update_balance(bal["balance"], bal["equity"])

        logger.info(
            "PaperTradeExecutor: %s closed – PnL=%.4f USDT (won=%s)",
            symbol, pnl, won,
        )
        return {
            "action": "CLOSE",
            "symbol": symbol,
            "pnl": pnl,
            "result": result,
        }
