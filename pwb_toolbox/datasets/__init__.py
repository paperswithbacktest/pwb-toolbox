from collections import defaultdict
from datetime import date
import os
import re

import datasets as ds
import pandas as pd

HF_ACCESS_TOKEN = os.environ["HF_ACCESS_TOKEN"]
if not HF_ACCESS_TOKEN:
    raise ValueError("Hugging Face access token not found in environment variables")


DAILY_PRICE_DATASETS = [
    "Bonds-Daily-Price",
    "Commodities-Daily-Price",
    "Cryptocurrencies-Daily-Price",
    "ETFs-Daily-Price",
    "Forex-Daily-Price",
    "Indices-Daily-Price",
    "Stocks-Daily-Price",
]

DAILY_FINANCIAL_DATASETS = [
    "Stocks-Quarterly-BalanceSheet",
    "Stocks-Quarterly-CashFlow",
    "Stocks-Quarterly-Earnings",
    "Stocks-Quarterly-IncomeStatement",
]

INTRADAY_PRICE_DATASETS = [
    "Stocks-1Min-Price",
]

INTRADAY_NEWS = [
    "All-Daily-News",
]


SP500_SYMBOLS = [
    "MMM",
    "AOS",
    "ABT",
    "ABBV",
    "ACN",
    "ADBE",
    "AMD",
    "AES",
    "AFL",
    "A",
    "APD",
    "ABNB",
    "AKAM",
    "ALB",
    "ARE",
    "ALGN",
    "ALLE",
    "LNT",
    "ALL",
    "GOOGL",
    "GOOG",
    "MO",
    "AMZN",
    "AMCR",
    "AEE",
    "AEP",
    "AXP",
    "AIG",
    "AMT",
    "AWK",
    "AMP",
    "AME",
    "AMGN",
    "APH",
    "ADI",
    "ANSS",
    "AON",
    "APA",
    "AAPL",
    "AMAT",
    "APTV",
    "ACGL",
    "ADM",
    "ANET",
    "AJG",
    "AIZ",
    "T",
    "ATO",
    "ADSK",
    "ADP",
    "AZO",
    "AVB",
    "AVY",
    "AXON",
    "BKR",
    "BALL",
    "BAC",
    "BK",
    "BBWI",
    "BAX",
    "BDX",
    "BRK-B",
    "BBY",
    "TECH",
    "BIIB",
    "BLK",
    "BX",
    "BA",
    "BKNG",
    "BWA",
    "BSX",
    "BMY",
    "AVGO",
    "BR",
    "BRO",
    "BF-B",
    "BLDR",
    "BG",
    "BXP",
    "CHRW",
    "CDNS",
    "CZR",
    "CPT",
    "CPB",
    "COF",
    "CAH",
    "KMX",
    "CCL",
    "CARR",
    "CTLT",
    "CAT",
    "CBOE",
    "CBRE",
    "CDW",
    "CE",
    "COR",
    "CNC",
    "CNP",
    "CF",
    "CRL",
    "SCHW",
    "CHTR",
    "CVX",
    "CMG",
    "CB",
    "CHD",
    "CI",
    "CINF",
    "CTAS",
    "CSCO",
    "C",
    "CFG",
    "CLX",
    "CME",
    "CMS",
    "KO",
    "CTSH",
    "CL",
    "CMCSA",
    "CAG",
    "COP",
    "ED",
    "STZ",
    "CEG",
    "COO",
    "CPRT",
    "GLW",
    "CPAY",
    "CTVA",
    "CSGP",
    "COST",
    "CTRA",
    "CRWD",
    "CCI",
    "CSX",
    "CMI",
    "CVS",
    "DHR",
    "DRI",
    "DVA",
    "DAY",
    "DECK",
    "DE",
    "DELL",
    "DAL",
    "DVN",
    "DXCM",
    "FANG",
    "DLR",
    "DFS",
    "DG",
    "DLTR",
    "D",
    "DPZ",
    "DOV",
    "DOW",
    "DHI",
    "DTE",
    "DUK",
    "DD",
    "EMN",
    "ETN",
    "EBAY",
    "ECL",
    "EIX",
    "EW",
    "EA",
    "ELV",
    "EMR",
    "ENPH",
    "ETR",
    "EOG",
    "EPAM",
    "EQT",
    "EFX",
    "EQIX",
    "EQR",
    "ERIE",
    "ESS",
    "EL",
    "EG",
    "EVRG",
    "ES",
    "EXC",
    "EXPE",
    "EXPD",
    "EXR",
    "XOM",
    "FFIV",
    "FDS",
    "FICO",
    "FAST",
    "FRT",
    "FDX",
    "FIS",
    "FITB",
    "FSLR",
    "FE",
    "FI",
    "FMC",
    "F",
    "FTNT",
    "FTV",
    "FOXA",
    "FOX",
    "BEN",
    "FCX",
    "GRMN",
    "IT",
    "GE",
    "GEHC",
    "GEV",
    "GEN",
    "GNRC",
    "GD",
    "GIS",
    "GM",
    "GPC",
    "GILD",
    "GPN",
    "GL",
    "GDDY",
    "GS",
    "HAL",
    "HIG",
    "HAS",
    "HCA",
    "DOC",
    "HSIC",
    "HSY",
    "HES",
    "HPE",
    "HLT",
    "HOLX",
    "HD",
    "HON",
    "HRL",
    "HST",
    "HWM",
    "HPQ",
    "HUBB",
    "HUM",
    "HBAN",
    "HII",
    "IBM",
    "IEX",
    "IDXX",
    "ITW",
    "INCY",
    "IR",
    "PODD",
    "INTC",
    "ICE",
    "IFF",
    "IP",
    "IPG",
    "INTU",
    "ISRG",
    "IVZ",
    "INVH",
    "IQV",
    "IRM",
    "JBHT",
    "JBL",
    "JKHY",
    "J",
    "JNJ",
    "JCI",
    "JPM",
    "JNPR",
    "K",
    "KVUE",
    "KDP",
    "KEY",
    "KEYS",
    "KMB",
    "KIM",
    "KMI",
    "KKR",
    "KLAC",
    "KHC",
    "KR",
    "LHX",
    "LH",
    "LRCX",
    "LW",
    "LVS",
    "LDOS",
    "LEN",
    "LLY",
    "LIN",
    "LYV",
    "LKQ",
    "LMT",
    "L",
    "LOW",
    "LULU",
    "LYB",
    "MTB",
    "MRO",
    "MPC",
    "MKTX",
    "MAR",
    "MMC",
    "MLM",
    "MAS",
    "MA",
    "MTCH",
    "MKC",
    "MCD",
    "MCK",
    "MDT",
    "MRK",
    "META",
    "MET",
    "MTD",
    "MGM",
    "MCHP",
    "MU",
    "MSFT",
    "MAA",
    "MRNA",
    "MHK",
    "MOH",
    "TAP",
    "MDLZ",
    "MPWR",
    "MNST",
    "MCO",
    "MS",
    "MOS",
    "MSI",
    "MSCI",
    "NDAQ",
    "NTAP",
    "NFLX",
    "NEM",
    "NWSA",
    "NWS",
    "NEE",
    "NKE",
    "NI",
    "NDSN",
    "NSC",
    "NTRS",
    "NOC",
    "NCLH",
    "NRG",
    "NUE",
    "NVDA",
    "NVR",
    "NXPI",
    "ORLY",
    "OXY",
    "ODFL",
    "OMC",
    "ON",
    "OKE",
    "ORCL",
    "OTIS",
    "PCAR",
    "PKG",
    "PLTR",
    "PANW",
    "PARA",
    "PH",
    "PAYX",
    "PAYC",
    "PYPL",
    "PNR",
    "PEP",
    "PFE",
    "PCG",
    "PM",
    "PSX",
    "PNW",
    "PNC",
    "POOL",
    "PPG",
    "PPL",
    "PFG",
    "PG",
    "PGR",
    "PLD",
    "PRU",
    "PEG",
    "PTC",
    "PSA",
    "PHM",
    "QRVO",
    "PWR",
    "QCOM",
    "DGX",
    "RL",
    "RJF",
    "RTX",
    "O",
    "REG",
    "REGN",
    "RF",
    "RSG",
    "RMD",
    "RVTY",
    "ROK",
    "ROL",
    "ROP",
    "ROST",
    "RCL",
    "SPGI",
    "CRM",
    "SBAC",
    "SLB",
    "STX",
    "SRE",
    "NOW",
    "SHW",
    "SPG",
    "SWKS",
    "SJM",
    "SW",
    "SNA",
    "SOLV",
    "SO",
    "LUV",
    "SWK",
    "SBUX",
    "STT",
    "STLD",
    "STE",
    "SYK",
    "SMCI",
    "SYF",
    "SNPS",
    "SYY",
    "TMUS",
    "TROW",
    "TTWO",
    "TPR",
    "TRGP",
    "TGT",
    "TEL",
    "TDY",
    "TFX",
    "TER",
    "TSLA",
    "TXN",
    "TXT",
    "TMO",
    "TJX",
    "TSCO",
    "TT",
    "TDG",
    "TRV",
    "TRMB",
    "TFC",
    "TYL",
    "TSN",
    "USB",
    "UBER",
    "UDR",
    "ULTA",
    "UNP",
    "UAL",
    "UPS",
    "URI",
    "UNH",
    "UHS",
    "VLO",
    "VTR",
    "VLTO",
    "VRSN",
    "VRSK",
    "VZ",
    "VRTX",
    "VTRS",
    "VICI",
    "V",
    "VST",
    "VMC",
    "WRB",
    "GWW",
    "WAB",
    "WBA",
    "WMT",
    "DIS",
    "WBD",
    "WM",
    "WAT",
    "WEC",
    "WFC",
    "WELL",
    "WST",
    "WDC",
    "WY",
    "WMB",
    "WTW",
    "WYNN",
    "XEL",
    "XYL",
    "YUM",
    "ZBRA",
    "ZBH",
    "ZTS",
]


