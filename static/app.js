/* ─────────────────────────────────────────────────────────────────────────────
   StrategyLab — app.js
   Frontend logic: editor, zero-config local data, dual-engine (Pine & Python),
   results visualization, and trade analytics
───────────────────────────────────────────────────────────────────────────── */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  currentLang: 'pine', // 'pine' | 'python'
  jobId: null,
  pollTimer: null,
  result: null,
  allTrades: [],
  equityChart: null,
  datasets: [],
  datasetsBySymbol: {},
  activePreset: 'all',
};

// ── DOM References ────────────────────────────────────────────────────────────
const el = {
  editor:          () => document.getElementById('pineEditor'),
  clearBtn:        () => document.getElementById('clearBtn'),
  loadExampleBtn:  () => document.getElementById('loadExampleBtn'),
  validateBtn:     () => document.getElementById('validateBtn'),
  validateStatus:  () => document.getElementById('validateStatus'),
  tabPine:         () => document.getElementById('tabPine'),
  tabPython:       () => document.getElementById('tabPython'),
  symbolSelect:    () => document.getElementById('symbolSelect'),
  interval:        () => document.getElementById('interval'),
  startDate:       () => document.getElementById('startDate'),
  endDate:         () => document.getElementById('endDate'),
  barsCount:       () => document.getElementById('barsCount'),
  dateBounds:      () => document.getElementById('dateBounds'),
  presetGroup:     () => document.getElementById('presetGroup'),
  runBtn:          () => document.getElementById('runBtn'),

  progressOverlay: () => document.getElementById('progressOverlay'),
  progressTitle:   () => document.getElementById('progressTitle'),
  progressSub:     () => document.getElementById('progressSub'),
  progressBar:     () => document.getElementById('progressBar'),
  progressPct:     () => document.getElementById('progressPct'),

  resultsSection:  () => document.getElementById('results-section'),
  reportMeta:      () => document.getElementById('reportMeta'),
  metricsGrid:     () => document.getElementById('metricsGrid'),
  equityChart:     () => document.getElementById('equityChart'),
  equitySub:       () => document.getElementById('equitySub'),
  returnTable:     () => document.getElementById('returnTable'),
  riskTable:       () => document.getElementById('riskTable'),
  tradeTable:      () => document.getElementById('tradeTable'),
  downloadBtn:     () => document.getElementById('downloadBtn'),

  tradesSection:   () => document.getElementById('trades-section'),
  tradesMeta:      () => document.getElementById('tradesMeta'),
  tradesBody:      () => document.getElementById('tradesBody'),

  navResults:      () => document.getElementById('nav-results'),
  navTrades:       () => document.getElementById('nav-trades'),
};

// ── Example Strategies ────────────────────────────────────────────────────────
const EXAMPLE_PINE = `//@version=5
strategy("EMA + RSI Momentum", overlay=true, initial_capital=10000, commission_value=0.1, default_qty_type=strategy.percent_of_equity, default_qty_value=100)

// ── Inputs
fastLen  = input.int(9,  title="Fast EMA Length", minval=1)
slowLen  = input.int(21, title="Slow EMA Length", minval=1)
rsiLen   = input.int(14, title="RSI Length",      minval=1)
rsiOB    = input.int(65, title="RSI Overbought",  minval=50)
rsiOS    = input.int(35, title="RSI Oversold",    maxval=50)

// ── Indicators
fastEMA = ta.ema(close, fastLen)
slowEMA = ta.ema(close, slowLen)
rsiVal  = ta.rsi(close, rsiLen)

// ── Signals
longCondition  = ta.crossover(fastEMA, slowEMA) and rsiVal < rsiOB
shortCondition = ta.crossunder(fastEMA, slowEMA) or rsiVal > rsiOB

// ── Execution
if longCondition
    strategy.entry("Long", strategy.long)

if shortCondition
    strategy.close("Long")

// ── Plots
plot(fastEMA, color=color.new(color.blue, 0),   title="Fast EMA")
plot(slowEMA, color=color.new(color.orange, 0), title="Slow EMA")
`;

