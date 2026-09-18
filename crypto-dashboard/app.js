const API_BASE = "https://api.coingecko.com/api/v3";

const els = {
  grid: document.getElementById("coin-grid"),
  loading: document.getElementById("loading"),
  errorBox: document.getElementById("error-box"),
  refreshBtn: document.getElementById("refresh-btn"),
  refreshStatus: document.getElementById("refresh-status"),
  settingsBtn: document.getElementById("settings-btn"),
  settingsPanel: document.getElementById("settings-panel"),
  coinCount: document.getElementById("coin-count"),
  vsCurrency: document.getElementById("vs-currency"),
  refreshInterval: document.getElementById("refresh-interval"),
  apiKey: document.getElementById("api-key"),
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
  search: "",
  filter: "all",
  sort: "market_cap",
  refreshTimer: null,
  countdownTimer: null,
  nextRefreshAt: null,
};

function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem("crypto-dashboard-settings") || "{}");
    return {
      coinCount: saved.coinCount || 50,
      vsCurrency: saved.vsCurrency || "usd",
      refreshInterval: saved.refreshInterval ?? 60000,
      apiKey: saved.apiKey || "",
    };
  } catch {
    return { coinCount: 50, vsCurrency: "usd", refreshInterval: 60000, apiKey: "" };
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
  const url = new URL(API_BASE + path);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  if (state.settings.apiKey) url.searchParams.set("x_cg_demo_api_key", state.settings.apiKey);
  return url.toString();
}

async function fetchMarkets() {
  const url = buildUrl("/coins/markets", {
    vs_currency: state.settings.vsCurrency,
    order: "market_cap_desc",
    per_page: state.settings.coinCount,
    page: 1,
    sparkline: "true",
    price_change_percentage: "1h,24h,7d",
  });
  const res = await fetch(url);
  if (!res.ok) {
    if (res.status === 429) throw new Error("RATE_LIMIT");
    throw new Error(`HTTP_${res.status}`);
  }
  return res.json();
}

function processCoins(raw) {
  return raw.map((c) => {
    const closes = (c.sparkline_in_7d?.prices || []).filter((n) => typeof n === "number" && !Number.isNaN(n));
    const signal = closes.length >= 51
      ? computeSignal({
          closes,
          changePct24h: c.price_change_percentage_24h_in_currency,
          changePct7d: c.price_change_percentage_7d_in_currency,
        })
      : { score: 0, label: "Zu wenig Daten", tone: "hold", reasons: [], lastRsi: null };
    return { raw: c, closes, signal };
  });
}

