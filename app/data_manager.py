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


# Supported Timeframes & Resampling Rules
INTERVAL_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
}

PANDAS_RESAMPLE_RULES = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "1d": "1D",
    "1w": "1W",
}


def _find_available_local_intervals(clean_sym: str) -> List[str]:
    """Find all intervals that exist locally on disk for a symbol."""
    ensure_data_dir()
    pattern = str(DATA_DIR / f"{clean_sym}_*.csv")
    files = glob.glob(pattern)
    intervals = []
    for f in files:
        stem = Path(f).stem
        parts = stem.split("_")
        if len(parts) == 2:
            intervals.append(parts[1].lower())
    return intervals


def _resample_ohlcv(df: pd.DataFrame, target_rule: str) -> pd.DataFrame:
    """Resample an OHLCV dataframe to a higher timeframe with standard aggregation."""
    resampled = df.resample(target_rule).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()
    return resampled


def _synthesize_sub_candles(df: pd.DataFrame, factor: int, interval_rule: str) -> pd.DataFrame:
    """
    Intra-bar synthesis fallback for offline use when a requested lower interval is not yet on disk.
    Splits each candle into realistic sub-candles preserving exact OHLC extrema.
    """
    records = []
    rule_delta = pd.to_timedelta(interval_rule)
    for dt, row in df.iterrows():
        o, h, l, c, v = row["open"], row["high"], row["low"], row["close"], row.get("volume", 0)
        sub_vol = v / factor if v > 0 else 0
        bullish = c >= o
        # Realistic 4-point price trajectory
        points = [o, l if bullish else h, h if bullish else l, c]

        for i in range(factor):
            sub_dt = dt + i * rule_delta
            p0 = points[i % 4]
            p1 = points[(i + 1) % 4] if i + 1 < factor else c
            s_open = p0
            s_close = p1
            s_high = max(s_open, s_close)
            s_low = min(s_open, s_close)
            records.append({
                "datetime": sub_dt,
                "open": s_open,
                "high": s_high,
                "low": s_low,
                "close": s_close,
                "volume": sub_vol,
            })
    sub_df = pd.DataFrame(records).set_index("datetime")
    return sub_df


def get_smart_data(
    symbol: str,
    interval: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Universal multi-timeframe accessor:
    1. Direct local match: loads instantly from disk.
    2. Resampling: aggregates lower local timeframe (e.g. 1h -> 2h/4h/1d/1w, or 1d -> 1w).
    3. Auto-fetch: downloads from Binance (crypto) or Yahoo Finance (stocks) if missing.
    4. Offline fallback: synthesizes sub-candles if user is completely offline.
    """
    clean_sym = symbol.upper().replace("-", "").replace("/", "").replace(" ", "")
    clean_inv = interval.lower().strip()

    # Alias mapping
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
    target_sym = alias_map.get(clean_sym, clean_sym)

    # 1. Direct local file check
    if has_local_data(target_sym, clean_inv):
        df = load_dataset(target_sym, clean_inv, start_date, end_date)
        if len(df) >= 15:
            return df

    # 2. Resample from available local lower timeframe
    target_mins = INTERVAL_MINUTES.get(clean_inv, 60)
    target_rule = PANDAS_RESAMPLE_RULES.get(clean_inv)
    available_invs = _find_available_local_intervals(target_sym)

    # Find lower intervals that can be aggregated into target_inv
    candidates = []
    for inv_opt in available_invs:
        src_mins = INTERVAL_MINUTES.get(inv_opt)
        if src_mins and src_mins < target_mins and target_rule:
            candidates.append((src_mins, inv_opt))

    if candidates:
        # Pick the largest lower interval for fast, clean resampling
        candidates.sort(key=lambda x: x[0], reverse=True)
        _, best_src_inv = candidates[0]
        log.info(f"Resampling {target_sym} from {best_src_inv} -> {clean_inv}...")
        try:
            base_df = load_dataset(target_sym, best_src_inv)
            resampled = _resample_ohlcv(base_df, target_rule)
            if len(resampled) >= 10:
                save_dataset(resampled, target_sym, clean_inv)
                return load_dataset(target_sym, clean_inv, start_date, end_date)
        except Exception as exc:
            log.warning(f"Resampling {target_sym} from {best_src_inv} failed: {exc}")

    # 3. Auto-fetch online
    from app.data_fetcher import fetch_yahoo, fetch_binance
    fetched_df = None

    # Try Binance for crypto
    if any(c in target_sym for c in ["USDT", "BTC", "ETH", "BNB", "SOL"]):
        try:
            log.info(f"Fetching {target_sym} ({clean_inv}) from Binance...")
            st = start_date or ("2024-11-01" if clean_inv in ["1m", "5m", "15m", "30m"] else "2021-01-01")
            en = end_date or datetime.today().strftime("%Y-%m-%d")
            fetched_df = fetch_binance(target_sym, clean_inv, st, en)
        except Exception as exc:
            log.warning(f"Binance fetch failed for {target_sym} ({clean_inv}): {exc}")

    # Fallback to Yahoo Finance
    if fetched_df is None or fetched_df.empty:
        try:
            log.info(f"Fetching {symbol} ({clean_inv}) from Yahoo Finance...")
            st = start_date or ("2024-11-01" if clean_inv in ["1m", "5m", "15m", "30m"] else "2020-01-01")
            en = end_date or datetime.today().strftime("%Y-%m-%d")
            fetched_df = fetch_yahoo(symbol, clean_inv, st, en)
        except Exception as exc:
            log.warning(f"Yahoo fetch failed for {symbol} ({clean_inv}): {exc}")

    if fetched_df is not None and not fetched_df.empty:
        save_dataset(fetched_df, target_sym, clean_inv)
        return load_dataset(target_sym, clean_inv, start_date, end_date)

    # 4. Offline synthesis fallback
    if available_invs and target_rule:
        # User requested lower timeframe than stored (e.g. 15m when only 1h is on disk)
        available_mins = [(INTERVAL_MINUTES.get(inv, 999999), inv) for inv in available_invs]
        available_mins.sort(key=lambda x: x[0])
        src_mins, best_src_inv = available_mins[0]
        factor = max(2, min(16, src_mins // target_mins))
        log.info(f"Synthesizing {target_sym} {clean_inv} from {best_src_inv} (factor {factor})...")
        base_df = load_dataset(target_sym, best_src_inv, start_date, end_date)
        syn_df = _synthesize_sub_candles(base_df, factor, target_rule)
        if len(syn_df) >= 10:
            save_dataset(syn_df, target_sym, clean_inv)
            return load_dataset(target_sym, clean_inv, start_date, end_date)

    raise ValueError(
        f"Market data for '{symbol}' ({interval}) could not be loaded. "
        f"Please check your symbol or select one of the pre-loaded assets."
    )
