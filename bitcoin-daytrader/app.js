// Bitcoin Day-Trader (Paper Trading) — live BTC/USDT candles from Binance's public API,
// simple technical-indicator signal, and a fully simulated (no real money) trading account
// persisted in localStorage.

const SYMBOL = "BTCUSDT";
const FEE_PCT = 0.001; // 0.1%, roughly matching a real exchange's taker fee
const STARTING_BALANCE = 10000;
const STATE_KEY = "btc-daytrader-state-v1";

const POLL_MS = { "1m": 15000, "5m": 30000, "15m": 60000, "1h": 60000, "4h": 120000 };

let state = loadState();
let currentInterval = "5m";
let klines = [];
let pollTimer = null;
let lastSignalTone = null;
let chart, candleSeries;

const els = {
  livePrice: document.getElementById("live-price"),
  liveChange: document.getElementById("live-change"),
  dataStatus: document.getElementById("data-status"),
  refreshBtn: document.getElementById("refresh-btn"),
  chartError: document.getElementById("chart-error"),
  signalBadge: document.getElementById("signal-badge"),
  signalReasons: document.getElementById("signal-reasons"),
  pfCash: document.getElementById("pf-cash"),
  pfBtc: document.getElementById("pf-btc"),
  pfEquity: document.getElementById("pf-equity"),
  pfPnl: document.getElementById("pf-pnl"),
  resetBtn: document.getElementById("reset-btn"),
  orderAmount: document.getElementById("order-amount"),
  buyBtn: document.getElementById("buy-btn"),
  sellBtn: document.getElementById("sell-btn"),
  autopilotToggle: document.getElementById("autopilot-toggle"),
  tape: document.getElementById("tape"),
  tradeLogBody: document.getElementById("trade-log-body"),
  tradeLogEmpty: document.getElementById("trade-log-empty"),
};

// ---------- State ----------

