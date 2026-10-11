"""Bulk downloads: S&P 500 daily bars (current constituents) and crypto daily bars.

    python -m daytrade.download_extra sp500
    python -m daytrade.download_extra crypto
"""
from __future__ import annotations

import sys
import time
from datetime import date, timedelta

import pandas as pd
from dotenv import load_dotenv

from . import data

CRYPTO = ["BTC/USD", "ETH/USD", "SOL/USD", "LTC/USD", "LINK/USD", "AVAX/USD", "DOGE/USD", "BCH/USD", "UNI/USD", "AAVE/USD"]


def main():
    load_dotenv()
    kind = sys.argv[1]
    end = (date.today() - timedelta(days=2)).isoformat()
    data.DATA_DIR.mkdir(exist_ok=True)
    if kind == "sp500":
        syms = pd.read_csv(sys.argv[2])["Symbol"].tolist()
        ok = 0
        for s in syms:
            if "." in s:
                continue
            try:
                df = data.fetch_daily(s, "2016-01-01", end)
                df.to_csv(data.cache_path(s, "1Day"), index_label="date")
                ok += 1
            except Exception as e:                                  # delisted / no data
                print(f"skip {s}: {str(e)[:60]}")
            time.sleep(0.3)
        print(f"done: {ok} symbols")
    else:
        for s in CRYPTO:
            try:
                df = data.fetch_crypto_daily(s, "2021-01-01T00:00:00Z", end + "T00:00:00Z")
                df.to_csv(data.cache_path(s.replace("/", ""), "1Day"), index_label="date")
                print(f"{s}: {len(df)} days {df.index[0].date()}..{df.index[-1].date()}")
            except Exception as e:
                print(f"skip {s}: {str(e)[:80]}")


if __name__ == "__main__":
    main()
