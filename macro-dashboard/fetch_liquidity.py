#!/usr/bin/env python3
"""Zentralbank-Liquidität (Fed netto + EZB + BoJ) in USD-Billionen, wöchentlich (Mittwoch), ab 2000.

Fed netto = Bilanzsumme (WALCL) - Treasury-Konto (WTREGEN) - Reverse Repo (RRPONTSYD)
EZB       = Bilanzsumme (ECBASSETSW, Mio. EUR) x EUR/USD (DEXUSEU)
BoJ       = Bilanzsumme (JPNASSETS, 100 Mio. JPY, monatlich) / USD/JPY (DEXJPUS)
Impuls    = Veränderung der Summe zum Vorjahr in Prozent.
Alle Quellen: FRED (CSV ohne API-Key). Fehlende Werte werden mit dem letzten bekannten fortgeschrieben.
"""
import bisect, csv, io, json, subprocess, sys, time
from datetime import date, datetime, timedelta, timezone

START = "2000-01-01"
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}&cosd=" + START


def fred(sid, retries=4):
    for attempt in range(retries):
        try:
            text = subprocess.run(["curl", "-sS", "--fail", "-m", "90", URL.format(id=sid)],
                                  capture_output=True, text=True, check=True).stdout
            rows = [(d, float(v)) for d, v in list(csv.reader(io.StringIO(text)))[1:] if v not in ("", ".")]
            if not rows:
                raise ValueError("leer")
            return rows
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** (attempt + 1))


class Series:
    """Letzter bekannter Wert am oder vor einem Datum."""
    def __init__(self, rows):
        self.d = [r[0] for r in rows]
        self.v = [r[1] for r in rows]

    def at(self, day):
        i = bisect.bisect_right(self.d, day) - 1
        return self.v[i] if i >= 0 else None


def build():
    walcl, tga, rrp = Series(fred("WALCL")), Series(fred("WTREGEN")), Series(fred("RRPONTSYD"))
    ecb, boj = Series(fred("ECBASSETSW")), Series(fred("JPNASSETS"))
    eur, jpy = Series(fred("DEXUSEU")), Series(fred("DEXJPUS"))
    last_day = max(walcl.d[-1], tga.d[-1])          # jüngster Stichtag, für den Fed-Daten vorliegen
    day = date(2000, 1, 5)                          # ein Mittwoch
    end = date.fromisoformat(last_day)
    rows = []
    while day <= end:
        k = day.isoformat()
        w, t, r, e, b, fe, fj = walcl.at(k), tga.at(k), rrp.at(k), ecb.at(k), boj.at(k), eur.at(k), jpy.at(k)
        if None not in (w, t, e, b, fe, fj):
            fed = (w - t - (r or 0) * 1000) / 1e6
            ecb_usd = e * fe / 1e6
            boj_usd = b * 1e8 / fj / 1e12
            rows.append((k, round(fed, 3), round(ecb_usd, 3), round(boj_usd, 3)))
        day += timedelta(days=7)
    total = {k: round(f + e + b, 3) for k, f, e, b in rows}
    keys = sorted(total)
    idx = {k: i for i, k in enumerate(keys)}
    yoy = []
    for k in keys:
        prev = (date.fromisoformat(k) - timedelta(days=364)).isoformat()
        if prev in total:
            yoy.append((k, round((total[k] / total[prev] - 1) * 100, 3)))
    series = {
        "LIQ_TOTAL": {"name": "Total", "points": [(k, total[k]) for k in keys]},
        "LIQ_YOY": {"name": "Impuls YoY %", "points": yoy},
        "LIQ_FED": {"name": "Fed netto", "points": [(k, f) for k, f, _, _ in rows]},
        "LIQ_ECB": {"name": "EZB", "points": [(k, e) for k, _, e, _ in rows]},
        "LIQ_BOJ": {"name": "BoJ", "points": [(k, b) for k, _, _, b in rows]},
    }
    return {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "series": series}


def keep_early_history(data, path):
    """Zeitraum vor Dez. 2002 (kein TGA bei FRED, Fed-Näherung) aus der vorhandenen Datei übernehmen."""
    try:
        old = json.load(open(path))["series"]
    except Exception:
        return data
    for k, v in data["series"].items():
        if k in old and v["points"]:
            first = v["points"][0][0]
            v["points"] = [tuple(p) for p in old[k]["points"] if p[0] < first] + v["points"]
    return data


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "data/liq.json"
    data = keep_early_history(build(), out)
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    for k, v in data["series"].items():
        print(k, len(v["points"]), v["points"][0], v["points"][-1])
