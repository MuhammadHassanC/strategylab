"""
Data Fetcher
-------------
Downloads OHLCV historical data from multiple free sources:
  - Yahoo Finance  (stocks, ETFs, crypto via yfinance)
  - Binance        (crypto, public REST API — no key required)
  - CoinGecko      (crypto market data)
  - Alpha Vantage  (stocks — free tier, API key optional)
"""

import time
import logging
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger(__name__)


# ─── Interval normalisation ───────────────────────────────────────────────────

YFINANCE_INTERVALS = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "2h": "2h", "4h": "4h",
    "1d": "1d", "1w": "1wk", "1M": "1mo",
}

BINANCE_INTERVALS = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "2h": "2h", "4h": "4h",
    "1d": "1d", "1w": "1w", "1M": "1M",
}

BINANCE_BASE = "https://api.binance.com/api/v3"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"


# ─── Yahoo Finance ────────────────────────────────────────────────────────────

def fetch_yahoo(symbol: str, interval: str, start: str, end: str) -> pd.DataFrame:
    """
    Download OHLCV from Yahoo Finance.
    symbol: e.g. 'AAPL', 'BTC-USD', 'ETH-USD', 'SPY'
    interval: '1d', '1h', '15m' …
    start/end: 'YYYY-MM-DD'
    """
    yf_interval = YFINANCE_INTERVALS.get(interval, "1d")
    log.info(f"[Yahoo] {symbol} | {yf_interval} | {start} → {end}")
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end, interval=yf_interval, auto_adjust=True)
    if df.empty:
        raise ValueError(f"Yahoo Finance returned no data for '{symbol}' ({yf_interval})")
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low",
                             "Close": "close", "Volume": "volume"})
    df.index.name = "datetime"
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(None)
    return df[["open", "high", "low", "close", "volume"]].dropna()


# ─── Binance ──────────────────────────────────────────────────────────────────

def _binance_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return int(dt.timestamp() * 1000)


