from __future__ import annotations

import os
import json
import math
import time
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Query

from server.auth_guard import require_auth

router = APIRouter(prefix="/api/strava", tags=["strava-import"])

STRAVA_AUTH_BASE = "https://www.strava.com/api/v3"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

# ----------------------------
# Activity filtering (CycleGraph = cycling only)
# ----------------------------
_ALLOWED_SPORT_TYPES = {
    # common cycling sports in Strava
    "Ride",
    "VirtualRide",
    "EBikeRide",
    "MountainBikeRide",
    "GravelRide",
    "EMountainBikeRide",
}


def _activity_sport_type(obj: Dict[str, Any]) -> Optional[str]:
    # Strava can return both "sport_type" and "type" depending on endpoint
    st = obj.get("sport_type")
    if isinstance(st, str) and st.strip():
        return st.strip()
    t = obj.get("type")
    if isinstance(t, str) and t.strip():
        return t.strip()
    return None


def _is_supported_cycling_activity(obj: Dict[str, Any]) -> bool:
    st = _activity_sport_type(obj)
    # If unknown/missing, we treat as "unknown" and allow it through to meta-check later
    if st is None:
        return True
    return st in _ALLOWED_SPORT_TYPES


# ----------------------------
# paths / io
# ----------------------------
def _repo_root_from_here() -> Path:
    # server/routes/.. -> repo root
    return Path(__file__).resolve().parents[2]


def _debug_fs(where: str, uid: Optional[str] = None) -> None:
    """
    Debug helper to understand where we write state/users/<uid> on Fly.
    Safe to keep for now; produces log lines only.
    """
    try:
        cwd = Path.cwd()
        repo = _repo_root_from_here()
        state = repo / "state"
        users = state / "users"
        target = (users / uid) if uid else None

        print(f"[FSDBG] where={where}")
        print(f"[FSDBG] cwd={cwd} exists={cwd.exists()}")
        print(f"[FSDBG] __file__={Path(__file__).resolve()}")
        print(f"[FSDBG] repo_root={repo} exists={repo.exists()}")
        print(f"[FSDBG] state={state} exists={state.exists()}")
        print(f"[FSDBG] users={users} exists={users.exists()}")

        # list a few entries defensively (avoid huge spam)
        try:
            print(f"[FSDBG] cwd_list={sorted([p.name for p in cwd.iterdir()])[:40]}")
        except Exception as e:
            print(f"[FSDBG] cwd_list_error={type(e).__name__}: {e}")

        try:
            if repo.exists():
                print(f"[FSDBG] repo_list={sorted([p.name for p in repo.iterdir()])[:40]}")
        except Exception as e:
            print(f"[FSDBG] repo_list_error={type(e).__name__}: {e}")

        if target is not None:
            print(f"[FSDBG] user_dir={target} exists={target.exists()}")

    except Exception as e:
        print(f"[FSDBG] ERROR where={where}: {type(e).__name__}: {e}")


from server.user_state import state_root


def _user_dir(uid: str) -> Path:
    return state_root() / "users" / uid


def _tokens_path(uid: str) -> Path:
    return _user_dir(uid) / "strava_tokens.json"


# ----------------------------
# Debug input control
# ----------------------------
def _allow_debug_inputs() -> bool:
    """Return True if debug inputs are allowed via environment variable."""
    return os.getenv("CG_ALLOW_DEBUG_INPUTS", "").lower() in ("1", "true", "yes")


# ----------------------------
# Sprint 4: sessions_index.json helpers
# ----------------------------
def _sessions_index_path(uid: str) -> Path:
    return _user_dir(uid) / "sessions_index.json"


# ✅ PATCH 2.3.1 (minimal og trygg): SSOT = {"sessions":[...]} + backward compat
def _load_sessions_index(uid: str) -> list[str]:
    p = _sessions_index_path(uid)
    if not p.exists():
        return []
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))

        # ✅ Backward compat: accept dict keys used across codebase
        if isinstance(obj, dict):
            for key in ("sessions", "rides", "ride_ids", "session_ids", "ids", "value"):
                v = obj.get(key)
                if isinstance(v, list):
                    return [str(x) for x in v]
            return []

        # legacy: raw list
        if isinstance(obj, list):
            return [str(x) for x in obj]

        return []
    except Exception:
        return []


