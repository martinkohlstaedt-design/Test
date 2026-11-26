#!/usr/bin/env python3
"""S&P-500-Bewertung von multpl.com (Shiller-/S&P-Daten, HTML-Tabellen, monatlich).

multpl.com ist eine Drittquelle ohne API; Struktur kann sich ändern.
Gewinnrendite minus 10J-Rendite (FRED GS10) ist eine einfache Risikoprämie.
"""
import csv, io, re, subprocess, time
from datetime import datetime

PAGES = {
    "SPX_PE": ("S&P 500 KGV (trailing)", "s-p-500-pe-ratio"),
    "SPX_CAPE": ("Shiller-KGV (CAPE)", "shiller-pe"),
    "SPX_EY": ("S&P 500 Gewinnrendite", "s-p-500-earnings-yield"),
}
ROW = re.compile(r"<td>\s*([A-Z][a-z]{2} \d{1,2}, \d{4})\s*</td>\s*<td>(.*?)</td>", re.S)


def curl(url, retries=4, ua=()):
    for attempt in range(retries):
        try:
            return subprocess.run(["curl", "-sSL", "--fail", "-m", "60", *ua, url],
                                  capture_output=True, text=True, check=True).stdout
        except subprocess.CalledProcessError:
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def multpl(slug):
    html = curl(f"https://www.multpl.com/{slug}/table/by-month", ua=("-A", "Mozilla/5.0"))
    out = {}
    for d, raw in ROW.findall(html):
        m = re.search(r"-?\d+(?:\.\d+)?", re.sub(r"<[^>]*>|&#x2002;|,", "", raw))
        if m:
            out[datetime.strptime(d, "%b %d, %Y").strftime("%Y-%m")] = float(m.group())
    if len(out) < 100:
        raise ValueError(f"{slug}: nur {len(out)} Zeilen geparst")
    return out


def gs10():
    text = curl("https://fred.stlouisfed.org/graph/fredgraph.csv?id=GS10&cosd=2000-01-01")
    return {d[:7]: float(v) for d, v in list(csv.reader(io.StringIO(text)))[1:] if v not in ("", ".")}


def build():
    data = {k: multpl(slug) for k, (_, slug) in PAGES.items()}
    series = {}
    for k, (name, _) in PAGES.items():
        pts = [(f"{m}-01", v) for m, v in sorted(data[k].items()) if m >= "2000-01"]
        series[k] = {"name": name, "group": "valuation", "unit": "%" if k == "SPX_EY" else "x", "transform": "level", "points": pts}
    y = gs10()
    erp = [(f"{m}-01", round(v - y[m], 3)) for m, v in sorted(data["SPX_EY"].items()) if m in y and m >= "2000-01"]
    series["SPX_ERP"] = {"name": "Gewinnrendite minus 10J-Rendite", "group": "valuation", "unit": "pp",
                         "transform": "level", "points": erp}
    return series


if __name__ == "__main__":
    for k, v in build().items():
        print(k, len(v["points"]), v["points"][0], v["points"][-1])
