from collections import defaultdict
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


def __convert_indices_to_usd(df_indices, df_forex):
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
    symbols = df_indices.symbol.unique()
    mapping = {k: v for k, v in mapping.items() if k in symbols}
    frames = []
    for symbol, currency in mapping.items():
        df_index = df_indices[df_indices["symbol"] == symbol].copy()
        if currency == "USD":
            frames.append(df_index)
            continue
        df_forex_currency = df_forex[df_forex["symbol"] == currency + "USD"].copy()
        if df_index.empty or df_forex_currency.empty:
            continue
        # Merge dataframes on the date column
        merged_df = pd.merge(
            df_index, df_forex_currency, on="date", suffixes=("", "_forex")
        )

        # Multiply the index prices by the corresponding forex rates
        merged_df["open"] = merged_df["open"] * merged_df["open_forex"]
        merged_df["high"] = merged_df["high"] * merged_df["high_forex"]
        merged_df["low"] = merged_df["low"] * merged_df["low_forex"]
        merged_df["close"] = merged_df["close"] * merged_df["close_forex"]

        frames.append(merged_df[["symbol", "date", "open", "high", "low", "close"]])

    df = pd.concat(frames, ignore_index=True)
    return df


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
        "EWJ": ["Indices-Daily-Price", "NKY"],
        "GLD": ["Commodities-Daily-Price", "GC1"],
        "IEF": ["Bonds-Daily-Price", "US10Y"],
        "IEV": ["Indices-Daily-Price", "SX5E"],
        "IWB": ["Indices-Daily-Price", "SPX"],
        "SHY": ["Bonds-Daily-Price", "US1Y"],
        "SPY": ["Indices-Daily-Price", "SPX"],
    }
    symbols = df_etfs.symbol.unique()
    mapping = {k: v for k, v in mapping.items() if k in symbols}

    grouped_path_symbols = defaultdict(list)
    for value in mapping.values():
        grouped_path_symbols[value[0]].append(value[1])
    grouped_path_symbols = dict(grouped_path_symbols)
    df_others = pd.concat(
        [
            load_dataset(path, symbols, to_usd=True)
            for path, symbols in grouped_path_symbols.items()
        ]
    )

    frames = []
    for etf, other in mapping.items():
        other_symbol = other[1]
        # Get the ETF & Index data
        etf_data = df_etfs[df_etfs["symbol"] == etf]
        if etf_data.empty:
            continue
        other_data = df_others[df_others["symbol"] == other_symbol]
        if other_data.empty:
            continue

        # Find the first overlapping date
        common_dates = etf_data["date"].isin(other_data["date"])
        first_common_date = etf_data.loc[common_dates, "date"].min()

        if pd.isnull(first_common_date):
            print(f"No common date found for {etf} and {other_symbol}")
            continue

        etf_first_common = etf_data[etf_data["date"] == first_common_date]
        other_first_common = other_data[other_data["date"] == first_common_date]

        # Compute the adjustment factor (using closing prices for simplicity)
        adjustment_factor = (
            etf_first_common["close"].values[0] / other_first_common["close"].values[0]
        )

        # Adjust index data before the first common date
        index_data_before_common = other_data[
            other_data["date"] < first_common_date
        ].copy()
        for column in ["open", "high", "low", "close"]:
            index_data_before_common.loc[:, column] *= adjustment_factor
        index_data_before_common.loc[:, "symbol"] = etf

        # Combine adjusted index data with ETF data
        combined_data = pd.concat([index_data_before_common, etf_data])
        frames.append(combined_data)

    # Concatenate all frames to form the final dataframe
    df = pd.concat(frames).sort_values(by=["date", "symbol"]).reset_index(drop=True)
    return df
