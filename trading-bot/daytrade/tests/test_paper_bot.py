import unittest

import pandas as pd

from daytrade.paper_bot import plan_orders


class PlanTests(unittest.TestCase):
    def test_buy_new_and_sell_exited(self):
        w = pd.Series({"AAA": 0.1, "BBB": 0.0})
        px = pd.Series({"AAA": 50.0, "BBB": 20.0})
        o = plan_orders(w, px, 100_000, {"BBB": 40})
        self.assertEqual(o, [{"symbol": "BBB", "side": "sell", "qty": 40}, {"symbol": "AAA", "side": "buy", "qty": 200}])

    def test_no_churn_on_small_drift(self):
        w = pd.Series({"AAA": 0.1}); px = pd.Series({"AAA": 50.0})
        self.assertEqual(plan_orders(w, px, 100_000, {"AAA": 170}), [])       # within 25 % of 200
        self.assertEqual(len(plan_orders(w, px, 100_000, {"AAA": 100})), 1)   # far off -> resize

    def test_position_not_in_universe_is_closed(self):
        o = plan_orders(pd.Series({"AAA": 0.0}), pd.Series({"AAA": 10.0}), 1000, {"ZZZ": 5})
        self.assertEqual(o, [{"symbol": "ZZZ", "side": "sell", "qty": 5}])


if __name__ == "__main__":
    unittest.main()
