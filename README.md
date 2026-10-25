# StrategyLab — Pine Script Backtester

A free, open-source, locally-hosted backtesting tool for TradingView Pine Script strategies. Paste any Pine Script strategy, select a symbol and date range, and get a full performance report — no account, no subscription, no data limits.

![StrategyLab Screenshot](docs/screenshot.png)

---

## Features

- **Pine Script Support** — Paste your strategy directly from TradingView. Supports Pine Script v4 and v5 syntax including `ta.sma`, `ta.ema`, `ta.rsi`, `ta.macd`, `ta.bb`, `ta.stoch`, `strategy.entry`, `strategy.exit`, and more.
- **Multiple Free Data Sources** — Pull historical OHLCV data from:
  - **Yahoo Finance** — Stocks, ETFs, Crypto (no API key required)
  - **Binance** — Crypto pairs via public REST API (no key required)
  - **CoinGecko** — Crypto daily data (no key required)
  - **Alpha Vantage** — Stocks (free API key available)
- **Supported Strategies** — Automatically detects and backtests:
  - Moving Average Crossover (SMA / EMA)
  - RSI (Relative Strength Index)
  - MACD Crossover
  - Bollinger Bands
  - RSI + Moving Average
  - RSI + MACD
  - Bollinger Bands + RSI
  - Stochastic Oscillator
- **Full Performance Report** — Sharpe ratio, Sortino ratio, Calmar ratio, profit factor, max drawdown, win rate, consecutive wins/losses, and more.
- **CSV Export** — Download a complete, professional report with summary metrics and the full trade log.
- **Equity Curve Chart** — Visual portfolio growth chart rendered in the browser.
- **Fast & Non-Blocking** — Backtests run asynchronously; the UI never freezes.
- **100% Local** — Runs entirely on your machine. Your strategy code never leaves your computer.

---

## Requirements

- Python 3.9 or higher
- pip

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/strategylab.git
cd strategylab

# 2. (Optional but recommended) Create a virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Running the Application

```bash
python run.py
```

The app will start and automatically open `http://127.0.0.1:5000` in your browser.

---

## Quick Start

1. Open the app in your browser (`http://127.0.0.1:5000`).
2. Paste your Pine Script strategy into the **Strategy Editor**, or click **Load Example** to use the built-in EMA + RSI strategy.
3. Click **Validate Script** to confirm it is valid Pine Script.
4. Choose your **Data Source**, enter a **Symbol** (e.g. `AAPL`, `BTCUSDT`), select a **Timeframe** and **Date Range**.
5. Click **Run Backtest** and wait for the results.
6. Review the **Performance Report** and **Trade Log**, then click **Download CSV Report** to save a full copy.

---

## Supported Pine Script Patterns

| Pattern | Detection Keywords |
|---|---|
| MA Crossover | `ta.sma`, `ta.ema` + `crossover`/`crossunder` |
| RSI | `ta.rsi` |
| MACD Crossover | `ta.macd` |
| Bollinger Bands | `ta.bb` |
| RSI + MA | `ta.rsi` + `ta.sma`/`ta.ema` |
| RSI + MACD | `ta.rsi` + `ta.macd` |
| BB + RSI | `ta.bb` + `ta.rsi` |
| Stochastic | `ta.stoch` |

> **Note:** Pine Script runs natively only inside TradingView. This tool interprets common Pine Script patterns and simulates them using Python/pandas. Complex custom logic may fall back to a best-fit strategy type.

---

## Data Source Guide

| Source | Asset Types | Key Required | Notes |
|---|---|---|---|
| Yahoo Finance | Stocks, ETFs, Crypto | No | Use symbols like `AAPL`, `BTC-USD`, `SPY` |
| Binance | Crypto pairs | No | Use pairs like `BTCUSDT`, `ETHUSDT` |
| CoinGecko | Crypto | No | Use coin IDs like `bitcoin`, `ethereum` |
| Alpha Vantage | Stocks | Free key | [Get key](https://www.alphavantage.co/support/#api-key) — demo key limited to `IBM` |

---

## CSV Report Contents

The downloaded CSV report includes:

- **Strategy Information** — name, type, symbol, data source, timeframe, period, initial capital
- **Performance Summary** — net profit, gross profit/loss, commission paid
- **Trade Statistics** — total trades, win rate, average win/loss, largest win/loss
- **Risk Metrics** — profit factor, max drawdown, Sharpe ratio, Sortino ratio, Calmar ratio
- **Streaks** — max consecutive wins and losses
- **Benchmark** — Buy & Hold return comparison
- **Full Trade Log** — every closed trade with entry/exit date, price, P&L, and P&L %

---

## Project Structure

```
strategylab/
├── run.py                  # Entry point — starts Flask and opens browser
├── requirements.txt        # Python dependencies
├── app/
│   ├── __init__.py
│   ├── routes.py           # Flask REST API endpoints
│   ├── pine_parser.py      # Pine Script detection, parsing, and type inference
│   ├── data_fetcher.py     # Multi-source historical data downloader
│   ├── backtester.py       # Vectorised backtesting engine + metrics
│   └── report_generator.py # CSV report builder
└── static/
    ├── index.html          # Frontend HTML
    ├── style.css           # Professional dark-theme stylesheet
    └── app.js              # Frontend logic (API calls, chart, tables)
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/validate-pine` | Validate if code is Pine Script |
| `POST` | `/api/backtest` | Start an async backtest job |
| `GET` | `/api/status/<job_id>` | Poll backtest job status |
| `GET` | `/api/download-csv/<job_id>` | Download CSV report |
| `GET` | `/api/symbols` | Suggested symbols per source |
| `GET` | `/api/intervals` | Supported intervals per source |
| `GET` | `/api/health` | Server health check |

---

## Roadmap

- [ ] Multi-symbol batch backtesting
- [ ] Walk-forward analysis
- [ ] Strategy parameter optimisation
- [ ] More indicator support (Ichimoku, SuperTrend, VWAP)
- [ ] Intraday data caching for faster re-runs
- [ ] Dark/light theme toggle

---

## Disclaimer

StrategyLab is provided for **educational and research purposes only**. Backtest results do not guarantee future performance. Past results are not indicative of future returns. Always do your own research before making any investment decisions.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
