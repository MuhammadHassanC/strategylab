# StrategyLab — Pine Script Backtester

A free, open-source, locally-hosted backtesting tool for TradingView Pine Script strategies. Paste any Pine Script strategy, choose a pre-loaded market asset and timeframe, and get instant performance reports with zero network latency, zero API rate limits, and 100% reliability.

---

## Key Highlights

- **100% Offline & Reliable** — Comes with pre-downloaded historical OHLCV market datasets (Crypto & Stocks). No API keys, no rate-limits, and no data source configuration errors.
- **Pine Script Support** — Paste your strategy directly from TradingView. Supports Pine Script v4 and v5 syntax including `ta.sma`, `ta.ema`, `ta.rsi`, `ta.macd`, `ta.bb`, `ta.stoch`, `strategy.entry`, `strategy.exit`, and variable-based parameter inputs (`input.int(...)`).
- **Pre-Loaded Market Datasets** — High-resolution historical datasets ready out of the box:
  - **Crypto**: `BTC/USDT` (Daily, 4H, 1H), `ETH/USDT` (Daily, 1H), `SOL/USDT` (Daily)
  - **Stocks & ETFs**: `AAPL` (Daily), `SPY` (Daily), `TSLA` (Daily), `NVDA` (Daily)
  - Automatic download and disk caching for any custom assets via `download_data.py`.
- **Institutional-Grade Performance Metrics** — Net profit, win rate, profit factor, max drawdown, Sharpe ratio, Sortino ratio, Calmar ratio, trade duration, streaks, and Buy & Hold comparison.
- **Interactive Equity Curve** — High-performance chart showing portfolio growth and drawdown over time.
- **Detailed Trade Log & CSV Export** — Complete record of every executed trade with entry/exit timestamps, prices, P&L, and one-click full CSV report download.
- **Fast & Non-Blocking** — Vectorised simulation running asynchronously on a background worker pool.

---

## Supported Pine Script Strategies

StrategyLab parses and backtests standard Pine Script patterns:

| Strategy Pattern | Indicators / Keywords |
|---|---|
| **Moving Average Crossover** | `ta.sma`, `ta.ema` + `crossover` / `crossunder` |
| **RSI Momentum & Mean Reversion** | `ta.rsi` + overbought / oversold thresholds |
| **MACD Trend Crossover** | `ta.macd` (signal line cross) |
| **Bollinger Bands** | `ta.bb` (upper/lower band bounces & breaks) |
| **RSI + Moving Average** | `ta.rsi` filtered with `ta.ema` / `ta.sma` trend |
| **RSI + MACD** | Momentum convergence signals |
| **Bollinger Bands + RSI** | Volatility envelope + momentum confirmation |
| **Stochastic Oscillator** | `ta.stoch` (%K / %D crossovers) |

---

## Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/Shifrozy/strategylab.git
cd strategylab
```

### 2. Set up virtual environment (recommended)
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS / Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

---

## Running StrategyLab

```bash
python run.py
```

The web application starts locally at:
👉 **`http://127.0.0.1:5000`** (opens automatically in your default browser).

---

## Quick Start Guide

1. Open **`http://127.0.0.1:5000`** in your browser.
2. In the **Strategy Editor**, paste your Pine Script strategy code (or click **Load Example** to load a ready-to-test EMA + RSI strategy).
3. Click **Validate Script** to inspect parsed variables and indicator parameters.
4. Under **Backtest Settings**:
   - Choose your asset (e.g. `BTC/USDT`, `ETH/USDT`, `AAPL`, `SPY`).
   - Pick your desired timeframe (`1D`, `4H`, `1H`).
   - Select your backtest date window (or click presets: `Max`, `2Y`, `1Y`).
5. Click **Run Backtest** — results appear instantly!
6. Inspect the performance overview, interactive equity curve, and individual trade logs. Click **Download CSV Report** to export everything for offline analysis or spreadsheet sharing.

---

## Pre-Downloading More Datasets

To refresh or pre-download additional market datasets into the local `data/` folder, simply run:

```bash
python download_data.py
```

All datasets are saved cleanly as standard CSVs in `data/<SYMBOL>_<INTERVAL>.csv`.

---

## Project Structure

```
strategylab/
├── run.py                  # Server launcher and browser auto-opener
├── download_data.py        # Dataset downloader & pre-fetch utility
├── requirements.txt        # Python package dependencies
├── data/                   # Bundled local OHLCV datasets (*.csv)
├── app/
│   ├── __init__.py
│   ├── routes.py           # REST API endpoints
│   ├── data_manager.py     # Local dataset loader & automated cache
│   ├── data_fetcher.py     # External data fetchers (Binance, Yahoo)
│   ├── pine_parser.py      # Pine Script v4/v5 parser & config extractor
│   ├── backtester.py       # Vectorised trade simulation engine
│   └── report_generator.py # CSV export report generator
└── static/
    ├── index.html          # Clean, modern single-page interface
    ├── style.css           # Premium financial dark-theme styles
    └── app.js              # Frontend application logic & chart rendering
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/api/datasets` | List all available local datasets and date bounds |
| `POST` | `/api/validate-pine` | Validate Pine Script syntax and infer strategy |
| `POST` | `/api/backtest` | Run an asynchronous backtest on local data |
| `GET`  | `/api/status/<job_id>` | Poll backtest execution status & progress |
| `GET`  | `/api/download-csv/<job_id>` | Download generated CSV report |
| `GET`  | `/api/symbols` | Suggested pre-loaded symbols |
| `GET`  | `/api/health` | Health check endpoint |

---

## License

MIT License — free for personal and commercial use.
