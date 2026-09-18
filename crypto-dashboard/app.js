const API_BASE_DEMO = "https://api.coingecko.com/api/v3";
const API_BASE_PRO = "https://pro-api.coingecko.com/api/v3";
const FIXED_COINS = ["bitcoin", "ethereum", "ripple", "solana", "dogecoin"];
const REF_MONDAY = Date.UTC(1970, 0, 5); // a Monday, used to align weekly buckets

const els = {
  grid: document.getElementById("coin-grid"),
  loading: document.getElementById("loading"),
  errorBox: document.getElementById("error-box"),
  refreshBtn: document.getElementById("refresh-btn"),
  refreshStatus: document.getElementById("refresh-status"),
  settingsBtn: document.getElementById("settings-btn"),
  settingsPanel: document.getElementById("settings-panel"),
  vsCurrency: document.getElementById("vs-currency"),
  refreshInterval: document.getElementById("refresh-interval"),
  apiKey: document.getElementById("api-key"),
  apiKeyType: document.getElementById("api-key-type"),
  searchInput: document.getElementById("search-input"),
  sortSelect: document.getElementById("sort-select"),
  filterBtns: Array.from(document.querySelectorAll(".filter-btn")),
  detailOverlay: document.getElementById("detail-overlay"),
  detailContent: document.getElementById("detail-content"),
  detailClose: document.getElementById("detail-close"),
};

const state = {
  settings: loadSettings(),
  watchlist: loadWatchlist(),
  coins: [],
  historyCache: {},
  search: "",
  filter: "all",
  sort: "default",
  refreshTimer: null,
  countdownTimer: null,
  nextRefreshAt: null,
  detail: { id: null, timeframe: "daily", ma: { sma20: false, sma50: true, sma200: true } },
};

function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem("crypto-dashboard-settings") || "{}");
    return {
      vsCurrency: saved.vsCurrency || "usd",
      refreshInterval: saved.refreshInterval ?? 60000,
      apiKey: saved.apiKey || "",
      keyType: saved.keyType || "demo",
    };
  } catch {
    return { vsCurrency: "usd", refreshInterval: 60000, apiKey: "", keyType: "demo" };
  }
}

function saveSettings() {
  localStorage.setItem("crypto-dashboard-settings", JSON.stringify(state.settings));
}

function loadWatchlist() {
  try {
    return new Set(JSON.parse(localStorage.getItem("crypto-dashboard-watchlist") || "[]"));
  } catch {
    return new Set();
  }
}

function saveWatchlist() {
  localStorage.setItem("crypto-dashboard-watchlist", JSON.stringify([...state.watchlist]));
}

function buildUrl(path, params) {
  const isPro = state.settings.keyType === "pro" && state.settings.apiKey;
  const base = isPro ? API_BASE_PRO : API_BASE_DEMO;
  const url = new URL(base + path);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  if (state.settings.apiKey) {
    url.searchParams.set(isPro ? "x_cg_pro_api_key" : "x_cg_demo_api_key", state.settings.apiKey);
  }
  return url.toString();
}

async function fetchJson(url) {
  let res;
  try {
    res = await fetch(url);
  } catch {
    throw new Error("NETWORK");
  }
  if (!res.ok) {
    if (res.status === 429) throw new Error("RATE_LIMIT");
    let detail = "";
    try {
      const body = await res.json();
      detail = body?.status?.error_message || body?.error || "";
    } catch {
      // response wasn't JSON, ignore
    }
    const err = new Error(`HTTP_${res.status}`);
    err.detail = detail;
    throw err;
  }
  return res.json();
}

function fetchMarkets() {
  const url = buildUrl("/coins/markets", {
    vs_currency: state.settings.vsCurrency,
    ids: FIXED_COINS.join(","),
    order: "market_cap_desc",
    price_change_percentage: "1h,24h,7d",
  });
  return fetchJson(url);
}

function extractSeries(chartResponse) {
  const prices = chartResponse.prices || [];
  const volumesRaw = chartResponse.total_volumes || [];
  const volMap = new Map(volumesRaw.map((v) => [v[0], v[1]]));
  return {
    times: prices.map((p) => p[0]),
    closes: prices.map((p) => p[1]),
    volumes: prices.map((p) => volMap.get(p[0]) || 0),
  };
}

