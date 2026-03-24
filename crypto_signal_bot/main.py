"""
Crypto Futures Signal Analysis Bot – Main entry point.

Usage:
    python -m crypto_signal_bot.main                        # Run once, console output
    python -m crypto_signal_bot.main --loop                 # Run every RUN_INTERVAL_MINUTES
    python -m crypto_signal_bot.main --export-json out.json # Write signals as JSON
    python -m crypto_signal_bot.main --paper-trading        # Forward signals to PaperInvest
    python -m crypto_signal_bot.main --backtest             # Backtest on historical candles

No live trades are executed unless --paper-trading is combined with a live exchange adapter.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from crypto_signal_bot.config.settings import (
    PAIRS,
    RUN_INTERVAL_MINUTES,
    TIMEFRAMES,
)
from crypto_signal_bot.analysis.candlestick_patterns import detect_patterns
from crypto_signal_bot.analysis.indicators import compute_indicators
from crypto_signal_bot.analysis.market_structure import analyse_market_structure
from crypto_signal_bot.analysis.support_resistance import find_support_resistance
from crypto_signal_bot.analysis.volume_analysis import analyse_volume
from crypto_signal_bot.data.data_fetcher import fetch_ohlcv
from crypto_signal_bot.strategy.risk_management import calculate_risk
from crypto_signal_bot.strategy.signal_engine import generate_signal
from crypto_signal_bot.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def run_analysis(pair: str, timeframe: str) -> dict:
    """Run the full analysis pipeline for one pair/timeframe combination.

    Args:
        pair:      e.g. ``"BTC/USDT"``
        timeframe: e.g. ``"15m"``

    Returns:
        Result dictionary suitable for printing / alerting.
    """
    logger.info("Analysing %s [%s] …", pair, timeframe)

    # 1. Fetch OHLCV data
    df = fetch_ohlcv(pair, timeframe)
    if df.empty:
        logger.warning("No data for %s %s – skipping.", pair, timeframe)
        return {}

    # 2. Technical indicators
    df = compute_indicators(df)

    # 3. Volume analysis
    df = analyse_volume(df)

    # 4. Market structure
    df = analyse_market_structure(df)

    # 5. Candlestick patterns
    df = detect_patterns(df)

    # 6. Support / resistance
    sr_levels = find_support_resistance(df)

    # 7. Signal generation
    signal_result = generate_signal(df)

    # 8. Risk management
    risk = calculate_risk(df, signal_result["signal"])

    # 9. Summarise latest values for display
    last = df.iloc[-1]

    # Nearest Fibonacci level to current price
    fib = df.attrs.get("fibonacci", {})
    fib_nearest = _nearest_fibonacci(risk.get("entry"), fib)

    summary = {
        "pair": pair,
        "timeframe": timeframe,
        "signal": signal_result["signal"],
        "signal_strength": signal_result.get("signal_strength", signal_result["signal"]),
        "score": signal_result["score"],
        "confidence": signal_result["confidence"],
        "entry": risk.get("entry"),
        "stop_loss": risk.get("stop_loss"),
        "sl_pct": risk.get("sl_pct"),
        "tp1": risk.get("tp1"),
        "tp1_pct": risk.get("tp1_pct"),
        "tp2": risk.get("tp2"),
        "tp2_pct": risk.get("tp2_pct"),
        "tp3": risk.get("tp3"),
        "tp3_pct": risk.get("tp3_pct"),
        "take_profit": risk.get("take_profit"),
        "rr_ratio": risk.get("rr_ratio"),
        "rsi": _fmt(last.get("rsi")),
        "adx": _fmt(last.get("adx")),
        "adx_trend": _adx_label(last.get("adx")),
        "rsi_divergence": last.get("rsi_divergence", "none"),
        "trend": last.get("structure", "RANGE"),
        "pattern": last.get("pattern", "None"),
        "vol_spike": bool(last.get("vol_spike", False)),
        "vol_trend": last.get("vol_trend", "flat"),
        "bos": bool(last.get("bos", False)),
        "choch": bool(last.get("choch", False)),
        "sr_levels": sr_levels,
        "fibonacci": fib,
        "fib_nearest": fib_nearest,
        "signal_details": signal_result["details"],
    }
    return summary


# ---------------------------------------------------------------------------
# Formatting / printing
# ---------------------------------------------------------------------------

_SEPARATOR = "=" * 60


def print_signal(result: dict) -> None:
    """Print a formatted signal to the console."""
    if not result:
        return

    signal = result["signal"]
    signal_emoji = {"LONG": "🟢", "SHORT": "🔴", "NO TRADE": "⚪"}.get(signal, "")

    lines = [
        _SEPARATOR,
        f"  PAIR:       {result['pair']}",
        f"  TIMEFRAME:  {result['timeframe']}",
        "",
        f"  SIGNAL:     {signal_emoji} {signal}",
        "",
    ]

    if result.get("stop_loss") is not None:
        lines += [
            f"  ENTRY:      {result['entry']}",
            f"  STOP LOSS:  {result['stop_loss']}",
            f"  TAKE PROFIT:{result['take_profit']}",
            f"  RISK/REWARD: 1:{result['rr_ratio']}",
            "",
        ]
    elif result.get("entry") is not None:
        lines.append(f"  ENTRY:      {result['entry']}")
        lines.append("")

    lines += [
        f"  RSI:        {result['rsi']}",
        f"  ADX:        {result.get('adx', 'N/A')} ({result.get('adx_trend', 'N/A')})",
        f"  DIVERGENCE: {result.get('rsi_divergence', 'none')}",
        f"  TREND:      {result['trend']}",
        f"  PATTERN:    {result['pattern']}",
        f"  VOLUME:     {'Spike 🔥' if result['vol_spike'] else result['vol_trend']}",
        f"  BOS:        {'Yes' if result['bos'] else 'No'}",
        f"  CHOCH:      {'Yes' if result['choch'] else 'No'}",
        "",
        f"  CONFIDENCE: {result['confidence']}%",
        f"  SCORE:      {result['score']}",
    ]

    sr = result.get("sr_levels", {})
    if sr.get("resistance"):
        lines.append(
            f"  RESISTANCE: {', '.join(str(r) for r in sr['resistance'][:3])}"
        )
    if sr.get("support"):
        lines.append(
            f"  SUPPORT:    {', '.join(str(s) for s in sr['support'][:3])}"
        )

    fn = result.get("fib_nearest", {})
    if fn.get("support_fib"):
        sf = fn["support_fib"]
        lines.append(f"  FIB SUPP:   {sf['price']} (Fib {sf['level']})")
    if fn.get("resistance_fib"):
        rf = fn["resistance_fib"]
        lines.append(f"  FIB RES:    {rf['price']} (Fib {rf['level']})")

    lines.append(_SEPARATOR)
    print("\n".join(lines))


def export_json(results: list[dict], path: str) -> None:
    """Write signal results to a JSON file for the GitHub Pages dashboard.

    Args:
        results: List of signal result dicts produced by :func:`run_analysis`.
        path:    Destination file path.
    """
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signals": [_serialise(r) for r in results if r],
    }
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Signals exported to %s", path)


def _serialise(result: dict) -> dict:
    """Return a JSON-serialisable copy of a result dict."""
    safe: dict = {}
    for k, v in result.items():
        if isinstance(v, float) and (v != v):  # NaN check
            safe[k] = None
        elif isinstance(v, dict):
            safe[k] = _serialise(v)
        else:
            safe[k] = v
    return safe


def _fmt(value) -> str:
    """Format a float value to 2 decimal places, or 'N/A' if unavailable."""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _adx_label(adx_value) -> str:
    """Return a human-readable label for the ADX reading."""
    try:
        v = float(adx_value)
    except (TypeError, ValueError):
        return "N/A"
    if v >= 40:
        return "Very Strong"
    if v >= 25:
        return "Strong"
    if v >= 20:
        return "Moderate"
    return "Weak / Ranging"


def _nearest_fibonacci(price, fib: dict) -> dict:
    """Return the two Fibonacci levels immediately below and above *price*."""
    if not fib or price is None:
        return {}
    try:
        price = float(price)
    except (TypeError, ValueError):
        return {}

    sorted_levels = []
    for label, level in fib.items():
        try:
            sorted_levels.append((label, float(level)))
        except (TypeError, ValueError):
            continue
    sorted_levels.sort(key=lambda x: x[1])

    below = None
    above = None
    for label, lv in sorted_levels:
        if lv <= price:
            below = (label, round(lv, 6))
        else:
            above = (label, round(lv, 6))
            break  # first level above is enough

    result = {}
    if below:
        result["support_fib"] = {"level": below[0], "price": below[1]}
    if above:
        result["resistance_fib"] = {"level": above[0], "price": above[1]}
    return result


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def _maybe_init_paper_trading() -> "tuple | None":
    """Initialise paper trading components when enabled.

    Returns:
        ``(executor, analytics)`` tuple when paper trading is enabled,
        ``None`` otherwise.
    """
    try:
        from paper_trading.config import PAPER_TRADING_ENABLED  # type: ignore[import]
        if not PAPER_TRADING_ENABLED:
            return None
    except ImportError:
        return None

    from paper_trading.paperinvest_client import PaperInvestClient  # type: ignore[import]
    from paper_trading.paper_trade_executor import PaperTradeExecutor  # type: ignore[import]
    from paper_trading.portfolio_manager import PortfolioManager  # type: ignore[import]
    from paper_trading.performance_analytics import PerformanceAnalytics  # type: ignore[import]
    from paper_trading.trade_logger import TradeLogger  # type: ignore[import]

    client = PaperInvestClient()
    client.initialize_account()
    pm = PortfolioManager()
    tl = TradeLogger()
    executor = PaperTradeExecutor(client=client, portfolio=pm, trade_log=tl)
    analytics = PerformanceAnalytics(pm)
    logger.info("Paper trading ENABLED – signals will be forwarded to PaperInvest.")
    return executor, analytics


def main(
    loop: bool = False,
    export_json_path: str | None = None,
    paper_trading: bool = False,
    backtest: bool = False,
) -> None:
    """Run the signal bot.

    Args:
        loop:             When True, repeat every ``RUN_INTERVAL_MINUTES`` minutes.
        export_json_path: When set, write all signal results to this JSON file.
        paper_trading:    When True, forward signals to the PaperInvest API.
        backtest:         When True, run a backtest on historical OHLCV data.
    """
    if backtest:
        _run_backtest()
        return

    logger.info("Crypto Futures Signal Bot started.")
    logger.info("Pairs: %s | Timeframes: %s", PAIRS, TIMEFRAMES)

    pt_components = None
    if paper_trading:
        pt_components = _maybe_init_paper_trading()

    while True:
        results: list[dict] = []
        for pair in PAIRS:
            for tf in TIMEFRAMES:
                try:
                    result = run_analysis(pair, tf)
                    print_signal(result)
                    if result:
                        results.append(result)
                        # Forward to paper trading executor
                        if pt_components:
                            executor, _ = pt_components
                            action = executor.process_signal(result)
                            if action.get("action") not in ("SKIP",):
                                logger.info(
                                    "Paper trade: %s", action
                                )
                except Exception:  # noqa: BLE001
                    logger.exception("Error analysing %s %s", pair, tf)

        if export_json_path:
            export_json(results, export_json_path)

        # Print paper trading summary after each round
        if pt_components:
            _, analytics = pt_components
            metrics = analytics.compute()
            _print_paper_summary(metrics)

        if not loop:
            break

        logger.info(
            "Sleeping %d minutes until next run …", RUN_INTERVAL_MINUTES
        )
        time.sleep(RUN_INTERVAL_MINUTES * 60)


def _print_paper_summary(metrics: dict) -> None:
    """Print a paper trading performance summary to the console.

    Args:
        metrics: Dict returned by :meth:`~paper_trading.performance_analytics.PerformanceAnalytics.compute`.
    """
    lines = [
        "=" * 60,
        "  📊  PAPER TRADING SUMMARY",
        "=" * 60,
        f"  Balance:        ${metrics.get('balance', 0):,.2f}",
        f"  Equity:         ${metrics.get('equity', 0):,.2f}",
        f"  Realized PnL:   ${metrics.get('total_realized_pnl', 0):+,.4f}",
        f"  Total Trades:   {metrics.get('total_trades', 0)}",
        f"  Win Rate:       {metrics.get('win_rate_pct', 0):.1f}%",
        f"  Profit Factor:  {metrics.get('profit_factor') or 'N/A'}",
        f"  Sharpe Ratio:   {metrics.get('sharpe_ratio') or 'N/A'}",
        f"  Max Drawdown:   {metrics.get('max_drawdown_pct', 0):.2f}%",
        f"  Expectancy:     ${metrics.get('expectancy', 0):+,.4f}",
        "=" * 60,
    ]
    print("\n".join(lines))


def _run_backtest() -> None:
    """Run a simplified backtest using historical OHLCV candles.

    The backtest iterates over the configured PAIRS/TIMEFRAMES and simulates
    paper trades through the PaperTradeExecutor using a local simulation
    client.  Results are printed to the console.

    Note: This is a walk-forward simulation, not a multi-pass optimiser.
    """
    try:
        from paper_trading.paperinvest_client import PaperInvestClient, _sim_reset  # type: ignore[import]
        from paper_trading.paper_trade_executor import PaperTradeExecutor  # type: ignore[import]
        from paper_trading.portfolio_manager import PortfolioManager  # type: ignore[import]
        from paper_trading.performance_analytics import PerformanceAnalytics  # type: ignore[import]
        from paper_trading.trade_logger import TradeLogger  # type: ignore[import]
        from paper_trading.config import BACKTEST_START, BACKTEST_END  # type: ignore[import]
    except ImportError as exc:
        logger.error("Backtest requires the paper_trading module: %s", exc)
        return

    logger.info("Starting backtest from %s to %s …", BACKTEST_START, BACKTEST_END)
    print(f"\n{'='*60}\n  BACKTEST MODE  ({BACKTEST_START} → {BACKTEST_END})\n{'='*60}")

    import os
    import tempfile
    tmp_db = os.path.join(tempfile.gettempdir(), "backtest_portfolio.db")
    tmp_csv = os.path.join(tempfile.gettempdir(), "backtest_trades.csv")

    _sim_reset()
    client = PaperInvestClient()
    client.initialize_account()
    pm = PortfolioManager(db_path=tmp_db)
    tl = TradeLogger(csv_path=tmp_csv)
    executor = PaperTradeExecutor(client=client, portfolio=pm, trade_log=tl)
    analytics = PerformanceAnalytics(pm)

    for pair in PAIRS:
        for tf in TIMEFRAMES:
            try:
                result = run_analysis(pair, tf)
                if result:
                    executor.process_signal(result)
            except Exception:  # noqa: BLE001
                logger.exception("Backtest error for %s %s", pair, tf)

    metrics = analytics.compute()
    _print_paper_summary(metrics)
    print(f"\nDetailed trade log saved to: {tmp_csv}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Crypto Futures Signal Analysis Bot"
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help=f"Run continuously every {RUN_INTERVAL_MINUTES} minutes.",
    )
    parser.add_argument(
        "--export-json",
        metavar="PATH",
        default=None,
        help="Write signal results to a JSON file (for the GitHub Pages dashboard).",
    )
    parser.add_argument(
        "--paper-trading",
        action="store_true",
        help="Forward signals to the PaperInvest paper-trading API.",
    )
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="Run a backtest simulation on the current configured pairs/timeframes.",
    )
    args = parser.parse_args()
    main(
        loop=args.loop,
        export_json_path=args.export_json,
        paper_trading=args.paper_trading,
        backtest=args.backtest,
    )
