import os

from kili.client import Kili
import requests
from bs4 import BeautifulSoup

from ssrn_abstract import SsrnAbstract


class SsrnStrategy:
    def __init__(self, abstract: SsrnAbstract):
        self.abstract = abstract
        self.trading_rules = ""
        self.backtrader = ""
        self.markets_traded = ""
        self.period_of_rebalancing = ""
        self.backtest_period = ""
        self.annual_return = ""
        self.maximum_drawdown = ""
        self.sharpe_ratio = ""
        self.annual_standard_deviation = ""

    def to_markdown(self):
        return f"""# {self.abstract.title}

A python [Backtrader](https://www.backtrader.com/) implementation of the algorithmic trading strategy described in the following paper.

# Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id={self.abstract.abstract_id})

# Trading rules

{self.trading_rules}

# Statistics

- **Markets Traded:** {self.markets_traded}
- **Period of Rebalancing:** {self.period_of_rebalancing}
- **Backtest period:** {self.backtest_period}
- **Annual Return:** {self.annual_return}
- **Maximum Drawdown:** {self.maximum_drawdown}
- **Sharpe Ratio:** {self.sharpe_ratio}
- **Annual Standard Deviation:** {self.annual_standard_deviation}

# Python code

## Backtrader

```python
{self.backtrader}
```"""
