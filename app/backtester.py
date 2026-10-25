"""
Backtesting Engine
-------------------
Runs a vectorised backtest based on the parsed Pine Script config.
Supports: SMA/EMA crossover, RSI, MACD cross, Bollinger Bands, RSI+MA,
          RSI+MACD, BB+RSI, Stochastic strategies.

All calculations are done with pandas — no third-party TA library required.
Designed to be fast (vectorised) and non-blocking (called from a thread pool).
"""

import math
import logging
import numpy as np
import pandas as pd
from typing import Optional

from app.pine_parser import PineStrategyConfig, infer_strategy_type

log = logging.getLogger(__name__)


# ─── Technical Indicator Library ─────────────────────────────────────────────

def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(window=length).mean()

def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=length).mean()
    loss = (-delta.clip(upper=0)).rolling(window=length).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Returns (macd_line, signal_line, histogram)"""
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def bollinger_bands(series: pd.Series, length: int = 20, mult: float = 2.0):
    """Returns (upper, mid, lower)"""
    mid = sma(series, length)
    std = series.rolling(window=length).std()
    upper = mid + mult * std
    lower = mid - mult * std
    return upper, mid, lower

def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

def stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
               k_period: int = 14, d_period: int = 3):
    """Returns (stoch_k, stoch_d)"""
    lowest = low.rolling(window=k_period).min()
    highest = high.rolling(window=k_period).max()
    k = 100 * (close - lowest) / (highest - lowest).replace(0, np.nan)
    d = k.rolling(window=d_period).mean()
    return k, d


def crossover(a: pd.Series, b: pd.Series) -> pd.Series:
    """True where a crosses above b."""
    return (a > b) & (a.shift(1) <= b.shift(1))

def crossunder(a: pd.Series, b: pd.Series) -> pd.Series:
    """True where a crosses below b."""
    return (a < b) & (a.shift(1) >= b.shift(1))


# ─── Signal Generators ───────────────────────────────────────────────────────

def _signals_ma_crossover(df: pd.DataFrame, cfg: PineStrategyConfig):
    fast_len = cfg.sma_lengths[0] if cfg.sma_lengths else (cfg.ema_lengths[0] if cfg.ema_lengths else 10)
    slow_len = cfg.sma_lengths[-1] if len(cfg.sma_lengths) > 1 else (cfg.ema_lengths[-1] if len(cfg.ema_lengths) > 1 else 20)

    use_ema = bool(cfg.ema_lengths) and not cfg.sma_lengths
    fn = ema if use_ema else sma

    fast = fn(df["close"], fast_len)
    slow = fn(df["close"], slow_len)

    long_entry = crossover(fast, slow)
    long_exit = crossunder(fast, slow)
    return long_entry, long_exit, {"fast_ma": fast, "slow_ma": slow}


def _signals_rsi(df: pd.DataFrame, cfg: PineStrategyConfig):
    r = rsi(df["close"], cfg.rsi_length)
    long_entry = crossover(r, pd.Series(30, index=r.index))
    long_exit = crossunder(r, pd.Series(70, index=r.index))
    return long_entry, long_exit, {"rsi": r}


def _signals_macd_cross(df: pd.DataFrame, cfg: PineStrategyConfig):
    ml, sl, hist = macd(df["close"], cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
    long_entry = crossover(ml, sl)
    long_exit = crossunder(ml, sl)
    return long_entry, long_exit, {"macd": ml, "macd_signal": sl, "macd_hist": hist}


def _signals_bollinger_bands(df: pd.DataFrame, cfg: PineStrategyConfig):
    upper, mid, lower = bollinger_bands(df["close"], cfg.bb_length, cfg.bb_mult)
    long_entry = df["close"] < lower
    long_exit = df["close"] > upper
    return long_entry, long_exit, {"bb_upper": upper, "bb_mid": mid, "bb_lower": lower}


def _signals_rsi_ma(df: pd.DataFrame, cfg: PineStrategyConfig):
    r = rsi(df["close"], cfg.rsi_length)
    ma_len = cfg.sma_lengths[0] if cfg.sma_lengths else (cfg.ema_lengths[0] if cfg.ema_lengths else 20)
    use_ema = bool(cfg.ema_lengths) and not cfg.sma_lengths
    ma = ema(df["close"], ma_len) if use_ema else sma(df["close"], ma_len)

    long_entry = (r < 35) & (df["close"] > ma)
    long_exit = (r > 65) | (df["close"] < ma)
    return long_entry, long_exit, {"rsi": r, "ma": ma}


def _signals_rsi_macd(df: pd.DataFrame, cfg: PineStrategyConfig):
    r = rsi(df["close"], cfg.rsi_length)
    ml, sl, hist = macd(df["close"], cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)

    long_entry = (r < 35) & crossover(ml, sl)
    long_exit = (r > 65) | crossunder(ml, sl)
    return long_entry, long_exit, {"rsi": r, "macd": ml, "macd_signal": sl}


def _signals_bb_rsi(df: pd.DataFrame, cfg: PineStrategyConfig):
    upper, mid, lower = bollinger_bands(df["close"], cfg.bb_length, cfg.bb_mult)
    r = rsi(df["close"], cfg.rsi_length)

    long_entry = (df["close"] < lower) & (r < 40)
    long_exit = (df["close"] > upper) & (r > 60)
    return long_entry, long_exit, {"bb_upper": upper, "bb_lower": lower, "rsi": r}


def _signals_stochastic(df: pd.DataFrame, cfg: PineStrategyConfig):
    k, d = stochastic(df["high"], df["low"], df["close"])
    long_entry = (k < 20) & crossover(k, d)
    long_exit = (k > 80) & crossunder(k, d)
    return long_entry, long_exit, {"stoch_k": k, "stoch_d": d}


SIGNAL_MAP = {
    "ma_crossover": _signals_ma_crossover,
    "rsi": _signals_rsi,
    "macd_cross": _signals_macd_cross,
    "bollinger_bands": _signals_bollinger_bands,
    "rsi_ma": _signals_rsi_ma,
    "rsi_macd": _signals_rsi_macd,
    "bb_rsi": _signals_bb_rsi,
    "stochastic": _signals_stochastic,
}


# ─── Position Simulator ──────────────────────────────────────────────────────

def simulate_trades(
    df: pd.DataFrame,
    long_entry: pd.Series,
    long_exit: pd.Series,
    initial_capital: float = 10_000.0,
    commission_pct: float = 0.1,
    qty_pct: float = 100.0,
) -> pd.DataFrame:
    """
    Vectorised position simulator.
    Returns a DataFrame with one row per closed trade.
    """
    closes = df["close"].values
    dates = df.index
    entry_signals = long_entry.values
    exit_signals = long_exit.values

    trades = []
    in_position = False
    entry_price = 0.0
    entry_date = None
    equity = initial_capital
    commission_frac = commission_pct / 100.0

    for i in range(1, len(closes)):
        if not in_position:
            if entry_signals[i]:
                # Size position as a % of current equity
                position_value = equity * (qty_pct / 100.0)
                shares = position_value / closes[i]
                entry_cost = position_value * commission_frac
                # Deduct entry commission from equity (position value stays "invested")
                equity -= position_value + entry_cost
                entry_price = closes[i]
                entry_date = dates[i]
                in_position = True
        else:
            if exit_signals[i]:
                sell_value = shares * closes[i]
                exit_cost = sell_value * commission_frac
                net_proceeds = sell_value - exit_cost
                equity += net_proceeds
                cost_basis = shares * entry_price
                pnl = sell_value - cost_basis - entry_cost - exit_cost
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": dates[i],
                    "entry_price": round(entry_price, 6),
                    "exit_price": round(closes[i], 6),
                    "shares": round(shares, 6),
                    "pnl": round(pnl, 4),
                    "pnl_pct": round((pnl / cost_basis) * 100, 4) if cost_basis != 0 else 0.0,
                    "equity_after": round(equity, 4),
                    "commission": round(entry_cost + exit_cost, 4),
                    "duration_bars": i - (list(dates).index(entry_date) if entry_date in dates else 0),
                })
                in_position = False

    return pd.DataFrame(trades)


# ─── Metrics Calculator ──────────────────────────────────────────────────────

def compute_metrics(
    trades_df: pd.DataFrame,
    ohlcv_df: pd.DataFrame,
    initial_capital: float,
    cfg: PineStrategyConfig,
    strategy_type: str,
) -> dict:
    """Compute comprehensive performance metrics from trade list."""
    if trades_df.empty:
        return {
            "error": "No trades were generated. "
                     "Try adjusting the date range or strategy parameters.",
            "total_trades": 0,
        }

    pnl = trades_df["pnl"]
    final_equity = trades_df["equity_after"].iloc[-1] if not trades_df.empty else initial_capital
    total_return = final_equity - initial_capital
    total_return_pct = (total_return / initial_capital) * 100

    winning = pnl[pnl > 0]
    losing = pnl[pnl <= 0]

    win_rate = len(winning) / len(pnl) * 100 if len(pnl) > 0 else 0
    avg_win = winning.mean() if not winning.empty else 0
    avg_loss = losing.mean() if not losing.empty else 0
    profit_factor = (winning.sum() / abs(losing.sum())) if losing.sum() != 0 else float("inf")

    # Equity curve for drawdown
    equity_curve = trades_df["equity_after"]
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()

    # Sharpe Ratio (annualised, assuming 252 trading days)
    if len(pnl) > 1 and pnl.std() != 0:
        pnl_pct = trades_df["pnl_pct"] / 100
        sharpe = (pnl_pct.mean() / pnl_pct.std()) * math.sqrt(min(len(pnl), 252))
    else:
        sharpe = 0.0

    # Sortino (only downside deviation)
    neg_returns = trades_df["pnl_pct"][trades_df["pnl_pct"] < 0] / 100
    sortino = 0.0
    if len(neg_returns) > 1 and neg_returns.std() != 0:
        sortino = (trades_df["pnl_pct"].mean() / 100 / neg_returns.std()) * math.sqrt(252)

    # Calmar ratio
    calmar = (total_return_pct / abs(max_drawdown)) if max_drawdown != 0 else 0.0

    # Buy and Hold baseline
    bh_return = (ohlcv_df["close"].iloc[-1] - ohlcv_df["close"].iloc[0]) / ohlcv_df["close"].iloc[0] * 100

    # Consecutive wins/losses
    wins_losses = (pnl > 0).astype(int).diff().ne(0).cumsum()
    groups = pnl.groupby(wins_losses)
    max_consec_wins = max((len(g) for _, g in groups if (g > 0).all()), default=0)
    max_consec_losses = max((len(g) for _, g in groups if (g <= 0).all()), default=0)

    # Average trade duration (bars)
    avg_duration = trades_df["duration_bars"].mean() if "duration_bars" in trades_df else 0

    return {
        # Identity
        "strategy_name": cfg.title,
        "strategy_type": strategy_type,
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "currency": cfg.currency,

        # P&L
        "total_net_profit": round(total_return, 4),
        "total_net_profit_pct": round(total_return_pct, 4),
        "gross_profit": round(winning.sum(), 4),
        "gross_loss": round(losing.sum(), 4),
        "commission_paid": round(trades_df["commission"].sum(), 4),

        # Trade counts
        "total_trades": len(pnl),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate_pct": round(win_rate, 2),

        # Averages
        "avg_winning_trade": round(avg_win, 4),
        "avg_losing_trade": round(avg_loss, 4),
        "avg_trade_pnl": round(pnl.mean(), 4),
        "avg_trade_pnl_pct": round(trades_df["pnl_pct"].mean(), 4),
        "avg_trade_duration_bars": round(avg_duration, 2),

        # Risk metrics
        "profit_factor": round(profit_factor, 4),
        "max_drawdown_pct": round(max_drawdown, 4),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "calmar_ratio": round(calmar, 4),

        # Streaks
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,

        # Largest
        "largest_winning_trade": round(winning.max() if not winning.empty else 0, 4),
        "largest_losing_trade": round(losing.min() if not losing.empty else 0, 4),

        # Comparison
        "buy_and_hold_return_pct": round(bh_return, 4),
        "alpha_vs_buy_hold_pct": round(total_return_pct - bh_return, 4),
    }


# ─── Public API ───────────────────────────────────────────────────────────────

def run_backtest(
    df: pd.DataFrame,
    cfg: PineStrategyConfig,
) -> dict:
    """
    Main entry point. Takes OHLCV DataFrame + parsed config.
    Returns {metrics, trades, equity_curve}.
    """
    strategy_type = infer_strategy_type("", cfg)

    signal_fn = SIGNAL_MAP.get(strategy_type)
    if signal_fn is None:
        signal_fn = SIGNAL_MAP["ma_crossover"]
        strategy_type = "ma_crossover"

    log.info(f"Running backtest: strategy_type={strategy_type}, bars={len(df)}")

    try:
        long_entry, long_exit, indicators = signal_fn(df, cfg)
    except Exception as e:
        raise RuntimeError(f"Signal generation failed: {e}") from e

    trades_df = simulate_trades(
        df, long_entry, long_exit,
        initial_capital=cfg.initial_capital,
        commission_pct=cfg.commission_value,
        qty_pct=cfg.default_qty_value,
    )

    metrics = compute_metrics(trades_df, df, cfg.initial_capital, cfg, strategy_type)

    # Build equity curve for chart (sample to 500 points max)
    if not trades_df.empty:
        eq = trades_df[["exit_date", "equity_after"]].copy()
        eq.columns = ["date", "equity"]
        if len(eq) > 500:
            eq = eq.iloc[::len(eq) // 500]
        equity_curve = eq.assign(
            date=eq["date"].astype(str)
        ).to_dict("records")
    else:
        equity_curve = []

    # Trade list (cap at 1000 for JSON)
    trade_list = []
    if not trades_df.empty:
        for _, row in trades_df.head(1000).iterrows():
            trade_list.append({
                "entry_date": str(row["entry_date"]),
                "exit_date": str(row["exit_date"]),
                "entry_price": row["entry_price"],
                "exit_price": row["exit_price"],
                "pnl": row["pnl"],
                "pnl_pct": row["pnl_pct"],
                "result": "Win" if row["pnl"] > 0 else "Loss",
            })

    return {
        "metrics": metrics,
        "trades": trade_list,
        "equity_curve": equity_curve,
        "strategy_type": strategy_type,
    }
