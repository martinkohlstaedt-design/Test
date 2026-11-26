#!/usr/bin/env python3
"""Global M2 (G4-Aggregat) aus Zentralbankdaten, umgerechnet in USD.

US  : FRED M2SL (Mrd. USD)
EZ  : EZB BSI M2 (Mio. EUR)
JP  : Bank of Japan M2 (100 Mio. JPY)
UK  : Bank of England M4, LPMAUYN (Mio. GBP) - UK veröffentlicht kein M2
FX  : FRED Monatsdurchschnitte (EXUSEU, EXJPUS, EXUSUK)
China fehlt: PBoC/NBS bieten keine maschinenlesbare API.
"""
import csv, io, json, subprocess, time
from datetime import datetime

START = "2000-01-01"


def curl(url, headers=(), retries=4):
    cmd = ["curl", "-sS", "--fail", "-m", "90"]
    for h in headers:
        cmd += ["-H", h]
    for attempt in range(retries):
        try:
            return subprocess.run(cmd + [url], capture_output=True, text=True, check=True).stdout
        except subprocess.CalledProcessError:
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def fred(sid):
    text = curl(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={START}")
    return {d[:7]: float(v) for d, v in list(csv.reader(io.StringIO(text)))[1:] if v not in ("", ".")}


def ecb_m2():
    text = curl(
        "https://data-api.ecb.europa.eu/service/data/BSI/M.U2.Y.V.M20.X.1.U2.2300.Z01.E"
        f"?startPeriod=2000-01&format=csvdata", ["Accept: text/csv"])
    rows = csv.DictReader(io.StringIO(text))
    return {r["TIME_PERIOD"]: float(r["OBS_VALUE"]) for r in rows if r["OBS_VALUE"]}  # Mio. EUR


def boj_m2():
    d = json.loads(curl("https://www.stat-search.boj.or.jp/api/v1/getDataCode?db=md02&code=MAM1NAM2M2MO&startDate=200001"))
    rs = d["RESULTSET"][0]["VALUES"]
    out = {f"{str(k)[:4]}-{str(k)[4:]}": v for k, v in zip(rs["SURVEY_DATES"], rs["VALUES"]) if v is not None}
    nxt = d.get("NEXTPOSITION")
    while nxt:
        d = json.loads(curl(f"https://www.stat-search.boj.or.jp/api/v1/getDataCode?db=md02&code=MAM1NAM2M2MO&startDate=200001&startPosition={nxt}"))
        rs = d["RESULTSET"][0]["VALUES"]
        out.update({f"{str(k)[:4]}-{str(k)[4:]}": v for k, v in zip(rs["SURVEY_DATES"], rs["VALUES"]) if v is not None})
        nxt = d.get("NEXTPOSITION")
    return out  # 100 Mio. JPY


def boe_m4():
    text = curl("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes"
                "&Datefrom=01/Jan/2000&Dateto=now&SeriesCodes=LPMAUYN&CSVF=TN&UsingCodes=Y")
    out = {}
    for d, v in list(csv.reader(io.StringIO(text)))[1:]:
        if v.strip():
            out[datetime.strptime(d, "%d %b %Y").strftime("%Y-%m")] = float(v)
    return out  # Mio. GBP


MAX_CARRY = 2  # Monate, die ein hinterherhinkender Wert (z. B. UK M4) fortgeschrieben werden darf


def build():
    us, ez, jp, uk = fred("M2SL"), ecb_m2(), boj_m2(), boe_m4()
    eurusd, jpyusd, gbpusd = fred("EXUSEU"), fred("EXJPUS"), fred("EXUSUK")
    local = {"US": us, "EZ": ez, "JP": jp, "UK": uk}
    to_usd = {  # Monat, lokaler Wert -> USD Billionen (None, wenn der Kurs fehlt)
        "US": lambda m, v: v / 1e3,
        "EZ": lambda m, v: v * 1e6 * eurusd[m] / 1e12 if m in eurusd else None,
        "JP": lambda m, v: v * 1e8 / jpyusd[m] / 1e12 if m in jpyusd else None,
        "UK": lambda m, v: v * 1e6 * gbpusd[m] / 1e12 if m in gbpusd else None,
    }

    def months_between(a, b):
        return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:]) - int(a[5:])

    parts = {k: {} for k in local}
    est = {}
    for m in sorted(set().union(*local.values())):
        vals, carried = {}, []
        for k, src in local.items():
            if m in src:
                v = to_usd[k](m, src[m])
            else:  # letzter bekannter Wert, mit dem aktuellen Kurs umgerechnet
                prev = [p for p in src if p < m and months_between(p, m) <= MAX_CARRY]
                v = to_usd[k](m, src[max(prev)]) if prev else None
                if v is not None:
                    carried.append(k)
            if v is None:
                break
            vals[k] = v
        else:
            if len(carried) <= 1:
                for k, v in vals.items():
                    parts[k][m] = v
                if carried:
                    est[m] = carried
    months = sorted(parts["US"])
    total = {m: sum(p[m] for p in parts.values()) for m in months}
    level = [(f"{m}-01", round(total[m], 3)) for m in months]
    yoy = []
    for i, m in enumerate(months):
        prev = f"{int(m[:4]) - 1}{m[4:]}"
        if prev in total:
            yoy.append((f"{m}-01", round((total[m] / total[prev] - 1) * 100, 3)))
    series = {
        "GLOBALM2": {"name": "Global M2 G4 (USD Bio.)", "group": "money", "unit": "USD Bio.", "transform": "level",
                     "points": level, "est": est},
        "GLOBALM2_YOY": {"name": "Global M2 G4 (YoY)", "group": "money", "unit": "%", "transform": "yoy", "points": yoy},
    }
    for k, p in parts.items():
        series[f"M2_{k}_USD"] = {"name": f"M2 {k} (USD Bio.)", "group": "money", "unit": "USD Bio.", "transform": "level",
                                 "points": [(f"{m}-01", round(p[m], 3)) for m in months]}
    return series


if __name__ == "__main__":
    s = build()
    for k, v in s.items():
        print(k, len(v["points"]), v["points"][0], v["points"][-1])
