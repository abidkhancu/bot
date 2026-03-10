"""
Configuration settings for the crypto signal bot.
Loads environment variables via python-dotenv with sensible defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Pairs and timeframes to analyse
# ---------------------------------------------------------------------------
PAIRS: list[str] = os.getenv(
    "PAIRS", "BTC/USDT,ETH/USDT,SOL/USDT"
).split(",")

TIMEFRAMES: list[str] = os.getenv(
    "TIMEFRAMES", "1m,5m,15m,1h,4h"
).split(",")

# ---------------------------------------------------------------------------
# Full catalogue of supported pairs (used by the interactive Web UI)
# ---------------------------------------------------------------------------
ALL_PAIRS: list[str] = [
    # Layer-1 / large caps
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "DOT/USDT",
    "MATIC/USDT",
    "LINK/USDT",
    # Mid caps / DeFi
    "DOGE/USDT",
    "LTC/USDT",
    "BCH/USDT",
    "UNI/USDT",
    "ATOM/USDT",
    "FTM/USDT",
    "NEAR/USDT",
    "APT/USDT",
    "ARB/USDT",
    "OP/USDT",
    # Meme coins
    "SHIB/USDT",
    "PEPE/USDT",
    "FLOKI/USDT",
    # Other popular futures
    "TRX/USDT",
    "TON/USDT",
    "SUI/USDT",
    "SEI/USDT",
    "INJ/USDT",
    "TIA/USDT",
    "WLD/USDT",
    "JUP/USDT",
    "WIF/USDT",
    "BONK/USDT",
]

# ---------------------------------------------------------------------------
# All supported timeframes (used by the interactive Web UI)
# ---------------------------------------------------------------------------
ALL_TIMEFRAMES: list[str] = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

# ---------------------------------------------------------------------------
# Data source
# ---------------------------------------------------------------------------
# Supported sources: "cryptocompare", "coingecko"
DATA_SOURCE: str = os.getenv("DATA_SOURCE", "cryptocompare")

# CryptoCompare public API (no key required for basic OHLCV)
CRYPTOCOMPARE_BASE_URL: str = "https://min-api.cryptocompare.com/data"
CRYPTOCOMPARE_API_KEY: str = os.getenv("CRYPTOCOMPARE_API_KEY", "")

# CoinGecko public API
COINGECKO_BASE_URL: str = "https://api.coingecko.com/api/v3"

# ---------------------------------------------------------------------------
# Candle limits
# ---------------------------------------------------------------------------
# Number of candles to fetch per request
CANDLE_LIMIT: int = int(os.getenv("CANDLE_LIMIT", "200"))

# ---------------------------------------------------------------------------
# Signal engine thresholds
# ---------------------------------------------------------------------------
LONG_THRESHOLD: int = int(os.getenv("LONG_THRESHOLD", "6"))
SHORT_THRESHOLD: int = int(os.getenv("SHORT_THRESHOLD", "-6"))

# ---------------------------------------------------------------------------
# Risk management
# ---------------------------------------------------------------------------
RISK_REWARD_RATIO: float = float(os.getenv("RISK_REWARD_RATIO", "3.0"))

# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------
# Run analysis every N minutes (used by main.py scheduler)
RUN_INTERVAL_MINUTES: int = int(os.getenv("RUN_INTERVAL_MINUTES", "15"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = os.getenv("LOG_FILE", "crypto_signal_bot.log")
