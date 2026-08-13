"""Pull a trading session out of ``pwb_toolbox.datasets`` and reduce it to facts.

The split here is deliberate: every function that shapes data is pure and takes
a DataFrame, and :func:`collect` is the only thing that touches the network.
That keeps the whole reduction — which close, which mover, how wide the
breadth — under test without a ``PWB_API_KEY`` or a live session, which is the
rule the rest of this repo's suite runs under.

Nothing here formats anything for speech. The facts come out as numbers and
``script.py`` decides how they get said.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

# Symbols as the Indices-Daily-Price dataset spells them, paired with the name
# an anchor would actually say.
INDEX_NAMES = {
    "SPX": "the S and P five hundred",
    "CCMP": "the Nasdaq",
    "NDX": "the Nasdaq one hundred",
    "INDU": "the Dow",
    "RTY": "the Russell two thousand",
}

DEFAULT_INDICES = ("SPX", "CCMP", "INDU")
DEFAULT_RATE_SYMBOL = "US10Y"
DEFAULT_CRUDE_SYMBOL = "CL1"
DEFAULT_CRYPTO_SYMBOL = "BTC"

# Enough large caps that the movers segment usually has a pronounceable name.
# Anything absent falls back to spelling the ticker, which is also how a desk
# reads an unfamiliar one. Override with --names for fuller coverage.
COMPANY_NAMES = {
    "AAPL": "Apple",
    "ABBV": "AbbVie",
    "ADBE": "Adobe",
    "AMD": "A M D",
    "AMZN": "Amazon",
    "AVGO": "Broadcom",
    "AXP": "American Express",
    "BA": "Boeing",
    "BAC": "Bank of America",
    "BKNG": "Booking Holdings",
    "BLK": "BlackRock",
    "CAT": "Caterpillar",
    "CRM": "Salesforce",
    "CRWD": "CrowdStrike",
    "CSCO": "Cisco",
    "CVX": "Chevron",
    "DAL": "Delta",
    "DIS": "Disney",
    "F": "Ford",
    "FDX": "FedEx",
    "GE": "General Electric",
    "GM": "General Motors",
    "GOOGL": "Alphabet",
    "GS": "Goldman Sachs",
    "HD": "Home Depot",
    "IBM": "I B M",
    "INTC": "Intel",
    "JNJ": "Johnson and Johnson",
    "JPM": "J P Morgan",
    "KO": "Coca-Cola",
    "LLY": "Eli Lilly",
    "MA": "Mastercard",
    "MCD": "McDonald's",
    "META": "Meta",
    "MRK": "Merck",
    "MS": "Morgan Stanley",
    "MSFT": "Microsoft",
    "MU": "Micron",
    "NFLX": "Netflix",
    "NKE": "Nike",
    "NVDA": "Nvidia",
    "ORCL": "Oracle",
    "PANW": "Palo Alto Networks",
    "PEP": "PepsiCo",
    "PFE": "Pfizer",
    "PG": "Procter and Gamble",
    "PLTR": "Palantir",
    "QCOM": "Qualcomm",
    "SBUX": "Starbucks",
    "SMCI": "Super Micro",
    "T": "A T and T",
    "TSLA": "Tesla",
    "UBER": "Uber",
    "UNH": "UnitedHealth",
    "UPS": "U P S",
    "V": "Visa",
    "VZ": "Verizon",
    "WFC": "Wells Fargo",
    "WMT": "Walmart",
    "XOM": "Exxon",
}


@dataclass
class Quote:
    """One instrument's move on the session."""

    symbol: str
    name: str
    close: float
    previous_close: float

    @property
    def point_change(self) -> float:
        return self.close - self.previous_close

    @property
    def percent_change(self) -> float:
        if not self.previous_close:
            return 0.0
        return 100.0 * (self.close - self.previous_close) / self.previous_close


