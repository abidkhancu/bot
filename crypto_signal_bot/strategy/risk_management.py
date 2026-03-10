"""
Risk management module.

Calculates:
- Entry price (last close)
- Stop loss (entry ± ATR)
- Take profit (entry ± ATR × risk_reward_ratio)
- Risk/reward ratio

Default risk/reward: 1:3 (configurable via settings).
"""

from __future__ import annotations

import pandas as pd

from crypto_signal_bot.config.settings import RISK_REWARD_RATIO
from crypto_signal_bot.utils.logger import get_logger

logger = get_logger(__name__)


def calculate_risk(
    df: pd.DataFrame,
    signal: str,
    rr_ratio: float = RISK_REWARD_RATIO,
) -> dict[str, float]:
    """Calculate risk management parameters for a given signal.

    Args:
        df:       OHLCV DataFrame with an ``atr`` column (from indicators module).
        signal:   ``"LONG"`` or ``"SHORT"``.
        rr_ratio: Risk/reward ratio (default: 3.0 → 1:3).

    Returns:
        Dictionary with keys:
            entry       – entry price (current close)
            stop_loss   – stop loss price
            take_profit – take profit price
            risk        – distance from entry to stop loss
            reward      – distance from entry to take profit
            rr_ratio    – actual risk/reward ratio used
    """
    if df.empty:
        logger.warning("Risk calculation skipped: empty DataFrame.")
        return {}

    last = df.iloc[-1]
    entry = float(last["close"])
    atr = float(last.get("atr", entry * 0.005))  # default 0.5 % if ATR missing

    if signal == "LONG":
        stop_loss = entry - atr
        take_profit = entry + atr * rr_ratio
    elif signal == "SHORT":
        stop_loss = entry + atr
        take_profit = entry - atr * rr_ratio
    else:
        # NO TRADE – return entry info only
        return {
            "entry": round(entry, 4),
            "stop_loss": None,
            "take_profit": None,
            "risk": None,
            "reward": None,
            "rr_ratio": rr_ratio,
        }

    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)

    result = {
        "entry": round(entry, 4),
        "stop_loss": round(stop_loss, 4),
        "take_profit": round(take_profit, 4),
        "risk": round(risk, 4),
        "reward": round(reward, 4),
        "rr_ratio": round(reward / (risk + 1e-10), 2),
    }

    logger.debug(
        "Risk params [%s]: entry=%.4f SL=%.4f TP=%.4f RR=%.2f",
        signal,
        result["entry"],
        result["stop_loss"],
        result["take_profit"],
        result["rr_ratio"],
    )
    return result