const EXAMPLE_PYTHON = `# StrategyLab Python Strategy
# The 'df' DataFrame contains: open, high, low, close, volume

import numpy as np
import pandas as pd

def strategy(df: pd.DataFrame):
    """
    Generate boolean Series: (entries, exits)
    """
    # 1. Calculate indicators
    fast_ema = df['close'].ewm(span=9, adjust=False).mean()
    slow_ema = df['close'].ewm(span=21, adjust=False).mean()
    
    # RSI (14)
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(window=14).mean()
    loss = (-delta.clip(upper=0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    # 2. Entry & Exit signals
    entries = (fast_ema > slow_ema) & (fast_ema.shift(1) <= slow_ema.shift(1)) & (rsi < 65)
    exits   = (fast_ema < slow_ema) | (rsi > 70)
    
    return entries, exits
`;

// ── Toast Notifications ───────────────────────────────────────────────────────
function showToast(msg, type = 'info', duration = 4000) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    container.setAttribute('aria-live', 'polite');
    document.body.appendChild(container);
  }
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.setAttribute('role', 'status');

  const icons = {
    success: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6L9 17l-5-5"/></svg>`,
    error: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    info: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`
  };

  t.innerHTML = `${icons[type] || icons.info}<span>${msg}</span>`;
  container.appendChild(t);
  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transform = 'translateY(12px) scale(0.96)';
    t.style.transition = 'all 0.25s var(--ease)';
    setTimeout(() => t.remove(), 260);
  }, duration);
}

// ── Format helpers ────────────────────────────────────────────────────────────
function fmt(val, decimals = 2) {
  if (val === null || val === undefined || val === '') return '—';
  const n = parseFloat(val);
  if (isNaN(n)) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtPct(val) { return fmt(val, 2) + '%'; }
function fmtCur(val, cur = 'USD') { return `${cur} ${fmt(val, 2)}`; }

function colorClass(val) {
  if (val > 0) return 'pos';
  if (val < 0) return 'neg';
  return '';
}

// ── Load Available Local Datasets ─────────────────────────────────────────────
async function loadAvailableDatasets() {
  try {
    const resp = await fetch('/api/datasets');
    if (!resp.ok) return;
    const data = await resp.json();
    state.datasets = data.datasets || [];
    state.datasetsBySymbol = data.by_symbol || {};

    onSymbolChange();
  } catch (err) {
    console.warn('Could not load dataset metadata:', err);
  }
}

const ALL_INTERVAL_GROUPS = [
  {
    group: 'Higher Timeframes',
    options: [
      { value: '1w', label: 'Weekly (1W)' },
      { value: '1d', label: 'Daily (1D)' },
    ]
  },
  {
    group: 'Hourly Timeframes',
    options: [
      { value: '4h', label: '4 Hours (4H)' },
      { value: '2h', label: '2 Hours (2H)' },
      { value: '1h', label: '1 Hour (1H)' },
    ]
  },
  {
    group: 'Minute Timeframes',
    options: [
      { value: '30m', label: '30 Minutes (30m)' },
      { value: '15m', label: '15 Minutes (15m)' },
      { value: '5m',  label: '5 Minutes (5m)' },
      { value: '1m',  label: '1 Minute (1m)' },
    ]
  }
];

function onSymbolChange() {
  const sym = el.symbolSelect().value;
  const intervalSelect = el.interval();
  const currentVal = intervalSelect.value || '1d';
  intervalSelect.innerHTML = '';

  ALL_INTERVAL_GROUPS.forEach(grp => {
    const optgroup = document.createElement('optgroup');
    optgroup.label = grp.group;
    grp.options.forEach(optData => {
      const opt = document.createElement('option');
      opt.value = optData.value;
      opt.textContent = optData.label;
      if (optData.value === currentVal) opt.selected = true;
      optgroup.appendChild(opt);
    });
    intervalSelect.appendChild(optgroup);
  });

  if (!intervalSelect.value) {
    intervalSelect.value = '1d';
  }

  updateIntervalMeta();
}

function updateIntervalMeta() {
  const sym = el.symbolSelect().value;
  const inv = el.interval().value;

  const match = state.datasets.find(d => d.symbol === sym && d.interval === inv);
  const symMeta = state.datasetsBySymbol[sym];

  if (match) {
    if (el.barsCount()) el.barsCount().textContent = `${match.bars.toLocaleString()} Bars`;
    if (el.dateBounds()) el.dateBounds().textContent = `${match.start} → ${match.end}`;
    applyDatePreset(state.activePreset, match.start, match.end);
  } else if (symMeta) {
    if (el.barsCount()) el.barsCount().textContent = `Data Ready (${inv.toUpperCase()})`;
    if (el.dateBounds()) el.dateBounds().textContent = `${symMeta.start} → ${symMeta.end}`;
    applyDatePreset(state.activePreset, symMeta.start, symMeta.end);
  }
}

function applyDatePreset(preset, datasetStart, datasetEnd) {
  state.activePreset = preset;
  if (!datasetStart || !datasetEnd) return;

  const endDt = new Date(datasetEnd);
  el.endDate().value = datasetEnd;

  if (preset === '1y') {
    const startDt = new Date(endDt);
    startDt.setFullYear(startDt.getFullYear() - 1);
    const startStr = startDt.toISOString().split('T')[0];
    el.startDate().value = startStr > datasetStart ? startStr : datasetStart;
  } else if (preset === '2y') {
    const startDt = new Date(endDt);
    startDt.setFullYear(startDt.getFullYear() - 2);
    const startStr = startDt.toISOString().split('T')[0];
    el.startDate().value = startStr > datasetStart ? startStr : datasetStart;
  } else {
    // Max / All
    el.startDate().value = datasetStart;
  }
}

// ── Switch Language (Pine / Python) ───────────────────────────────────────────
function switchLanguage(lang) {
  state.currentLang = lang;
  if (lang === 'python') {
    el.tabPython().classList.add('active');
    el.tabPython().setAttribute('aria-selected', 'true');
    el.tabPine().classList.remove('active');
    el.tabPine().setAttribute('aria-selected', 'false');
    el.editor().placeholder = `# Python Strategy\nimport pandas as pd\n\ndef strategy(df: pd.DataFrame):\n    # Calculate signals\n    return entries, exits`;
    if (!el.editor().value.trim() || el.editor().value === EXAMPLE_PINE) {
      el.editor().value = EXAMPLE_PYTHON;
    }
  } else {
    el.tabPine().classList.add('active');
    el.tabPine().setAttribute('aria-selected', 'true');
    el.tabPython().classList.remove('active');
    el.tabPython().setAttribute('aria-selected', 'false');
    el.editor().placeholder = `//@version=5\nstrategy("My Strategy", overlay=true)\n\n// Paste your Pine Script strategy here...`;
    if (!el.editor().value.trim() || el.editor().value === EXAMPLE_PYTHON) {
      el.editor().value = EXAMPLE_PINE;
    }
  }
  el.validateStatus().textContent = '';
  el.validateStatus().className = 'validate-status';
}

