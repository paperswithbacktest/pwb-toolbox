"""The World Model reader on synthetic tables: the point-in-time rule, case by case.

Every fixture is written to Parquet with the contract's Arrow types
(``date32`` intervals, ``timestamp[us, UTC]`` publication), sharded by year of
``known_at`` like the published tables, and read through the local source.
"""

import datetime as dt
import os
import random
import tempfile
import unittest

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from pwb_toolbox.world_model import WorldModel, WorldModelNotAvailable
from pwb_toolbox.world_model import _pit

IDENTIFIERS_SCHEMA = pa.schema([
    ("entity_id", pa.string()), ("scheme", pa.string()), ("value", pa.string()),
    ("valid_from", pa.date32()), ("valid_to", pa.date32()),
    ("known_at", pa.timestamp("us", tz="UTC")), ("source", pa.string()),
    ("confidence", pa.float32()), ("vintage", pa.string()),
])
ENTITIES_SCHEMA = pa.schema([
    ("entity_id", pa.string()), ("entity_type", pa.string()), ("name", pa.string()),
    ("country", pa.string()), ("valid_from", pa.date32()), ("valid_to", pa.date32()),
    ("known_at", pa.timestamp("us", tz="UTC")), ("source", pa.string()),
    ("source_doc", pa.string()), ("vintage", pa.string()),
])
EDGES_SCHEMA = pa.schema([
    ("src", pa.string()), ("dst", pa.string()), ("relation", pa.string()),
    ("weight", pa.float32()), ("sign", pa.int8()),
    ("valid_from", pa.date32()), ("valid_to", pa.date32()),
    ("known_at", pa.timestamp("us", tz="UTC")), ("source", pa.string()),
    ("source_doc", pa.string()), ("confidence", pa.float32()), ("method", pa.string()),
    ("evidence", pa.string()),
])


def d(text):
    return None if text is None else dt.date.fromisoformat(text)


def utc(text):
    """A publication instant; a bare date is noon UTC (mid-session in New York)."""
    if len(text) == 10:
        text += "T12:00:00"
    return dt.datetime.fromisoformat(text).replace(tzinfo=dt.timezone.utc)


def ident(entity, value, start, end, known, scheme="ticker_us", vintage="v1", source="filing", confidence=1.0):
    return dict(entity_id=entity, scheme=scheme, value=value, valid_from=d(start), valid_to=d(end),
                known_at=utc(known), source=source, confidence=confidence, vintage=vintage)


def entity(entity_id, name, start, end, known, vintage="v1"):
    return dict(entity_id=entity_id, entity_type="company", name=name, country="US",
                valid_from=d(start), valid_to=d(end), known_at=utc(known), source="sec_header",
                source_doc="0000000000-00-000000", vintage=vintage)


def edge(src, dst, relation, start, end, known, method="xbrl_v1", weight=0.1):
    return dict(src=src, dst=dst, relation=relation, weight=weight, sign=None,
                valid_from=d(start), valid_to=d(end), known_at=utc(known), source="test",
                source_doc="doc", confidence=1.0, method=method, evidence=None)


def write_table(directory, rows, schema):
    """One shard per year of ``known_at``, named like the published shards."""
    os.makedirs(directory, exist_ok=True)
    by_year = {}
    for row in rows:
        by_year.setdefault(row["known_at"].year, []).append(row)
    for year, part in by_year.items():
        pq.write_table(pa.Table.from_pylist(part, schema=schema),
                       os.path.join(directory, f"train-{year}.parquet"))
    return directory


class Fixture(unittest.TestCase):
    identifiers = []
    entities = []

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        if self.identifiers:
            write_table(os.path.join(self.root, "WorldModel-Identifiers"), self.identifiers, IDENTIFIERS_SCHEMA)
        if self.entities:
            write_table(os.path.join(self.root, "WorldModel-Entities"), self.entities, ENTITIES_SCHEMA)
        self.wm = WorldModel(local_dir=self.root)

    def tearDown(self):
        self._tmp.cleanup()


