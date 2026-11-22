"""``rate_to_price`` turns every Bonds-Daily-Price yield into a zero-coupon price.

The stored series are yields in percent. Before 0.1.54 the maturity was read
with ``(\\d+)([YM])$``, which does not match the TIPS real yields ``US5YT``,
``US10YT`` and ``US30YT``: they were served as yields, a "price" that went
through zero (US5YT -1.97 in 2021), and a strategy that traded them as prices
booked returns of several hundred percent on a sign change.
"""

import unittest
import warnings

import numpy as np
import pandas as pd

import pwb_toolbox.datasets as pwb_ds


def _frame(rows):
    df = pd.DataFrame(rows, columns=["symbol", "close"])
    for col in ("open", "high", "low"):
        df[col] = df["close"]
    df["date"] = pd.Timestamp("2021-08-02")
    return df


class BondRateToPriceTest(unittest.TestCase):
    def convert(self, rows):
        return pwb_ds._convert_bond_rates_to_prices(_frame(rows))

    def test_nominal_maturities_unchanged(self):
        out = self.convert([("US10Y", 4.0), ("US3M", 5.0), ("DE2Y", -0.5)])
        close = dict(zip(out["symbol"], out["close"]))
        self.assertAlmostEqual(close["US10Y"], 100 / 1.04 ** 10, places=10)
        self.assertAlmostEqual(close["US3M"], 100 / 1.05 ** 0.25, places=10)
        self.assertAlmostEqual(close["DE2Y"], 100 / 0.995 ** 2, places=10)

    def test_tips_real_yields_are_converted(self):
        out = self.convert([("US5YT", -1.972), ("US10YT", 4.413), ("US30YT", -0.586)])
        close = dict(zip(out["symbol"], out["close"]))
        self.assertAlmostEqual(close["US5YT"], 100 / (1 - 0.01972) ** 5, places=10)
        self.assertAlmostEqual(close["US10YT"], 100 / 1.04413 ** 10, places=10)
        self.assertAlmostEqual(close["US30YT"], 100 / (1 - 0.00586) ** 30, places=10)
        # a negative real yield is a price above par, never a negative price
        self.assertGreater(close["US5YT"], 100)
        self.assertTrue((out[["open", "high", "low", "close"]] > 0).all().all())

    def test_a_tips_series_through_zero_stays_positive_and_continuous(self):
        yields = np.array([0.30, 0.10, -0.05, -0.40, -1.97, -0.20, 0.15])
        out = self.convert([("US5YT", y) for y in yields])
        price = out["close"].to_numpy()
        self.assertTrue((price > 0).all())
        # a 25 bp move on a 5-year zero is about a 1.2 % price move, not a sign flip
        self.assertLess(np.abs(np.diff(np.log(price))).max(), 0.10)

    def test_an_unreadable_symbol_stays_a_yield_and_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            out = self.convert([("US10Y", 4.0), ("ESDE10", 1.2)])
        close = dict(zip(out["symbol"], out["close"]))
        self.assertEqual(close["ESDE10"], 1.2)
        names = [w for w in caught if issubclass(w.category, pwb_ds.UnconvertedBondRateWarning)]
        self.assertEqual(len(names), 1)
        self.assertIn("ESDE10", str(names[0].message))

    def test_no_warning_when_every_symbol_converts(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", pwb_ds.UnconvertedBondRateWarning)
            self.convert([("US10Y", 4.0), ("US10YT", 1.0)])

    def test_the_old_name_still_answers(self):
        legacy = getattr(pwb_ds, "__convert_bond_rates_to_prices")
        self.assertIs(legacy, pwb_ds._convert_bond_rates_to_prices)


if __name__ == "__main__":
    unittest.main()
