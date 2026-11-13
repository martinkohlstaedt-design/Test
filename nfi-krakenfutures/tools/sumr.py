"""usage: python sumr.py PREFIX... -> Tabelle Gewinn/DD je Strategie und Fenster aus logs/PREFIX_<w>.out"""
import sys, re, collections
W = ["w1", "w2", "w2c", "w4a", "w3", "val", "h1", "h2"]
res = collections.OrderedDict()
for p in sys.argv[1:]:
    for w in W:
        try:
            lines = open(f"/root/ft_workdir/logs/{p}_{w}.out").read().splitlines()
        except FileNotFoundError:
            continue
        for l in lines:
            c = l.split("│")
            if len(c) > 8:
                name = c[1].strip() + ("" if p in ("okf", "r4") else f"[{p}]")
                prof = float(c[5]); dd = float(re.findall(r"([\d.]+)%", c[8])[0])
                res.setdefault(name, {})[w] = (prof, dd)
print(f"{'Strategie':26s}" + "".join(f"{w:>12s}" for w in W) + "   Summe  maxDD  Train  Test")
for n, d in res.items():
    s = sum(v[0] for v in d.values()); m = max(v[1] for v in d.values())
    tr = sum(d[w][0] for w in W[:5] if w in d); te = sum(d[w][0] for w in W[5:] if w in d)
    print(f"{n:26s}" + "".join(f"{d[w][0]:7.1f}/{d[w][1]:4.1f}" if w in d else " " * 12 for w in W) + f" {s:7.1f} {m:6.1f} {tr:6.1f} {te:6.1f}")
