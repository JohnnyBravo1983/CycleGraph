import os, json, csv, time, sys
from pathlib import Path
from typing import Any, Dict, List, Iterable
import requests

# --- Paths & logs ---
ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

# Baseline kan overstyres med T8_BASELINE
BASELINE = Path(os.environ.get("T8_BASELINE", str(LOGS / "_t8_baseline_payload.json")))
OUT_CSV      = LOGS / "trinn8-sweep_matrix.csv"
OUT_CSV_LONG = LOGS / "trinn8-longride_sweep.csv"

# --- Seeds for determinisme ---
SEED_PROFILE = int(os.environ.get("SEED_PROFILE", "42"))
SEED_WEATHER = int(os.environ.get("SEED_WEATHER", "2025"))

# --- Endpoint (passer din port og /api-sti) ---
API_URL = os.environ.get("CG_API", "http://127.0.0.1:5175/api/sessions/local-mini/analyze")

# --- Kontroll-knapper via env ---
SMOKE       = os.environ.get("T8_SMOKE", "0") == "1"         # kjapp demo
MAX_REQ     = int(os.environ.get("T8_MAX_REQUESTS", "0"))    # 0 = ingen grense
SLEEP_MS    = int(os.environ.get("T8_SLEEP_MS", "75"))       # millisek mellom requests
RETRIES     = int(os.environ.get("T8_RETRIES", "2"))         # pr request
BACKOFF_S   = float(os.environ.get("T8_BACKOFF_S", "0.5"))   # eksponentielt backoff-baseline

# --- Intervaller ---
if SMOKE:
    CDA_RANGE = [0.30, 0.31]
    CRR_RANGE = [0.0035, 0.0040]
    W_RANGE   = [78.0, 85.0]
    EFF_RANGE = [96.0, 93.0]
else:
    CDA_RANGE = [0.28, 0.29, 0.30, 0.31, 0.32]
    CRR_RANGE = [0.0030, 0.0035, 0.0040, 0.0050, 0.0060]
    W_RANGE   = [70.0, 78.0, 85.0, 90.0]
    EFF_RANGE = [96.0, 95.0, 93.0, 90.0]  # synkende -> precision_watt øker

def _coerce_payload_shape(data: Any) -> Dict[str, Any]:
    """Tving til {samples:[], profile:{}, weather:{}} for trygg posting."""
    if isinstance(data, list):
        data = {"samples": data, "profile": {}, "weather": {}}
    elif isinstance(data, dict):
        data.setdefault("samples", [])
        data.setdefault("profile", {})
        data.setdefault("weather", {})
        if not isinstance(data["samples"], list):
            data["samples"] = []
        if not isinstance(data["profile"], dict):
            data["profile"] = {}
        if not isinstance(data["weather"], dict):
            data["weather"] = {}
    else:
        data = {"samples": [], "profile": {}, "weather": {}}
    return data

def _load_baseline() -> Dict[str, Any]:
    if not BASELINE.exists():
        raise FileNotFoundError(
            f"Mangler baseline payload: {BASELINE}\n"
            f"Tips: sett T8_BASELINE eller lag logs/_t8_baseline_payload.json"
        )
    # utf-8-sig for å tåle BOM
    with BASELINE.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return _coerce_payload_shape(data)