function loadState() {
  try {
    const raw = localStorage.getItem(STATE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) { /* ignore corrupt state */ }
  return { cashUsd: STARTING_BALANCE, btcAmount: 0, trades: [], autopilot: false };
}

function saveState() {
  localStorage.setItem(STATE_KEY, JSON.stringify(state));
}

// ---------- Indicators (same math family as crypto-dashboard/indicators.js) ----------

function calcEMA(values, period) {
  const out = new Array(values.length).fill(null);
  if (values.length < period) return out;
  const k = 2 / (period + 1);
  let seed = 0;
  for (let i = 0; i < period; i++) seed += values[i];
  seed /= period;
  out[period - 1] = seed;
  for (let i = period; i < values.length; i++) out[i] = values[i] * k + out[i - 1] * (1 - k);
  return out;
}

function calcRSI(values, period = 14) {
  const out = new Array(values.length).fill(null);
  if (values.length < period + 1) return out;
  let gainSum = 0, lossSum = 0;
  for (let i = 1; i <= period; i++) {
    const diff = values[i] - values[i - 1];
    gainSum += Math.max(diff, 0);
    lossSum += Math.max(-diff, 0);
  }
  let avgGain = gainSum / period, avgLoss = lossSum / period;
  out[period] = rsiFromAvg(avgGain, avgLoss);
  for (let i = period + 1; i < values.length; i++) {
    const diff = values[i] - values[i - 1];
    avgGain = (avgGain * (period - 1) + Math.max(diff, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-diff, 0)) / period;
    out[i] = rsiFromAvg(avgGain, avgLoss);
  }
  return out;
}

function rsiFromAvg(avgGain, avgLoss) {
  if (avgLoss === 0) return avgGain === 0 ? 50 : 100;
  return 100 - 100 / (1 + avgGain / avgLoss);
}

function calcMACD(values, fast = 12, slow = 26, signalPeriod = 9) {
  const emaFast = calcEMA(values, fast);
  const emaSlow = calcEMA(values, slow);
  const macdLine = values.map((_, i) => (emaFast[i] != null && emaSlow[i] != null ? emaFast[i] - emaSlow[i] : null));
  const firstValid = macdLine.findIndex((v) => v != null);
  const signalLine = new Array(values.length).fill(null);
  if (firstValid !== -1) {
    const compactEma = calcEMA(macdLine.slice(firstValid), signalPeriod);
    compactEma.forEach((v, i) => { if (v != null) signalLine[firstValid + i] = v; });
  }
  const histogram = values.map((_, i) => (macdLine[i] != null && signalLine[i] != null ? macdLine[i] - signalLine[i] : null));
  return { macdLine, signalLine, histogram };
}

function lastValid(arr) {
  for (let i = arr.length - 1; i >= 0; i--) if (arr[i] != null) return arr[i];
  return null;
}
function valueAt(arr, offsetFromEnd) {
  const idx = arr.length - 1 - offsetFromEnd;
  return idx >= 0 ? arr[idx] : null;
}

// Short-term signal tuned for intraday timeframes: EMA9/EMA21 trend, RSI14 momentum, MACD histogram.
function computeSignal(closes) {
  const ema9 = calcEMA(closes, 9);
  const ema21 = calcEMA(closes, 21);
  const rsi = calcRSI(closes, 14);
  const { histogram } = calcMACD(closes, 12, 26, 9);

  const lastPrice = closes[closes.length - 1];
  const lastEma9 = lastValid(ema9);
  const lastEma21 = lastValid(ema21);
  const lastRsi = lastValid(rsi);
  const lastHist = lastValid(histogram);
  const prevHist = valueAt(histogram, 1);

  let score = 0;
  const reasons = [];

  if (lastEma9 != null && lastEma21 != null) {
    if (lastPrice > lastEma9 && lastEma9 > lastEma21) { score += 2; reasons.push("Aufwärtstrend (Preis > EMA9 > EMA21)"); }
    else if (lastPrice < lastEma9 && lastEma9 < lastEma21) { score -= 2; reasons.push("Abwärtstrend (Preis < EMA9 < EMA21)"); }
  }

  if (lastRsi != null) {
    if (lastRsi < 30) { score += 2; reasons.push(`RSI ${lastRsi.toFixed(0)} (überverkauft)`); }
    else if (lastRsi > 70) { score -= 2; reasons.push(`RSI ${lastRsi.toFixed(0)} (überkauft)`); }
    else reasons.push(`RSI ${lastRsi.toFixed(0)} (neutral)`);
  }

  if (lastHist != null && prevHist != null) {
    if (prevHist <= 0 && lastHist > 0) { score += 2; reasons.push("MACD-Bullen-Crossover"); }
    else if (prevHist >= 0 && lastHist < 0) { score -= 2; reasons.push("MACD-Bären-Crossover"); }
    else if (lastHist > 0) { score += 1; reasons.push("MACD-Histogramm positiv"); }
    else if (lastHist < 0) { score -= 1; reasons.push("MACD-Histogramm negativ"); }
  }

  let label, tone;
  if (score >= 4) { label = "Starkes Kaufsignal"; tone = "strong-buy"; }
  else if (score >= 2) { label = "Kaufsignal"; tone = "buy"; }
  else if (score <= -4) { label = "Starkes Verkaufssignal"; tone = "strong-sell"; }
  else if (score <= -2) { label = "Verkaufssignal"; tone = "sell"; }
  else { label = "Neutral / Halten"; tone = "hold"; }

  return { score, label, tone, reasons };
}

// ---------- Data fetching (Binance public REST, no API key needed) ----------

async function fetchKlines(interval) {
  const url = `https://api.binance.com/api/v3/klines?symbol=${SYMBOL}&interval=${interval}&limit=300`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Binance-Klines-Fehler ${res.status}`);
  const raw = await res.json();
  return raw.map((k) => ({
    time: Math.floor(k[0] / 1000),
    open: parseFloat(k[1]),
    high: parseFloat(k[2]),
    low: parseFloat(k[3]),
    close: parseFloat(k[4]),
    volume: parseFloat(k[5]),
  }));
}

async function fetchTicker24h() {
  const res = await fetch(`https://api.binance.com/api/v3/ticker/24hr?symbol=${SYMBOL}`);
  if (!res.ok) throw new Error(`Binance-Ticker-Fehler ${res.status}`);
  return res.json();
}

async function fetchRecentTrades() {
  const res = await fetch(`https://api.binance.com/api/v3/trades?symbol=${SYMBOL}&limit=20`);
  if (!res.ok) throw new Error(`Binance-Trades-Fehler ${res.status}`);
  return res.json();
}

// ---------- Chart ----------

function initChart() {
  chart = LightweightCharts.createChart(document.getElementById("chart"), {
    layout: { background: { color: "#141821" }, textColor: "#c7cdd9" },
    grid: { vertLines: { color: "#20242f" }, horzLines: { color: "#20242f" } },
    timeScale: { timeVisible: true, secondsVisible: false },
    rightPriceScale: { borderColor: "#262c3a" },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  });
  candleSeries = chart.addCandlestickSeries({
    upColor: "#16c784", downColor: "#ea3943",
    borderUpColor: "#16c784", borderDownColor: "#ea3943",
    wickUpColor: "#16c784", wickDownColor: "#ea3943",
  });
  new ResizeObserver((entries) => {
    const { width, height } = entries[0].contentRect;
    chart.resize(width, height);
  }).observe(document.getElementById("chart"));
}

function renderChart() {
  candleSeries.setData(klines.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));
}

