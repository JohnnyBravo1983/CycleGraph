# server/routes/sessions.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Query
from cli.profile_binding import load_user_profile, compute_profile_version, binding_from
from server.utils.versioning import compute_version, load_profile

# Prøv å importere heuristikk-modul (Trinn 15). Hvis den ikke finnes, bruk trygge fallbacks.
try:
    from server.utils.heuristics import (
        compute_estimated_error_and_hint,
        append_benchmark_candidate,
    )
except Exception:
    def compute_estimated_error_and_hint(profile_used, weather_used):
        """
        Fallback-heuristikk:
        - est_range: [None, None]
        - hint: enkel tekst
        - completeness: 0.0 (ingen profilscore)
        """
        return [None, None], "no-heuristics-available", 0.0

    def append_benchmark_candidate(
        ride_id,
        profile_version,
        calibration_mae,
        estimated_error_pct_range,
        profile_completeness,
        has_device_data,
        hint,
    ):
        """
        Fallback-logger: gjør ingenting, men returnerer False for å indikere
        at ingen benchmark ble lagret.
        """
        return False


import json
import sys
import traceback
import hashlib
import math
import time
import os
import csv
import datetime
import re
import glob
from pathlib import Path
from typing import Any, Dict, Tuple, Optional, List

# ─────────────────────────────────────────────────────────────
# Rust adapter: preferer cyclegraph_core, fallback til cli.rust_bindings
# ─────────────────────────────────────────────────────────────
_adapter_import_error = None

def _load_rs_power_json():
    global _adapter_import_error

    # 1) Native extension (maturin) – foretrukket
    try:
        from cyclegraph_core import rs_power_json as _rs
        _adapter_import_error = None
        print("[SVR] Using cyclegraph_core.rs_power_json", flush=True)
        return _rs
    except Exception as e:
        _adapter_import_error = f"cyclegraph_core: {e!r}"

    # 2) Fallback: python wrapper (som igjen kan kalle rust internt)
    try:
        from cli.rust_bindings import rs_power_json as _rs
        print("[SVR] Using cli.rust_bindings.rs_power_json", flush=True)
        return _rs
    except Exception as e:
        _adapter_import_error = (_adapter_import_error or "") + f" | cli.rust_bindings: {e!r}"
        print(f"[SVR] Rust adapter not available: {_adapter_import_error}", flush=True)
        return None

rs_power_json = _load_rs_power_json()

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


RESULTS_DIR = os.path.join(os.getcwd(), "logs", "results")
DEBUG_DIR = os.path.join(os.getcwd(), "_debug")

# ==================== PATCH: PERSISTED-FIRST HELPER FUNCTIONS ====================

def _repo_root_from_here() -> Path:
    """
    Finn repo-root ved å gå oppover fra denne fila til vi finner en 'logs/' mappe.
    Robust mot at server starter med "feil" cwd.
    """
    p = Path(__file__).resolve().parent
    for _ in range(0, 10):
        if (p / "logs").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path.cwd()

def _pick_best_persisted_result_path(sid: str) -> Path | None:
    root = _repo_root_from_here()
    logs = root / "logs"
    fn = f"result_{sid}.json"

    # 1) Foretrukket: latest
    p1 = logs / "actual10" / "latest" / fn
    if p1.exists() and p1.stat().st_size > 20_000:
        return p1

    # 2) Største i actual10/** (typisk full doc)
    base = logs / "actual10"
    if base.exists():
        cands = list(base.rglob(fn))
        if cands:
            cands.sort(key=lambda p: p.stat().st_size, reverse=True)
            for p in cands:
                if p.exists() and p.stat().st_size > 20_000:
                    return p

    # 3) (valgfri) fallback til logs/results – men denne er ofte stub (1–2KB),
    # så vi bruker den IKKE her. Returnér None hvis ikke actual10 finnes.
    return None

def _pick_best_session_path(sid: str) -> Path | None:
    root = _repo_root_from_here()
    logs = root / "logs"
    fn = f"session_{sid}.json"

    # 1) Foretrukket: latest
    p1 = logs / "actual10" / "latest" / fn
    if p1.exists() and p1.stat().st_size > 1000:  # minst 1KB for å være meningsfull
        return p1

    # 2) Største i actual10/** (typisk full doc)
    base = logs / "actual10"
    if base.exists():
        cands = list(base.rglob(fn))
        if cands:
            cands.sort(key=lambda p: p.stat().st_size, reverse=True)
            for p in cands:
                if p.exists() and p.stat().st_size > 1000:
                    return p

    # 3) Fallback til logs/sessions (hvis vi har en slik mappe)
    fallback = logs / "sessions" / fn
    if fallback.exists() and fallback.stat().st_size > 1000:
        return fallback

    return None

def _load_samples_from_session_file(path: Path) -> list:
    with path.open('r', encoding='utf-8-sig') as f:
        doc = json.load(f)
    # Prøv først "samples", deretter "stream"
    samples = doc.get("samples")
    if samples is None:
        samples = doc.get("stream")
    if samples is None:
        return []
    # Sørg for at det er en liste
    if isinstance(samples, list):
        return samples
    return []

def _is_full_result_doc(doc: dict) -> bool:
    """
    "Full" betyr i praksis: har watts-serie eller ikke-null power i metrics.
    """
    try:
        m = doc.get("metrics") or {}
        pw = m.get("precision_watt")
        if isinstance(pw, (int, float)) and pw > 0:
            return True

        watts = doc.get("watts") or []
        if isinstance(watts, list) and len(watts) > 0:
            return True

        # Noen docs kan ha v_rel/wind_rel i stedet
        v_rel = doc.get("v_rel") or []
        wind_rel = doc.get("wind_rel") or []
        if isinstance(v_rel, list) and len(v_rel) > 0:
            return True
        if isinstance(wind_rel, list) and len(wind_rel) > 0:
            return True
    except Exception:
        pass
    return False

# ==================== WEATHER LOCK HELPER FUNCTIONS ====================

def _as_dict(x):
    return x if isinstance(x, dict) else {}

def _extract_persisted_weather(doc: dict) -> tuple[dict | None, dict | None, str | None]:
    """
    Hent weather_used/weather_meta/weather_fp fra persisted result-doc.
    Returnerer (wx_used, wx_meta, wx_fp) eller (None, None, None) hvis ikke tilgjengelig.
    """
    try:
        metrics = _as_dict(doc.get("metrics"))
        wx_used = _as_dict(metrics.get("weather_used"))
        wx_meta = _as_dict(metrics.get("weather_meta"))
        wx_fp = metrics.get("weather_fp")
        if not wx_used:
            return None, None, None
        return wx_used, wx_meta, wx_fp if isinstance(wx_fp, str) else None
    except Exception:
        return None, None, None

# ==================== DEDUPE PROFILE HELPER FUNCTION ====================

def _dedupe_profile_keys_for_rust(p: dict) -> dict:
    """
    Rust tolerant-parser feiler på duplicate keys når dict->JSON bygges fra flere kilder.
    Vi canonicaliserer crank efficiency til ÉN representasjon.
    """
    if not isinstance(p, dict):
        return p
    out = dict(p)

    # Hvis begge finnes: behold crank_eff_pct som primær, dropp crank_efficiency
    if "crank_eff_pct" in out and "crank_efficiency" in out:
        out.pop("crank_efficiency", None)

    # Hvis du har laget to ganger crank_eff_pct via merge, så skjer det typisk ved at
    # du har en nested/sekundær profil liggende. Pass på å ikke legge inn igjen.
    # (Hvis du har en slik struktur, fjern den her.)
    return out

# ==================== ORIGINAL HELPER FUNCTIONS ====================

