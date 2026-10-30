"""Kraken-Futures-Varianten von NFI_Fut_TieredLeverage/VolAdjStake/MemeCap aus
NFI_Variants.py, uebertragen auf Kraken's Pair-Format (XXX/USD:USD statt
XXX/USDT:USDT) und die tatsaechliche 44er Kraken-Coin-Liste (config_krakenfutures44_refreshed.json).
Gleiche Tier-Logik/Faktoren wie die validierten OKX-Varianten, nur die
Pair-Sets sind auf das kleinere, teilweise andere Kraken-Universum angepasst.
"""
from freqtrade.persistence import Trade
from NostalgiaForInfinityX8 import NostalgiaForInfinityX8


_LOW_VOL_PAIRS_KF = {"BTC/USD:USD", "ETH/USD:USD", "BNB/USD:USD", "LTC/USD:USD"}
_HIGH_VOL_PAIRS_KF = {
    "ONDO/USD:USD", "PEPE/USD:USD", "CRV/USD:USD", "INJ/USD:USD", "PENGU/USD:USD",
    "ZEC/USD:USD", "WLD/USD:USD", "UNI/USD:USD", "DASH/USD:USD", "NEAR/USD:USD",
    "TRUMP/USD:USD", "ARB/USD:USD", "RAY/USD:USD", "ENA/USD:USD", "XPL/USD:USD",
    "PUMP/USD:USD", "PONS/USD:USD",
}
_MEME_PAIRS_KF = {
    "PEPE/USD:USD", "SHIB/USD:USD", "DOGE/USD:USD",
    "PENGU/USD:USD", "TRUMP/USD:USD", "PUMP/USD:USD",
}
_MAX_MEME_SLOTS_KF = 2


class NFI_KF_TieredLeverage(NostalgiaForInfinityX8):
    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        base = super().leverage(pair, current_time, current_rate, proposed_leverage,
                                 max_leverage, entry_tag, side, **kwargs)
        if pair in _LOW_VOL_PAIRS_KF:
            factor = 5.0 / 3.0
        elif pair in _HIGH_VOL_PAIRS_KF:
            factor = 2.0 / 3.0
        else:
            factor = 1.0
        return min(base * factor, max_leverage)


class NFI_KF_VolAdjStake(NostalgiaForInfinityX8):
    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        base = super().custom_stake_amount(pair, current_time, current_rate, proposed_stake,
                                            min_stake, max_stake, leverage, entry_tag, side, **kwargs)
        if pair in _LOW_VOL_PAIRS_KF:
            factor = 1.3
        elif pair in _HIGH_VOL_PAIRS_KF:
            factor = 0.7
        else:
            factor = 1.0
        stake = base * factor
        if min_stake is not None and stake < min_stake:
            stake = min_stake
        if stake > max_stake:
            stake = max_stake
        return stake


class NFI_KF_TighterAbandon(NostalgiaForInfinityX8):
    """Gezielter Fix fuer das Half2/41-Coins Drawdown-Muster (NEAR -10.027 USD
    ueber 51 Tage, PUMP -6.711 USD): Bad-Trade-Controller deutlich frueher
    abbrechen lassen statt bei 14 Tagen/10% bzw. 25%-Struktur-Bruch."""
    bad_trade_controller_stale_min_age_days = 5.0
    bad_trade_controller_stale_min_adverse_move_pct = 6.0
    bad_trade_controller_structure_break_min_adverse_move_pct = 12.0


class NFI_KF_PositionCap(NostalgiaForInfinityX8):
    """Harter Cap: keine Einzelposition (inkl. aller Grind-/Rebuy-Nachkaeufe)
    darf mehr als 20% des aktuellen Gesamtkapitals an Margin binden. Der
    NEAR-Trade im Half2-Backtest erreichte 69% (50.667 von 73.048 USD) durch
    33 Grind-Orders ueber 51 Tage -- genau das soll dieser Cap verhindern."""
    _MAX_POSITION_FRACTION = 0.20

    def _position_cap(self):
        try:
            total = self.wallets.get_total_stake_amount()
        except Exception:
            total = self.config.get("dry_run_wallet", 10000)
        return total * self._MAX_POSITION_FRACTION

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        base = super().custom_stake_amount(pair, current_time, current_rate, proposed_stake,
                                            min_stake, max_stake, leverage, entry_tag, side, **kwargs)
        cap = self._position_cap()
        stake = min(base, cap)
        if min_stake is not None and stake < min_stake:
            stake = min_stake
        return stake

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                               min_stake, max_stake, current_entry_rate, current_exit_rate,
                               current_entry_profit, current_exit_profit, **kwargs):
        proposed = super().adjust_trade_position(
            trade, current_time, current_rate, current_profit, min_stake, max_stake,
            current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit, **kwargs)
        if proposed is None:
            return proposed
        # NFI can return either a plain stake amount or (stake_amount, order_tag).
        if isinstance(proposed, tuple):
            amount, order_tag = proposed[0], proposed[1]
        else:
            amount, order_tag = proposed, None
        if amount is None or amount <= 0:
            # Negative/zero amounts are grind-exits (partial closes), not size
            # increases -- the cap only applies to growing the position.
            return proposed
        cap = self._position_cap()
        current_stake = trade.stake_amount or 0.0
        if current_stake >= cap:
            return None
        capped = min(amount, cap - current_stake)
        return (capped, order_tag) if order_tag is not None else capped


class NFI_KF_AbandonAndCap(NFI_KF_PositionCap):
    """Kombination beider Fixes: frueherer Abandon-Exit UND harter Positions-Cap."""
    bad_trade_controller_stale_min_age_days = 5.0
    bad_trade_controller_stale_min_adverse_move_pct = 6.0
    bad_trade_controller_structure_break_min_adverse_move_pct = 12.0


class NFI_KF_AbandonCapV2(NFI_KF_AbandonAndCap):
    """Reaktion auf den ZEC-Trade im 44-v2-Backtest: 101 Grind-Orders ueber
    2 Monate, Peak-Stake 35.598 USD trotz aktivem 20%-Cap (der Cap ist relativ
    zum jeweils aktuellen Kapital -- waechst das Konto, waechst auch die
    absolute Grenze mit) und Exit letztlich ueber trailing_stop_loss, nicht
    ueber die Abandon-/Structure-Break-Pfade, die der bestehende Fix abdeckt.
    Drei zusaetzliche Bremsen:
      1) Cap von 20% auf 8% des aktuellen Kapitals gesenkt.
      2) Grind-/Rebuy-Zyklen hart auf 20 Orders pro Trade begrenzt.
      3) Zwangs-Exit nach 30 Tagen, unabhaengig vom sonstigen Exit-Grund --
         faengt genau die Faelle ab, die weder Abandon noch Structure-Break
         ausloesen, aber trotzdem ueber Wochen/Monate weiterlaufen."""
    _MAX_POSITION_FRACTION = 0.08
    _MAX_GRIND_ORDERS = 20
    _MAX_HOLD_DAYS = 30.0

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                               min_stake, max_stake, current_entry_rate, current_exit_rate,
                               current_entry_profit, current_exit_profit, **kwargs):
        if len(trade.orders) >= self._MAX_GRIND_ORDERS:
            return None
        return super().adjust_trade_position(
            trade, current_time, current_rate, current_profit, min_stake, max_stake,
            current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit, **kwargs)

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        age_days = (current_time - trade.open_date_utc).total_seconds() / 86400.0
        if age_days >= self._MAX_HOLD_DAYS:
            return f"exit_max_hold_{age_days:.0f}d"
        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)


class NFI_KF_AbandonCapV3(NFI_KF_AbandonCapV2):
    """Abgeschwaechte V2: V2 (Cap 8%/Grind-Limit 20/Max-Hold 30d) kostete zu
    viel Rendite, weil Grinding der Kern-Ertragsmechanismus der Strategie ist,
    nicht nur ein Risiko. V3 lockert alle drei Bremsen deutlich:
      1) Cap 8% -> 15% des aktuellen Kapitals.
      2) Grind-Limit 20 -> 40 Orders.
      3) Max-Hold 30 -> 60 Tage."""
    _MAX_POSITION_FRACTION = 0.15
    _MAX_GRIND_ORDERS = 40
    _MAX_HOLD_DAYS = 60.0


class NFI_KF_V2_Cap06(NFI_KF_AbandonCapV2):
    """Cap-Sweep: 6% statt 8%, Grind-Limit/Max-Hold wie V2."""
    _MAX_POSITION_FRACTION = 0.06


class NFI_KF_V2_Cap10(NFI_KF_AbandonCapV2):
    """Cap-Sweep: 10% statt 8%, Grind-Limit/Max-Hold wie V2."""
    _MAX_POSITION_FRACTION = 0.10


class NFI_KF_V2_Cap12(NFI_KF_AbandonCapV2):
    """Cap-Sweep: 12% statt 8%, Grind-Limit/Max-Hold wie V2."""
    _MAX_POSITION_FRACTION = 0.12


class NFI_KF_V2_Cap14(NFI_KF_AbandonCapV2):
    """Cap-Sweep: 14% statt 8%, Grind-Limit/Max-Hold wie V2."""
    _MAX_POSITION_FRACTION = 0.14


class NFI_KF_V2_RebuyTight(NFI_KF_AbandonCapV2):
    """V2 kombiniert mit engeren Rebuy-Schwellen (von OKX uebernommen, nie
    Kraken-spezifisch getestet): frueher/kleiner nachkaufen statt Default
    [-0.08,-0.10]/0.35."""
    rebuy_mode_thresholds_futures = [-0.05, -0.08]
    rebuy_mode_stake_multiplier = 0.25


class NFI_KF_V2_LongOnly(NFI_KF_AbandonCapV2):
    """V2, aber Shorts komplett deaktiviert. Test ob die Short-Seite ueber einen
    langen Zeitraum inkl. Baerenmarkt (2022-2026) tatsaechlich zur Rendite/zum
    Risiko beitraegt, oder ob (wie im kurzen Fut41-Fenster beobachtet: Shorts dort
    per Saldo leicht negativ) ein reiner Long-Bot gleich gut oder besser faehrt."""

    def __init__(self, config):
        super().__init__(config)
        self.can_short = False


class NFI_KF_V2_RebuyLoose(NFI_KF_AbandonCapV2):
    """V2 kombiniert mit weiteren Rebuy-Schwellen (von OKX uebernommen, nie
    Kraken-spezifisch getestet): spaeter/groesser nachkaufen statt Default
    [-0.08,-0.10]/0.35."""
    rebuy_mode_thresholds_futures = [-0.12, -0.16]
    rebuy_mode_stake_multiplier = 0.50


class NFI_KF_LongOnly_NoCapLimit(NFI_KF_AbandonAndCap):
    """Long-only-Fund: Shorts waren der Haupttreiber des Drawdowns (Vollzyklus:
    6,14% mit Shorts -> 1,45% ohne). Jetzt, wo Shorts weg sind, testen wir, ob
    der urspruengliche, grosszuegigere 20%-Cap (ohne Grind-Limit/Max-Hold aus V2)
    wieder vertretbar ist und mehr von der durch V2 'verschenkten' Rendite
    zurueckholt, ohne den Drawdown wieder explodieren zu lassen."""

    def __init__(self, config):
        super().__init__(config)
        self.can_short = False


class NFI_KF_LongOnly_V3(NFI_KF_AbandonCapV3):
    """Long-only + V3-Bremsen (Cap 15%/Grind-Limit 40/Max-Hold 60d) - mittlere
    Lockerung zwischen dem engen V2 und dem ungebremsten 20%-Cap."""

    def __init__(self, config):
        super().__init__(config)
        self.can_short = False


class NFI_KF_LongOnly_Cap12(NFI_KF_V2_Cap12):
    """Long-only + Cap 12% (V2-Grind-Limit/Max-Hold unveraendert) - kleine
    Lockerung des Positions-Caps."""

    def __init__(self, config):
        super().__init__(config)
        self.can_short = False


class NFI_KF_LongOnly_Cap17(NFI_KF_AbandonCapV2):
    """Feinsuche um V3 (15%/40/60d): Cap weiter auf 17% angehoben, Grind-Limit/
    Max-Hold wie V3 (40/60d), Long-only. Test ob zwischen V3 (15%, sicher) und
    NoCapLimit (20%, explodierte auf Fut41 mit DD 36%) noch Spielraum ist."""
    _MAX_POSITION_FRACTION = 0.17
    _MAX_GRIND_ORDERS = 40
    _MAX_HOLD_DAYS = 60.0

    def __init__(self, config):
        super().__init__(config)
        self.can_short = False


class NFI_KF_LongOnly_Grind60(NFI_KF_AbandonCapV2):
    """Feinsuche um V3: Cap/Max-Hold wie V3 (15%/60d), aber Grind-Limit von
    40 auf 60 Orders gelockert, Long-only."""
    _MAX_POSITION_FRACTION = 0.15
    _MAX_GRIND_ORDERS = 60
    _MAX_HOLD_DAYS = 60.0

    def __init__(self, config):
        super().__init__(config)
        self.can_short = False


class NFI_KF_LongOnly_Hold90(NFI_KF_AbandonCapV2):
    """Feinsuche um V3: Cap/Grind-Limit wie V3 (15%/40), aber Max-Hold von
    60 auf 90 Tage gelockert, Long-only."""
    _MAX_POSITION_FRACTION = 0.15
    _MAX_GRIND_ORDERS = 40
    _MAX_HOLD_DAYS = 90.0

    def __init__(self, config):
        super().__init__(config)
        self.can_short = False


class NFI_KF_V2_MemeCap(NFI_KF_AbandonCapV2):
    """V2 kombiniert mit Meme-Coin-Slot-Limit (aus NFI_KF_MemeCap): maximal 2 von 4
    offenen Trades duerfen Meme-Coins sein (PEPE/SHIB/DOGE/PENGU/TRUMP/PUMP). Deckt
    Klumpenrisiko durch hohe Korrelation innerhalb dieser Gruppe ab, das der
    Positions-Cap allein (ein Pro-Trade-Limit) nicht verhindert."""

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                             current_time, entry_tag, side, **kwargs):
        if pair in _MEME_PAIRS_KF:
            open_memes = sum(
                1 for t in Trade.get_open_trades() if t.pair in _MEME_PAIRS_KF
            )
            if open_memes >= _MAX_MEME_SLOTS_KF:
                return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs
        )


class NFI_KF_V2_TieredStake(NFI_KF_AbandonCapV2):
    """V2 kombiniert mit Volatilitaets-Tiering (aus NFI_KF_VolAdjStake/TieredLeverage):
    niedrigerer Hebel/Stake bei Hochvola-Coins, hoeherer bei Low-Vol-Coins. Setzt direkt
    an der Risikoquelle (Volatilitaet) an statt nur nachgelagert ueber den Positions-Cap
    nach bereits erfolgter Grind-Vergroesserung."""

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        base = super().leverage(pair, current_time, current_rate, proposed_leverage,
                                 max_leverage, entry_tag, side, **kwargs)
        if pair in _LOW_VOL_PAIRS_KF:
            factor = 5.0 / 3.0
        elif pair in _HIGH_VOL_PAIRS_KF:
            factor = 2.0 / 3.0
        else:
            factor = 1.0
        return min(base * factor, max_leverage)

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        base = NostalgiaForInfinityX8.custom_stake_amount(
            self, pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        if pair in _LOW_VOL_PAIRS_KF:
            factor = 1.3
        elif pair in _HIGH_VOL_PAIRS_KF:
            factor = 0.7
        else:
            factor = 1.0
        stake = base * factor
        cap = self._position_cap()
        stake = min(stake, cap)
        if min_stake is not None and stake < min_stake:
            stake = min_stake
        if stake > max_stake:
            stake = max_stake
        return stake


class NFI_KF_MemeCap(NostalgiaForInfinityX8):
    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                             current_time, entry_tag, side, **kwargs):
        if pair in _MEME_PAIRS_KF:
            open_memes = sum(
                1 for t in Trade.get_open_trades() if t.pair in _MEME_PAIRS_KF
            )
            if open_memes >= _MAX_MEME_SLOTS_KF:
                return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs
        )


class NFI_KF_LongOnly_Hold90_HyperTuned(NFI_KF_LongOnly_Hold90):
    """NFI_KF_LongOnly_Hold90 (Cap 15%/Grind40/Hold90d, Long-only) kombiniert
    mit den am 06.10. per Hyperopt gefundenen Rebuy-/Stop-Schwellenwerten
    (6-Monats-Fenster Dez25-Jul26, dort Long+Short: CAGR 232,72%, DD 4,99%).
    Noch nie mit der aktuellen Wrapper-Config zusammen getestet."""
    rebuy_mode_thresholds_futures = [-0.09, -0.09]
    rebuy_mode_stake_multiplier = 0.17
    stop_threshold_futures = 0.09
    stop_threshold_doom_futures = 0.27


class NFI_KF_LongOnly_Hold90_HyperTuned2(NFI_KF_LongOnly_Hold90_HyperTuned):
    """HyperTuned-Fix: zusaetzlich stop_threshold_futures_rebuy von NFI-Default
    1.0 (praktisch deaktiviert) auf 0.09 gesetzt -- das Attribut, das fuer
    Grinding-/Rebuy-Positionen tatsaechlich greift (im ersten HyperTuned-
    Versuch versehentlich nicht ueberschrieben)."""
    stop_threshold_futures_rebuy = 0.09


