# server/routes/sessions_list_router.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _repo_root_from_here() -> Path:
    """
    Robust mot at server kjører med “feil” cwd.
    Går oppover fra denne fila til vi finner en "logs/"-mappe.
    """
    p = Path(__file__).resolve().parent
    for _ in range(0, 10):
        if (p / "logs").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path.cwd()


def _read_json_utf8_sig(path: Path) -> Dict[str, Any]:
    """Tåler UTF-8 BOM."""
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _to_float(x: Any) -> Optional[float]:
    return float(x) if isinstance(x, (int, float)) else None


def _numeric_session_id_from_stem(stem: str) -> Optional[str]:
    """
    Tar inn f.eks. "result_16127771071" og returnerer "16127771071"
    Returnerer None for f.eks. "result_16127771071__backup"
    """
    if not stem.startswith("result_"):
        return None
    sid = stem.replace("result_", "", 1)
    return sid if sid.isdigit() else None


def _extract_profile_label(doc: Dict[str, Any], metrics: Dict[str, Any]) -> Optional[str]:
    # profil-label (robust)
    profile_used_doc = doc.get("profile_used") or {}
    if not isinstance(profile_used_doc, dict):
        profile_used_doc = {}

    profile_used_metrics = metrics.get("profile_used") or {}
    if not isinstance(profile_used_metrics, dict):
        profile_used_metrics = {}

    return (
        doc.get("profile_version")
        or profile_used_doc.get("profile_version")
        or profile_used_metrics.get("profile_version")
    )


def _extract_weather_source(doc: Dict[str, Any], metrics: Dict[str, Any]) -> Optional[str]:
    # weather_source (robust)
    weather_used = metrics.get("weather_used") or {}
    if not isinstance(weather_used, dict):
        weather_used = {}

    meta = weather_used.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}

    return (
        doc.get("weather_source")
        or metrics.get("weather_source")
        or meta.get("source")
        or weather_used.get("source")
        or weather_used.get("provider")
    )


def _row_from_doc(sid: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    metrics = doc.get("metrics") or {}
    if not isinstance(metrics, dict):
        metrics = {}

    precision = _to_float(metrics.get("precision_watt"))
    if precision is None:
        # ekstra fallback om noen docs har feltet utenfor metrics
        precision = _to_float(doc.get("precision_watt"))
    if precision is None:
        precision = _to_float(doc.get("precision_watt_avg"))

    return {
        "session_id": str(sid),
        "ride_id": str(sid),
        "start_time": doc.get("start_time"),
        "distance_km": doc.get("distance_km"),
        "precision_watt_avg": precision,
        "profile_label": _extract_profile_label(doc, metrics),
        "weather_source": _extract_weather_source(doc, metrics),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/list")
@router.get("/list/all")  # kompatibilitet med eksisterende frontend-calls
def list_sessions() -> List[Dict[str, Any]]:
    root = _repo_root_from_here()
    logs = root / "logs"

    rows: List[Dict[str, Any]] = []

    # 1) Prioritet: logs/actual10/latest (full analyse)
    latest_dir = logs / "actual10" / "latest"
    if latest_dir.exists():
        for p in latest_dir.glob("result_*.json"):
            sid = _numeric_session_id_from_stem(p.stem)
            if not sid:
                continue
            try:
                doc = _read_json_utf8_sig(p)
            except Exception:
                continue
            if isinstance(doc, dict):
                rows.append(_row_from_doc(sid, doc))

    # 2) Fallback: logs/results (ofte stub, men ok hvis latest ikke finnes)
    if not rows:
        res_dir = logs / "results"
        if res_dir.exists():
            for p in res_dir.glob("result_*.json"):
                sid = _numeric_session_id_from_stem(p.stem)
                if not sid:
                    continue
                try:
                    doc = _read_json_utf8_sig(p)
                except Exception:
                    continue
                if isinstance(doc, dict):
                    rows.append(_row_from_doc(sid, doc))

    # (Valgfritt) sorter litt penere: nyeste først hvis start_time finnes, ellers id desc
    def _sort_key(r: Dict[str, Any]):
        st = r.get("start_time")
        return (st is not None, st or "", r.get("session_id") or "")

    rows.sort(key=_sort_key, reverse=True)
    return rows


from fastapi import HTTPException
from fastapi.responses import JSONResponse

@router.get("/{session_id}/analyze")
def get_session_analyze(session_id: str):
    """
    MVP: Returner persisted analyze-result direkte fra fil,
    slik at SessionView ikke henger på “live analyze”-pipeline.
    Prioritet:
      1) logs/actual10/latest/result_{id}.json
      2) logs/results/result_{id}.json
    """
    root = _repo_root_from_here()
    logs = root / "logs"

    candidates = [
        logs / "actual10" / "latest" / f"result_{session_id}.json",
        logs / "results" / f"result_{session_id}.json",
    ]

    for p in candidates:
        if not p.exists():
            continue
        try:
            doc = _read_json_utf8_sig(p)
            # sørg for at session_id/ride_id finnes (noen docs mangler)
            if isinstance(doc, dict):
                doc.setdefault("session_id", str(session_id))
                doc.setdefault("ride_id", str(session_id))
            return JSONResponse(content=doc)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Kunne ikke lese {p}: {repr(e)}")

    raise HTTPException(
        status_code=404,
        detail=f"Fant ingen persisted result for id={session_id} (prøvde: {candidates})",
    )
