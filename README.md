# StrategyLab — Trading Strategy Backtester

A fast, offline backtesting tool for trading strategies. Test **Pine Script (v4 & v5)** and **Python (Pandas)** strategies on pre-loaded historical market data without TradingView limits or API keys.

---

## Key Highlights

- **Pine Script & Python Support** — Test both TradingView **Pine Script** strategies and custom **Python (Pandas)** strategies in one place.
- **100% Offline & Reliable** — Comes bundled with pre-downloaded historical OHLCV market datasets (Crypto & Stocks). No API keys, no rate-limits, and zero network configuration errors.
- **All Standard Timeframes Supported** — Seamless backtesting on:
  - **Higher Timeframes**: `1W` (Weekly), `1D` (Daily)
  - **Hourly Timeframes**: `4H` (4 Hours), `2H` (2 Hours), `1H` (1 Hour)
  - **Intraday & Scalping**: `30m`, `15m`, `5m`, `1m`
- **Smart Data Engine & Resampling** — Bundled with 35+ local datasets and intelligent on-the-fly OHLCV aggregation. Select any timeframe and the engine automatically prepares it from local data or caches it offline.
- **Pre-Loaded Market Datasets** — Ready out of the box:
  - **Crypto**: `BTC/USDT`, `ETH/USDT`, `SOL/USDT` across all swing and intraday timeframes.
  - **Stocks & ETFs**: `AAPL`, `SPY`, `TSLA`, `NVDA` across Daily, Hourly, and 15m timeframes.
  - Custom datasets can be downloaded or updated anytime via `python download_data.py`.
- **Detailed Trade Statistics** — Net profit, win rate, profit factor, max drawdown, Sharpe ratio, Sortino ratio, Calmar ratio, trade duration, streaks, and Buy & Hold comparison.
- **Interactive Equity Curve** — High-performance chart showing portfolio growth and drawdown over time.
- **Detailed Trade Log & CSV Export** — Complete record of every executed trade with entry/exit timestamps, prices, P&L, and one-click CSV report download.
- **Fast & Responsive** — Fast simulation running asynchronously on a background worker pool.

---

## Strategy Examples

### 1. Pine Script Strategy
```pinescript
//@version=5
strategy("EMA + RSI Momentum", overlay=true, initial_capital=10000, commission_value=0.1)

fastEMA = ta.ema(close, 9)
slowEMA = ta.ema(close, 21)
rsiVal  = ta.rsi(close, 14)

if ta.crossover(fastEMA, slowEMA) and rsiVal < 65
    strategy.entry("Long", strategy.long)

if ta.crossunder(fastEMA, slowEMA) or rsiVal > 70
    strategy.close("Long")
```

### 2. Python Strategy
```python
import pandas as pd
import numpy as np

def strategy(df: pd.DataFrame):
    """
    Generate boolean Series: (entries, exits)
    """
    fast_ema = df['close'].ewm(span=9, adjust=False).mean()
    slow_ema = df['close'].ewm(span=21, adjust=False).mean()
    
    entries = (fast_ema > slow_ema) & (fast_ema.shift(1) <= slow_ema.shift(1))
    exits   = (fast_ema < slow_ema) | (df['close'] < fast_ema * 0.98)
    
    return entries, exits
```

---

## Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/MuhammadHassanC/strategylab.git
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
2. In the **Strategy Editor**, select your language (**Pine Script** or **Python**) and paste your strategy code (or click **Load Example**).
3. Click **Validate Strategy** to inspect parsed variables or function signatures.
4. Under **Backtest Settings**:
   - Choose your asset (e.g. `BTC/USDT`, `ETH/USDT`, `AAPL`, `SPY`).
   - Pick your desired timeframe (`1D`, `4H`, `1H`).
   - Select your backtest date window (or click presets: `Max`, `2Y`, `1Y`).
5. Click **Run Backtest** — results appear instantly!
6. Inspect the performance overview, interactive equity curve, and individual trade logs. Click **Download CSV Report** to export everything.

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
│   ├── python_engine.py    # Python vectorized strategy runner
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
| `POST` | `/api/validate-strategy` | Validate Pine Script or Python strategy syntax |
| `POST` | `/api/backtest` | Run an asynchronous backtest on local data |
| `GET`  | `/api/status/<job_id>` | Poll backtest execution status & progress |
| `GET`  | `/api/download-csv/<job_id>` | Download generated CSV report |
| `GET`  | `/api/symbols` | Suggested pre-loaded symbols |
| `GET`  | `/api/health` | Health check endpoint |

---

## License

MIT License — free for personal and commercial use.
