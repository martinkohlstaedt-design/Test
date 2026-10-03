#!/usr/bin/env python3
"""Lädt US-Makrodaten von FRED (keyless CSV-Endpoint) und schreibt data/us.json."""
import csv, io, json, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone

START = "2000-01-01"
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}&cosd=" + START

# id, Name, Gruppe, Transformation, Einheit, Frequenz (Perioden pro Jahr), Downsample auf Wochen
SERIES = [
    # Wachstum
    ("GDPC1", "Reales BIP (YoY)", "growth", "yoy", "%", 4, False),
    ("INDPRO", "Industrieproduktion (YoY)", "growth", "yoy", "%", 12, False),
    ("RSAFS", "Einzelhandelsumsatz (YoY)", "growth", "yoy", "%", 12, False),
    ("UMCSENT", "Konsumentenstimmung (U. Michigan)", "growth", "level", "Index", 12, False),
    # Inflation
    ("CPIAUCSL", "CPI (YoY)", "inflation", "yoy", "%", 12, False),
    ("CPILFESL", "Kern-CPI (YoY)", "inflation", "yoy", "%", 12, False),
    ("PCEPILFE", "Kern-PCE (YoY)", "inflation", "yoy", "%", 12, False),
    ("T10YIE", "10J Breakeven-Inflation", "inflation", "level", "%", 252, True),
    # Arbeitsmarkt
    ("UNRATE", "Arbeitslosenquote", "labor", "level", "%", 12, False),
    ("PAYEMS", "Beschäftigung außerhalb Landwirtschaft (Δ pro Monat)", "labor", "diff", "Tsd.", 12, False),
    ("ICSA", "Erstanträge Arbeitslosenhilfe (wöchentlich)", "labor", "level", "Anträge", 52, False),
    ("CES0500000003", "Durchschnittl. Stundenlohn (YoY)", "labor", "yoy", "%", 12, False),
    # Geld & Liquidität
    ("M2SL", "Geldmenge M2 (YoY)", "money", "yoy", "%", 12, False),
    # Zinsen
    ("FEDFUNDS", "Fed Funds Rate", "rates", "level", "%", 12, False),
    ("DGS2", "2J Treasury-Rendite", "rates", "level", "%", 252, True),
    ("DGS10", "10J Treasury-Rendite", "rates", "level", "%", 252, True),
    ("T10Y2Y", "Zinskurve 10J–2J", "rates", "level", "pp", 252, True),
    ("T10Y3M", "Zinskurve 10J–3M", "rates", "level", "pp", 252, True),
    # Märkte
    ("SP500", "S&P 500", "markets", "level", "Punkte", 252, True),
    ("VIXCLS", "VIX", "markets", "level", "Punkte", 252, True),
    ("BAMLH0A0HYM2", "High-Yield Credit Spread", "markets", "level", "pp", 252, True),
    ("DTWEXBGS", "US-Dollar-Index (breit)", "markets", "level", "Index", 252, True),
    ("DCOILWTICO", "Rohöl WTI", "markets", "level", "USD", 252, True),
    # Rezession
    ("USREC", "NBER-Rezession", "recession", "level", "0/1", 12, False),
    ("SAHMREALTIME", "Sahm-Rule Indikator", "recession", "level", "pp", 12, False),
]


def fetch_csv(sid, retries=4):
    for attempt in range(retries):
        try:
            text = subprocess.run(
                ["curl", "-sS", "--fail", "-m", "90", URL.format(id=sid)],
                capture_output=True, text=True, check=True,
            ).stdout
            out = []
            for d, v in list(csv.reader(io.StringIO(text)))[1:]:
                if v in ("", "."):
                    continue
                out.append((d, float(v)))
            if not out:
                raise ValueError("leere Antwort")
            return out
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** (attempt + 1))


def transform(pts, kind, per):
    if kind == "level":
        return pts
    out = []
    if kind == "yoy":
        for i in range(per, len(pts)):
            prev = pts[i - per][1]
            if prev:
                out.append((pts[i][0], round((pts[i][1] / prev - 1) * 100, 3)))
    elif kind == "diff":
        for i in range(1, len(pts)):
            out.append((pts[i][0], round(pts[i][1] - pts[i - 1][1], 3)))
    return out


def weekly(pts):
    last = {}
    for d, v in pts:
        y, w, _ = date.fromisoformat(d).isocalendar()
        last[(y, w)] = (d, v)
    return [last[k] for k in sorted(last)]


def load(entry):
    sid, name, group, kind, unit, per, down = entry
    pts = transform(fetch_csv(sid), kind, per)
    if down:
        pts = weekly(pts)
    return sid, {"name": name, "group": group, "unit": unit, "transform": kind, "points": pts}


def main():
    result, failed = {}, []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {e[0]: ex.submit(load, e) for e in SERIES}
        for sid, fut in futures.items():
            try:
                _, data = fut.result()
                result[sid] = data
                print(f"ok   {sid:14s} {len(data['points']):5d} Punkte, letzter: {data['points'][-1]}")
            except Exception as e:
                failed.append(sid)
                print(f"FAIL {sid}: {e}", file=sys.stderr)
    ordered = {e[0]: result[e[0]] for e in SERIES if e[0] in result}
    try:
        import fetch_global_m2
        ordered.update(fetch_global_m2.build())
        print("ok   Global M2 (US, EZ, JP, UK)")
    except Exception as e:
        failed.append("GLOBALM2")
        print(f"FAIL Global M2: {e}", file=sys.stderr)
    payload = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "series": ordered}
    with open("data/us.json", "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    if failed:
        print("Fehlgeschlagen:", failed, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
