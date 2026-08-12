# Graph Report - .  (2026-08-08)

## Corpus Check
- Corpus is ~46,183 words - fits in a single context window. You may not need a graph.

## Summary
- 826 nodes · 1330 edges · 64 communities (54 shown, 10 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 104 edges (avg confidence: 0.77)
- Token cost: 91,445 input · 0 output

## Community Hubs (Navigation)
- SSRN Strategy Idea Mining
- Legacy Analysis Data Fetchers
- NAV Performance Metrics
- CCXT Crypto Connector
- Metrics and Plots Rationale
- Trade Statistics and Plots
- Backtesting Strategy Docs
- IB Connector Core
- Performance Plotting
- Base Strategy Abstraction
- Legacy Knowledge Datasets
- IB Connector Calibration Tests
- Legacy Feature Predictors
- Legacy News Datasets
- Dataset Docs and Examples
- Dataset Loading and Conversion
- Legacy Earnings Datasets
- Legacy Feature Targets
- Legacy Momentum Strategy
- Backtest Engine
- Portfolio and Universe
- Legacy Dataset Init
- SP500 Perimeter Definitions
- Long-Short Quantile Portfolios
- Optimal Limit Order Tests
- SSRN Abstract Idea Pipeline
- IB Server Launch Scripts
- Backtest Result Chart
- Execution NAV Flow Docs
- Commission Modeling
- Stock Perimeter Definitions
- Legacy Earnings Estimates
- Legacy Extended Datasets
- Legacy Raw Dataset Init
- Legacy Short Interest Data
- Legacy Timeseries Datasets
- Yahoo Timeseries Helpers
- Backtrader Optimization Docs
- Legacy Earnings Surprises
- Nasdaq Earnings Helpers
- README Reporting Examples
- IB Server Cron Environment
- Broker Factory
- Broker Connector Protocol Docs
- README Datasets and License
- Sigmoid Composite Indicators
- IB Trade Records
- Legacy Knowledge Timeseries
- Legacy Knowledge Graph Data
- Ulcer Index Metrics
- Dynamic Equal Weight Portfolio
- Monthly Ranked Equal Weight
- Weekly Long-Short Decile
- Legacy Momentum Models
- Project Banner Imagery
- Daily Equal Weight Portfolio
- Equal Weight Entry Exit
- Monthly Long-Short Portfolio
- IB Meta Strategy Execution
- IB Server Install Script
- IB Server Daily Run

## God Nodes (most connected - your core abstractions)
1. `_to_list()` - 34 edges
2. `SsrnAbstract` - 25 edges
3. `generate_monitoring_report()` - 20 edges
4. `BaseStrategy` - 19 edges
5. `IBConnector` - 18 edges
6. `load_dataset()` - 17 edges
7. `Raw` - 16 edges
8. `SsrnPaperSummarizer` - 15 edges
9. `load_dataset (datasets API)` - 15 edges
10. `Dataset` - 14 edges

## Surprising Connections (you probably didn't know these)
- `append_nav_history` --semantically_similar_to--> `NAV series (strategy.log_data)`  [INFERRED] [semantically similar]
  docs/execution.md → README.md
- `pwb conda environment (ib_server)` --semantically_similar_to--> `Runtime dependency set`  [INFERRED] [semantically similar]
  tools/ib_server/environment.yml → requirements.txt
- `SimpleMomentum (README example indicator)` --semantically_similar_to--> `DualMomentumSignal`  [INFERRED] [semantically similar]
  README.md → docs/backtesting.md
- `MonthlySwitcher (README example strategy)` --semantically_similar_to--> `MonthlyDualMomentumPortfolio`  [INFERRED] [semantically similar]
  README.md → docs/backtesting.md
- `main()` --calls--> `load_dataset()`  [INFERRED]
  pwb_toolbox_legacy/models/momentum.py → pwb_toolbox/datasets/__init__.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Live broker execution pipeline (NAV to orders to logs)** — docs_execution_ibconnector, docs_execution_append_nav_history, docs_execution_run_strategies, docs_execution_scale_positions, docs_execution_compute_orders, docs_execution_execute_and_log_orders, docs_execution_log_current_state [EXTRACTED 1.00]
- **pwb_toolbox.backtesting module decomposition** — docs_backtesting_backtest_engine, docs_backtesting_base_strategy_module, docs_backtesting_commission_module, docs_backtesting_indicators_module, docs_backtesting_optimization_engine, docs_backtesting_portfolio_module, docs_backtesting_strategies_module, docs_backtesting_universe_module [EXTRACTED 1.00]
- **Rebalancing-cadence portfolio template family** — docs_backtesting_dailyequalweightportfolio, docs_backtesting_dailyleverageportfolio, docs_backtesting_dynamicequalweightportfolio, docs_backtesting_monthlylongshortportfolio, docs_backtesting_monthlylongshortquantileportfolio, docs_backtesting_monthlyrankedequalweightportfolio, docs_backtesting_quarterlytopmomentumportfolio, docs_backtesting_rollingsemesterlongshortportfolio, docs_backtesting_weeklylongshortdecileportfolio, docs_backtesting_weightedallocationportfolio, docs_backtesting_equalweightentryexitportfolio [INFERRED 0.85]
- **Risk/Return Metric Set Reported for the Backtest** — static_images_backtest_result_sharpe_ratio, static_images_backtest_result_annual_return, static_images_backtest_result_annual_volatility, static_images_backtest_result_maximum_drawdown, static_images_backtest_result_backtest_period [EXTRACTED 1.00]
- **Showcase Composition: Curve Above, Metrics Below** — static_images_backtest_result_figure, static_images_backtest_result_net_worth_equity_curve, static_images_backtest_result_performance_metrics_table, static_images_backtest_result_low_volatility_strategy_profile [INFERRED 0.85]
- **Market-Terminal Imagery Composing the Project Banner** — static_images_pwb_toolbox_banner, static_images_pwb_toolbox_market_data_display, static_images_pwb_toolbox_price_time_series, static_images_pwb_toolbox_quote_ticker_grid [INFERRED 0.85]

## Communities (64 total, 10 thin omitted)

### Community 0 - "SSRN Strategy Idea Mining"
Cohesion: 0.06
Nodes (16): main(), command, option, Main entrypoint of strategy_ideas., main(), command, option, Predicts the category of a text. (+8 more)

### Community 1 - "Legacy Analysis Data Fetchers"
Cohesion: 0.05
Nodes (22): EarningsEstimate, date, Earnings estimate from Yahoo Finance., Earnings estimate from Yahoo Finance., Convert the frames to a dataset., EPSRevisions, date, EPS Revisions from Yahoo Finance. (+14 more)

### Community 2 - "NAV Performance Metrics"
Cohesion: 0.08
Nodes (41): annualized_volatility(), cagr(), calmar_ratio(), capm_alpha_beta(), kurtosis(), max_drawdown(), Maximum drawdown depth and duration., Return total return of a price series. (+33 more)

### Community 3 - "CCXT Crypto Connector"
Cohesion: 0.07
Nodes (29): Exchange, CCXTConnector, Utility functions to interact with cryptocurrency exchanges via ``ccxt``. This…, Instantiate the ``ccxt`` exchange using the provided credentials., Clear the exchange instance., Return the total account value from ``fetch_balance``. The return value is the…, Return current positions keyed by symbol., Place a collection of orders using ``create_order``. Parameters ----------… (+21 more)

### Community 4 - "Metrics and Plots Rationale"
Cohesion: 0.07
Nodes (38): acf(), fama_french_5factor(), fama_french_regression(), information_ratio(), _invert_matrix(), _ols(), omega_ratio(), pacf() (+30 more)

### Community 5 - "Trade Statistics and Plots"
Cohesion: 0.13
Nodes (33): plot_cumulative_shortfall(), plot_equity_curve(), plot_return_heatmap(), plot_underwater(), Plot cumulative return equity curve., Plot cumulative implementation shortfall over time., Plot calendar heatmap of returns from price series., Plot drawdown (underwater) chart. (+25 more)

### Community 6 - "Backtesting Strategy Docs"
Cohesion: 0.07
Nodes (32): backtest_engine module, base_strategy module, BaseStrategy, DualMomentumSignal.build_weights, commission module, MonthlyDualMomentumPortfolio._current_weights, DailyEqualWeightPortfolio, DailyLeveragePortfolio (+24 more)

### Community 7 - "IB Connector Core"
Cohesion: 0.11
Nodes (12): IBConnector, Small wrapper around :class:`ib_insync.IB`. Parameters ---------- host, port,…, Connect to the IB gateway and set the market data type., Return the net liquidation value of the account., Return current IB positions keyed by symbol., Ensure that the IB client is connected. Attempts to reconnect using the stored…, Place an order, reconnecting once on ``ConnectionError``., Return the contract's minimum price increment, or ``None`` if it can't be… (+4 more)

### Community 8 - "Performance Plotting"
Cohesion: 0.09
Nodes (23): cumulative_excess_return(), fama_french_3factor(), Cumulative excess return of strategy versus a benchmark., Skewness of returns of a price series., skewness(), plot_alpha_vs_return(), plot_cumulative_excess_return(), plot_exposure_ts() (+15 more)

### Community 9 - "Base Strategy Abstraction"
Cohesion: 0.11
Nodes (10): BaseStrategy, Return True if the instrument's price is not constant., Update progress bar and log current value., Get a dictionary of the latest positions., Base strategy providing progress logging utilities., DailyLeveragePortfolio, QuarterlyTopMomentumPortfolio, Generic: go `leverage` long whenever signal == 1, otherwise flat. (+2 more)

### Community 10 - "Legacy Knowledge Datasets"
Cohesion: 0.16
Nodes (8): date, Add wikipedia page to the DataFrame., Add relationships to the DataFrame., Add wikipedia title to the DataFrame., Stocks, curl -C - -O…, Returns the Wikipedia pages of companies that are traded., Wikipedia

### Community 11 - "IB Connector Calibration Tests"
Cohesion: 0.18
Nodes (14): fixture, Convert a series of daily closes into a per-instrument `sigma`. `sigma` is the…, _sigma_from_closes(), connector(), fake_contract(), _price_path(), Tests for the per-symbol limit-order calibration added to `IBConnector`.…, test_get_quote_calibration_combines_both() (+6 more)

### Community 12 - "Legacy Feature Predictors"
Cohesion: 0.15
Nodes (13): jit, barycentre_of_progressive_slopes(), bayesian_slope(), linear_regression_slope(), median_of_local_slopes(), median_of_progressive_slopes(), Slope of the linear regression: slope(close(1), ..., close(12)), Median of local slopes: median(close(12)-close(11), close(11)-close(10), ...,… (+5 more)

### Community 13 - "Legacy News Datasets"
Cohesion: 0.17
Nodes (7): Article, News, DataFrame, date, News from Yahoo Finance., News from Yahoo Finance., Get news for a given ticker.

### Community 14 - "Dataset Docs and Examples"
Cohesion: 0.15
Nodes (15): run_strategy (docs example entrypoint), adjust argument (price adjustment), Bonds-Daily-Price dataset, Commodities-Daily-Price dataset, Cryptocurrencies-Daily-Price dataset, ETFs-Daily-Price dataset, extend argument (history splicing), Forex-Daily-Price dataset (+7 more)

### Community 15 - "Dataset Loading and Conversion"
Cohesion: 0.29
Nodes (13): __convert_bond_rates_to_prices(), __convert_indices_to_usd(), __extend_etfs(), _get_pwb_api_key(), _list_hf_split_parquet_files(), load_dataset(), _load_dataset_from_hf(), _load_dataset_from_pwb() (+5 more)

### Community 16 - "Legacy Earnings Datasets"
Cohesion: 0.18
Nodes (8): Earnings, DataFrame, date, Earnings data from Yahoo Finance., Set the dataset dataframe., Earnings data from Yahoo Finance., Get earnings for a given ticker., Append a dataframe for a given symbol.

### Community 17 - "Legacy Feature Targets"
Cohesion: 0.14
Nodes (8): main(), command, option, main(), command, option, date, TargetsMonthly

### Community 18 - "Legacy Momentum Strategy"
Cohesion: 0.18
Nodes (6): CashNav, main(), MomentumStrategy, A momentum strategy that goes long the top quantile of stocks and short the…, Execute trades based on the momentum strategy., Analyzer returning cash and market values

### Community 19 - "Backtest Engine"
Cohesion: 0.22
Nodes (11): BrokerBase, callable, _apply_broker_kwargs(), generate_sensitivity_results(), _perturb_parameter(), Translate `broker_kwargs` into the correct broker setters., Run a tactical asset allocation strategy with Backtrader., run_strategy() (+3 more)

### Community 20 - "Portfolio and Universe"
Cohesion: 0.22
Nodes (10): generate_reports(), Any, Path, Series, Run multiple strategies and aggregate their NAVs into a single portfolio.…, Print performance summary and save standard backtest plots and metrics., run_portfolio(), get_least_volatile_symbols() (+2 more)

### Community 21 - "Legacy Dataset Init"
Cohesion: 0.17
Nodes (6): Dataset, date, Add previous data to the current data., Check if file exists., Convert a symbol to a ticker., To Hugging Face datasets.

### Community 22 - "SP500 Perimeter Definitions"
Cohesion: 0.15
Nodes (8): Perimeter, date, Index constituents data., date, Index constituents S&P 500., Index constituents S&P 500., Download the list of S&P 500 constituents from Wikipedia., SP500

### Community 23 - "Long-Short Quantile Portfolios"
Cohesion: 0.18
Nodes (3): MonthlyLongShortQuantilePortfolio, Semi-annual rebalancing portfolio that: • rebalances at the start of each…, RollingSemesterLongShortPortfolio

### Community 24 - "Optimal Limit Order Tests"
Cohesion: 0.27
Nodes (10): get_optimal_quote(), optimal_limit_order_formula(), Solve for the optimal limit-order price offset from the mid-price. `symbol` is…, q_max : Quantity in ATS to execute t_max : Time in seconds remaining to execute…, Regression tests for `pwb_toolbox.execution.optimal_limit_order`. Locks in the…, test_default_call_matches_legacy_output(), test_different_calibrations_produce_different_quotes(), test_quote_is_always_finite() (+2 more)

### Community 25 - "SSRN Abstract Idea Pipeline"
Cohesion: 0.18
Nodes (3): List all abstract ids from Kili, SsrnPaperCrawler, SsrnPaper

### Community 26 - "IB Server Launch Scripts"
Cohesion: 0.27
Nodes (11): is_ib_ready(), is_ib_running(), is_port_open(), kill_ib(), launch_ib(), login_ib(), main(), Check if IB Gateway is already running. (+3 more)

### Community 27 - "Backtest Result Chart"
Cohesion: 0.31
Nodes (11): Annual Return 5.00%, Annual Volatility 6.69%, Backtest Period 1990-2025, Visible Drawdown Events (2000-2002 flat, 2008-2009, 2011, Feb-Mar 2020 spike), Backtest Result Figure (Results from the Backtest), Last Update Marker (dashed right edge annotation), Low-Volatility, Steady-Compounding Strategy Profile, Maximum Drawdown 19.42% (+3 more)

### Community 28 - "Execution NAV Flow Docs"
Cohesion: 0.20
Nodes (10): append_nav_history, compute_orders, execute_and_log_orders, get_optimal_quote, Optimal Portfolio Liquidation with Limit Orders (Gueant, Lehalle, Tapia), log_current_state, pwb_toolbox.execution.optimal_limit_order, run_strategies (+2 more)

### Community 29 - "Commission Modeling"
Cohesion: 0.31
Nodes (8): ndarray, get_commissions(), _gibbs_sampler(), Safe Roll(1984)-style spread proxy from lag-1 autocov of Δp., Robust Gibbs sampler for c and sigma^2_u with defensive guards. Falls back to a…, _roll_c(), get_pricing(), Fetch OHLC pricing for the requested symbols. Parameters ---------- symbol_list…

### Community 30 - "Stock Perimeter Definitions"
Cohesion: 0.36
Nodes (4): DataFrame, date, Returns a DataFrame of NASDAQ stocks, Stocks

### Community 31 - "Legacy Earnings Estimates"
Cohesion: 0.25
Nodes (4): EarningsSurprise, date, Earnings surprise from Nasdaq., Earnings surprise from Nasdaq.

### Community 32 - "Legacy Extended Datasets"
Cohesion: 0.25
Nodes (4): ExtendedTrading, date, Extended trading from Nasdaq., Extended trading from Nasdaq.

### Community 34 - "Legacy Short Interest Data"
Cohesion: 0.25
Nodes (4): date, Short interest from Nasdaq., Short interest from Nasdaq., ShortInterest

### Community 35 - "Legacy Timeseries Datasets"
Cohesion: 0.25
Nodes (4): date, Timeseries 1mn from Yahoo Finance., Timeseries 1mn from Yahoo Finance., Timeseries1mn

### Community 36 - "Yahoo Timeseries Helpers"
Cohesion: 0.29
Nodes (4): date, Timeseries daily from Yahoo Finance., TimeseriesDaily, yahoo_headers()

### Community 37 - "Backtrader Optimization Docs"
Cohesion: 0.38
Nodes (7): Backtrader engine dependency, optimization_engine module (genetic algorithm), run_strategy (backtesting helper), Tests GitHub Actions workflow, Contribution workflow, Development dependency set, Runtime dependency set

### Community 38 - "Legacy Earnings Surprises"
Cohesion: 0.29
Nodes (4): EarningsForecast, date, Earnings forecast from Nasdaq., Earnings forecast from Nasdaq.

### Community 39 - "Nasdaq Earnings Helpers"
Cohesion: 0.38
Nodes (5): is_valid_json(), nasdaq_headers(), Send a SMS using Twilio., retry_get(), send_sms()

### Community 40 - "README Reporting Examples"
Cohesion: 0.33
Nodes (7): cagr, generate_reports, NAV series (strategy.log_data), plot_equity_curve, pwb_bt.run_strategy (README reference), run_strategy (README example entrypoint), total_return

### Community 41 - "IB Server Cron Environment"
Cohesion: 0.33
Nodes (7): Daily cron scheduling of run_daily.sh, execute_meta_strategy entrypoint, Interactive Brokers server tool (tools/ib_server), launch_ib entrypoint, monitor entrypoint, PWB_API_KEY credential fallback, pwb conda environment (ib_server)

### Community 42 - "Broker Factory"
Cohesion: 0.33
Nodes (5): Connector, create_connector(), Any, Factory for execution connectors. Call :func:`create_connector` with a…, Instantiate a connector based on a config mapping or environment. Parameters…

### Community 43 - "Broker Connector Protocol Docs"
Cohesion: 0.60
Nodes (6): Broker connector protocol (connect/get_account_nav/get_positions/disconnect), CCXTConnector, get_account_nav, get_positions, IBConnector, pwb_toolbox.execution module

### Community 44 - "README Datasets and License"
Cohesion: 0.40
Nodes (6): MIT License (Papers With Backtest), pwb_toolbox.datasets module, get_pricing, load_dataset, pwb_toolbox.performance module, pwb-toolbox package

### Community 46 - "IB Trade Records"
Cohesion: 0.33
Nodes (4): Utility functions to interact with Interactive Brokers via ``ib_insync``. This…, Container for information about a single trade., Return the record as a plain dictionary., TradeRecord

### Community 48 - "Legacy Knowledge Graph Data"
Cohesion: 0.33
Nodes (4): KnowledgeGraph, date, Index constituents data., Index constituents data.

### Community 49 - "Ulcer Index Metrics"
Cohesion: 0.33
Nodes (6): Ulcer index of a price series., Ulcer Performance Index., ulcer_index(), ulcer_performance_index(), test_ulcer_index_positive_when_underwater(), test_ulcer_index_zero_for_monotonic_series()

### Community 53 - "Legacy Momentum Models"
Cohesion: 0.50
Nodes (4): main(), command, option, train_test_split_v2()

### Community 54 - "Project Banner Imagery"
Cohesion: 0.50
Nodes (5): PWB Toolbox Project Banner Image, Financial Market Data Display, Multi-Series Price Time Series Chart, Quantitative Finance Visual Branding, Quote Ticker Grid with Signed Price Changes

### Community 58 - "IB Meta Strategy Execution"
Cohesion: 0.67
Nodes (3): execute(), get_meta_strategy(), Get meta strategy data

### Community 59 - "IB Server Install Script"
Cohesion: 0.83
Nodes (3): log(), install.sh script, warn()

## Knowledge Gaps
- **28 isolated node(s):** `run_daily.sh script`, `pwb_toolbox.performance module`, `run_strategy (README example entrypoint)`, `total_return`, `cagr` (+23 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_pricing()` connect `Commission Modeling` to `Backtest Engine`, `Dataset Loading and Conversion`?**
  _High betweenness centrality (0.250) - this node is a cross-community bridge._
- **Why does `load_dataset()` connect `Dataset Loading and Conversion` to `Legacy Feature Predictors`, `Legacy Feature Targets`, `Legacy Momentum Strategy`, `Legacy Dataset Init`, `Legacy Momentum Models`, `Commission Modeling`, `Stock Perimeter Definitions`?**
  _High betweenness centrality (0.141) - this node is a cross-community bridge._
- **Why does `Dataset` connect `Legacy Dataset Init` to `SSRN Strategy Idea Mining`, `Legacy Raw Dataset Init`, `Legacy Feature Predictors`, `Legacy Knowledge Timeseries`, `Legacy Knowledge Graph Data`, `Legacy Feature Targets`, `SP500 Perimeter Definitions`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `SsrnAbstract` (e.g. with `SsrnAbstractClassifier` and `SsrnAbstractCrawler`) actually correct?**
  _`SsrnAbstract` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `BaseStrategy` (e.g. with `DailyEqualWeightPortfolio` and `DailyLeveragePortfolio`) actually correct?**
  _`BaseStrategy` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `run_daily.sh script`, `pwb_toolbox.performance module`, `run_strategy (README example entrypoint)` to the rest of the system?**
  _28 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `SSRN Strategy Idea Mining` be split into smaller, more focused modules?**
  _Cohesion score 0.05701754385964912 - nodes in this community are weakly interconnected._