"""
Python Strategy Engine
----------------------
Executes user-defined Python vectorised strategies on OHLCV market data.
Expects a function:
    def strategy(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        ...
        return entries, exits
"""

import ast
import logging
import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any, Optional

from app.backtester import simulate_trades, compute_metrics, PineStrategyConfig

log = logging.getLogger(__name__)


def is_python_strategy(code: str) -> bool:
    """Check if code is a Python strategy rather than Pine Script."""
    s = code.strip()
    if s.startswith("//@version") or "ta.sma(" in s or "ta.ema(" in s or "strategy.entry(" in s:
        return False
    if "def strategy(" in s or "def generate_signals(" in s or "import pandas" in s or "import numpy" in s:
        return True
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def validate_python_code(code: str) -> Tuple[bool, str]:
    """Validate Python syntax and ensure required strategy function is defined."""
    if not code.strip():
        return False, "Strategy code cannot be empty."

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Python SyntaxError at line {e.lineno}: {e.msg}"

    # Check for strategy or generate_signals function
    func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    if "strategy" not in func_names and "generate_signals" not in func_names:
        return False, (
            "Python strategy must define a function 'strategy(df)' or 'generate_signals(df)' "
            "that accepts the OHLCV DataFrame and returns (entries, exits)."
        )

    return True, "Valid Python strategy."


def execute_python_strategy(
    df: pd.DataFrame,
    code: str,
    initial_capital: float = 10_000.0,
    commission_pct: float = 0.1,
    qty_pct: float = 100.0,
) -> Dict[str, Any]:
    """
    Executes Python strategy and calculates performance metrics.
    """
    # Safe execution scope
    local_scope: Dict[str, Any] = {}
    global_scope = {
        "__builtins__": __builtins__,
        "pd": pd,
        "pandas": pd,
        "np": np,
        "numpy": np,
    }

    try:
        compiled = compile(code, "<strategy>", "exec")
        exec(compiled, global_scope, local_scope)
    except Exception as e:
        raise RuntimeError(f"Strategy execution error during compilation: {e}") from e

    fn = local_scope.get("strategy") or local_scope.get("generate_signals")
    if not callable(fn):
        raise ValueError("Strategy function 'strategy(df)' not found in code.")

    try:
        # Pass copy of dataframe to prevent accidental inplace mutation
        res = fn(df.copy())
    except Exception as e:
        raise RuntimeError(f"Error while running strategy function: {e}") from e

    if not isinstance(res, (tuple, list)) or len(res) < 2:
        raise ValueError(
            "Strategy function must return a tuple of (entries, exits) boolean Series."
        )

    entries, exits = res[0], res[1]

    # Convert to pd.Series if needed
    if not isinstance(entries, pd.Series):
        entries = pd.Series(entries, index=df.index)
    if not isinstance(exits, pd.Series):
        exits = pd.Series(exits, index=df.index)

    entries = entries.fillna(False).astype(bool)
    exits = exits.fillna(False).astype(bool)

    # Run trade simulation
    trades_df = simulate_trades(
        df=df,
        long_entry=entries,
        long_exit=exits,
        initial_capital=initial_capital,
        commission_pct=commission_pct,
        qty_pct=qty_pct,
    )

    # Create dummy config for metrics calculator
    dummy_cfg = PineStrategyConfig()
    dummy_cfg.title = "Python Strategy"
    dummy_cfg.initial_capital = initial_capital
    dummy_cfg.commission_value = commission_pct
    dummy_cfg.default_qty_value = qty_pct
    dummy_cfg.currency = "USD"

    metrics = compute_metrics(
        trades_df=trades_df,
        ohlcv_df=df,
        initial_capital=initial_capital,
        cfg=dummy_cfg,
        strategy_type="python_vectorized",
    )

    # Build equity curve (max 500 points)
    if not trades_df.empty:
        eq = trades_df[["exit_date", "equity_after"]].copy()
        eq.columns = ["date", "equity"]
        if len(eq) > 500:
            eq = eq.iloc[::len(eq) // 500]
        equity_curve = eq.assign(date=eq["date"].astype(str)).to_dict("records")
    else:
        equity_curve = []

    # Trade list
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
        "strategy_type": "Python Vectorized Strategy",
    }