def _save_sessions_index(uid: str, rides: list[str]) -> None:
    p = _sessions_index_path(uid)
    p.parent.mkdir(parents=True, exist_ok=True)

    # ✅ Write SSOT in canonical format expected by ownership checks
    payload = {"sessions": [str(x) for x in rides]}
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _add_ride_to_sessions_index(uid: str, rid: str) -> list[str]:
    rid = str(rid).strip()

    # ✅ hard gate: match sessions_list_router rules
    if (not rid.isdigit()) or (len(rid) > 20):
        print("[STRAVA_IMPORT] skip invalid rid for index:", rid)
        return _load_sessions_index(uid)

    rides = _load_sessions_index(uid)
    if rid not in rides:
        rides.insert(0, rid)
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
# strava api (med auto-refresh + retry + 429 handling)
# PATCH 1: Observability + FAIL-FAST on 429 (no sleep / no retries)
# ----------------------------
def _strava_get(path: str, uid: str, tokens: Dict[str, Any], token_path: Path) -> Any:
    tokens = _maybe_refresh_and_save(uid, tokens, token_path)

    access = tokens.get("access_token")
    if not access:
        raise HTTPException(status_code=401, detail="missing_access_token")

    url = f"{STRAVA_AUTH_BASE}{path}"
    headers = {"Authorization": f"Bearer {access}"}

    # Single request (no retry loop)
    r = requests.get(url, headers=headers, timeout=20)

    # Always log rate-limit headers (no tokens)
    usage = r.headers.get("x-ratelimit-usage") or r.headers.get("X-RateLimit-Usage")
    limit = r.headers.get("x-ratelimit-limit") or r.headers.get("X-RateLimit-Limit")
    ra = r.headers.get("Retry-After")
    print(
        f"[STRAVA] resp status={r.status_code} endpoint={path} "
        f"usage={usage} limit={limit} retry_after={ra}"
    )

    # 429: rate limited (FAIL-FAST)
    if r.status_code == 429:
        # Strava sender ofte Retry-After i sekunder (men ikke alltid)
        try:
            retry_after_s = int(ra) if ra is not None else 60
        except Exception:
            retry_after_s = 60

        usage2 = usage
        limit2 = limit

        # LOGG: endpoint + headers (uten tokens)
        print(
            f"[STRAVA] 429 rate limit FAIL-FAST endpoint={path} "
            f"retry_after={retry_after_s}s usage={usage2} limit={limit2}"
        )

        # Returner strukturert detail så frontend kan vise "prøv igjen om X sek"
        raise HTTPException(
            status_code=429,
            detail={
                "error": "strava_rate_limited",
                "retry_after_seconds": retry_after_s,
                "endpoint": path,
                "x_ratelimit_usage": usage2,
                "x_ratelimit_limit": limit2,
            },
        )

    # refresh + retry once on auth failure (kept, but no loops)
    if r.status_code in (401, 403):
        tokens = _maybe_refresh_and_save(uid, tokens, token_path)
        access = tokens.get("access_token")
        if not access:
            raise HTTPException(status_code=401, detail="missing_access_token_after_refresh")
        headers = {"Authorization": f"Bearer {access}"}
        r = requests.get(url, headers=headers, timeout=20)

        # Log again after refresh attempt
        usage = r.headers.get("x-ratelimit-usage") or r.headers.get("X-RateLimit-Usage")
        limit = r.headers.get("x-ratelimit-limit") or r.headers.get("X-RateLimit-Limit")
        ra = r.headers.get("Retry-After")
        print(
            f"[STRAVA] resp status={r.status_code} endpoint={path} "
            f"usage={usage} limit={limit} retry_after={ra}"
        )

        # If still rate-limited after refresh (rare, but handle deterministically)
        if r.status_code == 429:
            try:
                retry_after_s = int(ra) if ra is not None else 60
            except Exception:
                retry_after_s = 60

            print(
                f"[STRAVA] 429 rate limit FAIL-FAST endpoint={path} "
                f"retry_after={retry_after_s}s usage={usage} limit={limit}"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "strava_rate_limited",
                    "retry_after_seconds": retry_after_s,
                    "endpoint": path,
                    "x_ratelimit_usage": usage,
                    "x_ratelimit_limit": limit,
                },
            )

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
            dtu = dt.datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc
            )
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

        heading_deg = last_heading
        if lat_deg is not None and lon_deg is not None and (i + 1) < len(LL):
            nxt = LL[i + 1]
            if (
                isinstance(nxt, (list, tuple))
                and len(nxt) == 2
                and nxt[0] is not None
                and nxt[1] is not None
            ):
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

    # ✅ PATCH: Kun skriv debug_session mirror hvis tillatt via miljøvariabel
    if _allow_debug_inputs():
        try:
            p_debug = root / "_debug" / f"session_{rid}.json"
            debug_session_path = str(p_debug)
            p_debug.parent.mkdir(parents=True, exist_ok=True)

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


