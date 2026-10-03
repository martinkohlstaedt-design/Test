"""CUSIP -> ticker (OpenFIGI) and adjusted daily prices (Yahoo chart API), both cached."""
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests

CACHE = Path(__file__).parent / ".cache"
FIGI_KEY = os.environ.get("OPENFIGI_KEY")
_BATCH = 100 if FIGI_KEY else 10
_PAUSE = 0.3 if FIGI_KEY else 2.6  # free tier: 25 requests/min


def map_cusips(cusips):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / "cusip_ticker.json"
    known = json.loads(path.read_text()) if path.exists() else {}
    todo = sorted({c for c in cusips if c not in known})
    headers = {"Content-Type": "application/json"}
    if FIGI_KEY:
        headers["X-OPENFIGI-APIKEY"] = FIGI_KEY
    for i in range(0, len(todo), _BATCH):
        batch = todo[i:i + _BATCH]
        jobs = [{"idType": "ID_CUSIP", "idValue": c} for c in batch]
        while True:
            r = requests.post("https://api.openfigi.com/v3/mapping", json=jobs,
                              headers=headers, timeout=30)
            if r.status_code == 429:
                time.sleep(30)
                continue
            r.raise_for_status()
            break
        for c, res in zip(batch, r.json()):
            ticker = None
            data = [d for d in res.get("data", []) if d.get("marketSector") == "Equity"]
            us = [d for d in data if d.get("exchCode") == "US"] or data
            if us:
                ticker = us[0]["ticker"].replace("/", "-")
            known[c] = ticker
        path.write_text(json.dumps(known))
        print(f"  mapped {min(i + _BATCH, len(todo))}/{len(todo)} CUSIPs", flush=True)
        time.sleep(_PAUSE)
    return known


def prices(ticker):
    """Adjusted close as a date-indexed Series (empty if unavailable)."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"px_{ticker}.csv"
    if path.exists():
        s = pd.read_csv(path, index_col=0, parse_dates=True)
        return s.iloc[:, 0] if len(s.columns) else pd.Series(dtype=float)
    time.sleep(0.3)
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
    r = requests.get(url, params={"range": "max", "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    s = pd.Series(dtype=float)
    if r.status_code == 200:
        try:
            res = r.json()["chart"]["result"][0]
            adj = res["indicators"]["adjclose"][0]["adjclose"]
            idx = pd.to_datetime(res["timestamp"], unit="s").normalize()
            s = pd.Series(adj, index=idx).dropna()
            s = s[~s.index.duplicated()]
        except (KeyError, TypeError, IndexError):
            pass
    elif r.status_code == 429:
        raise RuntimeError("Yahoo rate limit, retry later")
    s.rename("adj").to_csv(path)
    return s
