"""
Technical indicators module.

Computes a wide set of technical indicators and appends them as new columns
to the input OHLCV DataFrame.  Uses *pandas-ta* when available and falls back
to pure-NumPy/pandas implementations for each indicator so the module works
even without the optional library.

Indicators provided
-------------------
- RSI (14)
- SMA (20, 50, 200)
- EMA (9, 21, 50)
- MACD (12, 26, 9)
- Bollinger Bands (20, 2σ)
- Stochastic Oscillator (14, 3)
- ATR (14)
- VWAP
- Ichimoku Cloud
- Fibonacci retracement levels (stored as scalar metadata on the DataFrame)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crypto_signal_bot.utils.logger import get_logger

logger = get_logger(__name__)

# Try to import pandas-ta; fall back to manual implementations if unavailable.
try:
    import pandas_ta as ta  # type: ignore

    _PANDAS_TA_AVAILABLE = True
except ImportError:
    _PANDAS_TA_AVAILABLE = False
    logger.warning(
        "pandas-ta not installed – using built-in indicator calculations."
    )


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicator columns to *df* and return the result.

    Args:
        df: OHLCV DataFrame with columns: timestamp, open, high, low, close,
            volume.

    Returns:
        The same DataFrame (modified in-place) with extra indicator columns.
    """
    if df.empty or len(df) < 2:
        logger.warning("DataFrame too small to compute indicators.")
        return df

    df = df.copy()

    if _PANDAS_TA_AVAILABLE:
        df = _compute_with_pandas_ta(df)
    else:
        df = _compute_manual(df)

    df = _compute_vwap(df)
    df = _compute_ichimoku(df)
    df = _add_fibonacci(df)
    df = _compute_adx(df)
    df = _detect_rsi_divergence(df)

    return df


# ---------------------------------------------------------------------------
# pandas-ta path
# ---------------------------------------------------------------------------


def _compute_with_pandas_ta(df: pd.DataFrame) -> pd.DataFrame:
    """Use pandas-ta to calculate indicators."""
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # RSI
    df["rsi"] = ta.rsi(close, length=14)

    # SMAs
    for period in (20, 50, 200):
        df[f"sma_{period}"] = ta.sma(close, length=period)

    # EMAs
    for period in (9, 21, 50):
        df[f"ema_{period}"] = ta.ema(close, length=period)

    # MACD
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty:
        df["macd"] = macd_df.iloc[:, 0]
        df["macd_signal"] = macd_df.iloc[:, 2]
        df["macd_hist"] = macd_df.iloc[:, 1]

    # Bollinger Bands
    bb_df = ta.bbands(close, length=20, std=2)
    if bb_df is not None and not bb_df.empty:
        df["bb_lower"] = bb_df.iloc[:, 0]
        df["bb_mid"] = bb_df.iloc[:, 1]
        df["bb_upper"] = bb_df.iloc[:, 2]

    # Stochastic
    stoch_df = ta.stoch(high, low, close, k=14, d=3)
    if stoch_df is not None and not stoch_df.empty:
        df["stoch_k"] = stoch_df.iloc[:, 0]
        df["stoch_d"] = stoch_df.iloc[:, 1]

    # ATR
    df["atr"] = ta.atr(high, low, close, length=14)

    # ADX via pandas-ta (uses adx())
    adx_df = ta.adx(high, low, close, length=14)
    if adx_df is not None and not adx_df.empty:
        # columns: ADX_14, DMP_14, DMN_14
        df["adx"] = adx_df.iloc[:, 0]
        df["adx_di_pos"] = adx_df.iloc[:, 1]
        df["adx_di_neg"] = adx_df.iloc[:, 2]

    return df


# ---------------------------------------------------------------------------
# Manual fallback implementations
# ---------------------------------------------------------------------------


def _compute_manual(df: pd.DataFrame) -> pd.DataFrame:
    """Pure pandas/NumPy indicator calculations."""
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # RSI
    df["rsi"] = _rsi(close, 14)

    # SMAs
    for period in (20, 50, 200):
        df[f"sma_{period}"] = close.rolling(period).mean()

    # EMAs
    for period in (9, 21, 50):
        df[f"ema_{period}"] = close.ewm(span=period, adjust=False).mean()

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Bollinger Bands
    rolling_mean = close.rolling(20).mean()
    rolling_std = close.rolling(20).std()
    df["bb_mid"] = rolling_mean
    df["bb_upper"] = rolling_mean + 2 * rolling_std
    df["bb_lower"] = rolling_mean - 2 * rolling_std

    # Stochastic Oscillator
    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    df["stoch_k"] = 100 * (close - low14) / (high14 - low14 + 1e-10)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()

    # ATR
    df["atr"] = _atr(high, low, close, 14)

    return df

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - 100 / (1 + rs)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


# ---------------------------------------------------------------------------
# VWAP
# ---------------------------------------------------------------------------


