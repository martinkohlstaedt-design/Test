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

## Daytrading research on US stocks (`daytrade/`)

Intraday research toolkit for liquid US stocks. Research only - no order placement.

```bash
# 1. put ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY in .env (free Alpaca paper account)
python -m daytrade.download --symbols SPY QQQ AAPL MSFT NVDA AMZN META TSLA AMD GOOGL --start 2022-01-01
# 2. rolling walk-forward validation of ORB, VWAP-reversion, RVOL-momentum
python -m daytrade.validate
# sanity check on random-walk data: nothing should be profitable
python -m daytrade.validate --synthetic --train-days 120 --test-days 40
python -m unittest discover -s daytrade/tests -t .
```

Fills happen at the next bar's open, with slippage on every fill, stop-before-target
in ambiguous bars, positions flat by the close. Only out-of-sample walk-forward
numbers count. A strategy is only worth paper-trading if its OOS result stays
positive after costs across folds and symbols.

### Findings so far (real Alpaca data, 10 liquid US stocks / 45-stock daily universe)

- **Intraday (5-min, 2023-2026 walk-forward OOS):** ORB, VWAP-reversion and RVOL-momentum
  all lose after realistic costs (Sharpe -0.4 to -2.2 at 2 bps/side). Even with ZERO costs
  the gross edge is ~0 (avg 0.00-0.04 R/trade). No intraday edge found.
- **Swing (daily, 2016-2026):** `python -m daytrade.swing --grid`. The 50d-breakout trend
  filter has Sharpe ~1.1, stable across its whole parameter grid, but equals buy-and-hold of
  the same stocks (Sharpe ~1.13) - its benefit is lower drawdown (18 % vs 33 %), not alpha.
  RSI2 reversion and momentum do not beat buy-and-hold.
- **Survivorship bias:** the universe is today's large caps; every number is optimistic.

```bash
python -m daytrade.download_daily      # SIP daily bars 2016-> (free Alpaca plan, ends 2 days ago)
python -m daytrade.swing --grid
```

### Paper-trading bot (trend filter)

```bash
python -m daytrade.paper_bot             # dry run: shows the orders it would place
python -m daytrade.paper_bot --execute   # places market-on-open orders on the Alpaca PAPER account
```
Run once per trading day after the close. `.github/workflows/paper_bot.yml` automates this
(add `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET_KEY` as repository secrets; scheduled workflows
only run from the default branch). The endpoint is hard-coded to paper - there is no live switch.

### Return optimisation (trend filter, 2016-2026 backtest, validated on a 2016-20 / 2021-26 split)

| Variant | CAGR | Max DD | 2016-20 / 2021-26 CAGR |
|---|---|---|---|
| Trend filter (baseline) | 16.1 % | 17.6 % | 17.6 / 14.8 |
| **+ idle capital parked in SPY (bot default)** | **20.3 %** | 32.9 % | 22.9 / 18.1 |
| + 1.25x / 1.5x leverage (`--leverage`, 5 % financing) | 23.8 % / 27.2 % | 39.7 % / 46.1 % | |
| Top-5 momentum ranking (rejected) | 23.0 % | 27.3 % | 34.5 / 13.7 - fails out-of-sample |

More return here means more market risk, not free alpha. Survivorship bias still inflates all numbers.
`python -m daytrade.paper_bot [--no-park-spy] [--leverage 1.25]`

### Other strategies tested (no leverage; `python -m daytrade.rotation`)

| Strategy | CAGR | Sharpe | Max DD | dev 16-20 / test 21-26 CAGR |
|---|---|---|---|---|
| SPY / QQQ buy&hold | 15.1 / 20.5 % | 0.92 / 0.97 | 32 / 37 % | |
| Trend stocks + SPY park | 20.3 % | 1.14 | 32.9 % | 22.9 / 18.1 |
| **Trend stocks + QQQ park (bot default)** | **21.8 %** | **1.18** | 28.2 % | 25.2 / 19.0 |
| Trend stocks, idle -> SPY or IEF by regime | 16.8 % | 1.12 | 21.4 % | 19.5 / 14.5 |
| Sector rotation (top 3, 6-12m) | 7.1-13.5 % | 0.50-0.86 | 28-31 % | worse than SPY |
| Dual momentum | 7.4-10.3 % | 0.46-0.60 | 33-40 % | worse than SPY |
| ETF trend (Faber, 10m SMA) | 7.4 % | 0.91 | 12.1 % | low return, low risk |

Position count (6-20 slots) barely matters (20.5-22.2 %): a plateau, not a tuned peak. QQQ as the
parking asset leans on the 2016-26 tech bull market - hindsight - so treat 21.8 % as optimistic.
`python -m daytrade.paper_bot [--park QQQ|SPY|none]`

### "40 % day-trading strategies" from the internet, tested (`python -m daytrade.stocks_in_play`)

The best-known claim is the Zarattini/Barbon/Aziz 5-min opening-range breakout on "Stocks in Play"
(paper: Sharpe 2.8, ~36 % alpha, 4x leverage, no slippage). Rebuilt on 45 liquid US stocks, 5-min SIP
bars, Jan 2021 - Oct 2026 (the second half is after the paper's sample), 1 % risk per trade:

| Costs per side | 1x leverage | 4x leverage |
|---|---|---|
| 0 bps (the paper's assumption) | 8.6 %/yr, Sharpe 1.3 | 32.3 %/yr, Sharpe 1.4, DD 19 % |
| 1 bps (optimistic for mega caps) | 3.3 %/yr | 8.6 %/yr, DD 26 % |
| 2 bps (realistic) | -1.7 %/yr | -10.9 %/yr, DD 48 % |

With a coin flip for the direction the zero-cost result is still positive (4.6 %/yr @1x), so most of the
"edge" is the payoff structure, not the first-candle signal. Stop width / top-N / RVOL variants do not
rescue it. Conclusion: ~30-40 % appears only with zero costs AND 4x leverage; it does not survive realistic fills.

### Alternatives search (no leverage) - and a correction

`python -m daytrade.broad <constituents.csv>` (S&P 500, eligible only from index "Date added"),
crypto via `python -m daytrade.download_extra crypto`. 2016-2026 unless noted, 3 bps/side (crypto 25 bps).

| Option | CAGR | Sharpe | Max DD | Note |
|---|---|---|---|---|
| QQQ buy&hold | 20.5 % | 0.97 | 36.6 % | benchmark to beat |
| QQQ vol-target 20 % (max 1x, rest cash) | 19.2 % | 1.11 | 28.3 % | best simple risk-adjusted |
| QQQ below SMA150 -> cash | 18.0 % | 1.09 | 22.4 % | halves, drawdown |
| S&P 500 momentum top 20-40 + trend, idle->QQQ | 17-21 % | 0.77-0.83 | 37-38 % | 14 % in 2016-20 vs 23-28 % in 2021-26 |
| Trend (Donchian) on all S&P members, idle->QQQ | 12.6-13.7 % | 0.84-0.90 | 26 % | |
| Crypto BTC / BTC+ETH trend (2021-26) | 14-20 % | 0.56-0.69 | 36 % | b&h BTC 19 %, DD 77 % |

**Correction:** the 45-stock trend bot's 21.8 % (Sharpe 1.18) is inflated by hand-picked survivors; the same
rule on the whole S&P 500 gives ~13 %. Realistic expectation for unlevered long equity in this decade is
15-20 %; 40 % needs leverage, concentration or luck. Crypto "10-coin 45 %" is pure survivor selection.