async function fetchDailyHistory(id) {
  const url = buildUrl(`/coins/${id}/market_chart`, { vs_currency: state.settings.vsCurrency, days: "max" });
  return extractSeries(await fetchJson(url));
}

async function fetchHourlyHistory(id) {
  const url = buildUrl(`/coins/${id}/market_chart`, { vs_currency: state.settings.vsCurrency, days: 90 });
  return extractSeries(await fetchJson(url));
}

// ---------- Timeframe resampling ----------
function bucketKey4H(t) { return Math.floor(t / (4 * 3600 * 1000)); }
function bucketKeyWeekly(t) { return Math.floor((t - REF_MONDAY) / (7 * 86400000)); }
function bucketKeyMonthly(t) { const d = new Date(t); return d.getUTCFullYear() * 12 + d.getUTCMonth(); }

function resample(series, bucketFn) {
  const map = new Map();
  for (let i = 0; i < series.times.length; i++) {
    const key = bucketFn(series.times[i]);
    const existing = map.get(key);
    if (!existing) map.set(key, { t: series.times[i], close: series.closes[i], volume: series.volumes[i] || 0 });
    else {
      existing.t = series.times[i];
      existing.close = series.closes[i];
      existing.volume += series.volumes[i] || 0;
    }
  }
  const vals = [...map.values()];
  return { times: vals.map((v) => v.t), closes: vals.map((v) => v.close), volumes: vals.map((v) => v.volume) };
}

function getActiveSeries(id, timeframe) {
  const cache = state.historyCache[id];
  if (timeframe === "4h") return resample(cache.hourly, bucketKey4H);
  if (timeframe === "weekly") return resample(cache.daily, bucketKeyWeekly);
  if (timeframe === "monthly") return resample(cache.daily, bucketKeyMonthly);
  return cache.daily;
}

const TIMEFRAME_LABELS = { "4h": "4 Stunden", daily: "Täglich", weekly: "Wöchentlich", monthly: "Monatlich" };
const TIMEFRAME_UNIT = { "4h": "×4H", daily: "D", weekly: "W", monthly: "M" };

// ---------- Refresh cycle ----------
async function refresh(showSpinner = true) {
  if (showSpinner) {
    els.loading.classList.remove("hidden");
    els.errorBox.classList.add("hidden");
  }
  try {
    const rawCoins = await fetchMarkets();
    rawCoins.sort((a, b) => FIXED_COINS.indexOf(a.id) - FIXED_COINS.indexOf(b.id));

    const histories = await Promise.all(rawCoins.map((c) => fetchDailyHistory(c.id)));
    rawCoins.forEach((c, i) => {
      state.historyCache[c.id] = state.historyCache[c.id] || {};
      state.historyCache[c.id].daily = histories[i];
    });

    state.coins = rawCoins.map((raw, i) => {
      const hist = histories[i];
      const signal = hist.closes.length >= 30
        ? computeSignal({
            closes: hist.closes,
            volumes: hist.volumes,
            changePct24h: raw.price_change_percentage_24h_in_currency,
            changePct7d: raw.price_change_percentage_7d_in_currency,
          })
        : { score: 0, label: "Zu wenig Daten", tone: "hold", reasons: [], lastRsi: null };
      return { raw, signal, fixedIndex: i };
    });

    render();
    els.errorBox.classList.add("hidden");
  } catch (err) {
    showError(err);
  } finally {
    els.loading.classList.add("hidden");
    scheduleNextRefresh();
  }
}

function showError(err) {
  let msg;
  if (err.message === "RATE_LIMIT") {
    msg = "Rate-Limit von CoinGecko erreicht. Warte kurz oder trage unter ⚙ Einstellungen einen kostenlosen CoinGecko-API-Key ein.";
  } else if (err.message === "NETWORK") {
    msg = "Keine Verbindung zu CoinGecko möglich (Netzwerkfehler oder durch den Browser blockiert). Prüfe deine Internetverbindung, Adblocker oder Firewall.";
  } else if (err.message?.startsWith("HTTP_")) {
    const status = err.message.replace("HTTP_", "");
    if (status === "401" || status === "403") {
      msg = `CoinGecko lehnt den Zugriff ab (Fehler ${status}${err.detail ? ": " + err.detail : ""}). `
        + `Prüfe unter ⚙ Einstellungen: 1) ist der Key korrekt eingefügt (keine Leerzeichen)? `
        + `2) passt der eingestellte "Key-Typ" (Demo/Pro) zu der Art Key, die du im CoinGecko-Dashboard erstellt hast? `
        + `Ein "Demo API Key" gehört zu "Demo", ein Key aus einem bezahlten/Trial-Plan zu "Pro".`;
    } else {
      msg = `CoinGecko antwortete mit Fehler ${status}${err.detail ? ": " + err.detail : ""}.`;
    }
  } else {
    msg = "Marktdaten konnten nicht geladen werden. Prüfe deine Internetverbindung und versuche es erneut.";
  }
  els.errorBox.textContent = "⚠ " + msg;
  els.errorBox.classList.remove("hidden");
  if (state.coins.length === 0) els.grid.innerHTML = "";
}

