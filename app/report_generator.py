"""
CSV Report Generator
---------------------
Generates a professional, detailed CSV backtest report
with a summary section + full trade log.
"""

import csv
import io
from datetime import datetime
from typing import Optional


def generate_csv_report(
    metrics: dict,
    trades: list[dict],
    symbol: str,
    data_source: str,
    interval: str,
    start_date: str,
    end_date: str,
) -> str:
    """
    Build a complete CSV report string.
    Returns the CSV content as a string (UTF-8).
    """
    output = io.StringIO()
    writer = csv.writer(output)

    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # ─── Header Block ────────────────────────────────────────────────────────
    writer.writerow(["PINE SCRIPT STRATEGY TESTER — BACKTEST REPORT"])
    writer.writerow(["Generated", generated_at])
    writer.writerow([])

    # ─── Strategy Info ───────────────────────────────────────────────────────
    writer.writerow(["STRATEGY INFORMATION"])
    writer.writerow(["Field", "Value"])
    writer.writerow(["Strategy Name", metrics.get("strategy_name", "—")])
    writer.writerow(["Strategy Type", metrics.get("strategy_type", "—").replace("_", " ").title()])
    writer.writerow(["Symbol / Ticker", symbol.upper()])
    writer.writerow(["Data Source", data_source.title()])
    writer.writerow(["Timeframe", interval])
    writer.writerow(["Backtest Period", f"{start_date}  →  {end_date}"])
    writer.writerow(["Initial Capital", f"{metrics.get('currency','USD')} {metrics.get('initial_capital', 0):,.2f}"])
    writer.writerow([])

    # ─── Performance Summary ─────────────────────────────────────────────────
    writer.writerow(["PERFORMANCE SUMMARY"])
    writer.writerow(["Metric", "Value"])

    summary_rows = [
        ("Final Equity",             f"{metrics.get('currency','USD')} {metrics.get('final_equity', 0):,.2f}"),
        ("Total Net Profit",         f"{metrics.get('currency','USD')} {metrics.get('total_net_profit', 0):,.4f}"),
        ("Total Net Profit %",       f"{metrics.get('total_net_profit_pct', 0):.4f}%"),
        ("Gross Profit",             f"{metrics.get('currency','USD')} {metrics.get('gross_profit', 0):,.4f}"),
        ("Gross Loss",               f"{metrics.get('currency','USD')} {metrics.get('gross_loss', 0):,.4f}"),
        ("Total Commission Paid",    f"{metrics.get('currency','USD')} {metrics.get('commission_paid', 0):,.4f}"),
        ("",                         ""),
        ("Total Trades",             metrics.get('total_trades', 0)),
        ("Winning Trades",           metrics.get('winning_trades', 0)),
        ("Losing Trades",            metrics.get('losing_trades', 0)),
        ("Win Rate",                 f"{metrics.get('win_rate_pct', 0):.2f}%"),
        ("",                         ""),
        ("Avg Winning Trade",        f"{metrics.get('currency','USD')} {metrics.get('avg_winning_trade', 0):,.4f}"),
        ("Avg Losing Trade",         f"{metrics.get('currency','USD')} {metrics.get('avg_losing_trade', 0):,.4f}"),
        ("Avg Trade P&L",            f"{metrics.get('currency','USD')} {metrics.get('avg_trade_pnl', 0):,.4f}"),
        ("Avg Trade P&L %",          f"{metrics.get('avg_trade_pnl_pct', 0):.4f}%"),
        ("Avg Trade Duration (bars)", metrics.get('avg_trade_duration_bars', 0)),
        ("",                         ""),
        ("Largest Winning Trade",    f"{metrics.get('currency','USD')} {metrics.get('largest_winning_trade', 0):,.4f}"),
        ("Largest Losing Trade",     f"{metrics.get('currency','USD')} {metrics.get('largest_losing_trade', 0):,.4f}"),
        ("",                         ""),
        ("Profit Factor",            metrics.get('profit_factor', 0)),
        ("Max Drawdown",             f"{metrics.get('max_drawdown_pct', 0):.4f}%"),
        ("Sharpe Ratio",             metrics.get('sharpe_ratio', 0)),
        ("Sortino Ratio",            metrics.get('sortino_ratio', 0)),
        ("Calmar Ratio",             metrics.get('calmar_ratio', 0)),
        ("",                         ""),
        ("Max Consecutive Wins",     metrics.get('max_consecutive_wins', 0)),
        ("Max Consecutive Losses",   metrics.get('max_consecutive_losses', 0)),
        ("",                         ""),
        ("Buy & Hold Return %",      f"{metrics.get('buy_and_hold_return_pct', 0):.4f}%"),
        ("Alpha vs Buy & Hold",      f"{metrics.get('alpha_vs_buy_hold_pct', 0):.4f}%"),
    ]

    for row in summary_rows:
        writer.writerow(row)

    writer.writerow([])
    writer.writerow([])

    # ─── Trade Log ───────────────────────────────────────────────────────────
    writer.writerow(["COMPLETE TRADE LOG"])
    writer.writerow([
        "#",
        "Entry Date",
        "Exit Date",
        "Entry Price",
        "Exit Price",
        "P&L",
        "P&L %",
        "Result",
    ])

    for i, trade in enumerate(trades, start=1):
        writer.writerow([
            i,
            trade.get("entry_date", ""),
            trade.get("exit_date", ""),
            trade.get("entry_price", ""),
            trade.get("exit_price", ""),
            trade.get("pnl", ""),
            f"{trade.get('pnl_pct', 0):.4f}%",
            trade.get("result", ""),
        ])

    writer.writerow([])
    writer.writerow(["--- END OF REPORT ---"])

    return output.getvalue()