# ----------------------------
# Patch 3D: internal analyze call MUST forward cg_auth (not cg_uid)
# ----------------------------
def _trigger_analyze_local(rid: str, cg_auth: Optional[str]) -> Dict[str, Any]:
    base = os.getenv("CG_API_BASE") or "http://localhost:5175"
    url = f"{base}/api/sessions/{rid}/analyze?debug=1"

    cookies: Dict[str, str] = {}
    if cg_auth:
        cookies["cg_auth"] = str(cg_auth)

    try:
        r = requests.post(url, json={}, cookies=cookies, timeout=60)

        out: Dict[str, Any] = {
            "status_code": r.status_code,
            "url": url,
            "forwarded_cookies": list(cookies.keys()),
        }

        try:
            out["json"] = r.json()
        except Exception:
            out["text"] = (r.text or "")[:5000]

        return out
    except Exception as e:
        return {
            "status_code": 0,
            "error": repr(e),
            "url": url,
            "forwarded_cookies": list(cookies.keys()),
        }


# ----------------------------
# PATCH 2.4-B (A2): chunked/resumable sync endpoint
# ----------------------------
def _epoch_now() -> int:
    return int(time.time())


@router.post("/sync")
def sync_strava_activities(
    request: Request,
    user_id: str = Depends(require_auth),
    # tidsvindu
    after: Optional[int] = Query(None, description="Epoch seconds (UTC). If omitted, uses now-days."),
    before: Optional[int] = Query(None, description="Epoch seconds (UTC). If omitted, uses now."),
    days: int = Query(30, ge=1, le=365, description="Used when after is omitted."),
    # chunking/paging
    page: int = Query(1, ge=1, le=200, description="Strava paging (1..). One page per call."),
    per_page: int = Query(50, ge=1, le=200, description="Strava per_page."),
    batch_limit: int = Query(50, ge=1, le=200, description="Max rides imported this call."),
    max_activities: int = Query(150, ge=1, le=150, description="Early onboarding cap (MVP)."),
    analyze: bool = Query(True, description="Run local analyze step for each ride."),
) -> Dict[str, Any]:
    uid = user_id
    tp = _tokens_path(uid)
    if not tp.exists():
        raise HTTPException(status_code=401, detail="missing_server_tokens_for_user")

    tokens = _read_json_utf8_sig(tp)
    tokens = _maybe_refresh_and_save(uid, tokens, tp)

    now_ts = _epoch_now()
    before_ts = int(before) if before is not None else now_ts
    after_ts = int(after) if after is not None else (before_ts - int(days) * 86400)

    # Forward auth cookie into analyze call (same as /import/{rid})
    cg_auth = request.cookies.get("cg_auth")

    imported: List[str] = []
    errors: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    # One Strava page per call (resumable)
    url_path = (
        f"/athlete/activities?after={after_ts}&before={before_ts}"
        f"&per_page={per_page}&page={page}"
    )

    # ✅ PATCH: wrap _strava_get and convert 429 into resumable 200 payload
    try:
        acts = _strava_get(url_path, uid, tokens, tp)
    except HTTPException as he:
        if he.status_code == 429:
            retry_after_s = 15
            # If we get structured detail, pass it through
            if isinstance(he.detail, dict):
                retry_after_s = int(he.detail.get("retry_after_seconds") or retry_after_s)
            return {
                "ok": True,
                "uid": uid,
                "after": after_ts,
                "before": before_ts,
                "days": days if after is None else None,
                "page": page,
                "per_page": per_page,
                "batch_limit": batch_limit,
                "max_activities": max_activities,
                "imported_count": len(imported),
                "imported": imported,
                "errors_count": len(errors),
                "errors": errors[:50],
                "skipped_count": len(skipped),
                "skipped": skipped[:50],
                "next_page": page,  # samme page igjen
                "done": False,
                "rate_limited": True,
                "retry_after_s": retry_after_s,
                "rate_limit_detail": he.detail if isinstance(he.detail, dict) else None,
            }
        raise

    if not isinstance(acts, list):
        raise HTTPException(status_code=502, detail="strava_bad_payload")

    # If empty page -> done for this window
    if len(acts) == 0:
        return {
            "ok": True,
            "uid": uid,
            "after": after_ts,
            "before": before_ts,
            "days": days if after is None else None,
            "page": page,
            "per_page": per_page,
            "batch_limit": batch_limit,
            "max_activities": max_activities,
            "imported_count": 0,
            "imported": [],
            "errors_count": 0,
            "errors": [],
            "skipped_count": 0,
            "skipped": [],
            "next_page": None,
            "done": True,
        }

    # Enkelt "early onboarding cap": stopp etter max_activities basert på page/per_page
    remaining_total = max(0, int(max_activities) - ((int(page) - 1) * int(per_page)))
    if remaining_total <= 0:
        return {
            "ok": True,
            "uid": uid,
            "after": after_ts,
            "before": before_ts,
            "days": days if after is None else None,
            "page": page,
            "per_page": per_page,
            "batch_limit": batch_limit,
            "max_activities": max_activities,
            "imported_count": 0,
            "imported": [],
            "errors_count": len(errors),
            "errors": errors[:50],
            "skipped_count": len(skipped),
            "skipped": skipped[:50],
            "next_page": None,
            "done": True,
            "capped": True,
        }

    page_cap = min(int(batch_limit), remaining_total)

    # PATCH 1B — filtrer i /sync før _import_one
    for a in acts:
        if len(imported) >= page_cap:
            break

        if not isinstance(a, dict):
            continue

        # Skip non-cycling activities early (based on summary fields)
        if not _is_supported_cycling_activity(a):
            rid0 = a.get("id")
            skipped.append(
                {
                    "rid": str(rid0) if rid0 is not None else None,
                    "sport_type": _activity_sport_type(a),
                }
            )
            continue

        rid = a.get("id")
        if rid is None:
            errors.append({"rid": None, "detail": "missing_activity_id"})
            continue

        rid_s = str(rid)

        try:
            out = _import_one(uid=uid, rid=rid_s, cg_auth=cg_auth, analyze=analyze)

            # If meta-check inside _import_one decided to skip, don't count as imported
            if isinstance(out, dict) and out.get("skipped") is True:
                skipped.append({"rid": rid_s, "sport_type": out.get("sport_type")})
                continue

            imported.append(rid_s)

            # ✅ throttle (reduserer 429 dramatisk)
            time.sleep(0.3)

        except HTTPException as he:
            errors.append({"rid": rid_s, "status_code": he.status_code, "detail": he.detail})
        except Exception as e:
            errors.append({"rid": rid_s, "status_code": 0, "detail": repr(e)})

    done_strava = len(acts) < per_page
    done_cap = ((int(page) * int(per_page)) >= int(max_activities))
    done = bool(done_strava or done_cap)

    next_page = None if done else (page + 1)

    return {
        "ok": True,
        "uid": uid,
        "after": after_ts,
        "before": before_ts,
        "days": days if after is None else None,
        "page": page,
        "per_page": per_page,
        "batch_limit": batch_limit,
        "max_activities": max_activities,
        "imported_count": len(imported),
        "imported": imported,
        "errors_count": len(errors),
        "errors": errors[:50],
        "skipped_count": len(skipped),
        "skipped": skipped[:50],
        "next_page": next_page,
        "done": done,
        "capped": bool(done_cap and not done_strava),
    }