function scheduleNextRefresh() {
  clearTimeout(state.refreshTimer);
  clearInterval(state.countdownTimer);
  const interval = Number(state.settings.refreshInterval);
  if (!interval) {
    els.refreshStatus.textContent = "Auto-Refresh aus";
    return;
  }
  state.nextRefreshAt = Date.now() + interval;
  state.refreshTimer = setTimeout(() => refresh(false), interval);
  state.countdownTimer = setInterval(updateCountdown, 1000);
  updateCountdown();
}

function updateCountdown() {
  const remaining = Math.max(0, Math.round((state.nextRefreshAt - Date.now()) / 1000));
  els.refreshStatus.textContent = `Nächste Aktualisierung in ${remaining}s`;
}

function formatPrice(n, currency) {
  const symbol = currency === "eur" ? "€" : "$";
  if (n >= 1) return symbol + n.toLocaleString("de-DE", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
  return symbol + n.toLocaleString("de-DE", { maximumFractionDigits: 6 });
}

function formatPct(n) {
  if (typeof n !== "number" || Number.isNaN(n)) return "–";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function getFilteredSorted() {
  let list = state.coins;
  if (state.search.trim()) {
    const q = state.search.trim().toLowerCase();
    list = list.filter((c) => c.raw.name.toLowerCase().includes(q) || c.raw.symbol.toLowerCase().includes(q));
  }
  if (state.filter === "buy") list = list.filter((c) => c.signal.tone === "buy" || c.signal.tone === "strong-buy");
  if (state.filter === "sell") list = list.filter((c) => c.signal.tone === "sell" || c.signal.tone === "strong-sell");
  if (state.filter === "watchlist") list = list.filter((c) => state.watchlist.has(c.raw.id));

  const sorted = [...list];
  if (state.sort === "signal") sorted.sort((a, b) => b.signal.score - a.signal.score);
  else if (state.sort === "change24h") sorted.sort((a, b) => (b.raw.price_change_percentage_24h_in_currency ?? -999) - (a.raw.price_change_percentage_24h_in_currency ?? -999));
  else if (state.sort === "rsi") sorted.sort((a, b) => (a.signal.lastRsi ?? 999) - (b.signal.lastRsi ?? 999));
  else sorted.sort((a, b) => a.fixedIndex - b.fixedIndex);
  return sorted;
}

function render() {
  const list = getFilteredSorted();
  if (list.length === 0) {
    els.grid.innerHTML = `<p style="color:var(--text-dim);grid-column:1/-1;text-align:center;padding:30px 0;">Keine Coins gefunden.</p>`;
    return;
  }
  els.grid.innerHTML = list.map(cardHtml).join("");
  els.grid.querySelectorAll(".coin-card").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (e.target.closest(".star-btn")) return;
      openDetail(card.dataset.id);
    });
  });
  els.grid.querySelectorAll(".star-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleWatchlist(btn.dataset.id);
    });
  });
}

