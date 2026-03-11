"""
Signal engine module.

Combines output from all analysis modules into a single trading signal using a
weighted scoring system.

Scoring rules
-------------
Indicator                         | Bullish | Bearish
----------------------------------|---------|--------
RSI < 30 (oversold)               | +2      | –
RSI > 70 (overbought)             | –       | -2
RSI 30-45 (mild oversold)         | +1      | –
RSI 55-70 (mild overbought)       | –       | -1
EMA crossover (9 > 21)            | +2      | –
EMA crossover (9 < 21)            | –       | -2
Golden cross (EMA50 > SMA200)     | +2      | –
Death cross  (EMA50 < SMA200)     | –       | -2
MACD crossover (bullish)          | +1      | –
MACD crossover (bearish)          | –       | -1
MACD position positive            | +1      | –
MACD position negative            | –       | -1
Bullish candlestick pattern       | +3      | –
Bearish candlestick pattern       | –       | -3
Volume spike                      | +1      | –
Market structure UPTREND          | +2      | –
Market structure DOWNTREND        | –       | -2
BOS in trend direction            | +1      | -1
CHOCH (reversal signal)           | +/-1    | +/-1
Price above VWAP                  | +1      | –
Price below VWAP                  | –       | -1
BB position (outside band)        | +/-1    | +/-1
Stochastic oversold/overbought    | +1      | -1
Ichimoku: price above cloud       | +2      | –
Ichimoku: price below cloud       | –       | -2

Decision thresholds (configurable via settings):
    score >=  LONG_THRESHOLD  → LONG   (default: 5)
    score <= SHORT_THRESHOLD  → SHORT  (default: -5)
    otherwise                 → NO TRADE

Signal strength tiers:
    LONG  score ≥ 10 → STRONG LONG
    LONG  score  5-9 → LONG
    SHORT score ≤-10 → STRONG SHORT
    SHORT score -5–-9→ SHORT
"""

from __future__ import annotations

import math

import pandas as pd

from crypto_signal_bot.config.settings import LONG_THRESHOLD, SHORT_THRESHOLD
from crypto_signal_bot.utils.logger import get_logger

logger = get_logger(__name__)

# Bullish patterns (score +3)
_BULLISH_PATTERNS = {
    "Hammer",
    "Bullish Pin Bar",
    "Bullish Engulfing",
    "Morning Star",
}

# Bearish patterns (score -3)
_BEARISH_PATTERNS = {
    "Shooting Star",
    "Bearish Pin Bar",
    "Bearish Engulfing",
    "Evening Star",
}


