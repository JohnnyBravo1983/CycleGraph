import json, hashlib, os, re, time
from typing import Dict, Any, List

CONFIG_DIR = os.path.join("config")
PROFILE_FILE = os.path.join(CONFIG_DIR, "profile.user.json")
BINDINGS_FILE = os.path.join(CONFIG_DIR, "ride_profile_bindings.json")
RIDES_TXT_NAME = "Manuell_Cyclegraph_5Økter.txt"

def _sha_short(d: Dict[str, Any]) -> str:
    j = json.dumps(d, sort_keys=True, separators=(",",":"))
    return hashlib.sha256(j.encode()).hexdigest()[:12]

def load_user_profile() -> Dict[str, Any]:
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            p = json.load(f)
    except Exception:
        p = {}
    p.setdefault("device", "strava")
    if "weight" in p and "weight_kg" not in p: p["weight_kg"]=p.pop("weight")
    if "crank_eff" in p and "crank_eff_pct" not in p: p["crank_eff_pct"]=p.pop("crank_eff")
    return p

def compute_profile_version(p: Dict[str,Any]) -> str:
    h = _sha_short({k:p.get(k) for k in ("cda","crr","weight_kg","crank_eff_pct","device")})
    d = time.strftime("%Y%m%d")
    return f"v1-{h}-{d}"

def read_ride_ids_from_txt() -> List[str]:
    path = None
    for root, _, files in os.walk("."):
        for fn in files:
            if fn == RIDES_TXT_NAME:
                path = os.path.join(root, fn); break
        if path: break
    if not path:
        return []
    txt = open(path, "r", encoding="utf-8").read()
    return sorted(set(re.findall(r"\b\d{6,}\b", txt)))

def write_bindings(ride_ids: List[str], profile_version: str) -> Dict[str,str]:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        cur = json.load(open(BINDINGS_FILE, "r", encoding="utf-8"))
    except Exception:
        cur = {}
    for rid in ride_ids:
        cur[str(rid)] = profile_version
    with open(BINDINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2, ensure_ascii=False)
    return cur

def binding_for(sid: str) -> str:
    try:
        m = json.load(open(BINDINGS_FILE, "r", encoding="utf-8"))
        return m.get(str(sid)) or ""
    except Exception:
        return ""

# --- Trinn 7 compat alias ---
def binding_from(*args, **kwargs):
    """Compat alias: gammel navn -> ny funksjon."""
    return binding_for(*args, **kwargs)