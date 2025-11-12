# server/analysis/export13.py
# Trinn 13 – Export & Final Lock
# Leser result_*.json (+ valgfri session_*.json), profiler og CI-artefakter,
# og skriver deterministisk eksportpakke til export/<YYYYMMDD>/.

from __future__ import annotations
import os, sys, json, csv, shutil, hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# -------------------------
# Konstanter og guards
# -------------------------
REQUIRED_METRIC_KEYS = ["precision_watt", "drag_watt", "rolling_watt", "total_watt", "calibration_mae"]
EXPORT_SUBDIR_TRENDPIVOTS = "trend_pivots"

def _utc_datestr() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")

def _as_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x)

def _round6(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    try:
        return round(float(x), 6)
    except Exception:
        return None

def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def _load_json(p: Path) -> Dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def _copy_if_exists(src: Path, dst: Path) -> Optional[Path]:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        return dst
    return None

def _find_latest_tr9_root() -> Optional[Path]:
    # Forventet struktur fra Trinn 9: logs/<scope>/latest/
    logs = Path("logs")
    if not logs.exists():
        return None
    candidates = []
    for p in logs.rglob("latest"):
        # Sjekk at det finnes trinn9_trend_summary.csv under
        if (p / "trinn9_trend_summary.csv").exists():
            candidates.append(p)
    if not candidates:
        return None
    # Velg nyeste etter mtime
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]

def _gather_results() -> Dict[str, Dict[str, Any]]:
    """
    Søk bredt etter result_*.json:
      - logs/**/result_*.json
      - artifacts/**/result_*.json
      - repo-rot (./result_*.json)
    Returnerer map: ride_id -> parsed JSON
    """
    out: Dict[str, Dict[str, Any]] = {}
    roots = [Path("logs"), Path("artifacts"), Path(".")]
    seen: set[str] = set()

    def try_add(p: Path):
        try:
            obj = _load_json(p)
        except Exception:
            return
        rid = None
        try:
            rid = obj.get("ride_id") or obj.get("id") or obj.get("ride") or None
        except Exception:
            rid = None
        if not rid:
            stem = p.stem  # "result_<rideid>"
            if "_" in stem:
                rid = stem.split("_", 1)[1]
        if rid:
            k = str(rid)
            # seneste fil vinner dersom du har duplikater
            if k in out:
                # velg nyeste mtime
                oldp = out[k].get("__file__")
                if oldp:
                    oldmtime = Path(oldp).stat().st_mtime
                    newmtime = p.stat().st_mtime
                    if newmtime < oldmtime:
                        return
            obj["__file__"] = str(p)
            out[k] = obj

    for root in roots:
        if root.exists():
            for p in root.rglob("result_*.json"):
                try_add(p)

    return out


def _coalesce_session_record(rid: str, result_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lager eksportlinje (JSONL) i forward-kompatibelt skjema:
    {
      "ride_id": "string",
      "profile_version": "string",
      "weather_source": "string",
      "device": "string",
      "metrics": {...},
      "profile_used": {...} (hvis tilgjengelig)
    }
    """
    top_weather_source = result_obj.get("weather_source")
    metrics = result_obj.get("metrics") or {}
    profile_used = result_obj.get("profile_used") or (metrics.get("profile_used") if isinstance(metrics, dict) else None) or {}

    # Hent profile_version
    profile_version = result_obj.get("profile_version") or profile_used.get("profile_version") or metrics.get("profile_version")

    # Best-effort device
    device = profile_used.get("device") or result_obj.get("device") or "strava"

    # Sørg for at METRIC_KEYS finnes (None hvis ikke) + Patch 4: utvidet pick-liste og spesialhåndtering
    m: Dict[str, Any] = {}
    pick = [
        "precision_watt",
        "drag_watt",
        "rolling_watt",
        "total_watt",
        "calibration_mae",
        "estimated_error_pct_range",
        "precision_quality_hint",
    ]
    for k in pick:
        if not isinstance(metrics, dict):
            m[k] = None
            continue
        val = metrics.get(k)
        if k == "estimated_error_pct_range":
            # behold som liste [lo, hi] – rund komponenter
            if isinstance(val, (list, tuple)) and len(val) == 2:
                try:
                    lo = float(val[0]); hi = float(val[1])
                    m[k] = [round(lo, 6), round(hi, 6)]
                except Exception:
                    m[k] = val
            else:
                m[k] = val
        else:
            m[k] = _round6(val)

    # weather_source i metrics speiler toppnivå
    m["weather_source"] = top_weather_source or (metrics.get("weather_source") if isinstance(metrics, dict) else "") or ""

    # Forward-kompatibel record
    rec: Dict[str, Any] = {
        "ride_id": str(rid),
        "profile_version": _as_str(profile_version),
        "weather_source": _as_str(top_weather_source or ""),
        "device": _as_str(device),
        "metrics": m
    }

    if profile_used:
        # Pass-through, men sikre at tall er JSON-vennlige
        # (la felt stå som de er; eksporten er read-only artefakt)
        rec["profile_used"] = profile_used

    return rec

def _write_jsonl(lines: list[Dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        for rec in lines:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")

def _copy_tr9_pivots(latest_root: Path, out_root: Path) -> int:
    """
    Kopierer pivots (alle .csv i latest_root med 'pivot' i navnet) til export/trend_pivots/
    """
    count = 0
    out_dir = out_root / EXPORT_SUBDIR_TRENDPIVOTS
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in latest_root.glob("trinn9_pivot_*.csv"):
        shutil.copyfile(p, out_dir / p.name)
        count += 1
    return count

def main(argv: list[str]) -> int:
    # 1) Bestem output-root
    out_arg = None
    frozen_flag = False
    for i, a in enumerate(argv):
        if a in ("--out", "--output-dir") and i + 1 < len(argv):
            out_arg = argv[i + 1]
        if a == "--frozen":
            frozen_flag = True

    datestr = _utc_datestr()
    base = Path(out_arg) if out_arg else Path("export")
    export_root = base / datestr
    export_root.mkdir(parents=True, exist_ok=True)

    # 2) Samle resultater (ride-level)
    results = _gather_results()
    lines = []
    for rid, obj in sorted(results.items(), key=lambda kv: kv[0]):
        lines.append(_coalesce_session_record(rid, obj))

    sessions_jsonl = export_root / "sessions.jsonl"
    _write_jsonl(lines, sessions_jsonl)

    # 3) Kopier Trinn 10 audit: profile_versions.jsonl
    _copy_if_exists(Path("logs/profile/profile_versions.jsonl"), export_root / "profile_versions.jsonl")

    # 4) Kopier Trinn 11 matrix: artifacts/t11_matrix.csv
    _copy_if_exists(Path("artifacts/t11_matrix.csv"), export_root / "t11_matrix.csv")

    # 5) Kopier Trinn 9 trend: summary + pivots
    latest = _find_latest_tr9_root()
    if latest:
        _copy_if_exists(latest / "trinn9_trend_summary.csv", export_root / "trend_summary.csv")
        _copy_tr9_pivots(latest, export_root)

    # 6) Manifest (sha256 + counts) for determinisme
    manifest = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_weather_hint": bool(frozen_flag),
        "counts": {
            "sessions": len(lines)
        },
        "sha256": {}
    }
    for p in export_root.rglob("*"):
        if p.is_file():
            manifest["sha256"][str(p.relative_to(export_root))] = _sha256_file(p)

    with (export_root / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, separators=(",", ": "))

    # 7) Kort utskrift for CI/PS-skript
    print(f"[EXPORT13] wrote: {sessions_jsonl} ({len(lines)} lines)")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
