/* ─────────────────────────────────────────────────────────────────────────────
   StrategyLab — app.js
   Frontend logic: editor, API calls, chart rendering, results display
───────────────────────────────────────────────────────────────────────────── */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  jobId: null,
  pollTimer: null,
  result: null,
  trades: [],
  allTrades: [],
  equityChart: null,
};

// ── DOM References ────────────────────────────────────────────────────────────
const el = {
  editor:          () => document.getElementById('pineEditor'),
  clearBtn:        () => document.getElementById('clearBtn'),
  loadExampleBtn:  () => document.getElementById('loadExampleBtn'),
  validateBtn:     () => document.getElementById('validateBtn'),
  validateStatus:  () => document.getElementById('validateStatus'),
  dataSource:      () => document.getElementById('dataSource'),
  symbol:          () => document.getElementById('symbol'),
  symbolHint:      () => document.getElementById('symbolHint'),
  symbolSuggestions: () => document.getElementById('symbolSuggestions'),
  interval:        () => document.getElementById('interval'),
  startDate:       () => document.getElementById('startDate'),
  endDate:         () => document.getElementById('endDate'),
  avKeyGroup:      () => document.getElementById('avKeyGroup'),
  avKey:           () => document.getElementById('avKey'),
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

// ── Example Pine Script ───────────────────────────────────────────────────────
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

// ── Data Source → Symbol hints ─────────────────────────────────────────────
const SOURCE_HINTS = {
  yahoo:        { hint: 'e.g. AAPL, BTC-USD, SPY, ETH-USD',  default: 'AAPL' },
  binance:      { hint: 'e.g. BTCUSDT, ETHUSDT, SOLUSDT',    default: 'BTCUSDT' },
  coingecko:    { hint: 'e.g. bitcoin, ethereum, solana',     default: 'bitcoin' },
  alphavantage: { hint: 'e.g. IBM, AAPL (demo key = IBM)',    default: 'IBM' },
};

const SOURCE_SYMBOLS = {
  yahoo:        ['AAPL', 'MSFT', 'BTC-USD', 'ETH-USD', 'SPY', 'TSLA', 'NVDA'],
  binance:      ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT', 'XRPUSDT'],
  coingecko:    ['bitcoin', 'ethereum', 'solana', 'cardano', 'dogecoin'],
  alphavantage: ['IBM', 'AAPL', 'MSFT'],
};

const SOURCE_INTERVALS = {
  yahoo:        ['1m','5m','15m','30m','1h','4h','1d','1w','1M'],
  binance:      ['1m','5m','15m','30m','1h','4h','1d','1w'],
  coingecko:    ['1d'],
  alphavantage: ['1d'],
};

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'info', duration = 4000) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; setTimeout(() => t.remove(), 350); }, duration);
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

// ── Source change ─────────────────────────────────────────────────────────────
function onSourceChange() {
  const src = el.dataSource().value;
  const { hint, default: def } = SOURCE_HINTS[src] || {};
  if (hint) { el.symbolHint().textContent = hint; }
  if (def)  { el.symbol().value = def; el.symbol().placeholder = def; }

  // Interval options
  const validIntervals = SOURCE_INTERVALS[src] || ['1d'];
  const selInt = el.interval();
  Array.from(selInt.options).forEach(opt => {
    opt.disabled = !validIntervals.includes(opt.value);
  });
  if (!validIntervals.includes(selInt.value)) {
    selInt.value = '1d';
  }

  // Alpha Vantage key
  el.avKeyGroup().style.display = src === 'alphavantage' ? '' : 'none';

  // Symbol suggestions
  const syms = SOURCE_SYMBOLS[src] || [];
  const sug = el.symbolSuggestions();
  sug.innerHTML = '';
  syms.forEach(s => {
    const chip = document.createElement('span');
    chip.className = 'symbol-chip';
    chip.textContent = s;
    chip.addEventListener('click', () => { el.symbol().value = s; });
    sug.appendChild(chip);
  });
}

// ── Validate Pine Script ──────────────────────────────────────────────────────
async function validatePine() {
  const code = el.editor().value.trim();
  if (!code) { showToast('Please paste your Pine Script code first.', 'error'); return; }
  const statusEl = el.validateStatus();
  statusEl.textContent = 'Validating…';
  statusEl.className = 'validate-status info';
  try {
    const resp = await fetch('/api/validate-pine', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
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
  if (!code) { showToast('Paste your Pine Script strategy first.', 'error'); return; }

  const payload = {
    pine_code:  code,
    source:     el.dataSource().value,
    symbol:     el.symbol().value.trim(),
    interval:   el.interval().value,
    start:      el.startDate().value,
    end:        el.endDate().value,
    av_api_key: el.avKey().value.trim(),
  };

  if (!payload.symbol) { showToast('Please enter a symbol (e.g. AAPL, BTCUSDT).', 'error'); return; }

  // Show progress
  el.runBtn().disabled = true;
  showProgress(0, 'Starting backtest…', 'Sending your strategy to the analysis engine…');

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
      showToast(data.error || 'Request failed.', 'error', 6000);
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
    queued:   ['In Queue',          'Your backtest is queued and will start shortly…'],
    fetching: ['Fetching Market Data', `Downloading historical data from ${payload.source}…`],
    running:  ['Running Backtest',  'Calculating signals and simulating all trades…'],
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
        showToast('Backtest completed successfully.', 'success');
      } else if (data.status === 'error') {
        clearInterval(state.pollTimer);
        hideProgress();
        el.runBtn().disabled = false;
        showToast(data.error || 'Backtest failed.', 'error', 8000);
      }
    } catch (e) {
      // network hiccup — keep polling
    }
  }, 900);
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

