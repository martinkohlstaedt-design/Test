# Trading Bot

A crypto trading bot built on the same technical-indicator logic as the
`crypto-dashboard` in this repo (RSI, MACD, Bollinger Bands, Stochastic RSI,
On-Balance Volume, SMA50/200 golden/death cross), now automated: it can
backtest a strategy, search for better parameters, and run continuously
against live prices — in **paper trading** (simulated money) by default.

## ⚠️ Read this before running anything

- **This is not financial advice.** Nothing here predicts the market
  reliably. Backtests overfit easily; past performance on historical data is
  not a promise of future results.
- **Start in paper mode and stay there** until you have backtested,
  walk-forward-validated, and paper-traded a strategy for a meaningful
  period and understand exactly when and why it trades.
- **Never commit API keys.** `config.yaml` and `.env` are gitignored on
  purpose — this repository is public. Only `config.example.yaml` and
  `.env.example` (with blank secrets) are meant to be committed.
- **Live trading risks real money**, including total loss of whatever
  balance the API key can access. `LiveBroker` refuses to start unless you
  explicitly set `I_UNDERSTAND_LIVE_TRADING_RISK=true` — that switch exists
  so going live is a decision you make on purpose, not a side effect of a
  config typo.
- Consider an exchange **testnet** (e.g. Binance Futures Testnet) or a
  brand-new API key with a **small, capped balance and no withdrawal
  permission** as your first real-money-adjacent test, long before using a
  main account.

## Setup

```bash
cd trading-bot
pip install -r requirements.txt
cp config.example.yaml config.yaml
cp .env.example .env        # only needed for live mode later
```

## 1. Backtest a strategy

```bash
python run_backtest.py --exchange binance --symbol BTC/USDT --timeframe 1d --days 730
```

Prints total return, max drawdown, Sharpe ratio, win rate, and number of
trades over the fetched history, using `signal_engine.DEFAULT_PARAMS`. Pass
`--params best_params.json` to use parameters from a previous optimization
run instead.

## 2. Search for better parameters (with a held-out test split)

```bash
python run_optimization.py --exchange binance --symbol BTC/USDT --timeframe 1d --days 1095
```

This grid-searches `optimizer.DEFAULT_PARAM_GRID` on the first `--train-frac`
(default 70%) of the fetched history, then reports how the winning
parameters actually performed on the remaining, never-optimized-against
portion. **Trust the "test metrics" section, not the "train metrics"
section** — a strategy that only looks good on its training window is
overfit, not profitable. The winning parameters are saved to
`best_params.json`; edit `config.yaml`'s `signal_params` (or pass
`--params best_params.json` to `run_backtest.py`) to use them.

Re-run this periodically as new data comes in (true walk-forward
re-optimization) rather than trusting one search forever — markets change.

## 3. Run the paper-trading bot

```bash
python bot.py --config config.yaml
```

Polls each configured symbol every `poll_interval_seconds`, evaluates the
signal engine, and simulates buy/sell orders through `PaperBroker` — no real
money moves. Trades are logged to `logs/paper_trades.jsonl` and everything
the bot does is logged to `logs/bot.log` and the console. Stop with Ctrl+C.

## 4. Going live (only once you're confident)

1. In `config.yaml`, set `mode: live`.
2. In `.env`, fill in `<EXCHANGE>_API_KEY` / `<EXCHANGE>_API_SECRET` for an
   API key with **trading permission only — never enable withdrawals**.
3. Set `I_UNDERSTAND_LIVE_TRADING_RISK=true` in `.env`.
4. Start with a small `initial_balance`-equivalent and conservative
   `risk.max_position_pct` — the bot will size real orders off your real
   exchange balance.

`LiveBroker` in `broker.py` implements the same interface as `PaperBroker`,
so no strategy code changes between modes — only the config.

## Project layout

| File | Purpose |
|---|---|
| `indicators.py` | Vectorized RSI/MACD/Bollinger/Stochastic RSI/OBV/crossover (pandas) |
| `signal_engine.py` | Combines indicators into one buy/sell/hold score; all thresholds are tunable params |
| `data_feed.py` | ccxt-based OHLCV fetching (any exchange ccxt supports) |
| `broker.py` | `PaperBroker` (simulated fills) and `LiveBroker` (real ccxt orders) |
| `risk_manager.py` | Position sizing, stop-loss/take-profit, daily-loss kill switch |
| `backtester.py` | Runs engine + risk manager over historical data, computes metrics |
| `optimizer.py` | Grid search + train/test walk-forward split |
| `bot.py` | Live polling loop wiring everything together |
| `run_backtest.py`, `run_optimization.py` | CLI entry points |

## Known limitations

- The signal engine is the same rule-based composite scoring approach as
  the dashboard — not a machine-learned model. "Optimizing" it means
  grid-searching its thresholds/weights, not discovering new signals.
- `risk_manager` assumes one open position per symbol at a time (no
  pyramiding/averaging-in).
- `LiveBroker.get_position` approximates a spot position from the base
  asset's free balance — fine for a bot that solely manages that balance,
  wrong if you also hold/trade the asset manually elsewhere.
- Backtest fills assume your order executes at the candle's close price
  plus configured slippage — real fills can differ, especially in fast
  moves or on thin order books.
