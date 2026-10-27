"""
Pre-download Market Datasets
---------------------------
Downloads and prepares clean historical OHLCV data into the local `data/` folder.
This enables 100% offline, zero-failure backtesting with no API keys or live connection required.
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.data_fetcher import fetch_yahoo, fetch_binance
from app.data_manager import save_dataset, list_available_datasets, ensure_data_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("download_data")

# Multi-timeframe market assets
DOWNLOAD_TARGETS = [
    # Crypto from Binance (public REST, no key needed)
    {"source": "binance", "symbol": "BTCUSDT", "interval": "1w", "start": "2021-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "BTCUSDT", "interval": "1d", "start": "2021-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "BTCUSDT", "interval": "4h", "start": "2023-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "BTCUSDT", "interval": "2h", "start": "2023-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "BTCUSDT", "interval": "1h", "start": "2024-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "BTCUSDT", "interval": "30m", "start": "2024-11-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "BTCUSDT", "interval": "15m", "start": "2024-11-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "BTCUSDT", "interval": "5m", "start": "2024-12-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "BTCUSDT", "interval": "1m", "start": "2024-12-01", "end": "2024-12-31"},

    {"source": "binance", "symbol": "ETHUSDT", "interval": "1w", "start": "2021-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "ETHUSDT", "interval": "1d", "start": "2021-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "ETHUSDT", "interval": "4h", "start": "2023-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "ETHUSDT", "interval": "2h", "start": "2023-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "ETHUSDT", "interval": "1h", "start": "2024-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "ETHUSDT", "interval": "30m", "start": "2024-11-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "ETHUSDT", "interval": "15m", "start": "2024-11-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "ETHUSDT", "interval": "5m", "start": "2024-12-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "ETHUSDT", "interval": "1m", "start": "2024-12-01", "end": "2024-12-31"},

    {"source": "binance", "symbol": "SOLUSDT", "interval": "1w", "start": "2022-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "SOLUSDT", "interval": "1d", "start": "2022-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "SOLUSDT", "interval": "4h", "start": "2023-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "SOLUSDT", "interval": "1h", "start": "2024-01-01", "end": "2024-12-31"},
    {"source": "binance", "symbol": "SOLUSDT", "interval": "15m", "start": "2024-11-01", "end": "2024-12-31"},

    # Stocks / ETFs from Yahoo
    {"source": "yahoo", "symbol": "AAPL", "interval": "1w", "start": "2020-01-01", "end": "2024-12-31"},
    {"source": "yahoo", "symbol": "AAPL", "interval": "1d", "start": "2020-01-01", "end": "2024-12-31"},
    {"source": "yahoo", "symbol": "AAPL", "interval": "1h", "start": "2024-10-01", "end": "2024-12-31"},
    {"source": "yahoo", "symbol": "AAPL", "interval": "15m", "start": "2024-11-01", "end": "2024-12-31"},

    {"source": "yahoo", "symbol": "SPY", "interval": "1w", "start": "2020-01-01", "end": "2024-12-31"},
    {"source": "yahoo", "symbol": "SPY", "interval": "1d", "start": "2020-01-01", "end": "2024-12-31"},
    {"source": "yahoo", "symbol": "SPY", "interval": "1h", "start": "2024-10-01", "end": "2024-12-31"},
    {"source": "yahoo", "symbol": "SPY", "interval": "15m", "start": "2024-11-01", "end": "2024-12-31"},

    {"source": "yahoo", "symbol": "TSLA", "interval": "1w", "start": "2020-01-01", "end": "2024-12-31"},
    {"source": "yahoo", "symbol": "TSLA", "interval": "1d", "start": "2020-01-01", "end": "2024-12-31"},
    {"source": "yahoo", "symbol": "TSLA", "interval": "1h", "start": "2024-10-01", "end": "2024-12-31"},

    {"source": "yahoo", "symbol": "NVDA", "interval": "1w", "start": "2020-01-01", "end": "2024-12-31"},
    {"source": "yahoo", "symbol": "NVDA", "interval": "1d", "start": "2020-01-01", "end": "2024-12-31"},
    {"source": "yahoo", "symbol": "NVDA", "interval": "1h", "start": "2024-10-01", "end": "2024-12-31"},
]


def download_all():
    ensure_data_dir()
    print("=" * 60)
    print(" StrategyLab — Pre-downloading Local Market Datasets")
    print("=" * 60)

    success_count = 0
    for target in DOWNLOAD_TARGETS:
        sym = target["symbol"]
        inv = target["interval"]
        src = target["source"]
        st = target["start"]
        en = target["end"]

        print(f"\n[+] Fetching {sym} ({inv}) from {src} [{st} -> {en}]...")
        try:
            if src == "binance":
                df = fetch_binance(sym, inv, st, en)
            elif src == "yahoo":
                df = fetch_yahoo(sym, inv, st, en)
            else:
                continue

            saved_path = save_dataset(df, sym, inv)
            print(f"    [OK] Successfully saved {len(df)} candles to {saved_path.name}")
            success_count += 1
        except Exception as exc:
            print(f"    [ERROR] Failed to download {sym} ({inv}): {exc}")

        time.sleep(0.5)

    print("\n" + "=" * 60)
    print(f" Summary: {success_count}/{len(DOWNLOAD_TARGETS)} datasets ready locally.")
    print(" Available Datasets:")
    for ds in list_available_datasets():
        print(f"   * {ds['symbol']:<10} | {ds['interval']:<4} | {ds['bars']} bars | {ds['start']} -> {ds['end']} ({ds['filesize_kb']} KB)")
    print("=" * 60)


if __name__ == "__main__":
    download_all()
