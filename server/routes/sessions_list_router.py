# server/routes/sessions_list_router.py
from __future__ import annotations

import glob
import json
import os
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

BASE_DIR = os.getcwd()
RESULTS_DIR = os.path.join(BASE_DIR, "logs", "results")
DEBUG_DIR = os.path.join(BASE_DIR, "_debug")


def _ride_id_from_result_path(path: str) -> Optional[str]:
    """
    Trekk ut ren numerisk ride_id fra result_*.json.
    Ignorerer f.eks. result_16127771071__backup.json.
    """
    base = os.path.basename(path)
    m = re.match(r"result_(\d+)\.json$", base)
    if not m:
        return None
    return m.group(1)


def _load_result_for_list(ride_id: str) -> Optional[Dict[str, Any]]:
    """
    Minimal og eksplisitt loader for listeendepunktet:
    - Prøv _debug/result_{ride_id}.json først (ferdiganalysert)
    - Fallback til logs/results/result_{ride_id}.json
    - Les alltid med utf-8-sig for å håndtere BOM.
    """
    candidates = [
        os.path.join(DEBUG_DIR, f"result_{ride_id}.json"),
        os.path.join(RESULTS_DIR, f"result_{ride_id}.json"),
    ]

    for path in candidates:
        if not os.path.exists(path):
            continue

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                doc = json.load(f)
            print(
                f"[sessions_list_router] loaded ride_id={ride_id} from {path}",
                flush=True,
            )
            return doc
        except Exception as e:
            print(
                "[sessions_list_router][ERROR load] "
                f"ride_id={ride_id} path={path} error={repr(e)}",
                flush=True,
            )
            return None

    print(
        f"[sessions_list_router] NO FILE for ride_id={ride_id} "
        f"(candidates: {candidates})",
        flush=True,
    )
    return None


@router.get("/list/all")
def list_sessions() -> List[Dict[str, Any]]:
    """
    Returner en liste over økter basert på result_*.json i logs/results,
    men les selve innholdet fra _debug/ eller logs/results slik at vi
    får samme analyse som /api/sessions/{session_id}.
    """
    rows: List[Dict[str, Any]] = []

    pattern = os.path.join(RESULTS_DIR, "result_*.json")
    print(f"[sessions_list_router] scanning pattern={pattern}", flush=True)

    for path in glob.glob(pattern):
        ride_id = _ride_id_from_result_path(path)
        if not ride_id:
            print(
                f"[sessions_list_router] skip non-numeric file: {path}",
                flush=True,
            )
            continue

        result_doc = _load_result_for_list(ride_id)
        if not result_doc:
            print(
                f"[sessions_list_router] NO RESULT DOC for ride_id={ride_id}",
                flush=True,
            )
            continue

        metrics = result_doc.get("metrics") or {}
        if not isinstance(metrics, dict):
            metrics = {}

        # --- Precision Watt ---
        precision_watt_avg: Optional[float] = None

        pw_avg = result_doc.get("precision_watt_avg")
        if isinstance(pw_avg, (int, float)):
            precision_watt_avg = float(pw_avg)
        else:
            pw = metrics.get("precision_watt")
            if not isinstance(pw, (int, float)):
                pw = result_doc.get("precision_watt")
            if isinstance(pw, (int, float)):
                precision_watt_avg = float(pw)

        # --- profile_version ---
        profile_used = metrics.get("profile_used") or {}
        if not isinstance(profile_used, dict):
            profile_used = {}

        profile_version = result_doc.get("profile_version") or profile_used.get(
            "profile_version"
        )

        # --- weather_source ---
        weather_used = metrics.get("weather_used") or {}
        if not isinstance(weather_used, dict):
            weather_used = {}

        weather_source = (
            result_doc.get("weather_source")
            or metrics.get("weather_source")
            or weather_used.get("provider")
            or weather_used.get("source")
        )

        # --- start_time / distance_km ---
        start_time = result_doc.get("start_time")
        distance_km = result_doc.get("distance_km")

        if ride_id == "16127771071":
            print(
                "[sessions_list_router][DEBUG 16127771071] "
                f"keys={list(result_doc.keys())}; "
                f"metrics_keys={list(metrics.keys())}; "
                f"precision_watt={result_doc.get('precision_watt')}; "
                f"precision_watt_avg={precision_watt_avg}",
                flush=True,
            )

        rows.append(
            {
                "ride_id": ride_id,
                "id": ride_id,
                "profile_version": profile_version,
                "weather_source": weather_source,
                "start_time": start_time,
                "distance_km": distance_km,
                "precision_watt_avg": precision_watt_avg,
            }
        )

    print(f"[sessions_list_router] built {len(rows)} rows", flush=True)
    return rows
