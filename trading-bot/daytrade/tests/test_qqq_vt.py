import unittest

import numpy as np

from daytrade.qqq_vt_bot import decide, target_weight


class VtTests(unittest.TestCase):
    def test_calm_market_is_fully_invested(self):
        closes = 100 * np.cumprod(1 + np.full(40, 0.0005))
        self.assertEqual(target_weight(closes), 1.0)

    def test_volatile_market_scales_down(self):
        rng = np.random.default_rng(1)
        closes = 100 * np.cumprod(1 + rng.normal(0, 0.03, 40))          # ~48 % annual vol
        w = target_weight(closes)
        self.assertTrue(0.2 < w < 0.6, w)

    def test_band_blocks_small_moves_but_not_extremes(self):
        self.assertEqual(decide(0.75, 0.70), 0.70)         # inside band: hold
        self.assertEqual(decide(0.55, 0.70), 0.55)         # outside band: move
        self.assertEqual(decide(1.0, 0.95), 1.0)           # go fully invested
        self.assertEqual(decide(0.0, 0.05), 0.0)           # go fully out


if __name__ == "__main__":
    unittest.main()