function cardHtml(c) {
  const { raw, signal } = c;
  const change24 = raw.price_change_percentage_24h_in_currency;
  const changeClass = change24 > 0 ? "pos" : change24 < 0 ? "neg" : "";
  const starred = state.watchlist.has(raw.id);
  const crossBadge = signal.crossover === "golden" ? "🌟 Golden Cross" : signal.crossover === "death" ? "💀 Death Cross" : "";
  return `
    <div class="coin-card" data-id="${raw.id}">
      <div class="coin-card-top">
        <img src="${raw.image}" alt="" loading="lazy">
        <div>
          <div class="coin-name">${escapeHtml(raw.name)}</div>
          <div class="coin-symbol">${escapeHtml(raw.symbol)}</div>
        </div>
        <button class="star-btn ${starred ? "active" : ""}" data-id="${raw.id}" title="Watchlist">${starred ? "★" : "☆"}</button>
      </div>
      <div class="coin-price-row">
        <span class="coin-price">${formatPrice(raw.current_price, state.settings.vsCurrency)}</span>
        <span class="coin-change ${changeClass}">${formatPct(change24)}</span>
      </div>
      <div class="coin-indicators">
        <span>RSI(14D) <b>${signal.lastRsi != null ? signal.lastRsi.toFixed(0) : "–"}</b></span>
        <span>7d <b class="${raw.price_change_percentage_7d_in_currency > 0 ? "coin-change pos" : "coin-change neg"}">${formatPct(raw.price_change_percentage_7d_in_currency)}</b></span>
      </div>
      ${crossBadge ? `<div class="cross-badge">${crossBadge}</div>` : ""}
      <div class="signal-badge ${signal.tone}">${signal.label}</div>
    </div>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
}

function toggleWatchlist(id) {
  if (state.watchlist.has(id)) state.watchlist.delete(id);
  else state.watchlist.add(id);
  saveWatchlist();
  render();
}

// ---------- Detail view ----------
const charts = { price: null, rsi: null, macd: null, obv: null };

async function openDetail(id) {
  state.detail = { id, timeframe: "daily", ma: { sma20: false, sma50: true, sma200: true } };
  els.detailOverlay.classList.remove("hidden");
  await renderDetailBody();
}

async function setTimeframe(tf) {
  state.detail.timeframe = tf;
  const id = state.detail.id;
  if (tf === "4h" && !state.historyCache[id].hourly) {
    els.detailContent.insertAdjacentHTML("beforeend", `<p id="tf-loading" style="text-align:center;color:var(--text-dim);">Lade 4H-Daten…</p>`);
    try {
      state.historyCache[id].hourly = await fetchHourlyHistory(id);
    } catch (err) {
      document.getElementById("tf-loading")?.remove();
      els.detailContent.insertAdjacentHTML("beforeend", `<p style="color:var(--red);text-align:center;">4H-Daten konnten nicht geladen werden.</p>`);
      return;
    }
  }
  await renderDetailBody();
}

function toggleMa(key) {
  state.detail.ma[key] = !state.detail.ma[key];
  renderDetailBody();
}

async function renderDetailBody() {
  const { id, timeframe, ma } = state.detail;
  const coin = state.coins.find((c) => c.raw.id === id);
  if (!coin) return;

  const series = getActiveSeries(id, timeframe);
  const minPoints = { sma20: 20, sma50: 50, sma200: 200 };
  const signal = series.closes.length >= 30
    ? computeSignal({
        closes: series.closes,
        volumes: series.volumes,
        changePct24h: coin.raw.price_change_percentage_24h_in_currency,
        changePct7d: coin.raw.price_change_percentage_7d_in_currency,
      })
    : null;

  const unit = TIMEFRAME_UNIT[timeframe];
  const { raw } = coin;

  const tfTabs = Object.keys(TIMEFRAME_LABELS).map((tf) => `
    <button class="tf-tab ${tf === timeframe ? "active" : ""}" data-tf="${tf}">${TIMEFRAME_LABELS[tf]}</button>
  `).join("");

  const maToggles = [20, 50, 200].map((p) => {
    const key = `sma${p}`;
    const enoughData = series.closes.length >= minPoints[key];
    return `
      <label class="ma-toggle ${enoughData ? "" : "disabled"}">
        <input type="checkbox" data-ma="${key}" ${ma[key] ? "checked" : ""} ${enoughData ? "" : "disabled"}>
        ${p}${unit} MA
      </label>
    `;
  }).join("");

  if (!signal) {
    els.detailContent.innerHTML = `
      <div class="detail-header">
        <img src="${raw.image}" alt="">
        <div><h2>${escapeHtml(raw.name)}</h2><span class="coin-symbol">${escapeHtml(raw.symbol)}</span></div>
      </div>
      <div class="tf-tabs">${tfTabs}</div>
      <p style="color:var(--text-dim);padding:20px 0;text-align:center;">
        Zu wenig Datenpunkte (${series.closes.length}) für diesen Zeitrahmen, um verlässliche Indikatoren zu berechnen.
      </p>
    `;
    bindDetailControls();
    return;
  }

  const crossText = { golden: "🌟 Golden Cross", death: "💀 Death Cross", above: "SMA50 über SMA200", below: "SMA50 unter SMA200" }[signal.crossover] || "–";

  els.detailContent.innerHTML = `
    <div class="detail-header">
      <img src="${raw.image}" alt="">
      <div>
        <h2>${escapeHtml(raw.name)}</h2>
        <span class="coin-symbol">${escapeHtml(raw.symbol)}</span>
      </div>
    </div>
    <div class="detail-price">${formatPrice(raw.current_price, state.settings.vsCurrency)}
      <span class="coin-change ${raw.price_change_percentage_24h_in_currency > 0 ? "pos" : "neg"}" style="font-size:14px;">
        ${formatPct(raw.price_change_percentage_24h_in_currency)} (24h)
      </span>
    </div>

    <div class="tf-tabs">${tfTabs}</div>

    <div class="signal-badge ${signal.tone}" style="display:inline-block;">${signal.label} (Score ${signal.score})</div>
    <ul class="detail-reasons">${signal.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("") || "<li>Keine starken Signale</li>"}</ul>

    <div class="detail-grid">
      <div class="detail-stat"><span>RSI (14${unit})</span><b>${signal.lastRsi != null ? signal.lastRsi.toFixed(1) : "–"}</b></div>
      <div class="detail-stat"><span>Stochastic RSI %K</span><b>${signal.lastStochK != null ? signal.lastStochK.toFixed(0) : "–"}</b></div>
      <div class="detail-stat"><span>MACD-Histogramm</span><b>${signal.lastHist != null ? signal.lastHist.toFixed(2) : "–"}</b></div>
      <div class="detail-stat"><span>Bollinger %B</span><b>${signal.lastPercentB != null ? (signal.lastPercentB * 100).toFixed(0) + "%" : "–"}</b></div>
      <div class="detail-stat"><span>${20}${unit} MA</span><b>${signal.sma20 != null ? formatPrice(signal.sma20, state.settings.vsCurrency) : "–"}</b></div>
      <div class="detail-stat"><span>${50}${unit} MA</span><b>${signal.sma50 != null ? formatPrice(signal.sma50, state.settings.vsCurrency) : "–"}</b></div>
      <div class="detail-stat"><span>${200}${unit} MA</span><b>${signal.sma200 != null ? formatPrice(signal.sma200, state.settings.vsCurrency) : "–"}</b></div>
      <div class="detail-stat"><span>Trend (50/200)</span><b>${crossText}</b></div>
    </div>

    <div class="ma-toggles">${maToggles}</div>

    <div class="chart-wrap">
      <h3>Kursverlauf (${TIMEFRAME_LABELS[timeframe]})</h3>
      <canvas id="price-chart" height="140"></canvas>
    </div>
    <div class="chart-wrap">
      <h3>RSI (14) &amp; Stochastic RSI</h3>
      <canvas id="rsi-chart" height="80"></canvas>
    </div>
    <div class="chart-wrap">
      <h3>MACD (12, 26, 9)</h3>
      <canvas id="macd-chart" height="80"></canvas>
    </div>
    <div class="chart-wrap">
      <h3>On-Balance Volume</h3>
      <canvas id="obv-chart" height="70"></canvas>
    </div>
  `;

  drawDetailCharts(series, signal, timeframe);
  bindDetailControls();
}

function bindDetailControls() {
  els.detailContent.querySelectorAll(".tf-tab").forEach((btn) => {
    btn.addEventListener("click", () => setTimeframe(btn.dataset.tf));
  });
  els.detailContent.querySelectorAll("[data-ma]").forEach((cb) => {
    cb.addEventListener("change", () => toggleMa(cb.dataset.ma));
  });
}

function formatAxisDate(t, timeframe) {
  const d = new Date(t);
  if (timeframe === "4h") return d.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit" });
  if (timeframe === "monthly") return d.toLocaleDateString("de-DE", { month: "short", year: "2-digit" });
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: timeframe === "weekly" ? "2-digit" : undefined });
}

function drawDetailCharts(series, signal, timeframe) {
  const labels = series.times.map((t) => formatAxisDate(t, timeframe));
  const { ma } = state.detail;
  const { series: s } = signal;

  destroyCharts();

  const priceDatasets = [
    { label: "Preis", data: series.closes, borderColor: "#5b8def", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
  ];
  if (ma.sma20) priceDatasets.push({ label: `SMA20`, data: s.sma20, borderColor: "#f0b429", borderWidth: 1.5, pointRadius: 0, tension: 0.1 });
  if (ma.sma50) priceDatasets.push({ label: `SMA50`, data: s.sma50, borderColor: "#2ecc71", borderWidth: 1.5, pointRadius: 0, tension: 0.1 });
  if (ma.sma200) priceDatasets.push({ label: `SMA200`, data: s.sma200, borderColor: "#ef4655", borderWidth: 1.5, pointRadius: 0, tension: 0.1 });

  charts.price = new Chart(document.getElementById("price-chart"), {
    type: "line",
    data: { labels, datasets: priceDatasets },
    options: chartOptions(),
  });

  charts.rsi = new Chart(document.getElementById("rsi-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "RSI", data: s.rsi, borderColor: "#5b8def", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: "Stoch %K", data: s.stochK, borderColor: "#f0b429", borderWidth: 1, pointRadius: 0, tension: 0.1 },
        { label: "Stoch %D", data: s.stochD, borderColor: "#9aa1b9", borderWidth: 1, pointRadius: 0, tension: 0.1, borderDash: [4, 3] },
      ],
    },
    options: chartOptions({ min: 0, max: 100 }),
  });

  charts.macd = new Chart(document.getElementById("macd-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "MACD", data: s.macdLine, borderColor: "#5b8def", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: "Signal", data: s.signalLine, borderColor: "#f0b429", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: "Histogramm", data: s.histogram, type: "bar", backgroundColor: "rgba(91,141,239,0.3)" },
      ],
    },
    options: chartOptions(),
  });

  charts.obv = new Chart(document.getElementById("obv-chart"), {
    type: "line",
    data: { labels, datasets: [{ label: "OBV", data: s.obv, borderColor: "#f0b429", borderWidth: 1.5, pointRadius: 0, tension: 0.1, fill: true, backgroundColor: "rgba(240,180,41,0.12)" }] },
    options: chartOptions(),
  });
}

function chartOptions(extra = {}) {
  return {
    responsive: true,
    animation: false,
    interaction: { mode: "index", intersect: false },
    scales: {
      x: { ticks: { color: "#9aa1b9", maxTicksLimit: 8 }, grid: { color: "#262d42" } },
      y: { ticks: { color: "#9aa1b9" }, grid: { color: "#262d42" }, min: extra.min, max: extra.max },
    },
    plugins: { legend: { labels: { color: "#eef0f7", boxWidth: 12, font: { size: 11 } } } },
  };
}

function destroyCharts() {
  Object.keys(charts).forEach((k) => {
    charts[k]?.destroy();
    charts[k] = null;
  });
}

els.detailClose.addEventListener("click", () => {
  els.detailOverlay.classList.add("hidden");
  destroyCharts();
});
els.detailOverlay.addEventListener("click", (e) => {
  if (e.target === els.detailOverlay) {
    els.detailOverlay.classList.add("hidden");
    destroyCharts();
  }
});

// ---------- Controls ----------
els.refreshBtn.addEventListener("click", () => refresh(true));

els.settingsBtn.addEventListener("click", () => {
  els.settingsPanel.classList.toggle("hidden");
});

els.vsCurrency.value = state.settings.vsCurrency;
els.refreshInterval.value = state.settings.refreshInterval;
els.apiKey.value = state.settings.apiKey;
els.apiKeyType.value = state.settings.keyType;

els.vsCurrency.addEventListener("change", () => {
  state.settings.vsCurrency = els.vsCurrency.value;
  saveSettings();
  refresh(true);
});
els.refreshInterval.addEventListener("change", () => {
  state.settings.refreshInterval = Number(els.refreshInterval.value);
  saveSettings();
  scheduleNextRefresh();
});
els.apiKey.addEventListener("change", () => {
  state.settings.apiKey = els.apiKey.value.trim();
  saveSettings();
  refresh(true);
});
els.apiKeyType.addEventListener("change", () => {
  state.settings.keyType = els.apiKeyType.value;
  saveSettings();
  refresh(true);
});

els.searchInput.addEventListener("input", () => {
  state.search = els.searchInput.value;
  render();
});
els.sortSelect.addEventListener("change", () => {
  state.sort = els.sortSelect.value;
  render();
});
els.filterBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    els.filterBtns.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.filter = btn.dataset.filter;
    render();
  });
});

refresh(true);