def load_dataset(
    path,
    symbols=None,
    adjust=True,
    extend=False,
    to_usd=True,
    rate_to_price=True,
):
    dataset = ds.load_dataset(f"paperswithbacktest/{path}", token=HF_ACCESS_TOKEN)
    df = dataset["train"].to_pandas()

    if path in DAILY_PRICE_DATASETS or path in DAILY_FINANCIAL_DATASETS:
        df["date"] = pd.to_datetime(df["date"])

    if path in INTRADAY_PRICE_DATASETS or path in INTRADAY_NEWS:
        df["datetime"] = pd.to_datetime(df["datetime"])

    if isinstance(symbols, list) and "sp500" in symbols:
        symbols.remove("sp500")
        symbols += SP500_SYMBOLS

    if (
        path in DAILY_PRICE_DATASETS
        or path in INTRADAY_PRICE_DATASETS
        or path in DAILY_FINANCIAL_DATASETS
    ) and isinstance(symbols, list):
        df = df[df["symbol"].isin(symbols)].copy()

    if path in INTRADAY_NEWS and isinstance(symbols, list):
        df = df[
            df["symbols"].apply(lambda x: any(symbol in symbols for symbol in x))
        ].copy()

    if path in DAILY_PRICE_DATASETS:
        if adjust and "adj_close" in df.columns:
            adj_factor = df["adj_close"] / df["close"]
            df["adj_open"] = df["open"] * adj_factor
            df["adj_high"] = df["high"] * adj_factor
            df["adj_low"] = df["low"] * adj_factor
            df.drop(columns=["open", "high", "low", "close"], inplace=True)
            df.rename(
                columns={
                    "adj_open": "open",
                    "adj_high": "high",
                    "adj_low": "low",
                    "adj_close": "close",
                },
                inplace=True,
            )
        else:
            if "adj_close" in df.columns:
                df.drop(columns=["adj_close"])

    if path in DAILY_PRICE_DATASETS and (extend and path == "ETFs-Daily-Price"):
        df = __extend_etfs(df)

    if path in DAILY_PRICE_DATASETS and to_usd:
        if path == "Forex-Daily-Price":
            for index, row in df.iterrows():
                if row["symbol"].endswith("USD"):
                    continue
                df.at[index, "open"] = 1 / row["open"]
                df.at[index, "high"] = 1 / row["high"]
                df.at[index, "low"] = 1 / row["low"]
                df.at[index, "close"] = 1 / row["close"]
                df.at[index, "symbol"] = row["symbol"][3:] + "USD"
        elif path == "Indices-Daily-Price":
            df_forex = load_dataset("Forex-Daily-Price", to_usd=True)
            df = __convert_indices_to_usd(df, df_forex)

    if path in DAILY_PRICE_DATASETS and (rate_to_price and path == "Bonds-Daily-Price"):
        for index, row in df.iterrows():
            years_to_maturity = __extract_years_to_maturity(row["symbol"])
            if not years_to_maturity:
                continue
            face_value = 100
            for col in ["open", "high", "low", "close"]:
                rate = row[col]
                df.loc[index, col] = face_value / (1 + rate / 100) ** years_to_maturity

    return df


