# server/routes/sessions.py
from __future__ import annotations

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
    no_weather: bool = Query(False),  # beholdt for signatur-compat (ikke brukt i trinn 3)
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

    # Valider shape
    samples = list((body or {}).get("samples") or [])
    profile_in = dict((body or {}).get("profile") or {})
    if not isinstance(samples, list) or not isinstance(profile_in, dict):
        raise HTTPException(status_code=400, detail="Missing 'samples' or 'profile'")

    profile_scrubbed = _scrub_profile(profile_in)

    # Estimat-konfig (3. argument) – IKKE vær
    estimat_cfg: Dict[str, Any] = {}
    if force_recompute:
        estimat_cfg["force"] = True
    if isinstance(body.get("estimat"), dict):
        estimat_cfg.update(body["estimat"])
    elif isinstance(body.get("estimate"), dict):
        estimat_cfg.update(body["estimate"])

    # --- (VALGFRITT MEN ANBEFALT) MINIMAL NORMALISERING AV SAMPLES ---
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
        v_ms = s.get("v_ms")
        if v_ms is None:
            v_ms = s.get("v_mps", s.get("v"))
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
    # --- SLUTT NORMALISERING ---

    # ---------- HARD RUST SHORT-CIRCUIT ----------
    if rs_power_json is not None:
        # Kall adapter – NO-FALLBACK ved feil i debugfasen
        try:
            # NB: IKKE send weather som 3. arg i Trinn 3
            r = rs_power_json(mapped, profile_scrubbed, estimat_cfg or {})
        except Exception as e:
            # 🚫 Trinn 3 debug: IKKE gå til fallback; returnér rust_error
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

        # Parse adapter-output til dict, ellers returner rust_error
        resp: Dict[str, Any] = {}
        if isinstance(r, dict):
            resp = r  # type: ignore[assignment]
        else:
            try:
                resp = json.loads(r) if isinstance(r, (str, bytes, bytearray)) else {}
            except Exception as e:
                # 🚫 Trinn 3 debug: IKKE falle til fallback ved JSON-feil – returnér årsak
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
            # Pakk flat → metrics (belte & bukseseler), men ikke overskriv tall
            if "metrics" not in resp:
                keys = ("precision_watt", "drag_watt", "rolling_watt", "total_watt")
                if any(k in resp for k in keys):
                    mtmp = {k: resp.pop(k) for k in keys if k in resp}
                    if "profile_used" in resp and isinstance(resp["profile_used"], dict):
                        mtmp.setdefault("profile_used", resp["profile_used"])
                    resp["metrics"] = mtmp

            # Sett defaults uten å overstyre verdier fra Rust
            resp.setdefault("source", "rust_1arg")
            resp.setdefault("weather_applied", False)

            # TEST-KRAV: metrics.profile_used == innsendt profil (rå inn-profil)
            m = resp.setdefault("metrics", {})
            m.setdefault("profile_used", dict(profile_in))
            m.setdefault("weather_applied", bool(resp.get("weather_applied", False)))
            # Sanity for Trinn 3: total_watt = precision_watt hvis ikke satt
            m.setdefault("total_watt", m.get("precision_watt", 0.0))

            # Debug-oppdateringer
            dbg = resp.setdefault("debug", {})
            dbg.setdefault("reason", "ok")
            dbg["force_recompute"] = bool(force_recompute)
            dbg["persist_ignored"] = bool(force_recompute)
            dbg["ignored_persist"] = bool(force_recompute)
            # Patch: eksplisitt no-fallback og weather_source
            dbg["used_fallback"] = False
            if not dbg.get("weather_source"):
                dbg["weather_source"] = "neutral"
            if force_recompute:
                dbg["estimat_cfg_used"] = dict(estimat_cfg)

            # Vurder om vi faktisk har metrics
            rust_has_metrics = isinstance(m, dict) and any(
                k in m for k in ("precision_watt", "drag_watt", "rolling_watt", "total_watt")
            )

            if rust_has_metrics:
                # (5) Sett kilde og flagg eksplisitt per gren
                resp["source"] = "rust_1arg"
                resp["weather_applied"] = False
                # Debug: sett eksplisitt og rydd opp ev. blanke verdier
                dbg = resp.setdefault("debug", {})
                dbg["used_fallback"] = False
                if not dbg.get("weather_source"):
                    dbg["weather_source"] = "neutral"
                dbg.setdefault("reason", "ok")
                # Sanity for Trinn 3: total_watt = precision_watt
                m.setdefault("total_watt", m.get("precision_watt", 0.0))
                final = _ensure_contract_shape(resp)
                return final
            else:
                # 🚫 Trinn 3 debug: IKKE falle videre; returnér årsak
                print("[SVR] [RUST] missing/invalid metrics (no-fallback)", file=sys.stderr, flush=True)
                return {
                    "source": "rust_error",
                    "weather_applied": False,
                    "metrics": {},
                    "debug": {
                        "reason": "no-metrics-from-rust",
                        "used_fallback": False,
                        "weather_source": "neutral",
                        "adapter_resp_keys": list(resp.keys()) if isinstance(resp, dict) else [],
                        "metrics_seen": list((m or {}).keys()) if isinstance(m, dict) else [],
                    },
                }

    # ---------- PURE FALLBACK_PY (minimal) ----------
    # Bruk rå innsendt profil i metrics.profile_used gjennom helperen
    profile_used = dict((body or {}).get("profile") or {})
    weather_applied = False

    # Kun benyttes ved faktisk Rust-feil/ugyldig output – justert signatur
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
        # speil innsendt profil eksplisitt (i tillegg til speil via ensure)
        "profile_used": profile_used,
        "sid": sid,
    }
    print("[SVR] [FB] returning fallback_py")
    return _ensure_contract_shape(resp)
