"""Download and parse 13F-HR filings from SEC EDGAR (with on-disk cache)."""
import json
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

CACHE = Path(__file__).parent / ".cache"
UA = os.environ.get("SEC_USER_AGENT", "13f-backtest-research admin@example.com")
FIRST_PERIOD = "2013-09-30"  # 13F infotables are XML from the 2013Q3 period on
_session = requests.Session()
_session.headers["User-Agent"] = UA


def _get(url, as_json=False):
    for attempt in range(4):
        time.sleep(0.15)  # SEC fair-access limit: 10 req/s
        r = _session.get(url, timeout=30)
        if r.status_code == 200:
            return r.json() if as_json else r.text
        if r.status_code in (429, 503):
            time.sleep(2 ** attempt * 2)
            continue
        r.raise_for_status()
    raise RuntimeError(f"giving up on {url}")


def list_filings(cik):
    """All original 13F-HR filings for a manager from FIRST_PERIOD on."""
    sub = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", as_json=True)
    blocks = [sub["filings"]["recent"]]
    for f in sub["filings"].get("files", []):
        blocks.append(_get(f"https://data.sec.gov/submissions/{f['name']}", as_json=True))
    out = []
    for b in blocks:
        for form, acc, filed, period in zip(
            b["form"], b["accessionNumber"], b["filingDate"], b["reportDate"]
        ):
            if form == "13F-HR" and period >= FIRST_PERIOD:
                out.append({"acc": acc, "filed": filed, "period": period})
    return sorted(out, key=lambda x: x["period"])


def _local(tag):
    return tag.split("}")[-1]


def parse_infotable(xml_text):
    root = ET.fromstring(xml_text)
    rows = []
    for el in root.iter():
        if _local(el.tag) != "infoTable":
            continue
        d = {}
        for sub in el.iter():
            if sub.text and sub.text.strip():
                d.setdefault(_local(sub.tag), sub.text.strip())
        if d.get("putCall") or d.get("sshPrnamtType", "SH") != "SH":
            continue  # skip options and bonds: only plain share positions
        try:
            rows.append({"cusip": d["cusip"].upper(), "name": d.get("nameOfIssuer", ""),
                         "value": float(d["value"])})
        except (KeyError, ValueError):
            continue
    return rows


def _infotable_rows(cik, acc):
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    idx = _get(base + "/index.json", as_json=True)
    files = [i["name"] for i in idx["directory"]["item"]
             if i["name"].lower().endswith(".xml") and "primary_doc" not in i["name"].lower()]
    files.sort(key=lambda n: "infotable" not in n.lower())
    for name in files:
        rows = parse_infotable(_get(f"{base}/{name}"))
        if rows:
            return rows
    return []


def load_manager(cik):
    """-> list of {period, filed, positions: {cusip: {name, value}}}, cached."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"holdings_{cik}.json"
    cached = json.loads(path.read_text()) if path.exists() else {}
    result = []
    for f in list_filings(cik):
        if f["acc"] not in cached:
            cached[f["acc"]] = _infotable_rows(cik, f["acc"])
            path.write_text(json.dumps(cached))
        pos = {}
        for r in cached[f["acc"]]:
            p = pos.setdefault(r["cusip"], {"name": r["name"], "value": 0.0})
            p["value"] += r["value"]
        if pos:
            result.append({"period": f["period"], "filed": f["filed"], "positions": pos})
    return result