def _load_result_doc(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Prøv å laste analysert resultat for en gitt økt/ride_id.
    1) _debug/result_<id>.json (fasit fra scriptet)
    2) logs/results/result_<id>.json (fallback/skall)
    """
    candidates: list[str] = []

    # 1) Script/analysis sin _debug-mappe (fasit hvis den finnes)
    candidates.append(os.path.join(DEBUG_DIR, f"result_{session_id}.json"))
    # 2) Standard result-mappe som fallback
    candidates.append(os.path.join(RESULTS_DIR, f"result_{session_id}.json"))

    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue

    return None


def _ride_id_from_result_path(path: str) -> str:
    """
    Fallback: hent ride_id fra filnavnet, f.eks.
      logs/results/result_16127771071.json -> "16127771071"
    """
    base = os.path.basename(path)
    m = re.match(r"result_(.+)\.json$", base)
    if m:
        return m.group(1)
    return ""


@router.get("/list")
def list_sessions() -> List[Dict[str, Any]]:
    """
    Returner en liste over økter basert på result_*.json i logs/results,
    med samme kilde som /api/sessions/{session_id} (_load_result_doc).
    """
    rows: List[Dict[str, Any]] = []

    pattern = os.path.join(RESULTS_DIR, "result_*.json")
    for path in glob.glob(pattern):
        try:
            # 1) Hent ride_id ut fra filnavnet
            ride_id = _ride_id_from_result_path(path)
            if not ride_id:
                continue

            # 2) Bruk samme logikk som /sessions/{id} for å hente analysert resultat
            result_doc = _load_result_doc(ride_id)
            if not result_doc:
                # ingen analysert fil for denne økten – hopp over
                continue

            metrics = result_doc.get("metrics") or {}

            # 3) Precision Watt snitt: hent fra precision_watt_avg eller metrics.precision_watt
            precision_watt_avg = None
            pw_avg = result_doc.get("precision_watt_avg")
            if isinstance(pw_avg, (int, float)):
                precision_watt_avg = float(pw_avg)
            else:
                pw = metrics.get("precision_watt")
                if isinstance(pw, (int, float)):
                    precision_watt_avg = float(pw)

            # 4) profile_version: top-level eller inne i profile_used
            profile_used = result_doc.get("profile_used") or metrics.get("profile_used") or {}
            profile_version = result_doc.get("profile_version") or profile_used.get("profile_version")

            # 5) weather_source: prøv flere steder
            weather_used = metrics.get("weather_used") or {}
            weather_source = (
                result_doc.get("weather_source")
                or metrics.get("weather_source")
                or weather_used.get("provider")
                or weather_used.get("source")
            )

            # 6) start_time / distance_km – hvis/ når vi begynner å lagre dette
            start_time = result_doc.get("start_time")
            distance_km = result_doc.get("distance_km")

            rows.append(
                {
                    "ride_id": ride_id,
                    "id": ride_id,
                    "profile_version": profile_version,
                    "weather_source": weather_source,
                    "start_time": start_time,
                    "distance_km": distance_km,
                    "precision_watt_avg": precision_watt_avg,
                }
            )
        except Exception:
            # én korrupt fil skal ikke knekke hele lista
            continue

    return rows


G = 9.80665
RHO_DEFAULT = 1.225  # enkel fallback-rho

# --- WEATHER konfig ---
REDUCE_10M_TO_2M = 0.75  # konservativ nedskalering 10 m → 2 m (landevei)


# ----------------- HELPERE (kontrakt + nominelle metrics) -----------------

# --- Trinn 5: device lock + profile normalization ---

def _apply_device_heuristics(samples: list, device: str) -> list:
    if not isinstance(samples, list): return samples
    if (device or "").lower() != "strava": return samples
    out, prev = [], None
    for s in samples:
        s = dict(s or {})
        v = float(s.get("v_ms") or s.get("velocity_smooth") or 0.0)
        s["moving"] = bool(s.get("moving")) or (v > 0.3)  # moving-filter
        if s.get("grade") is None and s.get("altitude_m") is not None and prev is not None:
            dt = float(s.get("t",0.0)) - float(prev.get("t",0.0))
            if dt > 0:
                dh = float(s["altitude_m"]) - float(prev.get("altitude_m", s["altitude_m"]))
                vv = v if v > 0 else 10.0
                s["grade"] = (dh / (vv * dt)) * 100.0
        out.append(s); prev = s
    return out


DEFAULT_DEVICE = "strava"

def _ensure_profile_device(p: dict) -> dict:
    """Normaliser profil og lås device til 'strava' hvis mangler (ikke overstyr eksplisitt input)."""
    p = dict(p or {})
    # alias-normalisering
    if "weight" in p and "weight_kg" not in p:
        p["weight_kg"] = p.pop("weight")
    if "crank_eff" in p and "crank_eff_pct" not in p:
        p["crank_eff_pct"] = p.pop("crank_eff")
    # device-lock (kun hvis ikke satt)
    if not p.get("device"):
        p["device"] = DEFAULT_DEVICE
    return p

def _inject_profile_used(resp: dict, prof: dict) -> dict:
    """Sørg for at metrics.profile_used alltid er komplett og konsistent."""
    resp = dict(resp or {})
    metrics = dict(resp.get("metrics") or {})
    profile_used = {
        "cda": float(prof.get("cda")) if prof.get("cda") is not None else 0.30,
        "crr": float(prof.get("crr")) if prof.get("crr") is not None else 0.004,
        "weight_kg": float(prof.get("weight_kg")) if prof.get("weight_kg") is not None else 78.0,
        "crank_eff_pct": float(prof.get("crank_eff_pct")) if prof.get("crank_eff_pct") is not None else 95.5,
        "device": (prof.get("device") or DEFAULT_DEVICE),
    }
    metrics.setdefault("profile_used", {})
    metrics["profile_used"].update(profile_used)
    resp["metrics"] = metrics
    resp.setdefault("repr_kind", "object_v3")
    resp.setdefault("source", resp.get("source") or "rust_1arg")
    return resp


def _ensure_contract_shape(resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sett sikre defaults og garanter kontrakt — kun setdefault,
    ikke endre eksisterende tallverdier.
    """
    resp = dict(resp or {})

    # toppnivå defaults (ikke overskriv hvis Rust har satt disse)
    resp.setdefault("source", resp.get("source") or "fallback_py")
    resp.setdefault("weather_applied", False)
    resp.setdefault("profile_used", {})  # speiles ofte fra metrics.profile_used

    # metrics: bare default-nøkler, ingen beregning
    m = resp.setdefault("metrics", {})
    m.setdefault("precision_watt", 0.0)

    # --- PATCH A: alltid-felt i metrics (kalibrering) ---
    m.setdefault("calibration_mae", None)
    m.setdefault("calibrated", False)
    m.setdefault("calibration_status", "not_available")

    m.setdefault("drag_watt", 0.0)
    m.setdefault("rolling_watt", 0.0)
    # total_watt defaulter til precision_watt dersom mangler
    m.setdefault("total_watt", m.get("precision_watt", 0.0))
    m.setdefault("profile_used", {})
    # speil weather_applied inn i metrics kun hvis mangler
    m.setdefault("weather_applied", bool(resp.get("weather_applied", False)))

    # speil metrics.profile_used til toppnivå om det finnes (ikke tvang)
    if "profile_used" in m and isinstance(m["profile_used"], dict) and not resp.get("profile_used"):
        resp["profile_used"] = m["profile_used"]

    # debug-defaults (uten å overskrive eksisterende)
    dbg = resp.setdefault("debug", {})
    dbg.setdefault("reason", "ok")
    dbg.setdefault("force_recompute", False)
    dbg.setdefault("persist_ignored", False)
    dbg.setdefault("ignored_persist", False)

    return resp

# --- Trinn 6 helpers ---
def _t6_extract_device_watts(samples):
    out = []
    for s in samples or []:
        if isinstance(s, dict):
            v = s.get("device_watts", s.get("device_watt"))
            try:
                out.append(None if v is None else float(v))
            except Exception:
                out.append(None)
    return out

def _t6_series_mae(pred, dev):
    n = min(len(pred), len(dev))
    if n == 0: return None
    s = 0.0; c = 0
    for i in range(n):
        a = pred[i]; b = dev[i]
        if isinstance(a, (int,float)) and isinstance(b, (int,float)):
            s += abs(float(a) - float(b)); c += 1
    return (s/c) if c else None

def _t6_pick_predicted_series(result_dict):
    for k in ("watts", "total_watt_series", "power"):
        v = result_dict.get(k)
        if isinstance(v, list) and v and isinstance(v[0], (int, float)):
            return [float(x) for x in v]
    return []

def _t6_calib_csv_append(sid, n, calibrated, status, mae, mean_pred, mean_dev):
    if os.getenv("CG_CALIBRATE","") != "1":
        return
    try:
        os.makedirs("logs", exist_ok=True)
        p = "logs/trinn6-manual_sanity.csv"
        write_header = not os.path.exists(p)
        with open(p, "a", encoding="utf-8") as f:
            if write_header:
                f.write("sid,n,calibrated,status,mae,mean_pred,mean_dev\n")
            f.write(f"{sid},{n},{calibrated},{status},{'' if mae is None else mae},{'' if mean_pred is None else mean_pred},{'' if mean_dev is None else mean_dev}\n")
    except Exception:
        pass

