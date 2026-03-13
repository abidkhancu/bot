"""
Paper trading configuration.

All values can be overridden via environment variables (dotenv).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Master toggle
# ---------------------------------------------------------------------------
# Set to True to forward signals to the PaperInvest API / local simulator.
PAPER_TRADING_ENABLED: bool = os.getenv("PAPER_TRADING_ENABLED", "false").lower() == "true"

# ---------------------------------------------------------------------------
# PaperInvest API
# ---------------------------------------------------------------------------
PAPERINVEST_BASE_URL: str = os.getenv(
    "PAPERINVEST_BASE_URL", "https://app.paperinvest.io/api/v1"
)
# Single API key provided by PaperInvest (no secret required)
PAPERINVEST_API_KEY: str = os.getenv("PAPERINVEST_API_KEY", "")

# Seconds to wait before retrying a failed API call
API_RETRY_DELAY: float = float(os.getenv("PAPERINVEST_RETRY_DELAY", "2.0"))
API_MAX_RETRIES: int = int(os.getenv("PAPERINVEST_MAX_RETRIES", "3"))
API_TIMEOUT: float = float(os.getenv("PAPERINVEST_TIMEOUT", "10.0"))

# ---------------------------------------------------------------------------
# Account / simulation settings
# ---------------------------------------------------------------------------
# Starting balance used when running in local simulation mode
INITIAL_BALANCE: float = float(os.getenv("PAPER_INITIAL_BALANCE", "10000.0"))

# Default leverage for simulated futures positions
DEFAULT_LEVERAGE: int = int(os.getenv("PAPER_DEFAULT_LEVERAGE", "5"))

# ---------------------------------------------------------------------------
# Risk management
# ---------------------------------------------------------------------------
# Maximum fraction of portfolio to risk on any single trade (e.g. 0.01 = 1%)
MAX_RISK_PER_TRADE: float = float(os.getenv("PAPER_MAX_RISK_PER_TRADE", "0.01"))

# Maximum number of simultaneously open positions
MAX_OPEN_TRADES: int = int(os.getenv("PAPER_MAX_OPEN_TRADES", "5"))

# Maximum total loss allowed in a single day before halting new trades
# expressed as a fraction of portfolio value (e.g. 0.05 = 5%)
DAILY_LOSS_LIMIT: float = float(os.getenv("PAPER_DAILY_LOSS_LIMIT", "0.05"))

# Minimum signal confidence (%) required to place a paper trade
MIN_CONFIDENCE: int = int(os.getenv("PAPER_MIN_CONFIDENCE", "40"))

# Minimum signal score magnitude required
MIN_SCORE: int = int(os.getenv("PAPER_MIN_SCORE", "5"))

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
DATA_DIR: str = os.getenv("PAPER_DATA_DIR", "data")
PORTFOLIO_DB: str = os.path.join(DATA_DIR, "paper_portfolio.db")
TRADE_LOG_CSV: str = os.path.join(
    os.getenv("PAPER_LOG_DIR", "logs"), "paper_trades.csv"
)

# ---------------------------------------------------------------------------
# Backtesting
# ---------------------------------------------------------------------------
BACKTEST_START: str = os.getenv("BACKTEST_START", "2024-01-01")
BACKTEST_END: str = os.getenv("BACKTEST_END", "2024-12-31")
