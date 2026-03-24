"""
Volume analysis module.

Detects:
- Volume spikes (current volume > average * threshold)
- Volume trend (rising / falling / flat)
- Volume-price divergence (price up but volume falling, or vice-versa)

All results are stored as new columns on the DataFrame.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crypto_signal_bot.utils.logger import get_logger

logger = get_logger(__name__)

# Multiplier above average to classify as a "spike"
SPIKE_MULTIPLIER: float = 2.0
# Rolling window for average volume comparison
VOLUME_WINDOW: int = 20


def analyse_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Add volume analysis columns to *df* and return the result.

    New columns added:
        vol_avg          – rolling mean volume over ``VOLUME_WINDOW`` bars
        vol_ratio        – current volume / vol_avg
        vol_spike        – True when vol_ratio >= SPIKE_MULTIPLIER
        vol_trend        – 'rising', 'falling', or 'flat'
        vol_divergence   – 'bullish_div', 'bearish_div', or 'none'

    Args:
        df: OHLCV DataFrame (must contain ``close`` and ``volume`` columns).

    Returns:
        Modified DataFrame with volume analysis columns.
    """
    if df.empty or "volume" not in df.columns:
        logger.warning("Volume analysis skipped: missing data.")
        return df

    df = df.copy()

    # Average volume
    df["vol_avg"] = df["volume"].rolling(VOLUME_WINDOW, min_periods=1).mean()

    # Ratio of current volume to average
    df["vol_ratio"] = df["volume"] / (df["vol_avg"] + 1e-10)

    # Spike detection
    df["vol_spike"] = df["vol_ratio"] >= SPIKE_MULTIPLIER

    # Volume trend (compare recent half-window mean vs previous)
    half = max(VOLUME_WINDOW // 2, 1)
    recent_vol = df["volume"].rolling(half, min_periods=1).mean()
    prior_vol = df["volume"].rolling(VOLUME_WINDOW, min_periods=1).mean().shift(half)
    vol_change = recent_vol - prior_vol.fillna(recent_vol)

    df["vol_trend"] = "flat"
    df.loc[vol_change > prior_vol * 0.05, "vol_trend"] = "rising"
    df.loc[vol_change < -prior_vol * 0.05, "vol_trend"] = "falling"

    # Volume-price divergence
    df["vol_divergence"] = _detect_divergence(df)

    return df


# ---------------------------------------------------------------------------
# Divergence detection
# ---------------------------------------------------------------------------


def _detect_divergence(df: pd.DataFrame) -> pd.Series:
    """Detect volume-price divergence over a rolling window.

    Bullish divergence: price making lower lows but volume decreasing (selling
    pressure diminishing).
    Bearish divergence: price making higher highs but volume decreasing
    (buying pressure waning).

    Returns:
        Series with values: 'bullish_div', 'bearish_div', or 'none'.
    """
    window = 5
    result = pd.Series("none", index=df.index, dtype=str)

    price_change = df["close"].diff(window)
    vol_change = df["volume"].diff(window)

    # Bearish divergence: price up but volume down
    bearish = (price_change > 0) & (vol_change < 0)
    # Bullish divergence: price down but volume down (selling exhaustion)
    bullish = (price_change < 0) & (vol_change < 0)

    result[bearish] = "bearish_div"
    result[bullish] = "bullish_div"

    return result
