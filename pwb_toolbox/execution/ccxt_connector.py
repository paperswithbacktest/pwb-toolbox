"""Utility functions to interact with cryptocurrency exchanges via ``ccxt``.

This module mirrors the interface exposed by :class:`IBConnector` but uses
`ccxt`_ to communicate with crypto exchanges.  Only a small subset of
functionality is implemented which is sufficient for placing basic market or
limit orders and retrieving account information.

Example
-------
    >>> from pwb_toolbox.execution import create_connector
    >>> cc = create_connector({"broker": "ccxt", "exchange": "binance", "api_key": "...", "api_secret": "..."})
    >>> cc.connect()
    >>> nav = cc.get_account_nav()
    >>> positions = cc.get_positions()
    >>> cc.place_orders({"BTC/USDT": 0.01})
    >>> cc.disconnect()

The connector provides ``connect``/``disconnect`` helpers, account information
methods and simple order placement utilities.  Orders are submitted using
:func:`ccxt.Exchange.create_order` while price snapshots are obtained via
:func:`ccxt.Exchange.fetch_ticker`.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Dict, List, Optional

import pandas as pd
import ccxt


@dataclass
class TradeRecord:
    """Container for information about a single trade.

    The structure mirrors the ``TradeRecord`` used by :class:`IBConnector` so
    that calling code can operate on both connectors interchangeably.
    """

    timestamp: str
    ib_timestamp: Optional[str]
    symbol: str
    action: str
    quantity: float
    price: Optional[float]
    order_id: str
    status: str
    filled: float
    avg_fill_price: Optional[float]
    entry: Optional[float]
    exit: Optional[float]
    ret: Optional[float]
    direction: str
    order_type: str

    def as_dict(self) -> Dict[str, Optional[float]]:
        """Return the record as a plain dictionary."""

        return {
            "timestamp": self.timestamp,
            "ib_timestamp": self.ib_timestamp,
            "symbol": self.symbol,
            "action": self.action,
            "quantity": self.quantity,
            "price": self.price,
            "order_id": self.order_id,
            "status": self.status,
            "filled": self.filled,
            "avg_fill_price": self.avg_fill_price,
            "entry": self.entry,
            "exit": self.exit,
            "return": self.ret,
            "direction": self.direction,
            "order_type": self.order_type,
        }


class CCXTConnector:
    """Minimal wrapper around :mod:`ccxt` exchanges.

    Parameters
    ----------
    exchange : str
        Name of the exchange as expected by ``ccxt`` (e.g. ``"binance"``).
    api_key, api_secret : str, optional
        Credentials used to authenticate with the exchange.
    params : dict, optional
        Additional parameters passed to the exchange constructor.
    """

    def __init__(
        self,
        exchange: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        params: Optional[Dict[str, object]] = None,
    ) -> None:
        self.exchange_name = exchange
        self.api_key = api_key
        self.api_secret = api_secret
        self.params = params or {}
        self.exchange: Optional[ccxt.Exchange] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self) -> None:
        """Instantiate the ``ccxt`` exchange using the provided credentials."""

        exchange_class = getattr(ccxt, self.exchange_name)
        config = {"apiKey": self.api_key, "secret": self.api_secret}
        config.update(self.params)
        self.exchange = exchange_class(config)

    def disconnect(self) -> None:
        """Clear the exchange instance."""

        if self.exchange is not None:
            # Some exchanges implement ``close`` for websockets; ignore errors
            close = getattr(self.exchange, "close", None)
            if callable(close):
                try:  # pragma: no cover - network failure
                    close()
                except Exception:
                    pass
        self.exchange = None

    # ------------------------------------------------------------------
    # Account information helpers
    # ------------------------------------------------------------------
    def _ensure_connection(self) -> ccxt.Exchange:
        if self.exchange is None:
            raise ConnectionError("Exchange not connected")
        return self.exchange

    def get_account_nav(self) -> float:
        """Return the total account value from ``fetch_balance``.

        The return value is the sum of the ``total`` balances across all
        currencies.  It is only a rough approximation of the real NAV but is
        sufficient for simple monitoring purposes.
        """

        ex = self._ensure_connection()
        balance = ex.fetch_balance()
        totals = balance.get("total", {})
        if isinstance(totals, dict):
            return float(
                sum(v for v in totals.values() if isinstance(v, (int, float)))
            )
        try:
            return float(totals)
        except (TypeError, ValueError):
            return 0.0

    def get_positions(self) -> Dict[str, float]:
        """Return current positions keyed by symbol."""

        ex = self._ensure_connection()
        positions: Dict[str, float] = {}
        try:
            raw_positions = ex.fetch_positions()
        except Exception as exc:  # pragma: no cover - network failure
            logging.error("Error fetching positions: %s", exc)
            return positions

        for pos in raw_positions:
            symbol = pos.get("symbol")
            size = (
                pos.get("contracts")
                or pos.get("positionAmt")
                or pos.get("size")
                or pos.get("contractSize")
            )
            if symbol and size is not None:
                try:
                    positions[symbol] = float(size)
                except (TypeError, ValueError):
                    continue
        return positions

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------
    def place_orders(
        self, orders: Dict[str, float], order_type: str = "LMT"
    ) -> List[TradeRecord]:
        """Place a collection of orders using ``create_order``.

        Parameters
        ----------
        orders : dict
            Mapping of symbol to desired signed quantity.  Positive quantities
            represent buy orders and negative quantities sell orders.
        order_type : {"LMT", "MKT"}
            Preferred order type.  When ``"LMT"`` is requested a snapshot quote
            is fetched and used as the limit price; if unavailable the order is
            downgraded to a market order.
        """

        ex = self._ensure_connection()
        trade_records: List[TradeRecord] = []
        for symbol, qty in orders.items():
            side = "buy" if qty > 0 else "sell"
            amount = abs(qty)
            if amount == 0:
                continue

            price: Optional[float] = None
            ccxt_order_type = "limit"
            if order_type.upper() == "MKT":
                ccxt_order_type = "market"
            else:
                try:
                    ticker = ex.fetch_ticker(symbol)
                    price = ticker.get("last") or ticker.get("close")
                    if price is None:
                        ccxt_order_type = "market"
                except Exception as exc:  # pragma: no cover - network failure
                    logging.error("Error fetching ticker for %s: %s", symbol, exc)
                    ccxt_order_type = "market"

            if ccxt_order_type == "market":
                order = ex.create_order(symbol, ccxt_order_type, side, amount)
            else:
                order = ex.create_order(symbol, ccxt_order_type, side, amount, price)

            trade_records.append(
                TradeRecord(
                    timestamp=pd.Timestamp.utcnow().isoformat(),
                    ib_timestamp=order.get("datetime"),
                    symbol=symbol,
                    action=side.upper(),
                    quantity=amount,
                    price=price if ccxt_order_type == "limit" else None,
                    order_id=str(order.get("id")),
                    status=order.get("status", ""),
                    filled=float(order.get("filled", 0) or 0),
                    avg_fill_price=order.get("average"),
                    entry=None,
                    exit=None,
                    ret=None,
                    direction="long" if side == "buy" else "short",
                    order_type="LMT" if ccxt_order_type == "limit" else "MKT",
                )
            )
        return trade_records

    def execute_orders(
        self,
        orders: Dict[str, float],
        time_in_seconds: int,
        time_step: int = 60,
    ) -> List[TradeRecord]:
        """Execute ``orders``; currently a thin wrapper over :meth:`place_orders`.

        The ``time_in_seconds`` and ``time_step`` parameters are accepted for
        API compatibility with :class:`IBConnector` but are not used in the
        current implementation.
        """

        return self.place_orders(orders, order_type="LMT")
