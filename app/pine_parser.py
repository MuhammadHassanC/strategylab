"""
Pine Script Parser & Python Converter
--------------------------------------
Detects, validates, and interprets Pine Script strategy code.
Converts common Pine Script constructs into executable Python/pandas logic.
The converted code is never exposed to the end user.
"""

import re
import math
from typing import Optional

# ─── Pine Script Detection ────────────────────────────────────────────────────

PINE_SIGNATURES = [
    r"//@version\s*=?\s*\d",
    r"strategy\s*\(",
    r"indicator\s*\(",
    r"ta\.(sma|ema|rsi|macd|bb|atr|stoch|cci|mom|roc|vwap|highest|lowest|crossover|crossunder)\s*\(",
    r"\bclose\b|\bopen\b|\bhigh\b|\blow\b|\bvolume\b|\bhl2\b|\bhlc3\b|\bohlc4\b",
    r"strategy\.(entry|exit|close|position_size|netprofit|openprofit)",
    r"plot\s*\(|plotshape\s*\(",
    r"input\.(int|float|bool|string|source|timeframe)\s*\(",
    r"math\.(abs|ceil|floor|round|sqrt|min|max|log|exp|pow|sin|cos|tan)\s*\(",
]

PINE_PATTERN = re.compile("|".join(PINE_SIGNATURES), re.IGNORECASE)

def is_pine_script(code: str) -> bool:
    """Return True if the provided text looks like Pine Script."""
    if not code or len(code.strip()) < 10:
        return False
    matches = len(PINE_PATTERN.findall(code))
    return matches >= 2


# ─── Pine Script Tokenizer ────────────────────────────────────────────────────

def _extract_param(text: str, key: str, default=None):
    """Extract a named or positional parameter value from a Pine function call."""
    # named: key=value
    named = re.search(rf"\b{key}\s*=\s*([^\s,\)]+)", text)
    if named:
        val = named.group(1).strip().strip('"').strip("'")
        return val
    return default


def _parse_number(s, default=None):
    try:
        if isinstance(s, (int, float)):
            return float(s)
        s = str(s).strip()
        if s.lower() in ("true", "na", ""):
            return default
        return float(s)
    except Exception:
        return default


# ─── Strategy Config Extraction ──────────────────────────────────────────────

class PineStrategyConfig:
    """Parsed configuration extracted from a Pine Script strategy."""

    def __init__(self):
        self.title: str = "Unnamed Strategy"
        self.overlay: bool = True
        self.initial_capital: float = 10_000.0
        self.commission_value: float = 0.1          # %
        self.commission_type: str = "percent"
        self.default_qty_type: str = "percent_of_equity"
        self.default_qty_value: float = 100.0
        self.currency: str = "USD"

        # Detected indicators
        self.sma_lengths: list[int] = []
        self.ema_lengths: list[int] = []
        self.rsi_length: int = 14
        self.macd_fast: int = 12
        self.macd_slow: int = 26
        self.macd_signal: int = 9
        self.bb_length: int = 20
        self.bb_mult: float = 2.0
        self.atr_length: int = 14

        # Entry/exit rules (simplified)
        self.entries: list[dict] = []
        self.exits: list[dict] = []

        # Raw Pine lines for rule inference
        self.raw_lines: list[str] = []


