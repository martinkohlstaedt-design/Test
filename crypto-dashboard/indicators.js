// Reusable technical-indicator math, operating on plain arrays of closing prices.
// Every function returns an array aligned 1:1 with the input (nulls where not yet defined).

function calcSMA(values, period) {
  const out = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

function calcEMA(values, period) {
  const out = new Array(values.length).fill(null);
  if (values.length < period) return out;
  const k = 2 / (period + 1);
  let seed = 0;
  for (let i = 0; i < period; i++) seed += values[i];
  seed /= period;
  out[period - 1] = seed;
  for (let i = period; i < values.length; i++) {
    out[i] = values[i] * k + out[i - 1] * (1 - k);
  }
  return out;
}

// Wilder's smoothed RSI.
function calcRSI(values, period = 14) {
  const out = new Array(values.length).fill(null);
  if (values.length < period + 1) return out;

  let gainSum = 0;
  let lossSum = 0;
  for (let i = 1; i <= period; i++) {
    const diff = values[i] - values[i - 1];
    gainSum += Math.max(diff, 0);
    lossSum += Math.max(-diff, 0);
  }
  let avgGain = gainSum / period;
  let avgLoss = lossSum / period;
  out[period] = rsiFromAvg(avgGain, avgLoss);

  for (let i = period + 1; i < values.length; i++) {
    const diff = values[i] - values[i - 1];
    const gain = Math.max(diff, 0);
    const loss = Math.max(-diff, 0);
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    out[i] = rsiFromAvg(avgGain, avgLoss);
  }
  return out;
}

function rsiFromAvg(avgGain, avgLoss) {
  if (avgLoss === 0) return avgGain === 0 ? 50 : 100;
  const rs = avgGain / avgLoss;
  return 100 - 100 / (1 + rs);
}

function calcMACD(values, fast = 12, slow = 26, signalPeriod = 9) {
  const emaFast = calcEMA(values, fast);
  const emaSlow = calcEMA(values, slow);
  const macdLine = values.map((_, i) =>
    emaFast[i] != null && emaSlow[i] != null ? emaFast[i] - emaSlow[i] : null
  );

  const firstValid = macdLine.findIndex((v) => v != null);
  const signalLine = new Array(values.length).fill(null);
  if (firstValid !== -1) {
    const compact = macdLine.slice(firstValid);
    const compactEma = calcEMA(compact, signalPeriod);
    compactEma.forEach((v, i) => {
      if (v != null) signalLine[firstValid + i] = v;
    });
  }

  const histogram = values.map((_, i) =>
    macdLine[i] != null && signalLine[i] != null ? macdLine[i] - signalLine[i] : null
  );

  return { macdLine, signalLine, histogram };
}

function calcBollinger(values, period = 20, stdDevMult = 2) {
  const sma = calcSMA(values, period);
  const upper = new Array(values.length).fill(null);
  const lower = new Array(values.length).fill(null);
  for (let i = period - 1; i < values.length; i++) {
    let sumSq = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sumSq += (values[j] - sma[i]) ** 2;
    }
    const stdDev = Math.sqrt(sumSq / period);
    upper[i] = sma[i] + stdDevMult * stdDev;
    lower[i] = sma[i] - stdDevMult * stdDev;
  }
  return { middle: sma, upper, lower };
}

function lastValid(arr) {
  for (let i = arr.length - 1; i >= 0; i--) {
    if (arr[i] != null) return arr[i];
  }
  return null;
}

// Combines RSI + MACD crossover + moving-average trend + short-term momentum
// into one score from -6 (strong sell) to +6 (strong buy).
function computeSignal({ closes, changePct24h, changePct7d }) {
  const rsi = calcRSI(closes, 14);
  const { macdLine, signalLine, histogram } = calcMACD(closes, 12, 26, 9);
  const sma20 = calcSMA(closes, 20);
  const sma50 = calcSMA(closes, 50);

  const lastRsi = lastValid(rsi);
  const lastHist = lastValid(histogram);
  const prevHist = histogram.slice(0, -1).filter((v) => v != null).slice(-1)[0] ?? null;
  const lastMacd = lastValid(macdLine);
  const lastSignal = lastValid(signalLine);
  const lastPrice = closes[closes.length - 1];
  const lastSma20 = lastValid(sma20);
  const lastSma50 = lastValid(sma50);

  let score = 0;
  const reasons = [];

  if (lastRsi != null) {
    if (lastRsi < 30) { score += 2; reasons.push(`RSI ${lastRsi.toFixed(0)} (überverkauft)`); }
    else if (lastRsi < 40) { score += 1; reasons.push(`RSI ${lastRsi.toFixed(0)} (schwach)`); }
    else if (lastRsi > 70) { score -= 2; reasons.push(`RSI ${lastRsi.toFixed(0)} (überkauft)`); }
    else if (lastRsi > 60) { score -= 1; reasons.push(`RSI ${lastRsi.toFixed(0)} (stark)`); }
  }

  if (lastMacd != null && lastSignal != null) {
    const bullishCross = lastMacd > lastSignal && lastHist != null && prevHist != null && prevHist <= 0 && lastHist > 0;
    const bearishCross = lastMacd < lastSignal && lastHist != null && prevHist != null && prevHist >= 0 && lastHist < 0;
    if (bullishCross) { score += 2; reasons.push("MACD-Bullen-Crossover"); }
    else if (bearishCross) { score -= 2; reasons.push("MACD-Bären-Crossover"); }
    else if (lastHist != null && lastHist > 0) { score += 1; reasons.push("MACD-Histogramm positiv"); }
    else if (lastHist != null && lastHist < 0) { score -= 1; reasons.push("MACD-Histogramm negativ"); }
  }

  if (lastSma20 != null && lastSma50 != null) {
    if (lastPrice > lastSma20 && lastSma20 > lastSma50) { score += 1; reasons.push("Aufwärtstrend (Preis > SMA20 > SMA50)"); }
    else if (lastPrice < lastSma20 && lastSma20 < lastSma50) { score -= 1; reasons.push("Abwärtstrend (Preis < SMA20 < SMA50)"); }
  }

  if (typeof changePct24h === "number" && typeof changePct7d === "number") {
    if (changePct24h > 0 && changePct7d > 0) { score += 1; reasons.push("Momentum positiv (24h & 7d)"); }
    else if (changePct24h < 0 && changePct7d < 0) { score -= 1; reasons.push("Momentum negativ (24h & 7d)"); }
  }

  let label, tone;
  if (score >= 4) { label = "Starkes Kaufsignal"; tone = "strong-buy"; }
  else if (score >= 2) { label = "Kaufsignal"; tone = "buy"; }
  else if (score <= -4) { label = "Starkes Verkaufssignal"; tone = "strong-sell"; }
  else if (score <= -2) { label = "Verkaufssignal"; tone = "sell"; }
  else { label = "Neutral / Halten"; tone = "hold"; }

  return { score, label, tone, reasons, lastRsi, lastMacd, lastSignal, lastHist, sma20: lastSma20, sma50: lastSma50 };
}

if (typeof module !== "undefined") {
  module.exports = { calcSMA, calcEMA, calcRSI, calcMACD, calcBollinger, computeSignal, lastValid };
}
