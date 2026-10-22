#!/usr/bin/env python3
"""Update v12 -> v13 fuer den Kraken-Futures-NFI-Bot.

Ausfuehren im Ordner ~/nfi-krakenfutures-live (Bot vorher stoppen):
    python3 ~/nfi_v13_update.py

Was passiert:
- Backups: NFI_KF_Variants.py.vorv13 und docker-compose.yml.vorv13
- haengt die Klassen _StaleBEMixin, NFI_KF_V14_Stale72 und NFI_KF_V13 an
  user_data/strategies/NFI_KF_Variants.py an (nur falls noch nicht vorhanden)
- stellt in docker-compose.yml --strategy NFI_KF_V12 auf NFI_KF_V13 um
config.json und die Datenbank werden NICHT angefasst.
"""
import shutil
import sys
from pathlib import Path

STRAT = Path("user_data/strategies/NFI_KF_Variants.py")
COMPOSE = Path("docker-compose.yml")

ADDON = '''


# ============================================================================
# v13 = v12 + Breakeven-Exit: haengt ein Trade laenger als 72h und ist der
# Gesamt-Trade (inkl. Nachkaeufe/Teilverkaeufe) wieder mindestens +0,5 % im
# Plus, wird er geschlossen.
# ============================================================================

class _StaleBEMixin:
    _STALE_HOURS = 48
    _STALE_MIN_PROFIT = 0.005

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        if (current_time - trade.open_date_utc).total_seconds() > self._STALE_HOURS * 3600:
            try:
                total = trade.calculate_profit(current_rate).total_profit_ratio
            except Exception:
                total = current_profit
            if total >= self._STALE_MIN_PROFIT:
                return "stale_be"
        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)


class NFI_KF_V14_Stale72(_StaleBEMixin, NFI_KF_V12):
    """v12 + Breakeven-Exit nach 72h."""
    _STALE_HOURS = 72


class NFI_KF_V13(NFI_KF_V14_Stale72):
    """v13 (live): v12 + Exit zum Einstandspreis (+0,5 %), wenn ein Trade nach
    72h wieder im Plus ist."""
'''


def fail(msg):
    print("FEHLER: " + msg)
    print("Es wurde nichts veraendert. Bitte die Ausgabe an Claude schicken.")
    sys.exit(1)


def main():
    if not STRAT.is_file() or not COMPOSE.is_file():
        fail("Bitte im Ordner ~/nfi-krakenfutures-live ausfuehren "
             "(cd ~/nfi-krakenfutures-live).")
    code = STRAT.read_text()
    compose = COMPOSE.read_text()
    if "class NFI_KF_V12(" not in code:
        fail("In NFI_KF_Variants.py fehlt NFI_KF_V12 - ist v12 eingespielt?")
    already = "class NFI_KF_V13(" in code
    if "--strategy NFI_KF_V12" not in compose and "--strategy NFI_KF_V13" not in compose:
        fail("docker-compose.yml enthaelt weder NFI_KF_V12 noch NFI_KF_V13.")

    for path in (STRAT, COMPOSE):
        backup = Path(str(path) + ".vorv13")
        if backup.exists():
            print("Backup existiert schon, bleibt unveraendert: " + str(backup))
        else:
            shutil.copy2(path, backup)
            print("Backup angelegt: " + str(backup))

    if already:
        print("NFI_KF_V13 ist schon in der Strategie-Datei - nichts angehaengt.")
    else:
        new_code = code + ADDON
        compile(new_code, str(STRAT), "exec")  # Syntax-Check vor dem Schreiben
        STRAT.write_text(new_code)
        print("v13-Klassen an NFI_KF_Variants.py angehaengt.")

    COMPOSE.write_text(compose.replace("--strategy NFI_KF_V12", "--strategy NFI_KF_V13"))
    for line in COMPOSE.read_text().splitlines():
        if "--strategy" in line:
            print("docker-compose.yml:" + line)
    print("FERTIG. Jetzt: docker compose up -d")


if __name__ == "__main__":
    main()
