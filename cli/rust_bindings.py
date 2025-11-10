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

def _ensure_json_str(x: Any) -> str:
    """Sørg for JSON-streng til Rust (tåler dict/list/bytes/str)."""
    if isinstance(x, (dict, list)):
        return json.dumps(x, separators=(",", ":"))
    if isinstance(x, (bytes, bytearray)):
        try:
            return x.decode("utf-8")
        except Exception:
            return x.decode(errors="ignore")
    if isinstance(x, str):
        return x
    return json.dumps(x)


# --- splitt third i weather- og estimat-deler ------------------------------
# Utvidet med 2m-vind og dir_is_from som vi mapper/viderekobler
_WEATHER_KEYS = {
    "wind_ms",
    "wind_2m_ms",        # <— NY
    "wind_dir_deg",
    "air_temp_c",
    "air_pressure_hpa",
    "dir_is_from",       # <— NY (bool)
}

def _split_third(third_in: Any):
    """
    Tar 'third' (kan være dict/JSON-str) og deler i:
      weather: {wind_ms, wind_2m_ms, wind_dir_deg, air_temp_c, air_pressure_hpa, dir_is_from}
      estimat: resten (f.eks. force, debug-flagg)
    """
    t = _coerce_jsonish(third_in)
    if not isinstance(t, dict):
        return {}, {}

    weather = {k: t[k] for k in list(t.keys()) if k in _WEATHER_KEYS and t[k] is not None}
    estimat = {k: v for k, v in t.items() if k not in _WEATHER_KEYS}
    return weather, estimat


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
# Compute-adapter (ren OBJECT + fallback V3)
# ---------------------------------------------------------------------------
def _call_rust_compute(payload: Dict[str, Any]) -> str:
    """
    Serialiserer payload, dumper den til en tempfil med SHA i navnet,
    logger fingerprint (til STDERR), og kaller 1-arg-exporten.
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

    # Fingerprint til STDERR → ryddig separasjon fra adapter-retur
    try:
        keys = list(payload.keys())
        print(f"[RB] PAYLOAD SHA256={sha} LEN={len(s)} KEYS={keys} FILE={tmp}", file=sys.stderr, flush=True)
        if "weather" in payload:
            w = payload["weather"]
            print(
                "[RB] WEATHER OUT → "
                f"T={w.get('air_temp_c')}°C P={w.get('air_pressure_hpa')}hPa "
                f"wind_ms={w.get('wind_ms')} dir={w.get('wind_dir_deg')}° from={w.get('dir_is_from')}",
                file=sys.stderr,
                flush=True,
            )
        else:
            print("[RB] WEATHER OUT → <none>", file=sys.stderr, flush=True)
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
# ROBUST ADAPTER: OBJECT først (ren, alltid estimat), flatten weather → Rust
# ---------------------------------------------------------------------------
def rs_power_json(samples, profile, third) -> str:
    """
    Pakk JSON til Rust:
      {
        "samples": [...],
        "profile": {...},
        "weather": {...?},   # <-- VIKTIG: egen toppnøkkel
        "estimat": {...?}
      }
    """
    if _RUST_1ARG is None and _RUST_V3 is None:
        raise RuntimeError("Rust core adapter not available")

    sam = _coerce_jsonish(samples)
    pro = _coerce_jsonish(profile)

    # Del opp third i vær + estimat
    weather, estimat = _split_third(third)

    # Bygg payload tidlig, legg til weather/estimat under
    payload: Dict[str, Any] = {"samples": sam, "profile": pro}

    # -------------------------------------------------------------------
    # PATCH: Normaliser vind til “TO”-retning (+ alias/koerser)
    # -------------------------------------------------------------------
    if weather:
        # 1) Map mulige alias -> kanoniske nøkler
        try:
            # vindhastighet
            if "wind_ms" not in weather and "wind_2m_ms" in weather:
                weather["wind_ms"] = weather.get("wind_2m_ms")
            # lufttrykk alias
            if "air_pressure_hpa" not in weather and "pressure_hpa" in weather:
                weather["air_pressure_hpa"] = weather.get("pressure_hpa")
        except Exception:
            pass

        # 2) Koercer typer forsiktig
        try:
            if "wind_ms" in weather and weather["wind_ms"] is not None:
                weather["wind_ms"] = float(weather["wind_ms"])
            if "wind_dir_deg" in weather and weather["wind_dir_deg"] is not None:
                weather["wind_dir_deg"] = float(weather["wind_dir_deg"])
            if "air_temp_c" in weather and weather["air_temp_c"] is not None:
                weather["air_temp_c"] = float(weather["air_temp_c"])
            if "air_pressure_hpa" in weather and weather["air_pressure_hpa"] is not None:
                weather["air_pressure_hpa"] = float(weather["air_pressure_hpa"])
        except Exception:
            pass

        # 3) “FROM” (meteorologisk) -> “TO” (vektor) normalisering
        #    Default: dir_is_from=True når ikke oppgitt
        try:
            dir_is_from = bool(weather.get("dir_is_from", True))
        except Exception:
            dir_is_from = True

        try:
            wd = float(weather.get("wind_dir_deg", 0.0))
            wd = wd % 360.0
            if dir_is_from:
                wd = (wd + 180.0) % 360.0
            weather["wind_dir_deg"] = wd
        except Exception:
            pass

        payload["weather"] = weather

    if estimat:
        payload["estimat"] = estimat

    # Kall Rust (med tydelig RB-logging)
    return _call_rust_compute(payload)