@dataclass
class MarketFacts:
    """Everything the script needs about one session.

    Every field past ``session_date`` is optional: a dataset can be missing, a
    symbol can be absent, and the renderer drops the corresponding segment
    rather than inventing a number.
    """

    session_date: date
    indices: list[Quote] = field(default_factory=list)
    gainer: Quote | None = None
    loser: Quote | None = None
    advancers: int = 0
    decliners: int = 0
    rate: Quote | None = None
    crude: Quote | None = None
    crypto: Quote | None = None

    @property
    def breadth_total(self) -> int:
        return self.advancers + self.decliners

    @property
    def is_narrow(self) -> bool:
        """True when the session's gains were carried by a minority of names.

        Backs the "breadth was narrow" line with something real, so the joke
        about calling it broad-based only fires when it is actually earned.
        """
        if self.breadth_total < 20:
            return False
        return self.advancers < 0.45 * self.breadth_total

    @property
    def direction(self) -> str:
        """``up``, ``down`` or ``mixed`` across the tracked indices."""
        if not self.indices:
            return "mixed"
        ups = sum(1 for q in self.indices if q.percent_change > 0.05)
        downs = sum(1 for q in self.indices if q.percent_change < -0.05)
        if ups and not downs:
            return "up"
        if downs and not ups:
            return "down"
        return "mixed"


def latest_changes(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce a long price frame to one row per symbol: close and prior close.

    Symbols with a single observation are dropped — a session move needs two
    points, and a half-known symbol is worse on air than a missing one.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["symbol", "close", "previous_close"])

    frame = df.sort_values("date")
    tail = frame.groupby("symbol", sort=False).tail(2)

    rows = []
    for symbol, part in tail.groupby("symbol", sort=False):
        if len(part) < 2:
            continue
        previous, last = part.iloc[-2], part.iloc[-1]
        rows.append(
            {
                "symbol": symbol,
                "close": float(last["close"]),
                "previous_close": float(previous["close"]),
            }
        )

    return pd.DataFrame(rows, columns=["symbol", "close", "previous_close"])


def _quote(changes: pd.DataFrame, symbol: str, name: str | None = None) -> Quote | None:
    row = changes[changes["symbol"] == symbol]
    if row.empty:
        return None
    row = row.iloc[0]
    return Quote(
        symbol=symbol,
        name=name or INDEX_NAMES.get(symbol) or symbol,
        close=float(row["close"]),
        previous_close=float(row["previous_close"]),
    )


def index_quotes(df: pd.DataFrame, symbols=DEFAULT_INDICES) -> list[Quote]:
    """Quotes for the tracked indices, in the order given."""
    changes = latest_changes(df)
    found = (_quote(changes, symbol) for symbol in symbols)
    return [quote for quote in found if quote is not None]


def company_name(symbol: str, names: dict[str, str] | None = None) -> str:
    """A sayable name for a ticker, falling back to spelling it out."""
    table = names if names is not None else COMPANY_NAMES
    if symbol in table:
        return table[symbol]
    from .spoken import say_ticker

    return say_ticker(symbol)


def movers(
    df: pd.DataFrame,
    names: dict[str, str] | None = None,
    min_price: float = 5.0,
) -> tuple[Quote | None, Quote | None]:
    """The session's biggest gainer and biggest decliner.

    ``min_price`` keeps sub-five-dollar names out of the segment: a stock that
    moved forty percent off a two-dollar base is a data artifact more often
    than it is a story.
    """
    changes = latest_changes(df)
    if changes.empty:
        return None, None

    changes = changes[changes["previous_close"] >= min_price]
    if changes.empty:
        return None, None

    changes = changes.assign(
        pct=100.0
        * (changes["close"] - changes["previous_close"])
        / changes["previous_close"]
    )

    best = changes.loc[changes["pct"].idxmax()]
    worst = changes.loc[changes["pct"].idxmin()]

    def build(row) -> Quote:
        symbol = str(row["symbol"])
        return Quote(
            symbol=symbol,
            name=company_name(symbol, names),
            close=float(row["close"]),
            previous_close=float(row["previous_close"]),
        )

    return build(best), build(worst)


def breadth(df: pd.DataFrame) -> tuple[int, int]:
    """How many names in the frame rose and how many fell."""
    changes = latest_changes(df)
    if changes.empty:
        return 0, 0
    advancing = int((changes["close"] > changes["previous_close"]).sum())
    declining = int((changes["close"] < changes["previous_close"]).sum())
    return advancing, declining


