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
    # ── Layer-1 / Large-cap ──────────────────────────────────────────────────
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
    "TRX/USDT",
    "TON/USDT",
    "LTC/USDT",
    "BCH/USDT",
    "ETC/USDT",
    "XLM/USDT",
    "XMR/USDT",
    "ALGO/USDT",
    "VET/USDT",
    "HBAR/USDT",
    "FIL/USDT",
    "ICP/USDT",
    "EGLD/USDT",
    "CRO/USDT",
    "STX/USDT",
    "NEO/USDT",
    "IOTA/USDT",
    "WAVES/USDT",
    "DASH/USDT",
    "ZEC/USDT",
    "QTUM/USDT",
    "ONE/USDT",
    # ── DeFi ────────────────────────────────────────────────────────────────
    "DOGE/USDT",
    "UNI/USDT",
    "ATOM/USDT",
    "NEAR/USDT",
    "AAVE/USDT",
    "MKR/USDT",
    "COMP/USDT",
    "SNX/USDT",
    "CRV/USDT",
    "BAL/USDT",
    "1INCH/USDT",
    "SUSHI/USDT",
    "YFI/USDT",
    "DYDX/USDT",
    "GMX/USDT",
    "LDO/USDT",
    "RPL/USDT",
    "CAKE/USDT",
    "PENDLE/USDT",
    # ── Layer-2 / Scaling ────────────────────────────────────────────────────
    "ARB/USDT",
    "OP/USDT",
    "APT/USDT",
    "SUI/USDT",
    "SEI/USDT",
    "INJ/USDT",
    "IMX/USDT",
    "ZK/USDT",
    "STRK/USDT",
    "MANTA/USDT",
    # ── Meme coins ───────────────────────────────────────────────────────────
    "SHIB/USDT",
    "PEPE/USDT",
    "FLOKI/USDT",
    "WIF/USDT",
    "BONK/USDT",
    "BOME/USDT",
    "MEW/USDT",
    "ORDI/USDT",
    # ── AI / Data ────────────────────────────────────────────────────────────
    "FET/USDT",
    "AGIX/USDT",
    "TAO/USDT",
    "OCEAN/USDT",
    "GRT/USDT",
    "ARKM/USDT",
    "RNDR/USDT",
    # ── Gaming / Metaverse ───────────────────────────────────────────────────
    "AXS/USDT",
    "SAND/USDT",
    "MANA/USDT",
    "GALA/USDT",
    "ENJ/USDT",
    "GMT/USDT",
    # ── Infrastructure / Oracles ─────────────────────────────────────────────
    "BAND/USDT",
    "API3/USDT",
    "TRB/USDT",
    "UMA/USDT",
    # ── New & trending futures ───────────────────────────────────────────────
    "FTM/USDT",
    "TIA/USDT",
    "WLD/USDT",
    "JUP/USDT",
    "JTO/USDT",
    "W/USDT",
    "PYTH/USDT",
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
LONG_THRESHOLD: int = int(os.getenv("LONG_THRESHOLD", "5"))
SHORT_THRESHOLD: int = int(os.getenv("SHORT_THRESHOLD", "-5"))

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
