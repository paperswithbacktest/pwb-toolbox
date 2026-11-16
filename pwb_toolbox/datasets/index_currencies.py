"""Currency of every series in ``Indices-Daily-Price``, and its conversion to dollars.

The published table quotes every index in the currency of its market: the DAX
in euros (19 909.14 on 2024-12-30), the FTSE 100 in pounds (7 604.30 on
2020-01-02), the Nikkei in yen. ``load_dataset(..., to_usd=False)`` returns
those levels untouched; ``to_usd=True`` multiplies each one by the dollar value
of its currency (``XXXUSD`` in ``Forex-Daily-Price``) on the same day.

What this module fixes (2026-11-16): the old table behind ``to_usd`` missed
UKX, TWSE, WIG, TOP40, XU100, CRO, TALSE, VILSE, TUSISE and IDX:US -- left in
their own currency without a word -- and named the wrong currency for three
symbols (BVLX is the Lisbon all-share in euros, not Bolivia; BKA is the Boursa
Kuwait all-share, not Bosnia; MSETOP is the Mongolian Top 20, not North
Macedonia). Rows whose currency had no rate that day were dropped silently.

Rules, in the order they are tried for a row of currency ``C`` on day ``d``:

1. a hard peg from :data:`PEGS` in force on ``d``: the Gulf currencies to the
   dollar (their pairs start in 2009-10 and carry one-day spikes, AEDUSD x7
   on 2016-11-08), the convertible mark and the lev to the euro, the Namibian
   dollar to the rand;
2. otherwise the ``CUSD`` close of ``Forex-Daily-Price`` on ``d``, or on the
   last quoted day at most :data:`FX_STALENESS_DAYS` before it;
3. otherwise the row cannot be converted: it is dropped, and the load warns
   (:class:`IndexCurrencyWarning`) with the symbol and the dates lost. A
   symbol asked for by name that has no convertible row at all raises
   ``ValueError`` -- ``to_usd=False`` returns it in its own currency.

The euro: an index of a late adopter (:data:`EURO_ADOPTIONS`) is in its legacy
currency before the changeover. Its rate there is ``legacyUSD x conversion
rate`` when the legacy pair is in the forex table, ``EURUSD`` when the legacy
currency was already hard-pegged to the euro at its conversion rate, and
missing otherwise. Scaling by the conversion rate keeps the dollar series
continuous across the changeover. Before 1999 the founding members use the
synthetic ``EURUSD`` of the forex table, which stands for the legacy currencies
at their irrevocable rates -- an approximation, documented here.

Open, high and low take the pair's own open, high and low where the row is converted at
the market pair quoted that very day -- what the loader always did, so the indices it
already converted correctly do not move. Elsewhere (a peg, a stale quote, a pre-euro
segment) one rate, the close's, applies to all four columns.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

#: Tolerance when the forex table has no quote on the index's day (a holiday
#: of the currency market): the last quote at most this many days earlier.
FX_STALENESS_DAYS = 7

#: Series that are not prices in any currency (volatility indices, in points
#: of annualised volatility): never converted.
NO_CURRENCY = None

#: ISO code of the currency each symbol of ``Indices-Daily-Price`` is quoted
#: in, as published. Levels checked on 2024-12-30/31 against published closes
#: for the large markets; the ambiguous tickers checked by correlation with a
#: sibling index (BVLX vs PSI20: 0.968) or by the published level (MSETOP
#: 51 296.39 on 2024-12-31, the Mongolian Stock Exchange's own report).
INDEX_CURRENCY = {
    "ADSMI": "AED",  # Abu Dhabi
    "AEX": "EUR",  # Netherlands
    "AS30": "AUD",  # Australia, All Ordinaries
    "AS51": "AUD",  # Australia, S&P/ASX 200
    "AS52": "AUD",  # Australia
    "ASE": "EUR",  # Greece (drachma before 2001, see EURO_ADOPTIONS)
    "ATX": "EUR",  # Austria
    "BEL20": "EUR",  # Belgium
    "BELEX15": "RSD",  # Serbia
    "BGSMDC": "BWP",  # Botswana
    "BHSEEI": "BHD",  # Bahrain
    "BKA": "KWD",  # Boursa Kuwait All Share (not Bosnia)
    "BLOM": "USD",  # Beirut: constituents trade in dollars; the level did not follow the
    #                 lira's 98 % fall after 2019 (786 at end-2019, 2 517 at end-2024)
    "BSX": "BMD",  # Bermuda
    "BUX": "HUF",  # Hungary
    "BVLX": "EUR",  # Lisbon PSI All-Share (not Bolivia)
    "BVPSBVPS": "PAB",  # Panama
    "BVQA": "USD",  # Ecuador, Quito
    "CAC": "EUR",  # France
    "CASE": "EGP",  # Egypt
    "CCMP": "USD",  # Nasdaq Composite
    "COLCAP": "COP",  # Colombia
    "CRO": "EUR",  # Croatia (kuna before 2023, see EURO_ADOPTIONS)
    "CRSMBCT": "CRC",  # Costa Rica
    "CSEALL": "LKR",  # Sri Lanka
    "CYSMMAPA": "EUR",  # Cyprus (pound before 2008)
    "DARSDSEI": "TZS",  # Tanzania
    "DAX": "EUR",  # Germany
    "DFMGI": "AED",  # Dubai
    "DSEX": "BDT",  # Bangladesh
    "DSM": "QAR",  # Qatar
    "ECU": "USD",  # Ecuador, Guayaquil
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
    "IDX:US": "USD",  # US-listed Indonesia fund, in dollars
    "IGPA": "CLP",  # Chile
    "INDEXCF": "RUB",  # Russia
    "INDU": "USD",  # Dow Jones Industrial Average
    "INDZI": "IDR",  # Indonesia
    "ISEQ": "EUR",  # Ireland
    "JALSH": "ZAR",  # South Africa, All Share
    "JCI": "IDR",  # Indonesia
    "JMSMX": "JMD",  # Jamaica
    "JOSMGNFF": "JOD",  # Jordan
    "KFX": "DKK",  # Denmark
    "KNSMIDX": "KES",  # Kenya
    "KSE100": "PKR",  # Pakistan
    "KZKAK": "KZT",  # Kazakhstan
    "LSXC": "LAK",  # Laos
    "LUXXX": "EUR",  # Luxembourg
    "MALTEX": "EUR",  # Malta (lira before 2008)
    "MBI": "MKD",  # North Macedonia
    "MERVAL": "ARS",  # Argentina
    "MEXBOL": "MXN",  # Mexico
    "MONEX": "EUR",  # Montenegro
    "MOSENEW": "MAD",  # Morocco
    "MSETOP": "MNT",  # Mongolian Stock Exchange Top 20 (not North Macedonia)
    "MSM30": "OMR",  # Oman
    "NDX": "USD",  # Nasdaq 100
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
    "RIGSE": "EUR",  # Latvia (lats before 2014)
    "RTY": "USD",  # Russell 2000
    "SASEIDX": "SAR",  # Saudi Arabia
    "SASX10": "BAM",  # Bosnia and Herzegovina
    "SBITOP": "EUR",  # Slovenia (tolar before 2007)
    "SEMDEX": "MUR",  # Mauritius
    "SENSEX": "INR",  # India
    "SET50": "THB",  # Thailand
    "SHCOMP": "CNY",  # China
    "SHSZ300": "CNY",  # China
    "SKSM": "EUR",  # Slovakia (koruna before 2009)
    "SMI": "CHF",  # Switzerland
    "SOFIX": "EUR",  # Bulgaria (lev, pegged to the euro, before 2026)
    "SPBLPGPT": "PEN",  # Peru
    "SPTSX": "CAD",  # Canada
    "SPX": "USD",  # S&P 500
    "SSE50": "CNY",  # China
    "SX5E": "EUR",  # Euro Stoxx 50
    "TA125": "ILS",  # Israel
    "TALSE": "EUR",  # Estonia (kroon before 2011)
    "TEDPIX": "IRR",  # Iran
    "TOP40": "ZAR",  # South Africa, Top 40
    "TUSISE": "TND",  # Tunisia
    "TWSE": "TWD",  # Taiwan
    "UKX": "GBP",  # FTSE 100
    "VHINDEX": "VND",  # Vietnam, Hanoi
    "VILSE": "EUR",  # Lithuania (litas before 2015)
    "VIX": NO_CURRENCY,
    "VNINDEX": "VND",  # Vietnam, Ho Chi Minh City
    "VSTOXX": NO_CURRENCY,
    "VXJ": NO_CURRENCY,
    "WIG": "PLN",  # Poland
    "XU100": "TRY",  # Turkey
}

#: ``{symbol: (changeover, legacy currency, legacy units per euro, hard euro
#: peg at that rate since)}`` for the indices of late euro adopters.
EURO_ADOPTIONS = {
    "ASE": ("2001-01-01", "GRD", 340.75, None),
    "SBITOP": ("2007-01-01", "SIT", 239.64, None),
    "CYSMMAPA": ("2008-01-01", "CYP", 0.585274, None),
    "MALTEX": ("2008-01-01", "MTL", 0.4293, None),
    "SKSM": ("2009-01-01", "SKK", 30.126, None),
    "TALSE": ("2011-01-01", "EEK", 15.6466, "1999-01-01"),
    "RIGSE": ("2014-01-01", "LVL", 0.702804, "2005-01-01"),
    "VILSE": ("2015-01-01", "LTL", 3.4528, "2002-02-02"),
    "CRO": ("2023-01-01", "HRK", 7.5345, None),
    "SOFIX": ("2026-01-01", "BGN", 1.95583, "1999-01-01"),
}

#: ``{currency: (since, anchor, currency units per anchor unit)}``: a hard peg,
#: used instead of the market pair from ``since`` on.
PEGS = {
    "AED": ("1997-11-01", "USD", 3.6725),
    "SAR": ("1986-06-01", "USD", 3.75),
    "QAR": ("2001-07-09", "USD", 3.64),
    "BHD": ("1980-12-01", "USD", 0.376),
    "OMR": ("1986-01-01", "USD", 0.3845),
    "JOD": ("1995-10-23", "USD", 0.709),
    "BMD": (None, "USD", 1.0),
    "PAB": (None, "USD", 1.0),
    "BAM": ("1999-01-01", "EUR", 1.95583),
    "BGN": ("1999-01-01", "EUR", 1.95583),
    "NAD": ("1993-01-01", "ZAR", 1.0),
}

_PRICE_COLUMNS = ("open", "high", "low", "close", "adj_open", "adj_high", "adj_low", "adj_close")


class IndexCurrencyWarning(UserWarning):
    """Rows of ``Indices-Daily-Price`` that ``to_usd=True`` could not convert and dropped."""


def needed_currencies(symbols) -> list:
    """The ``XXX`` codes whose ``XXXUSD`` rates converting ``symbols`` may read."""
    out = set()
    for symbol in symbols:
        ccy = INDEX_CURRENCY.get(symbol)
        if ccy and ccy != "USD":
            out.add(ccy)
        if symbol in EURO_ADOPTIONS:
            out.add(EURO_ADOPTIONS[symbol][1])
    for ccy in list(out):
        peg = PEGS.get(ccy)
        if peg and peg[1] != "USD":
            out.add(peg[1])
    return sorted(out)


def _fx_bars(df_forex: pd.DataFrame) -> dict:
    """``{XXX: DataFrame of XXXUSD open/high/low/close indexed by sorted day}``."""
    if df_forex is None or df_forex.empty:
        return {}
    cols = [c for c in ("open", "high", "low", "close") if c in df_forex.columns]
    fx = df_forex[df_forex["symbol"].astype(str).str.endswith("USD")]
    out = {}
    for symbol, rows in fx.groupby("symbol"):
        frame = rows[cols].astype("float64").set_index(pd.to_datetime(rows["date"]))
        frame = frame[np.isfinite(frame["close"]) & (frame["close"] > 0)]
        frame = frame[~frame.index.duplicated(keep="last")].sort_index()
        out[str(symbol)[:-3]] = frame
    return out


def _intraday_ratio(bars: dict, symbol: str, days: pd.DatetimeIndex, col: str) -> np.ndarray:
    """``XXXUSD[col] / XXXUSD[close]`` on the index's own day, 1 elsewhere.

    Applied only where the row's rate is the market pair of the index's currency quoted that
    very day -- not a peg, not a stale quote, not a pre-euro legacy segment -- so that open,
    high and low are converted at the pair's own open, high and low, as before 2026-11-16.
    """
    out = np.ones(len(days))
    ccy = INDEX_CURRENCY.get(symbol)
    if not ccy or ccy == "USD" or ccy in PEGS:
        return out
    frame = bars.get(ccy)
    if frame is None or col not in frame.columns:
        return out
    eligible = np.ones(len(days), dtype=bool)
    adoption = EURO_ADOPTIONS.get(symbol)
    if adoption is not None:
        eligible &= days.values >= np.datetime64(pd.Timestamp(adoption[0]))
    ratio = (frame[col] / frame["close"]).reindex(days).to_numpy()
    good = eligible & np.isfinite(ratio) & (ratio > 0)
    out[good] = ratio[good]
    return out


def _fx_table(df_forex: pd.DataFrame) -> dict:
    """``{XXX: close series of XXXUSD indexed by sorted day}``."""
    if df_forex is None or df_forex.empty:
        return {}
    fx = df_forex[df_forex["symbol"].astype(str).str.endswith("USD")]
    out = {}
    for symbol, rows in fx.groupby("symbol"):
        s = pd.Series(
            rows["close"].astype("float64").to_numpy(),
            index=pd.to_datetime(rows["date"]),
        )
        s = s[np.isfinite(s) & (s > 0)]
        s = s[~s.index.duplicated(keep="last")].sort_index()
        out[str(symbol)[:-3]] = s
    return out


def _market_rate(fx: dict, ccy: str, days: pd.DatetimeIndex) -> np.ndarray:
    """``ccyUSD`` on each day, or the last quote within the staleness window."""
    if ccy == "USD":
        return np.ones(len(days))
    series = fx.get(ccy)
    if series is None or series.empty:
        return np.full(len(days), np.nan)
    order = np.argsort(days.values, kind="stable")
    left = pd.DataFrame({"day": days.values[order], "pos": order})
    right = pd.DataFrame({"day": series.index.values, "rate": series.to_numpy()})
    merged = pd.merge_asof(
        left, right, on="day", direction="backward",
        tolerance=pd.Timedelta(days=FX_STALENESS_DAYS),
    )
    out = np.full(len(days), np.nan)
    out[merged["pos"].to_numpy()] = merged["rate"].to_numpy()
    return out


def currency_rate(fx: dict, ccy: str, days: pd.DatetimeIndex) -> np.ndarray:
    """Dollars per unit of ``ccy`` on each day.

    A hard peg in force (:data:`PEGS`) wins over the market pair: the minor
    pairs of the forex table carry one-day spikes (``AEDUSD`` x7 on
    2016-11-08) that a pegged currency cannot have. Elsewhere the market rate.
    """
    rate = _market_rate(fx, ccy, days)
    peg = PEGS.get(ccy)
    if peg is not None:
        since, anchor, units = peg
        pegged = np.ones(len(days), dtype=bool)
        if since is not None:
            pegged = days.values >= np.datetime64(pd.Timestamp(since))
        if pegged.any():
            rate[pegged] = _market_rate(fx, anchor, days[pegged]) / units
    return rate


def index_rate(fx: dict, symbol: str, days: pd.DatetimeIndex) -> np.ndarray:
    """Dollars per index point's currency unit for ``symbol`` on each day (NaN: unknown)."""
    ccy = INDEX_CURRENCY[symbol]
    rate = currency_rate(fx, ccy, days)
    adoption = EURO_ADOPTIONS.get(symbol)
    if adoption is not None:
        changeover, legacy, per_euro, pegged_since = adoption
        before = days.values < np.datetime64(pd.Timestamp(changeover))
        if before.any():
            legacy_rate = _market_rate(fx, legacy, days[before]) * per_euro
            if pegged_since is not None:
                # Pegged to the euro at the conversion rate: EURUSD is exact.
                pegged = days[before].values >= np.datetime64(pd.Timestamp(pegged_since))
                legacy_rate[pegged] = rate[before][pegged]
            rate[before] = legacy_rate
    return rate


