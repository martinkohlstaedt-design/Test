// Reusable technical-indicator math, operating on plain arrays of closing prices / volumes.
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

// SMA over a series that may start with nulls (e.g. a derived indicator), assuming
// no gaps once the first non-null value appears.
function alignedSMA(values, period) {
  const firstValid = values.findIndex((v) => v != null);
  const out = new Array(values.length).fill(null);
  if (firstValid === -1) return out;
  const compact = values.slice(firstValid);
  const compactSma = calcSMA(compact, period);
  compactSma.forEach((v, i) => {
    if (v != null) out[firstValid + i] = v;
  });
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
  const realSignal = new Array(values.length).fill(null);
  if (firstValid !== -1) {
    const compact = macdLine.slice(firstValid);
    const compactEma = calcEMA(compact, signalPeriod);
    compactEma.forEach((v, i) => {
      if (v != null) realSignal[firstValid + i] = v;
    });
  }
  const histogram = values.map((_, i) =>
    macdLine[i] != null && realSignal[i] != null ? macdLine[i] - realSignal[i] : null
  );
  return { macdLine, signalLine: realSignal, histogram };
}

function calcBollinger(values, period = 20, stdDevMult = 2) {
  const sma = calcSMA(values, period);
  const upper = new Array(values.length).fill(null);
  const lower = new Array(values.length).fill(null);
  const percentB = new Array(values.length).fill(null);
  for (let i = period - 1; i < values.length; i++) {
    let sumSq = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sumSq += (values[j] - sma[i]) ** 2;
    }
    const stdDev = Math.sqrt(sumSq / period);
    upper[i] = sma[i] + stdDevMult * stdDev;
    lower[i] = sma[i] - stdDevMult * stdDev;
    percentB[i] = upper[i] === lower[i] ? 0.5 : (values[i] - lower[i]) / (upper[i] - lower[i]);
  }
  return { middle: sma, upper, lower, percentB };
}

// Stochastic RSI: applies the stochastic-oscillator formula to RSI values instead of price.
function calcStochasticRSI(closes, rsiPeriod = 14, stochPeriod = 14, kSmooth = 3, dSmooth = 3) {
  const rsi = calcRSI(closes, rsiPeriod);
  const rawK = new Array(closes.length).fill(null);
  for (let i = 0; i < closes.length; i++) {
    if (rsi[i] == null || i - stochPeriod + 1 < 0) continue;
    let mn = Infinity, mx = -Infinity, ok = true;
    for (let j = i - stochPeriod + 1; j <= i; j++) {
      if (rsi[j] == null) { ok = false; break; }
      mn = Math.min(mn, rsi[j]);
      mx = Math.max(mx, rsi[j]);
    }
    if (!ok) continue;
    rawK[i] = mx === mn ? 50 : ((rsi[i] - mn) / (mx - mn)) * 100;
  }
  const k = alignedSMA(rawK, kSmooth);
  const d = alignedSMA(k, dSmooth);
  return { k, d };
}

// On-Balance Volume: cumulative volume flow, signed by the direction of each price move.
function calcOBV(closes, volumes) {
  const out = new Array(closes.length).fill(null);
  if (!volumes || volumes.length !== closes.length) return out;
  out[0] = 0;
  for (let i = 1; i < closes.length; i++) {
    const vol = volumes[i] || 0;
    if (closes[i] > closes[i - 1]) out[i] = out[i - 1] + vol;
    else if (closes[i] < closes[i - 1]) out[i] = out[i - 1] - vol;
    else out[i] = out[i - 1];
  }
  return out;
}

function lastValid(arr) {
  if (!arr) return null;
  for (let i = arr.length - 1; i >= 0; i--) {
    if (arr[i] != null) return arr[i];
  }
  return null;
}

function valueAt(arr, offsetFromEnd) {
  if (!arr) return null;
  const idx = arr.length - 1 - offsetFromEnd;
  return idx >= 0 ? arr[idx] : null;
}

// Detects a moving-average crossover using the two most recent points where both
// series have a value. Returns "golden" (short crossed above long), "death"
// (short crossed below long), "above"/"below" (steady state) or null.
function detectCrossover(shortArr, longArr) {
  const idxs = [];
  for (let i = shortArr.length - 1; i >= 0 && idxs.length < 2; i--) {
    if (shortArr[i] != null && longArr[i] != null) idxs.unshift(i);
  }
  if (idxs.length < 2) return null;
  const [i0, i1] = idxs;
  const prevDiff = shortArr[i0] - longArr[i0];
  const currDiff = shortArr[i1] - longArr[i1];
  if (prevDiff <= 0 && currDiff > 0) return "golden";
  if (prevDiff >= 0 && currDiff < 0) return "death";
  return currDiff > 0 ? "above" : "below";
}

