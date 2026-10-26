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

    print("\nALL API ENDPOINTS TESTED SUCCESSFULLY!")

if __name__ == "__main__":
    test_api()