// ── Validate Strategy ─────────────────────────────────────────────────────────
async function validateStrategy() {
  const code = el.editor().value.trim();
  if (!code) { showToast('Please enter your strategy code first.', 'error'); return; }
  const statusEl = el.validateStatus();
  statusEl.textContent = 'Validating…';
  statusEl.className = 'validate-status info';
  try {
    const resp = await fetch('/api/validate-strategy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, lang: state.currentLang }),
    });
    const data = await resp.json();
    if (data.valid) {
      statusEl.textContent = `✓ ${data.message}  ·  Type: ${data.strategy_type}`;
      statusEl.className = 'validate-status valid';
    } else {
      statusEl.textContent = `✗ ${data.message}`;
      statusEl.className = 'validate-status error';
    }
  } catch (e) {
    statusEl.textContent = 'Connection error — make sure the server is running.';
    statusEl.className = 'validate-status error';
  }
}

// ── Run Backtest ──────────────────────────────────────────────────────────────
async function runBacktest() {
  const code = el.editor().value.trim();
  if (!code) { showToast('Please paste or write your strategy first.', 'error'); return; }

  const payload = {
    strategy_code: code,
    lang:          state.currentLang,
    symbol:        el.symbolSelect().value.trim(),
    interval:      el.interval().value,
    start:         el.startDate().value,
    end:           el.endDate().value,
  };

  if (!payload.symbol) { showToast('Please select a market asset.', 'error'); return; }

  // Show progress
  el.runBtn().disabled = true;
  showProgress(0, 'Initializing Backtest…', `Loading pre-downloaded market data for ${payload.symbol}…`);

  try {
    const resp = await fetch('/api/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) {
      hideProgress();
      el.runBtn().disabled = false;
      showToast(data.error || 'Backtest failed to start.', 'error', 6000);
      return;
    }
    state.jobId = data.job_id;
    pollStatus(payload);
  } catch (e) {
    hideProgress();
    el.runBtn().disabled = false;
    showToast('Could not connect to the server. Is it running?', 'error');
  }
}

