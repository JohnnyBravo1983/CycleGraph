from __future__ import annotations
from fastapi import APIRouter
from typing import Any, Dict, List
import glob, json, os, re

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


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


@router.get("/list")
def list_sessions() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    base = os.path.join(os.getcwd(), "logs", "results")
    for path in glob.glob(os.path.join(base, "result_*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)

            # 1) Prøv å hente ride_id/id fra selve JSON-en
            ride_id = str(doc.get("ride_id") or doc.get("id") or "")

            # 2) Hvis fortsatt tomt → hent fra filnavnet: result_16127771071.json -> 16127771071
            if not ride_id:
                basename = os.path.basename(path)
                if basename.startswith("result_") and basename.endswith(".json"):
                    ride_id = basename[len("result_") : -len(".json")]

            # Hvis vi fortsatt ikke har noe ID, hopp over fila
            if not ride_id:
                continue

            metrics = doc.get("metrics") or {}

            # Precision Watt snitt: hent fra metrics.precision_watt hvis mulig
            precision_watt_avg = None
            if isinstance(doc.get("precision_watt_avg"), (int, float)):
                precision_watt_avg = float(doc["precision_watt_avg"])
            elif isinstance(metrics.get("precision_watt"), (int, float)):
                precision_watt_avg = float(metrics["precision_watt"])

            rows.append(
                {
                    "ride_id": ride_id,
                    "profile_version": doc.get("profile_version"),
                    "weather_source": (
                        doc.get("weather_source") or metrics.get("weather_source")
                    ),
                    # Minisprint 2.5 – nye felter for frontend
                    "start_time": None,  # placeholder – ikke i JSON ennå
                    "distance_km": None,  # placeholder – ikke i JSON ennå
                    "precision_watt_avg": precision_watt_avg,
                }
            )

        except Exception:
            continue
    return rows
