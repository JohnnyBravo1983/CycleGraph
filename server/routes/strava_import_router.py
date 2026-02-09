# server/routes/strava_import_router.py
from __future__ import annotations

import os
import sys
import json
import math
import time
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Query

from server.auth_guard import require_auth
from server.user_state import state_root


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


def _user_dir(uid: str) -> Path:
    return state_root() / "users" / uid


def _ssot_user_session_path(uid: str, rid: str) -> Path:
    rid2 = str(rid)
    return state_root() / "users" / uid / "sessions" / f"session_{rid2}.json"


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


def _rebuild_sessions_index_from_sessions_dir(uid: str) -> List[str]:
    """
    PATCH 4B: batch-commit "belt and suspenders".
    Rebuild sessions_index.json strictly from users/<uid>/sessions/session_*.json
    """
    udir = _user_dir(uid)
    sdir = udir / "sessions"
    sdir.mkdir(parents=True, exist_ok=True)

    ids: List[str] = []
    for p in sdir.glob("session_*.json"):
        sid = p.stem.replace("session_", "")
        if sid.isdigit():
            ids.append(sid)

    uniq = sorted(set(ids), key=lambda x: int(x), reverse=True)
    payload = {"sessions": uniq}
    idxp = _sessions_index_path(uid)
    tmp = idxp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, idxp)
    return uniq


# ----------------------------
# SSOT helpers (sessions_index.json) - NEW FUNCTIONS
# ----------------------------
def _sessions_dir(uid: str) -> Path:
    return _user_dir(uid) / "sessions"


def _list_session_ids_on_disk(uid: str) -> List[str]:
    sdir = _sessions_dir(uid)
    if not sdir.exists():
        return []
    out: List[str] = []
    for p in sdir.glob("session_*.json"):
        sid = p.stem.replace("session_", "").strip()
        if sid.isdigit():
            out.append(sid)
    # newest-ish first
    out = sorted(set(out), reverse=True)
    return out


def _read_existing_index_ids(uid: str) -> set[str]:
    p = _sessions_index_path(uid)
    if not p.exists():
        return set()
    try:
        obj = json.loads(p.read_text(encoding="utf-8-sig"))
        if isinstance(obj, dict):
            arr = obj.get("sessions")
            if isinstance(arr, list):
                return set(str(x).strip() for x in arr if str(x).strip().isdigit())
        return set()
    except Exception:
        return set()


def _maybe_batch_analyze(uid: str, session_ids: List[str]) -> None:
    """
    Best-effort analyze. Must NOT crash import/sync if analysis fails.
    """
    try:
        if not session_ids:
            return
        # local import to avoid circulars
        from server.routes.sessions import batch_analyze_sessions_internal

        batch_analyze_sessions_internal(str(uid), [str(x) for x in session_ids])
    except Exception as e:
        print("[STRAVA][ANALYZE] batch analyze failed:", repr(e))


# ----------------------------
# Sprint 4: sessions_meta.json helpers (list-view cache)
# Dict format: { "<sid>": { ...fields... } }
# ----------------------------
def _sessions_meta_path_v1(uid: str) -> Path:
    return _user_dir(uid) / "sessions_meta.json"


def _load_sessions_meta_v1(uid: str) -> Dict[str, Any]:
    p = _sessions_meta_path_v1(uid)
    if not p.exists():
        return {}
    try:
        obj = _read_json_utf8_sig(p)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _save_sessions_meta_v1(uid: str, obj: Dict[str, Any]) -> None:
    p = _sessions_meta_path_v1(uid)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def _meta_upsert_v1(uid: str, sid: str, patch: Dict[str, Any]) -> None:
    sid = str(sid)
    meta = _load_sessions_meta_v1(uid)
    row = meta.get(sid)
    if not isinstance(row, dict):
        row = {}
        meta[sid] = row
    for k, v in patch.items():
        row[k] = v
    _save_sessions_meta_v1(uid, meta)


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


