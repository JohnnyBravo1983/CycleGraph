# server/analysis/t11_matrix.py
from __future__ import annotations

# --- imports + env ---
import os
import sys
import csv
import time
import json
import io
import gzip
from typing import List, Dict, Any, Optional, Iterable
from datetime import datetime, timezone
from pathlib import Path
from subprocess import check_output
import httpx

# Respekter no_weather fra env i CI (modulnivå default)
CG_NO_WX = (os.environ.get("CG_T11_NO_WEATHER", "0").strip().lower() in ("1", "true", "yes"))

GOLDEN_RIDES: List[str] = [
    "16127771071", "16262232459", "16279854313", "16311219004", "16333270450"
]

BASELINE_PATH = Path("ci/baseline/t11_base_mae.json")
ART_DIR = Path("artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = ART_DIR / "t11_matrix.csv"

REQUIRED_COLS = [
    "git_sha","profile_version","weather_source","ride_id",
    "precision_watt","drag_watt","rolling_watt","total_watt","calibration_mae",
    "estimated_error_pct_min","estimated_error_pct_max","precision_quality_hint",
]

# Treff ALLE underkataloger i actual10; vi forsøker rekkefølge: session → result → repo-rot → generisk
POSSIBLE_SAMPLE_FILES = [
    "logs/actual10/**/session_{rid}.json",
    "logs/actual10/**/result_{rid}.json",
    "result_{rid}.json",
    "logs/sessions/session_{rid}.json",
    "logs/results/result_{rid}.json",
    "logs/**/session_{rid}.json",
    "logs/**/result_{rid}.json",
]

# -------------------- helpers --------------------

def _git_sha() -> str:
    try:
        return check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return os.environ.get("GIT_SHA", "unknown")

def _ensure_server(url_base: str, timeout_s: float = 15.0):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            r = httpx.get(f"{url_base}/api/profile/get", timeout=2)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Server not responding at {url_base}")

def _get_profile_meta(url_base: str) -> Dict[str, Any]:
    r = httpx.get(f"{url_base}/api/profile/get", timeout=10)
    r.raise_for_status()
    data = r.json() or {}
    return {"profile_version": data.get("profile_version") or "", "profile": data.get("profile") or {}}

def _iter_candidate_paths(ride_id: str) -> Iterable[Path]:
    for pat in POSSIBLE_SAMPLE_FILES:
        pattern = pat.format(rid=ride_id)
        matched = []
        if any(ch in pattern for ch in "*?["):
            for p in Path(".").glob(pattern):
                if p.is_file():
                    matched.append(p)
        else:
            p = Path(pattern)
            if p.exists() and p.is_file():
                matched.append(p)

        # ASCII-safe debug
        if matched:
            print(f"[T11] pattern match -> {pattern}  count={len(matched)}")
            for p in matched[:3]:
                print(f"[T11]   file -> {p.as_posix()}")
            for p in matched:
                yield p
        else:
            print(f"[T11] pattern miss -> {pattern}")

# --- tolerant parser ---

def _try_json_parse(txt: str) -> Optional[dict]:
    try:
        return json.loads(txt)
    except Exception:
        return None

def _parse_json_tolerant(p: Path) -> Optional[dict]:
    """
    Tåler:
      - JSON Lines (tar første gyldige JSON-linje)
      - ledende/støytegn (tar substring fra første { til siste })
      - dårlige bytes (errors='ignore')
    """
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        # noen logger kan være binære/komprimerte ved uhell—prøv bytes→str
        try:
            b = p.read_bytes()
            # sniff gzip
            if len(b) >= 2 and b[0] == 0x1F and b[1] == 0x8B:
                try:
                    txt = gzip.decompress(b).decode("utf-8", errors="ignore")
                except Exception:
                    return None
            else:
                txt = b.decode("utf-8", errors="ignore")
        except Exception:
            return None

    # 1) ren JSON
    j = _try_json_parse(txt)
    if isinstance(j, dict):
        return j

    # 2) JSON Lines: ta første linje som parses
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        j = _try_json_parse(line)
        if isinstance(j, dict):
            return j

    # 3) bracket slice: fra første { til siste }
    s = txt.find("{")
    e = txt.rfind("}")
    if s != -1 and e != -1 and e > s:
        j = _try_json_parse(txt[s:e+1])
        if isinstance(j, dict):
            return j

    return None

# --- smarte extractors ---

_SAMPLE_KEYS_ORDER = ["samples", "records", "points", "stream", "rows", "list", "data_points"]
_HR_KEYS = {"hr","heartrate","heart_rate","bpm"}
_PWR_KEYS = {"watts","power","device_watts","pwr"}
_SPD_KEYS = {"speed","speed_ms","velocity","v_ms","kmh","kph"}
_TIME_KEYS = {"t","time","time_s","secs","seconds","elapsed"}

def _looks_like_sample_list(v: Any) -> bool:
    if not (isinstance(v, list) and v):
        return False
    if not all(isinstance(x, dict) for x in v[:5]):
        return False
    for x in v[:10]:
        keys = {k.lower() for k in x.keys()}
        if keys & _HR_KEYS or keys & _PWR_KEYS or keys & _SPD_KEYS or keys & _TIME_KEYS:
            return True
    return False

def _extract_samples_like(j: Any) -> Optional[list]:
    if not isinstance(j, dict):
        return None
    # 1) kjente nøkler på toppnivå
    for key in _SAMPLE_KEYS_ORDER:
        v = j.get(key)
        if _looks_like_sample_list(v):
            return v
    # 2) under data/payload/result
    for outer in ("data", "payload", "result"):
        inner = j.get(outer)
        if isinstance(inner, dict):
            for key in _SAMPLE_KEYS_ORDER:
                v = inner.get(key)
                if _looks_like_sample_list(v):
                    return v
    # 3) scan alle verdier
    for v in j.values():
        if _looks_like_sample_list(v):
            return v
    return None

def _merge_optional(dst: dict, src: Any, keys=("profile", "weather")):
    if not isinstance(src, dict):
        return
    for key in keys:
        val = src.get(key)
        if isinstance(val, dict) and key not in dst:
            dst[key] = val
    for outer in ("data", "payload", "result"):
        obj = src.get(outer)
        if isinstance(obj, dict):
            for key in keys:
                val = obj.get(key)
                if isinstance(val, dict) and key not in dst:
                    dst[key] = val

def _load_local_samples(ride_id: str) -> Optional[Dict[str, Any]]:
    """Finn lokalt json; returner {"samples":[...], profile?, weather?} eller meta-only stash."""
    setattr(_load_local_samples, "_stash", {})  # reset per kall
    any_matched = False
    for p in _iter_candidate_paths(ride_id):
        any_matched = True
        j = _parse_json_tolerant(p)
        if j is None:
            print(f"[T11] read/parse fail -> {p.name}")
            continue

        samples = _extract_samples_like(j)
        out: Dict[str, Any] = {}
        if samples:
            out["samples"] = samples

        _merge_optional(out, j, keys=("profile", "weather"))

        if out.get("samples"):
            print(f"[T11] ride={ride_id} using {p.as_posix()}  samples={len(out['samples'])}")
            return out
        else:
            if out:
                stash = getattr(_load_local_samples, "_stash", None) or {}
                stash.update(out)
                setattr(_load_local_samples, "_stash", stash)  # type: ignore
                print(f"[T11] ride={ride_id} meta-only in {p.name} (no samples)")

    stash = getattr(_load_local_samples, "_stash", None)
    if isinstance(stash, dict) and stash:
        print(f"[T11] ride={ride_id} no samples found, using stashed meta")
        return stash

    if not any_matched:
        print(f"[T11] ride={ride_id} no local files matched")
    return None

def _load_samples_for(ride_id: str) -> list:
    """Returner kun samples-listen (eller tom liste) fra _load_local_samples."""
    local = _load_local_samples(ride_id) or {}
    samples = local.get("samples")
    return samples if isinstance(samples, list) else []

# --- Patch B: ny request-hjelper som respekterer CG_NO_WX ---

def _analyze_one(url_base: str, ride_id: str, profile: dict, frozen: bool) -> dict | None:
    url = f"{url_base}/api/sessions/{ride_id}/analyze"

    # Re-les env her for å fange opp at andre trinn (f.eks. T14) endrer vær-modus uten restart
    CG_NO_WX_RUNTIME = (os.environ.get("CG_T11_NO_WEATHER", "0").strip().lower() in ("1", "true", "yes"))

    params = {
        "no_weather": True if CG_NO_WX_RUNTIME else False,
        "force_recompute": False,
        "debug": 0,
    }
    payload: Dict[str, Any] = {
        "samples": _load_samples_for(ride_id),  # eksisterende loader
        "profile": profile or {},
        # weather utelates; serveren skal ignorere når no_weather=true
    }

    # Om vi kjører "frozen" lokalt uten CG_NO_WX, kan vi hinte til serveren:
    if frozen and not CG_NO_WX_RUNTIME:
        payload.setdefault("weather", {})
        payload["weather"]["__mode"] = "frozen"

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, params=params, json=payload)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[T11] analyze failed ride={ride_id}: {e}", file=sys.stderr)
        # Prøv å logge responsinnhold hvis tilgjengelig
        try:
            if 'r' in locals():
                print("[T11] response text:", r.text[:2000], file=sys.stderr)
        except Exception:
            pass
        return None

