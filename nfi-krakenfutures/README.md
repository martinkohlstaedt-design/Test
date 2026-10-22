# NFI Kraken Futures – Strategie-Varianten und Testumgebung

Eigene Varianten der NostalgiaForInfinityX8 für Kraken Futures. Ergebnisse und
Einschränkungen: `docs/ERGEBNISSE.md`.

## Inhalt

- `strategies/NFI_KF_Variants.py` – alle Varianten (aktueller Stand: `NFI_KF_V13`).
  Braucht die Datei `NostalgiaForInfinityX8.py` im selben Ordner.
- `deploy/nfi_v13_update.py` – macht auf dem Server aus v12 die Version v13
  (legt Sicherungen an, ändert weder `config.json` noch die Datenbank).
- `deploy/ANLEITUNG_v12.md`, `deploy/docker-compose.v13.yml` – Update-Anleitung und Compose-Datei.

## Testumgebung neu aufbauen

```bash
python3 -m venv ~/freqtrade-venv
~/freqtrade-venv/bin/pip install "freqtrade==2026.8"
mkdir -p ~/ft_workdir/user_data/strategies
# NFI exakt in der Live-Version (v18.0.61 = Commit 8a0f555):
git clone --filter=blob:none https://github.com/iterativv/NostalgiaForInfinity nfi_src
git -C nfi_src show 8a0f555:NostalgiaForInfinityX8.py > ~/ft_workdir/user_data/strategies/NostalgiaForInfinityX8.py
cp strategies/NFI_KF_Variants.py ~/ft_workdir/user_data/strategies/
```

Kursdaten (5m-Futures, 1h-Funding/Mark) laden:

```bash
freqtrade download-data --config <config> --userdir user_data \
  --pairs <Liste> --timeframes 5m --trading-mode futures --timerange 20220801-
```

Hinweise:

- In Cloud-Umgebungen mit Proxy in der Config unter `exchange` setzen:
  `"ccxt_config"` und `"ccxt_async_config"` je `{"aiohttp_trust_env": true,
  "requests_trust_env": true, "options": {"defaultType": "swap"}}` und die Umgebungsvariablen
  `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` auf das CA-Bundle der Umgebung setzen.
- Backtest: `freqtrade backtesting --config <config> --strategy NFI_KF_V13
  --strategy-path user_data/strategies --timerange 20250926-20260315 --timeframe 5m --cache none`.
  Immer nur ein Backtest gleichzeitig (Arbeitsspeicher).
- Die Config enthält Börsen-Schlüssel und gehört **nicht** ins Repo (`.gitignore`).
