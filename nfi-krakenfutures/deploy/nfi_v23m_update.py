#!/usr/bin/env python3
"""Update v23L -> v23M: Liquidationspreis zuverlaessig setzen + Fehler protokollieren.

Befund 01.11.2026: Unter v23L blieb liquidation_price live in der DB leer (WLD, XMR), obwohl die
Berechnung im Container funktioniert und WLD seit dem Update nachgekauft hat. v23L hat Fehler still
verschluckt. v23M setzt den Wert zusaetzlich in jedem Bot-Durchlauf (bot_loop_start, direkt vor
freqtrades Trade.commit), mit freqtrades Sicherheitspuffer (5 %), und schreibt Fehler ins Log.

Ausfuehren im Ordner ~/nfi-krakenfutures-live:
    python3 ~/nfi_v23m_update.py

- Backups: NFI_KF_Variants.py.vorv23m und docker-compose.yml.vorv23m
- haengt _LiqLoopMixin und NFI_KF_V23M an (nur falls noch nicht vorhanden)
- stellt --strategy NFI_KF_V23L auf NFI_KF_V23M um
config.json und Datenbank werden NICHT angefasst.
"""
import shutil
import sys
from pathlib import Path

STRAT = Path("user_data/strategies/NFI_KF_Variants.py")
COMPOSE = Path("docker-compose.yml")

ADDON = '''

# ============================================================================
# v23M = v23L + Liquidationspreis zusaetzlich in jedem Bot-Durchlauf setzen
# (bot_loop_start, direkt vor freqtrades Trade.commit) und Fehler protokollieren.
# Hintergrund: Unter v23L blieb liquidation_price live in der DB leer, obwohl die
# Berechnung im Container funktioniert; v23L hat Fehler still verschluckt.
# ============================================================================

import logging as _v23m_logging
_v23m_log = _v23m_logging.getLogger("NFI_KF_V23M")


class _LiqLoopMixin:
    _liq_state = None

    def _liq_loop_update(self, current_time):
        from freqtrade.persistence import Trade as _T
        if self._liq_state is None:
            self._liq_state = {}
        for t in _T.get_open_trades():
            if not t.has_open_position or t.is_short:
                continue
            try:
                lp = self._estimate_liq(t)
            except Exception as e:
                key = ("err", t.pair, type(e).__name__)
                if key not in self._liq_state:
                    self._liq_state[key] = True
                    _v23m_log.warning(f"V23M: Liquidationspreis {t.pair} nicht berechenbar: {type(e).__name__}: {e}")
                continue
            if not lp:
                continue
            before = t.liquidation_price
            t.set_liquidation_price(lp)
            last = self._liq_state.get(t.id)
            if last is None or abs(last / lp - 1) > 0.005:
                self._liq_state[t.id] = lp
                _v23m_log.info(f"V23M: Liquidationspreis {t.pair} = {lp:.6g} (vorher {before}, "
                               f"Einstieg {t.open_rate:.6g}, Hebel {t.leverage})")
            try:
                df, _ = self.dp.get_analyzed_dataframe(t.pair, self.timeframe)
                rate = float(df["close"].iloc[-1])
                if rate < lp * (1 + self._LIQ_WARN):
                    if self._liq_warned is None:
                        self._liq_warned = {}
                    w = self._liq_warned.get(t.id)
                    if w is None or (current_time - w).total_seconds() > 6 * 3600:
                        self._liq_warned[t.id] = current_time
                        self.dp.send_msg(f"LIQUIDATIONS-WARNUNG {t.pair}: Kurs {rate:.6g}, "
                                         f"Liquidation ca. {lp:.6g} ({(rate / lp - 1) * 100:.1f} % Abstand)")
            except Exception:
                pass

    def bot_loop_start(self, current_time, **kwargs):
        try:
            if self.config["runmode"].value in ("live", "dry_run"):
                self._liq_loop_update(current_time)
        except Exception as e:
            _v23m_log.warning(f"V23M: bot_loop_start Fehler: {type(e).__name__}: {e}")
        return super().bot_loop_start(current_time=current_time, **kwargs)


class NFI_KF_V23M(_LiqLoopMixin, NFI_KF_V23L):
    """v23L + Liquidationspreis je Durchlauf setzen (vor Trade.commit) + Fehler-Log.
    Mit freqtrades Sicherheitspuffer (liquidation_buffer, Standard 5 %) wie im Dry-Run."""

    def _estimate_liq(self, trade):
        lp = super()._estimate_liq(trade)
        if lp:
            buf = getattr(self.dp._exchange, "liquidation_buffer", 0.05) or 0.0
            d = abs(trade.open_rate - lp) * buf
            lp = lp - d if trade.is_short else lp + d
        return lp
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
    if "class NFI_KF_V23L(" not in code:
        fail("In NFI_KF_Variants.py fehlt NFI_KF_V23L - ist v23L eingespielt?")
    already = "class NFI_KF_V23M(" in code
    if "--strategy NFI_KF_V23L" not in compose and "--strategy NFI_KF_V23M" not in compose:
        fail("docker-compose.yml enthaelt weder NFI_KF_V23L noch NFI_KF_V23M.")

    for path in (STRAT, COMPOSE):
        backup = Path(str(path) + ".vorv23m")
        if backup.exists():
            print("Backup existiert schon, bleibt unveraendert: " + str(backup))
        else:
            shutil.copy2(path, backup)
            print("Backup angelegt: " + str(backup))

    if already:
        print("NFI_KF_V23M ist schon in der Strategie-Datei - nichts angehaengt.")
    else:
        new_code = code + ADDON
        compile(new_code, str(STRAT), "exec")
        STRAT.write_text(new_code)
        print("v23M-Klasse an NFI_KF_Variants.py angehaengt.")

    COMPOSE.write_text(compose.replace("--strategy NFI_KF_V23L", "--strategy NFI_KF_V23M"))
    for line in COMPOSE.read_text().splitlines():
        if "--strategy" in line:
            print("docker-compose.yml:" + line)
    print("FERTIG. Jetzt: docker compose up -d")
    print("Rueckweg: cp user_data/strategies/NFI_KF_Variants.py.vorv23m user_data/strategies/NFI_KF_Variants.py "
          "&& cp docker-compose.yml.vorv23m docker-compose.yml && docker compose up -d")


if __name__ == "__main__":
    main()
