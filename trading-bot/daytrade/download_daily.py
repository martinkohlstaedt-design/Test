"""Download daily bars (SIP, adjusted) into data/<SYMBOL>_1Day.csv.

    python -m daytrade.download_daily --start 2016-01-01
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

from dotenv import load_dotenv

from . import data

# Mixed on purpose: today's winners AND laggards, so the test isn't just "stocks that went up".
# Still survivorship-biased (all of these exist today) - see README caveat.
UNIVERSE = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "AMD", "NFLX", "ADBE",
            "INTC", "CSCO", "ORCL", "IBM", "QCOM", "TXN", "JPM", "BAC", "WFC", "C", "GS",
            "V", "MA", "XOM", "CVX", "COP", "PFE", "MRK", "JNJ", "UNH", "ABT", "KO", "PEP",
            "PG", "WMT", "COST", "MCD", "NKE", "DIS", "T", "VZ", "BA", "CAT", "GE", "HD"]
BENCH = ["SPY", "QQQ"]


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=UNIVERSE + BENCH)
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default=(date.today() - timedelta(days=2)).isoformat())
    ap.add_argument("--feed", default="sip")
    a = ap.parse_args()
    data.DATA_DIR.mkdir(exist_ok=True)
    for s in a.symbols:
        df = data.fetch_daily(s, a.start, a.end, a.feed)
        df.to_csv(data.cache_path(s, "1Day"), index_label="date")
        print(f"{s}: {len(df)} days {df.index[0].date()} .. {df.index[-1].date()}")


if __name__ == "__main__":
    main()