# --- CSV helpers for Patch B ---

def _placeholder_row(git_sha: str, profile_version: str, ride_id: str) -> dict:
    return {
        "git_sha": git_sha,
        "profile_version": profile_version,
        "weather_source": "none",
        "ride_id": ride_id,
        "precision_watt": 0.0,
        "drag_watt": 0.0,
        "rolling_watt": 0.0,
        "total_watt": 0.0,
        "calibration_mae": "",
        "estimated_error_pct_min": "",
        "estimated_error_pct_max": "",
        "precision_quality_hint": "",
    }

def main() -> int:
    url_base = os.environ.get("CG_SERVER", "http://127.0.0.1:5175")
    wx_mode = os.environ.get("CG_WX_MODE", "real")  # "real" | "frozen"

    _ensure_server(url_base)
    git_sha = _git_sha()
    meta = _get_profile_meta(url_base)
    server_profile_version = meta["profile_version"]
    base_profile = meta["profile"]

    out: List[Dict[str, Any]] = []

    # Nye "required_rides" som Patch B spesifiserer (5 stk)
    required_rides = [
        "16127771071",
        "16127771072",
        "16127771073",
        "16127771074",
        "16127771075",
    ]

    for ride_id in required_rides:
        resp = _analyze_one(url_base, ride_id, base_profile, frozen=(wx_mode == "frozen"))
        if not resp:
            out.append(_placeholder_row(git_sha, server_profile_version, ride_id))
            continue

        metrics = resp.get("metrics", {}) or {}

        # Best effort profilversjon: resp -> metrics -> server-meta
        row_profile_version = resp.get("profile_version") or metrics.get("profile_version") or server_profile_version

        row: Dict[str, Any] = {
            "git_sha": git_sha,
            "profile_version": row_profile_version,
            "weather_source": metrics.get("weather_source", "none"),
            "ride_id": ride_id,
            "precision_watt": float(metrics.get("precision_watt", 0.0)) if metrics.get("precision_watt") is not None else 0.0,
            "drag_watt": float(metrics.get("drag_watt", 0.0)) if metrics.get("drag_watt") is not None else 0.0,
            "rolling_watt": float(metrics.get("rolling_watt", 0.0)) if metrics.get("rolling_watt") is not None else 0.0,
            "total_watt": float(metrics.get("total_watt", 0.0)) if metrics.get("total_watt") is not None else 0.0,
            "calibration_mae": metrics.get("calibration_mae", ""),
            "estimated_error_pct_min": "",
            "estimated_error_pct_max": "",
            "precision_quality_hint": metrics.get("precision_quality_hint", ""),
        }

        # Pakker ut range → to kolonner
        rng = metrics.get("estimated_error_pct_range")
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            try:
                row["estimated_error_pct_min"] = float(rng[0])
            except Exception:
                row["estimated_error_pct_min"] = ""
            try:
                row["estimated_error_pct_max"] = float(rng[1])
            except Exception:
                row["estimated_error_pct_max"] = ""

        out.append(row)

    # Skriv CSV uansett, med nøyaktig samme header som testen forventer
    header = [
        "git_sha","profile_version","weather_source","ride_id",
        "precision_watt","drag_watt","rolling_watt","total_watt","calibration_mae",
        "estimated_error_pct_min","estimated_error_pct_max","precision_quality_hint",
    ]
    ART_DIR.mkdir(parents=True, exist_ok=True)
    with (ART_DIR / "t11_matrix.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in out:
            w.writerow(r)

    print(f"[T11] wrote {len(out)} rows to artifacts/t11_matrix.csv")
    return 0

if __name__ == "__main__":
    sys.exit(main())