def _preflight() -> None:
    """Sjekk at server svarer på en enkel POST med baseline før vi pøser på."""
    try:
        base = _load_baseline()
    except Exception as e:
        print(f"[T8][ERR] Klarte ikke å lese baseline: {e}", file=sys.stderr)
        raise

    try:
        r = requests.post(API_URL, json=base, timeout=10)
        if r.status_code >= 400:
            print(f"[T8][ERR] Preflight HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            raise RuntimeError("Preflight feilet (HTTP >= 400)")
        _ = r.json()
        print("[T8] Preflight OK.")
    except requests.exceptions.ConnectionError as e:
        print(f"[T8][ERR] ConnectionError mot {API_URL}: {e}", file=sys.stderr)
        print("     Sjekk at serveren kjører på 127.0.0.1:5175 og at /api-stien stemmer.", file=sys.stderr)
        raise
    except Exception as e:
        print(f"[T8][ERR] Preflight exception: {e}", file=sys.stderr)
        raise

def _row(resp: Dict[str, Any], prof: Dict[str, Any], sid: str) -> Dict[str, Any]:
    m = dict(resp.get("metrics") or {})
    pu = dict(m.get("profile_used") or {})
    dbg = dict(resp.get("debug") or {})
    return {
        "sid": sid,
        "cda": prof.get("cda"),
        "crr": prof.get("crr"),
        "weight_kg": prof.get("weight_kg"),
        "crank_eff_pct": prof.get("crank_eff_pct"),
        "precision_watt": float(m.get("precision_watt") or 0.0),
        "drag_watt": float(m.get("drag_watt") or 0.0),
        "rolling_watt": float(m.get("rolling_watt") or 0.0),
        "total_watt": float(m.get("total_watt") or 0.0),
        "weather_applied": bool(resp.get("weather_applied")),
        "calibrated": bool(m.get("calibrated") or False),
        "calibration_mae": m.get("calibration_mae"),
        "calibration_status": (m.get("calibration_status") or ""),
        "profile_version": (pu.get("profile_version") or ""),
        "source": (resp.get("source") or ""),
        "repr_kind": (resp.get("repr_kind") or ""),
        "debug_reason": (dbg.get("reason") or ""),
    }
TRUNCATE_CSV = os.environ.get("T8_TRUNCATE", "0") == "1"

# --- add near top, after imports/consts ---
CSV_INITIALIZED = False  # ensures we truncate only once per run

def _write_csv(path: Path, rows: List[Dict[str, Any]]):
    """Append rows to CSV, truncating only on the very first call per run."""
    global CSV_INITIALIZED
    if not rows:
        return

    keys = [
        "sid","cda","crr","weight_kg","crank_eff_pct",
        "precision_watt","drag_watt","rolling_watt","total_watt",
        "weather_applied","calibrated","calibration_mae","calibration_status",
        "profile_version","source","repr_kind","debug_reason",
    ]

    # Truncate kun én gang per prosess (første kall)
    truncate_env = os.environ.get("T8_TRUNCATE", "0").strip()
    want_truncate = (truncate_env not in ("", "0", "false", "False", "FALSE"))

    first_call = not CSV_INITIALIZED
    mode = "w" if (first_call and (want_truncate or not path.exists())) else "a"

    with path.open(mode, newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        # Skriv header hvis vi nettopp trunca, eller filen ikke fantes
        if mode == "w":
            w.writeheader()
        for r in rows:
            w.writerow(r)

    CSV_INITIALIZED = True


def _post(payload: Dict[str, Any], retries: int = RETRIES, backoff: float = BACKOFF_S) -> Dict[str, Any]:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(API_URL, json=payload, timeout=120)
            if r.status_code >= 400:
                body = ""
                try:
                    body = r.text
                except Exception:
                    body = "<no body>"
                raise RuntimeError(f"HTTP {r.status_code} from server: {body[:400]}")
            return r.json()
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff * attempt)
            else:
                raise
    raise last_err  # type: ignore[misc]

def _merge_profile(base: Dict[str, Any], cda: float, crr: float, w: float, eff: float) -> Dict[str, Any]:
    out = dict(base)
    prof = dict((out.get("profile") or {}))
    prof.setdefault("device", "strava")
    prof.update({"cda": cda, "crr": crr, "weight_kg": w, "crank_eff_pct": eff})
    out["profile"] = prof
    out["nominal"] = True  # test only; server guardrail vil strippe dette i prod
    dbg = dict((out.get("debug") or {}))
    dbg["seed_profile"] = SEED_PROFILE
    dbg["seed_weather"] = SEED_WEATHER
    out["debug"] = dbg
    return out

def _param_grid() -> Iterable[Dict[str, float]]:
    for cda in CDA_RANGE:
        for crr in CRR_RANGE:
            for w in W_RANGE:
                for eff in EFF_RANGE:
                    yield {"cda": cda, "crr": crr, "w": w, "eff": eff}

def run_sweep(sid_label: str, base_payload: Dict[str, Any], out_csv: Path):
    rows: List[Dict[str, Any]] = []
    total = len(CDA_RANGE) * len(CRR_RANGE) * len(W_RANGE) * len(EFF_RANGE)
    count = 0
    written = 0

    print(f"[T8] Starter sweep ({total} kombinasjoner). SMOKE={SMOKE} MAX_REQ={MAX_REQ or '∞'} SLEEP_MS={SLEEP_MS}")
    for params in _param_grid():
        count += 1
        if MAX_REQ and count > MAX_REQ:
            print(f"[T8] Stopp ved MAX_REQ={MAX_REQ}.")
            break

        pl = _merge_profile(base_payload, params["cda"], params["crr"], params["w"], params["eff"])

        try:
            resp = _post(pl)
        except Exception as e:
            print(f"[T8][ERR] Req {count}/{total} feilet: {e}", file=sys.stderr)
            # valgfritt: break helt, eller hopp videre:
            break

        rows.append(_row(resp, pl["profile"], sid_label))

        # enkel progress
        if count % 10 == 0 or count == total:
            print(f"[T8] Progress: {count}/{total} …")

        # flush i batcher
        if len(rows) >= 200:
            _write_csv(out_csv, rows)
            written += len(rows)
            rows.clear()

        # liten brems for ikke å spamme serveren/loggene
        if SLEEP_MS > 0:
            time.sleep(SLEEP_MS / 1000.0)

    if rows:
        _write_csv(out_csv, rows)
        written += len(rows)

    print(f"[T8] Ferdig. Skrev {written} rader til {out_csv}")

if __name__ == "__main__":
    print(f"[T8] Using API_URL={API_URL}")
    print(f"[T8] Using BASELINE={BASELINE}")
    base = _load_baseline()
    _preflight()
    run_sweep("local", base, OUT_CSV)

    # Long ride (valgfri)
    long_path = LOGS / "_t8_long_payload.json"
    if long_path.exists():
        print(f"[T8] Long baseline: {long_path}")
        with long_path.open("r", encoding="utf-8-sig") as f:
            long_base = json.load(f)
        long_base = _coerce_payload_shape(long_base)
        _preflight()  # gjenbruk samme preflight mot API_URL
        run_sweep("long", long_base, OUT_CSV_LONG)