class NFI_KF_LongOnly_Hold90_Lev2(NFI_KF_LongOnly_Hold90):
    """Hold90 mit 2x statt 3x Hebel."""
    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        return 2.0


class NFI_KF_LongOnly_Hold90_Lev4(NFI_KF_LongOnly_Hold90):
    """Hold90 mit 4x statt 3x Hebel."""
    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        return 4.0


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15(NFI_KF_LongOnly_Hold90_Lev4):
    """Lev4, aber Grind-Limit von 40 auf 15 gesenkt: verhindert, dass sich die
    Grinding-Mechanik bei 4x Hebel zu tief in einen anhaltenden Abwaertstrend
    hineinkauft (Wurzel der OP/UNI-Verlusttrades in W4: 41 bzw. 7 Nachkauf-
    Orders ueber Tage/Wochen bei fallendem Kurs)."""
    _MAX_GRIND_ORDERS = 15


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit10(NFI_KF_LongOnly_Hold90_Lev4):
    """Wie GrindLimit15, aber noch straffer (10 statt 15 Nachkauf-Orders max)."""
    _MAX_GRIND_ORDERS = 10


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit20(NFI_KF_LongOnly_Hold90_Lev4):
    """Wie GrindLimit15, aber etwas lockerer (20 statt 15 Nachkauf-Orders max)."""
    _MAX_GRIND_ORDERS = 20


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit25(NFI_KF_LongOnly_Hold90_Lev4):
    """Wie GrindLimit15, aber noch lockerer (25 statt 15 Nachkauf-Orders max)."""
    _MAX_GRIND_ORDERS = 25


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_Cap12(NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15):
    """GrindLimit15 kombiniert mit einem moderat gesenkten Cap (12% statt 15%),
    um zu pruefen ob beide Hebel zusammen den Drawdown weiter senken oder sich
    nur gegenseitig Profit wegnehmen."""
    _MAX_POSITION_FRACTION = 0.12


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_Hold60(NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15):
    """GrindLimit15 kombiniert mit kuerzerem Max-Hold (60 statt 90 Tage), um
    die Exposure-Zeit gegenueber anhaltenden Abwaertstrends zusaetzlich zu
    verkuerzen."""
    _MAX_HOLD_DAYS = 60.0


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_WideRebuy(NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15):
    """GrindLimit15 kombiniert mit weiter auseinandergezogenen Rebuy-Schwellen
    (NFI-Standard: [-0.08, -0.10]), sodass die ersten Nachkauf-Stufen erst bei
    groesseren Drawdowns ausgeloest werden -- ergaenzt die Order-Anzahl-Grenze
    um eine Tiefen-Grenze."""
    rebuy_mode_thresholds_futures = [-0.12, -0.16]


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_TaperStake(NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15):
    """GrindLimit15 kombiniert mit einer abnehmenden Rebuy-Stake-Kurve: NFI's
    eigener "rebuy mode" nutzt rebuy_mode_stakes_futures als Multiplikator pro
    Nachkauf-Stufe (Standard: [1.0, 1.0], max. 2 Stufen -- die Listenlaenge
    legt in NFI selbst fest, wie viele Rebuy-Mode-Stufen erlaubt sind). Hier
    auf 4 Stufen erweitert (Schwellen wie NFI's eigene system_v3-Variante:
    [-0.08, -0.12, -0.16, -0.20]), aber mit abnehmendem Einsatz je Stufe
    (1.0 -> 0.7 -> 0.5 -> 0.3), damit tiefere Nachkaeufe weniger Kapital
    riskieren, ohne die Erholungschance durch zusaetzliche (kleinere)
    Versuche zu verlieren."""
    rebuy_mode_thresholds_futures = [-0.08, -0.12, -0.16, -0.20]
    rebuy_mode_stakes_futures = [1.0, 0.7, 0.5, 0.3]


class NFI_KF_LongOnly_Hold90_Lev4_PairGrind(NFI_KF_LongOnly_Hold90_Lev4):
    """Pair-spezifisches Grind-Limit: Etablierte Majors (hohe Liquiditaet,
    historisch weniger anfaellig fuer lange Abwaertstrends) duerfen bis 25
    Nachkauf-Orders akkumulieren, alle anderen Coins (inkl. OP/UNI-artiger
    Mid-Caps, die in W4 die grossen Verluste verursacht haben) werden auf 10
    begrenzt."""
    _MAX_GRIND_ORDERS = 25
    _MAJOR_COINS = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "LINK", "DOT", "LTC", "BCH", "XLM"}
    _MAX_GRIND_ORDERS_OTHER = 10

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                               min_stake, max_stake, current_entry_rate, current_exit_rate,
                               current_entry_profit, current_exit_profit, **kwargs):
        base = trade.pair.split("/")[0]
        if base not in self._MAJOR_COINS and len(trade.orders) >= self._MAX_GRIND_ORDERS_OTHER:
            return None
        return super().adjust_trade_position(
            trade, current_time, current_rate, current_profit, min_stake, max_stake,
            current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit, **kwargs)


class NFI_KF_LongOnly_Hold90_Lev4_Cap10(NFI_KF_LongOnly_Hold90_Lev4):
    """Lev4, aber Position-Cap von 15% auf 10% gesenkt, um das Kapital-Risiko
    pro Position trotz hoeherem Hebel auf einem aehnlichen Niveau wie beim
    3x/15%-Live-Setup zu halten (10% * 4x = 40% effektive Exposure pro Slot
    vs. 15% * 3x = 45% beim Original)."""
    _MAX_POSITION_FRACTION = 0.10


class NFI_KF_LongOnly_Hold90_Lev4_Tuned(NFI_KF_LongOnly_Hold90_Lev4):
    """Lev4 mit enger gezogenen Stop-/Grinding-Schwellen: Verluste wiegen bei
    4x Hebel schwerer als bei 3x, daher werden die Stop-Schwellen gegenueber
    dem NFI-Standard (stop_threshold_futures=0.10, doom=0.20, rebuy-Stop
    deaktiviert) enger gesetzt."""
    stop_threshold_futures = 0.06
    stop_threshold_futures_rebuy = 0.06
    stop_threshold_doom_futures = 0.14


class NFI_KF_LongOnly_Hold90_Protected(NFI_KF_LongOnly_Hold90):
    """Hold90 + Freqtrade-Protections (CooldownPeriod, StoplossGuard, MaxDrawdown)
    als zusaetzliche Sicherheitsschicht um die Strategie, ohne deren Signal-
    Logik selbst zu veraendern."""
    protections = [
        {"method": "CooldownPeriod", "stop_duration_candles": 12},
        {"method": "StoplossGuard", "lookback_period_candles": 288, "trade_limit": 3,
         "stop_duration_candles": 288, "only_per_pair": True},
        {"method": "MaxDrawdown", "lookback_period_candles": 2000, "trade_limit": 10,
         "stop_duration_candles": 288, "max_allowed_drawdown": 0.12},
    ]


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit10b(NFI_KF_LongOnly_Hold90_Lev4):
    """Wie GrindLimit10, aber eigener Name fuer den Grind-Limit-Sweep auf der
    61-Coin/MOT5-Basis (identischer Wert, nur zur klaren Zuordnung)."""
    _MAX_GRIND_ORDERS = 10


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit20b(NFI_KF_LongOnly_Hold90_Lev4):
    """Wie GrindLimit20, aber eigener Name fuer den Grind-Limit-Sweep auf der
    61-Coin/MOT5-Basis."""
    _MAX_GRIND_ORDERS = 20


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI(NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15):
    """GrindLimit15 kombiniert mit einer zusaetzlichen ROI-Tabelle (NFI nutzt
    normalerweise gar kein minimal_roi, nur eigene custom_exit/Grind-Logik):
    25% Sofort-Gewinnmitnahme, abnehmend auf 10% nach 1 Tag, 5% nach 3 Tagen.
    Soll seltene, sehr schnelle Spike-Gewinne vor einem Pullback sichern,
    bevor NFIs eigene (langsamere) Exit-Logik reagiert."""
    minimal_roi = {
        "0": 0.25,
        "1440": 0.10,
        "4320": 0.05,
    }


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_Safe(NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI):
    """Wie GrindLimit15_ROI, aber mit einer Sicherung gegen den Derisk-Bug:
    Freqtrade's minimal_roi-Check bewertet nur den Profit des aktuell noch
    offenen Rest-Bestands, nicht den gesamten Trade inkl. bereits realisierter
    Verluste aus fruehen Derisk-Verkaeufen. Dadurch kann die ROI-Tabelle einen
    Trade mitten in einer Derisk-Erholung komplett schliessen, sobald nur der
    kleine Rest-Bestand kurz im Plus ist - und realisiert dabei einen
    Gesamtverlust, den NFIs eigene Grinding-Logik (ohne ROI-Tabelle) ueber die
    naechsten Wochen noch ausgeglichen haette.
    Diese Variante blockiert einen ROI-Exit gezielt genau dann, wenn der
    GESAMTE Trade (realisiert + aktuell offen) noch im Minus waere - und
    laesst NFIs eigene Exit-Logik (Signal/Stop/Grinding) den Trade in diesem
    Fall zu Ende bringen, so wie ohne ROI-Tabelle. Betrifft nur den exit_reason
    "roi"; alle anderen Exit-Pfade (Signal, Stop, Liquidation, force_exit)
    bleiben unveraendert."""

    def confirm_trade_exit(self, pair, trade, order_type, amount, rate,
                            time_in_force, exit_reason, current_time, **kwargs):
        if exit_reason == "roi":
            total_profit_ratio = trade.calculate_profit(rate).total_profit_ratio
            if total_profit_ratio < 0:
                return False
        return super().confirm_trade_exit(
            pair, trade, order_type, amount, rate, time_in_force,
            exit_reason, current_time, **kwargs
        )


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_SafeGrace(NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI):
    """Wie ROI_Safe, aber der Veto gegen einen Verlust-ROI-Exit gilt nur
    innerhalb einer Gnadenfrist seit Trade-Eroeffnung (hier 45 Tage, laenger
    als die 39 Tage, die der LPT-Erholungsfall im Validierungsfenster
    brauchte) - nicht unbegrenzt wie bei ROI_Safe. Hintergrund: der
    unbegrenzte Safe-Fix verwettet im Hauptfenster teilweise, dass sich ein
    Trade erholt, was dort per Saldo schlechter ausging (weniger Profit, mehr
    Drawdown als ganz ohne Safe-Fix). Nach Ablauf der Gnadenfrist darf die
    ROI-Tabelle wieder normal aussteigen, auch mit Verlust."""
    _ROI_VETO_MAX_AGE_DAYS = 45.0

    def confirm_trade_exit(self, pair, trade, order_type, amount, rate,
                            time_in_force, exit_reason, current_time, **kwargs):
        if exit_reason == "roi":
            age_days = (current_time - trade.open_date_utc).total_seconds() / 86400.0
            if age_days <= self._ROI_VETO_MAX_AGE_DAYS:
                if trade.calculate_profit(rate).total_profit_ratio < 0:
                    return False
        return super().confirm_trade_exit(
            pair, trade, order_type, amount, rate, time_in_force,
            exit_reason, current_time, **kwargs
        )


class _ROISafeExitMixin:
    """Wiederverwendbare Fassung des Safe-Fix aus GrindLimit15_ROI_Safe fuer
    die weiteren Grind-Limit-/ROI-Varianten unten. Per Mixin statt Kopieren,
    damit der Fix ueberall exakt gleich bleibt."""

    def confirm_trade_exit(self, pair, trade, order_type, amount, rate,
                            time_in_force, exit_reason, current_time, **kwargs):
        if exit_reason == "roi":
            if trade.calculate_profit(rate).total_profit_ratio < 0:
                return False
        return super(_ROISafeExitMixin, self).confirm_trade_exit(
            pair, trade, order_type, amount, rate, time_in_force,
            exit_reason, current_time, **kwargs
        )


_STANDARD_ROI_TABLE = {"0": 0.25, "1440": 0.10, "4320": 0.05}


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit10_ROI_Safe(_ROISafeExitMixin, NFI_KF_LongOnly_Hold90_Lev4_GrindLimit10):
    """Grind-Limit-Resweep (10/15/20/25) jetzt mit ROI-Tabelle + Safe-Fix --
    die urspruengliche Feinsuche (ohne ROI) fand 15 als Optimum, das kann sich
    durch das veraenderte Exit-Verhalten der ROI-Tabelle verschoben haben."""
    minimal_roi = _STANDARD_ROI_TABLE


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit20_ROI_Safe(_ROISafeExitMixin, NFI_KF_LongOnly_Hold90_Lev4_GrindLimit20):
    minimal_roi = _STANDARD_ROI_TABLE


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit25_ROI_Safe(_ROISafeExitMixin, NFI_KF_LongOnly_Hold90_Lev4_GrindLimit25):
    minimal_roi = _STANDARD_ROI_TABLE


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI2_Safe(_ROISafeExitMixin, NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15):
    """Aggressivere ROI-Tabelle: mehr Stufen, schnellerer Abbau (0/6h/1d/2d/4d)
    -- greift frueher und oefter ein als die Standard-Tabelle, abgesichert
    durch den gleichen Safe-Fix."""
    minimal_roi = {
        "0": 0.35,
        "360": 0.18,
        "1440": 0.10,
        "2880": 0.06,
        "5760": 0.03,
    }


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI3_Safe(_ROISafeExitMixin, NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15):
    """Geduldigere ROI-Tabelle: nur zwei Stufen, kein weiterer Abbau nach Tag 2
    -- laesst Trades laenger laufen, bevor die Tabelle ueberhaupt greift."""
    minimal_roi = {
        "0": 0.20,
        "2880": 0.08,
    }


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_Safe_HoldGrace(NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_Safe):
    """Erweitert den Safe-Fix auf den Max-Hold-90-Tage-Mechanismus von
    NFI_KF_AbandonCapV2.custom_exit: der zwingt nach 90 Tagen einen Exit
    unabhaengig vom aktuellen Profit (belegte Faelle in frueheren Tests: z.B.
    INJ -17,4%, ICP -25,5%, CRV -3,8%, ZEC -10,4% ueber exit_max_hold_*).
    Statt sofort zwangsweise zu schliessen, bekommt eine nach 90 Tagen noch im
    Minus stehende Position bis zu 30 weitere Tage Gnadenfrist (Gesamt-Cap 120
    Tage), um sich ueber NFIs eigene Grinding-Logik zu erholen -- danach wird
    trotzdem zwangsweise geschlossen, damit Kapital nicht unbegrenzt gebunden
    bleibt."""
    _MAX_HOLD_GRACE_DAYS = 30.0

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        age_days = (current_time - trade.open_date_utc).total_seconds() / 86400.0
        if age_days >= self._MAX_HOLD_DAYS:
            total_profit_ratio = trade.calculate_profit(current_rate).total_profit_ratio
            if total_profit_ratio < 0 and age_days < (self._MAX_HOLD_DAYS + self._MAX_HOLD_GRACE_DAYS):
                return NFI_KF_AbandonAndCap.custom_exit(
                    self, pair, trade, current_time, current_rate, current_profit, **kwargs)
            return f"exit_max_hold_{age_days:.0f}d"
        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)


# Tranche-3-Coins (die 25 Coins, die die 61er-Liste auf 86 erweitern) -- im
# Schnitt deutlich kleinere Marktkapitalisierung/duennere Orderbuecher auf
# Kraken Futures als die urspruengliche 61er-Basisliste.
_THIN_LIQUIDITY_PAIRS_KF = {
    "1INCH/USD:USD", "APE/USD:USD", "BAT/USD:USD", "CFX/USD:USD", "CHZ/USD:USD",
    "CVX/USD:USD", "ENS/USD:USD", "FET/USD:USD", "FLOW/USD:USD", "IMX/USD:USD",
    "JASMY/USD:USD", "KAVA/USD:USD", "LPT/USD:USD", "LUNA2/USD:USD", "MANA/USD:USD",
    "MNT/USD:USD", "ORDI/USD:USD", "QNT/USD:USD", "QTUM/USD:USD", "ROSE/USD:USD",
    "RUNE/USD:USD", "STRK/USD:USD", "SUSHI/USD:USD", "XTZ/USD:USD", "YFI/USD:USD",
}


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_Safe_ThinCap(NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_Safe):
    """Zusaetzlich zum bestehenden %-Positions-Cap (15% des AKTUELLEN
    Kapitals, waechst also mit dem Konto mit) ein ABSOLUTER USD-Deckel fuer
    die duenn gehandelten Tranche-3-Alts (_THIN_LIQUIDITY_PAIRS_KF). Hintergrund:
    je groesser das Konto wird, desto groesser werden auch die Positionen in
    diesen Coins - Backtests modellieren aber keinen Market-Impact/Slippage,
    reale Kraken-Futures-Orderbuecher fuer diese Alts sind aber deutlich
    duenner als bei BTC/ETH/SOL. Dieser Fix begrenzt nur die Tranche-3-Coins
    auf einen festen USD-Betrag (Margin, vor Hebel) -- unabhaengig davon, wie
    gross das Konto schon gewachsen ist. Fuer alle anderen (liquideren) Coins
    bleibt ausschliesslich der bestehende %-Cap aktiv."""
    _THIN_PAIR_ABS_CAP_USD = 1500.0

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        if pair in _THIN_LIQUIDITY_PAIRS_KF:
            stake = min(stake, self._THIN_PAIR_ABS_CAP_USD)
            if min_stake is not None and stake < min_stake:
                stake = min_stake
        return stake

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                               min_stake, max_stake, current_entry_rate, current_exit_rate,
                               current_entry_profit, current_exit_profit, **kwargs):
        proposed = super().adjust_trade_position(
            trade, current_time, current_rate, current_profit, min_stake, max_stake,
            current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit, **kwargs)
        if proposed is None or trade.pair not in _THIN_LIQUIDITY_PAIRS_KF:
            return proposed
        if isinstance(proposed, tuple):
            amount, order_tag = proposed[0], proposed[1]
        else:
            amount, order_tag = proposed, None
        if amount is None or amount <= 0:
            # Negative/Null-Betraege sind Grind-Exits (Teilverkaeufe), nicht
            # Positions-Vergroesserungen -- der Deckel greift nur beim Aufbauen.
            return proposed
        current_stake = trade.stake_amount or 0.0
        if current_stake >= self._THIN_PAIR_ABS_CAP_USD:
            return None
        amount = min(amount, self._THIN_PAIR_ABS_CAP_USD - current_stake)
        return (amount, order_tag) if order_tag is not None else amount


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_Safe_ThinCap2500(NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_Safe_ThinCap):
    """Wie ThinCap, aber der absolute USD-Deckel fuer die duennen Tranche-3-
    Coins von 1.500 auf 2.500 USD angehoben -- 1.500 USD kostete im
    Hauptfenster real ~54 Prozentpunkte Profit (einige grosse, profitable
    Tranche-3-Positionen wurden dadurch gekappt), bei praktisch unveraendertem
    Drawdown. 2.500 USD soll einen besseren Kompromiss zwischen
    Slippage-Schutz und Profit testen."""
    _THIN_PAIR_ABS_CAP_USD = 2500.0