def __convert_indices_to_usd(
    df_indices: pd.DataFrame, df_forex: pd.DataFrame
) -> pd.DataFrame:
    mapping = {
        "ADSMI": "AED",  # United Arab Emirates
        "AEX": "EUR",  # Netherlands
        "AS30": "AUD",  # Australia
        "AS51": "AUD",  # Australia
        "AS52": "AUD",  # Australia
        "ASE": "EUR",  # Greece
        "ATX": "EUR",  # Austria
        "BEL20": "EUR",  # Belgium
        "BELEX15": "RSD",  # Serbia
        "BGSMDC": "BWP",  # Botswana
        "BHSEEI": "BHD",  # Bahrain
        "BKA": "BAM",  # Bosnia and Herzegovina
        "BLOM": "LBP",  # Lebanon
        "BSX": "BMD",  # Bermuda
        "BUX": "HUF",  # Hungary
        "BVLX": "BOB",  # Bolivia
        "BVPSBVPS": "PAB",  # Panama
        "BVQA": "USD",  # Ecuador
        "CAC": "EUR",  # France
        "CASE": "EGP",  # Egypt
        "CCMP": "USD",  # United States
        "COLCAP": "COP",  # Colombia
        "CRSMBCT": "CRC",  # Costa Rica
        "CSEALL": "LKR",  # Sri Lanka
        "CYSMMAPA": "EUR",  # Cyprus
        "DARSDSEI": "TZS",  # Tanzania
        "DAX": "EUR",  # Germany
        "DFMGI": "AED",  # United Arab Emirates
        "DSEX": "BDT",  # Bangladesh
        "DSM": "QAR",  # Qatar
        "ECU": "USD",  # Ecuador
        "FBMKLCI": "MYR",  # Malaysia
        "FSSTI": "SGD",  # Singapore
        "FTN098": "NAD",  # Namibia
        "FTSEMIB": "EUR",  # Italy
        "GGSECI": "GHS",  # Ghana
        "HEX": "EUR",  # Finland
        "HEX25": "EUR",  # Finland
        "HSI": "HKD",  # Hong Kong
        "IBEX": "EUR",  # Spain
        "IBOV": "BRL",  # Brazil
        "IBVC": "VES",  # Venezuela
        "ICEXI": "ISK",  # Iceland
        "IGPA": "CLP",  # Chile
        "INDEXCF": "RUB",  # Russia
        "INDU": "USD",  # United States
        "INDZI": "IDR",  # Indonesia
        "ISEQ": "EUR",  # Ireland
        "JALSH": "ZAR",  # South Africa
        "JCI": "IDR",  # Indonesia
        "JMSMX": "JMD",  # Jamaica
        "JOSMGNFF": "JOD",  # Jordan
        "KFX": "DKK",  # Denmark
        "KNSMIDX": "KES",  # Kenya
        "KSE100": "PKR",  # Pakistan
        "KZKAK": "KZT",  # Kazakhstan
        "LSXC": "LAK",  # Laos
        "LUXXX": "EUR",  # Luxembourg
        "MALTEX": "EUR",  # Malta
        "MBI": "MKD",  # North Macedonia
        "MERVAL": "ARS",  # Argentina
        "MEXBOL": "MXN",  # Mexico
        "MONEX": "EUR",  # Montenegro
        "MOSENEW": "MAD",  # Morocco
        "MSETOP": "MKD",  # North Macedonia
        "MSM30": "OMR",  # Oman
        "NDX": "USD",  # United States
        "NGSEINDX": "NGN",  # Nigeria
        "NIFTY": "INR",  # India
        "NKY": "JPY",  # Japan
        "NSEASI": "KES",  # Kenya
        "NZSE50FG": "NZD",  # New Zealand
        "OMX": "SEK",  # Sweden
        "OSEAX": "NOK",  # Norway
        "PCOMP": "PHP",  # Philippines
        "PFTS": "UAH",  # Ukraine
        "PSI20": "EUR",  # Portugal
        "PX": "CZK",  # Czech Republic
        "RIGSE": "EUR",  # Latvia
        "RTY": "USD",  # United States
        "SASEIDX": "SAR",  # Saudi Arabia
        "SASX10": "BAM",  # Bosnia and Herzegovina
        "SBITOP": "EUR",  # Slovenia
        "SEMDEX": "MUR",  # Mauritius
        "SENSEX": "INR",  # India
        "SET50": "THB",  # Thailand
        "SHCOMP": "CNY",  # China
        "SHSZ300": "CNY",  # China
        "SKSM": "EUR",  # Slovakia
        "SMI": "CHF",  # Switzerland
        "SOFIX": "BGN",  # Bulgaria
        "SPBLPGPT": "PEN",  # Peru
        "SPTSX": "CAD",  # Canada
        "SPX": "USD",  # United States
        "SSE50": "CNY",  # China
        "SX5E": "EUR",  # Europe
        "TA125": "ILS",  # Israel
    }
    frames = []

    # iterate over the symbols that actually exist in df_indices
    for symbol in df_indices["symbol"].unique():
        df_idx = df_indices[df_indices["symbol"] == symbol].copy()

        # 1) Figure out what currency the index is quoted in.
        ccy = mapping.get(symbol)  # None if not mapped
        if ccy is None or ccy == "USD":
            # Unknown or already USD – just keep the original rows
            frames.append(df_idx)
            continue

        # 2) Find the matching FX rate (home-ccy → USD)
        pair = ccy + "USD"
        df_fx = df_forex[df_forex["symbol"] == pair].copy()

        if df_idx.empty or df_fx.empty:
            # No FX data – keep raw index levels instead of dropping them
            frames.append(df_idx)
            continue

        # 3) Merge on date and convert OHLC
        merged = pd.merge(df_idx, df_fx, on="date", suffixes=("", "_fx"))
        for col in ("open", "high", "low", "close"):
            merged[col] = merged[col] * merged[f"{col}_fx"]

        frames.append(merged[["symbol", "date", "open", "high", "low", "close"]])

    if not frames:
        return pd.DataFrame(columns=df_indices.columns)

    # Combine everything back into one DataFrame
    return pd.concat(frames, ignore_index=True)