class HalfOpenInterval(Fixture):
    identifiers = [ident("E_A", "AAA", "2020-01-01", "2020-06-01", "2019-12-01")]

    def test_first_day_is_in(self):
        self.assertEqual(self.wm.resolve("AAA", "2020-01-01"), "E_A")

    def test_last_day_before_valid_to_is_in(self):
        self.assertEqual(self.wm.resolve("AAA", "2020-05-31"), "E_A")

    def test_valid_to_itself_is_out(self):
        self.assertIsNone(self.wm.resolve("AAA", "2020-06-01"))

    def test_day_before_valid_from_is_out(self):
        self.assertIsNone(self.wm.resolve("AAA", "2019-12-31"))

    def test_lower_case_ticker_is_normalized(self):
        self.assertEqual(self.wm.resolve(" aaa ", "2020-03-02"), "E_A")


class SeveralVintages(Fixture):
    # Two generations of the reference table carry the same publication; the
    # newer one (v2) re-emits it with a corrected interval. v1 must not leak in.
    identifiers = [
        ident("E_A", "VVV", "2010-01-01", "2012-01-01", "2010-01-05", vintage="2026-11-01"),
        ident("E_A", "VVV", "2010-01-01", "2011-01-01", "2010-01-05", vintage="2026-11-22"),
        ident("E_A", "VVV", "2010-01-01", "2011-01-01", "2010-01-05", vintage="2026-11-22"),
    ]

    def test_latest_vintage_wins_for_the_same_publication(self):
        self.assertEqual(self.wm.resolve("VVV", "2010-06-01"), "E_A")
        self.assertIsNone(self.wm.resolve("VVV", "2011-06-01"))

    def test_view_returns_one_row_per_interval(self):
        view = self.wm.identifiers("2010-06-01", scheme="ticker_us", values=["VVV"])
        self.assertEqual(view["vintage"].unique().tolist(), ["2026-11-22"])

    def test_panel_agrees(self):
        panel = self.wm.resolve_panel(["VVV"], ["2010-06-01", "2011-06-01"])
        self.assertEqual(panel["entity_id"].tolist()[0], "E_A")
        self.assertTrue(pd.isna(panel["entity_id"].tolist()[1]))


class ClosedByANewRow(Fixture):
    # Open interval published in 2020; the closing row (valid_to set) is a new
    # row published on 2021-03-05. Old rows stay in the table.
    identifiers = [
        ident("E_A", "OPN", "2020-01-02", None, "2020-01-10"),
        ident("E_A", "OPN", "2020-01-02", "2021-03-01", "2021-03-05"),
    ]

    def test_open_before_the_closing_row_is_known(self):
        self.assertEqual(self.wm.resolve("OPN", "2021-03-03"), "E_A")

    def test_closed_once_the_closing_row_is_known(self):
        self.assertIsNone(self.wm.resolve("OPN", "2021-03-10"))
        self.assertEqual(self.wm.resolve("OPN", "2021-03-10", date="2021-02-26"), "E_A")

    def test_open_interval_runs_forward(self):
        self.assertEqual(self.wm.resolve("OPN", "2020-12-31"), "E_A")


class ReusedTicker(Fixture):
    # XYZ is company A until 2005, then nobody, then company B from 2010.
    identifiers = [
        ident("E_A", "XYZ", "2000-01-03", "2005-07-01", "2000-01-03"),
        ident("E_A", "XYZ", "2000-01-03", "2005-07-01", "2005-07-05"),
        ident("E_B", "XYZ", "2010-02-01", None, "2010-02-01"),
        ident("E_A", "XYZ", "2000-01-03", "2005-07-01", "2010-02-01"),
    ]

    def test_each_company_at_its_own_dates(self):
        self.assertEqual(self.wm.resolve("XYZ", "2003-05-01"), "E_A")
        self.assertIsNone(self.wm.resolve("XYZ", "2007-05-01"))
        self.assertEqual(self.wm.resolve("XYZ", "2012-05-01"), "E_B")

    def test_today_knowledge_of_an_old_date(self):
        self.assertEqual(self.wm.resolve("XYZ", "2026-11-23", date="2003-05-01"), "E_A")


