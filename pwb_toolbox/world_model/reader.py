"""Reader of the World Model: ``resolve`` and ``get_graph`` at a date, point-in-time."""

from __future__ import annotations

import os
import warnings

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds

from . import _pit
from ._source import (
    EDGES_PREFIX,
    ENTITIES,
    IDENTIFIERS,
    LOCAL_DIR_ENV,
    HubSource,
    LocalSource,
    WorldModelNotAvailable,
    scan,
)

#: Relation vocabulary of the contract (§4), copied here on purpose: the
#: reader checks a caller's spelling without importing the producer's code.
RELATIONS = frozenset({
    "io_flow", "customer_of", "supplier_to", "geo_exposure", "text_similar",
    "tech_similar", "common_owner", "port_exposure", "issuer_of", "in_sector",
})
#: Relations never stored: ``supplier_to`` is ``customer_of`` reversed;
#: ``in_sector`` comes from the Sectors table.
DERIVED = {"supplier_to": "customer_of"}
NOT_READ_HERE = {"in_sector"}

IDENTIFIER_KEYS = ["scheme", "value"]
ENTITY_KEYS = ["entity_id"]
EDGE_KEYS = ["src", "dst", "relation", "method"]
EDGE_COLUMNS = [
    "src", "dst", "relation", "weight", "sign", "valid_from", "valid_to", "known_at",
    "source", "source_doc", "confidence", "method", "evidence",
]
IDENTIFIER_COLUMNS = [
    "entity_id", "scheme", "value", "valid_from", "valid_to", "known_at", "source", "confidence", "vintage",
]
ENTITY_COLUMNS = [
    "entity_id", "entity_type", "name", "country", "valid_from", "valid_to", "known_at",
    "source", "source_doc", "vintage",
]
DETAIL_COLUMNS = ["cik", "name", "source", "confidence", "valid_from", "valid_to", "known_at"]


def _known_filter(cutoff) -> ds.Expression:
    return pc.field("known_at") <= pa.scalar(pd.Timestamp(cutoff).to_pydatetime(),
                                            type=pa.timestamp("us", tz="UTC"))


def _frame(table: pa.Table | None, columns: list[str]) -> pd.DataFrame:
    if table is None or table.num_rows == 0:
        return _pit.typed(pd.DataFrame({c: pd.Series(dtype="object") for c in columns}))
    return _pit.typed(table.to_pandas(date_as_object=False))


