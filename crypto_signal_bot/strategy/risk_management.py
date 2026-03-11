"""
Risk management module.

Calculates:
- Entry price (last close)
- Stop loss (entry ± 1.5 × ATR)
- Take profit 1 (entry ± 1.5 × ATR, risk:reward 1:1)
- Take profit 2 (entry ± 3.0 × ATR, risk:reward 1:2)
- Take profit 3 (entry ± 4.5 × ATR, risk:reward 1:3)
- Percentage distances for SL and all TP levels

Default risk/reward: 1:3 (configurable via settings).
"""

from __future__ import annotations

import pandas as pd

from crypto_signal_bot.config.settings import RISK_REWARD_RATIO
from crypto_signal_bot.utils.logger import get_logger

logger = get_logger(__name__)

# Multiplier for the SL distance (1.5× ATR is a professional standard)
_SL_ATR_MULT = 1.5


def calculate_risk(
    df: pd.DataFrame,
    signal: str,
    rr_ratio: float = RISK_REWARD_RATIO,
) -> dict:
    """Calculate risk management parameters for a given signal.

    Args:
        df:       OHLCV DataFrame with an ``atr`` column (from indicators module).
        signal:   ``"LONG"`` or ``"SHORT"``.
        rr_ratio: Risk/reward ratio for TP3 (default: 3.0 → 1:3).

    Returns:
        Dictionary with keys:
            entry       – entry price (current close)
            stop_loss   – stop loss price
            sl_pct      – stop loss distance as percentage of entry
            tp1         – take profit level 1 (1:1 RR)
            tp1_pct     – TP1 distance as percentage of entry
            tp2         – take profit level 2 (1:2 RR)
            tp2_pct     – TP2 distance as percentage of entry
            tp3         – take profit level 3 (1:rr_ratio RR)
            tp3_pct     – TP3 distance as percentage of entry
            take_profit – alias for tp3 (backwards compatibility)
            risk        – distance from entry to stop loss
            reward      – distance from entry to tp3
            rr_ratio    – actual risk/reward ratio used
    """
    if df.empty:
        logger.warning("Risk calculation skipped: empty DataFrame.")
        return {}

    last = df.iloc[-1]
    entry = float(last["close"])
    atr_raw = last.get("atr")
    atr = float(atr_raw) if atr_raw is not None else entry * 0.005

    if signal == "LONG":
        sl_dist = atr * _SL_ATR_MULT
        stop_loss = entry - sl_dist
        tp1 = entry + sl_dist          # 1:1
        tp2 = entry + sl_dist * 2      # 1:2
        tp3 = entry + sl_dist * rr_ratio  # 1:rr_ratio
    elif signal == "SHORT":
        sl_dist = atr * _SL_ATR_MULT
        stop_loss = entry + sl_dist
        tp1 = entry - sl_dist
        tp2 = entry - sl_dist * 2
        tp3 = entry - sl_dist * rr_ratio
    else:
        # NO TRADE – return entry info only
        return {
            "entry": round(entry, 6),
            "stop_loss": None,
            "sl_pct": None,
            "tp1": None,
            "tp1_pct": None,
            "tp2": None,
            "tp2_pct": None,
            "tp3": None,
            "tp3_pct": None,
            "take_profit": None,
            "risk": None,
            "reward": None,
            "rr_ratio": rr_ratio,
        }

    sl_dist_actual = abs(entry - stop_loss)
    sl_pct = round(sl_dist_actual / entry * 100, 2)
    tp1_pct = round(abs(tp1 - entry) / entry * 100, 2)
    tp2_pct = round(abs(tp2 - entry) / entry * 100, 2)
    tp3_pct = round(abs(tp3 - entry) / entry * 100, 2)
    reward = abs(tp3 - entry)
    rr_actual = round(reward / (sl_dist_actual + 1e-10), 2)

    result = {
        "entry": round(entry, 6),
        "stop_loss": round(stop_loss, 6),
        "sl_pct": sl_pct,
        "tp1": round(tp1, 6),
        "tp1_pct": tp1_pct,
        "tp2": round(tp2, 6),
        "tp2_pct": tp2_pct,
        "tp3": round(tp3, 6),
        "tp3_pct": tp3_pct,
        "take_profit": round(tp3, 6),  # backwards compat
        "risk": round(sl_dist_actual, 6),
        "reward": round(reward, 6),
        "rr_ratio": rr_actual,
    }

    logger.debug(
        "Risk [%s]: entry=%.4f  SL=%.4f(-%.2f%%)  TP1=%.4f  TP2=%.4f  TP3=%.4f(+%.2f%%)  RR=%.2f",
        signal,
        entry, stop_loss, sl_pct,
        tp1, tp2, tp3, tp3_pct,
        rr_actual,
    )
    return result
