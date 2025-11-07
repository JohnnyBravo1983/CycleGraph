# server/routes/sessions.py
from __future__ import annotations
from cli.profile_binding import load_user_profile, compute_profile_version, binding_for

import json
import sys
import traceback
from typing import Any, Dict

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
    import os
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

    # Valider shape (lagre original info om klienten faktisk sendte profil)
    samples = list((body or {}).get("samples") or [])
    profile_in = dict((body or {}).get("profile") or {})
    client_sent_profile = bool(profile_in)

    if not isinstance(samples, list) or not isinstance(profile_in, dict):
        raise HTTPException(status_code=400, detail="Missing 'samples' or 'profile'")

    # --- Profil-normalisering (Patch A) ---
    profile = _ensure_profile_device((body.get("profile") or {}))
    body["profile"] = profile

    # Hvis klient ikke sendte profil, bruk lagret brukerprofil
    if not client_sent_profile:
        up = load_user_profile()
        profile = _ensure_profile_device(up)
        body["profile"] = profile

    # Finn profile_version (binding for sid hvis finnes, ellers hash av aktiv profil)
    sid_key = sid or ""
    profile_version = binding_for(sid_key) or compute_profile_version(profile)

    profile_scrubbed = _scrub_profile(profile)

    # --- Estimat + Weather (tredje-argument) ---
    estimat_cfg: Dict[str, Any] = {}
    if force_recompute:
        estimat_cfg["force"] = True
    if isinstance(body.get("estimat"), dict):
        estimat_cfg.update(body["estimat"])
    elif isinstance(body.get("estimate"), dict):
        estimat_cfg.update(body["estimate"])

    weather_in = {}
    if not no_weather and isinstance(body.get("weather"), dict):
        w = body["weather"]
        for k in ("wind_ms", "wind_dir_deg", "air_temp_c", "air_pressure_hpa"):
            if k in w and w[k] is not None:
                weather_in[k] = w[k]

    # third = estimat + weather (rs_power_json vil splitte selv)
    third = dict(estimat_cfg)
    third.update(weather_in)

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

    # ---------- HARD RUST SHORT-CIRCUIT ----------
    if rs_power_json is not None:
        try:
            # ✅ sender BOTH estimat og weather i tredje-argumentet
            r = rs_power_json(mapped, profile_scrubbed, third)
        except Exception as e:
            print(f"[SVR] [RUST] exception (no-fallback mode): {e!r}", file=sys.stderr, flush=True)
            return {
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

                # --- Trinn 6: passiv kalibrering (MAE mot device_watts om tilstede) ---
                try:
                    import os  # lokal import
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

                # --- Trinn 6: passiv kalibrering (MAE mot device_watts om tilstede) ---
                try:
                    import os  # lokal import
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
            except Exception as e:
                print(f"[SVR] [RUST] json.loads failed (no-fallback): {e!r}", file=sys.stderr, flush=True)
                return {
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
                resp["weather_applied"] = bool(weather_in)

            m = resp.setdefault("metrics", {})
            pu = m.setdefault("profile_used", dict(profile))
            if isinstance(pu, dict):
                pu.setdefault("profile_version", profile_version)
                m["profile_used"] = pu
            m.setdefault("weather_applied", bool(resp.get("weather_applied", False)))
            m.setdefault("total_watt", m.get("precision_watt", 0.0))

            dbg = resp.setdefault("debug", {})
            dbg.setdefault("reason", "ok")
            dbg["force_recompute"] = bool(force_recompute)
            dbg["persist_ignored"] = bool(force_recompute)
            dbg["ignored_persist"] = bool(force_recompute)
            dbg["used_fallback"] = False
            if not dbg.get("weather_source"):
                dbg["weather_source"] = "payload" if weather_in else "neutral"
            if force_recompute:
                dbg["estimat_cfg_used"] = dict(estimat_cfg)

            rust_has_metrics = isinstance(m, dict) and any(
                k in m for k in ("precision_watt", "drag_watt", "rolling_watt", "total_watt")
            )
            if rust_has_metrics:
                return _ensure_contract_shape(resp)

            print("[SVR] [RUST] missing/invalid metrics (no-fallback)", file=sys.stderr, flush=True)
            return {
                "source": "rust_error",
                "weather_applied": False,
                "metrics": {},
                "debug": {
                    "reason": "no-metrics-from-rust",
                    "used_fallback": False,
                    "weather_source": "payload" if weather_in else "neutral",
                    "adapter_resp_keys": list(resp.keys()) if isinstance(resp, dict) else [],
                    "metrics_seen": list((m or {}).keys()) if isinstance(m, dict) else [],
                },
            }

    # ---------- PURE FALLBACK_PY ----------
    profile_used = dict(profile)
    profile_used["profile_version"] = profile_version
    weather_applied = False

    fallback_metrics = _fallback_metrics(
        mapped,
        profile_used,
        weather_applied=weather_applied,
        profile_used=profile_used,
    )

    resp = {
        "source": "fallback_py",
        "weather_applied": False,
        "metrics": fallback_metrics,
        "debug": {
            "reason": "fallback-path",
            "note": "Legacy Python path executed (no Rust result short-circuited).",
            "force_recompute": bool(force_recompute),
            "persist_ignored": bool(force_recompute),
            "ignored_persist": bool(force_recompute),
            "used_fallback": True,
            "weather_source": "neutral",
        },
        "profile_used": profile_used,
        "sid": sid,
    }
    print("[SVR] [FB] returning fallback_py")
    return _ensure_contract_shape(resp)

