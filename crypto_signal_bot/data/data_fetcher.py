"""
Data fetcher module.

Retrieves OHLCV candlestick data from public APIs (CryptoCompare or
CoinGecko) and returns a normalised :class:`pandas.DataFrame` with columns:

    timestamp, open, high, low, close, volume

Supported timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d
"""

from __future__ import annotations

import time
from typing import Optional

import pandas as pd
import requests

from crypto_signal_bot.config.settings import (
    CANDLE_LIMIT,
    COINGECKO_BASE_URL,
    CRYPTOCOMPARE_API_KEY,
    CRYPTOCOMPARE_BASE_URL,
    DATA_SOURCE,
)
from crypto_signal_bot.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Timeframe helpers
# ---------------------------------------------------------------------------

# CryptoCompare endpoint + aggregate multiplier for each timeframe
_CC_TIMEFRAME_MAP: dict[str, tuple[str, int]] = {
    "1m": ("histominute", 1),
    "5m": ("histominute", 5),
    "15m": ("histominute", 15),
    "30m": ("histominute", 30),
    "1h": ("histohour", 1),
    "4h": ("histohour", 4),
    "1d": ("histoday", 1),
}

# CoinGecko uses seconds for the "days" parameter – map timeframe → days
_CG_TIMEFRAME_DAYS: dict[str, int] = {
    "1m": 1,
    "5m": 1,
    "15m": 2,
    "30m": 3,
    "1h": 7,
    "4h": 30,
    "1d": 365,
}

# CoinGecko coin-id mapping for common pairs
_CG_COIN_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "ADA": "cardano",
    "XRP": "ripple",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "DOGE": "dogecoin",
    "LTC": "litecoin",
    "BCH": "bitcoin-cash",
    "ETC": "ethereum-classic",
    "XLM": "stellar",
    "XMR": "monero",
    "ATOM": "cosmos",
    "UNI": "uniswap",
    "AAVE": "aave",
    "MKR": "maker",
    "COMP": "compound-governance-token",
    "SNX": "havven",
    "CRV": "curve-dao-token",
    "SUSHI": "sushi",
    "NEAR": "near",
    "ALGO": "algorand",
    "FIL": "filecoin",
    "ICP": "internet-computer",
    "HBAR": "hedera-hashgraph",
    "VET": "vechain",
    "SHIB": "shiba-inu",
    "TRX": "tron",
    "APT": "aptos",
    "ARB": "arbitrum",
    "OP": "optimism",
    "PEPE": "pepe",
    "SUI": "sui",
    "INJ": "injective-protocol",
    "FTM": "fantom",
    "SAND": "the-sandbox",
    "MANA": "decentraland",
    "AXS": "axie-infinity",
    "GALA": "gala",
    "GRT": "the-graph",
    "RNDR": "render-token",
    "FET": "fetch-ai",
    "OCEAN": "ocean-protocol",
    "LDO": "lido-dao",
    "CAKE": "pancakeswap-token",
    "GMX": "gmx",
    "DYDX": "dydx",
    "TIA": "celestia",
    "TON": "the-open-network",
    "WLD": "worldcoin-wld",
    "JUP": "jupiter-exchange-solana",
    "WIF": "dogwifcoin",
    "BONK": "bonk",
    "PYTH": "pyth-network",
    "SEI": "sei-network",
}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def fetch_ohlcv(
    pair: str,
    timeframe: str = "15m",
    limit: int = CANDLE_LIMIT,
    source: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch OHLCV data for *pair* at *timeframe* granularity.

    Args:
        pair:      Trading pair in ``BASE/QUOTE`` format, e.g. ``"BTC/USDT"``.
        timeframe: Candle interval.  Supported: 1m, 5m, 15m, 30m, 1h, 4h, 1d.
        limit:     Maximum number of candles to return.
        source:    Override the global ``DATA_SOURCE`` setting.

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume.
        Returns an empty DataFrame on error.
    """
    src = (source or DATA_SOURCE).lower()

    logger.info("Fetching %s %s data from %s …", pair, timeframe, src)

    try:
        if src == "cryptocompare":
            df = _fetch_cryptocompare(pair, timeframe, limit)
        elif src == "coingecko":
            df = _fetch_coingecko(pair, timeframe, limit)
        else:
            logger.error("Unknown data source: %s", src)
            return pd.DataFrame()
    except requests.exceptions.RequestException as exc:
        logger.error("Network error fetching %s: %s", pair, exc)
        return pd.DataFrame()
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error fetching %s", pair)
        return pd.DataFrame()

    if df.empty:
        logger.warning("No data returned for %s %s", pair, timeframe)
        return df

    df = _normalise(df)
    logger.info("Fetched %d candles for %s %s", len(df), pair, timeframe)
    return df


# ---------------------------------------------------------------------------
# CryptoCompare implementation
# ---------------------------------------------------------------------------


def _fetch_cryptocompare(pair: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Fetch OHLCV from CryptoCompare min-api."""
    base, quote = _split_pair(pair)

    if timeframe not in _CC_TIMEFRAME_MAP:
        logger.error("Unsupported timeframe for CryptoCompare: %s", timeframe)
        return pd.DataFrame()

    endpoint, aggregate = _CC_TIMEFRAME_MAP[timeframe]
    url = f"{CRYPTOCOMPARE_BASE_URL}/{endpoint}"

    params: dict = {
        "fsym": base,
        "tsym": quote,
        "limit": limit,
        "aggregate": aggregate,
    }
    if CRYPTOCOMPARE_API_KEY:
        params["api_key"] = CRYPTOCOMPARE_API_KEY

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("Response") == "Error":
        logger.error("CryptoCompare API error: %s", data.get("Message"))
        return pd.DataFrame()

    candles = data.get("Data", [])
    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(candles)
    df = df.rename(
        columns={
            "time": "timestamp",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volumefrom": "volume",
        }
    )
    # Keep only the columns we need
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    # Convert UNIX timestamp → datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    return df


# ---------------------------------------------------------------------------
# CoinGecko implementation
# ---------------------------------------------------------------------------


def _fetch_coingecko(pair: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Fetch OHLCV from CoinGecko /coins/{id}/ohlc endpoint."""
    base, quote = _split_pair(pair)

    coin_id = _CG_COIN_IDS.get(base.upper())
    if not coin_id:
        logger.error("CoinGecko coin ID not found for: %s", base)
        return pd.DataFrame()

    # CoinGecko OHLC endpoint supports only certain day values
    days = _CG_TIMEFRAME_DAYS.get(timeframe, 1)
    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/ohlc"
    params: dict = {"vs_currency": quote.lower(), "days": days}

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list) or not data:
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
    df["volume"] = 0.0  # CoinGecko OHLC endpoint does not include volume
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.tail(limit).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_pair(pair: str) -> tuple[str, str]:
    """Split ``"BTC/USDT"`` → ``("BTC", "USDT")``."""
    if "/" in pair:
        parts = pair.split("/")
    elif "-" in pair:
        parts = pair.split("-")
    else:
        # Fallback: assume 3-char base and remaining quote
        parts = [pair[:3], pair[3:]]
    if len(parts) != 2:
        raise ValueError(f"Cannot parse trading pair: {pair!r}")
    return parts[0].strip().upper(), parts[1].strip().upper()


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure correct dtypes, drop NaNs, and sort by timestamp."""
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=numeric_cols)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df
