from __future__ import annotations
from fastapi import APIRouter
from typing import Any, Dict, List, Optional
import glob, json, os, re

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

RESULTS_DIR = os.path.join(os.getcwd(), "logs", "results")
DEBUG_DIR = os.path.join(os.getcwd(), "_debug")


def _ride_id_from_path(path: str) -> str:
    """
    Fallback: hent ride_id fra filnavnet, f.eks.
      logs/results/result_16127771071.json -> "16127771071"
    """
    base = os.path.basename(path)
    m = re.match(r"result_(.+)\.json$", base)
    if m:
        return m.group(1)
    return ""


def _load_result_doc(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Prøv å laste analysert resultat for en gitt økt/ride_id.
    1) logs/results/result_<id>.json
    2) _debug/result_<id>.json
    """
    candidates: list[str] = []

    # Primær: resultat fra ordinær pipeline
    candidates.append(os.path.join(RESULTS_DIR, f"result_{session_id}.json"))
    # Fallback/fasit: debug-katalog
    candidates.append(os.path.join(DEBUG_DIR, f"result_{session_id}.json"))

    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # Hvis en fil er korrupt el.l., prøv neste kandidat
            continue

    return None


@router.get("/list")
def list_sessions() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for path in glob.glob(os.path.join(RESULTS_DIR, "result_*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)

            # Primær: hent fra selve JSON-dokumentet
            ride_id = str(doc.get("ride_id") or doc.get("id") or "")

            # Fallback: hent fra filnavnet hvis ride_id mangler i doc
            if not ride_id:
                ride_id = _ride_id_from_path(path)

            # Hvis vi fortsatt ikke har noe id, hopp over denne fila
            if not ride_id:
                continue

            rows.append(
                {
                    "ride_id": ride_id,
                    "id": ride_id,  # ekstra alias for frontendens skyld
                    "profile_version": doc.get("profile_version"),
                    "weather_source": (
                        doc.get("weather_source")
                        or (doc.get("metrics") or {}).get("weather_source")
                    ),
                }
            )
        except Exception:
            continue

    return rows


@router.get("/{session_id}")
def get_session(session_id: str) -> Dict[str, Any]:
    """
    Returner enkel sessions-respons, men med Precision Watt fra analysert resultat
    hvis det finnes på disk.
    """
    result_doc = _load_result_doc(session_id)

    if result_doc:
        metrics = result_doc.get("metrics") or {}

        precision_watt = metrics.get("precision_watt")
        precision_watt_ci = metrics.get("precision_watt_ci")  # hvis vi får det senere

        # Beholder eksisterende felter hvis de finnes i result_doc, ellers None
        return {
            "session_id": session_id,
            "precision_watt": precision_watt,
            "precision_watt_ci": precision_watt_ci,
            "strava_activity_id": result_doc.get("strava_activity_id"),
            "publish_state": result_doc.get("publish_state"),
            "publish_time": result_doc.get("publish_time"),
            "publish_hash": result_doc.get("publish_hash", ""),
            "publish_error": result_doc.get("publish_error"),
        }

    # Fallback – hvis vi ikke fant noen result_*.json
    return {
        "session_id": session_id,
        "precision_watt": None,
        "precision_watt_ci": None,
        "strava_activity_id": None,
        "publish_state": None,
        "publish_time": None,
        "publish_hash": "",
        "publish_error": None,
    }
