# cyclegraph/analyze.py
from __future__ import annotations
from typing import Dict, Any, Optional, Callable
import math

# --- Prøv å bruke fysikkfunksjon fra cli.analyze hvis tilgjengelig ---
_cli_physics_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
try:
    import importlib
    cli_mod = importlib.import_module("cli.analyze")
    # Prioritet: analyze_physics(session) → ellers physics(session) → ellers compute_physics(session)
    for name in ("analyze_physics", "physics", "compute_physics"):
        f = getattr(cli_mod, name, None)
        if callable(f):
            _cli_physics_fn = f
            break
except Exception:
    _cli_physics_fn = None


def _get(d: Dict[str, Any], path: str, default=None):
    cur: Any = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _safe_list(x):
    return x if isinstance(x, (list, tuple)) and len(x) > 0 else None


def _nan_none(x: Optional[float]):
    try:
        if x is None:
            return None
        if x != x:  # NaN
            return None
    except Exception:
        return None
    return x


def _fallback_physics(session: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal, stabil fysikkberegning basert på velocity_smooth + altitude.
    Antakelser er konservative og tydelig merket; lett å bytte ut med mer avansert kjernelogikk.
    """
    s = session
    streams = s.get("streams", {}) or {}

    v = _safe_list(streams.get("velocity_smooth"))
    alt = _safe_list(streams.get("altitude"))
    if not v or not alt:
        return {"ok": False, "reason": "missing_physics_streams"}

    # Defaults / overrides
    mass_total = (
        _get(s, "rider.mass_kg")
        or _get(s, "profile.mass_total_kg")
        or _get(s, "mass_total_kg")
        or 78.0
    )
    cda = (
        _get(s, "CdA")
        or _get(s, "profile.CdA")
        or 0.30
    )
    crr = (
        _get(s, "crr_used")
        or _get(s, "profile.Crr")
        or _get(s, "Crr")
        or 0.005
    )
    rho = _get(s, "weather.air_density") or 1.225  # kg/m^3
    g = 9.80665

    dt = streams.get("sample_seconds") or 1.0
    try:
        dt = float(dt)
        if dt <= 0:
            dt = 1.0
    except Exception:
        dt = 1.0

    n = min(len(v), len(alt))
    if n < 2:
        return {"ok": False, "reason": "too_few_samples"}

    pw_series = []
    prev_v = float(v[0])
    prev_h = float(alt[0])

    for i in range(n):
        vi = float(v[i])
        hi = float(alt[i])

        dv = vi - prev_v
        dh = hi - prev_h
        ds = max(vi * dt, 0.1)  # meter; unngå div/0

        slope = dh / ds  # dimless ca. tan(theta)
        # clamp: robuste grenser for støy
        if slope > 0.3: slope = 0.3
        if slope < -0.3: slope = -0.3

        # krefter
        cos_th = 1.0 / math.sqrt(1.0 + slope * slope)  # cos(arctan(slope))
        sin_th = slope * cos_th                        # sin(arctan(slope))

        F_roll = crr * mass_total * g * cos_th
        F_grav = mass_total * g * sin_th
        F_aero = 0.5 * rho * cda * vi * vi

        a = dv / dt
        F_inert = mass_total * a

        P = (F_roll + F_grav + F_aero + F_inert) * vi  # W
        if not math.isfinite(P) or P < 0:
            P = 0.0
        pw_series.append(P)

        prev_v, prev_h = vi, hi

    avg_pw = sum(pw_series) / len(pw_series) if pw_series else None

    return {
        "ok": True,
        "mode": "physics",
        "precision_watt": _nan_none(avg_pw),
        "precision_watt_ci": 0.0,  # placeholder
        "CdA": cda,
        "crr_used": crr,
        "avg": _nan_none(avg_pw),
        "avg_pulse": _get(s, "streams.hr.0"),
        "calibrated": True,
        "samples": len(pw_series),
    }


def analyze_session(session: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dict-modus analyzer for CycleGraph API.
    - Hvis powermeter-serier finnes, er det helt greit at en annen serie-basert analyzers
      håndterer dem via app.py-resolveren (series-modus).
    - Her fokuserer vi på physics-mode (velocity_smooth + altitude).
    - Hvis en mer avansert fysikkfunksjon finnes i cli.analyze, brukes den først.
    """
    streams = session.get("streams", {}) or {}
    has_watts = bool(_safe_list(streams.get("watts")))
    has_physics = bool(_safe_list(streams.get("velocity_smooth"))) and bool(_safe_list(streams.get("altitude")))

    if not (has_watts or has_physics):
        return {
            "ok": False,
            "reason": "missing_inputs",
            "detail": "Trenger enten watts+puls (powermeter) ELLER velocity_smooth+altitude (physics)."
        }

    if has_physics and _cli_physics_fn:
        # Prøv appens egen fysikk først (om den finnes i cli.analyze)
        try:
            out = _cli_physics_fn(session)
            if isinstance(out, dict):
                out.setdefault("mode", "physics")
                out.setdefault("ok", True)
                return out
        except Exception as e:
            # Faller tilbake til vår robuste fysikk
            return _fallback_physics(session)

    if has_physics:
        return _fallback_physics(session)

    # Hvis vi havner her har vi watts men denne dict-analyzeren er ikke den rette til serie-modus.
    # app.py vil vanligvis ha valgt series-analyzeren i stedet.
    return {
        "ok": False,
        "reason": "prefer_series_mode",
        "detail": "Powermeter funnet; bruk series-analyzer (watts,pulses,device_watts)."
    }
