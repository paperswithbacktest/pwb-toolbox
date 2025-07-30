"""Lightweight helpers for running Interactive Brokers backtests."""

from __future__ import annotations

from typing import Iterable, Mapping, Type

import backtrader as bt


class IBConnector:
    """Utility for creating Backtrader IB stores and data feeds."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        store_class: Type[bt.stores.IBStore] | None = None,
        feed_class: Type[bt.feeds.IBData] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self.store_class = store_class or bt.stores.IBStore
        self.feed_class = feed_class or bt.feeds.IBData

    def get_store(self) -> bt.stores.IBStore:
        """Instantiate and return an ``IBStore``."""
        return self.store_class(host=self.host, port=self.port, clientId=self.client_id)

    def create_feed(self, **kwargs) -> bt.feeds.IBData:
        """Create an ``IBData`` feed bound to the connector's store."""
        store = kwargs.pop("store", None) or self.get_store()
        return self.feed_class(store=store, **kwargs)


def run_ib_strategy(
    strategy: type[bt.Strategy],
    data_config: Iterable[Mapping[str, object]],
    **ib_kwargs,
):
    """Run ``strategy`` with Interactive Brokers data feeds.

    Parameters
    ----------
    strategy:
        The ``bt.Strategy`` subclass to execute.
    data_config:
        Iterable of dictionaries passed to ``IBData`` for each feed.
    ib_kwargs:
        Arguments forwarded to :class:`IBConnector`.
    Examples
    --------
    >>> data_cfg = [{"dataname": "AAPL", "name": "AAPL", "what": "MIDPOINT"}]
    >>> run_ib_strategy(MyStrategy, data_cfg, host="127.0.0.1")

    """
    connector = IBConnector(**ib_kwargs)
    cerebro = bt.Cerebro()
    store = connector.get_store()
    cerebro.broker = store.getbroker()

    for cfg in data_config:
        data = connector.create_feed(store=store, **cfg)
        name = cfg.get("name")
        cerebro.adddata(data, name=name)

    cerebro.addstrategy(strategy)
    return cerebro.run()