# ============================================================================
# Empfohlene Live-Basis OHNE Safe-Fix (der im Hauptfenster per Saldo
# Performance kostet, siehe NEAR/ZEC-Root-Cause-Analyse) + ThinCap2500.
# Ab hier: weitere, unabhaengige Optimierungsideen auf dieser Basis.
# ============================================================================

class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500(NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI):
    """Empfohlene Live-Basis: Grind-Limit 15 + ROI-Tabelle (OHNE den
    ROI-Safe-Exit-Fix) + absoluter 2.500-USD-Deckel fuer die duennen
    Tranche-3-Coins (Slippage-Schutz bei Kapitalerhoehung, nahezu kostenlos
    laut Test)."""
    _THIN_PAIR_ABS_CAP_USD = 2500.0

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        if pair in _THIN_LIQUIDITY_PAIRS_KF:
            stake = min(stake, self._THIN_PAIR_ABS_CAP_USD)
            if min_stake is not None and stake < min_stake:
                stake = min_stake
        return stake

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                               min_stake, max_stake, current_entry_rate, current_exit_rate,
                               current_entry_profit, current_exit_profit, **kwargs):
        proposed = super().adjust_trade_position(
            trade, current_time, current_rate, current_profit, min_stake, max_stake,
            current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit, **kwargs)
        if proposed is None or trade.pair not in _THIN_LIQUIDITY_PAIRS_KF:
            return proposed
        if isinstance(proposed, tuple):
            amount, order_tag = proposed[0], proposed[1]
        else:
            amount, order_tag = proposed, None
        if amount is None or amount <= 0:
            return proposed
        current_stake = trade.stake_amount or 0.0
        if current_stake >= self._THIN_PAIR_ABS_CAP_USD:
            return None
        amount = min(amount, self._THIN_PAIR_ABS_CAP_USD - current_stake)
        return (amount, order_tag) if order_tag is not None else amount


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_GlobalCap5000(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Zusaetzlich zum 2.500-USD-Deckel fuer duenne Tranche-3-Coins ein
    GENERELLER 5.000-USD-Deckel fuer ALLE Coins (auch liquide Majors wie
    NEAR/ZEC). Hintergrund: die Root-Cause-Analyse zeigte Einzeltrade-Verluste
    von -3.722 USD (NEAR) bzw. -2.718 USD (ZEC) bei bereits gewachsenem
    Konto -- ein genereller Deckel begrenzt, wie gross eine einzelne Position
    durch Grinding werden kann, unabhaengig vom Coin."""
    _GLOBAL_ABS_CAP_USD = 5000.0

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        stake = min(stake, self._GLOBAL_ABS_CAP_USD)
        if min_stake is not None and stake < min_stake:
            stake = min_stake
        return stake

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                               min_stake, max_stake, current_entry_rate, current_exit_rate,
                               current_entry_profit, current_exit_profit, **kwargs):
        proposed = super().adjust_trade_position(
            trade, current_time, current_rate, current_profit, min_stake, max_stake,
            current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit, **kwargs)
        if proposed is None:
            return proposed
        if isinstance(proposed, tuple):
            amount, order_tag = proposed[0], proposed[1]
        else:
            amount, order_tag = proposed, None
        if amount is None or amount <= 0:
            return proposed
        current_stake = trade.stake_amount or 0.0
        if current_stake >= self._GLOBAL_ABS_CAP_USD:
            return None
        amount = min(amount, self._GLOBAL_ABS_CAP_USD - current_stake)
        return (amount, order_tag) if order_tag is not None else amount


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_FundingFilter(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Zusaetzlich: blockiert Long-Entries, wenn die aktuelle Funding-Rate
    des Coins ueber dem ~99. Perzentil liegt (ueberhitzter/teurer Markt als
    Kontra-Signal). Nutzt die gleiche Feather-basierte PIT-sichere
    Funding-Rate-Lookup-Logik wie NFI_KF_ResearchVariants.NFI_KF_FundingFilter_05,
    hier aber auf der aktuellen empfohlenen Basis."""
    _MAX_FUNDING_RATE = 0.00005

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                             current_time, entry_tag, side, **kwargs):
        from NFI_KF_ResearchVariants import _load_funding_arrays
        import numpy as np
        import pandas as pd
        arrs = _load_funding_arrays(pair)
        if arrs is not None:
            ts, vals = arrs
            t = np.int64(pd.Timestamp(current_time).value)
            idx = np.searchsorted(ts, t, side="right") - 1
            if idx >= 0:
                last_funding = vals[idx]
                if np.isfinite(last_funding) and last_funding > self._MAX_FUNDING_RATE:
                    return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


# Korrelationsgruppen fuer den Klumpenrisiko-Filter unten -- Coins, die bei
# Alt-Season-Dumps/-Pumps tendenziell stark gemeinsam laufen.
_CORR_GROUP_L1_ALTS_KF = {
    "ADA/USD:USD", "AVAX/USD:USD", "DOT/USD:USD", "NEAR/USD:USD", "ATOM/USD:USD",
    "ALGO/USD:USD", "SUI/USD:USD", "APT/USD:USD", "SEI/USD:USD", "HBAR/USD:USD",
    "EGLD/USD:USD", "ICP/USD:USD", "TRX/USD:USD", "XLM/USD:USD", "XRP/USD:USD",
}
_CORR_GROUP_L2_SCALING_KF = {
    "ARB/USD:USD", "OP/USD:USD", "STRK/USD:USD", "IMX/USD:USD", "MNT/USD:USD",
    "POL/USD:USD",
}
_CORR_GROUP_DEFI_KF = {
    "AAVE/USD:USD", "UNI/USD:USD", "CRV/USD:USD", "LDO/USD:USD", "CVX/USD:USD",
    "SNX/USD:USD", "COMP/USD:USD", "SUSHI/USD:USD", "YFI/USD:USD", "DYDX/USD:USD",
    "ENS/USD:USD",
}
_CORR_GROUPS_KF = [_CORR_GROUP_L1_ALTS_KF, _CORR_GROUP_L2_SCALING_KF, _CORR_GROUP_DEFI_KF]
_MAX_CORR_GROUP_SLOTS_KF = 2


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CorrFilter(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Zusaetzlich: maximal 2 gleichzeitig offene Trades pro
    Korrelationsgruppe (L1-Alts, L2/Scaling, DeFi -- siehe _CORR_GROUPS_KF),
    analog zur bestehenden Meme-Coin-Slot-Kappung. Soll Klumpenrisiko durch
    mehrere stark korrelierte Alt-Positionen gleichzeitig begrenzen, das der
    reine Pro-Trade-Positions-Cap nicht abdeckt."""

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                             current_time, entry_tag, side, **kwargs):
        for group in _CORR_GROUPS_KF:
            if pair in group:
                open_in_group = sum(1 for t in Trade.get_open_trades() if t.pair in group)
                if open_in_group >= _MAX_CORR_GROUP_SLOTS_KF:
                    return False
                break
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_StopTight06(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Engere Stop-/Grinding-Schwellen (0,06 statt NFI-Standard 0,10) auf der
    AKTUELLEN Basis (GrindLimit15+ROI+ThinCap2500). Eine fruehere Version
    dieses Tests (vor Einfuehrung von GrindLimit15) war inkonsistent (half im
    Validierungsfenster, schadete im Hauptfenster) - da GrindLimit15 inzwischen
    den Hauptmechanismus fuer den Tail-Risk-Schutz uebernommen hat, koennte
    sich das Ergebnis jetzt anders verhalten."""
    stop_threshold_futures = 0.06
    stop_threshold_futures_rebuy = 0.06


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_StopTight08(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Wie StopTight06, aber moderater (0,08)."""
    stop_threshold_futures = 0.08
    stop_threshold_futures_rebuy = 0.08


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_StopLoose13(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Gegenrichtung: etwas lockerere Stop-Schwelle (0,13 statt 0,10) -- falls
    GrindLimit15 bereits genug Schutz bietet, koennte ein lockererer Stop mehr
    Erholungschancen vor dem Zwangs-Exit lassen."""
    stop_threshold_futures = 0.13
    stop_threshold_futures_rebuy = 0.13


# ============================================================================
# Weitere, noch nicht getestete Optimierungsideen auf der aktuellen Live-Basis
# (GrindLimit15 + ROI + ThinCap2500, ohne Safe-Fix).
# ============================================================================

class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TieredLev(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Volatilitaets-abhaengiger Hebel: Low-Vol-Majors (BTC/ETH/BNB/LTC)
    bekommen 5/3 des Basis-Hebels, High-Vol-Alts nur 2/3 -- faehrt mehr
    Risiko, wo die Schwankung geringer ist, und weniger, wo sie hoch ist.
    Noch nie auf der aktuellen GrindLimit15+ROI+ThinCap2500-Kombination
    getestet (nur auf frueheren, einfacheren Basen)."""

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        base = super().leverage(pair, current_time, current_rate, proposed_leverage,
                                 max_leverage, entry_tag, side, **kwargs)
        if pair in _LOW_VOL_PAIRS_KF:
            factor = 5.0 / 3.0
        elif pair in _HIGH_VOL_PAIRS_KF:
            factor = 2.0 / 3.0
        else:
            factor = 1.0
        return min(base * factor, max_leverage)


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_StagedTP(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Gestaffelte Teilgewinnmitnahme: sobald der GESAMTE Trade (realisiert +
    offen) zum ersten Mal 15% Profit erreicht, wird HALB die Position
    (50% des aktuellen Bestands) verkauft -- der Rest laeuft normal weiter
    (ROI-Tabelle/NFI-Exit-Logik greift unveraendert fuer den Rest). Im
    Gegensatz zur ROI-Tabelle (kompletter Exit) soll das mehr vom Trend
    mitnehmen, wenn der Trade nach dem ersten Ziel weiterlaeuft, und trotzdem
    fruehzeitig etwas Gewinn sichern. Ausgeloest nur EINMAL pro Trade (ueber
    einen eindeutigen Order-Tag erkennbar)."""
    _STAGED_TP_THRESHOLD = 0.15
    _STAGED_TP_FRACTION = 0.5
    _STAGED_TP_TAG = "staged_tp1"

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                               min_stake, max_stake, current_entry_rate, current_exit_rate,
                               current_entry_profit, current_exit_profit, **kwargs):
        already_staged = any(
            o.ft_order_tag == self._STAGED_TP_TAG for o in trade.orders
        )
        if not already_staged:
            total_profit_ratio = trade.calculate_profit(current_rate).total_profit_ratio
            if total_profit_ratio >= self._STAGED_TP_THRESHOLD:
                sell_stake = -(trade.stake_amount * self._STAGED_TP_FRACTION)
                return (sell_stake, self._STAGED_TP_TAG)
        return super().adjust_trade_position(
            trade, current_time, current_rate, current_profit, min_stake, max_stake,
            current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit, **kwargs)


_BTC_PAIR_KF = "BTC/USD:USD"
_btc_return_cache = {}


def _load_btc_return_array(lookback_hours=4):
    key = lookback_hours
    if key not in _btc_return_cache:
        import os
        import numpy as np
        import pandas as pd
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "krakenfutures", "futures")
        path = os.path.join(data_dir, "BTC_USD_USD-1h-futures.feather")
        try:
            df = pd.read_feather(path).sort_values("date")
            closes = df["close"].to_numpy()
            ret = closes / np.roll(closes, lookback_hours) - 1.0
            ret[:lookback_hours] = np.nan
            ts = (df["date"].astype("int64") * 1_000_000).to_numpy()  # ms -> ns Fix
            _btc_return_cache[key] = (ts, ret)
        except Exception:
            _btc_return_cache[key] = None
    return _btc_return_cache[key]


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Marktregime-Filter: blockiert NEUE Long-Entries (alle Coins), wenn
    BTC in den letzten 4 Stunden mehr als 8% gefallen ist -- ein
    PIT-sicherer Crash-Schutz, der verhindert, dass waehrend eines breiten
    Markt-Abverkaufs frisches Kapital in neue Positionen gesteckt wird.
    Bereits offene Positionen sind unberuehrt (nur Entries werden blockiert)."""
    _CRASH_LOOKBACK_HOURS = 4
    _CRASH_THRESHOLD = -0.08

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                             current_time, entry_tag, side, **kwargs):
        import numpy as np
        import pandas as pd
        arrs = _load_btc_return_array(self._CRASH_LOOKBACK_HOURS)
        if arrs is not None:
            ts, rets = arrs
            t = np.int64(pd.Timestamp(current_time).value)
            idx = np.searchsorted(ts, t, side="right") - 1
            if idx >= 0:
                r = rets[idx]
                if np.isfinite(r) and r < self._CRASH_THRESHOLD:
                    return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_NoWeekend(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Blockiert neue Long-Entries am Wochenende (Samstag/Sonntag UTC) --
    duennere Orderbuecher und groessere Spikes auf Kraken Futures ausserhalb
    der Wochentage als Entry-Risiko. Offene Positionen laufen unveraendert
    weiter, nur neue Entries werden am Wochenende blockiert."""

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                             current_time, entry_tag, side, **kwargs):
        if current_time.weekday() >= 5:
            return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard5(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard
):
    """Wie CrashGuard, aber Schwelle auf -5% (statt -8%) gesenkt, damit der
    Filter innerhalb der vorhandenen Testfenster ueberhaupt einmal greift
    (der staerkste BTC-4h-Ruecksetzer im Haupt-/Validierungsfenster lag bei
    nur -6,65%, nie unter -8%) -- zur gezielten Pruefung, was der Filter
    waehrend eines echten (wenn auch moderaten) Markt-Ruecksetzers bewirkt."""
    _CRASH_THRESHOLD = -0.05


# ============================================================================
# Kreative Zusatzideen auf der aktuellen Live-Basis + CrashGuard5
# (GrindLimit15 + ROI + ThinCap2500 + CrashGuard5).
# ============================================================================

class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard5_GrindAwareROI(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard5
):
    """Gestaffelter ROI-Deckel nach Grind-Tiefe: sobald eine Position bereits
    mindestens 5 Grind-/Nachkauf-Orders hinter sich hat (also bereits als
    "riskant" bewiesen ist), reicht ein niedrigerer Gesamt-Profit (5% statt
    der vollen ROI-Tabellen-Schwellen), um komplett auszusteigen. Frische,
    nicht gegrindete Positionen sind davon unberuehrt -- fuer sie gilt
    weiterhin die normale ROI-Tabelle. Zielt direkt auf die Erkenntnis aus
    der NEAR/ZEC-Root-Cause-Analyse: eine tief gegrindete Position, die
    endlich wieder ins Plus kommt, sollte diese Chance nicht verpassen,
    indem sie auf ein hohes ROI-Ziel wartet."""
    _GRIND_AWARE_MIN_ORDERS = 5
    _GRIND_AWARE_ROI = 0.05

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        if len(trade.orders) >= self._GRIND_AWARE_MIN_ORDERS:
            total_profit_ratio = trade.calculate_profit(current_rate).total_profit_ratio
            if total_profit_ratio >= self._GRIND_AWARE_ROI:
                return "exit_grindaware_roi"
        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)


_universe_agg_cache = {}