// Combines RSI, MACD, Bollinger %B, Stochastic RSI, OBV volume confirmation,
// a 50/200 moving-average crossover and short-term momentum into one composite
// score. Works on whatever timeframe's closes/volumes you hand it (daily, weekly, …).
function computeSignal({ closes, volumes, changePct24h, changePct7d }) {
  const rsi = calcRSI(closes, 14);
  const { macdLine, signalLine, histogram } = calcMACD(closes, 12, 26, 9);
  const sma20 = calcSMA(closes, 20);
  const sma50 = calcSMA(closes, 50);
  const sma200 = calcSMA(closes, 200);
  const bb = calcBollinger(closes, 20, 2);
  const stochRsi = calcStochasticRSI(closes, 14, 14, 3, 3);
  const obv = calcOBV(closes, volumes);

  const lastRsi = lastValid(rsi);
  const lastHist = lastValid(histogram);
  const prevHist = valueAt(histogram, 1);
  const lastMacd = lastValid(macdLine);
  const lastSignal = lastValid(signalLine);
  const lastPrice = closes[closes.length - 1];
  const lastSma20 = lastValid(sma20);
  const lastSma50 = lastValid(sma50);
  const lastSma200 = lastValid(sma200);
  const lastPercentB = lastValid(bb.percentB);
  const lastStochK = lastValid(stochRsi.k);
  const lastStochD = lastValid(stochRsi.d);
  const crossover = detectCrossover(sma50, sma200);

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
    else if (lastHist > 0) { score += 1; reasons.push("MACD-Histogramm positiv"); }
    else if (lastHist < 0) { score -= 1; reasons.push("MACD-Histogramm negativ"); }
  }

  if (lastSma20 != null && lastSma50 != null) {
    if (lastPrice > lastSma20 && lastSma20 > lastSma50) { score += 1; reasons.push("Aufwärtstrend (Preis > SMA20 > SMA50)"); }
    else if (lastPrice < lastSma20 && lastSma20 < lastSma50) { score -= 1; reasons.push("Abwärtstrend (Preis < SMA20 < SMA50)"); }
  }

  if (crossover === "golden") { score += 3; reasons.push("Golden Cross (SMA50 kreuzt SMA200 nach oben)"); }
  else if (crossover === "death") { score -= 3; reasons.push("Death Cross (SMA50 kreuzt SMA200 nach unten)"); }
  else if (crossover === "above") { score += 1; reasons.push("SMA50 über SMA200 (langfristiger Aufwärtstrend)"); }
  else if (crossover === "below") { score -= 1; reasons.push("SMA50 unter SMA200 (langfristiger Abwärtstrend)"); }

  if (lastPercentB != null) {
    if (lastPercentB < 0) { score += 1; reasons.push("Preis unter unterem Bollinger-Band"); }
    else if (lastPercentB > 1) { score -= 1; reasons.push("Preis über oberem Bollinger-Band"); }
  }

  if (lastStochK != null) {
    if (lastStochK < 20) { score += 1; reasons.push(`Stochastic RSI ${lastStochK.toFixed(0)} (überverkauft)`); }
    else if (lastStochK > 80) { score -= 1; reasons.push(`Stochastic RSI ${lastStochK.toFixed(0)} (überkauft)`); }
  }

  const obvNow = lastValid(obv);
  const obvPrev = valueAt(obv, 10);
  if (obvNow != null && obvPrev != null && closes.length > 11) {
    const priceTrend = closes[closes.length - 1] - closes[closes.length - 11];
    const obvTrend = obvNow - obvPrev;
    if (priceTrend > 0 && obvTrend > 0) { score += 1; reasons.push("Volumen bestätigt Aufwärtstrend (OBV steigt)"); }
    else if (priceTrend < 0 && obvTrend < 0) { score -= 1; reasons.push("Volumen bestätigt Abwärtstrend (OBV fällt)"); }
    else if (priceTrend > 0 && obvTrend < 0) { score -= 1; reasons.push("Warnung: bärische OBV-Divergenz"); }
    else if (priceTrend < 0 && obvTrend > 0) { score += 1; reasons.push("Hinweis: bullische OBV-Divergenz"); }
  }

  if (typeof changePct24h === "number" && typeof changePct7d === "number") {
    if (changePct24h > 0 && changePct7d > 0) { score += 1; reasons.push("Momentum positiv (24h & 7d)"); }
    else if (changePct24h < 0 && changePct7d < 0) { score -= 1; reasons.push("Momentum negativ (24h & 7d)"); }
  }

  let label, tone;
  if (score >= 6) { label = "Starkes Kaufsignal"; tone = "strong-buy"; }
  else if (score >= 3) { label = "Kaufsignal"; tone = "buy"; }
  else if (score <= -6) { label = "Starkes Verkaufssignal"; tone = "strong-sell"; }
  else if (score <= -3) { label = "Verkaufssignal"; tone = "sell"; }
  else { label = "Neutral / Halten"; tone = "hold"; }

  return {
    score, label, tone, reasons,
    series: { sma20, sma50, sma200, rsi, macdLine, signalLine, histogram, bbUpper: bb.upper, bbLower: bb.lower, bbMiddle: bb.middle, stochK: stochRsi.k, stochD: stochRsi.d, obv },
    lastRsi, lastMacd, lastSignal, lastHist, lastStochK, lastStochD, lastPercentB, crossover,
    sma20: lastSma20, sma50: lastSma50, sma200: lastSma200,
  };
}

if (typeof module !== "undefined") {
  module.exports = {
    calcSMA, calcEMA, calcRSI, calcMACD, calcBollinger, calcStochasticRSI, calcOBV,
    detectCrossover, computeSignal, lastValid, alignedSMA,
  };
}
