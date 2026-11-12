"""JavaScript value semantics the benchmarks depend on: how numbers print, JSON.stringify, String(), Number().

The benchmark ports (tau2-bench, AgentDojo) were written against JavaScript, and their tool results, messages and
grading compare printed values. These helpers keep the Python port byte-for-byte compatible with the recorded runs."""

from __future__ import annotations

import json
import math
import re
from decimal import Decimal
from typing import Any


def num_str(x: float | int) -> str:
    """Number.prototype.toString for a finite or infinite number."""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "0"
    if x.is_integer() and abs(x) < 2**53:
        return str(int(x))
    # shortest round-trip digits (repr), laid out with JavaScript's exponent rules
    _, ds, exp = Decimal(repr(abs(x))).as_tuple()
    digits = "".join(map(str, ds)).rstrip("0")
    exp += len(ds) - len(digits)
    digits = digits.lstrip("0")
    k = len(digits)
    e = k + exp - 1
    sign = "-" if x < 0 else ""
    if -7 < e < 21:
        if e >= k - 1:
            return sign + digits + "0" * (e - k + 1)
        if e >= 0:
            return sign + digits[: e + 1] + "." + digits[e + 1:]
        return sign + "0." + "0" * (-e - 1) + digits
    return sign + digits[0] + ("." + digits[1:] if k > 1 else "") + "e" + ("+" if e > 0 else "-") + str(abs(e))


def js_str(v: Any) -> str:
    """String(v)."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return num_str(v)
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return ",".join("" if x is None else js_str(x) for x in v)
    return "[object Object]"


def num(v: Any) -> float | int:
    """Number(v): NaN for what JavaScript can't convert."""
    if v is None:
        return 0
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return 0
        try:
            return int(s) if re.fullmatch(r"[+-]?\d+", s) else float(s)
        except ValueError:
            return math.nan
    if isinstance(v, list):
        return num(v[0]) if len(v) == 1 else 0 if not v else math.nan
    return math.nan


def truthy(v: Any) -> bool:
    if isinstance(v, float) and math.isnan(v):
        return False
    return bool(v)


def js_round(x: float) -> float:
    """Math.round: halves round up."""
    return math.floor(x + 0.5)


def _index_key(k: Any) -> bool:
    return isinstance(k, str) and k.isdigit() and (k == "0" or k[0] != "0") and int(k) < 2**32 - 1


def js_keys(d: dict) -> list:
    """Object.keys order: array-index keys ascending, then the rest in insertion order."""
    idx = sorted((k for k in d if _index_key(k)), key=int)
    return idx + [k for k in d if not _index_key(k)] if idx else list(d)


def _enc(v: Any, indent: str | None, level: int) -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return num_str(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        if not v:
            return "[]"
        items = [_enc(x, indent, level + 1) for x in v]
    elif isinstance(v, dict):
        if not v:
            return "{}"
        sep = ": " if indent is not None else ":"
        items = [f"{json.dumps(str(k), ensure_ascii=False)}{sep}{_enc(v[k], indent, level + 1)}" for k in js_keys(v)]
    elif isinstance(v, (set, frozenset)):
        return "{}"
    else:
        return json.dumps(str(v), ensure_ascii=False)
    open_, close = ("[", "]") if isinstance(v, (list, tuple)) else ("{", "}")
    if indent is None:
        return open_ + ",".join(items) + close
    pad, inner = "\n" + indent * level, "\n" + indent * (level + 1)
    return open_ + inner + ("," + inner).join(items) + pad + close


def dumps(v: Any, indent: int | None = None) -> str:
    """JSON.stringify(v, null, indent)."""
    return _enc(v, " " * indent if indent else None, 0)


def canonical(v: Any) -> str:
    """Key-sorted JSON with JavaScript number printing: equal values give equal strings."""
    if v is None or not isinstance(v, (dict, list, tuple)):
        return dumps(v)
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(canonical(x) for x in v) + "]"
    return "{" + ",".join(f"{json.dumps(k, ensure_ascii=False)}:{canonical(v[k])}" for k in sorted(v)) + "}"


def py_float(x: float) -> str:
    """tau2's calculate prints Python floats: 4 -> '4.0'."""
    return f"{num_str(x)}.0" if float(x).is_integer() and math.isfinite(x) else num_str(x)


def clone(v: Any) -> Any:
    """structuredClone for JSON data (much faster than copy.deepcopy on large databases)."""
    return json.loads(json.dumps(v))


def same_db(a: Any, b: Any) -> bool:
    """tau2's database comparison (key-order-free equality, 1 == 1.0). Structural equality gives the same verdict as
    comparing canonical JSON for this data, at a fraction of the cost."""
    return a == b


def to_fixed(x: float, digits: int) -> str:
    """Number.prototype.toFixed: rounds the exact binary value, ties away from zero."""
    from decimal import ROUND_HALF_UP
    if not math.isfinite(x):
        return num_str(x)
    q = Decimal(x + 0.0).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)  # + 0.0: -0 prints as 0
    return f"{q:f}"