def session_date(df: pd.DataFrame) -> date | None:
    """The most recent date present in a price frame."""
    if df is None or df.empty or "date" not in df.columns:
        return None
    latest = pd.to_datetime(df["date"]).max()
    return None if pd.isna(latest) else latest.date()


def demo_facts(session: date | None = None) -> MarketFacts:
    """A canned session, so the tool runs with no credentials and no network.

    The numbers are the ones from the hand-written reel this template was
    lifted from, which makes ``--demo`` a regression check on the prose as
    much as a smoke test on the plumbing.
    """
    session = session or date(2026, 8, 13)
    return MarketFacts(
        session_date=session,
        indices=[
            Quote("SPX", INDEX_NAMES["SPX"], 5432.10, 5399.72),
            Quote("CCMP", INDEX_NAMES["CCMP"], 17_204.55, 17_051.21),
            Quote("INDU", INDEX_NAMES["INDU"], 39_140.00, 39_000.00),
        ],
        gainer=Quote("NVDA", "Nvidia", 128.40, 112.63),
        loser=Quote("PFE", "Pfizer", 27.31, 35.01),
        advancers=181,
        decliners=319,
        rate=Quote("US10Y", "the ten-year", 4.09, 4.12),
        crude=Quote("CL1", "crude", 71.40, 72.05),
        crypto=Quote("BTC", "Bitcoin", 68_400.00, 65_100.00),
    )


def collect(
    indices=DEFAULT_INDICES,
    universe=("sp500",),
    rate_symbol: str | None = DEFAULT_RATE_SYMBOL,
    crude_symbol: str | None = DEFAULT_CRUDE_SYMBOL,
    crypto_symbol: str | None = DEFAULT_CRYPTO_SYMBOL,
    names: dict[str, str] | None = None,
) -> MarketFacts:
    """Load a session from the datasets and reduce it to :class:`MarketFacts`.

    The only networked function in this package. Each block is independent —
    a dataset that fails to load costs you its segment, not the broadcast.
    """
    import pwb_toolbox.datasets as pwb_ds

    def _safe(loader, label):
        try:
            return loader()
        except Exception as exc:  # noqa: BLE001 - one dead feed is not fatal
            print(f"warning: skipping {label} ({exc})")
            return None

    df_indices = _safe(
        lambda: pwb_ds.load_dataset("Indices-Daily-Price", list(indices)),
        "indices",
    )
    df_stocks = _safe(
        lambda: pwb_ds.load_dataset("Stocks-Daily-Price", list(universe)),
        "stocks",
    )

    facts = MarketFacts(session_date=date.today())

    if df_indices is not None and not df_indices.empty:
        facts.indices = index_quotes(df_indices, indices)
        found = session_date(df_indices)
        if found is not None:
            facts.session_date = found

    if df_stocks is not None and not df_stocks.empty:
        facts.gainer, facts.loser = movers(df_stocks, names)
        facts.advancers, facts.decliners = breadth(df_stocks)

    if rate_symbol:
        df_rate = _safe(
            lambda: pwb_ds.load_dataset(
                "Bonds-Daily-Price", [rate_symbol], rate_to_price=False
            ),
            "rates",
        )
        if df_rate is not None and not df_rate.empty:
            facts.rate = _quote(latest_changes(df_rate), rate_symbol, "the ten-year")

    if crude_symbol:
        df_crude = _safe(
            lambda: pwb_ds.load_dataset("Commodities-Daily-Price", [crude_symbol]),
            "commodities",
        )
        if df_crude is not None and not df_crude.empty:
            facts.crude = _quote(latest_changes(df_crude), crude_symbol, "crude")

    if crypto_symbol:
        df_crypto = _safe(
            lambda: pwb_ds.load_dataset(
                "Cryptocurrencies-Daily-Price", [crypto_symbol]
            ),
            "crypto",
        )
        if df_crypto is not None and not df_crypto.empty:
            facts.crypto = _quote(latest_changes(df_crypto), crypto_symbol, "Bitcoin")

    return facts