// ---------- Rendering ----------

function fmtUsd(n) {
  return n.toLocaleString("de-DE", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
}
function fmtBtc(n) {
  return `${n.toLocaleString("de-DE", { maximumFractionDigits: 6 })} BTC`;
}

function currentPrice() {
  return klines.length ? klines[klines.length - 1].close : null;
}

function renderLivePrice(ticker) {
  const price = parseFloat(ticker.lastPrice);
  const changePct = parseFloat(ticker.priceChangePercent);
  els.livePrice.textContent = fmtUsd(price);
  els.liveChange.textContent = `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}% (24h)`;
  els.liveChange.className = `chip ${changePct >= 0 ? "up" : "down"}`;
}

function renderSignal() {
  if (klines.length < 30) return null;
  const closes = klines.map((k) => k.close);
  const signal = computeSignal(closes);
  els.signalBadge.textContent = signal.label;
  els.signalBadge.className = `signal-badge ${signal.tone}`;
  els.signalReasons.innerHTML = signal.reasons.map((r) => `<li>${r}</li>`).join("");
  return signal;
}

function renderPortfolio() {
  const price = currentPrice() || 0;
  const equity = state.cashUsd + state.btcAmount * price;
  const pnl = equity - STARTING_BALANCE;
  const pnlPct = (pnl / STARTING_BALANCE) * 100;

  els.pfCash.textContent = fmtUsd(state.cashUsd);
  els.pfBtc.textContent = fmtBtc(state.btcAmount);
  els.pfEquity.textContent = fmtUsd(equity);
  els.pfPnl.textContent = `${pnl >= 0 ? "+" : ""}${fmtUsd(pnl)} (${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%)`;
  els.pfPnl.className = pnl >= 0 ? "up" : "down";
}

function renderTradeLog() {
  if (!state.trades.length) {
    els.tradeLogEmpty.classList.remove("hidden");
    els.tradeLogBody.innerHTML = "";
    return;
  }
  els.tradeLogEmpty.classList.add("hidden");
  els.tradeLogBody.innerHTML = state.trades
    .slice()
    .reverse()
    .map((t) => `
      <tr>
        <td>${new Date(t.time).toLocaleString("de-DE")}</td>
        <td>${t.source}</td>
        <td class="side-${t.side}">${t.side === "buy" ? "Kauf" : "Verkauf"}</td>
        <td>${fmtUsd(t.price)}</td>
        <td>${t.btcAmount.toFixed(6)}</td>
        <td>${fmtUsd(t.usdValue)}</td>
        <td>${fmtUsd(t.cashAfter)}</td>
      </tr>`)
    .join("");
}

function renderTape(trades) {
  els.tape.innerHTML = trades
    .slice()
    .reverse()
    .map((t) => {
      const price = parseFloat(t.price);
      const time = new Date(t.time).toLocaleTimeString("de-DE");
      const side = t.isBuyerMaker ? "down" : "up"; // taker side: not-maker-buyer means an aggressive buy
      return `<div class="tape-row"><span class="time">${time}</span><span class="price ${side}">${fmtUsd(price)}</span></div>`;
    })
    .join("");
}

// ---------- Trading ----------

function executeTrade(side, usdAmount, source = "Manuell") {
  const price = currentPrice();
  if (!price) return { ok: false, error: "Keine aktuellen Kursdaten verfügbar." };
  if (!usdAmount || usdAmount <= 0) return { ok: false, error: "Bitte einen gültigen Betrag angeben." };

  if (side === "buy") {
    if (usdAmount > state.cashUsd) return { ok: false, error: "Nicht genug Cash für diesen Kauf." };
    const fee = usdAmount * FEE_PCT;
    const btcBought = (usdAmount - fee) / price;
    state.cashUsd -= usdAmount;
    state.btcAmount += btcBought;
    state.trades.push({ time: Date.now(), source, side: "buy", price, btcAmount: btcBought, usdValue: usdAmount, cashAfter: state.cashUsd });
  } else {
    const btcToSell = usdAmount / price;
    if (btcToSell > state.btcAmount + 1e-9) return { ok: false, error: "Nicht genug BTC-Bestand für diesen Verkauf." };
    const gross = btcToSell * price;
    const fee = gross * FEE_PCT;
    state.cashUsd += gross - fee;
    state.btcAmount -= btcToSell;
    state.trades.push({ time: Date.now(), source, side: "sell", price, btcAmount: btcToSell, usdValue: gross - fee, cashAfter: state.cashUsd });
  }
  saveState();
  renderPortfolio();
  renderTradeLog();
  return { ok: true };
}

function runAutopilot(signal) {
  if (!state.autopilot || !signal) return;
  if (signal.tone === lastSignalTone) return; // only act when the signal actually changes

  const isBuySignal = signal.tone === "buy" || signal.tone === "strong-buy";
  const isSellSignal = signal.tone === "sell" || signal.tone === "strong-sell";

  if (isBuySignal && state.cashUsd > 1) {
    executeTrade("buy", state.cashUsd, "Auto");
  } else if (isSellSignal && state.btcAmount > 0) {
    executeTrade("sell", state.btcAmount * currentPrice(), "Auto");
  }
  lastSignalTone = signal.tone;
}

// ---------- Orchestration ----------

async function refreshAll() {
  try {
    els.dataStatus.textContent = "Aktualisiere…";
    const [newKlines, ticker, trades] = await Promise.all([
      fetchKlines(currentInterval),
      fetchTicker24h(),
      fetchRecentTrades(),
    ]);
    klines = newKlines;
    renderChart();
    renderLivePrice(ticker);
    renderTape(trades);
    const signal = renderSignal();
    renderPortfolio();
    runAutopilot(signal);
    els.chartError.classList.add("hidden");
    els.dataStatus.textContent = `Zuletzt aktualisiert: ${new Date().toLocaleTimeString("de-DE")}`;
  } catch (err) {
    els.chartError.textContent = `Kursdaten konnten nicht geladen werden: ${err.message}`;
    els.chartError.classList.remove("hidden");
    els.dataStatus.textContent = "Fehler beim Aktualisieren.";
  }
}

function schedulePolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(refreshAll, POLL_MS[currentInterval] || 30000);
}

