"""Test backtesting on all timeframes."""
from app.data_manager import get_smart_data
from app.backtester import run_backtest
from app.pine_parser import parse_pine_config

pine_code = """//@version=5
strategy("EMA Cross", overlay=true)
fast = ta.ema(close, 9)
slow = ta.ema(close, 21)
if ta.crossover(fast, slow)
    strategy.entry("L", strategy.long)
if ta.crossunder(fast, slow)
    strategy.close("L")
"""
cfg = parse_pine_config(pine_code)

print("\n=== TESTING CRYPTO (BTCUSDT) ACROSS ALL TIMEFRAMES ===")
test_intervals = ["1w", "1d", "4h", "2h", "1h", "30m", "15m", "5m", "1m"]
for inv in test_intervals:
    df = get_smart_data("BTCUSDT", inv)
    res = run_backtest(df, cfg)
    m = res["metrics"]
    print(f"[OK] BTCUSDT {inv:<4}: {len(df):>5} bars | Trades: {m['total_trades']:>3} | Net PnL: ${m['total_net_profit']:>9.2f} | WinRate: {m['win_rate_pct']:>5.1f}%")

print("\n=== TESTING STOCKS (AAPL) ACROSS TIMEFRAMES ===")
for inv in ["1w", "1d", "4h", "2h", "1h", "30m", "15m", "5m"]:
    df_aapl = get_smart_data("AAPL", inv)
    res_aapl = run_backtest(df_aapl, cfg)
    m = res_aapl["metrics"]
    print(f"[OK] AAPL    {inv:<4}: {len(df_aapl):>5} bars | Trades: {m['total_trades']:>3} | Net PnL: ${m['total_net_profit']:>9.2f} | WinRate: {m['win_rate_pct']:>5.1f}%")

print("\nALL TIMEFRAME TESTS PASSED SUCCESSFULLY!")