def generate_signal(df: pd.DataFrame) -> dict:
    """Generate a trading signal by scoring all available indicators.

    Args:
        df: OHLCV DataFrame after all analysis modules have been applied.

    Returns:
        Dictionary with keys:
            signal         – 'LONG', 'SHORT', or 'NO TRADE'
            signal_strength– human-readable strength label
            score          – total raw score
            confidence     – score-based confidence percentage (0-100)
            details        – dict of individual score contributions
    """
    if df.empty or len(df) < 2:
        logger.warning("Signal engine: insufficient data.")
        return {
            "signal": "NO TRADE",
            "signal_strength": "NO TRADE",
            "score": 0,
            "confidence": 0,
            "details": {},
        }

    last = df.iloc[-1]
    details: dict[str, int] = {}

    # ------------------------------------------------------------------
    # RSI
    # ------------------------------------------------------------------
    rsi = _get(last, "rsi")
    if rsi is not None:
        if rsi < 30:
            _add(details, "RSI oversold (<30)", 2)
        elif rsi > 70:
            _add(details, "RSI overbought (>70)", -2)
        elif rsi < 45:
            _add(details, "RSI mild oversold (30-45)", 1)
        elif rsi > 55:
            _add(details, "RSI mild overbought (55-70)", -1)

    # ------------------------------------------------------------------
    # EMA crossover (EMA9 vs EMA21)
    # ------------------------------------------------------------------
    ema9 = _get(last, "ema_9")
    ema21 = _get(last, "ema_21")
    if ema9 is not None and ema21 is not None:
        if ema9 > ema21:
            _add(details, "EMA9 > EMA21 (bullish cross)", 2)
        else:
            _add(details, "EMA9 < EMA21 (bearish cross)", -2)

    # ------------------------------------------------------------------
    # Golden / Death cross (EMA50 vs SMA200)
    # ------------------------------------------------------------------
    ema50 = _get(last, "ema_50")
    sma200 = _get(last, "sma_200")
    if ema50 is not None and sma200 is not None:
        if ema50 > sma200:
            _add(details, "Golden cross (EMA50 > SMA200)", 2)
        else:
            _add(details, "Death cross (EMA50 < SMA200)", -2)

    # ------------------------------------------------------------------
    # MACD – crossover AND position
    # ------------------------------------------------------------------
    macd_val = _get(last, "macd")
    macd_hist = _get(last, "macd_hist")
    if macd_hist is not None:
        prev_hist = _get(df.iloc[-2], "macd_hist") if len(df) > 1 else None
        if prev_hist is not None:
            if macd_hist > 0 and prev_hist <= 0:
                _add(details, "MACD bullish crossover", 1)
            elif macd_hist < 0 and prev_hist >= 0:
                _add(details, "MACD bearish crossover", -1)
    if macd_val is not None:
        if macd_val > 0:
            _add(details, "MACD positive (bullish momentum)", 1)
        else:
            _add(details, "MACD negative (bearish momentum)", -1)

    # ------------------------------------------------------------------
    # Candlestick pattern
    # ------------------------------------------------------------------
    pattern = last.get("pattern", "None")
    if pattern in _BULLISH_PATTERNS:
        _add(details, f"Bullish pattern: {pattern}", 3)
    elif pattern in _BEARISH_PATTERNS:
        _add(details, f"Bearish pattern: {pattern}", -3)

    # ------------------------------------------------------------------
    # Volume spike
    # ------------------------------------------------------------------
    vol_spike = last.get("vol_spike", False)
    if vol_spike:
        _add(details, "Volume spike", 1)

    # ------------------------------------------------------------------
    # Market structure trend
    # ------------------------------------------------------------------
    structure = last.get("structure", "RANGE")
    if structure == "UPTREND":
        _add(details, "Market structure uptrend", 2)
    elif structure == "DOWNTREND":
        _add(details, "Market structure downtrend", -2)

    # ------------------------------------------------------------------
    # Break of Structure / Change of Character
    # ------------------------------------------------------------------
    bos = last.get("bos", False)
    choch = last.get("choch", False)
    if bos:
        if structure == "UPTREND":
            _add(details, "BOS (uptrend continuation)", 1)
        elif structure == "DOWNTREND":
            _add(details, "BOS (downtrend continuation)", -1)
    if choch:
        if structure == "UPTREND":
            _add(details, "CHOCH (potential reversal down)", -1)
        elif structure == "DOWNTREND":
            _add(details, "CHOCH (potential reversal up)", 1)

    # ------------------------------------------------------------------
    # VWAP position
    # ------------------------------------------------------------------
    vwap = _get(last, "vwap")
    close = _get(last, "close")
    if vwap is not None and close is not None:
        if close > vwap:
            _add(details, "Price above VWAP", 1)
        else:
            _add(details, "Price below VWAP", -1)

    # ------------------------------------------------------------------
    # Bollinger Band position
    # ------------------------------------------------------------------
    bb_upper = _get(last, "bb_upper")
    bb_lower = _get(last, "bb_lower")
    if bb_upper is not None and bb_lower is not None and close is not None:
        if close > bb_upper:
            _add(details, "Price above upper BB (overbought)", -1)
        elif close < bb_lower:
            _add(details, "Price below lower BB (oversold)", 1)

    # ------------------------------------------------------------------
    # Stochastic
    # ------------------------------------------------------------------
    stoch_k = _get(last, "stoch_k")
    if stoch_k is not None:
        if stoch_k < 20:
            _add(details, "Stochastic oversold (<20)", 1)
        elif stoch_k > 80:
            _add(details, "Stochastic overbought (>80)", -1)

    # ------------------------------------------------------------------
    # Ichimoku Cloud position
    # ------------------------------------------------------------------
    span_a = _get(last, "ichimoku_span_a")
    span_b = _get(last, "ichimoku_span_b")
    if span_a is not None and span_b is not None and close is not None:
        cloud_top = max(span_a, span_b)
        cloud_bottom = min(span_a, span_b)
        if close > cloud_top:
            _add(details, "Price above Ichimoku cloud (bullish)", 2)
        elif close < cloud_bottom:
            _add(details, "Price below Ichimoku cloud (bearish)", -2)

    # ------------------------------------------------------------------
    # Aggregate score
    # ------------------------------------------------------------------
    score = sum(details.values())

    if score >= LONG_THRESHOLD:
        signal = "LONG"
    elif score <= SHORT_THRESHOLD:
        signal = "SHORT"
    else:
        signal = "NO TRADE"

    # Signal strength tier
    if signal == "LONG":
        signal_strength = "STRONG LONG" if score >= 10 else "LONG"
    elif signal == "SHORT":
        signal_strength = "STRONG SHORT" if score <= -10 else "SHORT"
    else:
        signal_strength = "NO TRADE"

    # Confidence: scale score to 0-100 (max possible ~26 with all indicators)
    max_possible = 26
    confidence = min(100, int(abs(score) / max_possible * 100))

    logger.info(
        "Signal: %s (%s) | Score: %d | Confidence: %d%%",
        signal, signal_strength, score, confidence,
    )

    return {
        "signal": signal,
        "signal_strength": signal_strength,
        "score": score,
        "confidence": confidence,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(row: pd.Series, key: str):
    """Safely retrieve a value from a row; return None if missing or NaN."""
    val = row.get(key)
    if val is None:
        return None
    try:
        if math.isnan(float(val)):
            return None
    except (TypeError, ValueError):
        pass
    return val


def _add(details: dict, key: str, value: int) -> None:
    """Accumulate score details."""
    details[key] = details.get(key, 0) + value