def _load_universe_aggregates(pairs, lookback_breadth_hours=4, lookback_momentum_hours=24):
    """Laedt 1h-Closes aller angegebenen Coins, berechnet pro Zeitpunkt
    (a) den Anteil der Coins mit negativem Return ueber lookback_breadth_hours
        (Markt-Breite/Breadth) und
    (b) den Median-Return ueber lookback_momentum_hours ueber alle Coins
        (Markt-Momentum),
    PIT-sicher (nur rueckwaertsgerichtete Returns). Wird einmalig pro
    Pair-Set berechnet und gecacht."""
    key = (tuple(sorted(pairs)), lookback_breadth_hours, lookback_momentum_hours)
    if key in _universe_agg_cache:
        return _universe_agg_cache[key]

    import os
    import pandas as pd
    import numpy as np

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "krakenfutures", "futures")
    series_breadth = {}
    series_momentum = {}
    for pair in pairs:
        fname = pair.replace("/", "_").replace(":", "_")
        path = os.path.join(data_dir, f"{fname}-1h-futures.feather")
        try:
            df = pd.read_feather(path).sort_values("date").set_index("date")
            closes = df["close"]
            ret_b = closes / closes.shift(lookback_breadth_hours) - 1.0
            ret_m = closes / closes.shift(lookback_momentum_hours) - 1.0
            series_breadth[pair] = ret_b
            series_momentum[pair] = ret_m
        except Exception:
            continue

    breadth_df = pd.DataFrame(series_breadth)
    momentum_df = pd.DataFrame(series_momentum)
    frac_red = (breadth_df < 0).sum(axis=1) / breadth_df.notna().sum(axis=1).replace(0, np.nan)
    median_momentum = momentum_df.median(axis=1)

    ts = breadth_df.index.values.astype("int64") * 1_000_000  # ms -> ns Fix
    frac_red_arr = frac_red.to_numpy()
    median_mom_arr = median_momentum.to_numpy()
    momentum_by_pair = {p: (ts, momentum_df[p].to_numpy()) for p in momentum_df.columns}

    result = (ts, frac_red_arr, median_mom_arr, momentum_by_pair)
    _universe_agg_cache[key] = result
    return result


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard5_BreadthGuard(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard5
):
    """Markt-Breiten-Filter statt (zusaetzlich zum) reinen BTC-Signal:
    blockiert neue Entries, wenn mindestens 70% der Coins im konfigurierten
    Universum gerade einen negativen 4h-Return haben -- erkennt breite
    Alt-spezifische Abverkaeufe, die in BTC alleine nicht sichtbar waeren
    (BTC kann stabil bleiben, waehrend Alts gleichzeitig fallen)."""
    _BREADTH_RED_THRESHOLD = 0.70

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                             current_time, entry_tag, side, **kwargs):
        import numpy as np
        import pandas as pd
        all_pairs = tuple(self.config.get("exchange", {}).get("pair_whitelist", []))
        ts, frac_red_arr, _, _ = _load_universe_aggregates(all_pairs)
        t = np.int64(pd.Timestamp(current_time).value)
        idx = np.searchsorted(ts, t, side="right") - 1
        if idx >= 0:
            frac_red = frac_red_arr[idx]
            if np.isfinite(frac_red) and frac_red >= self._BREADTH_RED_THRESHOLD:
                return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard5_ReentryCooldown(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard5
):
    """Re-Entry-Cooldown: nach einem Stop-Loss-Exit darf derselbe Coin fuer
    24 Stunden nicht erneut gekauft werden -- verhindert das sofortige
    Wieder-Einsteigen in einen Coin, der gerade zwangsweise mit Verlust
    verlassen wurde und moeglicherweise weiter im Abwaertstrend ist."""
    _COOLDOWN_HOURS = 24.0

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                             current_time, entry_tag, side, **kwargs):
        closed_trades = [t for t in Trade.get_trades_proxy(pair=pair, is_open=False)]
        if closed_trades:
            last_trade = max(closed_trades, key=lambda t: t.close_date)
            if last_trade.exit_reason and "stop_loss" in last_trade.exit_reason:
                hours_since = (current_time - last_trade.close_date_utc).total_seconds() / 3600.0
                if hours_since < self._COOLDOWN_HOURS:
                    return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard5_CapitalSkim(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard5
):
    """Profit-Skimming gegen Compounding-Tail-Risiko: der %-Positions-Cap
    bezieht sich normalerweise auf das AKTUELLE (unbegrenzt mitwachsende)
    Kapital -- genau das liess die NEAR/ZEC-Einzeltrade-Verluste spaeter im
    Backtest so gross werden. Diese Variante "deckelt" das fuer den Cap
    verwendete Kapital auf maximal das 3-fache des Startkapitals, so als
    wuerde alles ueber diesem Wachstumsfaktor regelmaessig abgeschoepft."""
    _CAPITAL_SKIM_MULTIPLE = 3.0

    def _position_cap(self):
        try:
            total = self.wallets.get_total_stake_amount()
        except Exception:
            total = self.config.get("dry_run_wallet", 10000)
        start_capital = self.config.get("dry_run_wallet", 10000)
        capped_total = min(total, start_capital * self._CAPITAL_SKIM_MULTIPLE)
        return capped_total * self._MAX_POSITION_FRACTION


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard5_MomentumFilter(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CrashGuard5
):
    """Momentum-Qualitaetsfilter: blockiert ein Entry-Signal, wenn der
    24h-Return dieses Coins unter dem Median-24h-Return des gesamten
    86-Coin-Universums liegt -- nimmt nur Signale in Coins mit
    ueberdurchschnittlicher relativer Staerke, statt jedes Signal
    gleich zu behandeln (Annaeherung an echtes Cross-Pair-Ranking, das
    freqtrades Pair-fuer-Pair-Entry-Verarbeitung so nicht directly erlaubt)."""

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                             current_time, entry_tag, side, **kwargs):
        import numpy as np
        import pandas as pd
        all_pairs = tuple(self.config.get("exchange", {}).get("pair_whitelist", []))
        ts, _, median_mom_arr, momentum_by_pair = _load_universe_aggregates(all_pairs)
        t = np.int64(pd.Timestamp(current_time).value)
        idx = np.searchsorted(ts, t, side="right") - 1
        if idx >= 0 and pair in momentum_by_pair:
            pair_ts, pair_mom = momentum_by_pair[pair]
            pair_idx = np.searchsorted(pair_ts, t, side="right") - 1
            if pair_idx >= 0:
                own_mom = pair_mom[pair_idx]
                median_mom = median_mom_arr[idx]
                if np.isfinite(own_mom) and np.isfinite(median_mom) and own_mom < median_mom:
                    return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


# ============================================================================
# Vierte Optimierungsrunde auf der Live-Basis (GrindLimit15+ROI+ThinCap2500,
# ohne CrashGuard -- der sich ueber mehrere Fenster als nicht robust erwies).
# ============================================================================

