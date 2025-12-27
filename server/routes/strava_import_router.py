# server/routes/strava_import_router.py
from __future__ import annotations

import os
import json
import math
import time
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/strava", tags=["strava-import"])

STRAVA_AUTH_BASE = "https://www.strava.com/api/v3"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


# ----------------------------
# paths / io
# ----------------------------
def _repo_root_from_here() -> Path:
    # server/routes/.. -> repo root
    return Path(__file__).resolve().parents[2]


def _user_dir(uid: str) -> Path:
    return _repo_root_from_here() / "state" / "users" / uid


def _tokens_path(uid: str) -> Path:
    return _user_dir(uid) / "strava_tokens.json"


# ----------------------------
# Sprint 4: sessions_index.json helpers
# ----------------------------
def _sessions_index_path(uid: str) -> Path:
    return _user_dir(uid) / "sessions_index.json"


def _load_sessions_index(uid: str) -> list[str]:
    p = _sessions_index_path(uid)
    if not p.exists():
        return []
    try:
        raw_txt = p.read_text(encoding="utf-8-sig") or ""
        raw = json.loads(raw_txt)

        # støtt både {"rides":[...]} og ["..."]
        if isinstance(raw, dict):
            xs = raw.get("rides")
        else:
            xs = raw

        if not isinstance(xs, list):
            return []

        out: list[str] = []
        for v in xs:
            if v is None:
                continue
            s = str(v).strip()
            if s:
                out.append(s)

        # dedupe, bevar rekkefølge
        seen = set()
        uniq: list[str] = []
        for r in out:
            if r in seen:
                continue
            seen.add(r)
            uniq.append(r)
        return uniq
    except Exception:
        return []


def _save_sessions_index(uid: str, rides: list[str]) -> None:
    p = _sessions_index_path(uid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"rides": rides}, ensure_ascii=False, indent=2), encoding="utf-8")


def _add_ride_to_sessions_index(uid: str, rid: str) -> list[str]:
    rid = str(rid).strip()
    rides = _load_sessions_index(uid)
    if rid and rid not in rides:
        rides.append(rid)
        _save_sessions_index(uid, rides)
    return rides


def _read_json_utf8_sig(p: Path) -> Dict[str, Any]:
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_json(p: Path, obj: Dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _now_ts_dirname() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


# ----------------------------
# Patch B: robust token refresh + retry
# ----------------------------
def _require_strava_client() -> tuple[str, str]:
    # støtt flere env-varianter (samme som resten av repoet ditt)
    cid = (
        os.getenv("STRAVA_CLIENT_ID")
        or os.getenv("CG_STRAVA_CLIENT_ID")
        or os.getenv("STRAVA_CLIENTID")
        or ""
    ).strip()
    csec = (
        os.getenv("STRAVA_CLIENT_SECRET")
        or os.getenv("CG_STRAVA_CLIENT_SECRET")
        or os.getenv("STRAVA_CLIENTSECRET")
        or ""
    ).strip()
    if not cid or not csec:
        raise HTTPException(status_code=500, detail="missing_strava_client_env")
    return cid, csec


def _refresh_tokens(refresh_token: str) -> Dict[str, Any]:
    cid, csec = _require_strava_client()
    payload = {
        "client_id": cid,
        "client_secret": csec,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    r = requests.post(STRAVA_TOKEN_URL, data=payload, timeout=15)
    if not r.ok:
        raise HTTPException(status_code=401, detail=f"strava_refresh_failed_{r.status_code}")
    try:
        return r.json()
    except Exception:
        raise HTTPException(status_code=401, detail="strava_refresh_failed_bad_json")


def _maybe_refresh_and_save(uid: str, tokens: Dict[str, Any], token_path: Path) -> Dict[str, Any]:
    # refresh hvis utløpt eller snart utløpt (leeway)
    leeway = int(os.getenv("STRAVA_REFRESH_LEEWAY_SEC", "120"))
    now = int(time.time())
    exp = int(tokens.get("expires_at") or 0)

    # Hvis expires_at er tilstede og fortsatt gyldig > leeway -> behold
    if exp and (exp - now) > leeway:
        return tokens

    rt = tokens.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="missing_refresh_token")

    data = _refresh_tokens(str(rt))

    new_tokens = dict(tokens)
    new_tokens["access_token"] = data.get("access_token") or new_tokens.get("access_token")
    new_tokens["refresh_token"] = data.get("refresh_token") or new_tokens.get("refresh_token")
    new_tokens["expires_at"] = int(data.get("expires_at") or 0)
    new_tokens["token_type"] = data.get("token_type") or new_tokens.get("token_type") or "Bearer"
    new_tokens["scope"] = data.get("scope") or new_tokens.get("scope")
    new_tokens["received_at"] = int(time.time())

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps(new_tokens, ensure_ascii=False, indent=2), encoding="utf-8")

    return new_tokens