def __extract_years_to_maturity(bond_symbol):
    match = re.search(r"(\d+)([YM])$", bond_symbol)
    if match:
        time_value = int(match.group(1))  # Extract the numeric value
        time_unit = match.group(2)  # Extract the time unit (Y or M)
        if time_unit == "Y":
            return time_value  # It's already in years
        elif time_unit == "M":
            return time_value / 12  # Convert months to years


def __extend_etfs(df_etfs):

    mapping = {
        "AGG": ["Bonds-Daily-Price", "US10Y"],
        "EPP": ["Indices-Daily-Price", "HSI"],
        "EWA": ["Indices-Daily-Price", "AS30"],  # Australia
        "EWO": ["Indices-Daily-Price", "ATX"],  # Austria
        "EWK": ["Indices-Daily-Price", "BEL20"],  # Belgium
        "EWZ": ["Indices-Daily-Price", "IBOV"],  # Brazil
        "EWC": ["Indices-Daily-Price", "SPTSX"],  # Canada
        "FXI": ["Indices-Daily-Price", "SSE50"],  # China
        "EWQ": ["Indices-Daily-Price", "CAC"],  # France
        "EWG": ["Indices-Daily-Price", "DAX"],  # Germany
        "EWH": ["Indices-Daily-Price", "HSI"],  # Hong Kong
        "EWI": ["Indices-Daily-Price", "FTSEMIB"],  # Italy
        "EWJ": ["Indices-Daily-Price", "NKY"],
        "EWM": ["Indices-Daily-Price", "FBMKLCI"],  # Malaysia
        "EWW": ["Indices-Daily-Price", "MEXBOL"],  # Mexico
        "EWN": ["Indices-Daily-Price", "AEX"],  # Netherlands
        "EWS": ["Indices-Daily-Price", "FSSTI"],  # Singapore
        "EZA": ["Indices-Daily-Price", "TOP40"],  # South Africa
        "EWP": ["Indices-Daily-Price", "IBEX"],  # Spain
        "EWD": ["Indices-Daily-Price", "OMX"],  # Sweden
        "EWL": ["Indices-Daily-Price", "SMI"],  # Switzerland
        "EWT": ["Indices-Daily-Price", "TWSE"],  # Taiwan
        "EWU": ["Indices-Daily-Price", "UKX"],  # United Kingdom
        "GLD": ["Commodities-Daily-Price", "GC1"],
        "IEF": ["Bonds-Daily-Price", "US10Y"],
        "IEV": ["Indices-Daily-Price", "SX5E"],
        "IWB": ["Indices-Daily-Price", "SPX"],
        "SHY": ["Bonds-Daily-Price", "US1Y"],
        "SPY": ["Indices-Daily-Price", "SPX"],
        "THD": ["Indices-Daily-Price", "SET50"],  # Thailand
    }
    symbols = df_etfs.symbol.unique()
    mapping = {k: v for k, v in mapping.items() if k in symbols}

    # Nothing to extend → just return the input
    if not mapping:
        return df_etfs.copy()

    # ------------------------------------------------------------------ step 2
    grouped = defaultdict(list)  # {path: [proxy1, proxy2, ...]}
    for _, (path, proxy) in mapping.items():
        grouped[path].append(proxy)

    # Load each dataset only if there's at least one proxy symbol
    other_frames = []
    for path, proxies in grouped.items():
        if proxies:  # skip empty lists
            other_frames.append(load_dataset(path, proxies, to_usd=True))

    # If no proxy data could be loaded, fall back to raw ETF data
    if not other_frames:
        return df_etfs.copy()

    df_others = pd.concat(other_frames, ignore_index=True)

    # ------------------------------------------------------------------ step 3
    frames = []
    for etf, (__, proxy) in mapping.items():
        etf_data = df_etfs[df_etfs["symbol"] == etf]
        proxy_data = df_others[df_others["symbol"] == proxy]

        if etf_data.empty or proxy_data.empty:
            frames.append(etf_data)  # keep raw ETF if proxy missing
            continue

        # Find first overlapping date
        first_common = etf_data.loc[
            etf_data["date"].isin(proxy_data["date"]), "date"
        ].min()
        if pd.isna(first_common):
            frames.append(etf_data)  # no overlap → keep raw ETF
            continue

        # Compute adjustment factor on that date
        k = (
            etf_data.loc[etf_data["date"] == first_common, "close"].iloc[0]
            / proxy_data.loc[proxy_data["date"] == first_common, "close"].iloc[0]
        )

        # Scale proxy history before the overlap
        hist = proxy_data[proxy_data["date"] < first_common].copy()
        hist[["open", "high", "low", "close"]] *= k
        hist["symbol"] = etf

        # Combine proxy history + actual ETF data
        frames.append(pd.concat([hist, etf_data]))

    # Add ETFs that were never in the mapping
    untouched = set(symbols) - set(mapping)
    frames.append(df_etfs[df_etfs["symbol"].isin(untouched)])

    return (
        pd.concat(frames, ignore_index=True)
        .sort_values(["date", "symbol"])
        .reset_index(drop=True)
    )