class WorldModel:
    """Point-in-time reader of the World Model tables.

    Parameters
    ----------
    revision : str or dict, optional
        Hub commit to read, for every table (``str``) or per table
        (``{"WorldModel-Identifiers": "<sha>"}``). A backtest is reproducible
        from ``(as_of, method, revision)``. Default: the current revision.
    local_dir : str, optional
        Read a local build instead of the Hub: a directory holding one
        sub-directory per table. Default: ``$PWB_WORLD_MODEL_DIR`` if set.
    tables : dict, optional
        Table name -> directory, for local tables kept elsewhere.
    token : str, optional
        Hub token; default ``$HF_ACCESS_TOKEN``, else the logged-in one. The
        tables are private.

    Every method takes an ``as_of``: nothing published after it is read
    (``known_at <= as_of``), and the intervals are tested at its date. See
    :func:`pwb_toolbox.world_model.resolve` for how a date is turned into a
    knowledge cutoff.
    """

    def __init__(self, revision=None, local_dir=None, tables=None, token=None):
        local_dir = local_dir if local_dir is not None else os.getenv(LOCAL_DIR_ENV)
        if local_dir or tables:
            if revision is not None:
                raise ValueError("revision pins a Hub read; a local build has none")
            self.source = LocalSource(local_dir, tables)
        else:
            self.source = HubSource(revision=revision, token=token)

    # ------------------------------------------------------------------
    # Raw reads
    # ------------------------------------------------------------------

    def _read(self, table: str, cutoff, filter=None, columns=None) -> pd.DataFrame:
        cutoff = pd.Timestamp(cutoff)
        expression = _known_filter(cutoff)
        if filter is not None:
            expression = expression & filter
        files = self.source.files(table, max_year=cutoff.year)
        if table == IDENTIFIERS:
            empty = IDENTIFIER_COLUMNS
        elif table == ENTITIES:
            empty = ENTITY_COLUMNS
        else:
            empty = EDGE_COLUMNS
        return _frame(scan(files, columns=columns, filter=expression), columns or empty)

    # ------------------------------------------------------------------
    # Views at one date
    # ------------------------------------------------------------------

    def identifiers(self, as_of, *, scheme=None, values=None, entity_ids=None, date=None) -> pd.DataFrame:
        """The Identifiers rows valid at ``as_of`` as they were known then.

        ``date`` (default: the date of ``as_of``) is the world date the
        intervals are tested on; ``as_of`` stays the knowledge cutoff.
        """
        cutoff, day = _pit.as_of_point(as_of)
        if date is not None:
            day = _pit.world_dates([date]).iloc[0]
        expression = None
        if scheme is not None:
            expression = pc.field("scheme") == scheme
        if values is not None:
            if scheme is None:
                raise ValueError("values= needs a scheme=")
            normalized = _pit.normalize_values(pd.Series(list(values)), scheme)
            expression = expression & pc.field("value").isin(normalized.dropna().unique().tolist())
        if entity_ids is not None:
            clause = pc.field("entity_id").isin(list(entity_ids))
            expression = clause if expression is None else expression & clause
        rows = self._read(IDENTIFIERS, cutoff, expression)
        return _pit.view(rows, IDENTIFIER_KEYS, cutoff, day).reset_index(drop=True)

    def entities(self, as_of, *, entity_ids=None, date=None) -> pd.DataFrame:
        """The Entities versions valid at ``as_of`` as they were known then."""
        cutoff, day = _pit.as_of_point(as_of)
        if date is not None:
            day = _pit.world_dates([date]).iloc[0]
        expression = None if entity_ids is None else pc.field("entity_id").isin(list(entity_ids))
        rows = self._read(ENTITIES, cutoff, expression)
        return _pit.view(rows, ENTITY_KEYS, cutoff, day).reset_index(drop=True)

    # ------------------------------------------------------------------
    # resolve
    # ------------------------------------------------------------------

    def resolve(self, ticker, as_of, scheme: str = "ticker_us", *, details: bool = False, date=None):
        """``entity_id`` of ``ticker`` at ``as_of``, or ``None`` when it does not resolve.

        With ``details=True``, a dict (``entity_id``, ``cik``, ``name``,
        ``source``, ``confidence``, ``valid_from``, ``valid_to``, ``known_at``)
        or ``None``. Nothing is guessed: no row, no answer.
        """
        cutoff, day = _pit.as_of_point(as_of)
        if date is not None:
            day = _pit.world_dates([date]).iloc[0]
        queries = pd.DataFrame({
            "ticker": [ticker],
            "_cutoff": pd.Series([cutoff], dtype=_pit._KNOWN_DTYPE),
            "_date": pd.Series([day], dtype=_pit._DATE_DTYPE),
        })
        out = self._resolve_queries(queries, scheme, details)
        row = out.iloc[0]
        if pd.isna(row["entity_id"]):
            return None
        if not details:
            return row["entity_id"]
        found = {c: (None if pd.isna(row[c]) else row[c]) for c in ["entity_id"] + DETAIL_COLUMNS}
        for column in ("valid_from", "valid_to"):
            if found[column] is not None:
                found[column] = pd.Timestamp(found[column]).date()
        if found["confidence"] is not None:
            found["confidence"] = float(found["confidence"])
        return found

    def resolve_panel(self, tickers, dates, *, pairs: bool = False, scheme: str = "ticker_us",
                      as_of=None, details: bool = False) -> pd.DataFrame:
        """Vectorised :meth:`resolve` over a panel: one row per ``(ticker, date)``.

        By default every ticker is resolved at every date (the cross product);
        ``pairs=True`` zips two sequences of equal length instead. Each date is
        its own knowledge cutoff -- what a backtest needs -- unless ``as_of``
        sets one cutoff for all rows (then ``dates`` are only world dates).

        Columns: ``ticker``, ``date``, ``entity_id`` (missing when not
        resolved), and with ``details=True`` those of :meth:`resolve`. The
        cost is two sorts and two as-of joins, linear in rows and queries.
        """
        tickers = list(pd.Series(tickers, dtype="object"))
        dates = list(pd.Series(dates, dtype="object")) if not isinstance(dates, pd.DatetimeIndex) else list(dates)
        if pairs and len(tickers) != len(dates):
            raise ValueError(f"pairs=True needs as many dates as tickers ({len(tickers)} != {len(dates)})")
        if not tickers or not dates:
            columns = ["ticker", "date", "entity_id"] + (DETAIL_COLUMNS if details else [])
            return pd.DataFrame(columns=columns)
        # Dates are converted once each, before the cross product repeats them.
        if as_of is None:
            cutoffs, days = _pit.as_of_points(dates)
        else:
            cutoff, _ = _pit.as_of_point(as_of)
            days = _pit.world_dates(dates)
            cutoffs = pd.Series([cutoff] * len(days), dtype=_pit._KNOWN_DTYPE)
        if pairs:
            query_tickers = tickers
        else:
            query_tickers = np.repeat(np.array(tickers, dtype="object"), len(dates)).tolist()
            take = np.tile(np.arange(len(dates)), len(tickers))
            cutoffs = cutoffs.iloc[take].reset_index(drop=True)
            days = days.iloc[take].reset_index(drop=True)
        queries = pd.DataFrame({"ticker": query_tickers, "_cutoff": cutoffs, "_date": days})
        out = self._resolve_queries(queries, scheme, details)
        out.insert(1, "date", days)
        return out

    def _resolve_queries(self, queries: pd.DataFrame, scheme: str, details: bool) -> pd.DataFrame:
        queries = queries.reset_index(drop=True)
        queries["scheme"] = scheme
        queries["value"] = _pit.normalize_values(queries["ticker"], scheme).astype("object")
        wanted = queries["value"].dropna().unique().tolist()
        max_cutoff = queries["_cutoff"].max()
        rows = self._read(
            IDENTIFIERS, max_cutoff,
            (pc.field("scheme") == scheme) & pc.field("value").isin(wanted),
        )
        rows = _pit.prepare(rows, IDENTIFIER_KEYS)
        hit = _pit.match(rows, IDENTIFIER_KEYS, queries.dropna(subset=["value"]))
        position = pd.Series(-1, index=queries.index, dtype="int64")
        position.loc[hit.index] = hit.to_numpy()
        resolved = position >= 0
        out = pd.DataFrame({"ticker": queries["ticker"].to_numpy()})
        out["entity_id"] = pd.Series(pd.NA, index=queries.index, dtype="object")
        if resolved.any():
            picked = rows.iloc[position[resolved].to_numpy()]
            out.loc[resolved, "entity_id"] = picked["entity_id"].to_numpy()
        if details:
            out = self._details(out, queries, rows, position, resolved)
        return out

    def _details(self, out, queries, rows, position, resolved) -> pd.DataFrame:
        for column in DETAIL_COLUMNS:
            out[column] = pd.Series(np.nan, index=out.index, dtype="object")
        if not resolved.any():
            return self._typed_details(out)
        picked = rows.iloc[position[resolved].to_numpy()]
        for column in ("source", "confidence", "valid_from", "valid_to", "known_at"):
            out.loc[resolved, column] = picked[column].to_numpy()

        matched = pd.DataFrame({
            "_query": np.flatnonzero(resolved.to_numpy()),
            "entity_id": out.loc[resolved, "entity_id"].to_numpy(),
            "_cutoff": queries.loc[resolved, "_cutoff"].to_numpy(),
            "_date": queries.loc[resolved, "_date"].to_numpy(),
        })
        max_cutoff = matched["_cutoff"].max()
        entity_ids = matched["entity_id"].unique().tolist()

        # CIK: the cik identifiers of the matched entities, read with the same rule.
        cik_rows = self._read(
            IDENTIFIERS, max_cutoff,
            (pc.field("scheme") == "cik") & pc.field("entity_id").isin(entity_ids),
        )
        if not cik_rows.empty:
            candidates = matched.merge(
                cik_rows[["entity_id", "value"]].drop_duplicates(), on="entity_id"
            )
            candidates["scheme"] = "cik"
            prepared = _pit.prepare(cik_rows, IDENTIFIER_KEYS)
            hit = _pit.match(prepared, IDENTIFIER_KEYS, candidates)
            candidates["_row"] = hit.to_numpy()
            candidates = candidates[candidates["_row"] >= 0]
            same = prepared["entity_id"].to_numpy()[candidates["_row"].to_numpy()] == candidates["entity_id"].to_numpy()
            candidates = candidates[same].sort_values(["_query", "value"]).drop_duplicates("_query")
            out.loc[candidates["_query"].to_numpy(), "cik"] = candidates["value"].to_numpy()

        # Name: the Entities version valid then, as known then.
        try:
            entity_rows = self._read(ENTITIES, max_cutoff, pc.field("entity_id").isin(entity_ids))
        except WorldModelNotAvailable as exc:
            warnings.warn(f"names left missing: {exc}", stacklevel=4)
            return self._typed_details(out)
        prepared = _pit.prepare(entity_rows, ENTITY_KEYS)
        hit = _pit.match(prepared, ENTITY_KEYS, matched)
        found = hit.to_numpy() >= 0
        out.loc[matched["_query"].to_numpy()[found], "name"] = prepared["name"].to_numpy()[hit.to_numpy()[found]]
        return self._typed_details(out)

    @staticmethod
    def _typed_details(out: pd.DataFrame) -> pd.DataFrame:
        return out.astype({"confidence": "float64"}).assign(
            valid_from=lambda f: pd.to_datetime(f["valid_from"]),
            valid_to=lambda f: pd.to_datetime(f["valid_to"]),
            known_at=lambda f: pd.to_datetime(f["known_at"], utc=True),
        )

    # ------------------------------------------------------------------
    # get_graph
    # ------------------------------------------------------------------

    def edge_families(self) -> list[str]:
        """Names of the ``WorldModel-Edges-<Family>`` datasets this source holds."""
        return self.source.edge_families()

    def get_graph(self, as_of, relations=None, method=None, *, date=None, families=None) -> pd.DataFrame:
        """Edges of the graph as it was knowable at ``as_of``.

        Parameters
        ----------
        as_of : date-like
            Knowledge cutoff (``known_at <= as_of``) and, unless ``date`` is
            given, the date the intervals ``[valid_from, valid_to)`` are tested on.
        relations : str or list of str, optional
            Relations to return (§4 vocabulary); default every stored one.
            ``supplier_to`` is derived from ``customer_of`` (``src``/``dst``
            swapped); ``in_sector`` is not served by this reader.
        method : str, list of str, ``"latest"`` or ``"all"``, optional
            Extractor(s) to read. Default (``None`` / ``"latest"``): for each
            relation, the method whose latest publication visible at ``as_of``
            is the most recent -- a later re-extraction replaces an earlier
            one, never mixes with it. ``"all"`` keeps every method side by side.
        date : date-like, optional
            World date for the interval test, when it differs from ``as_of``.
        families : list of str, optional
            ``WorldModel-Edges-<Family>`` datasets to read; default all of them.

        For each edge key ``(src, dst, relation, method)``, the rows of its
        latest publication with ``known_at <= as_of`` are kept, then those
        whose interval holds the date. Raises :class:`WorldModelNotAvailable`
        when no Edges dataset exists.
        """
        cutoff, day = _pit.as_of_point(as_of)
        if date is not None:
            day = _pit.world_dates([date]).iloc[0]
        requested = self._relations(relations)
        stored = None if requested is None else sorted({DERIVED.get(r, r) for r in requested})

        if families is None:
            families = self.edge_families()
        families = [f if f.startswith(EDGES_PREFIX) else EDGES_PREFIX + f for f in families]
        if not families:
            raise WorldModelNotAvailable(
                f"no {EDGES_PREFIX}<Family> dataset is published yet in "
                f"{self.source.describe()}: the graph has no edges to return"
            )
        expression = None if stored is None else pc.field("relation").isin(stored)
        parts = [self._read(family, cutoff, expression) for family in families]
        parts = [p for p in parts if not p.empty]
        if not parts:
            return self._empty_edges()
        edges = pd.concat(parts, ignore_index=True)

        if isinstance(method, str) and method not in ("latest", "all"):
            edges = edges[edges["method"] == method]
        elif isinstance(method, (list, tuple, set)):
            edges = edges[edges["method"].isin(list(method))]

        edges = _pit.latest_publication(edges, EDGE_KEYS, cutoff)
        if method is None or method == "latest":
            edges = self._latest_method(edges)
        edges = _pit.valid_on(edges, day)

        if requested is not None:
            frames = []
            for relation in requested:
                if relation in DERIVED:
                    reverse = edges[edges["relation"] == DERIVED[relation]].copy()
                    reverse[["src", "dst"]] = reverse[["dst", "src"]].to_numpy()
                    reverse["relation"] = relation
                    frames.append(reverse)
                else:
                    frames.append(edges[edges["relation"] == relation])
            edges = pd.concat(frames, ignore_index=True) if frames else edges.iloc[0:0]
        columns = [c for c in EDGE_COLUMNS if c in edges.columns]
        return edges[columns].sort_values(["relation", "src", "dst", "method"]).reset_index(drop=True)

    @staticmethod
    def _relations(relations):
        if relations is None:
            return None
        if isinstance(relations, str):
            relations = [relations]
        relations = list(dict.fromkeys(relations))
        unknown = sorted(set(relations) - RELATIONS)
        if unknown:
            raise ValueError(f"unknown relation(s) {unknown}; the vocabulary is {sorted(RELATIONS)}")
        refused = sorted(set(relations) & NOT_READ_HERE)
        if refused:
            raise NotImplementedError(
                f"{refused} are derived from WorldModel-Sectors, which this reader does not serve yet"
            )
        return relations

    @staticmethod
    def _latest_method(edges: pd.DataFrame) -> pd.DataFrame:
        if edges.empty:
            return edges
        per_method = edges.groupby(["relation", "method"], as_index=False)["known_at"].max()
        per_method = per_method.sort_values(["relation", "known_at", "method"])
        chosen = per_method.drop_duplicates("relation", keep="last")[["relation", "method"]]
        return edges.merge(chosen, on=["relation", "method"])

    @staticmethod
    def _empty_edges() -> pd.DataFrame:
        return _pit.typed(pd.DataFrame({c: pd.Series(dtype="object") for c in EDGE_COLUMNS}))