// ── Poll Status ───────────────────────────────────────────────────────────────
function pollStatus(payload) {
  if (state.pollTimer) clearInterval(state.pollTimer);

  const LABELS = {
    queued:   ['In Queue',          'Your backtest is queued…'],
    fetching: ['Loading Market Data', `Reading candles for ${payload.symbol} (${payload.interval}) from disk…`],
    running:  ['Testing Strategy',  'Checking buy and sell conditions on each candle…'],
    done:     ['Complete',          'Backtest finished.'],
    error:    ['Error',             ''],
  };

  state.pollTimer = setInterval(async () => {
    try {
      const resp = await fetch(`/api/status/${state.jobId}`);
      const data = await resp.json();

      const [title, sub] = LABELS[data.status] || ['Processing…', ''];
      showProgress(data.progress || 0, title, sub);

      if (data.status === 'done') {
        clearInterval(state.pollTimer);
        hideProgress();
        el.runBtn().disabled = false;
        renderResults(data.result, payload);
        showToast('Backtest completed successfully!', 'success');
      } else if (data.status === 'error') {
        clearInterval(state.pollTimer);
        hideProgress();
        el.runBtn().disabled = false;
        showToast(data.error || 'Backtest failed.', 'error', 8000);
      }
    } catch (e) {
      // network hiccup — keep polling
    }
  }, 400);
}

// ── Progress helpers ──────────────────────────────────────────────────────────
function showProgress(pct, title, sub) {
  el.progressOverlay().style.display = '';
  el.progressTitle().textContent  = title;
  el.progressSub().textContent    = sub;
  el.progressBar().style.width    = pct + '%';
  el.progressPct().textContent    = pct + '%';
}
function hideProgress() { el.progressOverlay().style.display = 'none'; }

