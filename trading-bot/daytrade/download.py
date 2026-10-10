"""Download 5-minute bars from Alpaca into data/<SYMBOL>_5Min.csv.

    python -m daytrade.download --symbols SPY QQQ AAPL --start 2022-01-01
"""
from __future__ import annotations

import argparse
from datetime import date

from dotenv import load_dotenv

from . import data

DEFAULT_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "AMD", "GOOGL"]


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--start", default="2022-01-01")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--timeframe", default="5Min")
    ap.add_argument("--feed", default="iex", help="iex (free) or sip (paid)")
    a = ap.parse_args()
    data.DATA_DIR.mkdir(exist_ok=True)
    for s in a.symbols:
        df = data.fetch_alpaca(s, a.start, a.end, a.timeframe, a.feed)
        df.to_csv(data.cache_path(s, a.timeframe), index_label="timestamp")
        print(f"{s}: {len(df)} bars {df.index[0].date()} .. {df.index[-1].date()}")


if __name__ == "__main__":
    main()