_MODELS: dict = {}


def _model(revision=None, local_dir=None) -> WorldModel:
    key = (repr(revision), local_dir if local_dir is not None else os.getenv(LOCAL_DIR_ENV))
    if key not in _MODELS:
        _MODELS[key] = WorldModel(revision=revision, local_dir=local_dir)
    return _MODELS[key]


def resolve(ticker, as_of, scheme: str = "ticker_us", *, details: bool = False, date=None,
            revision=None, local_dir=None):
    """``entity_id`` of an identifier at ``as_of``, point-in-time; ``None`` if unresolved.

    ``as_of`` is both the knowledge cutoff and the date the mapping must hold:

    * a date or a naive midnight timestamp means the end of that day, New York
      time (23:59:59.999999) -- a backtest deciding on day T's close may use
      what was published during T;
    * a naive timestamp with a time is that New York instant; a timezone-aware
      one is that instant.

    Rows published after the cutoff are never read. ``date`` tests the
    intervals on another day than ``as_of`` (e.g. today's knowledge of who held
    a ticker in 2010 -- not point-in-time, for research only).

    ``scheme`` is any identifier scheme of the table (``ticker_us``, ``cik``,
    ``cusip``, ``figi``...). ``details=True`` returns a dict with ``cik``,
    ``name``, ``source``, ``confidence`` and the matched interval.

    >>> resolve("TGX", "2012-06-01")                    # doctest: +SKIP
    """
    return _model(revision, local_dir).resolve(ticker, as_of, scheme, details=details, date=date)


def resolve_panel(tickers, dates, *, pairs: bool = False, scheme: str = "ticker_us", as_of=None,
                  details: bool = False, revision=None, local_dir=None) -> pd.DataFrame:
    """:func:`resolve` over a panel of tickers x dates, in one vectorised pass.

    See :meth:`WorldModel.resolve_panel`. Each date is its own knowledge
    cutoff, so the panel is point-in-time row by row.
    """
    return _model(revision, local_dir).resolve_panel(
        tickers, dates, pairs=pairs, scheme=scheme, as_of=as_of, details=details
    )


def get_graph(as_of, relations=None, method=None, *, date=None, families=None,
              revision=None, local_dir=None) -> pd.DataFrame:
    """Edges knowable at ``as_of`` and true on its date. See :meth:`WorldModel.get_graph`."""
    return _model(revision, local_dir).get_graph(
        as_of, relations=relations, method=method, date=date, families=families
    )


__all__ = ["WorldModel", "WorldModelNotAvailable", "get_graph", "resolve", "resolve_panel"]
