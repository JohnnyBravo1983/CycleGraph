# server/routes/sessions_list_router.py
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_RE_RESULT_SID = re.compile(r"^result_(\d+)")


def _repo_root_from_here() -> Path:
    p = Path(__file__).resolve().parent
    for _ in range(0, 10):
        if (p / "logs").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path.cwd()


def _read_json_utf8_sig(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None


def _normalize_doc(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        for k in ("result", "analysis", "data", "doc"):
            v = raw.get(k)
            if isinstance(v, dict):
                return v
        return raw
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                return item
    return {}


def _extract_session_id(doc: Dict[str, Any]) -> Optional[str]:
    for k in ("session_id", "ride_id", "id"):
        v = doc.get(k)
        if v is not None:
            return str(v)

    for path in (
        ("info", "session_id"),
        ("info", "ride_id"),
        ("meta", "session_id"),
        ("meta", "ride_id"),
        ("session", "id"),
        ("ride", "id"),
    ):
        cur: Any = doc
        ok = True
        for p in path:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                ok = False
                break
        if ok and cur is not None:
            return str(cur)

    return None


def _sid_from_filename(p: Path) -> Optional[str]:
    """
    Fallback: bruk filnavnet result_<digits>*.json som session_id.
    Eksempel: result_16127771071_direct.json -> 16127771071
    """
    m = _RE_RESULT_SID.match(p.stem)
    return m.group(1) if m else None


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s == "":
            return None
        return float(s)
    except Exception:
        return None


def _trend_sessions_lookup_start_time(session_id: str) -> Optional[str]:
    try:
        root = _repo_root_from_here()
        path = root / "logs" / "trend_sessions.csv"
        if not path.exists():
            return None

        with path.open("r", encoding="utf-8-sig", newline="") as f:
            r = csv.reader(f)
            _ = next(r, None)
            for row in r:
                if not row:
                    continue
                if row[0].strip() == str(session_id):
                    ts = (row[1] or "").strip() if len(row) > 1 else ""
                    return ts or None
        return None
    except Exception:
        return None


def _safe_get_metrics(doc: Dict[str, Any]) -> Dict[str, Any]:
    m = doc.get("metrics")
    return m if isinstance(m, dict) else {}


def _pick_precision_watt_avg(doc: Dict[str, Any], metrics: Dict[str, Any]) -> Optional[float]:
    """
    Velg "avg" i riktig rekkefølge.

    Viktig: legacy docs kan ha doc.watts som ikke er "precision/model/total".
    Derfor bruker vi ALDRI watts-mean som fallback før vi har en verifisert kontrakt.
    """
    pw_avg = _to_float(doc.get("precision_watt_avg"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("precision_watt_avg"))

    # Foretrekk modell/total før precision_watt i legacy
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("model_watt_wheel"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("total_watt"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("precision_watt"))

    return pw_avg




def _row_from_doc(doc: Dict[str, Any], source_path: Path, fallback_sid: str) -> Dict[str, Any]:
    """
    Bygger rad. Bruker fallback_sid hvis doc mangler id.
    """
    metrics = _safe_get_metrics(doc)

    distance_km = _to_float(doc.get("distance_km"))
    if distance_km is None:
        dm = _to_float(doc.get("distance_m"))
        if dm is not None:
            distance_km = dm / 1000.0

    pw_avg = _pick_precision_watt_avg(doc, metrics)

    sid = str(doc.get("session_id") or doc.get("ride_id") or doc.get("id") or fallback_sid)

    row: Dict[str, Any] = {
        "session_id": sid,
        "ride_id": str(doc.get("ride_id")) if doc.get("ride_id") is not None else sid,
        "start_time": doc.get("start_time"),
        "distance_km": distance_km,
        "precision_watt_avg": pw_avg,
        "profile_label": doc.get("profile_label") or (doc.get("profile_used") or {}).get("profile_label"),
        "weather_source": doc.get("weather_source") or (doc.get("weather") or {}).get("source"),
        "debug_source_path": str(source_path).replace("\\", "/"),
    }

    # PATCH C-final (safe): never break listing
    try:
        if row.get("start_time") in (None, ""):
            sid2 = row.get("session_id") or row.get("ride_id")
            if sid2:
                st = _trend_sessions_lookup_start_time(str(sid2))
                if st:
                    row["start_time"] = st
    except Exception:
        pass

    return row


def _gather_result_files(root: Path) -> List[Path]:
    files: List[Path] = []

    dbg = root / "_debug"
    if dbg.exists():
        # FIX: filtrer bort "_direct" så vi ikke får dobbelt/rare varianter
        files.extend(sorted([p for p in dbg.glob("result_*.json") if "_direct" not in p.name]))

    lr = root / "logs" / "results"
    if lr.exists():
        files.extend(sorted(lr.glob("result_*.json")))

    out = root / "out"
    if out.exists():
        files.extend(sorted(out.glob("result_*.json")))

    return files


def _prefer_path(a: Path, b: Path) -> Path:
    """
    Velg "beste" path for samme rid.

    Primærregel: NYESTE fil (mtime) vinner.
    Tie-break #1: logs/results foretrekkes fremfor _debug, deretter out.
    Tie-break #2: størst fil vinner (ofte full doc vs stub).
    """

    def tier(p: Path) -> int:
        s = str(p).replace("\\", "/")
        if "/logs/results/" in s:
            return 0
        if "/_debug/" in s:
            return 1
        if "/out/" in s:
            return 2
        return 9

    # 1) Nyeste mtime vinner
    try:
        ma = a.stat().st_mtime
        mb = b.stat().st_mtime
        if ma != mb:
            return a if ma > mb else b
    except Exception:
        pass

    # 2) Tier hvis mtime feiler/lik
    ta, tb = tier(a), tier(b)
    if ta != tb:
        return a if ta < tb else b

    # 3) Størst fil hvis fortsatt likt
    try:
        sa = a.stat().st_size
        sb = b.stat().st_size
        if sa != sb:
            return a if sa > sb else b
    except Exception:
        pass

    return a


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/list/all")
async def list_all() -> List[Dict[str, Any]]:
    import sys

    root = _repo_root_from_here()
    files = _gather_result_files(root)

    print(f"[list_all] __file__={__file__}", file=sys.stderr)
    print(f"[list_all] root={root} files={len(files)}", file=sys.stderr)

    best_by_sid: Dict[str, Path] = {}
    sid_from_doc = 0
    sid_from_name = 0
    sid_missing = 0

    for p in files:
        try:
            raw = _read_json_utf8_sig(p)
            doc = _normalize_doc(raw)

            sid = _extract_session_id(doc)
            if sid is not None:
                sid_from_doc += 1
            else:
                sid = _sid_from_filename(p)
                if sid is not None:
                    sid_from_name += 1
                else:
                    sid_missing += 1
                    continue

            if sid not in best_by_sid:
                best_by_sid[sid] = p
            else:
                best_by_sid[sid] = _prefer_path(best_by_sid[sid], p)
        except Exception:
            continue

    print(
        f"[list_all] sid_from_doc={sid_from_doc} sid_from_name={sid_from_name} sid_missing={sid_missing} unique={len(best_by_sid)}",
        file=sys.stderr,
    )

    rows: List[Dict[str, Any]] = []
    for sid, p in best_by_sid.items():
        try:
            raw = _read_json_utf8_sig(p)
            doc = _normalize_doc(raw)
            row = _row_from_doc(doc, p, fallback_sid=sid)
            rows.append(row)
        except Exception:
            continue

    # FIX: dropp helt tomme placeholder-resultater (typisk 0.0 i logs/results)
    rows = [r for r in rows if (_to_float(r.get("precision_watt_avg")) or 0.0) > 0.0]

    rows.sort(key=lambda r: str(r.get("start_time") or ""), reverse=True)

    # FIX: stabil UI (midlertidig) -> topp 9
    rows = rows[:9]

    print(f"[list_all] rows={len(rows)}", file=sys.stderr)
    return rows


@router.get("/list/_debug_paths")
async def _debug_paths() -> Dict[str, Any]:
    root = _repo_root_from_here()
    files = _gather_result_files(root)

    return {
        "router_file": str(Path(__file__).resolve()),
        "cwd": str(Path.cwd().resolve()),
        "root_from_here": str(root.resolve()),
        "files_from_here": len(files),
        "sample_files_from_here": [str(p).replace("\\", "/") for p in files[:8]],
    }