// ── Render Results ────────────────────────────────────────────────────────────
function renderResults(result, payload) {
  const m = result.metrics;
  state.result = result;
  state.allTrades = result.trades || [];

  // ── Meta description
  el.reportMeta().textContent =
    `${m.strategy_name}  ·  ${payload.symbol.toUpperCase()}  ·  ${payload.interval}  ·  ${payload.start} – ${payload.end}  ·  ${payload.source.charAt(0).toUpperCase()+payload.source.slice(1)}`;

  // ── Metric cards
  const cards = [
    { label: 'Total Net Profit',  value: fmtCur(m.total_net_profit, m.currency),  sub: fmtPct(m.total_net_profit_pct),       positive: m.total_net_profit > 0, negative: m.total_net_profit < 0 },
    { label: 'Win Rate',          value: fmtPct(m.win_rate_pct),                  sub: `${m.winning_trades}W / ${m.losing_trades}L`, positive: m.win_rate_pct >= 50, negative: m.win_rate_pct < 40 },
    { label: 'Total Trades',      value: m.total_trades,                          sub: 'closed positions' },
    { label: 'Profit Factor',     value: fmt(m.profit_factor, 3),                 sub: 'gross profit / loss', positive: m.profit_factor >= 1.5, negative: m.profit_factor < 1 },
    { label: 'Max Drawdown',      value: fmtPct(m.max_drawdown_pct),              sub: 'peak-to-trough', negative: true },
    { label: 'Sharpe Ratio',      value: fmt(m.sharpe_ratio, 3),                  sub: 'risk-adjusted return', positive: m.sharpe_ratio >= 1, negative: m.sharpe_ratio < 0 },
    { label: 'Final Equity',      value: fmtCur(m.final_equity, m.currency),      sub: `started with ${fmtCur(m.initial_capital, m.currency)}` },
    { label: 'Alpha vs Buy&Hold', value: fmtPct(m.alpha_vs_buy_hold_pct),         sub: `B&H: ${fmtPct(m.buy_and_hold_return_pct)}`, positive: m.alpha_vs_buy_hold_pct > 0, negative: m.alpha_vs_buy_hold_pct < 0 },
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
    ['Alpha vs Buy & Hold',     fmtPct(m.alpha_vs_buy_hold_pct),              colorClass(m.alpha_vs_buy_hold_pct)],
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
  const mainColor = isProfit ? '#22c55e' : '#ef4444';
  const fillColor = isProfit ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)';

  el.equitySub().textContent =
    `${metrics.currency} ${fmt(metrics.initial_capital)} → ${metrics.currency} ${fmt(metrics.final_equity)}`;

  const ctx = el.equityChart().getContext('2d');
  state.equityChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Portfolio Equity',
        data: values,
        borderColor: mainColor,
        backgroundColor: fillColor,
        borderWidth: 2,
        fill: true,
        tension: 0.3,
        pointRadius: equityCurve.length > 100 ? 0 : 3,
        pointHoverRadius: 5,
        pointBackgroundColor: mainColor,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#181c26',
          borderColor: '#1e2332',
          borderWidth: 1,
          titleColor: '#9da3b8',
          bodyColor: '#e8eaf2',
          padding: 12,
          callbacks: {
            label: ctx => ` ${metrics.currency} ${fmt(ctx.raw)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: {
            color: '#636a88',
            font: { family: 'Inter', size: 11 },
            maxTicksLimit: 8,
            maxRotation: 0,
          },
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: {
            color: '#636a88',
            font: { family: 'Inter', size: 11 },
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
      <td class="${isWin ? 'pos' : 'neg'}" style="color:${isWin?'#22c55e':'#ef4444'}">${t.pnl >= 0 ? '+' : ''}${fmt(t.pnl, 4)}</td>
      <td class="${isWin ? 'pos' : 'neg'}" style="color:${isWin?'#22c55e':'#ef4444'}">${t.pnl_pct >= 0 ? '+' : ''}${fmt(t.pnl_pct, 2)}%</td>
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
    el.editor().value = EXAMPLE_PINE;
    el.validateStatus().textContent = '';
    showToast('Example strategy loaded. Click "Run Backtest" to test it.', 'info');
  });

  // Clear
  el.clearBtn().addEventListener('click', () => {
    el.editor().value = '';
    el.validateStatus().textContent = '';
    el.validateStatus().className = 'validate-status';
  });

  // Validate
  el.validateBtn().addEventListener('click', validatePine);

  // Data source change
  el.dataSource().addEventListener('change', onSourceChange);
  onSourceChange(); // initialize

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

  // Set default end date to today
  const today = new Date().toISOString().split('T')[0];
  el.endDate().value = today;
}

document.addEventListener('DOMContentLoaded', init);