ALLOWED_FIELDS = {"open", "high", "low", "close", "volume"}


def get_pricing(
    symbol_list,
    fields=None,  # ← default set below
    start_date="1980-01-01",
    end_date=date.today().isoformat(),
    extend=False,
    keep_single_level=True,  # backward-compat flag
):
    """
    Fetch OHLC pricing for the requested symbols.

    Parameters
    ----------
    symbol_list : str | list[str]
        One ticker or a list of tickers.
    fields : list[str] | None
        Any subset of ["open", "high", "low", "close"].
        Defaults to ["close"] for backward compatibility.
    start_date, end_date : str (YYYY-MM-DD)
        Slice the date index (inclusive).
    extend : bool
        Pass-through to `load_dataset(..., extend=extend)`.
    keep_single_level : bool
        If `True` and only one field is requested, flatten the columns so the
        output matches the old behaviour (columns = symbols).  If `False`
        you always get a two-level MultiIndex `(symbol, field)`.

    Returns
    -------
    pd.DataFrame
        * MultiIndex columns (symbol, field) when `len(fields) > 1`
        * Single-level columns     (symbol)      when one field & keep_single_level=True
    """
    # ------------------------------------------------------------------ sanity
    if fields is None:
        fields = ["close"]
    if isinstance(symbol_list, str):
        symbol_list = [symbol_list]

    fields = [f.lower() for f in fields]
    bad = [f for f in fields if f not in ALLOWED_FIELDS]
    if bad:
        raise ValueError(f"Invalid field(s): {bad}. Allowed: {sorted(ALLOWED_FIELDS)}")

    # --------------------------------------------------------------- download
    DATASETS = [
        ("Stocks-Daily-Price", extend),
        ("ETFs-Daily-Price", extend),
        ("Cryptocurrencies-Daily-Price", extend),
        ("Bonds-Daily-Price", extend),
        ("Commodities-Daily-Price", extend),
        ("Forex-Daily-Price", extend),
        ("Indices-Daily-Price", False),  # indices generally have no proxy data
    ]
    remaining = set(symbol_list)  # symbols still to fetch
    frames = []
    for dataset_name, ext_flag in DATASETS:
        if not remaining:  # all symbols resolved → stop early
            break
        df_part = load_dataset(dataset_name, list(remaining), extend=ext_flag)
        if not df_part.empty:
            frames.append(df_part)
            remaining -= set(df_part["symbol"].unique())
    df = pd.concat(frames, ignore_index=True)

    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df.sort_index(inplace=True)
    df = df.loc[start_date:end_date]

    # ------------------------------------------------------------- reshape
    # Pivot can accept a list of values: returns columns = (field, symbol)
    prices = df.pivot_table(values=fields, index=df.index, columns="symbol")

    # Make outer level = symbol, inner = field  →  pivot_df[sym] gives OHLC block
    prices = prices.swaplevel(axis=1).sort_index(axis=1)

    # Optional: flatten back to the legacy layout if only one field requested
    if keep_single_level and len(fields) == 1:
        field = fields[0]
        prices.columns = prices.columns.droplevel(1)  # keep only the symbol names
        # optional: rename index level for clarity
        prices.name = field

    return prices
