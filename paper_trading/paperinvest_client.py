"""
PaperInvest API client.

Wraps the PaperInvest REST API with automatic retry logic and a transparent
local-simulation fallback for when no API credentials are configured.

If ``PAPERINVEST_API_KEY`` is empty the client falls back to an in-process
simulation that mirrors the same interface so the rest of the code works
without any external dependency.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests

from paper_trading.config import (
    API_MAX_RETRIES,
    API_RETRY_DELAY,
    API_TIMEOUT,
    DEFAULT_LEVERAGE,
    INITIAL_BALANCE,
    PAPERINVEST_API_KEY,
    PAPERINVEST_API_SECRET,
    PAPERINVEST_BASE_URL,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Local simulation store (used when no API key is set)
# ---------------------------------------------------------------------------
_SIM_ACCOUNT: dict[str, Any] = {
    "balance": INITIAL_BALANCE,
    "equity": INITIAL_BALANCE,
    "positions": {},   # symbol → position dict
    "orders": [],      # list of order dicts
}


def _sim_reset() -> None:
    """Reset the in-process simulation (useful for tests)."""
    _SIM_ACCOUNT["balance"] = INITIAL_BALANCE
    _SIM_ACCOUNT["equity"] = INITIAL_BALANCE
    _SIM_ACCOUNT["positions"] = {}
    _SIM_ACCOUNT["orders"] = []


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class PaperInvestClient:
    """REST client for the PaperInvest paper-trading API.

    When no API credentials are provided the client transparently falls back
    to a lightweight in-process simulation so that the paper trading module
    can be exercised without an internet connection.

    Args:
        api_key:    PaperInvest API key.  Defaults to ``PAPERINVEST_API_KEY``.
        api_secret: PaperInvest API secret.  Defaults to ``PAPERINVEST_API_SECRET``.
        base_url:   API base URL.  Defaults to ``PAPERINVEST_BASE_URL``.
    """

    def __init__(
        self,
        api_key: str = PAPERINVEST_API_KEY,
        api_secret: str = PAPERINVEST_API_SECRET,
        base_url: str = PAPERINVEST_BASE_URL,
    ) -> None:
        self._key = api_key
        self._secret = api_secret
        self._base = base_url.rstrip("/")
        self._session = requests.Session()
        if self._key:
            self._session.headers.update(
                {
                    "X-API-Key": self._key,
                    "X-API-Secret": self._secret,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
        self._use_sim = not bool(self._key)
        if self._use_sim:
            logger.info(
                "PaperInvestClient: no API key configured – using local simulation."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def initialize_account(self) -> dict[str, Any]:
        """Initialise (or retrieve) the paper trading account.

        Returns:
            Account info dict with ``account_id``, ``balance``, and ``equity``.
        """
        if self._use_sim:
            return {
                "account_id": "sim-local",
                "balance": _SIM_ACCOUNT["balance"],
                "equity": _SIM_ACCOUNT["equity"],
                "currency": "USDT",
            }
        return self._request("GET", "/account/initialize")

    def get_balance(self) -> dict[str, float]:
        """Return available balance and equity.

        Returns:
            Dict with ``balance`` and ``equity`` keys.
        """
        if self._use_sim:
            # Recompute equity from open positions' unrealised PnL
            equity = _SIM_ACCOUNT["balance"]
            for pos in _SIM_ACCOUNT["positions"].values():
                equity += pos.get("unrealized_pnl", 0.0)
            _SIM_ACCOUNT["equity"] = equity
            return {
                "balance": _SIM_ACCOUNT["balance"],
                "equity": equity,
            }
        data = self._request("GET", "/account/balance")
        return {
            "balance": float(data.get("available_balance", 0)),
            "equity": float(data.get("equity", 0)),
        }

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        leverage: int = DEFAULT_LEVERAGE,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict[str, Any]:
        """Place a paper trade order.

        Args:
            symbol:       Trading pair, e.g. ``"BTC/USDT"``.
            side:         ``"BUY"`` or ``"SELL"``.
            quantity:     Position size in base currency units.
            entry_price:  Entry price used for simulation.
            leverage:     Futures leverage multiplier.
            stop_loss:    Optional stop-loss price.
            take_profit:  Optional take-profit price.

        Returns:
            Order confirmation dict.
        """
        payload: dict[str, Any] = {
            "symbol": symbol,
            "side": side.upper(),
            "quantity": round(quantity, 6),
            "entry_price": entry_price,
            "leverage": leverage,
        }
        if stop_loss is not None:
            payload["stop_loss"] = stop_loss
        if take_profit is not None:
            payload["take_profit"] = take_profit

        if self._use_sim:
            return self._sim_place_order(payload)

        return self._request("POST", "/orders", json=payload)

    def close_position(self, symbol: str, exit_price: float | None = None) -> dict[str, Any]:
        """Close an open position for *symbol*.

        Args:
            symbol:     Trading pair to close.
            exit_price: Price used for PnL calculation (simulation only).

        Returns:
            Close confirmation dict.
        """
        if self._use_sim:
            return self._sim_close_position(symbol, exit_price)
        return self._request("POST", "/positions/close", json={"symbol": symbol})

    def get_open_positions(self) -> list[dict[str, Any]]:
        """Return a list of currently open positions.

        Returns:
            List of position dicts.
        """
        if self._use_sim:
            return list(_SIM_ACCOUNT["positions"].values())
        return self._request("GET", "/positions")  # type: ignore[return-value]

    def get_trade_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent closed trade history.

        Args:
            limit: Maximum number of trades to return.

        Returns:
            List of trade dicts.
        """
        if self._use_sim:
            closed = [o for o in _SIM_ACCOUNT["orders"] if o.get("status") == "CLOSED"]
            return closed[-limit:]
        return self._request("GET", f"/trades?limit={limit}")  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make a REST request with automatic retry logic.

        Args:
            method: HTTP verb (``"GET"``, ``"POST"``, …).
            path:   API path, e.g. ``"/account/balance"``.
            **kwargs: Passed through to :meth:`requests.Session.request`.

        Returns:
            Parsed JSON response.

        Raises:
            requests.HTTPError: When the server returns a non-2xx response
                after all retries are exhausted.
        """
        url = f"{self._base}{path}"
        last_exc: Exception | None = None
        for attempt in range(1, API_MAX_RETRIES + 1):
            try:
                resp = self._session.request(
                    method, url, timeout=API_TIMEOUT, **kwargs
                )
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.Timeout as exc:
                last_exc = exc
                logger.warning(
                    "PaperInvest API timeout (attempt %d/%d): %s",
                    attempt, API_MAX_RETRIES, url,
                )
            except requests.exceptions.HTTPError as exc:
                last_exc = exc
                logger.error(
                    "PaperInvest API HTTP error (attempt %d/%d): %s – %s",
                    attempt, API_MAX_RETRIES, exc.response.status_code, url,
                )
                # Do not retry client errors (4xx)
                if exc.response.status_code < 500:
                    break
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                logger.warning(
                    "PaperInvest API request error (attempt %d/%d): %s",
                    attempt, API_MAX_RETRIES, exc,
                )

            if attempt < API_MAX_RETRIES:
                time.sleep(API_RETRY_DELAY * attempt)

        raise requests.HTTPError(
            f"PaperInvest API failed after {API_MAX_RETRIES} retries: {url}"
        ) from last_exc

    # ------------------------------------------------------------------
    # Simulation helpers (no network required)
    # ------------------------------------------------------------------

    def _sim_place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Simulate placing an order locally."""
        symbol = payload["symbol"]
        side = payload["side"]
        qty = payload["quantity"]
        price = payload["entry_price"]
        leverage = payload.get("leverage", DEFAULT_LEVERAGE)

        margin_required = (qty * price) / leverage

        order: dict[str, Any] = {
            "order_id": str(uuid.uuid4())[:8],
            "symbol": symbol,
            "side": side,
            "quantity": qty,
            "entry_price": price,
            "leverage": leverage,
            "stop_loss": payload.get("stop_loss"),
            "take_profit": payload.get("take_profit"),
            "margin_used": margin_required,
            "status": "OPEN",
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "unrealized_pnl": 0.0,
        }

        # Deduct margin from available balance
        _SIM_ACCOUNT["balance"] = max(0.0, _SIM_ACCOUNT["balance"] - margin_required)

        # Track position (one per symbol, simplified)
        _SIM_ACCOUNT["positions"][symbol] = order
        _SIM_ACCOUNT["orders"].append(order)

        logger.info(
            "SIM ORDER: %s %s %s qty=%.4f @ %.4f (leverage x%d)",
            order["order_id"], side, symbol, qty, price, leverage,
        )
        return order

    def _sim_close_position(self, symbol: str, exit_price: float | None) -> dict[str, Any]:
        """Simulate closing an open position."""
        pos = _SIM_ACCOUNT["positions"].get(symbol)
        if not pos:
            logger.warning("SIM CLOSE: no open position for %s", symbol)
            return {"status": "NOT_FOUND", "symbol": symbol}

        entry = pos["entry_price"]
        qty = pos["quantity"]
        side = pos["side"]
        leverage = pos["leverage"]

        if exit_price is None:
            exit_price = entry  # flat exit for testing

        if side == "BUY":
            pnl = (exit_price - entry) * qty * leverage
        else:
            pnl = (entry - exit_price) * qty * leverage

        # Restore margin + PnL
        _SIM_ACCOUNT["balance"] += pos["margin_used"] + pnl

        result: dict[str, Any] = {
            "order_id": pos["order_id"],
            "symbol": symbol,
            "side": side,
            "entry_price": entry,
            "exit_price": exit_price,
            "quantity": qty,
            "leverage": leverage,
            "pnl": round(pnl, 4),
            "status": "CLOSED",
            "closed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Update order record
        pos.update(result)
        del _SIM_ACCOUNT["positions"][symbol]

        logger.info(
            "SIM CLOSE: %s %s PnL=%.4f USDT (balance=%.2f)",
            symbol, pos["order_id"], pnl, _SIM_ACCOUNT["balance"],
        )
        return result
