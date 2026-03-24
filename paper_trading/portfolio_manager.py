"""
Portfolio Manager – tracks account state in a local SQLite database.

Tables
------
portfolio
    Single-row table holding the latest account snapshot.

positions
    One row per open position.

trades
    Historical record of all closed trades.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Generator

from paper_trading.config import DAILY_LOSS_LIMIT, INITIAL_BALANCE, PORTFOLIO_DB

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_connection(db_path: str = PORTFOLIO_DB) -> sqlite3.Connection:
    """Return a SQLite connection with WAL journal mode and row_factory."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def _db(db_path: str = PORTFOLIO_DB) -> Generator[sqlite3.Connection, None, None]:
    conn = _get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# PortfolioManager
# ---------------------------------------------------------------------------

class PortfolioManager:
    """Persist and query paper trading state.

    All data is stored in a local SQLite database (``data/paper_portfolio.db``
    by default).

    Args:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str = PORTFOLIO_DB) -> None:
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self._db_path = db_path
        self._create_tables()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        with _db(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    id               INTEGER PRIMARY KEY CHECK (id = 1),
                    balance          REAL    NOT NULL DEFAULT 10000.0,
                    equity           REAL    NOT NULL DEFAULT 10000.0,
                    realized_pnl     REAL    NOT NULL DEFAULT 0.0,
                    peak_equity      REAL    NOT NULL DEFAULT 10000.0,
                    max_drawdown_pct REAL    NOT NULL DEFAULT 0.0,
                    daily_loss       REAL    NOT NULL DEFAULT 0.0,
                    daily_loss_date  TEXT    NOT NULL DEFAULT '',
                    total_trades     INTEGER NOT NULL DEFAULT 0,
                    winning_trades   INTEGER NOT NULL DEFAULT 0,
                    updated_at       TEXT    NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS positions (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol       TEXT    NOT NULL UNIQUE,
                    side         TEXT    NOT NULL,
                    entry_price  REAL    NOT NULL,
                    quantity     REAL    NOT NULL,
                    leverage     INTEGER NOT NULL DEFAULT 1,
                    stop_loss    REAL,
                    take_profit  REAL,
                    margin_used  REAL    NOT NULL DEFAULT 0.0,
                    order_id     TEXT    NOT NULL,
                    opened_at    TEXT    NOT NULL,
                    extra        TEXT    NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp      TEXT    NOT NULL,
                    symbol         TEXT    NOT NULL,
                    side           TEXT    NOT NULL,
                    entry_price    REAL    NOT NULL,
                    exit_price     REAL,
                    quantity       REAL    NOT NULL,
                    leverage       INTEGER NOT NULL DEFAULT 1,
                    stop_loss      REAL,
                    take_profit    REAL,
                    pnl            REAL,
                    trade_duration TEXT,
                    order_id       TEXT    NOT NULL,
                    status         TEXT    NOT NULL DEFAULT 'OPEN',
                    extra          TEXT    NOT NULL DEFAULT '{}'
                );
            """)

        # Ensure portfolio row exists
        with _db(self._db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO portfolio (id, updated_at) VALUES (1, ?)",
                (datetime.now(timezone.utc).isoformat(),),
            )

    # ------------------------------------------------------------------
    # Portfolio snapshot
    # ------------------------------------------------------------------

    def get_portfolio(self) -> dict[str, Any]:
        """Return the current portfolio snapshot.

        Returns:
            Dict with ``balance``, ``equity``, ``realized_pnl``, etc.
        """
        with _db(self._db_path) as conn:
            row = conn.execute("SELECT * FROM portfolio WHERE id=1").fetchone()
            return dict(row) if row else {}

    def update_balance(self, balance: float, equity: float) -> None:
        """Update the balance/equity and recalculate max drawdown.

        Args:
            balance: Available balance after current state.
            equity:  Total equity including unrealised PnL.
        """
        portfolio = self.get_portfolio()
        peak = max(portfolio.get("peak_equity", INITIAL_BALANCE), equity)
        drawdown = 0.0
        if peak > 0:
            drawdown = max(0.0, (peak - equity) / peak * 100)

        with _db(self._db_path) as conn:
            conn.execute(
                """UPDATE portfolio SET
                    balance          = ?,
                    equity           = ?,
                    peak_equity      = ?,
                    max_drawdown_pct = ?,
                    updated_at       = ?
                WHERE id = 1""",
                (balance, equity, peak, round(drawdown, 4),
                 datetime.now(timezone.utc).isoformat()),
            )

    def record_realized_pnl(self, pnl: float, won: bool) -> None:
        """Add a closed-trade PnL to cumulative counters.

        Args:
            pnl: Realised profit/loss amount.
            won: Whether the trade was profitable.
        """
        today = date.today().isoformat()
        portfolio = self.get_portfolio()
        daily_loss_date = portfolio.get("daily_loss_date", "")
        daily_loss = portfolio.get("daily_loss", 0.0) if daily_loss_date == today else 0.0

        if pnl < 0:
            daily_loss += abs(pnl)

        with _db(self._db_path) as conn:
            conn.execute(
                """UPDATE portfolio SET
                    realized_pnl   = realized_pnl + ?,
                    total_trades   = total_trades + 1,
                    winning_trades = winning_trades + ?,
                    daily_loss     = ?,
                    daily_loss_date= ?,
                    updated_at     = ?
                WHERE id = 1""",
                (pnl, 1 if won else 0, round(daily_loss, 4), today,
                 datetime.now(timezone.utc).isoformat()),
            )

    # ------------------------------------------------------------------
    # Daily loss limit check
    # ------------------------------------------------------------------

    def is_daily_loss_limit_hit(self) -> bool:
        """Return True if today's losses exceed the configured daily limit.

        Returns:
            True when trading should be paused for the day.
        """
        portfolio = self.get_portfolio()
        today = date.today().isoformat()
        if portfolio.get("daily_loss_date") != today:
            return False
        equity = portfolio.get("equity", INITIAL_BALANCE)
        daily_loss = portfolio.get("daily_loss", 0.0)
        if equity <= 0:
            return True
        return (daily_loss / equity) >= DAILY_LOSS_LIMIT

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def open_position(self, order: dict[str, Any]) -> None:
        """Persist a newly opened position.

        Args:
            order: Order dict returned by :class:`PaperInvestClient`.
        """
        extra = {k: v for k, v in order.items()
                 if k not in ("symbol", "side", "entry_price", "quantity",
                              "leverage", "stop_loss", "take_profit",
                              "margin_used", "order_id", "opened_at")}
        with _db(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO positions
                   (symbol, side, entry_price, quantity, leverage,
                    stop_loss, take_profit, margin_used, order_id, opened_at, extra)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    order["symbol"],
                    order["side"],
                    order["entry_price"],
                    order["quantity"],
                    order.get("leverage", 1),
                    order.get("stop_loss"),
                    order.get("take_profit"),
                    order.get("margin_used", 0.0),
                    order["order_id"],
                    order.get("opened_at", datetime.now(timezone.utc).isoformat()),
                    json.dumps(extra),
                ),
            )
        # Also add to trades table with OPEN status
        with _db(self._db_path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO trades
                   (timestamp, symbol, side, entry_price, quantity, leverage,
                    stop_loss, take_profit, order_id, status, extra)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    order.get("opened_at", datetime.now(timezone.utc).isoformat()),
                    order["symbol"],
                    order["side"],
                    order["entry_price"],
                    order["quantity"],
                    order.get("leverage", 1),
                    order.get("stop_loss"),
                    order.get("take_profit"),
                    order["order_id"],
                    "OPEN",
                    json.dumps(extra),
                ),
            )

    def close_position(self, order_id: str, exit_price: float, pnl: float) -> None:
        """Update records when a position is closed.

        Args:
            order_id:   The order identifier.
            exit_price: Closing price.
            pnl:        Realised profit / loss.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Calculate duration
        with _db(self._db_path) as conn:
            row = conn.execute(
                "SELECT opened_at FROM positions WHERE order_id=?", (order_id,)
            ).fetchone()
            duration = ""
            if row:
                try:
                    opened = datetime.fromisoformat(row["opened_at"])
                    delta = datetime.now(timezone.utc) - opened
                    hours, remainder = divmod(int(delta.total_seconds()), 3600)
                    minutes = remainder // 60
                    duration = f"{hours}h {minutes}m"
                except Exception:  # noqa: BLE001
                    logger.debug(
                        "Could not compute trade duration for order %s",
                        order_id, exc_info=True,
                    )

        with _db(self._db_path) as conn:
            conn.execute(
                "DELETE FROM positions WHERE order_id=?", (order_id,)
            )
            conn.execute(
                """UPDATE trades SET
                    exit_price     = ?,
                    pnl            = ?,
                    trade_duration = ?,
                    status         = 'CLOSED'
                WHERE order_id = ?""",
                (exit_price, round(pnl, 4), duration, order_id),
            )

    def get_open_positions(self) -> list[dict[str, Any]]:
        """Return all currently open positions.

        Returns:
            List of position dicts.
        """
        with _db(self._db_path) as conn:
            rows = conn.execute("SELECT * FROM positions").fetchall()
            return [dict(r) for r in rows]

    def count_open_positions(self) -> int:
        """Return the number of currently open positions.

        Returns:
            Integer count.
        """
        with _db(self._db_path) as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM positions").fetchone()
            return row["n"] if row else 0

    def has_open_position(self, symbol: str) -> bool:
        """Return True if there is already an open position for *symbol*.

        Args:
            symbol: Trading pair, e.g. ``"BTC/USDT"``.

        Returns:
            True if a position exists.
        """
        with _db(self._db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM positions WHERE symbol=?", (symbol,)
            ).fetchone()
            return (row["n"] if row else 0) > 0

    # ------------------------------------------------------------------
    # Trade history
    # ------------------------------------------------------------------

    def get_trade_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent trade records.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of trade dicts (most recent first).
        """
        with _db(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