async function refresh(showSpinner = true) {
  if (showSpinner) {
    els.loading.classList.remove("hidden");
    els.errorBox.classList.add("hidden");
  }
  try {
    const raw = await fetchMarkets();
    state.coins = processCoins(raw);
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
    msg = "Rate-Limit von CoinGecko erreicht. Warte kurz, reduziere die Coin-Anzahl oder trage unter ⚙ Einstellungen einen kostenlosen CoinGecko-API-Key ein.";
  } else if (err.message?.startsWith("HTTP_")) {
    msg = `CoinGecko antwortete mit Fehler ${err.message.replace("HTTP_", "")}. Eventuell ist ein API-Key nötig (siehe ⚙ Einstellungen).`;
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
  else sorted.sort((a, b) => a.raw.market_cap_rank - b.raw.market_cap_rank);
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
        <span>RSI(14h) <b>${signal.lastRsi != null ? signal.lastRsi.toFixed(0) : "–"}</b></span>
        <span>7d <b class="${raw.price_change_percentage_7d_in_currency > 0 ? "coin-change pos" : "coin-change neg"}">${formatPct(raw.price_change_percentage_7d_in_currency)}</b></span>
      </div>
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
let detailChart, rsiChart, macdChart;

async function openDetail(id) {
  const coin = state.coins.find((c) => c.raw.id === id);
  if (!coin) return;
  els.detailOverlay.classList.remove("hidden");
  els.detailContent.innerHTML = `<p style="color:var(--text-dim);padding:30px;text-align:center;">Lade Tagesdaten…</p>`;

  try {
    const url = buildUrl(`/coins/${id}/market_chart`, { vs_currency: state.settings.vsCurrency, days: 200 });
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP_${res.status}`);
    const data = await res.json();
    const dailyCloses = data.prices.map((p) => p[1]);
    const dailyDates = data.prices.map((p) => new Date(p[0]));

    const dailySignal = dailyCloses.length >= 51
      ? computeSignal({
          closes: dailyCloses,
          changePct24h: coin.raw.price_change_percentage_24h_in_currency,
          changePct7d: coin.raw.price_change_percentage_7d_in_currency,
        })
      : coin.signal;

    renderDetail(coin, dailyCloses, dailyDates, dailySignal);
  } catch (err) {
    els.detailContent.innerHTML = `<p style="color:var(--red);padding:30px;text-align:center;">
      Tagesdaten konnten nicht geladen werden (${escapeHtml(err.message)}).<br>
      Übersicht basiert weiter auf stündlichen Daten.
    </p>`;
  }
}

function renderDetail(coin, dailyCloses, dailyDates, signal) {
  const { raw } = coin;
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
    <div class="signal-badge ${signal.tone}" style="display:inline-block;">${signal.label} (Score ${signal.score})</div>
    <ul class="detail-reasons">${signal.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("") || "<li>Keine starken Signale</li>"}</ul>
    <div class="detail-grid">
      <div class="detail-stat"><span>RSI (14d)</span><b>${signal.lastRsi != null ? signal.lastRsi.toFixed(1) : "–"}</b></div>
      <div class="detail-stat"><span>SMA 20d</span><b>${signal.sma20 != null ? formatPrice(signal.sma20, state.settings.vsCurrency) : "–"}</b></div>
      <div class="detail-stat"><span>SMA 50d</span><b>${signal.sma50 != null ? formatPrice(signal.sma50, state.settings.vsCurrency) : "–"}</b></div>
      <div class="detail-stat"><span>7 Tage</span><b class="${raw.price_change_percentage_7d_in_currency > 0 ? "coin-change pos" : "coin-change neg"}">${formatPct(raw.price_change_percentage_7d_in_currency)}</b></div>
    </div>
    <div class="chart-wrap">
      <h3>Kursverlauf (200 Tage) mit SMA20 / SMA50</h3>
      <canvas id="price-chart" height="140"></canvas>
    </div>
    <div class="chart-wrap">
      <h3>RSI (14 Tage)</h3>
      <canvas id="rsi-chart" height="80"></canvas>
    </div>
    <div class="chart-wrap">
      <h3>MACD (12, 26, 9)</h3>
      <canvas id="macd-chart" height="80"></canvas>
    </div>
  `;

  const labels = dailyDates.map((d) => d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }));
  const sma20 = calcSMA(dailyCloses, 20);
  const sma50 = calcSMA(dailyCloses, 50);
  const rsi = calcRSI(dailyCloses, 14);
  const { macdLine, signalLine, histogram } = calcMACD(dailyCloses, 12, 26, 9);

  destroyCharts();

  detailChart = new Chart(document.getElementById("price-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Preis", data: dailyCloses, borderColor: "#5b8def", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: "SMA20", data: sma20, borderColor: "#f0b429", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: "SMA50", data: sma50, borderColor: "#ef4655", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
      ],
    },
    options: chartOptions(),
  });

  rsiChart = new Chart(document.getElementById("rsi-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [{ label: "RSI", data: rsi, borderColor: "#5b8def", borderWidth: 1.5, pointRadius: 0, tension: 0.1 }],
    },
    options: chartOptions({ min: 0, max: 100, hLines: [30, 70] }),
  });

  macdChart = new Chart(document.getElementById("macd-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "MACD", data: macdLine, borderColor: "#5b8def", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: "Signal", data: signalLine, borderColor: "#f0b429", borderWidth: 1.5, pointRadius: 0, tension: 0.1 },
        { label: "Histogramm", data: histogram, type: "bar", backgroundColor: "rgba(91,141,239,0.3)" },
      ],
    },
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
      y: {
        ticks: { color: "#9aa1b9" },
        grid: { color: "#262d42" },
        min: extra.min,
        max: extra.max,
      },
    },
    plugins: { legend: { labels: { color: "#eef0f7", boxWidth: 12, font: { size: 11 } } } },
  };
}

function destroyCharts() {
  [detailChart, rsiChart, macdChart].forEach((c) => c && c.destroy());
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

els.coinCount.value = state.settings.coinCount;
els.vsCurrency.value = state.settings.vsCurrency;
els.refreshInterval.value = state.settings.refreshInterval;
els.apiKey.value = state.settings.apiKey;

[els.coinCount, els.vsCurrency].forEach((el) =>
  el.addEventListener("change", () => {
    state.settings.coinCount = Number(els.coinCount.value);
    state.settings.vsCurrency = els.vsCurrency.value;
    saveSettings();
    refresh(true);
  })
);
els.refreshInterval.addEventListener("change", () => {
  state.settings.refreshInterval = Number(els.refreshInterval.value);
  saveSettings();
  scheduleNextRefresh();
});
els.apiKey.addEventListener("change", () => {
  state.settings.apiKey = els.apiKey.value.trim();
  saveSettings();
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
