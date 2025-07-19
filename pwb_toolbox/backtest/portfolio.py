from .base_strategy import BaseStrategy


class MonthlyEqualWeightPortfolio(BaseStrategy):
    params = (
        ("leverage", 0.9),
        ("signal_cls", None),
        ("signal_kwargs", {}),
    )

    def __init__(self):
        super().__init__()
        self.sig = {
            d._name: self.p.signal_cls(d, **self.p.signal_kwargs) for d in self.datas
        }
        self.last_month = -1

    def next(self):
        """Rebalance portfolio at the start of each month."""
        super().next()
        today = self.datas[0].datetime.date(0)
        if today.month == self.last_month:
            return
        self.last_month = today.month
        longs = [
            d for d in self.datas if self.is_tradable(d) and self.sig[d._name][0] == 1
        ]
        wt = (self.p.leverage / len(longs)) if longs else 0.0
        for d in self.datas:
            self.order_target_percent(d, target=wt if d in longs else 0)
