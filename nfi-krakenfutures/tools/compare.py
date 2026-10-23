"""Vergleichstabelle aus den Backtest-Logs.
usage: compare.py [PREFIX] STRAT [STRAT ...]   (Logs: /root/ft_workdir/logs/PREFIX_STRAT_FENSTER.log)
Ausgabe je Fenster: Gewinn % / Drawdown %.  PREFIX per Umgebungsvariable PREFIX (Standard: ref)."""
import glob, os, re, sys
LOGS = "/root/ft_workdir/logs"
ORDER = ["w1", "w2", "w2c", "w4a", "w3", "val", "h1", "h2"]
prefix = os.environ.get("PREFIX", "ref")
strats = sys.argv[1:]
print(f"{'strategy':26s}" + "".join(f"{w:>14s}" for w in ORDER) + "   maxDD")
for s in strats:
    cells, dds = [], []
    for w in ORDER:
        f = f"{LOGS}/{prefix}_{s}_{w}.log"
        val = "-"
        if os.path.exists(f):
            for line in open(f, errors="ignore"):
                if line.startswith("│ " + s + " ") or line.startswith("│ " + s + "│"):
                    p = [x.strip() for x in line.strip("│\n ").split("│")]
                    dd = re.search(r"([\d.]+)%", p[-1])
                    val = f"{float(p[4]):.1f}/{float(dd.group(1)):.1f}"
                    dds.append(float(dd.group(1)))
        cells.append(f"{val:>14s}")
    print(f"{s[-26:]:26s}" + "".join(cells) + f"   {max(dds) if dds else 0:.1f}")