class PublishedAfterT(Fixture):
    # ABC was mapped to A in a 2015 publication. A correction published on
    # 2016-01-01 says it was B all along. A backtest at 2015-12-31 must not see it.
    base = [ident("E_A", "ABC", "2014-01-01", None, "2015-06-01")]
    correction = [ident("E_B", "ABC", "2014-01-01", None, "2016-01-01")]
    identifiers = base + correction

    def test_correction_after_t_does_not_change_t(self):
        with_correction = self.wm.resolve("ABC", "2015-12-31")
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        write_table(os.path.join(other.name, "WorldModel-Identifiers"), self.base, IDENTIFIERS_SCHEMA)
        without_correction = WorldModel(local_dir=other.name).resolve("ABC", "2015-12-31")
        self.assertEqual(with_correction, "E_A")
        self.assertEqual(with_correction, without_correction)

    def test_correction_is_seen_once_published(self):
        self.assertEqual(self.wm.resolve("ABC", "2016-01-04"), "E_B")
        # even for an earlier world date: today's knowledge of 2014
        self.assertEqual(self.wm.resolve("ABC", "2016-01-04", date="2014-06-02"), "E_B")

    def test_not_visible_before_its_first_publication(self):
        self.assertIsNone(self.wm.resolve("ABC", "2015-05-29"))

    def test_panel_is_point_in_time_row_by_row(self):
        panel = self.wm.resolve_panel(["ABC"], ["2015-05-29", "2015-12-31", "2016-01-04"])
        self.assertEqual(panel["entity_id"].fillna("-").tolist(), ["-", "E_A", "E_B"])

    def test_future_shards_are_never_opened(self):
        # A shard for a year after the cutoff is not read at all: make it unreadable.
        path = os.path.join(self.root, "WorldModel-Identifiers", "train-2030.parquet")
        with open(path, "wb") as handle:
            handle.write(b"not parquet")
        self.assertEqual(self.wm.resolve("ABC", "2015-12-31"), "E_A")


class KnowledgeCutoffWithinTheDay(Fixture):
    identifiers = [
        # 16:00 New York on 2020-03-02
        ident("E_A", "AFT", "2020-03-02", None, "2020-03-02T21:00:00"),
        # 22:00 New York on 2020-03-02 (03:00 UTC the next day)
        ident("E_B", "LATE", "2020-03-02", None, "2020-03-03T03:00:00"),
        # 00:00 New York on 2020-03-03
        ident("E_C", "NEXT", "2020-03-02", None, "2020-03-03T05:00:00"),
    ]

    def test_a_date_means_the_end_of_that_day_in_new_york(self):
        self.assertEqual(self.wm.resolve("AFT", "2020-03-02"), "E_A")
        self.assertEqual(self.wm.resolve("LATE", "2020-03-02"), "E_B")
        self.assertIsNone(self.wm.resolve("NEXT", "2020-03-02"))
        self.assertEqual(self.wm.resolve("NEXT", dt.date(2020, 3, 3)), "E_C")

    def test_an_aware_timestamp_is_exact(self):
        self.assertIsNone(self.wm.resolve("AFT", pd.Timestamp("2020-03-02 20:59", tz="UTC")))
        self.assertEqual(self.wm.resolve("AFT", pd.Timestamp("2020-03-02 21:00", tz="UTC")), "E_A")

    def test_a_naive_time_is_new_york(self):
        self.assertIsNone(self.wm.resolve("AFT", "2020-03-02 15:59"))
        self.assertEqual(self.wm.resolve("AFT", "2020-03-02 16:00"), "E_A")


class Unresolved(Fixture):
    identifiers = [ident("E_A", "AAA", "2020-01-01", None, "2020-01-01")]

    def test_unknown_ticker(self):
        self.assertIsNone(self.wm.resolve("NOPE", "2021-01-04"))
        self.assertIsNone(self.wm.resolve("NOPE", "2021-01-04", details=True))

    def test_other_scheme_does_not_leak(self):
        self.assertIsNone(self.wm.resolve("AAA", "2021-01-04", scheme="cusip"))

    def test_before_any_shard(self):
        self.assertIsNone(self.wm.resolve("AAA", "1995-01-03"))

    def test_panel_marks_missing(self):
        with self.assertWarns(UserWarning):
            panel = self.wm.resolve_panel(["AAA", "NOPE"], ["2021-01-04"], details=True)
        self.assertEqual(panel["entity_id"].tolist()[0], "E_A")
        self.assertTrue(pd.isna(panel["entity_id"].tolist()[1]))
        self.assertTrue(pd.isna(panel["name"].tolist()[1]))
        # no Entities table here: the name stays missing, and that is said
        self.assertTrue(pd.isna(panel["name"].tolist()[0]))

    def test_missing_table_is_said(self):
        with self.assertRaises(WorldModelNotAvailable):
            WorldModel(local_dir=self.root).entities("2021-01-04")


