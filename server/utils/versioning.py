from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from typing import Dict, Any

CANON_KEYS = ("rider_weight_kg","bike_type","bike_weight_kg","tire_width_mm","tire_quality","device")

DEFAULT_PROFILE = {
    "rider_weight_kg": 75.0,
    "bike_type": "road",
    "bike_weight_kg": 8.0,   # auto-normaliseres i save/load
    "tire_width_mm": 28,
    "tire_quality": "performance",
    "device": "strava",
    "bike_name": "My Bike",
    "publish_to_strava": False,
    "consent": False,
}


def _repo_root() -> str:
    # Robust nok: appen kjøres fra repo root hos deg
    return os.getcwd()


def _user_dir(uid: str) -> str:
    # samme base som tokens: state/users/<uid>/
    return os.path.join(_repo_root(), "state", "users", uid)


def _paths(uid: str) -> tuple[str, str]:
    base = _user_dir(uid)
    profile_path = os.path.join(base, "profile.json")
    audit_path = os.path.join(base, "profile_versions.jsonl")
    return profile_path, audit_path


def _ensure_dirs(uid: str) -> None:
    os.makedirs(_user_dir(uid), exist_ok=True)


def _normalize_bike_weight(profile: Dict[str,Any]) -> None:
    bt = (profile.get("bike_type") or "road").lower()
    if bt == "road":
        profile["bike_weight_kg"] = float(profile.get("bike_weight_kg", 8.0)) or 8.0
    elif bt == "gravel":
        profile["bike_weight_kg"] = float(profile.get("bike_weight_kg", 9.5)) or 9.5
    else:
        profile["bike_weight_kg"] = float(profile.get("bike_weight_kg", 11.5)) or 11.5


def json_canon(obj: Dict[str, Any]) -> str:
    sub = {k: obj.get(k) for k in CANON_KEYS}
    return json.dumps(sub, sort_keys=True, separators=(",",":"), ensure_ascii=False)


def compute_version(profile_subset: Dict[str, Any]) -> Dict[str,str]:
    s = json_canon(profile_subset)
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]
    ymd = dt.datetime.utcnow().strftime("%Y%m%d")
    return {"version_hash": h, "profile_version": f"v1-{h}-{ymd}", "version_at": f"{ymd}T00:00:00Z"}


def decide_crank_eff_pct(now_utc: dt.datetime | None = None) -> float:
    m = (now_utc or dt.datetime.utcnow()).month
    return 96.0 if m in (11,12,1,2,3) else 97.0


def _write_profile_file(profile_path: str, doc: Dict[str,Any]) -> None:
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def _append_audit_line(audit_path: str, profile_version: str, version_hash: str, subset: Dict[str,Any]) -> None:
    line = {
        "ts": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile_version": profile_version,
        "version_hash": version_hash,
        "profile_subset": subset,
    }
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def load_profile(uid: str) -> Dict[str,Any]:
    """Les profil per uid. Hvis den ikke finnes, opprett initial profil uten å kalle save_profile (unngå rekursjon)."""
    if not uid:
        raise ValueError("uid is required")
    _ensure_dirs(uid)
    profile_path, audit_path = _paths(uid)

    if not os.path.exists(profile_path):
        prof = DEFAULT_PROFILE.copy()
        _normalize_bike_weight(prof)
        subset = {k: prof.get(k) for k in CANON_KEYS}
        v = compute_version(subset)
        prof["version_hash"]     = v["version_hash"]
        prof["profile_version"]  = v["profile_version"]
        prof["version_at"]       = v["version_at"]
        prof["crank_efficiency"] = decide_crank_eff_pct()
        _write_profile_file(profile_path, prof)
        _append_audit_line(audit_path, prof["profile_version"], prof["version_hash"], subset)
        return prof

    with open(profile_path, "r", encoding="utf-8") as f:
        prof = json.load(f)

    prof = {**DEFAULT_PROFILE, **prof}
    _normalize_bike_weight(prof)

    subset = {k: prof.get(k) for k in CANON_KEYS}
    v = compute_version(subset)
    prof["version_hash"]     = v["version_hash"]
    prof["profile_version"]  = v["profile_version"]
    prof["version_at"]       = v["version_at"]
    if "crank_efficiency" not in prof:
        prof["crank_efficiency"] = decide_crank_eff_pct()

    _write_profile_file(profile_path, prof)
    return prof


def save_profile(uid: str, incoming: Dict[str,Any]) -> Dict[str,Any]:
    """Lagre profil per uid."""
    if not uid:
        raise ValueError("uid is required")
    _ensure_dirs(uid)
    profile_path, audit_path = _paths(uid)

    if os.path.exists(profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            current = DEFAULT_PROFILE.copy()
    else:
        current = DEFAULT_PROFILE.copy()

    merged = {**DEFAULT_PROFILE, **current, **{k:v for k,v in (incoming or {}).items() if k!="crank_efficiency"}}
    _normalize_bike_weight(merged)

    subset = {k: merged.get(k) for k in CANON_KEYS}
    v = compute_version(subset)
    merged["version_hash"]     = v["version_hash"]
    merged["profile_version"]  = v["profile_version"]
    merged["version_at"]       = v["version_at"]
    merged["crank_efficiency"] = decide_crank_eff_pct()

    prev_version = current.get("profile_version")
    _write_profile_file(profile_path, merged)

    if prev_version != merged["profile_version"]:
        _append_audit_line(audit_path, merged["profile_version"], merged["version_hash"], subset)

    return merged


def get_profile_export(uid: str) -> Dict[str,Any]:
    prof = load_profile(uid)
    subset = {k: prof.get(k) for k in CANON_KEYS}
    v = compute_version(subset)  # deterministisk for GET
    return {"profile": subset, **v}