def _import_one(uid: str, rid: str, cg_auth: Optional[str], analyze: bool = True) -> Dict[str, Any]:
    rid = str(rid).strip()

    # Keep response-safe debug fields
    debug_session_written: Any = "UNSET"
    debug_session_path: Any = "UNSET"

    tp = _tokens_path(uid)
    if not tp.exists():
        raise HTTPException(status_code=401, detail="missing_server_tokens_for_user")

    tokens = _read_json_utf8_sig(tp)
    tokens = _maybe_refresh_and_save(uid, tokens, tp)

    meta, streams = _fetch_activity_and_streams(rid, uid, tokens, tp)

    # PATCH 1C — Meta-level gate: only store/analyze cycling activities
    sport_type = _activity_sport_type(meta if isinstance(meta, dict) else {})
    if sport_type is not None and sport_type not in _ALLOWED_SPORT_TYPES:
        print(f"[STRAVA_IMPORT] skip non-cycling activity rid={rid} sport_type={sport_type}")
        return {
            "ok": True,
            "uid": uid,
            "rid": str(rid),
            "skipped": True,
            "sport_type": sport_type,
            "reason": "non_cycling_activity",
        }

    # Now it's safe to add to SSOT index
    rides_now = _add_ride_to_sessions_index(uid, rid)

    # Canonicalize sessions_index.json (keep your existing behavior)
    try:
        p = _sessions_index_path(uid)
        raw_obj: Any = {}
        try:
            raw_obj = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception:
            raw_obj = {}

        if isinstance(raw_obj, dict):
            cand = None
            for key in ("sessions", "rides", "ride_ids", "session_ids", "ids", "value"):
                v = raw_obj.get(key)
                if isinstance(v, list):
                    cand = v
                    break
            items = cand or []
        elif isinstance(raw_obj, list):
            items = raw_obj
        else:
            items = []

        cleaned: list[str] = []
        for x in items:
            s = str(x).strip()
            if s.isdigit() and len(s) <= 20:
                cleaned.append(s)
        if rid.isdigit() and len(rid) <= 20 and rid not in cleaned:
            cleaned.insert(0, rid)

        seen = set()
        uniq: list[str] = []
        for s in cleaned:
            if s not in seen:
                uniq.append(s)
                seen.add(s)

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"sessions": uniq}, indent=2), encoding="utf-8")
    except Exception as e:
        print("[STRAVA_IMPORT] canonicalize_index_err:", repr(e))

    profile: Dict[str, Any] = {}
    samples = _build_samples_v1(meta, streams)

    session_doc = {
        "profile": profile,
        "samples": samples,
        "weather_hint": {},
        "strava": {
            "activity_id": str(rid),
            "sport_type": sport_type,
            "type": meta.get("type") if isinstance(meta, dict) else None,
            "mode": "indoor"
            if (isinstance(meta, dict) and (meta.get("trainer") or meta.get("sport_type") == "VirtualRide"))
            else "outdoor",
            "start_date": meta.get("start_date") if isinstance(meta, dict) else None,
        },
    }

    paths = _write_session_v1(uid, rid, session_doc)

    debug_session_written = paths.get("debug_session_written", debug_session_written)
    debug_session_path = paths.get("debug_session_path", debug_session_path)

    analyze_out = None
    if analyze:
        analyze_out = _trigger_analyze_local(rid, cg_auth)

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
        "analyze": analyze_out,
        "debug_session_written": debug_session_written,
        "debug_session_path": debug_session_path,
        "sport_type": sport_type,
    }


@router.post("/import/{rid}")
def import_strava_activity(
    rid: str,
    request: Request,
    user_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    FP = "STRAVA_IMPORT_ROUTER_AUTH_3D_20260114"
    print("[STRAVA_IMPORT]", FP, "rid=", rid)

    uid = user_id

    # Minimal refactor: reuse helper + forward cg_auth into analyze
    cg_auth = request.cookies.get("cg_auth")
    return _import_one(uid=uid, rid=str(rid), cg_auth=cg_auth, analyze=True)
