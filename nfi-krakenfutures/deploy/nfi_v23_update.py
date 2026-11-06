#!/usr/bin/env python3
"""Update v13 -> v23 (Grind x3) fuer den Kraken-Futures-NFI-Bot.

Ausfuehren im Ordner ~/nfi-krakenfutures-live (Bot vorher stoppen):
    python3 ~/nfi_v23_update.py

Was passiert:
- Backups: NFI_KF_Variants.py.vorv23 und docker-compose.yml.vorv23
- haengt die Klasse NFI_KF_V23_Grind3 an user_data/strategies/NFI_KF_Variants.py an
  (nur falls noch nicht vorhanden)
- stellt in docker-compose.yml --strategy NFI_KF_V13 auf NFI_KF_V23_Grind3 um
config.json und die Datenbank werden NICHT angefasst.
Rueckweg: Dateien *.vorv23 zurueckkopieren (siehe Ausgabe am Ende).
"""
import shutil
import sys
from pathlib import Path

STRAT = Path("user_data/strategies/NFI_KF_Variants.py")
COMPOSE = Path("docker-compose.yml")

ADDON = '''


# ============================================================================
# v23 = v13 + dreifacher Einsatz fuer Erst-Entries im Grind-Modus (Tag 120):
# ca. 12 % statt 4 % des Kontos als Marge. Alles andere wie v13.
# ============================================================================

class NFI_KF_V23_Grind3(NFI_KF_V13):
    """v13, aber Erst-Entries im Grind-Modus (Tag 120) mit dem 3-fachen Einsatz."""
    _GRIND_SCALE = 3.0

    def _scale_for(self, entry_tag):
        tags = (entry_tag or "").split()
        if tags and all(c in self.long_grind_mode_tags for c in tags):
            return self._GRIND_SCALE
        return super()._scale_for(entry_tag)
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
    if "class NFI_KF_V13(" not in code or "def _scale_for(" not in code:
        fail("In NFI_KF_Variants.py fehlt NFI_KF_V13 - ist v13 eingespielt?")
    already = "class NFI_KF_V23_Grind3(" in code
    if "--strategy NFI_KF_V13" not in compose and "--strategy NFI_KF_V23_Grind3" not in compose:
        fail("docker-compose.yml enthaelt weder NFI_KF_V13 noch NFI_KF_V23_Grind3.")

    for path in (STRAT, COMPOSE):
        backup = Path(str(path) + ".vorv23")
        if backup.exists():
            print("Backup existiert schon, bleibt unveraendert: " + str(backup))
        else:
            shutil.copy2(path, backup)
            print("Backup angelegt: " + str(backup))

    if already:
        print("NFI_KF_V23_Grind3 ist schon in der Strategie-Datei - nichts angehaengt.")
    else:
        new_code = code + ADDON
        compile(new_code, str(STRAT), "exec")  # Syntax-Check vor dem Schreiben
        STRAT.write_text(new_code)
        print("v23-Klasse an NFI_KF_Variants.py angehaengt.")

    COMPOSE.write_text(compose.replace("--strategy NFI_KF_V13", "--strategy NFI_KF_V23_Grind3"))
    for line in COMPOSE.read_text().splitlines():
        if "--strategy" in line:
            print("docker-compose.yml:" + line)
    print("FERTIG. Jetzt: docker compose up -d")
    print("Rueckweg: cp user_data/strategies/NFI_KF_Variants.py.vorv23 user_data/strategies/NFI_KF_Variants.py "
          "&& cp docker-compose.yml.vorv23 docker-compose.yml && docker compose up -d")


if __name__ == "__main__":
    main()