# ----------------------------
# geometry helpers
# ----------------------------
def _bear_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # enkel bearing (grader fra nord, 0..360)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)

    y = math.sin(dlon) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    brng = math.degrees(math.atan2(y, x))
    return (brng + 360.0) % 360.0


# ----------------------------
# strava api (med auto-refresh + retry)
# ----------------------------
def _strava_get(url_path: str, uid: str, tokens: Dict[str, Any], token_path: Path) -> Any:
    # 1) refresh hvis utløpt
    tokens = _maybe_refresh_and_save(uid, tokens, token_path)

    access = tokens.get("access_token")
    if not access:
        raise HTTPException(status_code=401, detail="missing_access_token")

    url = f"{STRAVA_AUTH_BASE}{url_path}"
    headers = {"Authorization": f"Bearer {access}"}

    r = requests.get(url, headers=headers, timeout=20)

    # 2) hvis Strava likevel svarer 401/403 -> refresh + retry 1 gang
    if r.status_code in (401, 403):
        tokens = _maybe_refresh_and_save(uid, tokens, token_path)
        access2 = tokens.get("access_token")
        if not access2:
            raise HTTPException(status_code=401, detail="missing_access_token_after_refresh")
        headers = {"Authorization": f"Bearer {access2}"}
        r = requests.get(url, headers=headers, timeout=20)

    if r.status_code in (401, 403):
        raise HTTPException(status_code=401, detail=f"strava_auth_failed_{r.status_code}")
    if not r.ok:
        raise HTTPException(status_code=502, detail=f"strava_error_{r.status_code}")

    try:
        return r.json()
    except Exception:
        raise HTTPException(status_code=502, detail="strava_bad_json")