def _compute_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Compute VWAP using cumulative sum within each trading session."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    tp_volume = typical_price * df["volume"]
    df["vwap"] = tp_volume.cumsum() / (df["volume"].cumsum() + 1e-10)
    return df


# ---------------------------------------------------------------------------
# Ichimoku Cloud
# ---------------------------------------------------------------------------


def _compute_ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Ichimoku Cloud components."""
    high = df["high"]
    low = df["low"]

    # Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
    df["ichimoku_tenkan"] = (high.rolling(9).max() + low.rolling(9).min()) / 2

    # Kijun-sen (Base Line): (26-period high + 26-period low) / 2
    df["ichimoku_kijun"] = (high.rolling(26).max() + low.rolling(26).min()) / 2

    # Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2, shifted 26 periods
    span_a = (df["ichimoku_tenkan"] + df["ichimoku_kijun"]) / 2
    df["ichimoku_span_a"] = span_a.shift(26)

    # Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2, shifted 26 periods
    span_b = (high.rolling(52).max() + low.rolling(52).min()) / 2
    df["ichimoku_span_b"] = span_b.shift(26)

    # Chikou Span (Lagging Span): close shifted back 26 periods
    df["ichimoku_chikou"] = df["close"].shift(-26)

    return df


# ---------------------------------------------------------------------------
# Fibonacci retracement levels
# ---------------------------------------------------------------------------


def _add_fibonacci(df: pd.DataFrame) -> pd.DataFrame:
    """Store Fibonacci retracement levels as DataFrame attributes.

    Levels are computed over the full price range in the DataFrame.
    Access via ``df.attrs["fibonacci"]``.
    """
    price_high = df["high"].max()
    price_low = df["low"].min()
    diff = price_high - price_low

    fib_levels = {
        "0.0": price_low,
        "0.236": price_low + 0.236 * diff,
        "0.382": price_low + 0.382 * diff,
        "0.5": price_low + 0.5 * diff,
        "0.618": price_low + 0.618 * diff,
        "0.786": price_low + 0.786 * diff,
        "1.0": price_high,
    }
    df.attrs["fibonacci"] = fib_levels
    return df


# ---------------------------------------------------------------------------
# ADX (Average Directional Index) – trend strength
# ---------------------------------------------------------------------------


def _compute_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Compute ADX, +DI and -DI (manual implementation).

    Columns added:
        adx       – 0-100 trend strength (>25 = trending, >40 = strong trend)
        adx_di_pos – +DI (bullish directional movement)
        adx_di_neg – -DI (bearish directional movement)
    """
    if "adx" in df.columns:
        # Already computed by pandas-ta path
        return df

    high = df["high"]
    low = df["low"]
    close = df["close"]

    # True Range
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    # Directional movements
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm_s = pd.Series(plus_dm, index=df.index).ewm(com=period - 1, min_periods=period).mean()
    minus_dm_s = pd.Series(minus_dm, index=df.index).ewm(com=period - 1, min_periods=period).mean()
    atr_s = tr.ewm(com=period - 1, min_periods=period).mean()

    plus_di = 100 * plus_dm_s / (atr_s + 1e-10)
    minus_di = 100 * minus_dm_s / (atr_s + 1e-10)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)

    df["adx"] = dx.ewm(com=period - 1, min_periods=period).mean()
    df["adx_di_pos"] = plus_di
    df["adx_di_neg"] = minus_di
    return df


# ---------------------------------------------------------------------------
# RSI divergence detector
# ---------------------------------------------------------------------------


def _detect_rsi_divergence(df: pd.DataFrame, lookback: int = 14) -> pd.DataFrame:
    """Detect classic RSI divergence over the last *lookback* candles.

    Adds column ``rsi_divergence``:
        "bullish"  – price made a lower low but RSI did not  (reversal up)
        "bearish"  – price made a higher high but RSI did not (reversal down)
        "none"     – no divergence detected
    """
    df["rsi_divergence"] = "none"

    if "rsi" not in df.columns or len(df) < lookback + 2:
        return df

    close = df["close"].to_numpy()
    rsi = df["rsi"].to_numpy()
    div = np.full(len(df), "none", dtype=object)

    for i in range(lookback, len(df)):
        window_close = close[i - lookback: i + 1]
        window_rsi = rsi[i - lookback: i + 1]

        if np.any(np.isnan(window_rsi)):
            continue

        prev_close = window_close[:-1]
        prev_rsi = window_rsi[:-1]

        prev_low_idx = int(np.argmin(prev_close))
        prev_high_idx = int(np.argmax(prev_close))

        cur_close = window_close[-1]
        cur_rsi = window_rsi[-1]

        # Bullish divergence: lower low in price but higher low in RSI
        if cur_close < prev_close[prev_low_idx] and cur_rsi > prev_rsi[prev_low_idx]:
            div[i] = "bullish"
        # Bearish divergence: higher high in price but lower high in RSI
        elif cur_close > prev_close[prev_high_idx] and cur_rsi < prev_rsi[prev_high_idx]:
            div[i] = "bearish"

    df["rsi_divergence"] = div
    return df