class Details(Fixture):
    identifiers = [
        ident("E_F", "FB", "2012-05-18", "2022-06-09", "2012-05-18"),
        ident("E_F", "META", "2022-06-09", None, "2022-06-09"),
        ident("E_F", "0001326801", "1990-01-01", None, "2004-07-29", scheme="cik", source="sec_header"),
        ident("E_X", "FB", "2025-06-26", None, "2025-06-26", confidence=0.8, source="listing_name"),
    ]
    entities = [
        entity("E_F", "Facebook Inc", "2004-07-29", None, "2004-07-29"),
        entity("E_F", "Facebook Inc", "2004-07-29", "2021-10-28", "2021-10-28"),
        entity("E_F", "Meta Platforms Inc", "2021-10-28", None, "2021-10-28"),
    ]

    def test_cik_and_name_as_of_then(self):
        found = self.wm.resolve("FB", "2015-01-02", details=True)
        self.assertEqual(found["entity_id"], "E_F")
        self.assertEqual(found["cik"], "0001326801")
        self.assertEqual(found["name"], "Facebook Inc")
        self.assertEqual(found["valid_from"], dt.date(2012, 5, 18))
        self.assertEqual(found["source"], "filing")

    def test_name_changes_over_time(self):
        self.assertEqual(self.wm.resolve("META", "2023-01-03", details=True)["name"], "Meta Platforms Inc")

    def test_resolve_by_cik(self):
        self.assertEqual(self.wm.resolve("0001326801", "2015-01-02", scheme="cik"), "E_F")
        self.assertEqual(self.wm.resolve(1326801, "2015-01-02", scheme="cik"), "E_F")

    def test_reused_ticker_keeps_its_own_confidence(self):
        found = self.wm.resolve("FB", "2026-01-02", details=True)
        self.assertEqual(found["entity_id"], "E_X")
        self.assertAlmostEqual(found["confidence"], 0.8, places=6)
        self.assertIsNone(found["name"])  # no Entities row for E_X: never invented


class OverlappingIntervalsOfOneEntity(Fixture):
    # One publication with a long interval and a short one inside it.
    identifiers = [
        ident("E_A", "OVL", "2000-01-03", "2010-01-04", "2011-01-03"),
        ident("E_A", "OVL", "2004-01-02", "2004-06-01", "2011-01-03"),
    ]

    def test_long_interval_still_covers_after_the_short_one(self):
        self.assertEqual(self.wm.resolve("OVL", "2026-01-02", date="2008-01-02"), "E_A")
        panel = self.wm.resolve_panel(["OVL"], ["2008-01-02"], as_of="2026-01-02")
        self.assertEqual(panel["entity_id"].tolist(), ["E_A"])


