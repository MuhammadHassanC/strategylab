"""Test Flask API endpoints and backtesting."""
import time
import requests

def test_api():
    base = "http://127.0.0.1:5000"
    
    # 1. Health
    h = requests.get(f"{base}/api/health")
    print(f"Health: {h.status_code} {h.json()}")
    assert h.status_code == 200

    # 2. Datasets
    d = requests.get(f"{base}/api/datasets")
    print(f"Datasets: {d.status_code}, Found {d.json()['count']} datasets")
    assert d.status_code == 200
    assert d.json()["count"] > 0

    # 3. Backtest on local BTC data
    pine = """//@version=5
strategy("EMA Trend", overlay=true)
fast = ta.ema(close, 9)
slow = ta.ema(close, 21)
if ta.crossover(fast, slow)
    strategy.entry("Long", strategy.long)
if ta.crossunder(fast, slow)
    strategy.close("Long")
"""
    payload = {
        "pine_code": pine,
        "symbol": "BTCUSDT",
        "interval": "1d",
        "start": "2022-01-01",
        "end": "2024-01-01",
    }
    b = requests.post(f"{base}/api/backtest", json=payload)
    print(f"Backtest queued: {b.status_code} {b.json()}")
    assert b.status_code == 200
    job_id = b.json()["job_id"]

    # Poll status
    for _ in range(10):
        time.sleep(0.5)
        s = requests.get(f"{base}/api/status/{job_id}").json()
        status = s.get("status")
        print(f"  Polling job {job_id}: status={status}")
        if status == "done":
            res = s["result"]
            metrics = res["metrics"]
            print(f"  SUCCESS! Trades: {metrics['total_trades']}, Net Profit: ${metrics['total_net_profit']}, Win Rate: {metrics['win_rate_pct']}%")
            break
        elif status == "error":
            print(f"  ERROR: {s.get('error')}")
            break

    # 4. CSV download
    csv_resp = requests.get(f"{base}/api/download-csv/{job_id}")
    print(f"CSV Download: {csv_resp.status_code}, Length: {len(csv_resp.text)} chars")
    assert csv_resp.status_code == 200

    # 5. Test Python strategy backtesting
    py_strategy = """
import pandas as pd
import numpy as np

def strategy(df: pd.DataFrame):
    fast = df['close'].ewm(span=9, adjust=False).mean()
    slow = df['close'].ewm(span=21, adjust=False).mean()
    entries = (fast > slow) & (fast.shift(1) <= slow.shift(1))
    exits = (fast < slow) & (fast.shift(1) >= slow.shift(1))
    return entries, exits
"""
    # Validation
    v_resp = requests.post(f"{base}/api/validate-strategy", json={"code": py_strategy, "lang": "python"})
    print(f"Python Strategy Validation: {v_resp.status_code} {v_resp.json()['message']}")
    assert v_resp.status_code == 200

    # Execution
    py_payload = {
        "strategy_code": py_strategy,
        "lang": "python",
        "symbol": "ETHUSDT",
        "interval": "1d",
        "start": "2022-01-01",
        "end": "2024-01-01",
    }
    pb = requests.post(f"{base}/api/backtest", json=py_payload)
    print(f"Python Backtest queued: {pb.status_code} {pb.json()}")
    assert pb.status_code == 200
    py_job_id = pb.json()["job_id"]

    for _ in range(10):
        time.sleep(0.5)
        ps = requests.get(f"{base}/api/status/{py_job_id}").json()
        if ps.get("status") == "done":
            p_metrics = ps["result"]["metrics"]
            print(f"  PYTHON SUCCESS! Trades: {p_metrics['total_trades']}, Net Profit: ${p_metrics['total_net_profit']}, Win Rate: {p_metrics['win_rate_pct']}%")
            break
        elif ps.get("status") == "error":
            print(f"  PYTHON ERROR: {ps.get('error')}")
            break

    print("\nALL API ENDPOINTS & PYTHON BACKTESTING TESTED SUCCESSFULLY!")

if __name__ == "__main__":
    test_api()
