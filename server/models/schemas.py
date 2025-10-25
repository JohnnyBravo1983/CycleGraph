# server/models/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, Literal

class ProfileIn(BaseModel):
    CdA: float = Field(..., gt=0)
    Crr: float = Field(..., gt=0)
    weight_kg: float = Field(..., gt=0)
    device: str

class MetricsOut(BaseModel):
    precision_watt: float
    precision_watt_ci: float
    total_watt: float
    drag_watt: float
    rolling_watt: float
    aero_fraction: float
    weather_applied: bool
    profile_used: ProfileIn

class DebugOut(BaseModel):
    analyzer_mode: Literal["series","single","unknown"] = "series"
    force_recompute: bool = False
    ignored_persist: bool = False
    reason: str = "ok"

class AnalyzeResponse(BaseModel):
    ok: bool = True
    session_id: str
    metrics: MetricsOut
    debug: DebugOut
