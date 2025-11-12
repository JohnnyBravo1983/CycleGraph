# server/routes/sessions.py
from __future__ import annotations
from cli.profile_binding import load_user_profile, compute_profile_version, binding_from

import json
import sys
import traceback
import hashlib
import math
import time
import os
import csv
import datetime
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

from fastapi import APIRouter, HTTPException, Request, Query

# Primær import med trygg fallback (brukes i standardstien)
try:
    from cli.rust_bindings import rs_power_json  # ✅ primær
except Exception:
    try:
        from cyclegraph.cli.rust_bindings import rs_power_json  # ✅ pakket namespace fallback
    except Exception as e_imp:
        rs_power_json = None  # type: ignore
        _adapter_import_error = e_imp

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

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
    try:
        data = await request.json()
    except Exception as e:
        return {"source": "error", "out": "", "probe": False, "err": f"json body: {e}"}

    if rs_power_json is None:
        err_msg = (
            f"Rust adapter import error: {_adapter_import_error}"
            if "_adapter_import_error" in globals()
            else "Rust adapter not available"
        )
        return {"source": "error", "out": "", "probe": False, "err": err_msg}

    # Scrub profile for å unngå dubletter/alias i passthrough
    prof = _scrub_profile(data.get("profile") or {})
    sam = data.get("samples") or []
    est = data.get("estimat") or data.get("estimate") or {}

    try:
        out = rs_power_json(sam, prof, est)
        return {"source": "rust", "out": out, "probe": False, "err": None}
    except Exception as e:
        return {"source": "error", "out": "", "probe": False, "err": repr(e)}




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

    # Les body trygt
    try:
        body = await request.json()
    except Exception:
        body = {}

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
                "debug": (body.get("debug") or {})
            }
            with dump_path.open("w", encoding="utf-8") as f:
                json.dump(payload_snapshot, f, ensure_ascii=False)
    except Exception:
        # Ikke la capture feile requesten
        pass

    # --- Profil-normalisering (Patch A) ---
    profile = _ensure_profile_device((body.get("profile") or {}))
    body["profile"] = profile

    # Hvis klient ikke sendte profil, bruk lagret brukerprofil
    if not client_sent_profile:
        up = load_user_profile()
        profile = _ensure_profile_device(up)
        body["profile"] = profile

    # --- TRINN 10.1: total weight (rider + bike) ---
    # Vi bevarer rider_weight_kg og bike_weight_kg separat i profile_used,
    # men 'weight_kg' som går til kjernen skal være SUM.
    try:
        rider_w = float((profile.get("rider_weight_kg") if profile.get("rider_weight_kg") is not None else profile.get("weight_kg")) or 75.0)
    except Exception:
        rider_w = 75.0
    try:
        bike_w = float(profile.get("bike_weight_kg") or 8.0)
    except Exception:
        bike_w = 8.0

    total_w = rider_w + bike_w
    profile["weight_kg"] = total_w              # brukes av kjernen
    profile["total_weight_kg"] = total_w        # ren speil for tydelighet
    # --- END TRINN 10.1 ---

    # --- TRINN 10: Profile versioning inject ---
    from server.utils.versioning import compute_version, load_profile

    # 1) hent subset for versjonering: klient → ellers disk
    profile_in = dict((body or {}).get("profile") or {})
    if profile_in:
        subset = {k: profile_in.get(k) for k in ("rider_weight_kg","bike_type","bike_weight_kg","tire_width_mm","tire_quality","device")}
    else:
        prof_disk = load_profile()
        subset = {k: prof_disk.get(k) for k in ("rider_weight_kg","bike_type","bike_weight_kg","tire_width_mm","tire_quality","device")}
    vinfo = compute_version(subset)  # {"version_hash","profile_version","version_at"}
    profile_version = vinfo["profile_version"]

    profile_scrubbed = _scrub_profile(profile)

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

    if center_lat is None: center_lat = hint.get("lat_deg")
    if center_lon is None: center_lon = hint.get("lon_deg")
    if ts_hour   is None:  ts_hour   = hint.get("ts_hour")

    wx_used: Optional[Dict[str, float]] = None
    wx_meta: Dict[str, Any] = {
        "provider":  "open-meteo/era5",
        "lat_used":  float(center_lat) if isinstance(center_lat, (int,float)) else None,
        "lon_used":  float(center_lon) if isinstance(center_lon, (int,float)) else None,
        "ts_hour":   int(ts_hour) if isinstance(ts_hour, (int,float)) else None,
        "height":    "10m->2m",
        "unit_wind": "m/s",
        "cache_key": None,
    }

    # Tillat eksplisitt client-vær (dev/test), men ellers hent selv
    wx_payload = dict((body or {}).get("weather") or {})
    if wx_payload:
        w_ms = float(wx_payload.get("wind_ms", 0.0))
        w_dd = float(wx_payload.get("wind_dir_deg", 0.0))
        t_c  = float(wx_payload.get("air_temp_c", 0.0))
        p_h  = float(wx_payload.get("air_pressure_hpa", 0.0))
        wx_used = {
            "wind_ms":          w_ms,  # forventet i m/s
            "wind_dir_deg":     w_dd,  # fra-retning
            "air_temp_c":       t_c,
            "air_pressure_hpa": p_h,
            "dir_is_from":      True,  # <-- NYTT: eksplisitt semantikk
            "meta": { "injected_client": True, "reduce_factor": None, "windspeed_10m_ms": None }
        }
    else:
        if isinstance(center_lat, (int,float)) and isinstance(center_lon, (int,float)) and isinstance(ts_hour, int):
            wx_meta["cache_key"] = f"om:{round(center_lat,4)}:{round(center_lon,4)}:{ts_hour}"
            wx_fetched = await _fetch_open_meteo_hour_ms(float(center_lat), float(center_lon), int(ts_hour))
            if wx_fetched:
                wx_used = wx_fetched
                wx_used["dir_is_from"] = True  # <-- NYTT: eksplisitt semantikk

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
        third.update({
            "wind_ms": wind_ms_val,
            "wind_dir_deg": wind_dir_deg_val,
            "air_temp_c": air_temp_c_val,
            "air_pressure_hpa": air_pressure_hpa_val,
            "dir_is_from": True
        })

        # Behold metadata for serverens observabilitet
        third["weather_meta"] = wx_meta
        fp = _wx_fp(wx_used)
        third["weather_fp"] = fp
        weather_applied = True

        try:
            print(
                f"[WX] hour={wx_meta['ts_hour']} lat={wx_meta['lat_used']:.5f} lon={wx_meta['lon_used']:.5f} "
                f"T={wx_used['air_temp_c']}°C P={wx_used['air_pressure_hpa']}hPa "
                f"wind_2m={wx_used['wind_ms']:.2f} m/s from={wx_used['wind_dir_deg']}° "
                f"(10m={wx_used.get('meta',{}).get('windspeed_10m_ms')} m/s, "
                f"factor={wx_used.get('meta',{}).get('reduce_factor')}) fp={fp[:8]}"
            )
        except Exception:
            pass
    else:
        # IKKE send 0-vær til Rust - fjern eventuelle vær-nøkler
        for k in ["wind_ms", "wind_dir_deg", "air_temp_c", "air_pressure_hpa", "dir_is_from"]:
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
            g = float(g); has_g = True
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
            {k: third.get(k) for k in ("wind_ms","wind_dir_deg","air_temp_c","air_pressure_hpa","dir_is_from")},
            flush=True,
        )
    except Exception:
        pass

    # ---------- HARD RUST SHORT-CIRCUIT ----------
    if rs_power_json is not None:
        try:
            # ✅ sender BOTH estimat og weather i tredje-argumentet
            r = rs_power_json(mapped, profile_scrubbed, third)
        except Exception as e:
            print(f"[SVR] [RUST] exception (no-fallback mode): {e!r}", file=sys.stderr, flush=True)
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
            try:
                _write_observability(err_resp)
            except Exception as e_log:
                print(f"[SVR][OBS] logging wrapper failed: {e_log!r}", flush=True)
            return err_resp

        resp: Dict[str, Any] = {}
        if isinstance(r, dict):
            resp = r
            # Injiser profile_used, deretter skaler (DEL / eff) og legg på profile_version
            try:
                resp = _inject_profile_used(resp, profile)

                # --- Trinn 5: anvend crank_eff_pct korrekt (rider power = wheel power / eta) ---
                metrics = resp.get("metrics") or {}
                try:
                    eff = float(profile.get("crank_eff_pct") or 95.5) / 100.0
                except Exception:
                    eff = 0.955
                base_pw = metrics.get("precision_watt")
                if base_pw is None:
                    base_pw = metrics.get("total_watt")
                if isinstance(base_pw, (int, float)) and eff > 0:
                    scaled = float(base_pw) / eff  # <-- viktig: DEL, ikke gang
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
                    metrics["weather_fp"] = _wx_fp(wx_used)

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

                resp["metrics"] = metrics
                resp["weather_applied"] = weather_applied
            except Exception:
                pass
        else:
            try:
                resp = json.loads(r) if isinstance(r, (str, bytes, bytearray)) else {}
                # Injiser profile_used, deretter skaler (DEL / eff) og legg på profile_version
                resp = _inject_profile_used(resp, profile)

                # --- Trinn 5: anvend crank_eff_pct korrekt (rider power = wheel power / eta) ---
                metrics = resp.get("metrics") or {}
                try:
                    eff = float(profile.get("crank_eff_pct") or 95.5) / 100.0
                except Exception:
                    eff = 0.955
                base_pw = metrics.get("precision_watt")
                if base_pw is None:
                    base_pw = metrics.get("total_watt")
                if isinstance(base_pw, (int, float)) and eff > 0:
                    scaled = float(base_pw) / eff  # <-- viktig: DEL, ikke gang
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
                    metrics["weather_fp"] = _wx_fp(wx_used)

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

                resp["metrics"] = metrics
                resp["weather_applied"] = weather_applied
            except Exception as e:
                print(f"[SVR] [RUST] json.loads failed (no-fallback): {e!r}", file=sys.stderr, flush=True)
                err_resp = {
                    "source": "rust_error",
                    "weather_applied": False,
                    "metrics": {},
                    "debug": {
                        "reason": "adapter-nonjson",
                        "used_fallback": False,
                        "weather_source": "neutral",
                        "adapter_raw": (r.decode() if isinstance(r, (bytes, bytearray)) else str(r)),
                        "exception": repr(e),
                    },
                }
                err_resp = _ensure_contract_shape(err_resp)
                try:
                    _write_observability(err_resp)
                except Exception as e_log:
                    print(f"[SVR][OBS] logging wrapper failed: {e_log!r}", flush=True)
                return err_resp

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

            # Legg til weather metadata hvis ikke allerede satt
            if weather_applied and wx_used and "weather_used" not in m:
                m["weather_used"] = wx_used
                m["weather_meta"] = wx_meta
                m["weather_fp"] = _wx_fp(wx_used)

            dbg = resp.setdefault("debug", {})
            dbg.setdefault("reason", "ok")
            dbg["force_recompute"] = bool(force_recompute)
            dbg["persist_ignored"] = bool(force_recompute)
            dbg["ignored_persist"] = bool(force_recompute)
            dbg["used_fallback"] = False
            if not dbg.get("weather_source"):
                dbg["weather_source"] = "historical" if weather_applied else "neutral"
            if force_recompute:
                dbg["estimat_cfg_used"] = dict(estimat_cfg)

            rust_has_metrics = isinstance(m, dict) and any(
                k in m for k in ("precision_watt", "drag_watt", "rolling_watt", "total_watt")
            )
            if rust_has_metrics:
                # --- Trinn 9: weather_source til toppnivå + metrics (før kontraktsikring / return) ---
                # --- Weather source propagation (Trinn 9) ---
                try:
                    _m = resp.get("metrics") or {}
                    _wm = (_m.get("weather_meta") or {})
                    _prov = _wm.get("provider") or _wm.get("source") or _wm.get("name")
                    resp["weather_source"] = _prov or "open-meteo"
                    _m["weather_source"] = resp["weather_source"]
                    resp["metrics"] = _m
                except Exception:
                    # Hold respons stabil selv om weather_meta mangler
                    resp.setdefault("weather_source", "unknown")
                    resp.setdefault("metrics", {}).setdefault("weather_source", resp["weather_source"])

                # --- TRINN 10: Profile versioning inject ---
                resp["profile_version"] = profile_version
                mu_top = resp.setdefault("profile_used", {})
                # Oppdater profile_used med totalvekt-informasjon
                mu_top["rider_weight_kg"] = rider_w
                mu_top["bike_weight_kg"] = bike_w
                mu_top["weight_kg"] = total_w          # total
                mu_top["total_weight_kg"] = total_w    # alias for klarhet
                mu_top.update({**profile, "profile_version": profile_version})

                # --- Trinn 7: kontraktsikre + observability ---
                try:
                    ensured = _ensure_contract_shape(resp)
                    
                    # --- TRINN 10: mirror profile_used inn i metrics.profile_used også ---
                    mu_top = ensured.setdefault("profile_used", {})
                    mm = ensured.setdefault("metrics", {})
                    mm.setdefault("profile_used", {})
                    # sørg for identisk speiling
                    mm["profile_used"] = dict(mu_top)
                    # --- END TRINN 10 ---
                    
                    _write_observability(ensured)
                    return ensured
                except Exception as e:
                    print(f"[SVR][OBS] logging wrapper failed: {e!r}", flush=True)
                    return _ensure_contract_shape(resp)
            else:
                # --- PATCH B: RUST ga ikke gyldige metrics (no-fallback) ---
                print("[SVR] [RUST] missing/invalid metrics (no-fallback)", file=sys.stderr, flush=True)
                err = {
                    "source": "rust_error",
                    "weather_applied": False,
                    "metrics": {},
                    "debug": {
                        "reason": "no-metrics-from-rust",
                        "used_fallback": False,
                        "weather_source": "historical" if weather_applied else "neutral",
                        "adapter_resp_keys": list(resp.keys()) if isinstance(resp, dict) else [],
                        "metrics_seen": list((m or {}).keys()) if isinstance(m, dict) else [],
                    },
                }
                # Trinn 7: kontraktsikre + observability for feilsvar også
                err = _ensure_contract_shape(err)
                try:
                    _write_observability(err)
                except Exception as e:
                    print(f"[SVR][OBS] logging wrapper failed: {e!r}", flush=True)
                return err

    # --- PATCH C: REN fallback_py-gren (ingen Rust-metrics tilgjengelig) ---
    # Bygg profile_used med totalvekt-informasjon for fallback
    profile_used = {
        "cda": float(profile.get("cda")) if profile.get("cda") is not None else 0.30,
        "crr": float(profile.get("crr")) if profile.get("crr") is not None else 0.004,
        "weight_kg": total_w,
        "rider_weight_kg": rider_w,
        "bike_weight_kg": bike_w,
        "total_weight_kg": total_w,
        "crank_eff_pct": float(profile.get("crank_eff_pct")) if profile.get("crank_eff_pct") is not None else 95.5,
        "device": profile.get("device") or DEFAULT_DEVICE,
        "profile_version": profile_version
    }

    fallback_metrics = _fallback_metrics(
        mapped,
        profile,                # NB: profile, ikke profile_used
        weather_applied=False,  # fallback: behandle som uten vær
        profile_used=profile_used,  # inkluderer profile_version og totalvekt
    )

    resp = {
        "source": "fallback_py",
        "weather_applied": False,
        "metrics": fallback_metrics,
        "debug": {
            "reason": "fallback_py",
            "used_fallback": True,
            "weather_source": "neutral",
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
        # Hold respons stabil selv om weather_meta mangler
        resp.setdefault("weather_source", "unknown")
        resp.setdefault("metrics", {}).setdefault("weather_source", resp["weather_source"])

    # --- TRINN 10: Profile versioning inject ---
    resp["profile_version"] = profile_version
    mu_top = resp.setdefault("profile_used", {})
    # Oppdater profile_used med totalvekt-informasjon
    mu_top["rider_weight_kg"] = rider_w
    mu_top["bike_weight_kg"] = bike_w
    mu_top["weight_kg"] = total_w          # total
    mu_top["total_weight_kg"] = total_w    # alias for klarhet
    mu_top.update({**profile, "profile_version": profile_version})

    # Trinn 7: kontraktsikre + observability før return
    resp = _ensure_contract_shape(resp)
    
    # --- TRINN 10: mirror profile_used inn i metrics.profile_used også ---
    mu_top = resp.setdefault("profile_used", {})
    mm = resp.setdefault("metrics", {})
    mm.setdefault("profile_used", {})
    # sørg for identisk speiling
    mm["profile_used"] = dict(mu_top)
    # --- END TRINN 10 ---
    
    try:
        _write_observability(resp)
    except Exception as e:
        print(f"[SVR][OBS] logging wrapper failed (fb): {e!r}", flush=True)
    return resp