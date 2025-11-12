from __future__ import annotations
import hashlib, json, os, datetime as dt
from typing import Dict, Any

CANON_KEYS = ("rider_weight_kg","bike_type","bike_weight_kg","tire_width_mm","tire_quality","device")

DATA_DIR  = os.path.join(os.getcwd(), "data")
LOG_DIR   = os.path.join(os.getcwd(), "logs", "profile")
PROFILE_PATH = os.path.join(DATA_DIR, "profile.json")
AUDIT_PATH   = os.path.join(LOG_DIR, "profile_versions.jsonl")

def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

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
    # Nov–Mar = 96%, ellers 97%
    return 96.0 if m in (11,12,1,2,3) else 97.0

def _write_profile_file(doc: Dict[str,Any]) -> None:
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

def _append_audit_line(profile_version: str, version_hash: str, subset: Dict[str,Any]) -> None:
    line = {
        "ts": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile_version": profile_version,
        "version_hash": version_hash,
        "profile_subset": subset,
    }
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

def load_profile() -> Dict[str,Any]:
    """Les profil. Hvis den ikke finnes, opprett initial profil uten å kalle save_profile (unngå rekursjon)."""
    _ensure_dirs()
    if not os.path.exists(PROFILE_PATH):
        # init med defaults → normaliser → versjoner → skriv → audit
        prof = DEFAULT_PROFILE.copy()
        _normalize_bike_weight(prof)
        subset = {k: prof.get(k) for k in CANON_KEYS}
        v = compute_version(subset)
        prof["version_hash"]     = v["version_hash"]
        prof["profile_version"]  = v["profile_version"]
        prof["version_at"]       = v["version_at"]
        prof["crank_efficiency"] = decide_crank_eff_pct()
        _write_profile_file(prof)
        _append_audit_line(prof["profile_version"], prof["version_hash"], subset)
        return prof
    # ellers: les fil
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        prof = json.load(f)
    # enkel robusthet: sikre felt + normaliser vekt og versjon på nytt
    prof = {**DEFAULT_PROFILE, **prof}
    _normalize_bike_weight(prof)
    subset = {k: prof.get(k) for k in CANON_KEYS}
    v = compute_version(subset)
    prof["version_hash"]     = v["version_hash"]
    prof["profile_version"]  = v["profile_version"]
    prof["version_at"]       = v["version_at"]
    if "crank_efficiency" not in prof:
        prof["crank_efficiency"] = decide_crank_eff_pct()
    _write_profile_file(prof)
    return prof

def save_profile(incoming: Dict[str,Any]) -> Dict[str,Any]:
    """Lagre profil. Ikke kall load_profile() her for å unngå rekursjon hvis fil mangler."""
    _ensure_dirs()
    # forsøk å lese eksisterende fil; hvis ikke finnes, bruk defaults som current
    if os.path.exists(PROFILE_PATH):
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            current = DEFAULT_PROFILE.copy()
    else:
        current = DEFAULT_PROFILE.copy()

    # slå sammen defaults → current → incoming (ignorer crank_efficiency fra klient)
    merged = {**DEFAULT_PROFILE, **current, **{k:v for k,v in (incoming or {}).items() if k!="crank_efficiency"}}
    _normalize_bike_weight(merged)

    subset = {k: merged.get(k) for k in CANON_KEYS}
    v = compute_version(subset)
    merged["version_hash"]     = v["version_hash"]
    merged["profile_version"]  = v["profile_version"]
    merged["version_at"]       = v["version_at"]
    merged["crank_efficiency"] = decide_crank_eff_pct()

    prev_version = current.get("profile_version")
    _write_profile_file(merged)

    if prev_version != merged["profile_version"]:
        _append_audit_line(merged["profile_version"], merged["version_hash"], subset)

    return merged

def get_profile_export() -> Dict[str,Any]:
    prof = load_profile()
    subset = {k: prof.get(k) for k in CANON_KEYS}
    v = compute_version(subset)  # deterministisk for GET
    return {"profile": subset, **v}
