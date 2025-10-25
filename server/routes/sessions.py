# server/routes/sessions.py
from fastapi import APIRouter, Query, Body, HTTPException
from typing import Optional, Dict, Any
from ..models.schemas import AnalyzeResponse, ProfileIn, MetricsOut, DebugOut
from ..analysis.analyzer import analyze_series

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

@router.post("/{sid}/analyze", response_model=AnalyzeResponse)
def analyze_session(
    sid: str,
    force_recompute: bool = Query(False),
    no_weather: bool = Query(False),
    payload: Dict[str, Any] = Body(...)
):
    if "profile" not in payload:
        raise HTTPException(status_code=400, detail="profile required")

    profile: Dict[str, Any] = payload["profile"]

    # TODO: bytt denne mocken med faktisk persist-lag (hent fra storage)
    persisted = {"mean_power": 240.0}

    res = analyze_series(
        sid=sid,
        profile=profile,
        force_recompute=force_recompute,
        no_weather=no_weather,
        persisted=persisted
    )

    m = res["metrics"]
    metrics = MetricsOut(
        precision_watt=m["precision_watt"],
        precision_watt_ci=m["precision_watt_ci"],
        total_watt=m["total_watt"],
        drag_watt=m["drag_watt"],
        rolling_watt=m["rolling_watt"],
        aero_fraction=m["aero_fraction"],
        weather_applied=not no_weather,
        profile_used=ProfileIn(**profile),
    )

    debug = DebugOut(**res["debug"])

    # Komprimert, grep-vennlig logg
    print(
        f"[analyze] sid={sid} "
        f"CdA={profile['CdA']:.3f} Crr={profile['Crr']:.3f} W={profile['weight_kg']:.1f} dev={profile.get('device','?')} "
        f"force={force_recompute} ignored_persist={debug.ignored_persist} no_weather={no_weather} "
        f"→ pw={metrics.precision_watt:.1f} tot={metrics.total_watt:.1f} drag={metrics.drag_watt:.1f} roll={metrics.rolling_watt:.1f} reason={debug.reason}"
    )

    return AnalyzeResponse(
        ok=True,
        session_id=sid,
        metrics=metrics,
        debug=debug
    )
