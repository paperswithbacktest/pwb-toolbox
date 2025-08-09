"""Utility functions to interact with Interactive Brokers via ``ib_insync``.

This module centralizes all logic that is specific to the Interactive Brokers
API so that scripts such as ``run_live.py`` can focus on computing target
positions.  The implementation is a thin wrapper around the :mod:`ib_insync`
package which provides convenient synchronous access to IB.

Example
-------
    >>> from pwb_toolbox.execution import create_connector
    >>> ibc = create_connector({"broker": "ib"})
    >>> ibc.connect()
    >>> nav = ibc.get_account_nav()
    >>> positions = ibc.get_positions()
    >>> ibc.disconnect()

The :class:`IBConnector` class exposes methods for obtaining account
information, retrieving current positions and submitting orders.  The order
placement logic mirrors the one previously implemented in ``run_live.py`` and
supports both market and limit orders.  For limit orders a snapshot quote is
requested and the last trade price (or closing price as a fallback) is used as
the limit price.  If no price is available the order is converted into a market
order.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import time
from typing import Dict, List, Optional

import pandas as pd
from ib_insync import IB, LimitOrder, MarketOrder, Stock

from .optimal_limit_order import get_optimal_quote


@dataclass
class TradeRecord:
    """Container for information about a single trade."""

    timestamp: str
    ib_timestamp: Optional[str]
    symbol: str
    action: str
    quantity: int
    price: Optional[float]
    order_id: int
    status: str
    filled: float
    avg_fill_price: float
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


class IBConnector:
    """Small wrapper around :class:`ib_insync.IB`.

    Parameters
    ----------
    host, port, client_id : optional
        Connection parameters passed to :meth:`ib_insync.IB.connect`.
    market_data_type : int, optional
        Market data type requested through :meth:`ib_insync.IB.reqMarketDataType`.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        market_data_type: int = 4,
    ) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self.market_data_type = market_data_type
        self.ib = IB()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self) -> None:
        """Connect to the IB gateway and set the market data type."""

        self.ib.connect(self.host, self.port, clientId=self.client_id)
        self.ib.reqMarketDataType(self.market_data_type)

    def disconnect(self) -> None:
        """Disconnect from IB."""

        self.ib.disconnect()

    # ------------------------------------------------------------------
    # Account information helpers
    # ------------------------------------------------------------------
    def get_account_nav(self) -> float:
        """Return the net liquidation value of the account."""

        account_nav_value = 0.0
        for item in self.ib.accountSummary():
            if item.tag == "NetLiquidation":
                account_nav_value = float(item.value)
                break
        return account_nav_value

    def get_positions(self) -> Dict[str, float]:
        """Return current IB positions keyed by symbol."""

        return {p.contract.symbol: p.position for p in self.ib.positions()}

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------
    def _ensure_connection(self) -> None:
        """Ensure that the IB client is connected.

        Attempts to reconnect using the stored parameters when disconnected.
        Raises ``ConnectionError`` if reconnection fails.
        """

        if not self.ib.isConnected():
            try:
                self.connect()
            except Exception as exc:  # pragma: no cover - network failure
                raise ConnectionError("Unable to reconnect to IB") from exc

    def _place_order_with_reconnect(self, contract, order):
        """Place an order, reconnecting once on ``ConnectionError``."""

        self._ensure_connection()
        try:
            return self.ib.placeOrder(contract, order)
        except ConnectionError as exc:
            logging.warning("Connection error while placing order: %s", exc)
            self._ensure_connection()
            return self.ib.placeOrder(contract, order)

    def place_orders(
        self, orders: Dict[str, float], order_type: str = "LMT"
    ) -> List[TradeRecord]:
        """Place a collection of orders.

        Parameters
        ----------
        orders : dict
            Mapping of symbol to desired signed quantity.  Positive quantities
            represent buy orders and negative quantities sell orders.
        order_type : {"LMT", "MKT"}
            Preferred order type.  When ``"LMT"`` is requested a snapshot quote
            is fetched and used as the limit price; if unavailable the order is
            downgraded to a market order.

        Returns
        -------
        list of :class:`TradeRecord`
            Trade information for each successfully submitted order.
        """

        trade_records: List[TradeRecord] = []
        for symbol, qty in orders.items():
            contract = Stock(symbol, "SMART", "USD")
            self.ib.qualifyContracts(contract)

            action = "BUY" if qty > 0 else "SELL"
            quantity = abs(int(qty))
            if quantity == 0:
                continue

            price: Optional[float] = None
            if order_type.upper() == "MKT":
                order = MarketOrder(action, quantity)
            else:
                try:
                    ticker = self.ib.reqMktData(contract, "", snapshot=True)
                    self.ib.sleep(1)
                    price = ticker.last if pd.notna(ticker.last) else ticker.close
                    if price is None or pd.isna(price):
                        order = MarketOrder(action, quantity)
                    else:
                        order = LimitOrder(action, quantity, price)
                except Exception as exc:  # pragma: no cover - network failure
                    logging.error("Error fetching market data for %s: %s", symbol, exc)
                    order = MarketOrder(action, quantity)

            trade = self._place_order_with_reconnect(contract, order)
            self.ib.sleep(1)
            ib_timestamp = trade.log[-1].time.isoformat() if trade.log else None

            trade_records.append(
                TradeRecord(
                    timestamp=pd.Timestamp.utcnow().isoformat(),
                    ib_timestamp=ib_timestamp,
                    symbol=symbol,
                    action=action,
                    quantity=quantity,
                    price=price,
                    order_id=trade.order.orderId,
                    status=trade.orderStatus.status,
                    filled=trade.orderStatus.filled,
                    avg_fill_price=trade.orderStatus.avgFillPrice,
                    entry=None,
                    exit=None,
                    ret=None,
                    direction="long" if action == "BUY" else "short",
                    order_type=order.orderType,
                )
            )
        return trade_records

    def execute_orders(
        self,
        orders: Dict[str, float],
        time_in_seconds: int,
        time_step: int = 60,
    ) -> List[TradeRecord]:
        """Execute ``orders`` using the optimal limit order strategy.

        The execution algorithm follows the strategy implemented in
        :func:`optimal_limit_order.get_optimal_quote`.  For each symbol a
        sequence of limit orders is submitted.  Orders are refreshed every
        ``time_step`` seconds with the remaining quantity and the time left to
        trade.  Any residual quantity after ``time_in_seconds`` is sent as a
        market order.

        Parameters
        ----------
        orders
            Mapping of symbol to desired signed quantity.  Positive quantities
            represent buy orders and negative quantities sell orders.
        time_in_seconds
            Maximum time allowed to execute the orders.
        time_step
            Refresh interval for the limit orders in seconds.

        Returns
        -------
        list of :class:`TradeRecord`
            Trade information for each submitted order (including refreshes and
            the final market order if necessary).
        """

        trade_records: List[TradeRecord] = []
        start_time = time.time()
        deadline = start_time + time_in_seconds

        # Prepare contracts and remaining quantities for all symbols
        order_info: Dict[str, Dict[str, object]] = {}
        for symbol, qty in orders.items():
            remaining_qty = abs(int(qty))
            if remaining_qty <= 0:
                continue
            contract = Stock(symbol, "SMART", "USD")
            self.ib.qualifyContracts(contract)
            action = "BUY" if qty > 0 else "SELL"
            order_info[symbol] = {
                "contract": contract,
                "action": action,
                "remaining_qty": remaining_qty,
            }

        while time.time() < deadline and any(
            info["remaining_qty"] > 0 for info in order_info.values()
        ):
            placed_orders: Dict[str, tuple] = {}
            for symbol, info in order_info.items():
                remaining_qty = int(info["remaining_qty"])
                if remaining_qty <= 0:
                    continue

                contract = info["contract"]
                action = str(info["action"])
                remaining_time = max(int(deadline - time.time()), 0)

                # Obtain a snapshot to compute the mid price
                try:
                    ticker = self.ib.reqMktData(contract, "", snapshot=True)
                    self.ib.sleep(1)
                    mid_price = None
                    if (
                        ticker.bid is not None
                        and ticker.ask is not None
                        and pd.notna(ticker.bid)
                        and pd.notna(ticker.ask)
                    ):
                        mid_price = (ticker.bid + ticker.ask) / 2
                    if mid_price is None or pd.isna(mid_price):
                        mid_price = (
                            ticker.last if pd.notna(ticker.last) else ticker.close
                        )
                except Exception:  # pragma: no cover - network failure
                    mid_price = None

                if mid_price is None or pd.isna(mid_price):
                    order = MarketOrder(action, remaining_qty)
                    price: Optional[float] = None
                else:
                    quote = get_optimal_quote(
                        symbol=symbol,
                        quantity=remaining_qty,
                        time_in_seconds=remaining_time,
                    )
                    price = (
                        mid_price - quote if action == "BUY" else mid_price + quote
                    )
                    if not (math.isfinite(quote) and math.isfinite(price)):
                        order = MarketOrder(action, remaining_qty)
                        price = None
                    else:
                        order = LimitOrder(action, remaining_qty, price)

                trade = self._place_order_with_reconnect(contract, order)
                placed_orders[symbol] = (trade, price, order)

            # Allow orders to work for the specified time step
            self.ib.sleep(time_step)

            for symbol, (trade, price, order) in placed_orders.items():
                info = order_info[symbol]
                action = str(info["action"])
                filled = int(trade.orderStatus.filled)
                info["remaining_qty"] = max(int(info["remaining_qty"]) - filled, 0)
                ib_timestamp = trade.log[-1].time.isoformat() if trade.log else None

                trade_records.append(
                    TradeRecord(
                        timestamp=pd.Timestamp.utcnow().isoformat(),
                        ib_timestamp=ib_timestamp,
                        symbol=symbol,
                        action=action,
                        quantity=filled if filled else int(info["remaining_qty"]),
                        price=price,
                        order_id=trade.order.orderId,
                        status=trade.orderStatus.status,
                        filled=trade.orderStatus.filled,
                        avg_fill_price=trade.orderStatus.avgFillPrice,
                        entry=None,
                        exit=None,
                        ret=None,
                        direction="long" if action == "BUY" else "short",
                        order_type=order.orderType,
                    )
                )

                if info["remaining_qty"] > 0 and trade.orderStatus.status not in {
                    "Filled",
                    "Cancelled",
                }:
                    try:
                        self.ib.cancelOrder(order)
                    except Exception:  # pragma: no cover - network failure
                        pass

        # Send market orders for any remaining quantities
        for symbol, info in order_info.items():
            remaining_qty = int(info["remaining_qty"])
            if remaining_qty <= 0:
                continue
            contract = info["contract"]
            action = str(info["action"])
            order = MarketOrder(action, remaining_qty)
            trade = self._place_order_with_reconnect(contract, order)
            self.ib.sleep(1)
            ib_timestamp = trade.log[-1].time.isoformat() if trade.log else None
            trade_records.append(
                TradeRecord(
                    timestamp=pd.Timestamp.utcnow().isoformat(),
                    ib_timestamp=ib_timestamp,
                    symbol=symbol,
                    action=action,
                    quantity=remaining_qty,
                    price=None,
                    order_id=trade.order.orderId,
                    status=trade.orderStatus.status,
                    filled=trade.orderStatus.filled,
                    avg_fill_price=trade.orderStatus.avgFillPrice,
                    entry=None,
                    exit=None,
                    ret=None,
                    direction="long" if action == "BUY" else "short",
                    order_type=order.orderType,
                )
            )

        return trade_records

