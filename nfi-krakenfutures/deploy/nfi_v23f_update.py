#!/usr/bin/env python3
"""Fix fuer v23: NFI-Timeout-Pruefung bei Kraken Futures (v23 -> v23F).

Problem im Live-Log: "TypeError: unsupported operand type(s) for *: 'NoneType' and 'float'
calling check_exit_timeout". Kraken Futures liefert fuer Orders keinen 'price' (None);
NFI rechnet order.price * 0.97 -> Fehler. Folge: NFIs Regel "Order abbrechen, wenn der
Kurs > 3 % weggelaufen ist" greift nie (der normale 10-min-Timeout von freqtrade schon).
Der Fix nimmt den angefragten Orderpreis (ft_price) bzw. safe_price.

Ausfuehren im Ordner ~/nfi-krakenfutures-live (Bot vorher stoppen):
    python3 ~/nfi_v23f_update.py

- Backups: NFI_KF_Variants.py.vorv23f und docker-compose.yml.vorv23f
- haengt _OrderTimeoutFixMixin und NFI_KF_V23F an (nur falls noch nicht vorhanden)
- stellt --strategy NFI_KF_V23_Grind3 auf NFI_KF_V23F um
config.json und Datenbank werden NICHT angefasst.
"""
import shutil
import sys
from pathlib import Path

STRAT = Path("user_data/strategies/NFI_KF_Variants.py")
COMPOSE = Path("docker-compose.yml")

ADDON = '''


# ============================================================================
# v23F = v23 + Fix: Kraken Futures liefert order.price = None. NFIs
# check_entry_timeout/check_exit_timeout rechnen order.price * 1.03 und werfen
# TypeError; hier mit dem angefragten Preis (ft_price) bzw. safe_price.
# ============================================================================

class _OrderTimeoutFixMixin:
    def _order_ref_price(self, order):
        for attr in ("price", "ft_price", "safe_price", "average"):
            v = getattr(order, attr, None)
            if v:
                return float(v)
        return None

    def _top_of_book(self, pair):
        ob = self.dp.orderbook(pair, 1)
        return ob["bids"][0][0], ob["asks"][0][0]

    def check_entry_timeout(self, pair, trade, order, current_time, **kwargs):
        p = self._order_ref_price(order)
        if p is None:
            return False
        try:
            bids, asks = self._top_of_book(pair)
        except Exception:
            return False
        if trade.is_short:
            return asks < p * 0.97
        return bids > p * 1.03

    def check_exit_timeout(self, pair, trade, order, current_time, **kwargs):
        if order.ft_order_tag is not None and order.ft_order_tag == "force_exit":
            return False
        p = self._order_ref_price(order)
        if p is None:
            return False
        try:
            bids, asks = self._top_of_book(pair)
        except Exception:
            return False
        if trade.is_short:
            return bids > p * 1.03
        return asks < p * 0.97


class NFI_KF_V23F(_OrderTimeoutFixMixin, NFI_KF_V23_Grind3):
    """v23 (Grind x3) + Fix der Order-Timeout-Pruefung fuer Kraken Futures."""
'''


def fail(msg):
    print("FEHLER: " + msg)
    print("Es wurde nichts veraendert. Bitte die Ausgabe an Claude schicken.")
    sys.exit(1)


def main():
    if not STRAT.is_file() or not COMPOSE.is_file():
        fail("Bitte im Ordner ~/nfi-krakenfutures-live ausfuehren (cd ~/nfi-krakenfutures-live).")
    code = STRAT.read_text()
    compose = COMPOSE.read_text()
    if "class NFI_KF_V23_Grind3(" not in code:
        fail("In NFI_KF_Variants.py fehlt NFI_KF_V23_Grind3 - ist v23 eingespielt?")
    already = "class NFI_KF_V23F(" in code
    if "--strategy NFI_KF_V23_Grind3" not in compose and "--strategy NFI_KF_V23F" not in compose:
        fail("docker-compose.yml enthaelt weder NFI_KF_V23_Grind3 noch NFI_KF_V23F.")

    for path in (STRAT, COMPOSE):
        backup = Path(str(path) + ".vorv23f")
        if backup.exists():
            print("Backup existiert schon, bleibt unveraendert: " + str(backup))
        else:
            shutil.copy2(path, backup)
            print("Backup angelegt: " + str(backup))

    if already:
        print("NFI_KF_V23F ist schon in der Strategie-Datei - nichts angehaengt.")
    else:
        new_code = code + ADDON
        compile(new_code, str(STRAT), "exec")
        STRAT.write_text(new_code)
        print("v23F-Klasse an NFI_KF_Variants.py angehaengt.")

    COMPOSE.write_text(compose.replace("--strategy NFI_KF_V23_Grind3", "--strategy NFI_KF_V23F"))
    for line in COMPOSE.read_text().splitlines():
        if "--strategy" in line:
            print("docker-compose.yml:" + line)
    print("FERTIG. Jetzt: docker compose up -d")
    print("Rueckweg: cp user_data/strategies/NFI_KF_Variants.py.vorv23f user_data/strategies/NFI_KF_Variants.py "
          "&& cp docker-compose.yml.vorv23f docker-compose.yml && docker compose up -d")


if __name__ == "__main__":
    main()