def _write_json_atomic(p: Path, obj: Dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


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
# Strava lock helpers (SSOT)
# ----------------------------
def _lock_paths(uid: str) -> Tuple[Path, Path]:
    user_dir = state_root() / "users" / uid
    return (user_dir / ".strava_lock.json", user_dir / ".strava_lock")  # json SSOT, legacy fallback


def _read_strava_lock(uid: str) -> Optional[Dict[str, Any]]:
    p_json, p_legacy = _lock_paths(uid)
    p = p_json if p_json.exists() else (p_legacy if p_legacy.exists() else None)
    if not p:
        return None
    try:
        return _read_json_utf8_sig(p)
    except Exception:
        return None


def _write_strava_lock(uid: str, lock: Dict[str, Any]) -> None:
    p_json, _ = _lock_paths(uid)
    try:
        p_json.parent.mkdir(parents=True, exist_ok=True)
        p_json.write_text(json.dumps(lock, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# ----------------------------
# strava api (med auto-refresh + retry + 429 handling)
# PATCH 1: Observability + FAIL-FAST on 429 (no sleep / no retries)
# ----------------------------
def _strava_get(path: str, uid: str, tokens: Dict[str, Any], token_path: Path) -> Any:
    now = dt.datetime.now(dt.timezone.utc)

    # 0) Lock gate (do NOT call Strava when locked)
    lock = _read_strava_lock(uid)
    if isinstance(lock, dict) and lock.get("locked") is True:
        locked_until = lock.get("locked_until_utc")

        # beregn retry_after_seconds
        retry_after_s = 60
        try:
            if isinstance(locked_until, str) and locked_until.endswith("Z"):
                dt_until = dt.datetime.strptime(locked_until, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=dt.timezone.utc
                )
                now2 = dt.datetime.now(tz=dt.timezone.utc)
                retry_after_s = max(1, int((dt_until - now2).total_seconds()))
        except Exception:
            retry_after_s = 60

        reason = lock.get("reason") or "locked"
        print(
            f"[STRAVA] LOCKED (skip request) endpoint={path} "
            f"retry_after={retry_after_s}s reason={reason}"
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "strava_rate_limited",
                "reason": reason,
                "retry_after_seconds": retry_after_s,
                "endpoint": path,
                "locked_until_utc": locked_until,
            },
        )

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
    read_usage = r.headers.get("x-readratelimit-usage") or r.headers.get("X-ReadRateLimit-Usage")
    read_limit = r.headers.get("x-readratelimit-limit") or r.headers.get("X-ReadRateLimit-Limit")
    ra = r.headers.get("Retry-After")
    reset = r.headers.get("x-ratelimit-reset") or r.headers.get("X-RateLimit-Reset")

    print(
        f"[STRAVA] resp status={r.status_code} endpoint={path} "
        f"usage={usage} limit={limit} read_usage={read_usage} read_limit={read_limit} "
        f"retry_after={ra} reset={reset}"
    )

    # If we can detect daily read limit exceeded, write lock until next UTC midnight
    try:
        if isinstance(read_usage, str) and isinstance(read_limit, str):
            read_used_today = int(read_usage.split(",")[1].strip())
            read_limit_today = int(read_limit.split(",")[1].strip())
            if read_used_today >= read_limit_today:
                tomorrow = now + dt.timedelta(days=1)
                next_midnight = dt.datetime(
                    year=tomorrow.year,
                    month=tomorrow.month,
                    day=tomorrow.day,
                    tzinfo=dt.timezone.utc,
                )
                lock_payload = {
                    "locked": True,
                    "reason": "read_daily_limit_exceeded",
                    "locked_at_utc": now.isoformat().replace("+00:00", "Z"),
                    "locked_until_utc": next_midnight.isoformat().replace("+00:00", "Z"),
                    "read_usage": read_usage,
                    "read_limit": read_limit,
                }
                _write_strava_lock(uid, lock_payload)
    except Exception:
        pass

    # 429: rate limited (FAIL-FAST)
    if r.status_code == 429:
        try:
            retry_after_s = int(ra) if ra is not None else 60
        except Exception:
            retry_after_s = 60

        print(
            f"[STRAVA] 429 rate limit FAIL-FAST endpoint={path} "
            f"retry_after={retry_after_s}s usage={usage} limit={limit} "
            f"read_usage={read_usage} read_limit={read_limit}"
        )

        raise HTTPException(
            status_code=429,
            detail={
                "error": "strava_rate_limited",
                "retry_after_seconds": retry_after_s,
                "endpoint": path,
                "x_ratelimit_usage": usage,
                "x_ratelimit_limit": limit,
                "x_readratelimit_usage": read_usage,
                "x_readratelimit_limit": read_limit,
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

        usage = r.headers.get("x-ratelimit-usage") or r.headers.get("X-RateLimit-Usage")
        limit = r.headers.get("x-ratelimit-limit") or r.headers.get("X-RateLimit-Limit")
        read_usage = r.headers.get("x-readratelimit-usage") or r.headers.get("X-ReadRateLimit-Usage")
        read_limit = r.headers.get("x-readratelimit-limit") or r.headers.get("X-ReadRateLimit-Limit")
        ra = r.headers.get("Retry-After")
        reset = r.headers.get("x-ratelimit-reset") or r.headers.get("X-RateLimit-Reset")

        print(
            f"[STRAVA] resp status={r.status_code} endpoint={path} "
            f"usage={usage} limit={limit} read_usage={read_usage} read_limit={read_limit} "
            f"retry_after={ra} reset={reset}"
        )

        if r.status_code == 429:
            try:
                retry_after_s = int(ra) if ra is not None else 60
            except Exception:
                retry_after_s = 60

            print(
                f"[STRAVA] 429 rate limit FAIL-FAST endpoint={path} "
                f"retry_after={retry_after_s}s usage={usage} limit={limit} "
                f"read_usage={read_usage} read_limit={read_limit}"
            )

            raise HTTPException(
                status_code=429,
                detail={
                    "error": "strava_rate_limited",
                    "retry_after_seconds": retry_after_s,
                    "endpoint": path,
                    "x_ratelimit_usage": usage,
                    "x_ratelimit_limit": limit,
                    "x_readratelimit_usage": read_usage,
                    "x_readratelimit_limit": read_limit,
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

    # NEW (SSOT): write canonical session for this user
    try:
        ssot_p = _ssot_user_session_path(uid, rid)
        _write_json_atomic(ssot_p, doc)
    except Exception as e:
        print(f"[SSOT] session write failed rid={rid} uid={uid} err={e!r}", file=sys.stderr)

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
# PATCH 2.4-B (A2): chunked/resumable sync endpoint
# ----------------------------
def _epoch_now() -> int:
    return int(time.time())


@router.post("/sync")
async def sync_strava_activities(
    request: Request,
    user_id: str = Depends(require_auth),
    # tidsvindu
    after: Optional[int] = Query(None, description="Epoch seconds (UTC). If omitted, uses now-days."),
    before: Optional[int] = Query(None, description="Epoch seconds (UTC). If omitted, uses now."),
    days: int = Query(30, ge=1, le=365, description="Used when after is omitted."),
    # chunking/paging
    page: int = Query(1, ge=1, le=200, description="Strava paging (1..). Start page."),
    per_page: int = Query(50, ge=1, le=200, description="Strava per_page."),
    batch_limit: int = Query(150, ge=1, le=200, description="Max rides imported this call."),
    max_activities: int = Query(150, ge=1, le=150, description="Early onboarding cap (MVP)."),
    analyze: bool = Query(True, description="Run local analyze step for each ride."),
    sweep: bool = Query(True, description="If true, auto-page until done (or caps). Signup-friendly."),
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

    cur_page = int(page)
    total_seen = 0

    next_page: Optional[int] = None
    done = False
    done_strava = False
    done_cap = False
    stop_mid_page = False

    while True:
        url_path = (
            f"/athlete/activities?after={after_ts}&before={before_ts}"
            f"&per_page={per_page}&page={cur_page}"
        )

        # ✅ PATCH: wrap _strava_get and convert 429 into resumable 200 payload
        try:
            acts = _strava_get(url_path, uid, tokens, tp)
        except HTTPException as he:
            if he.status_code == 429:
                retry_after_s = 15
                if isinstance(he.detail, dict):
                    retry_after_s = int(he.detail.get("retry_after_seconds") or retry_after_s)
                return {
                    "ok": True,
                    "uid": uid,
                    "after": after_ts,
                    "before": before_ts,
                    "days": days if after is None else None,
                    "page": cur_page,
                    "per_page": per_page,
                    "batch_limit": batch_limit,
                    "max_activities": max_activities,
                    "imported_count": len(imported),
                    "imported": imported,
                    "index_count": 0,
                    "errors_count": len(errors),
                    "errors": errors[:50],
                    "skipped_count": len(skipped),
                    "skipped": skipped[:50],
                    "next_page": cur_page,
                    "done": False,
                    "rate_limited": True,
                    "retry_after_s": retry_after_s,
                    "rate_limit_detail": he.detail if isinstance(he.detail, dict) else None,
                }
            raise

        if not isinstance(acts, list):
            errors.append({"rid": None, "detail": "strava_activities_not_list"})
            done = True
            next_page = None
            break

        # If empty page -> done for this window
        if len(acts) == 0:
            done_strava = True
            done = True
            next_page = None
            break

        # Import this page (may stop mid-page due to caps)
        for a in acts:
            # caps (total per call + onboarding cap)
            if len(imported) >= int(batch_limit):
                stop_mid_page = True
                break
            if (len(imported) + len(skipped)) >= int(max_activities):
                stop_mid_page = True
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
                # In sync, we set analyze=False and will run batch analyze at the end.
                out = _import_one(uid=uid, rid=rid_s, cg_auth=cg_auth, analyze=False)

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

        total_seen += len(acts)

        # Page/window done checks
        done_strava = len(acts) < int(per_page)
        done_cap = ((cur_page * int(per_page)) >= int(max_activities)) or (
            (len(imported) + len(skipped)) >= int(max_activities)
        )
        done_batch = len(imported) >= int(batch_limit)

        done = bool(done_strava or done_cap or done_batch)

        if done:
            # If we stopped mid-page due to batch/cap, safest resume is same page.
            if stop_mid_page and not done_strava:
                next_page = cur_page
            else:
                next_page = None if (done_strava or done_cap) else (cur_page + 1)
            break

        # Auto-page only if sweep=True
        if not sweep:
            next_page = cur_page + 1
            break

        cur_page += 1

    # PATCH 4B: SSOT batch-commit: ensure index matches sessions/ after this call
    canonical = _rebuild_sessions_index_from_sessions_dir(uid)

    # ========== AUTO-ANALYZE PATCH ==========
    ensured: List[str] = []
    analyzed_count = 0

    if analyze and imported:
        # Lazy import to avoid circular dependency
        from server.routes.sessions import batch_analyze_sessions_internal

        try:
            result = await batch_analyze_sessions_internal(user_id=uid, force=False, debug=0)
            analyzed_count = result.get("analyzed", 0)
            print(f"[SYNC] Auto-analyzed {analyzed_count}/{len(imported)} sessions", file=sys.stderr)
        except Exception as e:
            print(f"[SYNC] Auto-analyze failed: {e}", file=sys.stderr)

        ensured = imported
    # ========== END AUTO-ANALYZE PATCH ==========

    return {
        "ok": True,
        "uid": uid,
        "after": after_ts,
        "before": before_ts,
        "days": days if after is None else None,
        "page": cur_page,
        "per_page": per_page,
        "batch_limit": batch_limit,
        "max_activities": max_activities,
        "sweep": sweep,
        "total_seen": total_seen,
        "imported_count": len(imported),
        "imported": imported,
        "index_count": len(canonical),
        "errors_count": len(errors),
        "errors": errors[:50],
        "skipped_count": len(skipped),
        "skipped": skipped[:50],
        "next_page": next_page,
        "done": bool(next_page is None and done),
        "capped": bool(done_cap and not done_strava),
        "stopped_mid_page": bool(stop_mid_page),
        "resume_same_page": bool(next_page == cur_page and stop_mid_page),
        "ensure_analyze_count": len(ensured),
        "ensure_analyze": ensured[:50],
        "auto_analyzed": analyzed_count,
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

    # --- PATCH A: distance_km from Strava (meters -> km) ---
    dist_m = meta.get("distance") if isinstance(meta, dict) else None
    try:
        distance_km = float(dist_m) / 1000.0 if dist_m is not None else None
    except Exception:
        distance_km = None

    # ------------------------------------------------------------
    # SSOT metadata (distance, hr, duration) — primary from Strava meta
    # ------------------------------------------------------------
    distance_m_meta = meta.get("distance") if isinstance(meta, dict) else None
    distance_km_meta = (float(distance_m_meta) / 1000.0) if isinstance(distance_m_meta, (int, float)) else None

    # Prefer Strava activity.distance; fallback to streams-derived distance_km
    distance_km_final = distance_km_meta if distance_km_meta is not None else distance_km
    distance_m_final = float(distance_m_meta) if isinstance(distance_m_meta, (int, float)) else None

    # Duration (prefer elapsed_time; fallback moving_time)
    elapsed_s = None
    moving_s = None
    if isinstance(meta, dict):
        et = meta.get("elapsed_time")
        mt = meta.get("moving_time")
        if isinstance(et, (int, float)) and et > 0:
            elapsed_s = int(et)
        if isinstance(mt, (int, float)) and mt > 0:
            moving_s = int(mt)

    # Heart rate (avg/max) — from Strava activity meta (most reliable)
    avg_hr_bpm = None
    max_hr_bpm = None
    if isinstance(meta, dict):
        ah = meta.get("average_heartrate")
        mh = meta.get("max_heartrate")
        if isinstance(ah, (int, float)) and ah > 0:
            avg_hr_bpm = float(ah)
        if isinstance(mh, (int, float)) and mh > 0:
            max_hr_bpm = float(mh)

    # End time (optional): compute if we have start_time + elapsed_s
    end_time = None
    try:
        if isinstance(meta, dict) and elapsed_s:
            # start_date is typically ISO8601 (UTC) from Strava
            st = meta.get("start_date")
            if isinstance(st, str) and st:
                # robust parse: accept "Z" suffix
                st2 = st.replace("Z", "+00:00")
                dt0 = dt.datetime.fromisoformat(st2)
                dt1 = dt0 + dt.timedelta(seconds=int(elapsed_s))
                end_time = dt1.isoformat().replace("+00:00", "Z")
    except Exception:
        end_time = None

    profile: Dict[str, Any] = {}
    samples = _build_samples_v1(meta, streams)

    session_doc = {
        "profile": profile,
        "samples": samples,
        "weather_hint": {},
        # SSOT core fields (for list + analyze)
        "distance_km": distance_km_final,
        "distance_m": distance_m_final,
        "avg_hr_bpm": avg_hr_bpm,
        "max_hr_bpm": max_hr_bpm,
        "elapsed_s": elapsed_s,
        "moving_s": moving_s,
        "end_time": end_time,
        "strava": {
            "activity_id": str(rid),
            "sport_type": sport_type,
            "type": meta.get("type") if isinstance(meta, dict) else None,
            "mode": "indoor"
            if (
                isinstance(meta, dict)
                and (meta.get("trainer") or meta.get("sport_type") == "VirtualRide")
            )
            else "outdoor",
            "start_date": meta.get("start_date") if isinstance(meta, dict) else None,
        },
    }

    paths = _write_session_v1(uid, rid, session_doc)

    # ✅ Deterministic list metadata (so Rides list can render without analyze)
    try:
        start_time = meta.get("start_date") if isinstance(meta, dict) else None

        _meta_upsert_v1(
            uid,
            rid,
            {
                "session_id": str(rid),
                "start_time": start_time,
                "end_time": end_time,
                "sport_type": sport_type,
                "distance_km": distance_km_final,
                "distance_m": distance_m_final,
                "avg_hr_bpm": avg_hr_bpm,
                "max_hr_bpm": max_hr_bpm,
                "elapsed_s": elapsed_s,
                "moving_s": moving_s,
                "precision_watt_avg": None,  # enriched after analyze
                "address": None,  # enriched later
                "has_result": False,
            },
        )
    except Exception as e:
        print("[STRAVA_IMPORT] meta_upsert_v1_err:", repr(e))

    debug_session_written = paths.get("debug_session_written", debug_session_written)
    debug_session_path = paths.get("debug_session_path", debug_session_path)

    # PATCH 4A: index commit skal skje etter analyze (eller uten analyze)
    analyze_out = None
    rides_now: List[str] = []

    if analyze:
        try:
            _maybe_batch_analyze(uid, [rid])
            analyze_out = {"status": "batch_analyze_called"}
        except Exception:
            # best-effort rollback: remove SSOT session so index never points to partial state
            try:
                ssot_p = _ssot_user_session_path(uid, rid)
                if ssot_p.exists():
                    ssot_p.unlink()
            except Exception as e2:
                print("[STRAVA_IMPORT] rollback_ssot_session_err:", repr(e2))
            raise

    # 3) Update index LAST (atomic commit point)
    # (runs both when analyze=True succeeds and when analyze=False)
    rides_now = _add_ride_to_sessions_index(uid, rid)

    # Canonicalize sessions_index.json (keep your existing behavior)
    try:
        _ = _sessions_index_path(uid)
    except Exception as e:
        print("[STRAVA_IMPORT] canonicalize_index_err:", repr(e))

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
