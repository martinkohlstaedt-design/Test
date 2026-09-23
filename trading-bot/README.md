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

## 2. Search for better parameters (rolling walk-forward)

```bash
python run_optimization.py --exchange binance --symbol BTC/USDT --timeframe 1d --days 1095 --folds 4
```

This grid-searches `optimizer.DEFAULT_PARAM_GRID` — including
`require_uptrend_filter` (refuse to buy below the long-term trend MA — the
standard fix for oscillator strategies "catching falling knives") and the
risk manager's `stop_loss_pct`/`take_profit_pct`, not just the signal
thresholds — across **several rolling train/test folds**, not just one
split. Each fold optimizes only on its training window and is scored only
on its own held-out test window, so you get an out-of-sample return per
fold instead of one number that might just be a lucky split.

**Read the per-fold table, not just the best fold.** A parameter set that
was profitable in 1 of 4 folds and lost money in the other 3 has no real
edge — the summary's `profitable_folds` count and `worst_test_return_pct`
tell you this directly; the CLI prints a warning when most folds lost
money. Only the most recent fold's winning params are saved to
`best_params.json` (closest to current conditions); edit `config.yaml`'s
`signal_params` (or pass `--params best_params.json` to `run_backtest.py`,
which also picks up any risk-manager fields in that file) to use them.

Re-run this periodically as new data comes in rather than trusting one
search forever — markets change, and no search here "solves" profitability;
it only ever tells you what would have worked on the past.

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

## 5. Funding-rate arbitrage (market-neutral, separate from the signal bot)

A different way to earn from crypto markets that doesn't depend on predicting
price direction: **buy an asset spot and short the same amount as a
perpetual future.** Price moves cancel out; what's left is the *funding rate*
that perpetual longs pay shorts (usually every 8h, hourly on some exchanges)
whenever the perp trades above spot — which is most of the time in bull
markets. When funding turns negative, the short *pays* instead.

These tools only **read public data** — no API key, no orders, nothing live.

### See what funding pays right now

```bash
python run_funding_monitor.py --exchange binance --symbols BTC/USDT ETH/USDT SOL/USDT
```

Prints the current, 7-day and 30-day average funding per coin as an
annualized percentage (APR), plus how often it was positive. Remember that
with 1x leverage only about half your capital sits in the short, so your
return on total capital is roughly **half** these numbers, minus fees.

### Backtest it on real history

```bash
python run_funding_backtest.py --exchange binance --symbol BTC/USDT --days 1095
python run_funding_backtest.py --symbol ETH/USDT --leverage 2 --entry-apr 8 --exit-apr 2
```

Simulates the position on historical funding payments and hourly prices,
with fees on every leg, and compares two scenarios:

- **with entry/exit rule** — only hold the position while the trailing
  `--lookback-days` average funding APR is above `--entry-apr`, exit below
  `--exit-apr` (decisions only use funding already paid, no look-ahead);
- **always in** — hold the whole time, as a baseline.

It reports return, annualized return, max drawdown, time in position, total
funding received vs. fees paid, and how often the position was rebalanced
or liquidated. Entries/exits/rebalances are logged to
`logs/funding_backtest_events.jsonl`.

What the model does (see `funding_backtest.py` for details):

- **Leverage** (`--leverage`) = short notional / futures margin. 1x puts half
  the capital in spot and half as margin; higher leverage earns more funding
  per euro but gets liquidated by smaller rallies.
- **Liquidation**: checked against every candle's high. If the short's loss
  eats its margin, the margin is gone and the unhedged spot is sold at that
  candle's close.
- **Rebalancing**: when the futures margin has fallen to half its target,
  some spot is sold and the short reduced to restore the split — this is
  what keeps a real position alive through a rally (costs fees each time).

Not modeled: the basis (price gap) between spot and perp, interest on idle
cash, the exchange going bust or freezing withdrawals (the biggest real risk
— both legs usually sit on the same exchange), and taxes.

**Exchanges:** any ccxt exchange with perpetuals works (`--exchange okx`,
`krakenfutures`, `hyperliquid`, ...). How far back the backtest can go
depends on how much funding history the exchange serves: Binance goes back
years, Kraken Futures about a year, OKX/Bitget/KuCoin only ~3 months. Also
check which exchanges actually let you trade perpetual futures where you
live — e.g. Binance restricts derivatives for retail customers in several EU
countries, while Kraken Futures is offered under EU regulation.

**Reality check:** funding income is real but modest. In a sample run
over Sept 2025 – Sept 2026 on Kraken Futures, BTC and ETH returned roughly
1% for the year (always-in, 1x) — the entry/exit rule did *not* help there,
since fees from frequent re-entries ate the difference. Funding pays well
mostly during euphoric bull phases. Run the backtest yourself on the coins
and period you care about before drawing conclusions.

## Project layout

| File | Purpose |
|---|---|
| `indicators.py` | Vectorized RSI/MACD/Bollinger/Stochastic RSI/OBV/crossover (pandas) |
| `signal_engine.py` | Combines indicators into one buy/sell/hold score; all thresholds are tunable params |
| `data_feed.py` | ccxt-based OHLCV fetching (any exchange ccxt supports) |
| `broker.py` | `PaperBroker` (simulated fills) and `LiveBroker` (real ccxt orders) |
| `risk_manager.py` | Position sizing, stop-loss/take-profit, daily-loss kill switch |
| `backtester.py` | Runs engine + risk manager over historical data, computes metrics |
| `optimizer.py` | Grid search (signal + risk params) with rolling walk-forward validation |
| `bot.py` | Live polling loop wiring everything together |
| `run_backtest.py`, `run_optimization.py` | CLI entry points |
| `funding_data.py` | Funding-rate + perp price history via ccxt, APR conversion |
| `funding_backtest.py` | Cash-and-carry (long spot + short perp) simulation with fees, rebalancing, liquidation |
| `run_funding_monitor.py`, `run_funding_backtest.py` | CLI entry points for funding-rate arbitrage |

## Trading other assets, not just Bitcoin

`config.yaml`'s `symbols` is a list — add as many trading pairs as you like
(e.g. `ETH/USDT`, `SOL/USDT`), and `bot.py` polls and trades each one
independently with the same strategy. `data_feed.py` and `broker.py` are
built on **ccxt**, so any of the ~100 crypto exchanges it supports (Binance,
Kraken, Coinbase, ...) work by changing `exchange:` — no code changes.

That said, ccxt only covers **crypto exchanges**. Trading other asset
classes in the traditional sense — stocks, forex, commodities, bonds —
would need a different data/broker layer entirely (e.g. Alpaca or Interactive
Brokers for stocks, OANDA for forex): different APIs, different market
hours, different order types. None of that is wired up here; ask if you want
it added for a specific asset class and broker.

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
