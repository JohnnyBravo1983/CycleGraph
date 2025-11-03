# cli/rust_bindings.py
import json
import hashlib
import tempfile
import os
import sys
from typing import Any, Dict, Sequence

# Prøv pakke-root først (vanligst), fall tilbake til submodul
try:
    import cyclegraph_core as cg
except Exception:
    from cyclegraph_core import cyclegraph_core as cg  # fallback

_RUST_1ARG = getattr(cg, "compute_power_with_wind_json", None)
_RUST_V3   = getattr(cg, "compute_power_with_wind_json_v3", None)  # kun for introspeksjon/fallback


# ---------------------------------------------------------------------------
# JSON-hjelpere
# ---------------------------------------------------------------------------
def _coerce_jsonish(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, (str, bytes, bytearray)):
        try:
            return json.loads(x)
        except Exception:
            return x
    return x


# ---------------------------------------------------------------------------
# Kalibrering (Rust eller fallback)
# ---------------------------------------------------------------------------
def calibrate_session(
    watts: Sequence[float],
    speed_ms: Sequence[float],
    altitude_m: Sequence[float],
    profile: Dict[str, Any],
    weather: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Kaller Rust-kalibrering og normaliserer retur for testene:
      - out["profile"]: JSON-streng
      - cda/crr/mae: float
      - calibrated: bool
    Myk fallback dersom rust_calibrate_session ikke finnes.
    """
    if cg is None or not hasattr(cg, "rust_calibrate_session"):
        prof_out = dict(profile or {})
        out: Dict[str, Any] = {
            "calibrated": False,
            "cda": float(prof_out.get("cda") or prof_out.get("CdA") or 0.30),
            "crr": float(prof_out.get("crr") or prof_out.get("Crr") or 0.004),
            "mae": 0.0,
            "profile": "{}",
        }
        try:
            out["profile"] = json.dumps(prof_out, ensure_ascii=False)
        except Exception:
            pass
        return out

    prof_arg: Any = json.dumps(profile, ensure_ascii=False) if isinstance(profile, dict) else profile
    wthr_arg: Any = json.dumps(weather, ensure_ascii=False) if isinstance(weather, dict) else weather

    out: Any = cg.rust_calibrate_session(watts, speed_ms, altitude_m, prof_arg, wthr_arg)

    if isinstance(out, str):
        try:
            out = json.loads(out)
        except Exception:
            out = {"raw": out}

    out = dict(out or {})
    out.setdefault("calibrated", False)
    out["calibrated"] = bool(out["calibrated"])

    for k in ("cda", "crr", "mae"):
        v = out.get(k)
        try:
            out[k] = 0.0 if v is None else float(v)
        except Exception:
            out[k] = 0.0

    prof = out.get("profile")
    if isinstance(prof, dict):
        try:
            out["profile"] = json.dumps(prof, ensure_ascii=False)
        except Exception:
            out["profile"] = "{}"
    elif isinstance(prof, str):
        pass
    else:
        out["profile"] = "{}"

    return out


def calibrate_session_dict(
    watts: Sequence[float],
    speed_ms: Sequence[float],
    altitude_m: Sequence[float],
    profile: Dict[str, Any],
    weather: Dict[str, Any],
) -> Dict[str, Any]:
    """Som over, men koercer out['profile'] til dict for backend-bruk."""
    out = calibrate_session(watts, speed_ms, altitude_m, profile, weather)
    out["profile"] = _coerce_jsonish(out.get("profile"))
    return out


# ---------------------------------------------------------------------------
# Compute-adapter (ren OBJECT + fallback TRIPLE)
# ---------------------------------------------------------------------------
def _call_rust_compute(payload: Dict[str, Any]) -> str:
    """
    Serialiserer payload, dumper den til en tempfil med SHA i navnet,
    logger fingerprint (til stderr), og kaller 1-arg-exporten.
    """
    s = json.dumps(payload)
    sha = hashlib.sha256(s.encode("utf-8")).hexdigest()
    flag = "rb-1arg"
    tmp = os.path.join(tempfile.gettempdir(), f"cg_payload_{flag}_{sha[:8]}.json")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(s)
    except Exception:
        tmp = "<mem>"

    # Fingerprint til STDERR → behold ren JSON på STDOUT
    try:
        keys = list(payload.keys())
        print(f"[RB] PAYLOAD SHA256={sha} LEN={len(s)} KEYS={keys} FILE={tmp}", file=sys.stderr)
    except Exception:
        pass

    if _RUST_1ARG is not None:
        return _RUST_1ARG(s)

    if _RUST_V3 is not None:
        return _RUST_V3(s)

    raise RuntimeError(
        "Ingen Rust-export tilgjengelig (forventer compute_power_with_wind_json "
        "eller compute_power_with_wind_json_v3 i cyclegraph_core)."
    )


# ---------------------------------------------------------------------------
# ROBUST ADAPTER: OBJECT først (ren, alltid estimat), fallback til TRIPLE
# ---------------------------------------------------------------------------
def rs_power_json(samples, profile, third=None) -> str:
    """
    Backcompat for gamle 3-args kall (samples, profile, estimat).
    Denne ADAPTEREN sender alltid en ren OBJECT med 'estimat' (minst {}).
    'weather' sendes aldri i denne stien.
    Ved parse-feil i Rust (ValueError/parse error), faller vi tilbake til TRIPLE.
    """
    samples = _coerce_jsonish(samples)
    profile = _coerce_jsonish(profile)
    third   = _coerce_jsonish(third)

    # Alltid ha med estimat (minst {})
    payload: Dict[str, Any] = {
        "samples": samples,
        "profile": profile,
        "estimat": third if isinstance(third, dict) else {},
    }

    try:
        # Primær: 1-arg OBJECT
        return _call_rust_compute(payload)
    except Exception as e_obj:
        # Fallback: TRIPLE (legacy)
        try:
            tri = [samples, profile, payload["estimat"]]
            s = json.dumps(tri)
            if _RUST_1ARG is not None:
                return _RUST_1ARG(s)
            if _RUST_V3 is not None:
                return _RUST_V3(s)
            raise RuntimeError("Ingen Rust-export tilgjengelig i fallback (TRIPLE).")
        except Exception as e_tri:
            raise ValueError(f"adapter OBJECT->TRIPLE failed: obj={e_obj!r}; tri={e_tri!r}")
