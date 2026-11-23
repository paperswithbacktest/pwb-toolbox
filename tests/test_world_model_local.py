"""The reader on a real local build of the reference tables (skipped without it).

Point ``PWB_WORLD_MODEL_TEST_DIR`` at a directory holding
``WorldModel-Identifiers/`` and ``WorldModel-Entities/`` (one generation each,
or several with a ``manifest.json`` each: the newest is read). Nothing is
downloaded; only the rows of the tickers asked for are read from the shards.
"""

import os
import unittest

import pandas as pd

from pwb_toolbox.world_model import WorldModel

ROOT = os.path.expanduser(
    os.getenv("PWB_WORLD_MODEL_TEST_DIR", "~/dev/pwb/worldmodel-cache/out")
)
HAVE_BUILD = os.path.isdir(os.path.join(ROOT, "WorldModel-Identifiers"))
TODAY = "2026-11-23"


@unittest.skipUnless(HAVE_BUILD, f"no local World Model build under {ROOT}")
class LocalBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wm = WorldModel(local_dir=ROOT)

    def cik(self, ticker, as_of, date=None):
        found = self.wm.resolve(ticker, as_of, details=True, date=date)
        return None if found is None else found["cik"]

    def test_tgx_is_theragenics_until_29_october_2013(self):
        self.assertEqual(self.cik("TGX", "2012-06-01"), "0000795551")
        self.assertEqual(self.cik("TGX", TODAY, date="2013-10-28"), "0000795551")
        self.assertIsNone(self.wm.resolve("TGX", TODAY, date="2013-10-29"))
        self.assertIsNone(self.wm.resolve("TGX", "2013-11-15"))

    def test_point_in_time_hides_what_was_published_later(self):
        # In 2009 nothing published yet covered TGX on that day; the gap is
        # filled by rows published in 2026, visible only with today's knowledge.
        self.assertIsNone(self.wm.resolve("TGX", "2009-06-01"))
        self.assertEqual(self.cik("TGX", TODAY, date="2009-06-01"), "0000795551")

    def test_googl(self):
        found = self.wm.resolve("GOOGL", "2024-01-02", details=True)
        self.assertEqual(found["cik"], "0001652044")
        self.assertEqual(found["name"], "Alphabet Inc.")

    def test_reused_ticker(self):
        old, new = self.cik("DELL", TODAY, "2010-06-01"), self.cik("DELL", TODAY, "2020-06-01")
        self.assertEqual((old, new), ("0000826083", "0001571996"))
        self.assertNotEqual(self.wm.resolve("DELL", TODAY, date="2010-06-01"),
                            self.wm.resolve("DELL", TODAY, date="2020-06-01"))

    def test_panel_agrees_with_resolve(self):
        dates = pd.bdate_range("2012-01-02", "2014-01-02", freq="21B")
        panel = self.wm.resolve_panel(["TGX", "GOOGL", "DELL"], dates)
        for ticker, date, got in panel[["ticker", "date", "entity_id"]].itertuples(index=False):
            expected = self.wm.resolve(ticker, date)
            self.assertEqual(None if pd.isna(got) else got, expected, (ticker, date))


if __name__ == "__main__":
    unittest.main()
