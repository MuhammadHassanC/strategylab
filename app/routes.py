"""
Flask Application — Strategy Tester API
-----------------------------------------
Provides REST endpoints for the frontend:
  POST /api/backtest       — run a full backtest
  GET  /api/download-csv   — download last report as CSV
  GET  /api/symbols        — suggested symbols per source
  GET  /api/health         — health check
"""

import io
import logging
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from flask import Flask, jsonify, request, send_file, session
from flask_cors import CORS

from app.pine_parser import is_pine_script, parse_pine_config, infer_strategy_type
from app.data_fetcher import fetch_data
from app.data_manager import get_smart_data, list_available_datasets, has_local_data
from app.backtester import run_backtest
from app.report_generator import generate_csv_report

# ─── Setup ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

app = Flask(__name__, static_folder="../static", static_url_path="")
app.secret_key = "strategy-tester-secret-2025"
CORS(app, resources={r"/api/*": {"origins": "*"}})

# One thread-pool executor for non-blocking backtests
executor = ThreadPoolExecutor(max_workers=4)

# In-memory store for last CSV (per session not needed since single user local)
_last_csv: dict[str, str] = {}   # key = job_id, value = csv string
_job_status: dict[str, dict] = {}
_job_lock = threading.Lock()


# ─── Helper ───────────────────────────────────────────────────────────────────

def _run_job(job_id: str, pine_code: str, symbol: str,
             interval: str, start: str, end: str):
    """Runs in background thread using local pre-downloaded dataset."""
    try:
        with _job_lock:
            _job_status[job_id] = {"status": "fetching", "progress": 15}

        # Load from local dataset (zero network failure)
        df = get_smart_data(symbol, interval, start, end)

        with _job_lock:
            _job_status[job_id] = {"status": "running", "progress": 50}

        cfg = parse_pine_config(pine_code)
        result = run_backtest(df, cfg)

        # Generate CSV
        csv_str = generate_csv_report(
            metrics=result["metrics"],
            trades=result["trades"],
            symbol=symbol,
            data_source="Local Dataset",
            interval=interval,
            start_date=start,
            end_date=end,
        )
        _last_csv[job_id] = csv_str

        with _job_lock:
            _job_status[job_id] = {
                "status": "done",
                "progress": 100,
                "result": result,
                "csv_available": True,
            }
        log.info(f"Job {job_id} completed successfully for {symbol} ({interval}).")

    except Exception as exc:
        tb = traceback.format_exc()
        log.error(f"Job {job_id} failed: {tb}")
        with _job_lock:
            _job_status[job_id] = {
                "status": "error",
                "progress": 0,
                "error": str(exc),
            }


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": "1.0.0"})


@app.route("/api/validate-pine", methods=["POST"])
def validate_pine():
    """Quickly validate whether submitted code is Pine Script."""
    data = request.get_json(force=True, silent=True) or {}
    code = data.get("code", "")
    if not code.strip():
        return jsonify({"valid": False, "message": "No code provided."}), 400

    if not is_pine_script(code):
        return jsonify({
            "valid": False,
            "message": (
                "The code you submitted doesn't appear to be a Pine Script strategy. "
                "Make sure it includes strategy() or indicator() declarations, "
                "and uses Pine Script syntax (ta.sma, ta.rsi, strategy.entry, etc.)."
            )
        }), 422

    cfg = parse_pine_config(code)
    strategy_type = infer_strategy_type(code, cfg)

    return jsonify({
        "valid": True,
        "strategy_name": cfg.title,
        "strategy_type": strategy_type.replace("_", " ").title(),
        "message": f"Valid Pine Script detected — {cfg.title}",
    })


@app.route("/api/backtest", methods=["POST"])
def backtest():
    """
    Start a backtest job asynchronously using local data.
    Returns a job_id immediately. Poll /api/status/<job_id> for progress.
    """
    import uuid
    data = request.get_json(force=True, silent=True) or {}

    pine_code = data.get("pine_code", "").strip()
    symbol = data.get("symbol", "").strip()
    interval = data.get("interval", "1d").strip()
    start = data.get("start", "").strip()
    end = data.get("end", "").strip()

    # ── Validation
    if not pine_code:
        return jsonify({"error": "Pine Script code is required."}), 400
    if not is_pine_script(pine_code):
        return jsonify({
            "error": (
                "The submitted code doesn't appear to be a valid Pine Script strategy. "
                "Please paste a strategy that uses strategy() or indicator() calls, "
                "with Pine Script indicators (ta.sma, ta.rsi, etc.)."
            )
        }), 422
    if not symbol:
        return jsonify({"error": "A symbol or ticker is required (e.g. BTCUSDT, AAPL)."}), 400

    job_id = str(uuid.uuid4())[:8]
    with _job_lock:
        _job_status[job_id] = {"status": "queued", "progress": 0}

    executor.submit(_run_job, job_id, pine_code, symbol, interval, start, end)
    log.info(f"Backtest queued: job={job_id} symbol={symbol} interval={interval}")

    return jsonify({"job_id": job_id, "message": "Backtest started successfully."})


@app.route("/api/datasets")
def datasets():
    """Return all pre-loaded local market datasets and metadata."""
    items = list_available_datasets()
    by_symbol = {}
    for item in items:
        sym = item["symbol"]
        if sym not in by_symbol:
            by_symbol[sym] = {
                "symbol": sym,
                "intervals": [],
                "start": item["start"],
                "end": item["end"],
                "total_bars": item["bars"],
            }
        by_symbol[sym]["intervals"].append(item["interval"])
        if item["start"] < by_symbol[sym]["start"]:
            by_symbol[sym]["start"] = item["start"]
        if item["end"] > by_symbol[sym]["end"]:
            by_symbol[sym]["end"] = item["end"]

    return jsonify({
        "count": len(items),
        "datasets": items,
        "by_symbol": by_symbol,
    })


@app.route("/api/status/<job_id>")
def job_status(job_id: str):
    """Poll backtest status."""
    with _job_lock:
        status = _job_status.get(job_id)
    if status is None:
        return jsonify({"error": "Job not found."}), 404
    return jsonify(status)


@app.route("/api/download-csv/<job_id>")
def download_csv(job_id: str):
    """Download the CSV report for a completed job."""
    csv_str = _last_csv.get(job_id)
    if not csv_str:
        return jsonify({"error": "Report not found or job not completed yet."}), 404
    buf = io.BytesIO(csv_str.encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"backtest_report_{job_id}.csv",
    )


@app.route("/api/symbols")
def symbols():
    """Return available pre-loaded symbols and popular defaults."""
    items = list_available_datasets()
    local_symbols = sorted(list(set(d["symbol"] for d in items)))
    return jsonify({
        "local": local_symbols,
        "crypto": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        "stocks": ["AAPL", "SPY", "TSLA", "NVDA"],
    })

