"""Quick end-to-end test of the backtesting engine."""
import sys
sys.path.insert(0, ".")

from app.pine_parser import is_pine_script, parse_pine_config, infer_strategy_type
from app.backtester import run_backtest
from app.report_generator import generate_csv_report
import pandas as pd
import numpy as np

code = """//@version=5
strategy("EMA + RSI Momentum", overlay=true, initial_capital=10000, commission_value=0.1)
fastLen = input.int(9)
slowLen = input.int(21)
rsiLen = input.int(14)
fastEMA = ta.ema(close, fastLen)
slowEMA = ta.ema(close, slowLen)
rsiVal = ta.rsi(close, rsiLen)
longCondition = ta.crossover(fastEMA, slowEMA)
if longCondition
    strategy.entry("Long", strategy.long)
if ta.crossunder(fastEMA, slowEMA)
    strategy.close("Long")
"""

print("Is Pine Script:", is_pine_script(code))
assert is_pine_script(code), "Should detect as Pine Script"

cfg = parse_pine_config(code)
print("Strategy Name:", cfg.title)
print("EMA lengths:", cfg.ema_lengths)
print("RSI length:", cfg.rsi_length)

stype = infer_strategy_type(code, cfg)
print("Inferred type:", stype)

# Synthetic OHLCV data
np.random.seed(42)
n = 500
prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
df = pd.DataFrame({
    "open": prices * 0.999,
    "high": prices * 1.002,
    "low": prices * 0.998,
    "close": prices,
    "volume": np.random.randint(1000, 10000, n) * 1.0,
}, index=pd.date_range("2020-01-01", periods=n, freq="D"))

result = run_backtest(df, cfg)
m = result["metrics"]

print()
print("=== BACKTEST RESULTS ===")
print("Total trades:       ", m.get("total_trades"))
print("Win rate %:         ", m.get("win_rate_pct"))
print("Net profit:         ", m.get("total_net_profit"))
print("Sharpe ratio:       ", m.get("sharpe_ratio"))
print("Max drawdown %:     ", m.get("max_drawdown_pct"))
print("Buy & Hold return %:", m.get("buy_and_hold_return_pct"))
print("Equity curve pts:   ", len(result["equity_curve"]))
print("Trades in log:      ", len(result["trades"]))

assert m["total_trades"] >= 0, "Trade count should be non-negative"

# CSV report
csv = generate_csv_report(
    metrics=m,
    trades=result["trades"],
    symbol="TEST",
    data_source="synthetic",
    interval="1d",
    start_date="2020-01-01",
    end_date="2021-05-15",
)
assert "STRATEGY INFORMATION" in csv, "CSV should contain strategy section"
assert "COMPLETE TRADE LOG" in csv, "CSV should contain trade log section"
print()
print("CSV report generated OK, length:", len(csv), "chars")

# Test local dataset loading and backtest on real BTCUSDT data
from app.data_manager import load_dataset, list_available_datasets
available = list_available_datasets()
print()
print(f"=== LOCAL DATASETS ({len(available)} available) ===")
for ds in available[:4]:
    print(f"  * {ds['symbol']} ({ds['interval']}): {ds['bars']} bars from {ds['start']} to {ds['end']}")

btc_df = load_dataset("BTCUSDT", "1d", "2023-01-01", "2024-01-01")
print(f"\nLoaded BTCUSDT real data: {len(btc_df)} bars ({btc_df.index[0].date()} -> {btc_df.index[-1].date()})")
btc_result = run_backtest(btc_df, cfg)
btc_m = btc_result["metrics"]
print(f"BTC Strategy Trades: {btc_m.get('total_trades')}, Net Profit: ${btc_m.get('total_net_profit')}, Win Rate: {btc_m.get('win_rate_pct')}%")
print()
print("ALL TESTS PASSED")
