"""
Initialize Online Portfolio Selection Module.
"""
# Parent Class
from systematic_trading.online_portfolio_selection.base import OLPS
from systematic_trading.online_portfolio_selection.up import UP

# Benchmarks
from systematic_trading.online_portfolio_selection.bah import BAH
from systematic_trading.online_portfolio_selection.best_stock import BestStock
from systematic_trading.online_portfolio_selection.crp import CRP
from systematic_trading.online_portfolio_selection.bcrp import BCRP

# Momentum
from systematic_trading.online_portfolio_selection.eg import EG
from systematic_trading.online_portfolio_selection.ftl import FTL
from systematic_trading.online_portfolio_selection.ftrl import FTRL

# Mean Reversion
from systematic_trading.online_portfolio_selection.rmr import RMR
from systematic_trading.online_portfolio_selection.pamr import PAMR
from systematic_trading.online_portfolio_selection.cwmr import CWMR
from systematic_trading.online_portfolio_selection.olmar import OLMAR

# Pattern Matching
from systematic_trading.online_portfolio_selection.corn import CORN
from systematic_trading.online_portfolio_selection.cornu import CORNU
from systematic_trading.online_portfolio_selection.cornk import CORNK
from systematic_trading.online_portfolio_selection.scorn import SCORN
from systematic_trading.online_portfolio_selection.scornk import SCORNK
from systematic_trading.online_portfolio_selection.fcorn import FCORN
from systematic_trading.online_portfolio_selection.fcornk import FCORNK
