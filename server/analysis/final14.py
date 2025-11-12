# server/analysis/final14.py
from __future__ import annotations
import os, sys, json, csv, hashlib, time
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable, Dict, Any, List, Tuple, Optional

import httpx

UTC = timezone.utc

# ------------------------------
# Utils
# ------------------------------
def _utc_datestr() -> str:
    return datetime.now(UTC).strftime("%Y%m%d")

def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _write_jsonl(lines: Iterable[Dict[str, Any]], out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8", newline="") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            n += 1
    return n

def _read_jsonl(p: Path) -> List[Dict[str, Any]]:
    if not p.exists():
        return []
    rows = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

def _csv_rows(p: Path) -> List[Dict[str, str]]:
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        return list(rdr)

def _env_true(name: str, default: str = "0") -> bool:
    return (os.environ.get(name, default) or "").lower() in ("1", "true", "yes")

def _log(msg: str) -> None:
    print(f"[FINAL14] {msg}", flush=True)

# ------------------------------
# Session discovery
# ------------------------------
def discover_session_ids(server_base: str) -> List[str]:
    """
    Prøv API-liste først (/api/sessions/list). Fallback: glob av session_*.json.
    Du kan overstyre med CG_SESSIONS_GLOB (f.eks. 'sessions/session_*.json').
    """
    # 1) API discovery
    url1 = f"{server_base}/api/sessions/list"
    try:
        with httpx.Client(follow_redirects=True, timeout=30.0) as cx:
            r = cx.get(url1)
            if r.status_code == 200:
                data = r.json()
                ids = data.get("sessions") or data.get("ids") or []
                ids = [str(x) for x in ids if x]
                if ids:
                    _log(f"Fant {len(ids)} sessions via API.")
                    return ids
    except Exception:
        pass

    # 2) Glob fallback
    glob_pat = os.environ.get("CG_SESSIONS_GLOB", "sessions/session_*.json")
    ids: List[str] = []
    for fp in Path(".").glob(glob_pat):
        stem = fp.stem  # session_<id>
        if "_" in stem:
            sid = stem.split("_", 1)[1]
        else:
            sid = stem
        if sid:
            ids.append(sid)
    if ids:
        _log(f"Fant {len(ids)} sessions via glob '{glob_pat}'.")
    else:
        _log("ADVARSEL: Fant ingen sessions via API eller glob. Angi CG_SESSIONS_GLOB ved behov.")
    return sorted(set(ids))

# ------------------------------
# Analyze sweep
# ------------------------------
def analyze_one(server_base: str, sid: str, frozen_weather: bool, force_recompute: bool) -> Optional[Dict[str, Any]]:
    """
    Kaller /api/sessions/{sid}/analyze. Vi sender minimal payload – server har robust body-coercion.
    weather: 'frozen' styres via miljø (CG_WX_MODE=frozen); vi setter no_weather=False i params for T14.
    """
    params = {
        "no_weather": False,               # Final = bruk vær (frozen via env)
        "force_recompute": bool(force_recompute),
        "debug": 0,
    }
    url = f"{server_base}/api/sessions/{sid}/analyze"
    payload: Dict[str, Any] = {}          # server-side loader håndterer samples

    try:
        with httpx.Client(follow_redirects=True, timeout=300.0) as cx:
            r = cx.post(url, params=params, json=payload)
            if r.status_code != 200:
                _log(f"SID={sid}: HTTP {r.status_code} – {r.text[:240]}")
                return None
            return r.json()
    except Exception as e:
        _log(f"SID={sid}: exception {e}")
        return None

def run_sweep(server_base: str, sids: List[str], frozen_weather: bool, force_recompute: bool) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for i, sid in enumerate(sids, 1):
        _log(f"Analyze {i}/{len(sids)} sid={sid} ...")
        res = analyze_one(server_base, sid, frozen_weather, force_recompute)
        if res is None:
            continue
        # Kontrakts-sjekk (kjernefelter)
        top = {
            "ride_id": str(sid),
            "profile_version": res.get("profile_version"),
            "weather_source": res.get("weather_source"),
            "device": (res.get("profile_used") or {}).get("device"),
            "metrics": (res.get("metrics") or {}),
            "profile_used": (res.get("profile_used") or {}),
        }
        rows.append(top)
    _log(f"Sweep ferdig: {len(rows)} resultater.")
    return rows

# ------------------------------
# Aggregation by profile_version
# ------------------------------
def aggregate_by_profile_version(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Enkel aggregasjon per profile_version (gjennomsnitt + count på nøkkelmålinger).
    """
    acc: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        pv = r.get("profile_version") or "unknown"
        m = r.get("metrics") or {}
        bucket = acc.setdefault(pv, {
            "precision_watt_sum": 0.0, "precision_watt_count": 0,
            "drag_watt_sum": 0.0, "drag_watt_count": 0,
            "rolling_watt_sum": 0.0, "rolling_watt_count": 0,
            "total_watt_sum": 0.0, "total_watt_count": 0,
            "calibration_mae_sum": 0.0, "calibration_mae_count": 0,
            "rows": 0,
        })
        def _acc(key_src: str, key_sum: str, key_cnt: str):
            v = m.get(key_src)
            if isinstance(v, (int, float)):
                bucket[key_sum] += float(v)
                bucket[key_cnt] += 1

        _acc("precision_watt", "precision_watt_sum", "precision_watt_count")
        _acc("drag_watt", "drag_watt_sum", "drag_watt_count")
        _acc("rolling_watt", "rolling_watt_sum", "rolling_watt_count")
        _acc("total_watt", "total_watt_sum", "total_watt_count")
        _acc("calibration_mae", "calibration_mae_sum", "calibration_mae_count")
        bucket["rows"] += 1

    # compute means
    out: Dict[str, Dict[str, Any]] = {}
    for pv, b in acc.items():
        def mean(sumk: str, cntk: str) -> Optional[float]:
            c = b[cntk]
            return (b[sumk] / c) if c > 0 else None

        out[pv] = {
            "profile_version": pv,
            "precision_watt_mean": mean("precision_watt_sum", "precision_watt_count"),
            "drag_watt_mean": mean("drag_watt_sum", "drag_watt_count"),
            "rolling_watt_mean": mean("rolling_watt_sum", "rolling_watt_count"),
            "total_watt_mean": mean("total_watt_sum", "total_watt_count"),
            "calibration_mae_mean": mean("calibration_mae_sum", "calibration_mae_count"),
            "rows": b["rows"],
        }
    return out

# ------------------------------
# Verification against T11
# ------------------------------
def verify_against_t11(t11_csv: Path, sessions_jsonl: Path) -> Dict[str, Any]:
    t11 = _csv_rows(t11_csv)
    sess = _read_jsonl(sessions_jsonl)

    t11_ids = {r.get("ride_id") for r in t11 if r.get("ride_id")}
    s_ids   = {r.get("ride_id") for r in sess if r.get("ride_id")}
    inter   = sorted(t11_ids & s_ids)

    # Enkle sanity-regler
    non_null_ok = all(
        (r.get("metrics") or {}).get("precision_watt") is not None and
        (r.get("metrics") or {}).get("total_watt") is not None
        for r in sess
    )

    profile_mirror_ok = all(
        (r.get("profile_used") or {}).get("profile_version") == r.get("profile_version")
        for r in sess if r.get("profile_version")
    )

    weather_mirror_ok = all(
        (r.get("metrics") or {}).get("weather_source") == r.get("weather_source")
        for r in sess if r.get("weather_source")
    )

    return {
        "t11_rows": len(t11),
        "sessions_rows": len(sess),
        "intersection_count": len(inter),
        "non_null_metrics": bool(non_null_ok),
        "profile_version_mirrored": bool(profile_mirror_ok),
        "weather_source_mirrored": bool(weather_mirror_ok),
        "intersection_ids": inter[:16],  # kort liste i manifest
    }

# ------------------------------
# Main entry
# ------------------------------
def main(argv: List[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser("final14")
    ap.add_argument("--server", default=os.environ.get("CG_SERVER", "http://127.0.0.1:5175"))
    ap.add_argument("--out-root", default="export")
    ap.add_argument("--date", default=_utc_datestr())
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--force", action="store_true", help="force_recompute analyzer=true")
    args = ap.parse_args(argv)

    # Determinisme-guards
    os.environ.setdefault("TZ", "UTC")
    os.environ.setdefault("LANG", "C")
    os.environ.setdefault("LC_ALL", "C")
    os.environ.setdefault("PYTHONHASHSEED", "0")
    # Vær i frossen modus
    os.environ.setdefault("CG_WX_MODE", "frozen")

    out_root = Path(args.out_root) / args.date
    out_root.mkdir(parents=True, exist_ok=True)

    if args.sweep:
        sids = discover_session_ids(args.server)
        rows = run_sweep(args.server, sids, frozen_weather=True, force_recompute=args.force)
        # midlertidig cache før eksport13 kjører:
        tmp_jsonl = out_root / "sessions_tmp.jsonl"
        _write_jsonl(rows, tmp_jsonl)
        _log(f"Skrev midlertidig {tmp_jsonl}")

    if args.verify:
        # paths for verify
        sessions_jsonl = out_root / "sessions.jsonl"
        t11_csv = out_root / "t11_matrix.csv"
        # fallback: finn t11 i artifacts/
        if not t11_csv.exists():
            alt = Path("artifacts") / "t11_matrix.csv"
            if alt.exists():
                t11_csv = alt

        info = {
            "date": args.date,
            "now_utc": datetime.now(UTC).isoformat(),
            "paths": {
                "sessions_jsonl": str(sessions_jsonl.resolve()),
                "t11_matrix_csv": str(t11_csv.resolve()) if t11_csv.exists() else None,
            },
            "sha256": {},
            "verify": {},
        }

        if sessions_jsonl.exists():
            info["sha256"]["sessions_jsonl"] = _sha256_file(sessions_jsonl)
        if t11_csv.exists():
            info["sha256"]["t11_matrix_csv"] = _sha256_file(t11_csv)

        if t11_csv.exists() and sessions_jsonl.exists():
            info["verify"] = verify_against_t11(t11_csv, sessions_jsonl)
        else:
            info["verify"] = {"note": "mangler sessions.jsonl eller t11_matrix.csv – kjør eksport og/eller T11 først"}

        manifest = out_root / "final14_manifest.json"
        with manifest.open("w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        _log(f"Skrev manifest: {manifest}")

    if not args.sweep and not args.verify:
        ap.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
