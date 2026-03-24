"""
Market structure module.

Identifies:
- Higher highs (HH), Higher lows (HL) → UPTREND
- Lower highs (LH), Lower lows (LL) → DOWNTREND
- Sideways / mixed → RANGE
- Break of Structure (BOS)
- Change of Character (CHOCH)

Results are stored as new columns on the DataFrame.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema  # type: ignore

from crypto_signal_bot.utils.logger import get_logger

logger = get_logger(__name__)

# Order for local extrema detection (number of bars on each side)
SWING_ORDER: int = 5


def analyse_market_structure(df: pd.DataFrame) -> pd.DataFrame:
    """Add market structure columns to *df* and return the result.

    New columns / attributes added:
        swing_high   – True at swing high bars
        swing_low    – True at swing low bars
        structure    – 'UPTREND', 'DOWNTREND', or 'RANGE'
        bos          – True when a Break of Structure occurs
        choch        – True when a Change of Character occurs

    Args:
        df: OHLCV DataFrame.

    Returns:
        Modified DataFrame.
    """
    if df.empty or len(df) < SWING_ORDER * 2 + 1:
        logger.warning("Market structure analysis skipped: not enough data.")
        df["swing_high"] = False
        df["swing_low"] = False
        df["structure"] = "RANGE"
        df["bos"] = False
        df["choch"] = False
        return df

    df = df.copy()

    # ------------------------------------------------------------------
    # Detect swing highs and lows
    # ------------------------------------------------------------------
    high_arr = df["high"].values
    low_arr = df["low"].values

    high_indices = argrelextrema(high_arr, np.greater_equal, order=SWING_ORDER)[0]
    low_indices = argrelextrema(low_arr, np.less_equal, order=SWING_ORDER)[0]

    df["swing_high"] = False
    df["swing_low"] = False
    df.loc[df.index[high_indices], "swing_high"] = True
    df.loc[df.index[low_indices], "swing_low"] = True

    # ------------------------------------------------------------------
    # Classify trend using last few swings
    # ------------------------------------------------------------------
    df["structure"] = _classify_trend(df)

    # ------------------------------------------------------------------
    # Break of Structure (BOS) and Change of Character (CHOCH)
    # ------------------------------------------------------------------
    df["bos"] = False
    df["choch"] = False
    df = _detect_bos_choch(df)

    return df


# ---------------------------------------------------------------------------
# Trend classification
# ---------------------------------------------------------------------------


def _classify_trend(df: pd.DataFrame) -> pd.Series:
    """Classify each row as UPTREND, DOWNTREND, or RANGE."""
    structure = pd.Series("RANGE", index=df.index, dtype=str)

    swing_highs = df.loc[df["swing_high"], "high"]
    swing_lows = df.loc[df["swing_low"], "low"]

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return structure

    # Compare successive swing highs and lows
    hh = (swing_highs.diff() > 0).sum()
    lh = (swing_highs.diff() < 0).sum()
    hl = (swing_lows.diff() > 0).sum()
    ll = (swing_lows.diff() < 0).sum()

    if hh > lh and hl > ll:
        trend = "UPTREND"
    elif lh > hh and ll > hl:
        trend = "DOWNTREND"
    else:
        trend = "RANGE"

    # Apply to full series (simple global classification)
    structure[:] = trend
    return structure


# ---------------------------------------------------------------------------
# BOS and CHOCH detection
# ---------------------------------------------------------------------------


def _detect_bos_choch(df: pd.DataFrame) -> pd.DataFrame:
    """Detect Break of Structure and Change of Character.

    BOS: price breaks beyond the most recent swing high/low in the direction
         of the existing trend.
    CHOCH: price breaks beyond the most recent swing high/low *against* the
           existing trend, signalling a potential reversal.
    """
    close = df["close"]
    trend = df["structure"].iloc[-1]  # Use the overall trend

    swing_high_vals = df.loc[df["swing_high"], "high"]
    swing_low_vals = df.loc[df["swing_low"], "low"]

    if swing_high_vals.empty or swing_low_vals.empty:
        return df

    last_swing_high = swing_high_vals.iloc[-1]
    last_swing_low = swing_low_vals.iloc[-1]

    # BOS: in an uptrend, close breaks above last swing high
    #      in a downtrend, close breaks below last swing low
    if trend == "UPTREND":
        bos_mask = close > last_swing_high
        choch_mask = close < last_swing_low
    elif trend == "DOWNTREND":
        bos_mask = close < last_swing_low
        choch_mask = close > last_swing_high
    else:
        bos_mask = pd.Series(False, index=df.index)
        choch_mask = pd.Series(False, index=df.index)

    df.loc[bos_mask, "bos"] = True
    df.loc[choch_mask, "choch"] = True
    return df


# ---------------------------------------------------------------------------
# Convenience summary accessor
# ---------------------------------------------------------------------------


def get_structure_summary(df: pd.DataFrame) -> dict:
    """Return a concise dict describing the latest market structure."""
    if "structure" not in df.columns:
        return {"trend": "UNKNOWN", "bos": False, "choch": False}

    latest = df.iloc[-1]
    return {
        "trend": latest.get("structure", "RANGE"),
        "bos": bool(latest.get("bos", False)),
        "choch": bool(latest.get("choch", False)),
        "swing_high": bool(latest.get("swing_high", False)),
        "swing_low": bool(latest.get("swing_low", False)),
    }
