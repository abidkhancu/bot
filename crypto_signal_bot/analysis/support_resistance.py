"""
Support and resistance zone detection module.

Identifies key support and resistance levels using swing highs and swing lows.
Returns a list of price levels that have been tested multiple times.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crypto_signal_bot.utils.logger import get_logger

logger = get_logger(__name__)

# Number of bars on each side to qualify as a swing point
SWING_ORDER: int = 5
# Proximity tolerance: levels within this fraction of price are merged
MERGE_TOLERANCE: float = 0.005  # 0.5 %


def find_support_resistance(df: pd.DataFrame) -> dict[str, list[float]]:
    """Find support and resistance levels from swing highs and lows.

    Args:
        df: OHLCV DataFrame.

    Returns:
        Dictionary with keys 'resistance' and 'support', each containing a
        list of price levels sorted from closest to furthest from current close.
    """
    if df.empty or len(df) < SWING_ORDER * 2 + 1:
        logger.warning("Support/resistance detection skipped: not enough data.")
        return {"resistance": [], "support": []}

    high = df["high"].values
    low = df["low"].values
    close = df["close"].iloc[-1]

    # Detect local maxima and minima
    resistance_levels = _find_swing_highs(high)
    support_levels = _find_swing_lows(low)

    # Merge nearby levels
    resistance_levels = _merge_levels(resistance_levels, close)
    support_levels = _merge_levels(support_levels, close)

    # Filter: resistance above close, support below close
    resistance_levels = sorted(
        [lvl for lvl in resistance_levels if lvl > close]
    )
    support_levels = sorted(
        [lvl for lvl in support_levels if lvl < close], reverse=True
    )

    return {"resistance": resistance_levels[:5], "support": support_levels[:5]}


def nearest_support(df: pd.DataFrame) -> float | None:
    """Return the nearest support level below the current close price."""
    levels = find_support_resistance(df)
    supports = levels.get("support", [])
    return supports[0] if supports else None


def nearest_resistance(df: pd.DataFrame) -> float | None:
    """Return the nearest resistance level above the current close price."""
    levels = find_support_resistance(df)
    resistances = levels.get("resistance", [])
    return resistances[0] if resistances else None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_swing_highs(arr: np.ndarray) -> list[float]:
    """Return price values at local maxima in *arr*."""
    levels = []
    for i in range(SWING_ORDER, len(arr) - SWING_ORDER):
        window = arr[i - SWING_ORDER: i + SWING_ORDER + 1]
        if arr[i] == window.max():
            levels.append(float(arr[i]))
    return levels


def _find_swing_lows(arr: np.ndarray) -> list[float]:
    """Return price values at local minima in *arr*."""
    levels = []
    for i in range(SWING_ORDER, len(arr) - SWING_ORDER):
        window = arr[i - SWING_ORDER: i + SWING_ORDER + 1]
        if arr[i] == window.min():
            levels.append(float(arr[i]))
    return levels


def _merge_levels(levels: list[float], reference: float) -> list[float]:
    """Merge price levels that are within ``MERGE_TOLERANCE`` of each other."""
    if not levels:
        return []

    levels = sorted(set(levels))
    merged: list[float] = [levels[0]]

    for lvl in levels[1:]:
        if abs(lvl - merged[-1]) / (reference + 1e-10) < MERGE_TOLERANCE:
            # Replace with average of the two
            merged[-1] = (merged[-1] + lvl) / 2
        else:
            merged.append(lvl)

    return merged