// ── Render Results ────────────────────────────────────────────────────
function renderResults(result, payload) {
  const m = result.metrics;
  state.result = result;
  state.allTrades = result.trades || [];

  const langTag = payload.lang === 'python' ? 'Python Strategy' : 'Pine Script';

  // ── Meta description
  el.reportMeta().textContent =
    `${m.strategy_name}  ·  ${payload.symbol.toUpperCase()}  ·  ${payload.interval.toUpperCase()}  ·  ${payload.start} to ${payload.end}  ·  ${langTag}`;

  // ── Metric cards
  const cards = [
    { label: 'Total Net Profit',  value: fmtCur(m.total_net_profit, m.currency),  sub: fmtPct(m.total_net_profit_pct),       positive: m.total_net_profit > 0, negative: m.total_net_profit < 0 },
    { label: 'Win Rate',          value: fmtPct(m.win_rate_pct),                  sub: `${m.winning_trades}W / ${m.losing_trades}L`, positive: m.win_rate_pct >= 50, negative: m.win_rate_pct < 40 },
    { label: 'Total Trades',      value: m.total_trades,                          sub: 'closed trades' },
    { label: 'Profit Factor',     value: fmt(m.profit_factor, 3),                 sub: 'gross profit / loss', positive: m.profit_factor >= 1.5, negative: m.profit_factor < 1 },
    { label: 'Max Drawdown',      value: fmtPct(m.max_drawdown_pct),              sub: 'peak-to-trough drop', negative: true },
    { label: 'Sharpe Ratio',      value: fmt(m.sharpe_ratio, 3),                  sub: 'risk-adjusted score', positive: m.sharpe_ratio >= 1, negative: m.sharpe_ratio < 0 },
    { label: 'Ending Balance',    value: fmtCur(m.final_equity, m.currency),      sub: `started with ${fmtCur(m.initial_capital, m.currency)}` },
    { label: 'vs Buy & Hold',     value: fmtPct(m.alpha_vs_buy_hold_pct),         sub: `B&H: ${fmtPct(m.buy_and_hold_return_pct)}`, positive: m.alpha_vs_buy_hold_pct > 0, negative: m.alpha_vs_buy_hold_pct < 0 },
  ];

  const grid = el.metricsGrid();
  grid.innerHTML = '';
  cards.forEach(c => {
    const div = document.createElement('div');
    div.className = 'metric-card' + (c.positive ? ' positive' : c.negative ? ' negative' : '');
    div.innerHTML = `
      <div class="metric-label">${c.label}</div>
      <div class="metric-value ${c.positive ? 'positive' : c.negative ? 'negative' : ''}">${c.value}</div>
      ${c.sub ? `<div class="metric-sub">${c.sub}</div>` : ''}
    `;
    grid.appendChild(div);
  });

  // ── Equity curve chart
  renderEquityChart(result.equity_curve, m);

  // ── Stat tables
  renderStatTable(el.returnTable(), [
    ['Total Net Profit',        m.currency + ' ' + fmt(m.total_net_profit),    colorClass(m.total_net_profit)],
    ['Total Net Profit %',      fmtPct(m.total_net_profit_pct),                colorClass(m.total_net_profit_pct)],
    ['Gross Profit',            m.currency + ' ' + fmt(m.gross_profit),        'pos'],
    ['Gross Loss',              m.currency + ' ' + fmt(m.gross_loss),          'neg'],
    ['Commission Paid',         m.currency + ' ' + fmt(m.commission_paid),     'neg'],
    ['Buy & Hold Return',       fmtPct(m.buy_and_hold_return_pct),             colorClass(m.buy_and_hold_return_pct)],
    ['Strategy vs Buy & Hold',  fmtPct(m.alpha_vs_buy_hold_pct),              colorClass(m.alpha_vs_buy_hold_pct)],
  ]);

  renderStatTable(el.riskTable(), [
    ['Max Drawdown',            fmtPct(m.max_drawdown_pct),   'neg'],
    ['Sharpe Ratio',            fmt(m.sharpe_ratio, 3),       colorClass(m.sharpe_ratio)],
    ['Sortino Ratio',           fmt(m.sortino_ratio, 3),      colorClass(m.sortino_ratio)],
    ['Calmar Ratio',            fmt(m.calmar_ratio, 3),       colorClass(m.calmar_ratio)],
    ['Profit Factor',           fmt(m.profit_factor, 3),      colorClass(m.profit_factor - 1)],
  ]);

  renderStatTable(el.tradeTable(), [
    ['Total Trades',            m.total_trades,               ''],
    ['Winning Trades',          m.winning_trades,             'pos'],
    ['Losing Trades',           m.losing_trades,              'neg'],
    ['Win Rate',                fmtPct(m.win_rate_pct),       colorClass(m.win_rate_pct - 50)],
    ['Avg Trade P&L',           m.currency + ' ' + fmt(m.avg_trade_pnl), colorClass(m.avg_trade_pnl)],
    ['Avg Win',                 m.currency + ' ' + fmt(m.avg_winning_trade), 'pos'],
    ['Avg Loss',                m.currency + ' ' + fmt(m.avg_losing_trade),  'neg'],
    ['Largest Win',             m.currency + ' ' + fmt(m.largest_winning_trade), 'pos'],
    ['Largest Loss',            m.currency + ' ' + fmt(m.largest_losing_trade),  'neg'],
    ['Max Consec. Wins',        m.max_consecutive_wins,       'pos'],
    ['Max Consec. Losses',      m.max_consecutive_losses,     'neg'],
    ['Avg Duration (bars)',     fmt(m.avg_trade_duration_bars, 1), ''],
  ]);

  // ── Show sections
  el.resultsSection().style.display = '';
  el.navResults().classList.add('active');
  el.resultsSection().scrollIntoView({ behavior: 'smooth', block: 'start' });

  // ── Trades
  renderTrades(state.allTrades);
  el.tradesMeta().textContent = `${state.allTrades.length} closed trades — showing all`;
  el.tradesSection().style.display = '';
  el.navTrades().classList.add('active');

  // ── Download button
  el.downloadBtn().onclick = () => downloadCSV();
}

