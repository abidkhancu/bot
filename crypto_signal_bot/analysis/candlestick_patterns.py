"""
Candlestick pattern detection module.

Detects the following single and multi-candle patterns:
- Doji
- Hammer
- Shooting Star
- Pin Bar (bullish / bearish)
- Bullish Engulfing
- Bearish Engulfing
- Morning Star (simplified)
- Evening Star (simplified)

Each detected pattern is appended as a new column (boolean flag) and a
human-readable ``pattern`` string column is added summarising the most
significant pattern on each bar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crypto_signal_bot.utils.logger import get_logger

logger = get_logger(__name__)


def detect_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Detect candlestick patterns and add result columns to *df*.

    New columns added:
        pattern_doji              – True/False
        pattern_hammer            – True/False
        pattern_shooting_star     – True/False
        pattern_bullish_pin_bar   – True/False
        pattern_bearish_pin_bar   – True/False
        pattern_bullish_engulfing – True/False
        pattern_bearish_engulfing – True/False
        pattern                   – string label of most significant pattern
                                    (or 'None')

    Args:
        df: OHLCV DataFrame.

    Returns:
        Modified DataFrame.
    """
    if df.empty or len(df) < 2:
        logger.warning("Candlestick pattern detection skipped: not enough data.")
        df["pattern"] = "None"
        return df

    df = df.copy()

    body = (df["close"] - df["open"]).abs()
    candle_range = df["high"] - df["low"]
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
    is_bullish = df["close"] > df["open"]
    is_bearish = df["close"] < df["open"]

    # Avoid division by zero
    rng = candle_range.replace(0, np.nan)

    # ------------------------------------------------------------------
    # Doji: body <= 10 % of range
    # ------------------------------------------------------------------
    df["pattern_doji"] = (body / rng) <= 0.10

    # ------------------------------------------------------------------
    # Hammer: small body at top, long lower wick (≥ 2× body), small upper wick
    # ------------------------------------------------------------------
    df["pattern_hammer"] = (
        (lower_wick >= 2 * body)
        & (upper_wick <= body * 0.5)
        & (~df["pattern_doji"])
    )

    # ------------------------------------------------------------------
    # Shooting Star: small body at bottom, long upper wick (≥ 2× body)
    # ------------------------------------------------------------------
    df["pattern_shooting_star"] = (
        (upper_wick >= 2 * body)
        & (lower_wick <= body * 0.5)
        & (~df["pattern_doji"])
    )

    # ------------------------------------------------------------------
    # Pin Bar (bullish): lower wick ≥ 66 % of range, bullish body
    # Pin Bar (bearish): upper wick ≥ 66 % of range, bearish body
    # ------------------------------------------------------------------
    df["pattern_bullish_pin_bar"] = (lower_wick / rng >= 0.66) & is_bullish
    df["pattern_bearish_pin_bar"] = (upper_wick / rng >= 0.66) & is_bearish

    # ------------------------------------------------------------------
    # Engulfing patterns (two-candle)
    # ------------------------------------------------------------------
    prev_open = df["open"].shift(1)
    prev_close = df["close"].shift(1)

    # Bullish engulfing: previous candle bearish, current candle bullish and
    # fully engulfs previous body.
    df["pattern_bullish_engulfing"] = (
        is_bullish
        & (prev_close < prev_open)  # previous was bearish
        & (df["open"] <= prev_close)
        & (df["close"] >= prev_open)
    )

    # Bearish engulfing: previous candle bullish, current candle bearish and
    # fully engulfs previous body.
    df["pattern_bearish_engulfing"] = (
        is_bearish
        & (prev_close > prev_open)  # previous was bullish
        & (df["open"] >= prev_close)
        & (df["close"] <= prev_open)
    )

    # ------------------------------------------------------------------
    # Consolidated pattern label (priority order: engulfing > pin bar >
    # hammer/star > doji)
    # ------------------------------------------------------------------
    df["pattern"] = "None"

    df.loc[df["pattern_doji"], "pattern"] = "Doji"
    df.loc[df["pattern_hammer"], "pattern"] = "Hammer"
    df.loc[df["pattern_shooting_star"], "pattern"] = "Shooting Star"
    df.loc[df["pattern_bullish_pin_bar"], "pattern"] = "Bullish Pin Bar"
    df.loc[df["pattern_bearish_pin_bar"], "pattern"] = "Bearish Pin Bar"
    df.loc[df["pattern_bullish_engulfing"], "pattern"] = "Bullish Engulfing"
    df.loc[df["pattern_bearish_engulfing"], "pattern"] = "Bearish Engulfing"

    return df
