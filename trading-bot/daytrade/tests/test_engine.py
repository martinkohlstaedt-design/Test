"""Run with: python -m unittest discover -s daytrade/tests -t ."""
import unittest

import numpy as np

from daytrade import data
from daytrade.engine import Costs, metrics, run, simulate_trade
from daytrade.features import Day, build_days
from daytrade.strategies import Setup


def flat_day(n=78, price=100.0):
    a = np.full(n, price)
    return Day("T", __import__("pandas").Timestamp("2024-01-02"), a.copy(), a.copy(), a.copy(), a.copy(),
               np.full(n, 1e5), a.copy(), np.full(n, 0.2), np.ones(n), 1, price, 5)


class EngineTests(unittest.TestCase):
    def test_target_hit_long(self):
        d = flat_day(); d.h[5] = 102.5
        t = simulate_trade(d, Setup(2, 1, 99.0, 102.0), Costs(slippage_bps=0))
        self.assertEqual(t["reason"], "target"); self.assertAlmostEqual(t["ret"], 0.02)

    def test_stop_before_target_same_bar(self):
        d = flat_day(); d.h[5] = 103; d.l[5] = 98.5
        t = simulate_trade(d, Setup(2, 1, 99.0, 102.0), Costs(slippage_bps=0))
        self.assertEqual(t["reason"], "stop"); self.assertAlmostEqual(t["ret"], -0.01)

    def test_short_and_eod_exit_with_slippage(self):
        d = flat_day()
        t = simulate_trade(d, Setup(2, -1, 101.0, 98.0), Costs(slippage_bps=2))
        self.assertEqual(t["reason"], "eod"); self.assertAlmostEqual(t["ret"], -0.0004, places=6)

    def test_gap_through_stop_rejected(self):
        d = flat_day(); d.o[3] = 98.0
        self.assertIsNone(simulate_trade(d, Setup(3, 1, 99.0, 102.0), Costs()))

    def test_no_lookahead_in_features(self):
        df = data.synthetic(days=40, seed=1)
        a = build_days(df, "X")
        df2 = df.copy(); df2.iloc[-50:, df2.columns.get_loc("close")] *= 1.5   # change the future
        b = build_days(df2, "X")
        k = 30
        np.testing.assert_allclose(a[k].atr, b[k].atr); np.testing.assert_allclose(a[k].rvol, b[k].rvol)
        self.assertEqual(a[k].trend, b[k].trend)

    def test_random_walk_has_no_edge(self):
        """On a pure random walk, costs must make every strategy a net loser or ~flat."""
        frames = {f"S{i}": data.synthetic(days=250, seed=i) for i in range(4)}
        days = {s: build_days(df, s) for s, df in frames.items()}
        from daytrade.strategies import PARAM_GRIDS
        costs = Costs()
        idx = __import__("pandas").DatetimeIndex(sorted({d.date for v in days.values() for d in v}))
        for strat, space in PARAM_GRIDS.items():
            p = {k: v[0] for k, v in space.items()}
            m = metrics(run(days, strat, p, costs), idx, costs)
            self.assertLess(m["sharpe"], 1.5, f"{strat} looks profitable on random data: {m}")


if __name__ == "__main__":
    unittest.main()