def _fetch_activity_and_streams(
    rid: str, uid: str, tokens: Dict[str, Any], token_path: Path
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    meta = _strava_get(f"/activities/{rid}", uid, tokens, token_path)

    # Minimum: tid/distanse/hr/cad/watts/latlng
    # Legger til altitude/velocity_smooth/grade_smooth/moving når tilgjengelig
    stream_keys = [
        "time",
        "distance",
        "heartrate",
        "cadence",
        "watts",
        "latlng",
        "altitude",
        "velocity_smooth",
        "grade_smooth",
        "moving",
    ]
    streams = _strava_get(
        f"/activities/{rid}/streams?keys={','.join(stream_keys)}&key_by_type=true",
        uid,
        tokens,
        token_path,
    )
    return meta, streams


# ----------------------------
# sessiondoc v1 builder
# ----------------------------
def _data_of(streams: Dict[str, Any], key: str) -> List[Any]:
    return (streams.get(key) or {}).get("data", []) if isinstance(streams, dict) else []


def _iso_utc_from_epoch(sec: Optional[int]) -> Optional[str]:
    if sec is None:
        return None
    return dt.datetime.fromtimestamp(int(sec), tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_samples_v1(meta: Dict[str, Any], streams: Dict[str, Any]) -> List[Dict[str, Any]]:
    start_date = meta.get("start_date")  # typisk "...Z"
    start_epoch = None
    if isinstance(start_date, str) and start_date.endswith("Z"):
        try:
            dtu = dt.datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
            start_epoch = int(dtu.timestamp())
        except Exception:
            start_epoch = None

    T = _data_of(streams, "time")
    LL = _data_of(streams, "latlng")
    ALT = _data_of(streams, "altitude")
    V = _data_of(streams, "velocity_smooth")
    G = _data_of(streams, "grade_smooth")
    HR = _data_of(streams, "heartrate")
    MOV = _data_of(streams, "moving")

    n = len(T) if T else len(LL)
    n = max(n, len(LL))

    samples: List[Dict[str, Any]] = []
    last_heading = 0.0

    for i in range(n):
        lat_deg = None
        lon_deg = None
        if i < len(LL) and isinstance(LL[i], (list, tuple)) and len(LL[i]) == 2:
            lat_deg = float(LL[i][0]) if LL[i][0] is not None else None
            lon_deg = float(LL[i][1]) if LL[i][1] is not None else None

        t = float(T[i]) if i < len(T) and T[i] is not None else float(i)
        t_abs = _iso_utc_from_epoch((start_epoch + int(t)) if start_epoch is not None else None)

        v_ms = float(V[i]) if i < len(V) and V[i] is not None else 0.0
        altitude_m = float(ALT[i]) if i < len(ALT) and ALT[i] is not None else 0.0
        grade = float(G[i]) if i < len(G) and G[i] is not None else 0.0
        hr = float(HR[i]) if i < len(HR) and HR[i] is not None else None

        # heading: beregn fra latlng dersom mulig
        heading_deg = last_heading
        if lat_deg is not None and lon_deg is not None and (i + 1) < len(LL):
            nxt = LL[i + 1]
            if isinstance(nxt, (list, tuple)) and len(nxt) == 2 and nxt[0] is not None and nxt[1] is not None:
                try:
                    heading_deg = _bear_deg(lat_deg, lon_deg, float(nxt[0]), float(nxt[1]))
                    last_heading = heading_deg
                except Exception:
                    heading_deg = last_heading

        moving = None
        if i < len(MOV) and isinstance(MOV[i], bool):
            moving = MOV[i]
        else:
            moving = bool(v_ms > 0.1)

        samples.append(
            {
                "t": t,
                "t_abs": t_abs,
                "lat_deg": lat_deg,
                "lon_deg": lon_deg,
                "v_ms": v_ms,
                "altitude_m": altitude_m,
                "grade": grade,
                "heading_deg": heading_deg,
                "hr": hr,
                "moving": moving,
            }
        )

    return samples


def _write_session_v1(uid: str, rid: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    root = _repo_root_from_here()
    logs = root / "logs"
    ts = _now_ts_dirname()

    p1 = logs / "actual10" / ts / f"session_{rid}.json"
    p2 = logs / "actual10" / "latest" / f"session_{rid}.json"

    _write_json(p1, doc)
    _write_json(p2, doc)

    # --- Patch 3C: write debug_session mirror for analyze input ---
    debug_session_written = False
    debug_session_path = None
    try:
        p_debug = root / "_debug" / f"session_{rid}.json"
        debug_session_path = str(p_debug)
        p_debug.parent.mkdir(parents=True, exist_ok=True)

        # Copy from latest actual10 session file (p2)
        # Ensure p2 exists first
        if p2.exists():
            p_debug.write_text(p2.read_text(encoding="utf-8"), encoding="utf-8")
            debug_session_written = True
    except Exception:
        debug_session_written = False
    # --- end Patch 3C ---

    return {
        "ts_path": str(p1),
        "latest_path": str(p2),
        "debug_session_written": debug_session_written,
        "debug_session_path": debug_session_path,
    }


def _trigger_analyze_local(rid: str) -> Dict[str, Any]:
    # intern call: unngår å import-koble oss til analyze_session-signaturen
    base = os.getenv("CG_API_BASE") or "http://localhost:5175"
    url = f"{base}/api/sessions/{rid}/analyze?force_recompute=1&debug=1"
    try:
        r = requests.post(url, json={}, timeout=60)
        out: Dict[str, Any] = {"status_code": r.status_code}
        try:
            out["json"] = r.json()
        except Exception:
            out["text"] = r.text[:500]
        return out
    except Exception as e:
        return {"status_code": 0, "error": repr(e), "url": url}


@router.post("/import/{rid}")
def import_strava_activity(rid: str, request: Request) -> Dict[str, Any]:
    FP = "STRAVA_IMPORT_ROUTER_FP_3X_20251227"
    print("[STRAVA_IMPORT]", FP, "rid=", rid)

    # If earlier patches are not present for some reason, ensure fields exist in response
    debug_session_written: Any = "UNSET"
    debug_session_path: Any = "UNSET"

    uid = request.cookies.get("cg_uid") or ""
    if not uid:
        raise HTTPException(status_code=401, detail="missing_cg_uid_cookie")

    tp = _tokens_path(uid)
    if not tp.exists():
        raise HTTPException(status_code=401, detail="missing_server_tokens_for_user")

    # Sprint 4: sørg for at denne rid’en blir en del av "mine rides"
    rides_now = _add_ride_to_sessions_index(uid, str(rid))

    tokens = _read_json_utf8_sig(tp)

    # pre-flight refresh (utløpt -> refresh nå, og lagre)
    tokens = _maybe_refresh_and_save(uid, tokens, tp)

    meta, streams = _fetch_activity_and_streams(rid, uid, tokens, tp)

    # profile: for sprint 2 kan vi holde dette minimalt; analyze har egne defaults/overrides
    profile: Dict[str, Any] = {}

    samples = _build_samples_v1(meta, streams)

    session_doc = {
        "profile": profile,
        "samples": samples,
        "weather_hint": {},  # beholdes som objekt (analyze kan fylle)
        "strava": {
            "activity_id": str(rid),
            "mode": "indoor" if meta.get("trainer") or meta.get("sport_type") == "VirtualRide" else "outdoor",
            "start_date": meta.get("start_date"),
        },
    }

    paths = _write_session_v1(uid, rid, session_doc)

    # Pull debug fields up to function scope so we can always include them in response
    debug_session_written = paths.get("debug_session_written", debug_session_written)
    debug_session_path = paths.get("debug_session_path", debug_session_path)

    analyze = _trigger_analyze_local(rid)

    return {
        "ok": True,
        "uid": uid,
        "rid": str(rid),
        "index_rides_count": len(rides_now),
        "index_path": str(_sessions_index_path(uid)).replace("\\", "/"),
        "session_paths": {
            "ts_path": paths.get("ts_path"),
            "latest_path": paths.get("latest_path"),
        },
        "samples_len": len(samples),
        "analyze": analyze,
        # Patch 3X: proof of running code + debug mirror status
        "fingerprint": FP,
        "debug_session_written": debug_session_written,
        "debug_session_path": debug_session_path,
    }