function renderStatTable(tableEl, rows) {
  tableEl.innerHTML = '';
  rows.forEach(([label, value, cls]) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${label}</td><td class="${cls}">${value}</td>`;
    tableEl.appendChild(tr);
  });
}

// ── Equity Chart ──────────────────────────────────────────────────────────────
function renderEquityChart(equityCurve, metrics) {
  if (state.equityChart) { state.equityChart.destroy(); state.equityChart = null; }
  if (!equityCurve || !equityCurve.length) {
    el.equitySub().textContent = 'No equity data available.';
    return;
  }

  const labels = equityCurve.map(p => {
    const d = new Date(p.date);
    return isNaN(d) ? p.date : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
  });
  const values = equityCurve.map(p => p.equity);
  const isProfit = values[values.length - 1] >= values[0];
  const mainColor = isProfit ? '#99b898' : '#e84a5f';

  el.equitySub().textContent =
    `${metrics.currency} ${fmt(metrics.initial_capital)} → ${metrics.currency} ${fmt(metrics.final_equity)}`;

  const ctx = el.equityChart().getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 300);
  if (isProfit) {
    gradient.addColorStop(0, 'rgba(153, 184, 152, 0.32)');
    gradient.addColorStop(0.7, 'rgba(153, 184, 152, 0.06)');
    gradient.addColorStop(1, 'rgba(153, 184, 152, 0.00)');
  } else {
    gradient.addColorStop(0, 'rgba(232, 74, 95, 0.32)');
    gradient.addColorStop(0.7, 'rgba(232, 74, 95, 0.06)');
    gradient.addColorStop(1, 'rgba(232, 74, 95, 0.00)');
  }

  state.equityChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Portfolio Equity',
        data: values,
        borderColor: mainColor,
        backgroundColor: gradient,
        borderWidth: 2.2,
        fill: true,
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 6,
        pointHoverBackgroundColor: mainColor,
        pointHoverBorderColor: '#ffffff',
        pointHoverBorderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1b2327',
          borderColor: 'rgba(254, 206, 168, 0.25)',
          borderWidth: 1,
          titleColor: '#fecea8',
          titleFont: { family: 'Plus Jakarta Sans', size: 12, weight: '600' },
          bodyColor: '#ffffff',
          bodyFont: { family: 'JetBrains Mono', size: 13, weight: '600' },
          padding: 12,
          boxPadding: 4,
          usePointStyle: true,
          callbacks: {
            label: ctx => ` ${metrics.currency} ${fmt(ctx.raw)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: {
            color: '#6e8088',
            font: { family: 'JetBrains Mono', size: 11 },
            maxTicksLimit: 8,
            maxRotation: 0,
          },
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: {
            color: '#6e8088',
            font: { family: 'JetBrains Mono', size: 11 },
            callback: val => `${metrics.currency} ${fmt(val, 0)}`,
          },
        },
      },
    },
  });
}