def convert_indices_to_usd(df_indices: pd.DataFrame, df_forex: pd.DataFrame, requested=None) -> pd.DataFrame:
    """``df_indices`` with every price column in dollars (see the module docstring).

    ``requested`` is the list of symbols the caller named, if any: one of them
    left without a single convertible row raises ``ValueError``; any other
    dropped row is reported by an :class:`IndexCurrencyWarning`.
    """
    if df_indices.empty or "symbol" not in df_indices.columns:
        return df_indices
    fx = _fx_table(df_forex)
    bars = _fx_bars(df_forex)
    requested = set(requested or ())
    days_all = pd.to_datetime(df_indices["date"])
    keep = np.ones(len(df_indices), dtype=bool)
    rate_all = np.ones(len(df_indices))
    intraday = {c: np.ones(len(df_indices)) for c in ("open", "high", "low")}
    out = df_indices.copy()
    price_cols = [c for c in _PRICE_COLUMNS if c in out.columns]
    for col in price_cols:
        out[col] = out[col].astype("float64")
    dropped = {}
    unconvertible = []
    for symbol, idx in out.groupby("symbol", sort=False).indices.items():
        if symbol in INDEX_CURRENCY and INDEX_CURRENCY[symbol] is NO_CURRENCY:
            continue
        days = pd.DatetimeIndex(days_all.iloc[idx])
        if symbol not in INDEX_CURRENCY:
            rate = np.full(len(idx), np.nan)
        else:
            rate = index_rate(fx, symbol, days)
        ok = np.isfinite(rate)
        if not ok.all():
            lost = days[~ok]
            dropped[symbol] = (int((~ok).sum()), len(idx), lost.min().date(), lost.max().date())
            if not ok.any() and symbol in requested:
                unconvertible.append(symbol)
        rate_all[idx] = rate
        for col in intraday:
            intraday[col][idx] = _intraday_ratio(bars, symbol, days, col)
        keep[idx[~ok]] = False
    if unconvertible:
        reasons = ", ".join(
            f"{s} ({INDEX_CURRENCY.get(s, 'currency unknown')})" for s in sorted(unconvertible)
        )
        raise ValueError(
            "Indices-Daily-Price: no dollar rate for "
            f"{reasons} in Forex-Daily-Price, so to_usd=True cannot convert it. "
            "Pass to_usd=False to get the index in its own currency."
        )
    if dropped:
        detail = "; ".join(
            f"{s} [{INDEX_CURRENCY.get(s, '?')}] {n}/{total} rows {a}..{b}"
            for s, (n, total, a, b) in sorted(dropped.items())
        )
        warnings.warn(
            "Indices-Daily-Price to_usd=True: rows without a dollar rate for their "
            f"currency were dropped -- {detail}. Use to_usd=False for the local-currency series.",
            IndexCurrencyWarning,
            stacklevel=3,
        )
    for col in price_cols:
        base = col[4:] if col.startswith("adj_") else col
        factor = rate_all * intraday[base] if base in intraday else rate_all
        out[col] = out[col].to_numpy() * factor
    return out[keep].reset_index(drop=True)
