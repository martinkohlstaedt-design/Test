"""Main trading loop. Reads config.yaml, polls the exchange for fresh
candles, evaluates the signal engine, and routes orders through whichever
broker the config selects (paper by default; live only with the explicit
safety opt-in described in README.md).

Run with:  python bot.py [--config config.yaml]
Stop with: Ctrl+C (finishes the current iteration, then exits cleanly)
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

from broker import LiveBroker, PaperBroker
from data_feed import fetch_ohlcv
from risk_manager import RiskManager
from signal_engine import DEFAULT_PARAMS, SignalEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/bot.log")],
)
log = logging.getLogger("bot")

_shutdown_requested = False


def _handle_shutdown(signum, frame):
    global _shutdown_requested
    log.info("Shutdown requested, finishing current iteration...")
    _shutdown_requested = True


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def build_broker(config: dict):
    mode = config.get("mode", "paper")
    if mode == "paper":
        p = config.get("paper", {})
        return PaperBroker(
            initial_balance=p.get("initial_balance", 10_000),
            fee_pct=p.get("fee_pct", 0.001),
            slippage_pct=p.get("slippage_pct", 0.0005),
        )
    if mode == "live":
        exchange_id = config["exchange"]
        key_env = f"{exchange_id.upper()}_API_KEY"
        secret_env = f"{exchange_id.upper()}_API_SECRET"
        api_key, api_secret = os.environ.get(key_env), os.environ.get(secret_env)
        if not api_key or not api_secret:
            raise RuntimeError(
                f"mode: live requires {key_env} and {secret_env} to be set (see .env.example)."
            )
        return LiveBroker(exchange_id, api_key, api_secret)
    raise ValueError(f"Unknown mode '{mode}', expected 'paper' or 'live'")


def run(config_path: str) -> None:
    load_dotenv()
    config = load_config(config_path)

    exchange_id = config["exchange"]
    symbols = config["symbols"]
    timeframe = config.get("timeframe", "1h")
    poll_interval = config.get("poll_interval_seconds", 300)

    risk_cfg = config.get("risk", {})
    risk_manager = RiskManager(
        max_position_pct=risk_cfg.get("max_position_pct", 0.2),
        stop_loss_pct=risk_cfg.get("stop_loss_pct", 0.05),
        take_profit_pct=risk_cfg.get("take_profit_pct", 0.10),
        max_daily_loss_pct=risk_cfg.get("max_daily_loss_pct", 0.05),
    )
    signal_params = {**DEFAULT_PARAMS, **config.get("signal_params", {})}
    engine = SignalEngine(signal_params)
    broker = build_broker(config)

    log.info("Starting bot: mode=%s exchange=%s symbols=%s timeframe=%s",
             config.get("mode", "paper"), exchange_id, symbols, timeframe)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    start_of_day_equity: dict[str, float] = {}
    halted_today: dict[str, bool] = {s: False for s in symbols}
    last_day: dict[str, object] = {}

    while not _shutdown_requested:
        for symbol in symbols:
            try:
                process_symbol(symbol, exchange_id, timeframe, engine, risk_manager, broker,
                               start_of_day_equity, halted_today, last_day)
            except Exception:
                log.exception("Error processing %s, continuing with next symbol", symbol)

        if _shutdown_requested:
            break
        time.sleep(poll_interval)

    log.info("Bot stopped.")


def process_symbol(symbol, exchange_id, timeframe, engine, risk_manager, broker,
                    start_of_day_equity, halted_today, last_day) -> None:
    df = fetch_ohlcv(exchange_id, symbol, timeframe=timeframe, limit=500)
    if len(df) < 200:
        log.warning("%s: only %d candles available, need >=200 for SMA200 — skipping", symbol, len(df))
        return

    prepared = engine.prepare(df)
    price = prepared["close"].iloc[-1]
    today = prepared.index[-1].floor("D")

    if last_day.get(symbol) != today:
        last_day[symbol] = today
        start_of_day_equity[symbol] = _current_equity(broker, symbol, price)
        halted_today[symbol] = False

    pos = broker.get_position(symbol)

    if pos.is_open:
        exit_reason = risk_manager.check_exit(pos.entry_price, price)
        if exit_reason:
            trade = broker.place_order(symbol, "sell", pos.amount, price, reason=exit_reason)
            log.info("%s: %s at %.6f (%s)", symbol, trade.side.upper(), trade.price, exit_reason)
            pos = broker.get_position(symbol)

    equity = _current_equity(broker, symbol, price)
    if not halted_today[symbol] and risk_manager.kill_switch_triggered(start_of_day_equity[symbol], equity):
        halted_today[symbol] = True
        log.warning("%s: daily loss limit hit, halting new entries until tomorrow", symbol)

    signal_result = engine.evaluate(prepared)
    log.info("%s: price=%.6f score=%.1f label=%s reasons=%s",
             symbol, price, signal_result.score, signal_result.label, signal_result.reasons)

    if halted_today[symbol]:
        return

    if not pos.is_open and signal_result.label in ("BUY", "STRONG_BUY"):
        balance = broker.get_balance() if isinstance(broker, PaperBroker) else broker.get_balance("USDT")
        amount = risk_manager.position_size(balance, price)
        if amount > 0:
            trade = broker.place_order(symbol, "buy", amount, price, reason=signal_result.label)
            log.info("%s: BUY %.6f @ %.6f (%s)", symbol, trade.amount, trade.price, signal_result.label)
    elif pos.is_open and signal_result.label in ("SELL", "STRONG_SELL"):
        trade = broker.place_order(symbol, "sell", pos.amount, price, reason=signal_result.label)
        log.info("%s: SELL %.6f @ %.6f (%s)", symbol, trade.amount, trade.price, signal_result.label)


def _current_equity(broker, symbol: str, price: float) -> float:
    if isinstance(broker, PaperBroker):
        return broker.equity({symbol: price})
    pos = broker.get_position(symbol)
    return broker.get_balance("USDT") + pos.amount * price


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    if not Path(args.config).exists():
        print(f"'{args.config}' not found. Copy config.example.yaml to {args.config} first.", file=sys.stderr)
        sys.exit(1)
    run(args.config)