// ── Render Trades Table ───────────────────────────────────────────────────────
function renderTrades(trades) {
  const tbody = el.tradesBody();
  tbody.innerHTML = '';
  trades.forEach((t, i) => {
    const isWin = t.result === 'Win';
    const row = document.createElement('tr');
    row.dataset.result = isWin ? 'win' : 'loss';
    row.innerHTML = `
      <td>${i + 1}</td>
      <td>${formatDate(t.entry_date)}</td>
      <td>${formatDate(t.exit_date)}</td>
      <td>${fmt(t.entry_price, 4)}</td>
      <td>${fmt(t.exit_price, 4)}</td>
      <td class="${isWin ? 'pos' : 'neg'}" style="color:${isWin?'#99b898':'#e84a5f'}">${t.pnl >= 0 ? '+' : ''}${fmt(t.pnl, 4)}</td>
      <td class="${isWin ? 'pos' : 'neg'}" style="color:${isWin?'#99b898':'#e84a5f'}">${t.pnl_pct >= 0 ? '+' : ''}${fmt(t.pnl_pct, 2)}%</td>
      <td><span class="${isWin ? 'badge-win' : 'badge-loss'}">${t.result}</span></td>
    `;
    tbody.appendChild(row);
  });
}

function formatDate(str) {
  if (!str) return '—';
  const d = new Date(str);
  if (isNaN(d)) return str;
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

// ── Filter Trades ─────────────────────────────────────────────────────────────
document.addEventListener('click', e => {
  const btn = e.target.closest('.filter-btn');
  if (!btn) return;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const filter = btn.dataset.filter;
  const filtered = filter === 'all' ? state.allTrades
    : state.allTrades.filter(t => (filter === 'win' ? t.result === 'Win' : t.result !== 'Win'));
  renderTrades(filtered);
  el.tradesMeta().textContent = `${filtered.length} of ${state.allTrades.length} trades`;
});

// ── Download CSV ──────────────────────────────────────────────────────────────
async function downloadCSV() {
  if (!state.jobId) { showToast('No completed backtest found.', 'error'); return; }
  try {
    const resp = await fetch(`/api/download-csv/${state.jobId}`);
    if (!resp.ok) { showToast('CSV not available yet.', 'error'); return; }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backtest_report_${state.jobId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('CSV report downloaded successfully.', 'success');
  } catch (e) {
    showToast('Download failed.', 'error');
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
function init() {
  // Load example
  el.loadExampleBtn().addEventListener('click', () => {
    if (state.currentLang === 'python') {
      el.editor().value = EXAMPLE_PYTHON;
    } else {
      el.editor().value = EXAMPLE_PINE;
    }
    el.validateStatus().textContent = '';
    showToast(`Example ${state.currentLang === 'python' ? 'Python' : 'Pine Script'} strategy loaded.`, 'info');
  });

  // Clear
  el.clearBtn().addEventListener('click', () => {
    el.editor().value = '';
    el.validateStatus().textContent = '';
    el.validateStatus().className = 'validate-status';
  });

  // Language Tabs
  if (el.tabPine()) el.tabPine().addEventListener('click', () => switchLanguage('pine'));
  if (el.tabPython()) el.tabPython().addEventListener('click', () => switchLanguage('python'));

  // Validate
  el.validateBtn().addEventListener('click', validateStrategy);

  // Asset / Interval changes
  el.symbolSelect().addEventListener('change', onSymbolChange);
  el.interval().addEventListener('change', updateIntervalMeta);

  // Period Presets
  const presetBtns = document.querySelectorAll('.preset-btn');
  presetBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      presetBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const preset = btn.dataset.preset;
      const sym = el.symbolSelect().value;
      const inv = el.interval().value;
      const match = state.datasets.find(d => d.symbol === sym && d.interval === inv);
      const symMeta = state.datasetsBySymbol[sym];
      const start = match ? match.start : (symMeta ? symMeta.start : null);
      const end = match ? match.end : (symMeta ? symMeta.end : null);
      if (start && end) {
        applyDatePreset(preset, start, end);
      }
    });
  });

  // Run
  el.runBtn().addEventListener('click', runBacktest);

  // Nav smooth scroll
  document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', e => {
      const href = link.getAttribute('href');
      if (href && href.startsWith('#')) {
        e.preventDefault();
        const target = document.querySelector(href);
        if (target) target.scrollIntoView({ behavior: 'smooth' });
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
      }
    });
  });

  // Initial load
  loadAvailableDatasets();
  switchLanguage('pine');
}

document.addEventListener('DOMContentLoaded', init);
