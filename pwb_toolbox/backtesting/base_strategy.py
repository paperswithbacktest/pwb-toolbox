from tqdm import tqdm

from ..engine import load as _load_engine

bt = _load_engine()  # backtrader by default, Tradewind on request; see pwb_toolbox.engine


class BaseStrategy(bt.Strategy):
    """Base strategy providing progress logging utilities."""

    params = (("total_days", 0),)

    def __init__(self):
        super().__init__()
        self.pbar = tqdm(total=self.params.total_days)
        self.log_data = []

    def is_tradable(self, data):
        """Return True if the instrument's price is not constant."""
        if len(data.close) < 3:
            return False
        return data.close[0] != data.close[-2]

    def next(self):
        """Update progress bar and log current value."""
        self.pbar.update(1)
        self.log_data.append(
            {
                "date": self.datas[0].datetime.date(0).isoformat(),
                "value": self.broker.getvalue(),
            }
        )

    def get_latest_positions(self):
        """Get a dictionary of the latest positions."""
        return {data._name: self.broker.getposition(data).size for data in self.datas}