def _extract_var_ints(code: str) -> dict:
    """Build a dict of varname -> int for simple integer assignments like: fastLen = input.int(9)"""
    result = {}
    # input.int(value) or input.int(defval=value)
    for m in re.finditer(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*input\.int\s*\(\s*(\d+)', code):
        result[m.group(1)] = int(m.group(2))
    # simple literal assignments: myLen = 14
    for m in re.finditer(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(\d+)\b', code):
        if m.group(1) not in result:
            result[m.group(1)] = int(m.group(2))
    return result


def parse_pine_config(code: str) -> PineStrategyConfig:
    cfg = PineStrategyConfig()
    cfg.raw_lines = [l.strip() for l in code.splitlines()]
    _vars = _extract_var_ints(code)

    # ── Strategy header
    strat_match = re.search(
        r'strategy\s*\(\s*"([^"]+)"',
        code, re.IGNORECASE
    )
    if strat_match:
        cfg.title = strat_match.group(1)

    ic_match = re.search(r'initial_capital\s*=\s*([\d.]+)', code)
    if ic_match:
        cfg.initial_capital = float(ic_match.group(1))

    comm_match = re.search(r'commission_value\s*=\s*([\d.]+)', code)
    if comm_match:
        cfg.commission_value = float(comm_match.group(1))

    qty_match = re.search(r'default_qty_value\s*=\s*([\d.]+)', code)
    if qty_match:
        cfg.default_qty_value = float(qty_match.group(1))

    def _resolve(token: str) -> Optional[int]:
        """Return integer value for a literal digit or a variable name."""
        token = token.strip()
        if token.isdigit():
            return int(token)
        return _vars.get(token)

    # ── SMA lengths
    for m in re.finditer(r'ta\.sma\s*\([^,\)]+,\s*([a-zA-Z0-9_]+)', code):
        v = _resolve(m.group(1))
        if v: cfg.sma_lengths.append(v)
    for m in re.finditer(r'(?<!ta\.)\bsma\s*\([^,\)]+,\s*([a-zA-Z0-9_]+)', code):
        v = _resolve(m.group(1))
        if v: cfg.sma_lengths.append(v)

    # ── EMA lengths
    for m in re.finditer(r'ta\.ema\s*\([^,\)]+,\s*([a-zA-Z0-9_]+)', code):
        v = _resolve(m.group(1))
        if v: cfg.ema_lengths.append(v)
    for m in re.finditer(r'(?<!ta\.)\bema\s*\([^,\)]+,\s*([a-zA-Z0-9_]+)', code):
        v = _resolve(m.group(1))
        if v: cfg.ema_lengths.append(v)

    # ── RSI
    rsi_m = re.search(r'ta\.rsi\s*\([^,\)]+,\s*([a-zA-Z0-9_]+)', code)
    if rsi_m:
        v = _resolve(rsi_m.group(1))
        if v: cfg.rsi_length = v

    # ── MACD
    macd_m = re.search(
        r'ta\.macd\s*\([^,\)]+,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', code
    )
    if macd_m:
        cfg.macd_fast = int(macd_m.group(1))
        cfg.macd_slow = int(macd_m.group(2))
        cfg.macd_signal = int(macd_m.group(3))

    # ── Bollinger Bands
    bb_m = re.search(
        r'ta\.bb\s*\([^,\)]+,\s*(\d+)\s*,\s*([\d.]+)', code
    )
    if bb_m:
        cfg.bb_length = int(bb_m.group(1))
        cfg.bb_mult = float(bb_m.group(2))

    # ── ATR
    atr_m = re.search(r'ta\.atr\s*\(\s*(\d+)', code)
    if atr_m:
        cfg.atr_length = int(atr_m.group(1))

    # ── Entry rules
    for m in re.finditer(
        r'strategy\.entry\s*\(\s*"([^"]+)"\s*,\s*(strategy\.[a-z]+)',
        code, re.IGNORECASE
    ):
        direction = "long" if "long" in m.group(2).lower() else "short"
        cfg.entries.append({"id": m.group(1), "direction": direction})

    # ── Exit rules
    for m in re.finditer(
        r'strategy\.exit\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"',
        code, re.IGNORECASE
    ):
        cfg.exits.append({"id": m.group(1), "from": m.group(2)})

    # ── Deduplicate
    cfg.sma_lengths = sorted(set(cfg.sma_lengths))
    cfg.ema_lengths = sorted(set(cfg.ema_lengths))

    return cfg


# ─── Strategy Type Inference ─────────────────────────────────────────────────

def infer_strategy_type(code: str, cfg: PineStrategyConfig) -> str:
    """
    Infer the strategy type from the code so the backtester
    knows which signals to generate.
    """
    code_l = code.lower()

    has_rsi = "ta.rsi" in code_l or ("rsi" in code_l and "length" in code_l)
    has_macd = "ta.macd" in code_l or ("macd" in code_l and ("fast" in code_l or "slow" in code_l))
    has_bb = "ta.bb(" in code_l or "bbands" in code_l or "bollinger" in code_l
    has_sma = bool(cfg.sma_lengths) and len(cfg.sma_lengths) >= 2
    has_ema = bool(cfg.ema_lengths) and len(cfg.ema_lengths) >= 2
    has_cross = "crossover" in code_l or "crossunder" in code_l
    has_stoch = "ta.stoch" in code_l or "stochastic" in code_l

    if has_rsi and has_macd:
        return "rsi_macd"
    if has_macd and has_cross:
        return "macd_cross"
    if has_bb and has_rsi:
        return "bb_rsi"
    if has_bb:
        return "bollinger_bands"
    if has_rsi and (has_sma or has_ema):
        return "rsi_ma"
    if has_rsi:
        return "rsi"
    if (has_ema or has_sma) and has_cross:
        return "ma_crossover"
    if has_stoch:
        return "stochastic"
    if has_macd:
        return "macd_cross"

    # fallback: SMA crossover with defaults
    return "ma_crossover"