def fetch_binance(symbol: str, interval: str, start: str, end: str) -> pd.DataFrame:
    """
    Download OHLCV from Binance public API (no auth needed).
    symbol: e.g. 'BTCUSDT', 'ETHUSDT'
    """
    bi = BINANCE_INTERVALS.get(interval, "1d")
    start_ms = _binance_ms(start)
    end_ms = _binance_ms(end)
    log.info(f"[Binance] {symbol} | {bi} | {start} → {end}")

    all_candles = []
    limit = 1000

    while start_ms < end_ms:
        url = (
            f"{BINANCE_BASE}/klines"
            f"?symbol={symbol.upper()}&interval={bi}"
            f"&startTime={start_ms}&endTime={end_ms}&limit={limit}"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        all_candles.extend(data)
        # advance to next batch
        last_ts = data[-1][0]
        if last_ts == start_ms:
            break
        start_ms = last_ts + 1
        if len(data) < limit:
            break
        time.sleep(0.1)

    if not all_candles:
        raise ValueError(f"Binance returned no data for '{symbol}' ({bi})")

    df = pd.DataFrame(all_candles, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("datetime")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df[["open", "high", "low", "close", "volume"]].dropna()


# ─── CoinGecko ────────────────────────────────────────────────────────────────

COINGECKO_IDS = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "binancecoin": "binancecoin", "bnb": "binancecoin",
    "solana": "solana", "sol": "solana",
    "cardano": "cardano", "ada": "cardano",
    "ripple": "ripple", "xrp": "ripple",
    "polkadot": "polkadot", "dot": "polkadot",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "avalanche-2": "avalanche-2", "avax": "avalanche-2",
    "chainlink": "chainlink", "link": "chainlink",
    "litecoin": "litecoin", "ltc": "litecoin",
    "shiba-inu": "shiba-inu", "shib": "shiba-inu",
}

def fetch_coingecko(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    Download daily OHLCV from CoinGecko (free tier).
    symbol: coin id like 'bitcoin', 'ethereum' or common alias 'btc','eth'
    CoinGecko only provides daily data via free OHLC endpoint.
    """
    coin_id = COINGECKO_IDS.get(symbol.lower(), symbol.lower())
    start_ts = int(datetime.strptime(start, "%Y-%m-%d").timestamp())
    end_ts = int(datetime.strptime(end, "%Y-%m-%d").timestamp())
    log.info(f"[CoinGecko] {coin_id} | daily | {start} → {end}")

    url = f"{COINGECKO_BASE}/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": "max"}
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code == 429:
        raise ValueError("CoinGecko rate limit hit — try again in a minute.")
    resp.raise_for_status()
    data = resp.json()

    if not data:
        raise ValueError(f"CoinGecko returned no data for '{coin_id}'")

    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("datetime")
    df = df[(df.index.view("int64") // 10**9 >= start_ts) &
            (df.index.view("int64") // 10**9 <= end_ts)]
    df["volume"] = 0.0   # CoinGecko OHLC free tier has no volume
    return df[["open", "high", "low", "close", "volume"]].dropna()


# ─── Alpha Vantage ────────────────────────────────────────────────────────────

AV_BASE = "https://www.alphavantage.co/query"

def fetch_alpha_vantage(symbol: str, interval: str, start: str, end: str,
                        api_key: str = "demo") -> pd.DataFrame:
    """
    Download OHLCV from Alpha Vantage (free tier / demo key).
    Works for stock symbols. demo key limited to certain symbols.
    """
    if interval == "1d":
        function = "TIME_SERIES_DAILY"
        ts_key = "Time Series (Daily)"
    elif interval in ("1h", "60min"):
        function = "TIME_SERIES_INTRADAY"
        ts_key = "Time Series (60min)"
    else:
        function = "TIME_SERIES_INTRADAY"
        ts_key = f"Time Series ({interval})"

    params = {
        "function": function,
        "symbol": symbol.upper(),
        "outputsize": "full",
        "apikey": api_key,
    }
    if function == "TIME_SERIES_INTRADAY":
        params["interval"] = interval

    log.info(f"[AlphaVantage] {symbol} | {interval} | {start} → {end}")
    resp = requests.get(AV_BASE, params=params, timeout=30)
    resp.raise_for_status()
    js = resp.json()

    if ts_key not in js:
        note = js.get("Note", js.get("Information", "Unknown error"))
        raise ValueError(f"Alpha Vantage error: {note}")

    rows = []
    for date_str, ohlcv in js[ts_key].items():
        rows.append({
            "datetime": pd.to_datetime(date_str),
            "open": float(ohlcv.get("1. open", 0)),
            "high": float(ohlcv.get("2. high", 0)),
            "low": float(ohlcv.get("3. low", 0)),
            "close": float(ohlcv.get("4. close", 0)),
            "volume": float(ohlcv.get("5. volume", 0)),
        })

    df = pd.DataFrame(rows).set_index("datetime").sort_index()
    df = df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
    return df.dropna()


# ─── Unified Fetch ────────────────────────────────────────────────────────────

def fetch_data(
    source: str,
    symbol: str,
    interval: str,
    start: str,
    end: str,
    av_api_key: str = "demo"
) -> pd.DataFrame:
    """
    Unified entry point. source: 'yahoo' | 'binance' | 'coingecko' | 'alphavantage'
    Returns clean DataFrame with columns: open, high, low, close, volume
    Raises ValueError with human-readable message on failure.
    """
    source = source.lower().strip()

    if source == "yahoo":
        df = fetch_yahoo(symbol, interval, start, end)
    elif source == "binance":
        df = fetch_binance(symbol, interval, start, end)
    elif source == "coingecko":
        df = fetch_coingecko(symbol, start, end)
    elif source in ("alphavantage", "alpha_vantage"):
        df = fetch_alpha_vantage(symbol, interval, start, end, av_api_key)
    else:
        raise ValueError(f"Unknown data source: '{source}'")

    # Final sanity check
    if df.empty:
        raise ValueError("No data returned — check symbol, date range, or data source.")
    if len(df) < 30:
        raise ValueError(
            f"Not enough data ({len(df)} bars). "
            "Extend the date range or choose a higher timeframe."
        )

    log.info(f"Fetched {len(df)} bars from {source} for {symbol}")
    return df