function setInterval_(interval) {
  currentInterval = interval;
  document.querySelectorAll(".tf-btn").forEach((btn) => btn.classList.toggle("active", btn.dataset.interval === interval));
  refreshAll();
  schedulePolling();
}

function pctOfAvailable(side, pct) {
  const price = currentPrice();
  if (!price) return 0;
  if (side === "buy") return Math.floor(state.cashUsd * (pct / 100));
  return Math.floor(state.btcAmount * price * (pct / 100));
}

function bindEvents() {
  document.getElementById("timeframe-group").addEventListener("click", (e) => {
    const btn = e.target.closest(".tf-btn");
    if (btn) setInterval_(btn.dataset.interval);
  });

  els.refreshBtn.addEventListener("click", refreshAll);

  els.buyBtn.addEventListener("click", () => {
    const amount = parseFloat(els.orderAmount.value);
    const result = executeTrade("buy", amount, "Manuell");
    if (!result.ok) alert(result.error);
  });

  els.sellBtn.addEventListener("click", () => {
    const amount = parseFloat(els.orderAmount.value);
    const result = executeTrade("sell", amount, "Manuell");
    if (!result.ok) alert(result.error);
  });

  document.querySelectorAll(".pct-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pct = parseFloat(btn.dataset.pct);
      const side = state.btcAmount * (currentPrice() || 0) >= state.cashUsd ? "sell" : "buy";
      els.orderAmount.value = pctOfAvailable(side, pct);
    });
  });

  els.resetBtn.addEventListener("click", () => {
    if (!confirm("Paper-Trading-Portfolio wirklich zurücksetzen?")) return;
    state = { cashUsd: STARTING_BALANCE, btcAmount: 0, trades: [], autopilot: state.autopilot };
    saveState();
    renderPortfolio();
    renderTradeLog();
  });

  els.autopilotToggle.checked = state.autopilot;
  els.autopilotToggle.addEventListener("change", () => {
    state.autopilot = els.autopilotToggle.checked;
    lastSignalTone = null; // re-arm so a currently-held signal can trigger a trade
    saveState();
  });
}

function init() {
  initChart();
  bindEvents();
  renderPortfolio();
  renderTradeLog();
  setInterval_(currentInterval);
}

init();
