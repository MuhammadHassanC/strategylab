"""
Data Manager
------------
Manages local OHLCV datasets and automated caching.
Eliminates data source selection errors by storing pre-downloaded
historical data locally on disk in the `data/` folder.
"""

import os
import glob
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import pandas as pd

log = logging.getLogger(__name__)

# Base path for local datasets
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def ensure_data_dir() -> Path:
    """Ensure the data/ directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def _dataset_filename(symbol: str, interval: str) -> str:
    """Standardized filename for dataset: e.g. BTCUSDT_1d.csv or AAPL_1h.csv"""
    clean_sym = symbol.upper().replace("-", "").replace("/", "").replace(" ", "")
    clean_inv = interval.lower().strip()
    return f"{clean_sym}_{clean_inv}.csv"


def get_dataset_path(symbol: str, interval: str) -> Path:
    """Get path to a specific symbol + interval dataset."""
    ensure_data_dir()
    return DATA_DIR / _dataset_filename(symbol, interval)


def has_local_data(symbol: str, interval: str) -> bool:
    """Check if local data exists for symbol and interval."""
    path = get_dataset_path(symbol, interval)
    return path.exists() and path.stat().st_size > 100


def save_dataset(df: pd.DataFrame, symbol: str, interval: str) -> Path:
    """Save cleaned OHLCV DataFrame to local CSV."""
    ensure_data_dir()
    path = get_dataset_path(symbol, interval)

    df_clean = df.copy()
    # Ensure required columns
    required = ["open", "high", "low", "close"]
    for col in required:
        if col not in df_clean.columns:
            raise ValueError(f"DataFrame missing required column: {col}")
    if "volume" not in df_clean.columns:
        df_clean["volume"] = 0.0

    df_clean = df_clean[["open", "high", "low", "close", "volume"]]
    df_clean.index.name = "datetime"
    df_clean = df_clean.sort_index()

    # Save with ISO datetime index
    df_clean.to_csv(path, date_format="%Y-%m-%d %H:%M:%S")
    log.info(f"Saved {len(df_clean)} bars to {path}")
    return path


def load_dataset(
    symbol: str,
    interval: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Load OHLCV DataFrame from local dataset.
    Filters by start_date and end_date if provided.
    """
    path = get_dataset_path(symbol, interval)
    if not path.exists():
        raise FileNotFoundError(
            f"No local data found for symbol '{symbol}' with interval '{interval}'."
        )

    df = pd.read_csv(path, parse_dates=["datetime"], index_col="datetime")
    df = df.sort_index()

    # Filter date range
    if start_date:
        try:
            start_dt = pd.to_datetime(start_date)
            df = df[df.index >= start_dt]
        except Exception as e:
            log.warning(f"Failed to parse start_date '{start_date}': {e}")

    if end_date:
        try:
            # Include entire end_date day
            end_dt = pd.to_datetime(end_date)
            if end_dt.hour == 0 and end_dt.minute == 0:
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
            df = df[df.index <= end_dt]
        except Exception as e:
            log.warning(f"Failed to parse end_date '{end_date}': {e}")

    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])
    return df


def list_available_datasets() -> List[Dict[str, Any]]:
    """
    Scans the data/ folder and returns metadata for all downloaded datasets.
    """
    ensure_data_dir()
    datasets = []
    csv_files = glob.glob(str(DATA_DIR / "*_*.csv"))

    for filepath in csv_files:
        p = Path(filepath)
        name = p.stem  # e.g. BTCUSDT_1d
        parts = name.split("_")
        if len(parts) != 2:
            continue
        symbol, interval = parts[0], parts[1]

        try:
            # Read first and last row quickly
            df = pd.read_csv(p, parse_dates=["datetime"], index_col="datetime")
            if df.empty:
                continue

            start_str = df.index[0].strftime("%Y-%m-%d")
            end_str = df.index[-1].strftime("%Y-%m-%d")
            total_bars = len(df)

            datasets.append({
                "symbol": symbol,
                "interval": interval,
                "bars": total_bars,
                "start": start_str,
                "end": end_str,
                "filesize_kb": round(p.stat().st_size / 1024, 1),
            })
        except Exception as e:
            log.warning(f"Could not read metadata for {p}: {e}")

    return sorted(datasets, key=lambda x: (x["symbol"], x["interval"]))


def get_smart_data(
    symbol: str,
    interval: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Primary accessor:
    1. If local dataset exists, load directly from disk (fast, offline, 100% reliable).
    2. If not local, automatically attempts to fetch and store locally for next time.
    """
    clean_sym = symbol.upper().replace("-", "").replace("/", "").replace(" ", "")

    # First check exact local match
    if has_local_data(clean_sym, interval):
        df = load_dataset(clean_sym, interval, start_date, end_date)
        if len(df) >= 30:
            return df

    # Check common aliases (e.g., BTC-USD -> BTCUSDT, AAPL -> AAPL)
    alias_map = {
        "BTC": "BTCUSDT",
        "BTCUSD": "BTCUSDT",
        "BTC-USD": "BTCUSDT",
        "ETH": "ETHUSDT",
        "ETHUSD": "ETHUSDT",
        "ETH-USD": "ETHUSDT",
        "SOL": "SOLUSDT",
        "SOLUSD": "SOLUSDT",
        "SOL-USD": "SOLUSDT",
    }
    if clean_sym in alias_map and has_local_data(alias_map[clean_sym], interval):
        df = load_dataset(alias_map[clean_sym], interval, start_date, end_date)
        if len(df) >= 30:
            return df

    # If not found locally, attempt automatic background fetch & cache
    from app.data_fetcher import fetch_yahoo, fetch_binance
    fetched_df = None

    # Try Binance for crypto
    if any(c in clean_sym for c in ["USDT", "BTC", "ETH", "BNB", "SOL"]):
        try:
            log.info(f"Auto-fetching {clean_sym} ({interval}) from Binance...")
            st = start_date or "2020-01-01"
            en = end_date or datetime.today().strftime("%Y-%m-%d")
            fetched_df = fetch_binance(clean_sym, interval, st, en)
        except Exception as exc:
            log.warning(f"Auto-fetch from Binance failed: {exc}")

    # Fallback or try Yahoo Finance
    if fetched_df is None or fetched_df.empty:
        try:
            log.info(f"Auto-fetching {symbol} ({interval}) from Yahoo Finance...")
            st = start_date or "2020-01-01"
            en = end_date or datetime.today().strftime("%Y-%m-%d")
            fetched_df = fetch_yahoo(symbol, interval, st, en)
        except Exception as exc:
            log.warning(f"Auto-fetch from Yahoo failed: {exc}")

    if fetched_df is not None and not fetched_df.empty:
        save_dataset(fetched_df, clean_sym, interval)
        return load_dataset(clean_sym, interval, start_date, end_date)

    # If completely unavailable, check if any local dataset for this symbol exists in another interval
    raise ValueError(
        f"Data for '{symbol}' ({interval}) is not available locally and could not be fetched automatically. "
        f"Please select one of the pre-loaded symbols."
    )