# --- Trinn 7: Observability Logging ---
def _write_observability(resp: dict) -> None:
    """Intern Trinn7-helper for JSON+CSV observability logging."""
    os.makedirs("logs", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    # Full JSON-dump (én per run)
    jpath = f"logs/trinn7-observability_{ts}.json"
    try:
        with open(jpath, "w", encoding="utf-8") as jf:
            json.dump(resp, jf, ensure_ascii=False, indent=2)
    except Exception as e_json:
        print(f"[SVR][OBS] JSON-write failed: {e_json!r}", flush=True)

    # CSV-record med flate nøkkelfelter
    m = dict(resp.get("metrics") or {})
    pu = dict((m.get("profile_used") or {})) if isinstance(m, dict) else {}
    dbg = dict(resp.get("debug") or {})
    row = {
        "precision_watt": m.get("precision_watt"),
        "total_watt": m.get("total_watt"),
        "weather_applied": resp.get("weather_applied"),
        "crank_eff_pct": pu.get("crank_eff_pct") or (resp.get("profile_used") or {}).get("crank_eff_pct"),
        "calibration_mae": m.get("calibration_mae"),
        "calibrated": m.get("calibrated"),
        "calibration_status": m.get("calibration_status"),
        "source": resp.get("source"),
        "repr_kind": resp.get("repr_kind"),
        "weather_source": dbg.get("weather_source"),
        "profile_version": pu.get("profile_version"),
        "debug_reason": dbg.get("reason"),
    }

    csv_path = "logs/trinn7-observability.csv"
    try:
        write_header = not os.path.exists(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8") as cf:
            w = csv.DictWriter(cf, fieldnames=list(row.keys()))
            if write_header:
                w.writeheader()
            w.writerow(row)
        print(f"[SVR][OBS] wrote {csv_path} + {jpath}", flush=True)
    except Exception as e_csv:
        print(f"[SVR][OBS] CSV-write failed: {e_csv!r}", flush=True)

# --- Vær-hjelpere ---
def _center_latlon_and_hour_from_samples(samples: list[dict]) -> Tuple[Optional[float], Optional[float], Optional[int]]:
    lat_sum = lon_sum = 0.0
    n_ll = 0
    t_abs = []

    for s in samples or []:
        lat = s.get("lat_deg"); lon = s.get("lon_deg")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            lat_sum += float(lat); lon_sum += float(lon); n_ll += 1
        ta = s.get("t_abs")
        if isinstance(ta, (int, float)):
            t_abs.append(float(ta))

    center_lat = (lat_sum / n_ll) if n_ll > 0 else None
    center_lon = (lon_sum / n_ll) if n_ll > 0 else None

    ts_hour = None
    if t_abs:
        mid = t_abs[len(t_abs)//2]
        ts_hour = int(round(mid / 3600.0)) * 3600

    return center_lat, center_lon, ts_hour

def _iso_hour_from_unix(ts_hour: int) -> str:
    # UNIX → "YYYY-MM-DDTHH:00"
    return datetime.datetime.utcfromtimestamp(int(ts_hour)).strftime("%Y-%m-%dT%H:00")

def _unix_from_iso_hour(s: str) -> int:
    return int(datetime.datetime.strptime(s, "%Y-%m-%dT%H:00").replace(tzinfo=datetime.timezone.utc).timestamp())

async def _fetch_open_meteo_hour_ms(lat: float, lon: float, ts_hour: int) -> Optional[Dict[str, float]]:
    """
    Hent timesoppløst vær fra Open-Meteo i m/s (10 m), °C, hPa.
    Returnerer dict med felt klare for fysikkmotoren (etter skalering til 2 m).
    """
    import aiohttp
    # Vi låser til m/s for å unngå enhetsfeil.
    # Bruker 'past_days' bredt nok til å dekke historiske økter rundt ts_hour.
    base = (
        "https://archive-api.open-meteo.com/v1/era5"
        "?latitude={lat}&longitude={lon}"
        "&hourly=temperature_2m,pressure_msl,windspeed_10m,winddirection_10m"
        "&windspeed_unit=ms"
        "&timezone=UTC"
        "&past_days=30"
    ).format(lat=lat, lon=lon)

    # Vi trenger bare én time (ts_hour); filterer client-side på første timepost
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(base, timeout=12) as resp:
                if resp.status != 200:
                    print(f"[WX] open-meteo HTTP {resp.status}")
                    return None
                payload = await resp.json()

        hrs = payload.get("hourly") or {}
        times = hrs.get("time") or []
        t2m   = hrs.get("temperature_2m") or []
        pmsl  = hrs.get("pressure_msl") or []
        w10   = hrs.get("windspeed_10m") or []      # m/s (10 m)
        wdir  = hrs.get("winddirection_10m") or []  # deg (fra)

        if not (times and t2m and pmsl and w10 and wdir):
            print("[WX] open-meteo payload missing fields")
            return None

        # Finn index for ønsket UTC-time (ts_hour er UNIX sekunder avrundet time)
        wanted_iso = _iso_hour_from_unix(ts_hour)  # f.eks. "2025-11-09T14:00"
        try:
            idx = times.index(wanted_iso)
        except ValueError:
            # Fallback: nærmeste time
            idx = min(range(len(times)), key=lambda i: abs(_unix_from_iso_hour(times[i]) - ts_hour))

        # Les verdier
        t_c    = float(t2m[idx])
        p_hpa  = float(pmsl[idx])
        w10_ms = float(w10[idx])     # m/s @10 m
        w_deg  = float(wdir[idx])    # fra-retning

        # Skaler 10 m → 2 m
        w2_ms = w10_ms * float(REDUCE_10M_TO_2M)

        return {
            "air_temp_c":       t_c,
            "air_pressure_hpa": p_hpa,
            "wind_ms":          w2_ms,   # endelig m/s (≈2 m)
            "wind_dir_deg":     w_deg,   # "fra"-retning
            "meta": {
                "windspeed_10m_ms": w10_ms,
                "reduce_factor":    REDUCE_10M_TO_2M,
                "source":           "open-meteo/era5"
            }
        }
    except Exception as e:
        print(f"[WX] fetch_open_meteo error: {e}")
        return None

def _wx_fp(wx: Dict[str, Any]) -> str:
    try:
        return hashlib.sha1(json.dumps(wx, sort_keys=True).encode("utf-8")).hexdigest()
    except Exception:
        return ""

# --- Trinn 15 hjelper ---
def _body_has_device_watts(samples) -> bool:
    if not isinstance(samples, list):
        return False
    for s in samples:
        if isinstance(s, dict) and ("device_watts" in s) and (s.get("device_watts") is not None):
            return True
    return False

def _nominal_metrics(profile: dict) -> dict:
    # (ikke brukt til beregning i kontrakt; beholdt for ev. tester)
    G_loc = 9.80665
    RHO = 1.225
    v = 6.0
    w = float(profile.get("weight_kg") or profile.get("weightKg") or 78.0)
    cda = float(profile.get("CdA", profile.get("cda", 0.30)))
    crr = float(profile.get("Crr", profile.get("crr", 0.004)))
    drag = 0.5 * RHO * cda * (v ** 3)
    roll = w * G_loc * crr * v
    return {"precision_watt": drag + roll, "drag_watt": drag, "rolling_watt": roll}


def _bool(val: Any) -> bool:
    try:
        return bool(val)
    except Exception:
        return False


def _profile_used_from(profile: dict) -> dict:
    """Bygg nøyaktig profile_used slik testene forventer (snake_case på weight_kg)."""
    out: Dict[str, Any] = {}
    if "CdA" in profile:
        out["CdA"] = float(profile["CdA"])
    if "Crr" in profile:
        out["Crr"] = float(profile["Crr"])
    if "weight_kg" in profile:
        out["weight_kg"] = float(profile["weight_kg"])
    elif "weightKg" in profile:
        out["weight_kg"] = float(profile["weightKg"])
    if "device" in profile:
        out["device"] = profile["device"]
    return out


def _base_debug(force_recompute: bool, used_fallback: bool) -> Dict[str, Any]:
    """Minimal debug-blokk som ALLTID returneres (med default reason='ok')."""
    return {
        "force_recompute": bool(force_recompute),
        "persist_ignored": bool(force_recompute),  # back-compat
        "ignored_persist": bool(force_recompute),  # det testene krever
        "used_fallback": bool(used_fallback),
        "reason": "ok",
    }


def _fallback_metrics(samples, profile, weather_applied: bool, profile_used=None):
    """
    Minimal, deterministisk fallback for tester – leverer allokert nøkkelpakke
    og kan (valgfritt) inkludere profile_used slik den kom inn.
    """
    weight = float(profile.get("weight_kg") or profile.get("weightKg") or 78.0)
    cda = float(profile.get("CdA", profile.get("cda", 0.28)))
    crr = float(profile.get("Crr", profile.get("crr", 0.004)))

    V_NOM = 6.0
    RHO_DEF = 1.225
    G_CONST = 9.80665

    def pack(drag: float, roll: float) -> Dict[str, Any]:
        total = drag + roll
        out = {
            "precision_watt": total,
            "total_watt": total,
            "drag_watt": drag,
            "rolling_watt": roll,
            "weather_applied": bool(weather_applied),
            "precision_watt_ci": 0.0,
        }
        if profile_used is not None:
            out["profile_used"] = profile_used  # legges inne i metrics
        return out

    if not samples:
        drag = 0.5 * RHO_DEF * cda * (V_NOM ** 3)
        roll = crr * weight * G_CONST * V_NOM
        return pack(drag, roll)

    n = 0
    sum_drag = 0.0
    sum_roll = 0.0
    for s in samples:
        v = float(s.get("v_ms") or s.get("v_mps") or s.get("v") or 0.0)
        if v <= 0.0:
            continue
        n += 1
        # ignorér vind i fallback; v_rel = v
        sum_drag += 0.5 * RHO_DEF * cda * (v ** 3)
        sum_roll += crr * weight * G_CONST * v

    drag = (sum_drag / n) if n else 0.0
    roll = (sum_roll / n) if n else 0.0
    return pack(drag, roll)


# ----------------- PROFIL-KANONISERING -----------------
def _scrub_profile(profile_in: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliser alias/kapitalisering og fjern dubletter/None."""
    p = dict(profile_in or {})

    # 1) Alias → kanonisk (alltid), og fjern original—også hvis begge finnes
    if "CdA" in p:
        if "cda" not in p or p.get("cda") is None:
            p["cda"] = p["CdA"]
        p.pop("CdA", None)
    if "Crr" in p:
        if "crr" not in p or p.get("crr") is None:
            p["crr"] = p["Crr"]
        p.pop("Crr", None)
    if "weightKg" in p:
        if "weight_kg" not in p or p.get("weight_kg") is None:
            p["weight_kg"] = p["weightKg"]
        p.pop("weightKg", None)

    # 2) Dropp None
    for k in list(p.keys()):
        if p[k] is None:
            del p[k]

    # 3) Koersjon til tall der relevant (tåler str/float/int)
    def _f(x):
        try:
            return float(x)
        except Exception:
            return None

    if "cda" in p:
        v = _f(p["cda"])
        if v is not None:
            p["cda"] = v
        else:
            p.pop("cda", None)
    if "crr" in p:
        v = _f(p["crr"])
        if v is not None:
            p["crr"] = v
        else:
            p.pop("crr", None)
    if "weight_kg" in p:
        v = _f(p["weight_kg"])
        if v is not None:
            p["weight_kg"] = v
        else:
            p.pop("weight_kg", None)

    return p


# ----------------- MIDlERTIDIG DEBUG-ENDepunkt (adapter passthrough) -----------------
@router.post("/debug/rb")
async def debug_rb(request: Request):
    """
    Minimal passthrough → kaller rs_power_json direkte med body som kommer inn.
    Forventer OBJECT: {"samples":[...], "profile":{...}, "estimat":{...}}
    Returnerer {"source":"rust"/"error", "out":<str>, "probe": <bool>, "err":<str|None>}
    """
    global rs_power_json, _adapter_import_error

    # Hvis adapter ikke er lastet (eller reload har tuklet), prøv én gang til
    if rs_power_json is None:
        rs_power_json = _load_rs_power_json()

    try:
        data = await request.json()
    except Exception as e:
        return {"source": "error", "out": "", "probe": False, "err": f"json body: {e!r}"}

    if rs_power_json is None:
        return {
            "source": "error",
            "out": "",
            "probe": False,
            "err": f"Rust adapter not available: {_adapter_import_error}",
        }

    prof = _scrub_profile(data.get("profile") or {})
    sam = data.get("samples") or []
    est = data.get("estimat") or data.get("estimate") or {}

    try:
        out = rs_power_json(sam, prof, est)
        return {"source": "rust", "out": out, "probe": False, "err": None}
    except Exception as e:
        return {"source": "error", "out": "", "probe": False, "err": repr(e)}

# ----------------- ANALYZE: RUST-FØRST + TIDLIG RETURN -----------------
# ----------------- ANALYZE: RUST-FØRST + TIDLIG RETURN -----------------
@router.post("/{sid}/analyze")
async def analyze_session(
    sid: str,
    request: Request,
    no_weather: bool = Query(False),
    force_recompute: bool = Query(False),
    debug: int = Query(0),
):
    want_debug = bool(debug)
    print(f"[SVR] >>> ANALYZE ENTER (Rust-first) sid={sid} debug={want_debug}")

    # ==================== PATCH 1: logg force_recompute tidlig ====================
    print(
        f"[SVR] >>> ANALYZE ENTER sid={sid} force_recompute={force_recompute}",
        file=sys.stderr,
    )
    # ============================================================================

    # ─────────────────────────────────────────────────────────────────────────────
    # FINAL OVERRIDE helper: sørg for at UI alltid matcher "wheel"-definisjonen
    # ─────────────────────────────────────────────────────────────────────────────
    def _final_ui_override(resp: Dict[str, Any]) -> Dict[str, Any]:
        try:
            m = (resp.get("metrics") or {})
            if not isinstance(m, dict):
                return resp

            wheel = m.get("model_watt_wheel")
            if wheel is None:
                wheel = m.get("total_watt")

            prof = m.get("profile_used") or {}
            eff = m.get("eff_used")
            if eff is None:
                try:
                    eff = float((prof or {}).get("crank_eff_pct", 95.5)) / 100.0
                except Exception:
                    eff = 0.955

            # clamp
            try:
                eff = float(eff)
            except Exception:
                eff = 0.955
            eff = max(0.50, min(1.0, eff))

            if wheel is not None:
                try:
                    wheel_f = float(wheel)
                except Exception:
                    return resp

                # UI-definisjon
                m["precision_watt"] = wheel_f
                m["total_watt"] = wheel_f

                # Diagnose/avansert
                m["precision_watt_crank"] = wheel_f / eff if eff > 0 else wheel_f
                m["eff_used"] = eff

                resp["metrics"] = m
        except Exception:
            # Ikke la override knekke responsen
            return resp
        return resp

    # ==================== WEATHER LOCK INITIALIZATION ====================
    # ─────────────────────────────────────────────────────────────────────
    # WEATHER LOCK: ved recompute (profilendring) låser vi vær til persisted
    # ─────────────────────────────────────────────────────────────────────
    locked_wx_used = None
    locked_wx_meta = None
    locked_wx_fp = None
    weather_locked = False

    # Selv om vi bypasser persisted *resultat* ved force_recompute,
    # så ønsker vi å gjenbruke samme vær som fasit/persisted (stabilt).
    if force_recompute:
        try:
            _p = _pick_best_persisted_result_path(sid)
            if _p is not None and _p.exists():
                with _p.open("r", encoding="utf-8-sig") as f:
                    _doc = json.load(f)
                locked_wx_used, locked_wx_meta, locked_wx_fp = _extract_persisted_weather(_doc)
                if locked_wx_used:
                    weather_locked = True
                    print(f"[SVR] weather_lock sid={sid} path={_p}", flush=True)
        except Exception as e:
            print(f"[SVR] weather_lock_failed sid={sid} err={e}", flush=True)

    # ==================== PATCH 2: persisted hit/bypass logging ====================
    if force_recompute:
        print(
            f"[SVR] persisted_bypass sid={sid} reason=force_recompute",
            file=sys.stderr,
        )
    else:
        persisted_path = _pick_best_persisted_result_path(sid)
        if persisted_path is not None:
            try:
                with persisted_path.open("r", encoding="utf-8-sig") as f:
                    doc = json.load(f)

                if isinstance(doc, dict) and _is_full_result_doc(doc):
                    dbg = doc.get("debug") or {}
                    if isinstance(dbg, dict):
                        dbg.setdefault("reason", "persisted_hit")
                        dbg.setdefault("persist_path", str(persisted_path))
                        doc["debug"] = dbg

                    doc.setdefault("source", "persisted")
                    print(
                        f"[SVR] persisted_hit sid={sid} path={persisted_path}",
                        file=sys.stderr,
                    )
                    return _final_ui_override(doc)
                else:
                    print(
                        f"[SVR] persisted_skip sid={sid} path={persisted_path} reason=not_full_doc",
                        file=sys.stderr,
                    )

            except Exception as e:
                print(
                    f"[SVR] persisted_read_failed sid={sid} path={persisted_path} err={e}",
                    file=sys.stderr,
                )
    # ==============================================================================

    # ==================== ORIGINAL ANALYZE LOGIC ====================

    # === SAFE BODY READ v2 (med BOM-strip + logging) ===
    try:
        raw = await request.body()
    except Exception as e:
        print(f"[SVR] ERROR reading body: {e!r}", flush=True)
        raw = b""

    # Normaliser til bytes
    if isinstance(raw, str):
        raw_bytes = raw.encode("utf-8", errors="ignore")
    else:
        raw_bytes = bytes(raw or b"")

    # Strip UTF-8 BOM hvis til stede (typisk fra PowerShell Set-Content -Encoding utf8)
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        print("[SVR] INFO: Stripped UTF-8 BOM from request body", flush=True)
        raw_bytes = raw_bytes[3:]

    text = raw_bytes.decode("utf-8", errors="ignore").strip()

    if text:
        try:
            body = json.loads(text)
        except Exception as e:
            print(
                f"[SVR] WARN: JSON decode failed, using empty body: {e!r}",
                flush=True,
            )
            body = {}
    else:
        body = {}
    # === END SAFE BODY READ v2 ===

    # --- T8: robust normalisering av body ---
    # Tillat at body kan være dict, list, str/bytes → form til {samples, profile, weather}
    def _coerce_payload(x):
        import json as _json

        # 1) str/bytes → parse
        if isinstance(x, (str, bytes, bytearray)):
            try:
                x = _json.loads(x)
            except Exception:
                x = {}
        # 2) list → anta samples
        if isinstance(x, list):
            return {"samples": x, "profile": {}, "weather": {}}
        # 3) dict → sørg for nøkler
        if isinstance(x, dict):
            out = dict(x)
            if "samples" not in out or not isinstance(out.get("samples"), list):
                out["samples"] = []
            if "profile" not in out or not isinstance(out.get("profile"), dict):
                out["profile"] = {}
            if "weather" not in out or not isinstance(out.get("weather"), dict):
                out["weather"] = {}
            return out
        # 4) alt annet → tom payload
        return {"samples": [], "profile": {}, "weather": {}}

    body = _coerce_payload(body)

    # Valider shape (lagre original info om klienten faktisk sendte profil)
    samples = body["samples"]
    profile_in = body["profile"]
    client_sent_profile = bool(profile_in)

    # === PATCH A: load samples from persisted session_<sid>.json if request omitted them ===
    if not isinstance(samples, list) or len(samples) == 0:
        sess_path = _pick_best_session_path(sid)
        if sess_path is not None:
            try:
                loaded = _load_samples_from_session_file(sess_path)
                body["samples"] = loaded
                samples = loaded  # <-- KRITISK: oppdater også lokal variabel
                if want_debug:
                    dbg = body.get("debug") or {}
                    if isinstance(dbg, dict):
                        dbg["used_fallback"] = True
                        dbg["session_path"] = str(sess_path)
                        dbg["samples_loaded"] = len(samples)
                        body["debug"] = dbg
                print(
                    f"[SVR] loaded_session_samples sid={sid} n={len(samples)} path={sess_path}",
                    file=sys.stderr,
                )
            except Exception as e:
                print(
                    f"[SVR] failed_load_session_samples sid={sid} path={sess_path} err={e}",
                    file=sys.stderr,
                )

    if not isinstance(samples, list) or not isinstance(profile_in, dict):
        raise HTTPException(status_code=400, detail="Missing 'samples' or 'profile'")

    # --- Trinn 8A: Guardrail for 'nominal' (kun i test-modus) ---
    test_mode = bool(int(os.environ.get("CG_TESTMODE", "0")))
    if not test_mode and isinstance(body, dict) and "nominal" in body:
        body.pop("nominal", None)

    # --- Trinn 8B: Payload capture (valgfri) ---
    try:
        if bool(int(os.environ.get("CG_DUMP_PAYLOAD", "0"))):
            LOGS = Path(__file__).resolve().parents[2] / "logs"
            LOGS.mkdir(exist_ok=True)
            dump_path = LOGS / "_t8_baseline_payload.json"
            # Lag et minimalt, trygt snapshot (samples + profile + weather + optional debug)
            payload_snapshot = {
                "samples": samples,
                "profile": profile_in or {},
                "weather": (body.get("weather") or {}),
                "debug": (body.get("debug") or {}),
            }
            with dump_path.open("w", encoding="utf-8") as f:
                json.dump(payload_snapshot, f, ensure_ascii=False)
    except Exception:
        # Ikke la capture feile requesten
        pass

    # --- Profil-normalisering (Patch A) ---
    profile = _ensure_profile_device((body.get("profile") or {}))
    body["profile"] = profile

    if not client_sent_profile:
        up = load_user_profile()
        profile = _ensure_profile_device(up)
        body["profile"] = profile

    # === PATCH B: apply profile_override after base profile is selected ===
    override = body.get("profile_override") or {}
    if isinstance(override, dict) and override:
        # allow weight_kg alias -> rider_weight_kg
        if "weight_kg" in override and "rider_weight_kg" not in override:
            override["rider_weight_kg"] = override["weight_kg"]
        if "total_weight_kg" in override and "rider_weight_kg" not in override:
            override["rider_weight_kg"] = override["total_weight_kg"]

        profile.update(override)
        body["profile"] = profile
        if want_debug:
            dbg = body.get("debug") or {}
            if isinstance(dbg, dict):
                dbg["override_applied"] = True
                dbg["override_keys"] = sorted(list(override.keys()))
                body["debug"] = dbg

    # --- TRINN 10.1: total weight (rider + bike) ---
    # Vi bevarer rider_weight_kg og bike_weight_kg separat i profile_used,
    # men 'weight_kg' som går til kjernen skal være SUM.
    try:
        rider_w = float(
            (
                profile.get("rider_weight_kg")
                if profile.get("rider_weight_kg") is not None
                else profile.get("weight_kg")
            )
            or 75.0
        )
    except Exception:
        rider_w = 75.0
    try:
        bike_w = float(profile.get("bike_weight_kg") or 8.0)
    except Exception:
        bike_w = 8.0

    total_w = rider_w + bike_w
    profile["weight_kg"] = total_w  # brukes av kjernen
    profile["total_weight_kg"] = total_w  # ren speil for tydelighet
    # --- END TRINN 10.1 ---

    # --- TRINN 10: Profile versioning inject ---
    # 1) hent subset for versjonering: klient → ellers disk
    profile_in = dict((body or {}).get("profile") or {})
    if profile_in:
        subset = {
            k: profile_in.get(k)
            for k in (
                "rider_weight_kg",
                "bike_type",
                "bike_weight_kg",
                "tire_width_mm",
                "tire_quality",
                "device",
            )
        }
    else:
        prof_disk = load_profile()
        subset = {
            k: prof_disk.get(k)
            for k in (
                "rider_weight_kg",
                "bike_type",
                "bike_weight_kg",
                "tire_width_mm",
                "tire_quality",
                "device",
            )
        }
    vinfo = compute_version(subset)  # {"version_hash","profile_version","version_at"}
    profile_version = vinfo["profile_version"]

    profile_scrubbed = _scrub_profile(profile)

    # ==================== PATCH: DEDUPE PROFILE KEYS FOR RUST ====================
    # Fjern duplicate keys før Rust-call for å unngå duplicate key errors i JSON-parser
    profile_scrubbed = _dedupe_profile_keys_for_rust(profile_scrubbed)
    # ==================== END PATCH ====================

    # --- Estimat (tredje-argument) ---
    estimat_cfg: Dict[str, Any] = {}
    if force_recompute:
        estimat_cfg["force"] = True
    if isinstance(body.get("estimat"), dict):
        estimat_cfg.update(body["estimat"])
    elif isinstance(body.get("estimate"), dict):
        estimat_cfg.update(body["estimate"])

    # === WX PATCH START ===
    # --- WEATHER: finn anker (lat/lon + ts_hour) ---
    hint = dict((body or {}).get("weather_hint") or {})
    center_lat, center_lon, ts_hour = _center_latlon_and_hour_from_samples(samples)

    if center_lat is None:
        center_lat = hint.get("lat_deg")
    if center_lon is None:
        center_lon = hint.get("lon_deg")
    if ts_hour is None:
        ts_hour = hint.get("ts_hour")

    wx_used: Optional[Dict[str, float]] = None
    wx_meta: Dict[str, Any] = {
        "provider": "open-meteo/era5",
        "lat_used": float(center_lat) if isinstance(center_lat, (int, float)) else None,
        "lon_used": float(center_lon) if isinstance(center_lon, (int, float)) else None,
        "ts_hour": int(ts_hour) if isinstance(ts_hour, (int, float)) else None,
        "height": "10m->2m",
        "unit_wind": "m/s",
        "cache_key": None,
    }

    fp = None

    # WEATHER LOCK: bruk låst vær hvis tilgjengelig
    if weather_locked:
        # 🔒 Bruk persisted vær nøyaktig (stabilt, "fasit")
        wx_used = dict(locked_wx_used or {})
        if isinstance(locked_wx_meta, dict) and locked_wx_meta:
            wx_meta = dict(locked_wx_meta)
        fp = locked_wx_fp or _wx_fp(wx_used)
        # sikre eksplisitt semantikk
        wx_used.setdefault("dir_is_from", True)
        wx_used["force"] = True
        print(
            f"[WX] locked sid={sid} T={wx_used.get('air_temp_c')}°C P={wx_used.get('air_pressure_hpa')}hPa "
            f"wind_ms={wx_used.get('wind_ms')} from={wx_used.get('wind_dir_deg')}° fp={fp[:8] if isinstance(fp,str) else fp}",
            flush=True,
        )
    else:
        # Tillat eksplisitt client-vær (dev/test), men ellers hent selv
        wx_payload = dict((body or {}).get("weather") or {})
        if wx_payload:
            w_ms = float(wx_payload.get("wind_ms", 0.0))
            w_dd = float(wx_payload.get("wind_dir_deg", 0.0))
            t_c = float(wx_payload.get("air_temp_c", 0.0))
            p_h = float(wx_payload.get("air_pressure_hpa", 0.0))
            wx_used = {
                "wind_ms": w_ms,  # forventet i m/s
                "wind_dir_deg": w_dd,  # fra-retning
                "air_temp_c": t_c,
                "air_pressure_hpa": p_h,
                "dir_is_from": True,  # eksplisitt semantikk
                "meta": {
                    "injected_client": True,
                    "reduce_factor": None,
                    "windspeed_10m_ms": None,
                },
            }
        else:
            if (
                isinstance(center_lat, (int, float))
                and isinstance(center_lon, (int, float))
                and isinstance(ts_hour, int)
            ):
                wx_meta["cache_key"] = f"om:{round(center_lat, 4)}:{round(center_lon, 4)}:{ts_hour}"
                wx_fetched = await _fetch_open_meteo_hour_ms(
                    float(center_lat), float(center_lon), int(ts_hour)
                )
                if wx_fetched:
                    wx_used = wx_fetched
                    wx_used["dir_is_from"] = True  # eksplisitt semantikk

    # Bygg third med weather hvis tilgjengelig
    third = dict(estimat_cfg)
    weather_applied = False

    if wx_used and not no_weather:
        # Normaliser til kanoniske navn for Rust-bindingen
        wind_ms_val = float(wx_used.get("wind_ms", 0.0))
        wind_dir_deg_val = float(wx_used.get("wind_dir_deg", 0.0))
        air_temp_c_val = float(wx_used.get("air_temp_c", 15.0))
        air_pressure_hpa_val = float(wx_used.get("air_pressure_hpa", 1013.25))

        # Oppdater third med kanoniske navn på toppnivå
        third.update(
            {
                "wind_ms": wind_ms_val,
                "wind_dir_deg": wind_dir_deg_val,
                "air_temp_c": air_temp_c_val,
                "air_pressure_hpa": air_pressure_hpa_val,
                "dir_is_from": True,
            }
        )

        # Behold metadata for serverens observabilitet
        third["weather_meta"] = wx_meta
        fp = fp or _wx_fp(wx_used)
        third["weather_fp"] = fp
        weather_applied = True

        try:
            print(
                f"[WX] hour={wx_meta['ts_hour']} lat={wx_meta['lat_used']:.5f} lon={wx_meta['lon_used']:.5f} "
                f"T={wx_used['air_temp_c']}°C P={wx_used['air_pressure_hpa']}hPa "
                f"wind_2m={wx_used['wind_ms']:.2f} m/s from={wx_used['wind_dir_deg']}° "
                f"(10m={wx_used.get('meta', {}).get('windspeed_10m_ms')} m/s, "
                f"factor={wx_used.get('meta', {}).get('reduce_factor')}) fp={fp[:8]}"
            )
        except Exception:
            pass
    else:
        # IKKE send 0-vær til Rust - fjern eventuelle vær-nøkler
        for k in [
            "wind_ms",
            "wind_dir_deg",
            "air_temp_c",
            "air_pressure_hpa",
            "dir_is_from",
        ]:
            third.pop(k, None)
        weather_applied = False
        if no_weather:
            print("[WX] weather disabled via no_weather flag")
        else:
            print("[WX] no weather available (missing lat/lon/ts_hour or fetch failed)")
    # === WX PATCH END ===

    # --- Enhetsheuristikk på samples (før mapping/Rust) ---
    samples = body.get("samples") or []
    samples = _apply_device_heuristics(samples, profile.get("device"))
    body["samples"] = samples  # hold body i sync

    # --- (VALGFRITT) NORMALISERING AV SAMPLES -> mapped ---
    def _coerce_f(x):
        try:
            return float(x)
        except Exception:
            return 0.0

    mapped = []
    for s in samples:
        if not isinstance(s, dict):
            continue
        t = _coerce_f(s.get("t", 0.0))
        v_ms = s.get("v_ms", s.get("v_mps", s.get("v")))
        v_ms = _coerce_f(v_ms)
        alt = _coerce_f(s.get("altitude_m", s.get("alt")))
        g = s.get("grade", s.get("slope"))
        try:
            g = float(g)
            has_g = True
        except Exception:
            has_g = False
        out_s = {"t": t, "v_ms": v_ms, "altitude_m": alt}
        if has_g:
            out_s["grade"] = g
        mv = s.get("moving")
        if isinstance(mv, bool):
            out_s["moving"] = mv
        hd = s.get("heading_deg", s.get("heading"))
        try:
            if hd is not None:
                out_s["heading_deg"] = float(hd)
        except Exception:
            pass
        mapped.append(out_s)

    # --- DEBUG PROBE: show what we actually pass to binding ---
    try:
        t_keys = sorted(list(third.keys()))
        wx_nested = third.get("weather") if isinstance(third.get("weather"), dict) else None
        print(
            "[SVR→RB] third keys:",
            t_keys,
            " wx_nested_keys=",
            (sorted(wx_nested.keys()) if wx_nested else None),
            " flat_wx=",
            {
                k: third.get(k)
                for k in (
                    "wind_ms",
                    "wind_dir_deg",
                    "air_temp_c",
                    "air_pressure_hpa",
                    "dir_is_from",
                )
            },
            flush=True,
        )
    except Exception:
        pass

    # =========================================
    # PATCH A — REBUILD ANALYSIS PAYLOAD
    # =========================================

    global rs_power_json
    if rs_power_json is None:
        rs_power_json = _load_rs_power_json()

    # ---------- HARD RUST SHORT-CIRCUIT ----------
    if rs_power_json is not None:
        try:
            # ✅ sender BOTH estimat og weather i tredje-argumentet
            r = rs_power_json(mapped, profile_scrubbed, third)
        except Exception as e:
            print(
                f"[SVR] [RUST] exception (no-fallback mode): {e!r}",
                file=sys.stderr,
                flush=True,
            )
            err_resp = {
                "source": "rust_error",
                "weather_applied": False,
                "metrics": {},
                "debug": {
                    "reason": "rust-exception",
                    "used_fallback": False,
                    "weather_source": "neutral",
                    "exception": repr(e),
                },
            }
            err_resp = _ensure_contract_shape(err_resp)
            err_resp = _final_ui_override(err_resp)
            try:
                _write_observability(err_resp)
            except Exception as e_log:
                print(f"[SVR][OBS] logging wrapper failed: {e_log!r}", flush=True)
            return err_resp

        resp: Dict[str, Any] = {}
        if isinstance(r, dict):
            resp = r
        else:
            try:
                resp = json.loads(r) if isinstance(r, (str, bytes, bytearray)) else {}
            except Exception as e:
                print(
                    f"[SVR] [RUST] json.loads failed (no-fallback): {e!r}",
                    file=sys.stderr,
                    flush=True,
                )
                err_resp = {
                    "source": "rust_error",
                    "weather_applied": False,
                    "metrics": {},
                    "debug": {
                        "reason": "adapter-nonjson",
                        "used_fallback": False,
                        "weather_source": "neutral",
                        "adapter_raw": (
                            r.decode() if isinstance(r, (bytes, bytearray)) else str(r)
                        ),
                        "exception": repr(e),
                    },
                }
                err_resp = _ensure_contract_shape(err_resp)
                err_resp = _final_ui_override(err_resp)
                try:
                    _write_observability(err_resp)
                except Exception as e_log:
                    print(f"[SVR][OBS] logging wrapper failed: {e_log!r}", flush=True)
                return err_resp

        # Injiser profile_used, deretter skaler (DEL / eff) og legg på profile_version
        try:
            resp = _inject_profile_used(resp, profile)

            # --- Trinn 5: anvend crank_eff_pct korrekt (rider power = wheel power / eta) ---
            metrics = resp.get("metrics") or {}

            # ==================== PATCH: PEDAL-BASED WATTS CANONICALIZATION ====================
            # Prefer pedal-based watts if present (avoids negative downhill "free energy" lowering average)
            if isinstance(metrics, dict) and "precision_watt_pedal" in metrics:
                metrics.setdefault("precision_watt_signed", metrics.get("precision_watt"))
                metrics.setdefault("total_watt_signed", metrics.get("total_watt"))
                metrics.setdefault("gravity_watt_signed", metrics.get("gravity_watt"))
                metrics.setdefault("model_watt_wheel_signed", metrics.get("model_watt_wheel"))

                metrics["precision_watt"] = metrics.get("precision_watt_pedal")
                metrics["total_watt"] = metrics.get("total_watt_pedal", metrics.get("model_watt_wheel_pedal"))
                metrics["gravity_watt"] = metrics.get("gravity_watt_pedal")
                metrics["model_watt_wheel"] = metrics.get("model_watt_wheel_pedal", metrics.get("model_watt_wheel"))
            # ==================== END PATCH ====================

            try:
                eff = float(profile.get("crank_eff_pct") or 95.5) / 100.0
            except Exception:
                eff = 0.955
            base_pw = metrics.get("precision_watt")
            if base_pw is None:
                base_pw = metrics.get("total_watt")
            if isinstance(base_pw, (int, float)) and eff > 0:
                scaled = float(base_pw) / eff  # DEL, ikke gang
                metrics["precision_watt"] = scaled
                if metrics.get("total_watt") is None:
                    metrics["total_watt"] = scaled

            pu = metrics.get("profile_used") or {}
            pu["profile_version"] = profile_version
            metrics["profile_used"] = pu

            # --- Legg til weather metadata i metrics ---
            if weather_applied and wx_used:
                metrics["weather_used"] = wx_used
                metrics["weather_meta"] = wx_meta
                metrics["weather_fp"] = fp if isinstance(fp, str) else _wx_fp(wx_used)
                metrics["weather_source"] = "locked" if weather_locked else metrics.get("weather_source")

            # --- Trinn 6: passiv kalibrering (MAE mot device_watts om tilstede) ---
            try:
                _pred_series = _t6_pick_predicted_series(resp)
                _dev_series = _t6_extract_device_watts(samples)

                mae = None
                status = "not_available"
                calibrated = False

                if _pred_series and any(isinstance(x, (int, float)) for x in _dev_series):
                    n = min(len(_pred_series), len(_dev_series))
                    if n >= 3:
                        pred = []
                        dev = []
                        for i in range(n):
                            di = _dev_series[i]
                            if isinstance(di, (int, float)):
                                pred.append(float(_pred_series[i]))
                                dev.append(float(di))
                        mae = _t6_series_mae(pred, dev)
                        if mae is not None:
                            calibrated = True
                            status = "ok"
                        else:
                            status = "not_enough_overlap"
                    else:
                        status = "not_enough_samples"
                else:
                    status = "not_available"

                metrics["calibration_mae"] = mae
                metrics["calibrated"] = calibrated
                metrics["calibration_status"] = status

                if os.getenv("CG_CALIBRATE", "") == "1":

                    def _mean(xs):
                        xs2 = [float(x) for x in xs if isinstance(x, (int, float))]
                        return (sum(xs2) / len(xs2)) if xs2 else None

                    _t6_calib_csv_append(
                        sid=sid,
                        n=min(len(_pred_series), len(_dev_series)),
                        calibrated=calibrated,
                        status=status,
                        mae=mae,
                        mean_pred=_mean(_pred_series),
                        mean_dev=_mean(_dev_series),
                    )
            except Exception:
                metrics.setdefault("calibration_mae", None)
                metrics.setdefault("calibrated", False)
                metrics.setdefault("calibration_status", "fallback")

            # --- Trinn 15: heuristisk presisjonsindikator + benchmark-logg ---
            try:
                profile_used_t15 = (
                    (metrics.get("profile_used") or resp.get("profile_used") or {})
                    if isinstance(metrics, dict)
                    else {}
                )
                wx_used_t15 = (metrics.get("weather_used") or resp.get("weather_used") or {})
                est_range, hint, completeness = compute_estimated_error_and_hint(
                    profile_used_t15 or {}, wx_used_t15 or {}
                )

                metrics["estimated_error_pct_range"] = est_range
                metrics["precision_quality_hint"] = hint

                try:
                    resp_obj = resp if isinstance(resp, dict) else {}
                    profile_version_bm = (
                        resp_obj.get("profile_version")
                        or (profile_used_t15.get("profile_version") if isinstance(profile_used_t15, dict) else "")
                        or ""
                    )
                    samples_in = (body.get("samples") if isinstance(body, dict) else None) or []
                    has_device = _body_has_device_watts(samples_in)
                    calib_mae = metrics.get("calibration_mae")

                    ok = append_benchmark_candidate(
                        ride_id=sid,
                        profile_version=profile_version_bm,
                        calibration_mae=calib_mae,
                        estimated_error_pct_range=est_range if isinstance(est_range, list) else [None, None],
                        profile_completeness=completeness,
                        has_device_data=has_device,
                        hint=hint,
                    )
                    print(f"[SVR][T15] benchmark_append ok={ok}", flush=True)
                except Exception as _e:
                    print(f"[SVR][T15] benchmark_append failed: {_e!r}", flush=True)
            except Exception as e:
                print(f"[SVR][T15] heuristic failed: {e!r}", flush=True)

            resp["metrics"] = metrics
            resp["weather_applied"] = weather_applied
        except Exception as e:
            print(f"[SVR] Error processing Rust response: {e}")

        if isinstance(resp, dict):
            # Pakk flat → metrics hvis nødvendig
            if "metrics" not in resp:
                keys = ("precision_watt", "drag_watt", "rolling_watt", "total_watt")
                if any(k in resp for k in keys):
                    mtmp = {k: resp.pop(k) for k in keys if k in resp}
                    if "profile_used" in resp and isinstance(resp["profile_used"], dict):
                        mtmp.setdefault("profile_used", resp["profile_used"])
                    resp["metrics"] = mtmp

            resp.setdefault("source", "rust_1arg")
            if "weather_applied" not in resp:
                resp["weather_applied"] = weather_applied

            m = resp.setdefault("metrics", {})
            pu = m.setdefault("profile_used", dict(profile))
            if isinstance(pu, dict):
                pu.setdefault("profile_version", profile_version)
                m["profile_used"] = pu
            m.setdefault("weather_applied", weather_applied)
            m.setdefault("total_watt", m.get("precision_watt", 0.0))

            # Legg til weather metadata hvis ikke allerede satt (med weather_lock guard)
            if not weather_locked and weather_applied and wx_used and "weather_used" not in m:
                m["weather_used"] = wx_used
                m["weather_meta"] = wx_meta
                m["weather_fp"] = _wx_fp(wx_used)

            dbg = resp.setdefault("debug", {})
            dbg.setdefault("reason", "ok")
            dbg["force_recompute"] = bool(force_recompute)
            dbg["persist_ignored"] = bool(force_recompute)
            dbg["ignored_persist"] = bool(force_recompute)
            dbg["used_fallback"] = False
            dbg["weather_locked"] = bool(weather_locked)  # <-- Viktig: vis at vær er låst
            if not dbg.get("weather_source"):
                dbg["weather_source"] = "historical" if weather_applied else "neutral"
            if force_recompute:
                dbg["estimat_cfg_used"] = dict(estimat_cfg)

            rust_has_metrics = isinstance(m, dict) and any(
                k in m for k in ("precision_watt", "drag_watt", "rolling_watt", "total_watt")
            )
            if rust_has_metrics:
                # --- Weather source propagation (Trinn 9) ---
                try:
                    _m = resp.get("metrics") or {}
                    _wm = (_m.get("weather_meta") or {})
                    _prov = _wm.get("provider") or _wm.get("source") or _wm.get("name")
                    resp["weather_source"] = _prov or "open-meteo"
                    _m["weather_source"] = resp["weather_source"]
                    resp["metrics"] = _m
                except Exception:
                    resp.setdefault("weather_source", "unknown")
                    resp.setdefault("metrics", {}).setdefault("weather_source", resp["weather_source"])

                # --- TRINN 10: Profile versioning inject ---
                resp["profile_version"] = profile_version
                mu_top = resp.setdefault("profile_used", {})
                mu_top["rider_weight_kg"] = rider_w
                mu_top["bike_weight_kg"] = bike_w
                mu_top["weight_kg"] = total_w
                mu_top["total_weight_kg"] = total_w
                mu_top.update({**profile, "profile_version": profile_version})

                # --- Trinn 7: kontraktsikre + observability ---
                try:
                    ensured = _ensure_contract_shape(resp)

                    # Mirror profile_used inn i metrics.profile_used
                    mu_top = ensured.setdefault("profile_used", {})
                    mm = ensured.setdefault("metrics", {})
                    mm.setdefault("profile_used", {})
                    mm["profile_used"] = dict(mu_top)

                    # ✅ FINAL OVERRIDE rett før vi skriver/returnerer
                    ensured = _final_ui_override(ensured)

                    _write_observability(ensured)

                    # Ride-specific result logging
                    rid = str(sid)
                    safe = re.sub(r"[^0-9A-Za-z_-]+", "", rid)
                    outdir = Path("logs") / "results"
                    outdir.mkdir(parents=True, exist_ok=True)
                    (outdir / f"result_{safe}.json").write_text(
                        json.dumps(
                            ensured,
                            ensure_ascii=False,
                            indent=2,
                            separators=(",", ": "),
                        ),
                        encoding="utf-8",
                    )

                    return ensured
                except Exception as e:
                    print(f"[SVR][OBS] logging wrapper failed: {e!r}", flush=True)
                    resp2 = _ensure_contract_shape(resp)
                    resp2 = _final_ui_override(resp2)
                    return resp2
            else:
                # --- PATCH B: RUST ga ikke gyldige metrics (no-fallback) ---
                print(
                    "[SVR] [RUST] missing/invalid metrics (no-fallback)",
                    file=sys.stderr,
                    flush=True,
                )
                err = {
                    "source": "rust_error",
                    "weather_applied": False,
                    "metrics": {},
                    "debug": {
                        "reason": "no-metrics-from-rust",
                        "used_fallback": False,
                        "weather_source": ("historical" if weather_applied else "neutral"),
                        "adapter_resp_keys": list(resp.keys()) if isinstance(resp, dict) else [],
                        "metrics_seen": list((m or {}).keys()) if isinstance(m, dict) else [],
                    },
                }
                err = _ensure_contract_shape(err)
                err = _final_ui_override(err)
                try:
                    _write_observability(err)
                except Exception as e:
                    print(f"[SVR][OBS] logging wrapper failed: {e!r}", flush=True)
                return err

    # --- PATCH C: REN fallback_py-gren (ingen Rust-metrics tilgjengelig) ---
    weather_flag = bool(wx_used) and not no_weather

    # Bygg profile_used med totalvekt-informasjon for fallback
    profile_used = {
        "cda": float(profile.get("cda")) if profile.get("cda") is not None else 0.30,
        "crr": float(profile.get("crr")) if profile.get("crr") is not None else 0.004,
        "weight_kg": total_w,
        "rider_weight_kg": rider_w,
        "bike_weight_kg": bike_w,
        "total_weight_kg": total_w,
        "crank_eff_pct": float(profile.get("crank_eff_pct"))
        if profile.get("crank_eff_pct") is not None
        else 95.5,
        "device": profile.get("device") or DEFAULT_DEVICE,
        "profile_version": profile_version,
    }

    # Kall fallback-motoren (Python-fysikk)
    fallback_metrics = _fallback_metrics(
        mapped,
        profile,  # NB: profile, ikke profile_used
        weather_applied=weather_flag,
        profile_used=profile_used,
    )

    # Hvis vi faktisk har wx_used: speil det inn i metrics slik at CLI kan verifisere (med weather_lock guard)
    if not weather_locked and weather_flag and wx_used:
        try:
            fallback_metrics.setdefault("weather_used", wx_used)
            fallback_metrics.setdefault("weather_meta", wx_meta)
            fallback_metrics.setdefault("weather_fp", _wx_fp(wx_used))
        except Exception:
            pass

    # --- Trinn 15: Heuristisk presisjonsindikator for fallback ---
    try:
        est_range, hint, completeness = compute_estimated_error_and_hint(profile_used, wx_used or {})
        fallback_metrics["estimated_error_pct_range"] = est_range
        fallback_metrics["precision_quality_hint"] = hint
        print(f"[SVR][T15] (fallback) → est_range={est_range} hint={hint}")
    except Exception as e:
        print(f"[SVR][T15] (fallback) compute_estimated_error_and_hint failed: {e}")

    resp = {
        "source": "fallback_py",
        "weather_applied": weather_flag,
        "metrics": fallback_metrics,
        "debug": {
            "reason": "fallback_py",
            "used_fallback": True,
            "weather_source": "neutral",  # oppdateres under
            "weather_locked": bool(weather_locked),
            "adapter_resp_keys": [],
            "metrics_seen": list(fallback_metrics.keys()),
        },
    }

    # --- Weather source propagation (Trinn 9) ---
    try:
        _m = resp.get("metrics") or {}
        _wm = (_m.get("weather_meta") or {})
        _prov = _wm.get("provider") or _wm.get("source") or _wm.get("name")
        resp["weather_source"] = _prov or "open-meteo"
        _m["weather_source"] = resp["weather_source"]
        resp["metrics"] = _m
    except Exception:
        resp.setdefault("weather_source", "unknown")
        resp.setdefault("metrics", {}).setdefault("weather_source", resp["weather_source"])

    # --- TRINN 10: Profile versioning inject ---
    resp["profile_version"] = profile_version
    mu_top = resp.setdefault("profile_used", {})
    mu_top["rider_weight_kg"] = rider_w
    mu_top["bike_weight_kg"] = bike_w
    mu_top["weight_kg"] = total_w
    mu_top["total_weight_kg"] = total_w
    mu_top.update({**profile, "profile_version": profile_version})

    # Trinn 7: kontraktsikre + observability før return
    resp = _ensure_contract_shape(resp)

    # --- TRINN 10: mirror profile_used inn i metrics.profile_used også ---
    mu_top = resp.setdefault("profile_used", {})
    mm = resp.setdefault("metrics", {})
    mm.setdefault("profile_used", {})
    mm["profile_used"] = dict(mu_top)

    # ✅ FINAL OVERRIDE rett før vi logger/returnerer fallback
    resp = _final_ui_override(resp)

    try:
        _write_observability(resp)

        # --- Ride-specific result logging ---
        rid = str(sid)
        safe = re.sub(r"[^0-9A-Za-z_-]+", "", rid)
        outdir = Path("logs") / "results"
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / f"result_{safe}.json").write_text(
            json.dumps(
                resp,
                ensure_ascii=False,
                indent=2,
                separators=(",", ": "),
            ),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[SVR][OBS] logging wrapper failed (fb): {e!r}", flush=True)

    return resp



@router.get("/{session_id}")
def get_session(session_id: str) -> Dict[str, Any]:
    """
    Returner enkel sessions-respons, med Precision Watt hentet fra
    enten _debug/result_<id>.json (fasit) eller logs/results/result_<id>.json (fallback).
    I tillegg returnerer vi litt debug-info om hvilke paths som ble sjekket.
    """

    base_dir = os.getcwd()
    debug_path = os.path.join(base_dir, "_debug", f"result_{session_id}.json")
    results_path = os.path.join(base_dir, "logs", "results", f"result_{session_id}.json")

    debug_exists = os.path.exists(debug_path)
    results_exists = os.path.exists(results_path)

    doc: Optional[Dict[str, Any]] = None
    source = None  # liten debug-tag så vi ser hva som brukes

    debug_error: Optional[str] = None

    # 1) Prøv _debug først (sanntidsanalyse fra scriptet)
    if debug_exists:
        try:
            # utf-8-sig stripper BOM automatisk (løser JSONDecodeError på BOM)
            with open(debug_path, "r", encoding="utf-8-sig") as f:
                doc = json.load(f)
                source = "_debug"
        except Exception as e_any:
            debug_error = f"debug read error: {e_any!r}"
            doc = None

    # 2) Hvis vi ikke fikk debug-doc, prøv logs/results som fallback
    if doc is None and results_exists:
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                doc = json.load(f)
                source = "logs/results"
        except Exception:
            doc = None

    # 3) Hvis vi fant en doc et av stedene, trekk ut metrics + kjente felter
    if doc is not None:
        metrics = doc.get("metrics") or {}

        precision_watt = metrics.get("precision_watt")
        precision_watt_ci = metrics.get("precision_watt_ci")

        return {
            "session_id": session_id,
            "precision_watt": precision_watt,
            "precision_watt_ci": precision_watt_ci,
            "strava_activity_id": doc.get("strava_activity_id"),
            "publish_state": doc.get("publish_state"),
            "publish_time": doc.get("publish_time"),
            "publish_hash": doc.get("publish_hash", ""),
            "publish_error": doc.get("publish_error"),
            # ekstra debug-felt
            "analysis_source": source,
            "raw_has_metrics": bool(metrics),
            "base_dir": base_dir,
            "debug_path": debug_path,
            "debug_exists": debug_exists,
            "results_path": results_path,
            "results_exists": results_exists,
            "debug_error": debug_error,
        }

    # 4) Fallback – vi fant ingen result-fil for denne økten
    return {
        "session_id": session_id,
        "precision_watt": None,
        "precision_watt_ci": None,
        "strava_activity_id": None,
        "publish_state": None,
        "publish_time": None,
        "publish_hash": "",
        "publish_error": None,
        # ekstra debug-felt
        "analysis_source": None,
        "raw_has_metrics": False,
        "base_dir": base_dir,
        "debug_path": debug_path,
        "debug_exists": debug_exists,
        "results_path": results_path,
        "results_exists": results_exists,
        "debug_error": debug_error,
    }