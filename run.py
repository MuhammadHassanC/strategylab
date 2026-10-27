"""
Entry point — run.py
Usage: python run.py
"""

import os
import webbrowser
import threading
from app.routes import app

HOST = "127.0.0.1"
PORT = 5000

def open_browser():
    import time
    time.sleep(1.2)
    webbrowser.open(f"http://{HOST}:{PORT}")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  StrategyLab — Strategy Tester (Pine Script & Python)")
    print(f"  Running at ->  http://{HOST}:{PORT}")
    print("="*60 + "\n")

    t = threading.Thread(target=open_browser, daemon=True)
    t.start()

    app.run(host=HOST, port=PORT, debug=False, threaded=True)