class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TrailingStop(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Trailing-Stop ab 10% Profit (statt des reinen ROI-Komplett-Exits):
    sobald ein Trade 10% im Plus steht, zieht ein Trailing-Stop mit 3%
    Abstand nach -- soll mehr vom Trend mitnehmen, wenn der Kurs nach dem
    Erreichen der ersten ROI-Schwelle noch weiterlaeuft, statt starr beim
    ersten Ziel komplett zu verkaufen."""
    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.10
    trailing_only_offset_is_reached = True


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_VolumeFilter(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Volumen-Bestaetigungsfilter: blockiert ein Entry-Signal, wenn das
    aktuelle 5m-Volumen unter dem 20-Perioden-Durchschnitt liegt -- soll
    Fehlsignale bei auslaufenden/duennen Bewegungen vermeiden."""
    _VOL_MEAN_PERIOD = 20

    def populate_indicators(self, dataframe, metadata):
        dataframe = super().populate_indicators(dataframe, metadata)
        dataframe["%-vol_mean_ratio"] = (
            dataframe["volume"] / dataframe["volume"].rolling(self._VOL_MEAN_PERIOD).mean()
        )
        return dataframe

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                             current_time, entry_tag, side, **kwargs):
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(df) > 0:
            last_ratio = df["%-vol_mean_ratio"].iloc[-1]
            if last_ratio == last_ratio and last_ratio < 1.0:  # NaN-sicherer Check
                return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_WideRebuy(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Rebuy-Schwellen erneut getestet (frueher auf Basis ohne ROI-Tabelle
    als wirkungslos befunden, da die Strategie fuer diese Trades den
    grinding_v2-Pfad statt des rebuy_mode-Pfads nutzt) -- Re-Check auf der
    aktuellen Basis, falls die ROI-Tabelle das genutzte Exit-Verhalten
    inzwischen veraendert hat."""
    rebuy_mode_thresholds_futures = [-0.12, -0.16]


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TaperStake(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500
):
    """Wie WideRebuy, aber mit abnehmender Rebuy-Stake-Kurve (frueher
    ebenfalls wirkungslos)."""
    rebuy_mode_thresholds_futures = [-0.08, -0.12, -0.16, -0.20]
    rebuy_mode_stakes_futures = [1.0, 0.7, 0.5, 0.3]


# Individuelle ThinCap-Werte: die 25 Tranche-3-Coins sind nicht alle gleich
# duenn gehandelt. Grobe Zweiteilung nach bekannter Marktkapitalisierung/
# Liquiditaet -- die groesseren/etablierteren Alts bekommen mehr Spielraum,
# die kleinsten/spekulativsten bleiben eng gedeckelt.
_THIN_TIER_A_KF = {  # etablierter/liquider innerhalb der Tranche-3-Gruppe
    "1INCH/USD:USD", "CVX/USD:USD", "ENS/USD:USD", "FET/USD:USD", "IMX/USD:USD",
    "MNT/USD:USD", "QNT/USD:USD", "STRK/USD:USD", "SUSHI/USD:USD", "XTZ/USD:USD",
    "YFI/USD:USD",
}
_THIN_TIER_B_KF = _THIN_LIQUIDITY_PAIRS_KF - _THIN_TIER_A_KF  # kleinste/spekulativste


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCapTiered(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI
):
    """Wie ThinCap2500, aber zweistufig statt ein Pauschalwert: Tier A
    (etabliertere Tranche-3-Alts) 3.500 USD, Tier B (kleinste/spekulativste)
    1.800 USD."""
    _THIN_TIER_A_CAP_USD = 3500.0
    _THIN_TIER_B_CAP_USD = 1800.0

    def _tiered_cap(self, pair):
        if pair in _THIN_TIER_A_KF:
            return self._THIN_TIER_A_CAP_USD
        if pair in _THIN_TIER_B_KF:
            return self._THIN_TIER_B_CAP_USD
        return None

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        cap = self._tiered_cap(pair)
        if cap is not None:
            stake = min(stake, cap)
            if min_stake is not None and stake < min_stake:
                stake = min_stake
        return stake

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                               min_stake, max_stake, current_entry_rate, current_exit_rate,
                               current_entry_profit, current_exit_profit, **kwargs):
        proposed = super().adjust_trade_position(
            trade, current_time, current_rate, current_profit, min_stake, max_stake,
            current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit, **kwargs)
        cap = self._tiered_cap(trade.pair)
        if proposed is None or cap is None:
            return proposed
        if isinstance(proposed, tuple):
            amount, order_tag = proposed[0], proposed[1]
        else:
            amount, order_tag = proposed, None
        if amount is None or amount <= 0:
            return proposed
        current_stake = trade.stake_amount or 0.0
        if current_stake >= cap:
            return None
        amount = min(amount, cap - current_stake)
        return (amount, order_tag) if order_tag is not None else amount


# ============================================================================
# Derisk-Kalibrierung fuer 4x Hebel. Neue Trades laufen in NFI ueber
# system_v4 (system_name_use = system_v4); dessen Derisk-Schwellen werden durch
# den Hebel geteilt, sind also in Margin-% definiert und loesen bei 4x schon bei
# 25% kleineren Kursbewegungen aus als fuer NFI's 3x vorgesehen.
# ============================================================================

_V4_BASE = NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_DeriskScaled(_V4_BASE):
    """system_v4-Derisk-Schwellen x4/3 (Kurs-% wie bei 3x Hebel)."""
    system_v4_derisk_level_1_futures = [-0.24, -0.467]
    system_v4_derisk_level_2_futures = [-0.32, -0.72]
    system_v4_derisk_level_3_futures = [-0.40, -0.80]


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_DeriskSmaller(_V4_BASE):
    """Bei Derisk nur halb so viel verkaufen (10/15/25% statt 20/30/50%)."""
    system_v4_derisk_level_1_stake_futures = 0.10
    system_v4_derisk_level_2_stake_futures = 0.15
    system_v4_derisk_level_3_stake_futures = 0.25


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_DeriskHold(_V4_BASE):
    """NFI-eigene, standardmaessig deaktivierte Derisk-Hold-Regel: kein Derisk,
    solange der Tagestrend intakt ist (ROC_9_1d > -10)."""
    bad_trade_controller_derisk_hold_enable = True


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_CapGate(_V4_BASE):
    """NFI-eigenes, standardmaessig deaktiviertes Kapitulations-Gate: keine
    Grind-Nachkaeufe jenseits Derisk-Level-1 solange MFI_14_4h < 30."""
    bad_trade_controller_capitulation_add_gate_enable = True


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_HoldCapGate(_V4_BASE):
    bad_trade_controller_derisk_hold_enable = True
    bad_trade_controller_capitulation_add_gate_enable = True


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_NoDerisk(_V4_BASE):
    """Diagnose: Derisk komplett aus (zeigt den Netto-Wert des Derisk)."""
    derisk_enable = False


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_DeriskTighter(_V4_BASE):
    """system_v4-Derisk-Schwellen x3/4 (frueher derisken)."""
    system_v4_derisk_level_1_futures = [-0.135, -0.26]
    system_v4_derisk_level_2_futures = [-0.18, -0.405]
    system_v4_derisk_level_3_futures = [-0.225, -0.45]


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_DeriskBigger(_V4_BASE):
    """Bei Derisk 1,5x so viel verkaufen (30/45/75%)."""
    system_v4_derisk_level_1_stake_futures = 0.30
    system_v4_derisk_level_2_stake_futures = 0.45
    system_v4_derisk_level_3_stake_futures = 0.75


class NFI_KF_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_WithShorts(_V4_BASE):
    """Live-Basis, aber mit NFI-Shorts (502/542/562 usw.) wieder aktiviert."""
    def __init__(self, config):
        super().__init__(config)
        self.can_short = True


class NFI_KF_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_WithShortsLev2(
    NFI_KF_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_WithShorts
):
    """Shorts aktiv, aber nur mit 2x Hebel (Short-Squeeze-Risiko), Longs 4x."""
    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        return 2.0 if side == "short" else 4.0


_btc_sma_cache = {}


def _load_btc_below_sma_array(sma_hours):
    """(Kerzen-Schlusszeit ns, BTC-Schluss < SMA) aus BTC-1h-Daten; nur
    abgeschlossene Kerzen -> PIT-sicher."""
    if sma_hours not in _btc_sma_cache:
        import os
        import pandas as pd
        path = os.path.join(os.path.dirname(__file__), "..", "data", "krakenfutures", "futures",
                            "BTC_USD_USD-1h-futures.feather")
        try:
            df = pd.read_feather(path).sort_values("date")
            sma = df["close"].rolling(sma_hours, min_periods=sma_hours).mean()
            below = (df["close"] < sma).to_numpy() & sma.notna().to_numpy()
            close_ts = (df["date"].astype("int64") * 1_000_000).to_numpy() + 3_600_000_000_000
            _btc_sma_cache[sma_hours] = (close_ts, below)
        except Exception:
            _btc_sma_cache[sma_hours] = None
    return _btc_sma_cache[sma_hours]


class NFI_KF_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_ShortsBearOnly(
    NFI_KF_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_WithShorts
):
    """Shorts nur, wenn BTC unter seinem 50-Tage-Durchschnitt notiert
    (Baerenmarkt-Regime). Longs unveraendert."""
    _BTC_SMA_HOURS = 50 * 24

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                             current_time, entry_tag, side, **kwargs):
        if side == "short":
            import numpy as np
            import pandas as pd
            arrs = _load_btc_below_sma_array(self._BTC_SMA_HOURS)
            if arrs is None:
                return False
            ts, below = arrs
            idx = np.searchsorted(ts, np.int64(pd.Timestamp(current_time).value), side="right") - 1
            if idx < 0 or not below[idx]:
                return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_ShortsBearOnly100(
    NFI_KF_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_ShortsBearOnly
):
    _BTC_SMA_HOURS = 100 * 24


# ============================================================================
# NFI beschraenkt die profitabelsten Signale (Top-Coins-Modus 141-145) auf eine
# feste Liste von 56 Coins; 38 unserer 86 Coins sind dort nicht enthalten.
# ============================================================================

_KF_TOP_EXTRA_LIQUID = [
    "ASTER", "AXS", "COMP", "EGLD", "ENA", "GRT", "PENGU", "PEPE", "PUMP",
    "PYTH", "RAY", "SHIB", "SNX", "STX", "TAO", "TRUMP", "XPL",
]
_KF_TOP_EXTRA_THIN = [
    "BAT", "CFX", "CHZ", "CVX", "ENS", "FET", "FLOW", "IMX", "JASMY", "KAVA",
    "LPT", "LUNA2", "MANA", "MNT", "ORDI", "QNT", "QTUM", "ROSE", "STRK",
    "SUSHI", "YFI",
]


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopLiquid(_V4_BASE):
    """Top-Coins-Modus (141-145) zusaetzlich fuer die 17 liquiden Nicht-Top-Coins."""
    top_coins_mode_coins = NostalgiaForInfinityX8.top_coins_mode_coins + _KF_TOP_EXTRA_LIQUID


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopAll(_V4_BASE):
    """Top-Coins-Modus (141-145) fuer alle 86 Coins."""
    top_coins_mode_coins = (NostalgiaForInfinityX8.top_coins_mode_coins
                            + _KF_TOP_EXTRA_LIQUID + _KF_TOP_EXTRA_THIN)


_KF_MEME = {"PEPE", "SHIB", "PENGU", "TRUMP", "PUMP"}


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopAllNoMeme(_V4_BASE):
    """Top-Coins-Modus fuer alle 86 Coins ausser Meme-Coins (Liquidations-
    risiko bei Crash-Kerzen, z.B. PEPE 13.04.2024)."""
    top_coins_mode_coins = NostalgiaForInfinityX8.top_coins_mode_coins + [
        c for c in _KF_TOP_EXTRA_LIQUID + _KF_TOP_EXTRA_THIN if c not in _KF_MEME]


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopAllMeme2x(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopAll
):
    """Top-Coins-Modus fuer alle 86 Coins, Meme-Coins aber nur mit 2x Hebel
    (Liquidationsabstand ~50% statt ~25%)."""
    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        if pair.partition("/")[0] in _KF_MEME:
            return 2.0
        return 4.0


# ============================================================================
# Weitere NFI-Code-Hebel: Grind-Modus (Tag 120) auf Coin-Liste + 1 Slot
# beschraenkt; experimentelle Einstiegssignale 7-11 standardmaessig aus.
# ============================================================================

_KF_ALL_COINS = (NostalgiaForInfinityX8.top_coins_mode_coins
                 + _KF_TOP_EXTRA_LIQUID + _KF_TOP_EXTRA_THIN)


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_GrindModeAll(_V4_BASE):
    """Grind-Modus (Tag 120) fuer alle Coins (ohne Meme) und 2 statt 1 Slot."""
    grind_mode_coins = sorted(set(NostalgiaForInfinityX8.grind_mode_coins)
                              | {c for c in _KF_ALL_COINS if c not in _KF_MEME})
    grind_mode_max_slots = 2


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_Exp78(_V4_BASE):
    """NFI-Experimentalsignale 7 (ADX Trend-Birth) + 8 (Donchian-Breakout) an."""
    long_entry_signal_params = {
        **NostalgiaForInfinityX8.long_entry_signal_params,
        "long_entry_condition_7_enable": True,
        "long_entry_condition_8_enable": True,
    }


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_Exp7to11(_V4_BASE):
    """Alle NFI-Experimentalsignale 7-11 an."""
    long_entry_signal_params = {
        **NostalgiaForInfinityX8.long_entry_signal_params,
        **{f"long_entry_condition_{i}_enable": True for i in range(7, 12)},
    }


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopNoMemeGrindAll(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopAllNoMeme
):
    """Kandidat: Top-Coins-Modus fuer alle Coins ausser Meme + Grind-Modus
    fuer alle Coins ausser Meme mit 2 Slots."""
    grind_mode_coins = NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_GrindModeAll.grind_mode_coins
    grind_mode_max_slots = 2


# ============================================================================
# Tranche 4: 8 weitere Nicht-Meme-Coins mit ueberdurchschnittlichem Volumen
# (Daten ab 02/2025). Vorsorglich mit 2.500-USD-Deckel wie duenne Coins.
# ============================================================================

_KF_TRANCHE4 = ["ZRO", "SYN", "KAS", "GRASS", "ACE", "VIRTUAL", "JTO", "EIGEN"]
_KF_TRANCHE4_PAIRS = {f"{c}/USD:USD" for c in _KF_TRANCHE4}


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopNoMemeGrindAll_T4(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopNoMemeGrindAll
):
    top_coins_mode_coins = sorted(set(
        NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopNoMemeGrindAll.top_coins_mode_coins
        + _KF_TRANCHE4))
    grind_mode_coins = sorted(set(
        NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopNoMemeGrindAll.grind_mode_coins
        + _KF_TRANCHE4))

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        if pair in _KF_TRANCHE4_PAIRS:
            stake = min(stake, self._THIN_PAIR_ABS_CAP_USD)
            if min_stake is not None and stake < min_stake:
                return min_stake
        return stake


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopNoMemeGrindAll_No4363(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopNoMemeGrindAll
):
    """Kombination ohne die beiden ueber Fenster verlustreichen Signale 43 und 63."""
    long_entry_signal_params = {
        **NostalgiaForInfinityX8.long_entry_signal_params,
        "long_entry_condition_43_enable": False,
        "long_entry_condition_63_enable": False,
    }


class NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopNoMemeGrindAll_Rebuy50(
    NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopNoMemeGrindAll
):
    """Rebuy-Modus-Startstake 0,50 statt 0,25 (Tag 64: 24 Trades, 0 Verluste)."""
    system_v4_rebuy_mode_stake_multiplier = 0.50


# ============================================================================
# Kapital-Effizienz: v6 belegt nie alle 5 Slots (Median-Haltedauer 2-5 h), der
# 15%-Positionsdeckel (inkl. Nachkaeufe) ist der eigentliche Engpass und
# blockiert zugleich NFIs Grinding (Erst-Entry nutzt bereits die vollen 15%).
# ============================================================================

_V6_BASE = NFI_KF_LongOnly_Hold90_Lev4_GrindLimit15_ROI_ThinCap2500_TopNoMemeGrindAll


class NFI_KF_V6_Cap20(_V6_BASE):
    _MAX_POSITION_FRACTION = 0.20


class NFI_KF_V6_Cap25(_V6_BASE):
    _MAX_POSITION_FRACTION = 0.25


class NFI_KF_V6_Cap30(_V6_BASE):
    _MAX_POSITION_FRACTION = 0.30


class NFI_KF_V6_Init10Cap20(_V6_BASE):
    """NFI wie vorgesehen: Erst-Entry 10% des Kapitals, Nachkaeufe bis 20%."""
    _MAX_POSITION_FRACTION = 0.20
    _INITIAL_FRACTION = 0.10

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        try:
            total = self.wallets.get_total_stake_amount()
        except Exception:
            total = self.config.get("dry_run_wallet", 10000)
        stake = min(stake, total * self._INITIAL_FRACTION)
        if min_stake is not None and stake < min_stake:
            return min_stake
        return stake


class NFI_KF_V6_ROI35(_V6_BASE):
    minimal_roi = {"0": 0.35, "1440": 0.10, "4320": 0.05}


class NFI_KF_V6_ROI50(_V6_BASE):
    minimal_roi = {"0": 0.50, "1440": 0.10, "4320": 0.05}


class NFI_KF_V6_NoROI(_V6_BASE):
    minimal_roi = {"0": 100.0}


class NFI_KF_V6_Init25Cap30(_V6_BASE):
    """Erst-Entry als fester Kapitalanteil (statt Kapital/MOT), Slots bleiben 5:
    Erst-Entry 25% des Gesamtkapitals, Gesamtposition inkl. Nachkaeufe max. 30%.
    Begrenzung durch freies Kapital (max_stake) bleibt: in Crash-Wellen mit vielen
    gleichzeitigen Signalen bekommen spaetere Trades automatisch nur den Rest.
    Duenne Coins behalten ihren 2.500-USD-Deckel."""
    _MAX_POSITION_FRACTION = 0.30
    _INITIAL_FRACTION = 0.25

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        if pair in _THIN_LIQUIDITY_PAIRS_KF:
            return stake
        try:
            total = self.wallets.get_total_stake_amount()
        except Exception:
            total = self.config.get("dry_run_wallet", 10000)
        stake = max(stake, total * self._INITIAL_FRACTION)
        stake = min(stake, total * self._MAX_POSITION_FRACTION)
        if max_stake is not None:
            stake = min(stake, max_stake)
        if min_stake is not None and stake < min_stake:
            return min_stake
        return stake


class NFI_KF_V6_Init30Cap35(NFI_KF_V6_Init25Cap30):
    _MAX_POSITION_FRACTION = 0.35
    _INITIAL_FRACTION = 0.30


class NFI_KF_V6_Init35Cap40(NFI_KF_V6_Init25Cap30):
    _MAX_POSITION_FRACTION = 0.40
    _INITIAL_FRACTION = 0.35


class NFI_KF_V6_Cap25ROI50(NFI_KF_V6_Cap25):
    minimal_roi = {"0": 0.50, "1440": 0.10, "4320": 0.05}


class NFI_KF_V6_Scale125Cap30(_V6_BASE):
    """Korrigierte Variante von Init25Cap30: skaliert NFIs eigene Stake-Berechnung
    (proposed_stake x Faktor) statt sie zu ueberschreiben. Dadurch bleiben NFIs
    Modus-Multiplikatoren erhalten (Rebuy-Modus 0,25x, Grind-Modus 0,2x ...).
    Faktor 1,25 bei 5 Slots = Erst-Entry 25% statt 20% fuer normale Signale."""
    _MAX_POSITION_FRACTION = 0.30
    _STAKE_SCALE = 1.25

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake * self._STAKE_SCALE, min_stake,
            max_stake, leverage, entry_tag, side, **kwargs)
        if max_stake is not None:
            stake = min(stake, max_stake)
        return stake


class NFI_KF_V6_Scale150Cap35(NFI_KF_V6_Scale125Cap30):
    _MAX_POSITION_FRACTION = 0.35
    _STAKE_SCALE = 1.50


# ============================================================================
# Modus-spezifische Groesse/Hebel auf Basis v7 (Cap25). Top-Coins-Modus
# (141-145) liefert ~94% des Gewinns, Rebuy-Modus (61-65) schwankt stark.
# ============================================================================

def _is_rebuy_mode(strategy, entry_tag):
    tags = (entry_tag or "").split()
    if not tags:
        return False
    return all(c in strategy.long_rebuy_mode_tags for c in tags) or (
        any(c in strategy.long_rebuy_mode_tags for c in tags)
        and all(c in strategy.long_rebuy_grind_mode_tags for c in tags))


class NFI_KF_V7_RebuyLev3(NFI_KF_V6_Cap25):
    """Rebuy-Modus mit NFIs eigenem Rebuy-Hebel (3x) statt pauschal 4x."""
    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        return 3.0 if _is_rebuy_mode(self, entry_tag) else 4.0


class NFI_KF_V7_TopScale125(NFI_KF_V6_Cap25):
    """Nur Top-Coins-Signale (141-145) mit 1,25x Erst-Entry (25% statt 20%),
    Gesamtdeckel 30%; alle anderen Modi unveraendert."""
    _MAX_POSITION_FRACTION = 0.30
    _TOP_SCALE = 1.25

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        tags = (entry_tag or "").split()
        is_top = bool(tags) and all(c in self.long_top_coins_mode_tags for c in tags)
        scale = self._TOP_SCALE if is_top else 1.0
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake * scale, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        if not is_top:
            # Nicht-Top-Modi bleiben exakt bei v7 (Deckel 25%)
            try:
                total = self.wallets.get_total_stake_amount()
            except Exception:
                total = self.config.get("dry_run_wallet", 10000)
            stake = min(stake, total * 0.25)
        if max_stake is not None:
            stake = min(stake, max_stake)
        return stake


class NFI_KF_V7_TopScale125_RebuyLev3(NFI_KF_V7_TopScale125):
    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        return 3.0 if _is_rebuy_mode(self, entry_tag) else 4.0


class NFI_KF_V7_TopScale150(NFI_KF_V7_TopScale125):
    """Nur Top-Coins-Signale mit 1,5x Erst-Entry (30%), Gesamtdeckel 35%."""
    _MAX_POSITION_FRACTION = 0.35
    _TOP_SCALE = 1.50


# ============================================================================
# Risiko-adaptive Groesse fuer Top-Coins-Signale: vergroessern nur, wenn das
# Umfeld es traegt. Schwachstelle aller Groessen-Varianten war das Crash-Fenster
# (mehr Drawdown, kein Mehrgewinn).
# ============================================================================

class NFI_KF_V7_TopAdaptive(NFI_KF_V6_Cap25):
    """Top-Coins-Signale mit _TOP_SCALE nur bei 'risk-on', sonst 1,0x (= v7).
    risk-on wird von Unterklassen definiert (_risk_on)."""
    _MAX_POSITION_FRACTION = 0.30
    _TOP_SCALE = 1.25

    def _risk_on(self, current_time):
        return True

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        tags = (entry_tag or "").split()
        is_top = bool(tags) and all(c in self.long_top_coins_mode_tags for c in tags)
        scale = self._TOP_SCALE if (is_top and self._risk_on(current_time)) else 1.0
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake * scale, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        if scale == 1.0:
            try:
                total = self.wallets.get_total_stake_amount()
            except Exception:
                total = self.config.get("dry_run_wallet", 10000)
            stake = min(stake, total * 0.25)
        if max_stake is not None:
            stake = min(stake, max_stake)
        return stake


class NFI_KF_V7_TopRegime125(NFI_KF_V7_TopAdaptive):
    """risk-on = BTC ueber seinem 100-Tage-Durchschnitt (letzte abgeschlossene 1h-Kerze)."""
    _BTC_SMA_HOURS = 100 * 24

    def _risk_on(self, current_time):
        import numpy as np
        import pandas as pd
        arrs = _load_btc_below_sma_array(self._BTC_SMA_HOURS)
        if arrs is None:
            return False
        ts, below = arrs
        idx = np.searchsorted(ts, np.int64(pd.Timestamp(current_time).value), side="right") - 1
        return idx >= 0 and not below[idx]


class NFI_KF_V7_TopRegime150(NFI_KF_V7_TopRegime125):
    _MAX_POSITION_FRACTION = 0.35
    _TOP_SCALE = 1.50


class NFI_KF_V7_TopDDGuard150(NFI_KF_V7_TopAdaptive):
    """risk-on = Konto hoechstens 5% unter seinem bisherigen Hoechststand."""
    _MAX_POSITION_FRACTION = 0.35
    _TOP_SCALE = 1.50
    _DD_LIMIT = 0.05

    def _risk_on(self, current_time):
        try:
            eq = self.wallets.get_total_stake_amount()
        except Exception:
            return True
        peak = max(getattr(self, "_eq_peak", eq), eq)
        self._eq_peak = peak
        return eq >= peak * (1.0 - self._DD_LIMIT)


class NFI_KF_V7_TopScale125_Slots(NFI_KF_V7_TopScale125):
    """v7+ mit mehr Slots (per --max-open-trades), aber gleicher Positionsgroesse
    wie bei 5 Slots: proposed_stake (= Kapital/MOT) wird mit MOT/5 kompensiert.
    Zusatz-Slots greifen nur in Signal-Wellen und erhalten dann das noch freie
    Kapital (max_stake), mehr als 100% Marge ist nie moeglich."""
    _BASE_SLOTS = 5

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        mot = self.config.get("max_open_trades", self._BASE_SLOTS) or self._BASE_SLOTS
        comp = max(1.0, mot / self._BASE_SLOTS)
        return super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake * comp, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)


# ============================================================================
# Allgemeine v7+-Klasse: Hebel und Margen-Multiplikator getrennt einstellbar.
# Gleiche Positionsgroesse (Notional) bei weniger Hebel = mehr Abstand zur
# Liquidation; das zusaetzlich gebundene Kapital liegt sonst ohnehin brach.
# Mit _LEV=4, _MM=1 identisch zu NFI_KF_V7_TopScale125.
# ============================================================================

class NFI_KF_V7P_Gen(NFI_KF_V6_Cap25):
    _LEV = 4.0
    _MM = 1.0              # Margen-Multiplikator (4/Hebel fuer gleiches Notional)
    _TOP_SCALE = 1.25
    _TOP_CAP = 0.30
    _NONTOP_CAP = 0.25

    @property
    def _MAX_POSITION_FRACTION(self):
        return self._TOP_CAP * self._MM

    @property
    def _THIN_PAIR_ABS_CAP_USD(self):
        return 2500.0 * self._MM

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        return self._LEV

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        tags = (entry_tag or "").split()
        is_top = bool(tags) and all(c in self.long_top_coins_mode_tags for c in tags)
        scale = (self._TOP_SCALE if is_top else 1.0) * self._MM
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake * scale, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        if not is_top:
            try:
                total = self.wallets.get_total_stake_amount()
            except Exception:
                total = self.config.get("dry_run_wallet", 10000)
            stake = min(stake, total * self._NONTOP_CAP * self._MM)
        if max_stake is not None:
            stake = min(stake, max_stake)
        return stake


class NFI_KF_V7P_Lev3(NFI_KF_V7P_Gen):
    """v7+ mit 3x Hebel und 4/3 Marge (gleiches Notional, Liquidation ~33% statt ~25%)."""
    _LEV = 3.0
    _MM = 4.0 / 3.0


class NFI_KF_V7P_Lev2(NFI_KF_V7P_Gen):
    """v7+ mit 2x Hebel und doppelter Marge (gleiches Notional, Liquidation ~50%)."""
    _LEV = 2.0
    _MM = 2.0


class NFI_KF_V7_TopScale125_Grind10(NFI_KF_V7_TopScale125):
    _MAX_GRIND_ORDERS = 10


class NFI_KF_V7_TopScale125_Grind25(NFI_KF_V7_TopScale125):
    _MAX_GRIND_ORDERS = 25


class NFI_KF_V7_TopScale125_Hold30(NFI_KF_V7_TopScale125):
    _MAX_HOLD_DAYS = 30.0


class NFI_KF_V7_TopScale125_Hold45(NFI_KF_V7_TopScale125):
    _MAX_HOLD_DAYS = 45.0


# ============================================================================
# Freqtrade-Protections (bisher keine aktiv) auf Basis v7+.
# Backtest nur mit --enable-protections wirksam; live immer aktiv.
# ============================================================================

class NFI_KF_V7P_ProtLowProfit(NFI_KF_V7_TopScale125):
    """Sperrt einen Coin 3 Tage, wenn sein letzter Trade (7-Tage-Fenster) unter -5% lag."""
    @property
    def protections(self):
        return [{"method": "LowProfitPairs", "lookback_period_candles": 2016, "trade_limit": 1,
                 "stop_duration_candles": 864, "required_profit": -0.05, "only_per_pair": True}]


class NFI_KF_V7P_ProtMaxDD(NFI_KF_V7_TopScale125):
    """Keine neuen Entries fuer 12h, wenn die geschlossenen Trades der letzten 7 Tage
    zusammen mehr als 10% Drawdown ergeben."""
    @property
    def protections(self):
        return [{"method": "MaxDrawdown", "lookback_period_candles": 2016, "trade_limit": 3,
                 "stop_duration_candles": 144, "max_allowed_drawdown": 0.10}]


class NFI_KF_V7P_ProtCooldown(NFI_KF_V7_TopScale125):
    """Nach einem Exit 1h kein erneuter Entry auf demselben Coin."""
    @property
    def protections(self):
        return [{"method": "CooldownPeriod", "stop_duration_candles": 12}]


# ============================================================================
# Signal-Stufen: Trade-Analyse v7+ (8 Fenster) -- Signal 145 verursacht die
# Haelfte aller Verluste (Gewinn/Verlust 1,8 vs. ~10 bei 141-144).
# ============================================================================

class NFI_KF_V7P_Tier(NFI_KF_V6_Cap25):
    """Erst-Entry-Skalierung je Signal-Gruppe; Deckel je Gruppe = 0,25 x max(1, Skala)."""
    _SCALES = {"141": 1.5, "142": 1.5, "143": 1.5, "144": 1.5, "145": 1.0}
    _DEFAULT_SCALE = 1.0
    _MODE_SCALES = {}          # z.B. {"rebuy": 0.75, "quick": 0.75}
    _MAX_POSITION_FRACTION = 0.35   # globaler Deckel (Grinds), Gruppen-Deckel unten

    def _scale_for(self, entry_tag):
        tags = (entry_tag or "").split()
        if tags and all(c in self.long_top_coins_mode_tags for c in tags):
            return min(self._SCALES.get(c, 1.0) for c in tags)
        if tags and all(c in self.long_quick_mode_tags for c in tags):
            return self._MODE_SCALES.get("quick", self._DEFAULT_SCALE)
        if _is_rebuy_mode(self, entry_tag):
            return self._MODE_SCALES.get("rebuy", self._DEFAULT_SCALE)
        return self._DEFAULT_SCALE

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        scale = self._scale_for(entry_tag)
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake * scale, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        try:
            total = self.wallets.get_total_stake_amount()
        except Exception:
            total = self.config.get("dry_run_wallet", 10000)
        stake = min(stake, total * 0.25 * max(1.0, scale))
        if max_stake is not None:
            stake = min(stake, max_stake)
        if min_stake is not None and stake < min_stake:
            return min_stake
        return stake


class NFI_KF_V7P_TierPlus(NFI_KF_V7P_Tier):
    _MODE_SCALES = {"rebuy": 0.75, "quick": 0.75}


class NFI_KF_V7P_TierSafe(_ROISafeExitMixin, NFI_KF_V7P_Tier):
    """Stufenmodell A + kein ROI-Exit, solange der Trade inkl. Derisk-Verkaeufe
    insgesamt im Minus ist (Grinding darf aufholen; Slots sind nie alle belegt)."""


class NFI_KF_V7P_Tier145Low(NFI_KF_V7P_Tier):
    _SCALES = {"141": 1.5, "142": 1.5, "143": 1.5, "144": 1.5, "145": 0.75}


class NFI_KF_V7P_Tier175(NFI_KF_V7P_Tier):
    _SCALES = {"141": 1.75, "142": 1.75, "143": 1.75, "144": 1.75, "145": 1.0}
    _MAX_POSITION_FRACTION = 0.40


class NFI_KF_V7P_TierC(NFI_KF_V7P_Tier):
    """Stufen C: starke Top-Signale 141-144 x1,75, schwaches 145 x0,75, Rest x1,0."""
    _SCALES = {"141": 1.75, "142": 1.75, "143": 1.75, "144": 1.75, "145": 0.75}
    _MAX_POSITION_FRACTION = 0.40


# ============================================================================
# v8-Kandidat = Stufenmodell A + Signal 145 x0,75. Darauf: Volatilitaets-
# Normierung der Positionsgroesse (Tagesvola aus den letzten 3 Tagen 5m,
# PIT-sicher ueber den analysierten Dataframe bis zur aktuellen Kerze).
# ============================================================================

NFI_KF_V8 = NFI_KF_V7P_Tier145Low


class NFI_KF_V8_VolNorm(NFI_KF_V7P_Tier145Low):
    _VOL_TARGET = 0.046      # Median-Tagesvola der 86 Coins 2025-2026
    _VOL_MIN = 0.6
    _VOL_MAX = 1.4
    _VOL_CANDLES = 864       # 3 Tage 5m

    def _vol_factor(self, pair):
        try:
            import numpy as np
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            closes = df["close"].iloc[-(self._VOL_CANDLES + 1):]
            if len(closes) < self._VOL_CANDLES // 2:
                return 1.0
            vol = float(np.log(closes).diff().std() * np.sqrt(288))
            if not np.isfinite(vol) or vol <= 0:
                return 1.0
            return float(min(self._VOL_MAX, max(self._VOL_MIN, self._VOL_TARGET / vol)))
        except Exception:
            return 1.0

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        vf = self._vol_factor(pair)
        return super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake * vf, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)


class NFI_KF_V8_VolDown(NFI_KF_V8_VolNorm):
    """Nur verkleinern: volatile Coins kleiner, ruhige nie groesser als im Stufenmodell."""
    _VOL_MAX = 1.0


class NFI_KF_V8_StrongROI35(NFI_KF_V7P_Tier145Low):
    """Starke Top-Signale (141-144) duerfen bis +35% laufen (Sofort-ROI), alle
    anderen Signale behalten die bisherigen +25% (per custom_exit)."""
    minimal_roi = {"0": 0.35, "1440": 0.10, "4320": 0.05}
    _STRONG = ("141", "142", "143", "144")
    _OTHER_INSTANT_ROI = 0.25

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        tags = (trade.enter_tag or "").split()
        is_strong = bool(tags) and all(c in self._STRONG for c in tags)
        if not is_strong and current_profit >= self._OTHER_INSTANT_ROI:
            return "roi_25"
        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)


class NFI_KF_V8_StrongROI50(NFI_KF_V8_StrongROI35):
    minimal_roi = {"0": 0.50, "1440": 0.10, "4320": 0.05}


class NFI_KF_V8_Normal15(NFI_KF_V7P_Tier145Low):
    """v8 + NFI-Normalmodus (Signale 1-13, 0 Verlierer in 8 Fenstern) x1,5."""
    _EXTRA = {"normal": 1.5}

    def _scale_for(self, entry_tag):
        tags = (entry_tag or "").split()
        if tags and all(c in self.long_normal_mode_tags for c in tags) and "normal" in self._EXTRA:
            return self._EXTRA["normal"]
        if tags and all(c in self.long_scalp_mode_tags for c in tags) and "scalp" in self._EXTRA:
            return self._EXTRA["scalp"]
        if tags and all(c in self.long_rapid_mode_tags for c in tags) and "rapid" in self._EXTRA:
            return self._EXTRA["rapid"]
        return super()._scale_for(entry_tag)


class NFI_KF_V8_Clean15(NFI_KF_V8_Normal15):
    """v8 + alle Modi ohne Verlierer (Normal, Scalp, Rapid) x1,5."""
    _EXTRA = {"normal": 1.5, "scalp": 1.5, "rapid": 1.5}


class NFI_KF_V8_CleanG(NFI_KF_V8_Clean15):
    """v8-Kandidat + Grind-Modus (Tag 120) x1,5."""
    def _scale_for(self, entry_tag):
        tags = (entry_tag or "").split()
        if tags and all(c in self.long_grind_mode_tags for c in tags):
            return 1.5
        return super()._scale_for(entry_tag)


class NFI_KF_V8_CleanRQ(NFI_KF_V8_Clean15):
    """v8-Kandidat + schwache Modi Rebuy/Quick x0,75."""
    _MODE_SCALES = {"rebuy": 0.75, "quick": 0.75}


# ============================================================================
# Neue Mechanismen auf Basis v8 (NFI_KF_V8_Clean15)
# ============================================================================

def _is_strong_signal(strategy, entry_tag):
    """Starke Signale laut 8-Fenster-/Walk-Forward-Analyse: Top 141-144 sowie
    Normal-, Scalp- und Rapid-Modus."""
    tags = (entry_tag or "").split()
    if not tags:
        return False
    strong_top = ("141", "142", "143", "144")
    for group in (strong_top, strategy.long_normal_mode_tags, strategy.long_scalp_mode_tags,
                  strategy.long_rapid_mode_tags):
        if all(c in group for c in tags):
            return True
    return False


class NFI_KF_V8_Reserve1(NFI_KF_V8_Clean15):
    """Der letzte freie Slot ist starken Signalen vorbehalten: schwache Signale
    (145, Rebuy, Quick, Grind ...) werden abgelehnt, wenn nur noch ein Slot frei ist."""
    _RESERVED = 1

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs):
        if not _is_strong_signal(self, entry_tag):
            from freqtrade.persistence import Trade as _T
            mot = self.config.get("max_open_trades", 5)
            if _T.get_open_trade_count() >= mot - self._RESERVED:
                return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_V8_Disc03(NFI_KF_V8_Clean15):
    """Erst-Entry als Limit 0,3% unter dem vorgeschlagenen Kurs (Nachkaeufe unveraendert)."""
    _ENTRY_DISCOUNT = 0.003

    def custom_entry_price(self, pair, trade, current_time, proposed_rate, entry_tag, side, **kwargs):
        if trade is None and side == "long":
            return proposed_rate * (1.0 - self._ENTRY_DISCOUNT)
        return proposed_rate


# ============================================================================
# Meme-Coins zurueck in den Top-Coins-Modus, aber mit reduzierter Groesse.
# v6-Test: Top mit Memes H1 364% vs. ohne 287%, aber PEPE-Liquidation 04/2024.
# ============================================================================

class NFI_KF_V8_MemeTop05(NFI_KF_V8_Clean15):
    """v8 + Meme-Coins (PEPE, SHIB, PENGU, TRUMP, PUMP) im Top-Coins-Modus,
    jede Meme-Position mit 0,5x der normalen Groesse (Stufen-Faktor bleibt)."""
    top_coins_mode_coins = sorted(set(NFI_KF_V8_Clean15.top_coins_mode_coins) | _KF_MEME)
    _MEME_SCALE = 0.5

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        scale = self._MEME_SCALE if pair.partition("/")[0] in _KF_MEME else 1.0
        return super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake * scale, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)


class NFI_KF_V8_MemeTop075(NFI_KF_V8_MemeTop05):
    _MEME_SCALE = 0.75


# ============================================================================
# v9-Kandidaten: Derisk (system_v4) verkauft oft am Tief. Was-waere-wenn auf
# den 8 v8-Fenstern: Halten statt Derisk-Verkauf waere in 79 % der Faelle und
# in allen Fenstern besser gewesen (+29,7k USD). Liquidation bei 4x ~ -24 %
# Kurs, daher Derisk nicht abschalten, sondern spaeter/kleiner.
# ============================================================================

class NFI_KF_V9_DeriskL1Off(NFI_KF_V8_Clean15):
    """Derisk Stufe 1 (ab -4,5 % Kurs) aus, Stufen 2 und 3 unveraendert."""
    system_v4_derisk_level_1_enable = False


class NFI_KF_V9_DeriskLoose(NFI_KF_V8_Clean15):
    """Alle Derisk-Schwellen x1,5 (Stufe 3 sofort bei -80 % Marge = -20 % Kurs)."""
    system_v4_derisk_level_1_futures = [-0.27, -0.52]
    system_v4_derisk_level_2_futures = [-0.36, -0.80]
    system_v4_derisk_level_3_futures = [-0.45, -0.80]


class NFI_KF_V9_DeriskSmall(NFI_KF_V8_Clean15):
    """Derisk-Verkaeufe halb so gross (10/15/25 % statt 20/30/50 % der Erstposition)."""
    system_v4_derisk_level_1_stake_futures = 0.10
    system_v4_derisk_level_2_stake_futures = 0.15
    system_v4_derisk_level_3_stake_futures = 0.25


# ============================================================================
# v9-Kandidaten: lange Trades. v8 (8 Fenster): Trades < 24h 461 Stueck, 7
# Verlierer, +319k USD; Trades > 24h 56 Stueck, 16 Verlierer, -20k USD.
# Idee: haengende Trades frueher bei kleinem Gewinn schliessen.
# ============================================================================

class NFI_KF_V9_RoiTail(NFI_KF_V8_Clean15):
    """ROI-Tabelle mit flacherem Ende: ab 2 Tagen +4 %, ab 3 Tagen +2 % Marge."""
    minimal_roi = {"0": 0.25, "1440": 0.10, "2880": 0.04, "4320": 0.02}


class NFI_KF_V9_StaleBE(NFI_KF_V8_Clean15):
    """Nach 48h Exit, sobald der Gesamt-Trade (inkl. Derisk/Grinds) mit
    mindestens +0,5 % Marge im Plus ist."""
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


class NFI_KF_V9_DeriskL1OffStrong(NFI_KF_V8_Clean15):
    """Derisk Stufe 1 nur bei starken Signalen (141-144, Normal, Scalp, Rapid)
    aus; Signal 145 und schwache Modi behalten Stufe 1 (L1Off: H1-DD durch
    NEAR/145 -11,2k)."""
    _cur_enter_tag = None

    @property
    def system_v4_derisk_level_1_enable(self):
        return not _is_strong_signal(self, self._cur_enter_tag)

    def adjust_trade_position(self, trade, *args, **kwargs):
        self._cur_enter_tag = trade.enter_tag
        return super().adjust_trade_position(trade, *args, **kwargs)


class NFI_KF_V9_DeriskL12OffStrong(NFI_KF_V9_DeriskL1OffStrong):
    """Wie L1OffStrong, zusaetzlich Derisk Stufe 2 bei starken Signalen aus
    (Stufe 3 bei -15 % Kurs bleibt als Crash-Schutz)."""

    @property
    def system_v4_derisk_level_2_enable(self):
        return not _is_strong_signal(self, self._cur_enter_tag)


class NFI_KF_V9_L1OffStrongStale(NFI_KF_V9_DeriskL1OffStrong):
    """Kombi: Derisk L1 aus bei starken Signalen + Breakeven-Exit nach 48h
    (StaleBE allein: W2c 39,4 statt 26,2 %, sonst -0,5 bis -2,6 %)."""
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


# ============================================================================
# Gesamt-Exposure-Deckel. Mark-to-Market-Analyse (inkl. offener Positionen,
# 5m-Tiefs): v8 faellt im Crash 03.02.2025 kurzzeitig auf 45 % des Hochs, weil
# bis zu 5 Positionen a 30 % Marge (x4) gleichzeitig offen sind. Freqtrades
# Drawdown zaehlt nur realisierte Verluste und zeigt das nicht.
# ============================================================================

class _ExposureCapMixin:
    """Summe der Margen aller offenen Trades <= _EXPOSURE_CAP x Gesamtkapital
    (neue Trades und Nachkaeufe werden entsprechend verkleinert/abgelehnt)."""
    _EXPOSURE_CAP = 1.0

    def _open_margin(self):
        from freqtrade.persistence import Trade as _T
        return sum((t.stake_amount or 0.0) for t in _T.get_trades_proxy(is_open=True))

    def _exposure_room(self):
        try:
            total = self.wallets.get_total_stake_amount()
        except Exception:
            total = self.config.get("dry_run_wallet", 10000)
        return self._EXPOSURE_CAP * total - self._open_margin()

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        room = self._exposure_room()
        if min_stake is not None and room < min_stake:
            return 0
        return min(stake, room)

    def adjust_trade_position(self, trade, *args, **kwargs):
        res = super().adjust_trade_position(trade, *args, **kwargs)
        amount, tag = (res if isinstance(res, tuple) else (res, None))
        if amount is not None and amount > 0:
            room = self._exposure_room()
            if room <= 0:
                return None
            if amount > room:
                amount = room
            return (amount, tag) if tag is not None else amount
        return res


class NFI_KF_V9_L12ExpCap100(_ExposureCapMixin, NFI_KF_V9_DeriskL12OffStrong):
    _EXPOSURE_CAP = 1.0


class NFI_KF_V9_L12ExpCap75(_ExposureCapMixin, NFI_KF_V9_DeriskL12OffStrong):
    _EXPOSURE_CAP = 0.75


class NFI_KF_V8_ExpCap75(_ExposureCapMixin, NFI_KF_V8_Clean15):
    _EXPOSURE_CAP = 0.75


# ============================================================================
# Crash-Haeufung: In den MTM-Tiefpunkten (13.04.2024, 03.02.2025, 10.10.2025)
# hat NFI innerhalb von 10-30 min 3-5 Dips gleichzeitig gekauft. Drossel:
# hoechstens N neue Erst-Entries pro 60 min.
# ============================================================================

class _EntryThrottleMixin:
    _THROTTLE_N = 2
    _THROTTLE_MIN = 60

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs):
        from datetime import timedelta
        from freqtrade.persistence import Trade as _T
        since = current_time - timedelta(minutes=self._THROTTLE_MIN)
        recent = [t for t in _T.get_trades_proxy() if t.open_date_utc >= since]
        if len(recent) >= self._THROTTLE_N:
            return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_V8_Throttle2(_EntryThrottleMixin, NFI_KF_V8_Clean15):
    _THROTTLE_N = 2


class NFI_KF_V8_Throttle1(_EntryThrottleMixin, NFI_KF_V8_Clean15):
    _THROTTLE_N = 1


class NFI_KF_V8_RebuyHalf(NFI_KF_V8_Clean15):
    """Rebuy-Modus (61-65) x0,5: 3 der 12 liquidationsnaechsten Positionen
    (JASMY 65 liquidiert, PEPE 61 -91 % Marge, LPT 63) waren Rebuy-Trades."""
    _MODE_SCALES = {"rebuy": 0.5}


class NFI_KF_V8_CapGate(NFI_KF_V8_Clean15):
    """NFI-eigenes Kapitulations-Gate: keine Grind-Nachkaeufe jenseits Derisk-1
    solange MFI_14_4h < 30."""
    bad_trade_controller_capitulation_add_gate_enable = True


class NFI_KF_V8_DeriskHold(NFI_KF_V8_Clean15):
    """NFI-eigene Derisk-Hold-Regel (kein Derisk solange ROC_9_1d > -10)."""
    bad_trade_controller_derisk_hold_enable = True


class NFI_KF_V8_Quick15(NFI_KF_V8_Clean15):
    """Quick-Modus (41-46, G/V 5,2) x1,5."""
    _MODE_SCALES = {"quick": 1.5}


class NFI_KF_V8_GrindSlots3(NFI_KF_V8_Clean15):
    grind_mode_max_slots = 3


class NFI_KF_V8_MaxPos30(NFI_KF_V8_Clean15):
    """Globaler Positionsdeckel inkl. Grinds 30 % statt 35 %."""
    _MAX_POSITION_FRACTION = 0.30


# ============================================================================
# Liquidations-Puffer: gleiches Notional wie v8, aber weniger Hebel und
# entsprechend mehr Marge (freies Kapital ist da, Slots sind selten voll).
# Liquidation dann bei ~-31 % (3x) statt ~-23 % (4x) Kursbewegung.
# NFI rechnet viele Schwellen als Margen-% (Kurs-% x Hebel); damit die
# Logik bei denselben Kursbewegungen ausloest, werden die system_v4-Schwellen
# und die ROI-Tabelle mit Hebel/4 skaliert.
# ============================================================================

class _EqNotionalLevMixin:
    _LEV = 3.0
    _BASE_LEV = 4.0
    _BASE_MAX_POS = 0.35
    _BASE_THIN_CAP = 2500.0
    _mm_on = True

    @property
    def _MM(self):
        return self._BASE_LEV / self._LEV

    @property
    def _MAX_POSITION_FRACTION(self):
        return self._BASE_MAX_POS * (self._MM if self._mm_on else 1.0)

    @property
    def _THIN_PAIR_ABS_CAP_USD(self):
        return self._BASE_THIN_CAP * (self._MM if self._mm_on else 1.0)

    def __init__(self, config):
        super().__init__(config)
        f = self._LEV / self._BASE_LEV
        for name in dir(type(self)):
            if not (name.startswith("system_v4_") and name.endswith("_futures")):
                continue
            if "stake" in name or "distance" in name:
                continue
            if not ("threshold" in name or "derisk" in name):
                continue
            val = getattr(self, name)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                setattr(self, name, val * f)
            elif isinstance(val, list) and all(isinstance(v, (int, float)) for v in val):
                setattr(self, name, [v * f for v in val])
        self.minimal_roi = {k: v * f for k, v in self.minimal_roi.items()}

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        return min(self._LEV, max_leverage)

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        self._mm_on = False
        try:
            stake = super().custom_stake_amount(
                pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
                leverage, entry_tag, side, **kwargs)
        finally:
            self._mm_on = True
        if not stake:
            return stake
        stake *= self._MM
        if max_stake is not None:
            stake = min(stake, max_stake)
        return stake


class NFI_KF_V8_Lev3Eq(_EqNotionalLevMixin, NFI_KF_V8_Clean15):
    _LEV = 3.0


class NFI_KF_V8_Lev35Eq(_EqNotionalLevMixin, NFI_KF_V8_Clean15):
    """Mittelweg: 3,5x, gleiches Notional wie v8 (Liquidation ~-27 % statt ~-23 %)."""
    _LEV = 3.5


# ============================================================================
# Hebel nach Volatilitaet: nur gerade sehr volatile Coins (3-Tages-Vola der
# 5m-Kerzen, PIT) bekommen 3x bei gleichem Notional; ruhige Coins wie v8 (4x).
# NFI-Schwellen (system_v4 Derisk/Grind) und ROI werden PRO TRADE mit
# Hebel/4 skaliert, damit sie bei denselben Kursbewegungen ausloesen.
# ============================================================================

class NFI_KF_V8_VolLev(NFI_KF_V8_Clean15):
    _BASE_LEV = 4.0
    _CALM_LEV = 4.0
    _WILD_LEV = 3.0
    _VOL_THR = 0.06          # Tagesvola (v8-Median der Coins ~0,046)
    _VOL_CANDLES = 864
    use_custom_roi = True
    _scale_names = None
    _cur_lev = 4.0
    _mm_on = True

    def _wild(self, pair):
        try:
            import numpy as np
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            closes = df["close"].iloc[-(self._VOL_CANDLES + 1):]
            if len(closes) < self._VOL_CANDLES // 2:
                return False
            vol = float(np.log(closes).diff().std() * np.sqrt(288))
            return bool(np.isfinite(vol) and vol > self._VOL_THR)
        except Exception:
            return False

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        lev = self._WILD_LEV if self._wild(pair) else self._CALM_LEV
        return min(lev, max_leverage)

    @property
    def _MAX_POSITION_FRACTION(self):
        return 0.35 * (self._BASE_LEV / self._cur_lev if self._mm_on else 1.0)

    @property
    def _THIN_PAIR_ABS_CAP_USD(self):
        return 2500.0 * (self._BASE_LEV / self._cur_lev if self._mm_on else 1.0)

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                             min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        self._mm_on = False
        try:
            stake = super().custom_stake_amount(
                pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
                leverage, entry_tag, side, **kwargs)
        finally:
            self._mm_on = True
        if not stake or not leverage:
            return stake
        stake *= self._BASE_LEV / leverage
        if max_stake is not None:
            stake = min(stake, max_stake)
        return stake

    def _threshold_names(self):
        if self._scale_names is None:
            names = []
            for name in dir(type(self)):
                if not (name.startswith("system_v4_") and name.endswith("_futures")):
                    continue
                if "stake" in name or "distance" in name:
                    continue
                if "threshold" in name or "derisk" in name:
                    val = getattr(type(self), name, None)
                    if isinstance(val, (int, float, list)) and not isinstance(val, bool):
                        names.append(name)
            self._scale_names = names
        return self._scale_names

    def adjust_trade_position(self, trade, *args, **kwargs):
        lev = trade.leverage or self._BASE_LEV
        self._cur_lev = lev
        if lev == self._BASE_LEV:
            return super().adjust_trade_position(trade, *args, **kwargs)
        f = lev / self._BASE_LEV
        saved = {}
        for name in self._threshold_names():
            val = getattr(type(self), name)
            saved[name] = self.__dict__.get(name, None)
            setattr(self, name, [v * f for v in val] if isinstance(val, list) else val * f)
        try:
            return super().adjust_trade_position(trade, *args, **kwargs)
        finally:
            for name, old in saved.items():
                if old is None:
                    self.__dict__.pop(name, None)
                else:
                    self.__dict__[name] = old
            self._cur_lev = self._BASE_LEV

    def custom_roi(self, pair, trade, current_time, trade_duration, entry_tag, side, **kwargs):
        lev = trade.leverage or self._BASE_LEV
        if lev == self._BASE_LEV:
            return None
        keys = [k for k in self.minimal_roi.keys() if k <= trade_duration]
        if not keys:
            return None
        return self.minimal_roi[max(keys)] * lev / self._BASE_LEV


class NFI_KF_V8_CrashLev3(NFI_KF_V8_VolLev):
    """Weniger Hebel (gleiches Notional) nur fuer Erst-Entries waehrend eines
    akuten Crashs (BTC in den letzten 60 min > 3 % gefallen). Diese Trades sind
    die profitabelsten (65 Trades, 1 Verlierer, +58,7k), tragen aber das
    Liquidationsrisiko (PEPE/TAO 10.10.25 -90 % Marge bei 4x)."""
    _WILD_LEV = 3.0
    _BTC_DROP = -0.03

    def _wild(self, pair):
        try:
            df, _ = self.dp.get_analyzed_dataframe("BTC/USD:USD", self.timeframe)
            closes = df["close"].iloc[-13:]
            if len(closes) < 13:
                return False
            return bool(closes.iloc[-1] / closes.iloc[0] - 1 < self._BTC_DROP)
        except Exception:
            return False


class NFI_KF_V8_CrashLev2(NFI_KF_V8_CrashLev3):
    _WILD_LEV = 2.0


# ============================================================================
# Notbremse gegen langsame Verlierer (WLD/JASMY/JUP/ZEC/NEAR: 78-87 %
# Margenverlust vor Erholung oder Endverlust). Ab _CUT_AT Margenverlust der
# offenen Position einmalig 50 % verkaufen: halbiert den Schaden, falls die
# Restposition doch liquidiert wird (isolierte Marge: Liquidationspreis der
# Restposition bleibt gleich, Verlust je Liquidation sinkt).
# ============================================================================

class NFI_KF_V9_CrashLev3Cut70(NFI_KF_V8_CrashLev3):
    _CUT_AT = -0.70
    _CUT_FRACTION = 0.5

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                              min_stake, max_stake, *args, **kwargs):
        try:
            done = trade.get_custom_data("emergency_cut")
        except Exception:
            done = None
        if not done and current_profit is not None and current_profit <= self._CUT_AT:
            sell = (trade.stake_amount or 0.0) * self._CUT_FRACTION
            if min_stake is None or sell > min_stake:
                try:
                    trade.set_custom_data("emergency_cut", True)
                except Exception:
                    pass
                return -sell, "emergency_cut"
        return super().adjust_trade_position(trade, current_time, current_rate, current_profit,
                                             min_stake, max_stake, *args, **kwargs)


class NFI_KF_V9_CrashLev3Cut60(NFI_KF_V9_CrashLev3Cut70):
    _CUT_AT = -0.60


class NFI_KF_V9(NFI_KF_V8_CrashLev3):
    """v9 (live): v8 (NFI_KF_V8_Clean15) + 3x statt 4x Hebel bei gleicher
    Positionsgroesse fuer Erst-Entries waehrend eines akuten Crashs (BTC in
    60 min > 3 % gefallen). Liquidation dieser Positionen erst bei ~-31 % statt
    ~-23 % Kursbewegung; im Crash 10.10.2025 fehlten bei v8 < 1 % bis zur
    Liquidation von PEPE/TAO."""


# ============================================================================
# v10-Kandidaten auf Basis v9 (CrashLev3): weitere Fast-Liquidationen kamen
# fast nur aus Signal 145 (JUP 81 %, NEAR 78 %, LDO 77 %, DOT 76 % Margen-
# verlust) und dem Rebuy-Modus (JASMY 65: 87 %/97 %). Diese Trades zusaetzlich
# mit 3x bei gleichem Notional.
# ============================================================================

def _is_145_only(entry_tag):
    tags = (entry_tag or "").split()
    return bool(tags) and all(c == "145" for c in tags)


class NFI_KF_V10_Weak3(NFI_KF_V9):
    """v9 + 3x (gleiches Notional) auch fuer Signal 145 und Rebuy-Modus."""
    _WEAK_145 = True
    _WEAK_REBUY = True

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        weak = (self._WEAK_145 and _is_145_only(entry_tag)) or \
               (self._WEAK_REBUY and _is_rebuy_mode(self, entry_tag))
        if weak or self._wild(pair):
            return min(self._WILD_LEV, max_leverage)
        return min(self._CALM_LEV, max_leverage)


class NFI_KF_V10_145Lev3(NFI_KF_V10_Weak3):
    _WEAK_REBUY = False


class NFI_KF_V10_RebuyLev3(NFI_KF_V10_Weak3):
    _WEAK_145 = False


class NFI_KF_V10_Weak3Q(NFI_KF_V10_Weak3):
    """Weak3 + Quick-Modus (41-46) mit 3x (WLD 46: 87 % Margenverlust)."""

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        tags = (entry_tag or "").split()
        if tags and all(c in self.long_quick_mode_tags for c in tags):
            return min(self._WILD_LEV, max_leverage)
        return super().leverage(pair, current_time, current_rate, proposed_leverage,
                                max_leverage, entry_tag, side, **kwargs)


class NFI_KF_V10_Weak3Crash2(NFI_KF_V10_Weak3):
    """Weak3 mit empfindlicherer Crash-Schwelle (BTC 60 min < -2 %)."""
    _BTC_DROP = -0.02


class NFI_KF_V10_145Q(NFI_KF_V10_Weak3Q):
    """Crash + Signal 145 + Quick-Modus mit 3x; Rebuy bleibt 4x (Rebuy 3x war
    in H2 bei doppelten Gebuehren instabil: 179 statt 243 %, DD 15,8 %)."""
    _WEAK_REBUY = False


class NFI_KF_V10(NFI_KF_V10_145Q):
    """v10 (live): v9 + 3x Hebel bei gleicher Positionsgroesse auch fuer
    Signal 145 und den Quick-Modus (Rebuy bleibt 4x). Backtest (8 Fenster):
    nur noch 1 Position ueber 80 % Margenverlust (v8: 5, v9: 4)."""


class NFI_KF_V11_Crash4(NFI_KF_V10):
    """v10 mit Crash-Schwelle BTC 60 min < -4 % statt -3 %."""
    _BTC_DROP = -0.04


class NFI_KF_V11_L1OffStrong(NFI_KF_V10, NFI_KF_V9_DeriskL1OffStrong):
    """v10 + Derisk Stufe 1 aus bei starken Signalen (v9-Kandidat L1OffStrong:
    W3 1537 statt 1440, H1 953 statt 884, MC-DD besser)."""


class NFI_KF_V11(NFI_KF_V11_L1OffStrong):
    """v11 (live): v10 + Derisk Stufe 1 aus bei starken Signalen (141-144,
    Normal, Scalp, Rapid). Backtest vs v10: +4-10 % Gewinn in 5 von 8
    Fenstern, Monte-Carlo-DD (95 %) 22,4 statt 25,6 %."""


class NFI_KF_V12_L12OffStrong(NFI_KF_V11):
    """v11 + auch Derisk Stufe 2 aus bei starken Signalen (Stufe 3 bleibt)."""

    @property
    def system_v4_derisk_level_2_enable(self):
        return not _is_strong_signal(self, self._cur_enter_tag)


class NFI_KF_V12_Rebuy075(NFI_KF_V11):
    """v11 + Rebuy-Modus x0,75 (JASMY 65 bleibt bei 87 % Margenverlust)."""
    _MODE_SCALES = {"rebuy": 0.75}


class NFI_KF_V12(NFI_KF_V12_L12OffStrong):
    """v12 (live): v11 + Derisk Stufe 2 aus bei starken Signalen (Stufe 3
    bleibt). Backtest vs v11: W3 1610 statt 1391 %, H1 937 statt 895 %,
    Monte-Carlo-DD (95 %) 18,5 statt 22,6 %."""



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


# ============================================================================
# Phase v16: Signal-Auswertung v13 (471 Trades, 7 Fenster): Signal 145 = 20 % der
# Trades, 9 % des Gewinns, Haelfte aller Verlierer; Rebuy (61-68) = 10 % der
# Trades, 1 % des Gewinns, 3 der schlimmsten Trades (JASMY -97, LPT -64, ICP -48).
# Test: diese Signale nicht mehr handeln (Nachkaeufe laufender Trades bleiben).
# ============================================================================

class _BlockSignalsMixin:
    _BLOCK_TAGS = frozenset()

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs):
        tags = (entry_tag or "").split()
        if tags and all(t in self._BLOCK_TAGS for t in tags):
            from freqtrade.persistence import Trade as _T
            if not _T.get_trades_proxy(pair=pair, is_open=True):   # nur Erst-Entries
                return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_V16_No145(_BlockSignalsMixin, NFI_KF_V13):
    _BLOCK_TAGS = frozenset({"145"})


class NFI_KF_V16_NoRebuy(_BlockSignalsMixin, NFI_KF_V13):
    _BLOCK_TAGS = frozenset({"61", "62", "63", "64", "65", "68"})


class NFI_KF_V16_NoBoth(_BlockSignalsMixin, NFI_KF_V13):
    _BLOCK_TAGS = frozenset({"145", "61", "62", "63", "64", "65", "68"})


class _BlockCoinsMixin:
    _BLOCK_COINS = frozenset()

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs):
        if pair.split("/")[0] in self._BLOCK_COINS:
            from freqtrade.persistence import Trade as _T
            if not _T.get_trades_proxy(pair=pair, is_open=True):   # nur Erst-Entries
                return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_V17_NoWeak7(_BlockCoinsMixin, NFI_KF_V13):
    _BLOCK_COINS = frozenset({"JASMY", "JUP", "LDO", "OP", "ENS", "LPT", "ICP"})


# ============================================================================
# Drawdown-Kandidaten (v18) auf Basis v13: Drawdown inkl. offener Positionen
# kommt aus Crash-Phasen. Hier: kleinere/keine Erst-Entries bei Crash.
# ============================================================================

class _CrashStakeMixin:
    _CRASH_STAKE = 0.5     # Faktor auf Marge/Positionsgroesse bei Erst-Entries im Crash (0 = nicht kaufen)
    _SLOW_DROP = None      # optional: BTC-Rueckgang ueber 24h (z. B. -0.05) wie Crash behandeln

    def _slow(self):
        if self._SLOW_DROP is None:
            return False
        try:
            df, _ = self.dp.get_analyzed_dataframe("BTC/USD:USD", self.timeframe)
            closes = df["close"].iloc[-289:]
            return len(closes) >= 289 and bool(closes.iloc[-1] / closes.iloc[0] - 1 < self._SLOW_DROP)
        except Exception:
            return False

    def _stress(self, pair):
        return self._wild(pair) or self._slow()

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        if stake and self._CRASH_STAKE < 1.0 and self._stress(pair):
            if self._CRASH_STAKE <= 0:
                return 0.0
            stake *= self._CRASH_STAKE
            if min_stake is not None and stake < min_stake:
                return 0.0
        return stake


class NFI_KF_V18_CrashHalf(_CrashStakeMixin, NFI_KF_V13):
    _CRASH_STAKE = 0.5


class NFI_KF_V18_CrashStop(_CrashStakeMixin, NFI_KF_V13):
    _CRASH_STAKE = 0.0


class NFI_KF_V18_Slow5Half(_CrashStakeMixin, NFI_KF_V13):
    _CRASH_STAKE = 0.5
    _SLOW_DROP = -0.05


# ============================================================================
# v19-Kandidat: Positionsgroesse nach Kontostand (Equity-Kurve). Liegt das
# Konto inkl. offener Positionen mehr als _EQ_DD unter seinem bisherigen
# Hoechststand, werden neue Erst-Entries nur mit _EQ_STAKE der Marge eroeffnet.
# Der Hoechststand lebt im Prozess (nach Neustart startet er neu).
# ============================================================================

class _EquityDDStakeMixin:
    _EQ_DD = 0.15
    _EQ_STAKE = 0.5
    _eq_peak = 0.0

    def _equity_mtm(self, current_time):
        from freqtrade.persistence import Trade as _T
        eq = self.wallets.get_total_stake_amount()
        for t in _T.get_trades_proxy(is_open=True):
            try:
                df, _ = self.dp.get_analyzed_dataframe(t.pair, self.timeframe)
                eq += t.calculate_profit(float(df["close"].iloc[-1])).profit_abs
            except Exception:
                pass
        return eq

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        try:
            eq = self._equity_mtm(current_time)
            if eq > self._eq_peak:
                self._eq_peak = eq
            if stake and self._eq_peak > 0 and eq < self._eq_peak * (1 - self._EQ_DD):
                stake *= self._EQ_STAKE
                if min_stake is not None and stake < min_stake:
                    return 0.0
        except Exception:
            pass
        return stake


class NFI_KF_V19_EqDD15(_EquityDDStakeMixin, NFI_KF_V13):
    _EQ_DD = 0.15
    _EQ_STAKE = 0.5


class NFI_KF_V19_EqDD08(_EquityDDStakeMixin, NFI_KF_V13):
    _EQ_DD = 0.08
    _EQ_STAKE = 0.5


# ============================================================================
# v20-Kandidat: Crash-Trim. Faellt BTC akut (>3 % in 60 min), wird jede offene
# Position, die schon mehr als _TRIM_LOSS Margenverlust hat, einmalig um
# _TRIM_FRACTION verkleinert (weniger Exposure beim Crash).
# ============================================================================

class _CrashTrimMixin:
    _TRIM_LOSS = -0.10
    _TRIM_FRACTION = 0.3

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                              min_stake, max_stake, *args, **kwargs):
        try:
            done = trade.get_custom_data("crash_trim")
        except Exception:
            done = None
        if (not done and current_profit is not None and current_profit <= self._TRIM_LOSS
                and self._wild(trade.pair)):
            sell = (trade.stake_amount or 0.0) * self._TRIM_FRACTION
            if min_stake is None or sell > min_stake:
                try:
                    trade.set_custom_data("crash_trim", True)
                except Exception:
                    pass
                return -sell, "crash_trim"
        return super().adjust_trade_position(trade, current_time, current_rate, current_profit,
                                             min_stake, max_stake, *args, **kwargs)


class NFI_KF_V20_Trim30(_CrashTrimMixin, NFI_KF_V13):
    _TRIM_FRACTION = 0.3


class NFI_KF_V20_Trim50(_CrashTrimMixin, NFI_KF_V13):
    _TRIM_FRACTION = 0.5


class NFI_KF_V21_145Lev2(NFI_KF_V13):
    """v13, aber Erst-Entries mit Signal 145 mit 2x statt 3x Hebel (gleiches Notional,
    Marge x2 statt x4/3; Schwellen/ROI pro Trade mit Hebel/4 skaliert)."""
    _LEV_145 = 2.0

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        if _is_145_only(entry_tag):
            return min(self._LEV_145, max_leverage)
        return super().leverage(pair, current_time, current_rate, proposed_leverage,
                                max_leverage, entry_tag, side, **kwargs)


class NFI_KF_V22_RebuyLev2(NFI_KF_V13):
    """v13, aber Erst-Entries im Rebuy-Modus (61-68) mit 2x statt 4x Hebel (gleiches Notional)."""
    _LEV_REBUY = 2.0

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage,
                 entry_tag, side, **kwargs):
        if _is_rebuy_mode(self, entry_tag):
            return min(self._LEV_REBUY, max_leverage)
        return super().leverage(pair, current_time, current_rate, proposed_leverage,
                                max_leverage, entry_tag, side, **kwargs)


class NFI_KF_V23_Grind3(NFI_KF_V13):
    """v13, aber Erst-Entries im Grind-Modus (Tag 120) mit dem 3-fachen Einsatz
    (ca. 12 % statt 4 % des Kontos als Marge)."""
    _GRIND_SCALE = 3.0

    def _scale_for(self, entry_tag):
        tags = (entry_tag or "").split()
        if tags and all(c in self.long_grind_mode_tags for c in tags):
            return self._GRIND_SCALE
        return super()._scale_for(entry_tag)


# ============================================================================
# v24-Kandidaten (Drawdown): (a) alle Erst-Entries kleiner (Effizienzlinie:
# Drawdown gegen Gewinn), (b) LossGate: keine neuen Erst-Entries, solange
# bereits _GATE_N offene Positionen mehr als _GATE_LOSS Margenverlust haben.
# ============================================================================

class _GlobalScaleMixin:
    _GLOBAL_SCALE = 0.75

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = super().custom_stake_amount(
            pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
            leverage, entry_tag, side, **kwargs)
        if not stake:
            return stake
        stake *= self._GLOBAL_SCALE
        if min_stake is not None and stake < min_stake:
            return min_stake
        return stake


class NFI_KF_V24_Scale75(_GlobalScaleMixin, NFI_KF_V13):
    _GLOBAL_SCALE = 0.75


class NFI_KF_V24_Scale50(_GlobalScaleMixin, NFI_KF_V13):
    _GLOBAL_SCALE = 0.50


class _LossGateMixin:
    _GATE_N = 2
    _GATE_LOSS = -0.15

    def _n_underwater(self):
        from freqtrade.persistence import Trade as _T
        n = 0
        for t in _T.get_trades_proxy(is_open=True):
            try:
                df, _ = self.dp.get_analyzed_dataframe(t.pair, self.timeframe)
                if t.calc_profit_ratio(float(df["close"].iloc[-1])) <= self._GATE_LOSS:
                    n += 1
            except Exception:
                pass
        return n

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs):
        from freqtrade.persistence import Trade as _T
        if not _T.get_trades_proxy(pair=pair, is_open=True) and self._n_underwater() >= self._GATE_N:
            return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_V24_LossGate2(_LossGateMixin, NFI_KF_V13):
    _GATE_N = 2
    _GATE_LOSS = -0.15


# ============================================================================
# v25: mehr Signale. 19 Coins und mehrere Modi liefern nie Trades; Slots sind
# meist frei (Trades dauern median 3 h). Experimentelle NFI-Signale einschalten.
# ============================================================================

class NFI_KF_V25_Exp7to11(NFI_KF_V13):
    long_entry_signal_params = {
        **NFI_KF_V13.long_entry_signal_params,
        **{f"long_entry_condition_{i}_enable": True for i in range(7, 12)},
    }


class NFI_KF_V25_Rapid105(NFI_KF_V13):
    long_entry_signal_params = {
        **NFI_KF_V13.long_entry_signal_params,
        "long_entry_condition_105_enable": True,
    }


class NFI_KF_V25_Btc121(NFI_KF_V13):
    long_entry_signal_params = {
        **NFI_KF_V13.long_entry_signal_params,
        "long_entry_condition_121_enable": True,
    }


# ============================================================================
# v26: Crash-Staffel. Befund (tools/troughs): An allen vier Drawdown-Tiefpunkten
# wurden ALLE Slots innerhalb von 20-30 min im fallenden Messer gefuellt (je
# 20-48 % Marge), die Positionen enden meist im Plus, ziehen das Konto aber
# auf -41 bis -51 %. Statt Crash-Kaeufe zu verbieten: nach Tiefe staffeln.
# Erlaubte Zahl frischer Positionen (eroeffnet in den letzten _COHORT_H Stunden)
# waechst mit dem BTC-Abstand zum 24h-Hoch: 1 + (Abstand - _LADDER_START) / _LADDER_STEP.
# ============================================================================

class _CrashLadderMixin:
    _LADDER_START = 0.03
    _LADDER_STEP = 0.02
    _COHORT_H = 2.0

    def _btc_dd24(self):
        try:
            df, _ = self.dp.get_analyzed_dataframe("BTC/USD:USD", self.timeframe)
            c = df["close"].iloc[-288:]
            if len(c) < 24:
                return 0.0
            return float(1 - c.iloc[-1] / c.max())
        except Exception:
            return 0.0

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs):
        from datetime import timedelta
        from freqtrade.persistence import Trade as _T
        if not _T.get_trades_proxy(pair=pair, is_open=True):
            dd = self._btc_dd24()
            if dd >= self._LADDER_START:
                allowed = 1 + int((dd - self._LADDER_START) / self._LADDER_STEP)
                since = current_time - timedelta(hours=self._COHORT_H)
                fresh = sum(1 for t in _T.get_trades_proxy(is_open=True)
                            if t.open_date_utc >= since)
                if fresh >= allowed:
                    return False
        return super().confirm_trade_entry(
            pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs)


class NFI_KF_V26_Ladder2(_CrashLadderMixin, NFI_KF_V13):
    _LADDER_STEP = 0.02


class NFI_KF_V26_Ladder15(_CrashLadderMixin, NFI_KF_V13):
    _LADDER_STEP = 0.015


class NFI_KF_V26_Ladder3(_CrashLadderMixin, NFI_KF_V13):
    _LADDER_STEP = 0.03


# ============================================================================
# v27: Crash-Limit tiefer. Im akuten Crash (BTC > 3 % in 60 min) Erst-Entries
# als Limit _CRASH_DIP unter dem vorgeschlagenen Kurs: faellt das Messer weiter
# (Tiefpunkte lagen 10-30 min nach den Kaeufen), wird billiger gefuellt; dreht der
# Markt sofort, entfaellt der Kauf (Order-Timeout 10 min). Normale Phasen unveraendert.
# ============================================================================

class _CrashDipMixin:
    _CRASH_DIP = 0.015

    def custom_entry_price(self, pair, trade, current_time, proposed_rate, entry_tag, side, **kwargs):
        rate = super().custom_entry_price(pair, trade, current_time, proposed_rate, entry_tag, side, **kwargs)
        if trade is None and side == "long" and rate and self._wild(pair):
            return rate * (1.0 - self._CRASH_DIP)
        return rate


class NFI_KF_V27_CrashDip15(_CrashDipMixin, NFI_KF_V13):
    _CRASH_DIP = 0.015


class NFI_KF_V27_CrashDip30(_CrashDipMixin, NFI_KF_V13):
    _CRASH_DIP = 0.03


class NFI_KF_V27_CrashDip50(_CrashDipMixin, NFI_KF_V13):
    _CRASH_DIP = 0.05


# ============================================================================
# v28: Einstieg bestaetigen. 36 % der Trades liegen nach der ersten Kerze im
# Minus, der Kurs faellt nach dem Einstieg median noch 1,8 % (25 %: >4,4 %).
# Statt sofort zu kaufen: Signal eine Kerze aufschieben und nur kaufen, wenn
# diese Kerze hoeher schliesst als die Signal-Kerze (das Messer hat gedreht).
# ============================================================================

class _ConfirmEntryMixin:
    _CONFIRM_BARS = 1

    def populate_entry_trend(self, dataframe, metadata):
        df = super().populate_entry_trend(dataframe, metadata)
        if "enter_long" not in df.columns:
            return df
        n = self._CONFIRM_BARS
        sig = df["enter_long"].shift(n).fillna(0).astype(bool)
        up = df["close"] > df["close"].shift(n)
        for k in range(1, n):
            up &= df["close"].shift(k) > df["close"].shift(n)
        tag = df["enter_tag"].shift(n) if "enter_tag" in df.columns else None
        df["enter_long"] = (sig & up).astype(int)
        if tag is not None:
            df["enter_tag"] = tag.where(df["enter_long"] == 1, None)
        return df


class NFI_KF_V28_Confirm1(_ConfirmEntryMixin, NFI_KF_V13):
    _CONFIRM_BARS = 1


class NFI_KF_V28_Confirm2(_ConfirmEntryMixin, NFI_KF_V13):
    _CONFIRM_BARS = 2


# ============================================================================
# v30: Liquidationspreis selbst berechnen. Kraken liefert freqtrade keinen
# Liquidationspreis (live None) und der Backtest setzt ihn nie -> NFIs
# Liquidations-Logik (grind_4-Rettung u. a.) ist tot und der Backtest kennt keine
# Liquidation (nur Stop -99 % Marge). Hier aus Krakens Margin-Stufen
# (dry_run_liquidation_price) nach jeder Pruefung neu gesetzt: wirkt live UND im
# Backtest (freqtrade simuliert dann Liquidationen). Live zusaetzlich Telegram-
# Warnung, wenn der Kurs naeher als _LIQ_WARN an die Liquidation kommt.
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


class NFI_KF_V30_Liq(_LiqAwareMixin, NFI_KF_V23_Grind3):
    """v23 + selbst berechneter Liquidationspreis (+ Live-Warnung)."""


class NFI_KF_V29_Lev3Eq(_LiqAwareMixin, NFI_KF_V23_Grind3):
    """Alle Trades 3x bei gleichem Positionswert (Marge x4/3); Schwellen wie bisher
    in Kursbewegung (skaliert mit Hebel/4)."""
    _CALM_LEV = 3.0


class NFI_KF_V29_Lev3Nat(_LiqAwareMixin, NFI_KF_V23_Grind3):
    """Alle Trades 3x wie von NFI ausgelegt: NFI-Schwellen und ROI unskaliert
    (Basis 3x), Marge-Anteil wie bisher (Positionswert -25 %)."""
    _BASE_LEV = 3.0
    _CALM_LEV = 3.0


class NFI_KF_DebugLiq(NFI_KF_V13):
    """Nur zur Diagnose: protokolliert, ob freqtrade im Backtest einen Liquidationspreis setzt."""
    _seen_liq = None

    def adjust_trade_position(self, trade, current_time, current_rate, *args, **kwargs):
        if self._seen_liq is None:
            self._seen_liq = set()
        if trade.id not in self._seen_liq:
            self._seen_liq.add(trade.id)
            print(f"DEBUGLIQ {trade.pair} lev={trade.leverage} open={trade.open_rate} liq={trade.liquidation_price}", flush=True)
        return super().adjust_trade_position(trade, current_time, current_rate, *args, **kwargs)



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


class NFI_KF_V23L(_LiqAwareMixin, NFI_KF_V23F):
    """Live-Kandidat: v23F + selbst berechneter Liquidationspreis (wie im Backtest) + Telegram-Warnung."""
