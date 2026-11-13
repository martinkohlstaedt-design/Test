#!/usr/bin/env python3
"""Update v23F -> v23L: Liquidationspreis fuer Kraken Futures selbst berechnen.

Kraken liefert freqtrade keinen Liquidationspreis (in der Datenbank immer None).
Folge: NFIs Rettungslogik nahe der Liquidation greift live nie (im Backtest schon).
v23L berechnet den Preis live genauso wie der Backtest und warnt per Telegram,
wenn der Kurs naeher als 10 % an die Liquidation kommt.

Ausfuehren im Ordner ~/nfi-krakenfutures-live (Bot vorher stoppen):
    python3 ~/nfi_v23l_update.py

- Backups: NFI_KF_Variants.py.vorv23l und docker-compose.yml.vorv23l
- haengt _LiqAwareMixin und NFI_KF_V23L an (nur falls noch nicht vorhanden)
- stellt --strategy NFI_KF_V23F auf NFI_KF_V23L um
config.json und Datenbank werden NICHT angefasst.
"""
import shutil
import sys
from pathlib import Path

STRAT = Path("user_data/strategies/NFI_KF_Variants.py")
COMPOSE = Path("docker-compose.yml")

ADDON = '''


# ============================================================================
# v23L = v23F + Liquidationspreis selbst berechnen. Kraken liefert freqtrade
# keinen Liquidationspreis (live None); im Backtest rechnet freqtrade ihn aus
# Krakens Margin-Stufen. Ohne ihn greift NFIs Rettungslogik nahe der
# Liquidation live nie. Hier wird er live genauso berechnet wie im Backtest;
# zusaetzlich Telegram-Warnung, wenn der Kurs naeher als 10 % an die
# Liquidation kommt (je Trade hoechstens alle 6 Stunden).
# ============================================================================

class _LiqAwareMixin:
    _LIQ_WARN = 0.10
    _liq_warned = None

    def _estimate_liq(self, trade):
        ex = self.dp._exchange
        return ex.dry_run_liquidation_price(
            pair=trade.pair, open_rate=trade.open_rate, is_short=trade.is_short,
            amount=trade.amount, stake_amount=trade.stake_amount, leverage=trade.leverage,
            wallet_balance=trade.stake_amount, open_trades=[])

    def adjust_trade_position(self, trade, current_time, current_rate, *args, **kwargs):
        try:
            lp = self._estimate_liq(trade)
            if lp:
                trade.set_liquidation_price(lp)
                if (self.config["runmode"].value in ("live", "dry_run") and not trade.is_short
                        and current_rate < lp * (1 + self._LIQ_WARN)):
                    if self._liq_warned is None:
                        self._liq_warned = {}
                    last = self._liq_warned.get(trade.id)
                    if last is None or (current_time - last).total_seconds() > 6 * 3600:
                        self._liq_warned[trade.id] = current_time
                        self.dp.send_msg(f"LIQUIDATIONS-WARNUNG {trade.pair}: Kurs {current_rate:.6g}, "
                                         f"Liquidation ca. {lp:.6g} ({(current_rate / lp - 1) * 100:.1f} % Abstand)")
        except Exception:
            pass
        return super().adjust_trade_position(trade, current_time, current_rate, *args, **kwargs)


class NFI_KF_V23L(_LiqAwareMixin, NFI_KF_V23F):
    """v23F + selbst berechneter Liquidationspreis (wie im Backtest) + Telegram-Warnung."""
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
    if "class NFI_KF_V23F(" not in code:
        fail("In NFI_KF_Variants.py fehlt NFI_KF_V23F - ist v23F eingespielt?")
    already = "class NFI_KF_V23L(" in code
    if "--strategy NFI_KF_V23F" not in compose and "--strategy NFI_KF_V23L" not in compose:
        fail("docker-compose.yml enthaelt weder NFI_KF_V23F noch NFI_KF_V23L.")

    for path in (STRAT, COMPOSE):
        backup = Path(str(path) + ".vorv23l")
        if backup.exists():
            print("Backup existiert schon, bleibt unveraendert: " + str(backup))
        else:
            shutil.copy2(path, backup)
            print("Backup angelegt: " + str(backup))

    if already:
        print("NFI_KF_V23L ist schon in der Strategie-Datei - nichts angehaengt.")
    else:
        new_code = code + ADDON
        compile(new_code, str(STRAT), "exec")
        STRAT.write_text(new_code)
        print("v23L-Klasse an NFI_KF_Variants.py angehaengt.")

    COMPOSE.write_text(compose.replace("--strategy NFI_KF_V23F", "--strategy NFI_KF_V23L"))
    for line in COMPOSE.read_text().splitlines():
        if "--strategy" in line:
            print("docker-compose.yml:" + line)
    print("FERTIG. Jetzt: docker compose up -d")
    print("Rueckweg: cp user_data/strategies/NFI_KF_Variants.py.vorv23l user_data/strategies/NFI_KF_Variants.py "
          "&& cp docker-compose.yml.vorv23l docker-compose.yml && docker compose up -d")


if __name__ == "__main__":
    main()
