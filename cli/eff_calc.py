# cli/eff_calc.py
from typing import List, Tuple

try:
    from cyclegraph_core import calculate_efficiency_series as _rust_calc
except Exception:
    _rust_calc = None

def _calc_eff_series(watts: List[float], pulses: List[float]) -> Tuple[float, str, List[float], List[str]]:
    if _rust_calc is not None:
        try:
            return _rust_calc(watts, pulses)
        except Exception:
            pass  # fall back til Python

    # Python fallback
    n = min(len(watts), len(pulses))
    if n == 0:
        return 0.0, "OK – treningen ser balansert ut.", [], []

    w = watts[:n]
    p = pulses[:n]
    avg_w = sum(w) / n
    avg_p = sum(p) / n if n > 0 else 0.0
    avg_eff = (avg_w / avg_p) if avg_p > 0 else 0.0

    if avg_eff < 1.0:
        session_status = "Lav effekt – vurder å øke tråkkfrekvens eller intensitet."
    elif avg_p > 170.0:
        session_status = "Høy puls – vurder lengre restitusjon."
    else:
        session_status = "OK – treningen ser balansert ut."

    per_point_eff: List[float] = []
    per_point_status: List[str] = []
    for wi, pi in zip(w, p):
        eff = 0.0 if pi == 0 else wi / pi
        per_point_eff.append(eff)
        if eff < 1.0:
            st = "Lav effekt"
        elif pi > 170.0:
            st = "Høy puls"
        else:
            st = "OK"
        per_point_status.append(st)

    return avg_eff, session_status, per_point_eff, per_point_status