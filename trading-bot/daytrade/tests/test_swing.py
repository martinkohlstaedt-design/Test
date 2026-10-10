import unittest

import numpy as np
import pandas as pd

from daytrade import swing


def panel(n=400, seed=0, k=4):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    c = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (n, k)), axis=0)), index=idx, columns=list("ABCD")[:k])
    o = c.shift(1).fillna(c.iloc[0]) * (1 + rng.normal(0, 0.001, (n, k)))
    return {"open": o, "high": np.maximum(o, c) * 1.002, "low": np.minimum(o, c) * 0.998, "close": c}


class SwingTests(unittest.TestCase):
    def test_signals_ignore_the_future(self):
        px = panel()
        px2 = {k: v.copy() for k, v in px.items()}
        for v in px2.values():
            v.iloc[300:] *= 1.7
        for f in (swing.trend_donchian, swing.rsi2_reversion, swing.xsec_momentum):
            a, b = f(px), f(px2)
            pd.testing.assert_frame_equal(a.iloc[:300], b.iloc[:300], check_exact=False)

    def test_execution_is_next_open(self):
        px = panel(k=1)
        w = pd.DataFrame(0.0, index=px["close"].index, columns=["A"])
        w.iloc[100] = 1.0                      # decided at close of day 100
        r = swing.backtest(w, px, cost_bps=0)
        o = px["open"]["A"]
        self.assertAlmostEqual(r.iloc[101], o.iloc[102] / o.iloc[101] - 1)   # earns open101->open102
        self.assertEqual(r.iloc[100], 0.0)

    def test_costs_charged_on_turnover(self):
        px = panel(k=1)
        w = pd.DataFrame(0.0, index=px["close"].index, columns=["A"])
        w.iloc[100] = 1.0
        diff = swing.backtest(w, px, 0).iloc[101] - swing.backtest(w, px, 10).iloc[101]
        self.assertAlmostEqual(diff, 10 / 1e4)

    def test_random_walk_no_edge(self):
        px = panel(n=2500, k=4, seed=3)
        w = swing.equalise(swing.trend_donchian(px), min_slots=4)
        self.assertLess(swing.stats(swing.backtest(w, px, 3.0))["sharpe"], 0.8)


if __name__ == "__main__":
    unittest.main()