class PanelMatchesTheRule(unittest.TestCase):
    """The vectorised panel equals the contract's rule applied query by query."""

    def test_random_tables(self):
        rng = random.Random(7)
        rows = []
        tickers = [f"T{i}" for i in range(12)]
        for ticker in tickers:
            for _ in range(rng.randint(1, 4)):  # publications
                known = dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=rng.randint(0, 7000))
                cursor = dt.date(1998, 1, 1) + dt.timedelta(days=rng.randint(0, 500))
                for _ in range(rng.randint(1, 4)):  # disjoint segments, one entity each
                    start = cursor + dt.timedelta(days=rng.randint(0, 400))
                    end = start + dt.timedelta(days=rng.randint(1, 2000))
                    owner = rng.choice(["E1", "E2", "E3"])
                    rows.append(ident(owner, ticker, start.isoformat(), end.isoformat(), known.isoformat()))
                    if rng.random() < 0.3:  # an overlapping interval of the same entity
                        inner = start + dt.timedelta(days=rng.randint(0, (end - start).days))
                        rows.append(ident(owner, ticker, start.isoformat(), inner.isoformat(), known.isoformat()))
                    cursor = end
                if rng.random() < 0.3:
                    rows[-1]["valid_to"] = None
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        write_table(os.path.join(tmp.name, "WorldModel-Identifiers"), rows, IDENTIFIERS_SCHEMA)
        model = WorldModel(local_dir=tmp.name)
        dates = [dt.date(1999, 1, 1) + dt.timedelta(days=97 * k) for k in range(100)]
        panel = model.resolve_panel(tickers + ["NONE"], dates)

        frame = _pit.typed(pd.DataFrame(rows))
        expected = []
        for ticker in tickers + ["NONE"]:
            for day in dates:
                cutoff, world = _pit.as_of_point(day)
                hit = _pit.view(frame[frame["value"] == ticker], ["scheme", "value"], cutoff, world)
                owners = hit["entity_id"].unique().tolist()
                self.assertLessEqual(len(owners), 1)
                expected.append(owners[0] if owners else None)
        got = [None if pd.isna(v) else v for v in panel["entity_id"].tolist()]
        self.assertEqual(got, expected)
        self.assertGreater(sum(v is not None for v in got), 50)

    def test_pairs(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        write_table(os.path.join(tmp.name, "WorldModel-Identifiers"),
                    [ident("E_A", "AAA", "2020-01-01", None, "2020-01-01")], IDENTIFIERS_SCHEMA)
        model = WorldModel(local_dir=tmp.name)
        panel = model.resolve_panel(["AAA", "AAA"], ["2019-06-03", "2020-06-01"], pairs=True)
        self.assertEqual(len(panel), 2)
        self.assertEqual(panel["entity_id"].fillna("-").tolist(), ["-", "E_A"])
        with self.assertRaises(ValueError):
            model.resolve_panel(["AAA"], ["2019-06-03", "2020-06-01"], pairs=True)


class Graph(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        write_table(os.path.join(self.root, "WorldModel-Identifiers"),
                    [ident("E_A", "AAA", "2000-01-01", None, "2000-01-01")], IDENTIFIERS_SCHEMA)
        self.edges = [
            # FY2019 customer link, published with the 10-K in March 2020
            edge("E_C", "E_S", "customer_of", "2020-01-01", "2021-01-01", "2020-03-02", weight=0.2),
            # the same edge re-read by a second extractor, published later
            edge("E_C", "E_S", "customer_of", "2020-01-01", "2021-01-01", "2020-09-01", method="llm_v2", weight=0.25),
            # a correction of the xbrl_v1 weight published in 2021
            edge("E_C", "E_S", "customer_of", "2020-01-01", "2021-01-01", "2021-02-01", weight=0.3),
            edge("E_C", "E_T", "customer_of", "2020-01-01", None, "2020-03-02"),
            edge("E_S", "E_T", "io_flow", "2019-01-01", None, "2019-12-15", method="bea_2017"),
        ]
        write_table(os.path.join(self.root, "WorldModel-Edges-Supply"), self.edges[:4], EDGES_SCHEMA)
        write_table(os.path.join(self.root, "WorldModel-Edges-IO"), self.edges[4:], EDGES_SCHEMA)
        self.wm = WorldModel(local_dir=self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_edges_dataset_is_said(self):
        empty = tempfile.TemporaryDirectory()
        self.addCleanup(empty.cleanup)
        write_table(os.path.join(empty.name, "WorldModel-Identifiers"),
                    [ident("E_A", "AAA", "2000-01-01", None, "2000-01-01")], IDENTIFIERS_SCHEMA)
        with self.assertRaisesRegex(WorldModelNotAvailable, "no WorldModel-Edges-"):
            WorldModel(local_dir=empty.name).get_graph("2020-06-01")

    def test_families_are_found(self):
        self.assertEqual(self.wm.edge_families(), ["WorldModel-Edges-IO", "WorldModel-Edges-Supply"])

    def test_nothing_before_publication(self):
        graph = self.wm.get_graph("2020-02-28", relations="customer_of")
        self.assertTrue(graph.empty)
        self.assertIn("src", graph.columns)

    def test_point_in_time_and_latest_method(self):
        graph = self.wm.get_graph("2020-06-01", relations=["customer_of"])
        self.assertEqual(set(graph["method"]), {"xbrl_v1"})
        self.assertEqual(sorted(graph["dst"]), ["E_S", "E_T"])
        # after the second extractor is published, it is the latest method
        later = self.wm.get_graph("2020-10-01", relations=["customer_of"])
        self.assertEqual(later["method"].tolist(), ["llm_v2"])

    def test_correction_after_t_is_invisible_at_t(self):
        at_t = self.wm.get_graph("2020-12-31", relations="customer_of", method="xbrl_v1")
        weights = dict(zip(at_t["dst"], at_t["weight"]))
        self.assertAlmostEqual(weights["E_S"], 0.2, places=6)
        after = self.wm.get_graph("2021-02-02", relations="customer_of", method="xbrl_v1",
                                  date="2020-12-31")
        self.assertAlmostEqual(dict(zip(after["dst"], after["weight"]))["E_S"], 0.3, places=6)

    def test_interval_is_half_open(self):
        on_end = self.wm.get_graph("2021-01-01", relations="customer_of", method="xbrl_v1")
        self.assertEqual(on_end["dst"].tolist(), ["E_T"])

    def test_all_methods(self):
        graph = self.wm.get_graph("2020-10-01", relations="customer_of", method="all")
        self.assertEqual(sorted(graph["method"]), ["llm_v2", "xbrl_v1", "xbrl_v1"])

    def test_supplier_to_is_derived(self):
        graph = self.wm.get_graph("2020-06-01", relations="supplier_to")
        self.assertEqual(sorted(zip(graph["src"], graph["dst"])), [("E_S", "E_C"), ("E_T", "E_C")])
        self.assertEqual(set(graph["relation"]), {"supplier_to"})

    def test_every_relation_by_default(self):
        graph = self.wm.get_graph("2020-06-01")
        self.assertEqual(sorted(graph["relation"].unique()), ["customer_of", "io_flow"])

    def test_vocabulary(self):
        with self.assertRaises(ValueError):
            self.wm.get_graph("2020-06-01", relations="owns")
        with self.assertRaises(NotImplementedError):
            self.wm.get_graph("2020-06-01", relations="in_sector")


class GraphLatestKnown(unittest.TestCase):
    """``period="latest_known"``: the reader picks the vintage, not the date."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        write_table(os.path.join(self.root, "WorldModel-Identifiers"),
                    [ident("E_A", "AAA", "2000-01-01", None, "2000-01-01")], IDENTIFIERS_SCHEMA)
        rows = [
            # the 2022 vintage of a yearly table, published in 2024
            edge("E_A", "E_B", "io_flow", "2022-01-01", "2023-01-01", "2024-03-01", method="bea", weight=0.1),
            # the 2023 vintage, published in 2025 (after its interval ended)
            edge("E_A", "E_B", "io_flow", "2023-01-01", "2024-01-01", "2025-03-01", method="bea", weight=0.2),
            # a late correction of the 2022 vintage: never replaces the 2023 one
            edge("E_A", "E_B", "io_flow", "2022-01-01", "2023-01-01", "2025-06-01", method="bea", weight=0.15),
            # a correction of the 2023 vintage, published after 2026-01-01
            edge("E_A", "E_B", "io_flow", "2023-01-01", "2024-01-01", "2026-02-01", method="bea", weight=0.25),
            # another pair, only ever published for 2021
            edge("E_A", "E_C", "io_flow", "2021-01-01", "2022-01-01", "2022-05-01", method="bea", weight=0.3),
        ]
        write_table(os.path.join(self.root, "WorldModel-Edges-IO"), rows, EDGES_SCHEMA)
        self.wm = WorldModel(local_dir=self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def latest(self, as_of):
        graph = self.wm.get_graph(as_of, relations="io_flow", period="latest_known")
        return {dst: (row.reference_period.date().isoformat(), round(float(row.weight), 6))
                for dst, row in graph.set_index("dst").iterrows()}

    def test_2023_vintage_published_in_2025_is_chosen_in_2026(self):
        self.assertEqual(self.latest("2026-01-01"),
                         {"E_B": ("2023-01-01", 0.2), "E_C": ("2021-01-01", 0.3)})

    def test_2023_vintage_is_ignored_before_its_publication(self):
        self.assertEqual(self.latest("2025-01-01"),
                         {"E_B": ("2022-01-01", 0.1), "E_C": ("2021-01-01", 0.3)})

    def test_correction_of_the_period_replaces_it_once_published(self):
        self.assertEqual(self.latest("2026-03-01")["E_B"], ("2023-01-01", 0.25))

    def test_reference_period_column(self):
        graph = self.wm.get_graph("2026-01-01", period="latest_known")
        self.assertEqual(graph.columns[-1], "reference_period")
        self.assertTrue((graph["reference_period"] == graph["valid_from"]).all())
        empty = self.wm.get_graph("2020-01-01", period="latest_known")
        self.assertTrue(empty.empty)
        self.assertIn("reference_period", empty.columns)

    def test_default_reading_is_unchanged(self):
        # the date test finds nothing: no interval holds 2026-01-01
        self.assertTrue(self.wm.get_graph("2026-01-01", relations="io_flow").empty)
        graph = self.wm.get_graph("2025-04-01", relations="io_flow", date="2023-06-01")
        self.assertEqual([round(float(w), 6) for w in graph["weight"]], [0.2])
        self.assertNotIn("reference_period", graph.columns)

    def test_bad_period_and_date(self):
        with self.assertRaises(ValueError):
            self.wm.get_graph("2026-01-01", period="latest")
        with self.assertRaises(ValueError):
            self.wm.get_graph("2026-01-01", period="latest_known", date="2023-06-01")


class AsOfConversion(unittest.TestCase):
    def test_vector_and_scalar_agree(self):
        values = ["2020-03-02", pd.Timestamp("2020-07-01"), dt.date(2020, 11, 2),
                  pd.Timestamp("2020-03-02 21:00", tz="UTC"), "2020-03-02 10:30"]
        cutoffs, dates = _pit.as_of_points(values)
        for value, cutoff, date in zip(values, cutoffs, dates):
            self.assertEqual(_pit.as_of_point(value), (cutoff, date))
        self.assertEqual(str(cutoffs[0]), "2020-03-03 04:59:59.999999+00:00")  # EST
        self.assertEqual(str(cutoffs[1]), "2020-07-02 03:59:59.999999+00:00")  # EDT

    def test_as_of_is_required(self):
        with self.assertRaises(ValueError):
            _pit.as_of_point(None)


if __name__ == "__main__":
    unittest.main()


class HubSourceOffline(unittest.TestCase):
    """The Hub path with the Hub replaced: pinning, shard window, errors."""

    def setUp(self):
        from unittest import mock

        self.mock = mock
        environment = mock.patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("PWB_WORLD_MODEL_DIR", None)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.local = write_table(
            os.path.join(self._tmp.name, "ids"),
            [ident("E_A", "AAA", "2000-01-01", None, "2000-01-01"),
             ident("E_B", "AAA", "2000-01-01", None, "2030-01-01")],
            IDENTIFIERS_SCHEMA,
        )
        self.downloads = []

    def _download(self, repo_id, repo_type, filename, revision, token):
        self.downloads.append((repo_id, filename, revision))
        return os.path.join(self.local, os.path.basename(filename))

    def test_current_revision_and_shard_window(self):
        snapshot = ("abc123", ["data/train-2000.parquet", "data/train-2030.parquet", "README.md"])
        with self.mock.patch("pwb_toolbox.datasets._hub_snapshot", return_value=snapshot), \
             self.mock.patch("huggingface_hub.hf_hub_download", side_effect=self._download):
            model = WorldModel()
            self.assertEqual(model.resolve("AAA", "2020-01-02"), "E_A")
        self.assertEqual(self.downloads, [
            ("paperswithbacktest/WorldModel-Identifiers", "data/train-2000.parquet", "abc123"),
        ])

    def test_pinned_revision(self):
        info = self.mock.Mock(sha="def456", siblings=[self.mock.Mock(rfilename="data/train-2000.parquet")])
        api = self.mock.Mock()
        api.return_value.dataset_info.return_value = info
        with self.mock.patch("huggingface_hub.HfApi", api), \
             self.mock.patch("huggingface_hub.hf_hub_download", side_effect=self._download):
            model = WorldModel(revision={"WorldModel-Identifiers": "def456"})
            self.assertEqual(model.resolve("AAA", "2020-01-02"), "E_A")
        api.return_value.dataset_info.assert_called_once_with(
            "paperswithbacktest/WorldModel-Identifiers", revision="def456"
        )
        self.assertEqual(self.downloads[0][2], "def456")

    def test_unreadable_dataset_is_said(self):
        with self.mock.patch("pwb_toolbox.datasets._hub_snapshot", side_effect=RuntimeError("404")):
            with self.assertRaisesRegex(WorldModelNotAvailable, "WorldModel-Identifiers"):
                WorldModel().resolve("AAA", "2020-01-02")

    def test_no_edges_family_on_the_hub(self):
        api = self.mock.Mock()
        api.return_value.list_datasets.return_value = []
        with self.mock.patch("huggingface_hub.HfApi", api):
            with self.assertRaisesRegex(WorldModelNotAvailable, "no WorldModel-Edges-"):
                WorldModel().get_graph("2020-01-02")
