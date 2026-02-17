from __future__ import annotations

import csv
import json
import os
import re
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import APIRouter, Depends, Query, Request, Response
from server.auth_guard import require_auth
from server.user_state import state_root


router = APIRouter(prefix="/api/sessions", tags=["sessions"])

logger = logging.getLogger(__name__)


# -------------------------------
# PATCH B2/B3: start_time fra resultfil + fingerprint/debug
# -------------------------------
_TABS_RE = re.compile(r'"t_abs"\s*:\s*"([^"]+)"')

# PATCH: end_time seek-from-end (siste t_abs)  (legacy / kan ryddes senere)
_LAST_TABS_RE = re.compile(r'"t_abs"\s*:\s*"([^"]+)"')


def _compute_status(uid: str, sid: str) -> str:
    session_path = state_root() / "users" / uid / "sessions" / f"session_{sid}.json"
    result_path  = state_root() / "users" / uid / "results"  / f"result_{sid}.json"

    if not session_path.exists():
        return "needs_import"
    if not result_path.exists():
        return "needs_analysis"
    return "ready"


# -------------------------------
# PATCH S6-A: Meta derivation helpers
# -------------------------------
def _safe_float(x):
    """
    Safely convert to float, handling NaN and invalid values.
    """
    try:
        if x is None:
            return None
        v = float(x)
        # NaN guard
        if v != v:
            return None
        return v
    except Exception:
        return None


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _distance_km_from_samples(samples: list) -> float | None:
    # samples may contain non-dicts
    s = [x for x in samples if isinstance(x, dict)]
    if not s:
        return None

    # 1) Prefer GPS distance (lat/lon)
    pts: list[tuple[float, float]] = []
    for x in s:
        if x.get("moving") is False:
            continue
        lat = x.get("lat_deg")
        lon = x.get("lon_deg")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            pts.append((float(lat), float(lon)))

    if len(pts) >= 2:
        total_m = 0.0
        last = pts[0]
        for cur in pts[1:]:
            total_m += _haversine_m(last[0], last[1], cur[0], cur[1])
            last = cur
        km = total_m / 1000.0
        if 0.1 <= km <= 400.0:
            return km

    # 2) Fallback: integrate v_ms over t_abs
    total_m = 0.0
    prev_t = None
    prev_v = None
    for x in s:
        if x.get("moving") is False:
            continue
        t = x.get("t_abs")
        v = x.get("v_ms")
        if not isinstance(t, (int, float)) or not isinstance(v, (int, float)):
            continue
        t = float(t)
        v = float(v)
        if prev_t is not None and prev_v is not None:
            dt = t - prev_t
            # guard against bad jumps
            if 0.0 <= dt <= 10.0:
                total_m += prev_v * dt
        prev_t = t
        prev_v = v

    km = total_m / 1000.0
    if 0.1 <= km <= 400.0:
        return km

    return None


def _derive_meta_from_samples(samples: list) -> dict:
    """
    Deterministisk meta fra session samples.
    - hr_avg/hr_max fra samples[].hr
    - elapsed_s + end_time fra samples[0].t_abs og samples[-1].t_abs (epoch seconds)
    - distance_km fra samples (via GPS eller v_ms)
    """
    out = {
        "hr_avg": None,
        "hr_max": None,
        "elapsed_s": None,
        "end_time": None,
        "distance_km": None,
        "elevation_gain_m": None,
    }

    if not isinstance(samples, list) or not samples:
        return out

    # ---- HR ----
    hrs = []
    for s in samples:
        if not isinstance(s, dict):
            continue
        h = s.get("hr")
        if isinstance(h, (int, float)):
            # guard for garbage
            if 30 <= h <= 240:
                hrs.append(float(h))

    if hrs:
        out["hr_avg"] = sum(hrs) / len(hrs)
        out["hr_max"] = max(hrs)

    # ---- elapsed_s + end_time via t_abs ----
    s0 = samples[0] if isinstance(samples[0], dict) else None
    s1 = samples[-1] if isinstance(samples[-1], dict) else None

    t0 = _safe_float(s0.get("t_abs")) if s0 else None
    t1 = _safe_float(s1.get("t_abs")) if s1 else None

    if t0 is not None and t1 is not None and t1 >= t0:
        elapsed = t1 - t0
        # guard: 0..2 døgn
        if 0 <= elapsed <= 60 * 60 * 24 * 2:
            out["elapsed_s"] = int(round(elapsed))
            out["end_time"] = t1  # epoch seconds (float)

    # ---- distance_km ----
    out["distance_km"] = _distance_km_from_samples(samples)
    # ---- elevation_gain_m ----
    gain = 0.0
    prev_alt = None
    for s in samples:
        if not isinstance(s, dict):
            continue
        alt = s.get("altitude_m")
        if isinstance(alt, (int, float)) and -500 < alt < 9000:
            if prev_alt is not None and alt > prev_alt:
                gain += alt - prev_alt
            prev_alt = alt
    out["elevation_gain_m"] = round(gain, 1) if gain > 0 else None
    return out


def _load_sessions_meta(meta_path: Path) -> Dict[str, Any]:
    """
    Load sessions_meta.json safely.
    """
    try:
        if meta_path.exists():
            return json.loads(meta_path.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}


def _atomic_write_json(path: Path, obj: Any) -> None:
    """
    Atomically write JSON to file.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# -------------------------------
# NEW HELPERS (activity distance fallback)
# -------------------------------
def _repo_root_from_here() -> Path:
    """
    Robust repo-root detection.

    This file lives at:
      CycleGraph/frontend/server/routes/sessions_list_router.py

    Prior bug: parents[2] returns ".../frontend" (NOT repo root),
    which caused logs lookup to point at /app/frontend/logs/results.

    We walk upwards and pick the first parent that has a "logs" dir
    (or ".git" / "pyproject.toml" / "frontend" marker), else fallback.
    """
    here = Path(__file__).resolve()

    # Walk up and find a plausible repo root
    for p in here.parents:
        try:
            if (p / "logs").exists():
                return p
            if (p / ".git").exists():
                return p
            if (p / "pyproject.toml").exists():
                return p
            # common project marker(s)
            if (p / "frontend").exists() and (p / "core").exists():
                return p
        except Exception:
            continue

    # Fallback: expected structure: .../frontend/server/routes/<file>
    # parents[3] => CycleGraph repo root
    try:
        return here.parents[3]
    except Exception:
        return here.parents[0]


def _safe_sid(sid: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "", str(sid or ""))


def _logs_results_dir() -> Path:
    """
    SSOT for analyze output in prod container.

    Prefer repo-root/logs/results (works both local + Fly if repo-root detection works),
    else hard fallback to /app/logs/results.
    """
    try:
        root = _repo_root_from_here()
        p = root / "logs" / "results"
        return p
    except Exception:
        return Path("/app/logs/results")


def _logs_result_path(sid: str) -> Path:
    # Match SessionView semantics: if state_root() is /app/state, logs is /app/logs
    sid2 = _safe_sid(sid)
    root = state_root()
    if root.name == "state":
        return root.parent / "logs" / "results" / f"result_{sid2}.json"
    # dev fallback
    return Path(os.getcwd()) / "logs" / "results" / f"result_{sid2}.json"


def _ssot_user_result_path(uid: str, sid: str) -> Path:
    sid2 = _safe_sid(sid)
    return state_root() / "users" / uid / "results" / f"result_{sid2}.json"


def _allow_debug_inputs() -> bool:
    return os.getenv("CG_ALLOW_DEBUG_INPUTS", "").lower() in ("1", "true", "yes")


def _debug_result_path(sid: str) -> Optional[Path]:
    if not _allow_debug_inputs():
        return None
    sid2 = _safe_sid(sid)
    root = state_root()
    if root.name == "state":
        return root.parent / "_debug" / f"result_{sid2}.json"
    return Path(os.getcwd()) / "_debug" / f"result_{sid2}.json"


def _read_json_if_exists(p: Path) -> Optional[Dict[str, Any]]:
    try:
        if p and p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _extract_list_item(sid: str, doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    d = doc or {}
    m = d.get("metrics") or {}
    if not isinstance(m, dict):
        m = {}

    return {
        "ride_id": sid,
        "id": sid,
        "profile_version": (d.get("profile_version") or m.get("profile_version")),
        "weather_source": (d.get("weather_source") or m.get("weather_source")),
        "start_time": (
            d.get("start_time")
            or m.get("start_time")
            or d.get("start_time_iso")
            or m.get("start_time_iso")
        ),
        "distance_km": (
            d.get("distance_km")
            or m.get("distance_km")
            or d.get("distance")
            or m.get("distance")
        ),
        "precision_watt_avg": (
            d.get("precision_watt_avg")
            or m.get("precision_watt_avg")
            or m.get("precision_watt_pedal")
            or m.get("precision_watt")
        ),
    }


def _allowed_ids_list_from_index_doc(index_doc: Any) -> List[str]:
    """
    Returner ride_ids i rekkefølge (best effort) fra sessions_index.json.
    Vi prøver flere kjente keys, men bevarer rekkefølgen i lista.
    """
    out: List[str] = []
    seen: set[str] = set()

    def push(v: Any) -> None:
        s = str(v).strip()
        if not s:
            return
        if s in seen:
            return
        seen.add(s)
        out.append(s)

    if isinstance(index_doc, dict):
        for key in ("sessions", "rides", "ride_ids", "session_ids", "ids", "value"):
            v = index_doc.get(key)
            if isinstance(v, list) and v:
                for x in v:
                    push(x)
                if out:
                    return out

    if isinstance(index_doc, list):
        for x in index_doc:
            push(x)

    return out


def _distance_km_from_activity(sid: str) -> Optional[float]:
    """
    Strava activity JSON har vanligvis 'distance' i meter.
    Vi prøver begge kjente steder i container:
      - /app/data/raw/activity_<sid>.json  (legacy)
      - /app/src/cyclegraph/data/raw/activity_<sid>.json (nåværende)
    """
    root = _repo_root_from_here()
    candidates = [
        root / "data" / "raw" / f"activity_{sid}.json",
        root / "src" / "cyclegraph" / "data" / "raw" / f"activity_{sid}.json",
    ]
    for p in candidates:
        doc = _read_json_if_exists(p)
        if not isinstance(doc, dict):
            continue

        d_m = doc.get("distance")
        if d_m is None and isinstance(doc.get("activity"), dict):
            d_m = doc["activity"].get("distance")

        try:
            if d_m is not None:
                km = float(d_m) / 1000.0
                return round(km, 3)
        except Exception:
            pass

    return None


def _pick_result_path(sid: str, uid: Optional[str] = None) -> Path | None:
    """
    Return the exact result json for a session id.

    Prod data lives on the Fly volume mounted at /app/state, user-scoped.
    We must NOT fuzzy match other files (wrong ride -> wrong metadata).
    """
    if not uid:
        return None

    root = Path("/app/state") / "users" / str(uid)

    cand_dirs: list[Path] = [
        root / "results",
        root / "logs" / "results",
        root / "_debug",
        root / "sessions" / "results",
        root / "sessions",
    ]

    filename = f"result_{sid}.json"

    for d in cand_dirs:
        try:
            exact = d / filename
            if exact.exists() and exact.is_file():
                return exact
        except Exception:
            continue

    try:
        for p in root.rglob(filename):
            if p.is_file():
                return p
    except Exception:
        pass

    return None


def _extract_first_t_abs_fast(path: Path) -> Optional[str]:
    """
    Les kun starten av resultfilen og plukk første forekomst av "t_abs": "...."
    Unngår å parse hele JSON / samples-arrayet.
    """
    try:
        with path.open("rb") as f:
            chunk = f.read(512_000)
        text = chunk.decode("utf-8", errors="ignore")
        m = _TABS_RE.search(text)
        if not m:
            return None
        return m.group(1)
    except Exception:
        return None


def _extract_last_t_abs_seek(
    p: Path, max_bytes: int = 8 * 1024 * 1024, chunk_size: int = 256 * 1024
) -> Optional[str]:
    """
    Finn siste "t_abs": "..." ved å lese bakover i chunks.
    (legacy / kan ryddes senere)
    """
    try:
        size = p.stat().st_size
        with p.open("rb") as f:
            read_total = 0
            pos = size
            buf = ""

            while pos > 0 and read_total < max_bytes:
                step = min(chunk_size, pos)
                pos -= step
                f.seek(pos)
                chunk = f.read(step)
                read_total += step

                txt = chunk.decode("utf-8", errors="ignore")
                buf = txt + buf

                matches = list(_LAST_TABS_RE.finditer(buf))
                if matches:
                    return matches[-1].group(1)

            return None
    except Exception:
        return None


def _compute_distance_km_from_result(p: Path) -> Optional[float]:
    """
    Fallback: beregn distanse fra samples ved å summere v_ms * dt.
    (legacy / kan ryddes senere)
    """
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        samples = obj.get("samples")
        if not isinstance(samples, list) or len(samples) < 2:
            return None

        dist_m = 0.0
        prev_t = None
        prev_v = None

        for s in samples:
            if not isinstance(s, dict):
                continue
            t = s.get("t")
            v = s.get("v_ms")
            if not isinstance(t, (int, float)) or not isinstance(v, (int, float)):
                continue

            if prev_t is not None and prev_v is not None:
                dt = float(t) - float(prev_t)
                if dt > 0 and dt < 60:
                    dist_m += 0.5 * (float(prev_v) + float(v)) * dt

            prev_t = t
            prev_v = v

        km = dist_m / 1000.0
        return km if km > 0 else None
    except Exception:
        return None


def _extract_end_time_and_km_from_result(p: Path) -> tuple[Optional[str], Optional[float]]:
    """
    Legacy C4 helper (ikke brukt etter PATCH C4-REPLACE).
    Lar den stå for nå for å unngå å miste noe underveis.
    """
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        samples = obj.get("samples")
        if not isinstance(samples, list) or len(samples) < 2:
            print("[LIST/ALL][C4 RETURN]", None, None)
            return (None, None)

        end_abs: Optional[str] = None
        for s in reversed(samples):
            if isinstance(s, dict):
                ta = s.get("t_abs")
                if isinstance(ta, str) and ta:
                    end_abs = ta
                    break

        dist_m = 0.0
        prev_t = None
        prev_v = None

        for s in samples:
            if not isinstance(s, dict):
                continue
            t = s.get("t")
            v = s.get("v_ms")
            if not isinstance(t, (int, float)) or not isinstance(v, (int, float)):
                continue

            if prev_t is not None and prev_v is not None:
                dt = float(t) - float(prev_t)
                if 0 < dt < 60:
                    dist_m += 0.5 * (float(prev_v) + float(v)) * dt

            prev_t = t
            prev_v = v

        km = dist_m / 1000.0
        if km <= 0:
            km = None

        print("[LIST/ALL][C4 RETURN]", end_abs, km)
        return (end_abs, km)
    except Exception:
        print("[LIST/ALL][C4 RETURN]", None, None)
        return (None, None)


def _parse_dt(s: str) -> Optional[datetime]:
    if not isinstance(s, str) or not s.strip():
        return None
    ss = s.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ss)
    except Exception:
        return None


def _fmt_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# -------------------------------
# PATCH C4-REPLACE: "siste mile"
# -------------------------------


def _json_load_any(p: Path) -> Optional[dict]:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print("[LIST/ALL][C4] json load failed sid=", p.stem, "err=", repr(e))
            return None


def _extract_end_and_km_from_samples(samples: list) -> Tuple[Optional[str], Optional[float]]:
    if not samples:
        return None, None

    end_time: Optional[str] = None
    for s in reversed(samples):
        if not isinstance(s, dict):
            continue
        ta = s.get("t_abs")
        if isinstance(ta, str) and ta:
            end_time = ta
            break

    dist_m: Optional[float] = None
    for s in reversed(samples):
        if not isinstance(s, dict):
            continue
        dm = s.get("distance_m")
        if isinstance(dm, (int, float)):
            dist_m = float(dm)
            break

    km = (dist_m / 1000.0) if dist_m is not None else None
    return end_time, km


def _compute_end_time_and_km(root: Path, sid: str) -> Tuple[Optional[str], Optional[float]]:
    print("[LIST/ALL][C4 ENTER] sid=", sid)

    # NOTE: this call requires uid, but kept as-is (legacy debug path).
    rp = _pick_result_path(sid)
    if rp and rp.exists():
        print("[LIST/ALL][C4] using file:", str(rp))
        doc = _json_load_any(rp)
        if isinstance(doc, dict):
            samples = doc.get("samples")
            if isinstance(samples, list) and len(samples) > 0:
                end_time, km = _extract_end_and_km_from_samples(samples)

                if km is None:
                    dk = doc.get("distance_km")
                    if isinstance(dk, (int, float)):
                        km = float(dk)

                print("[LIST/ALL][C4 RETURN]", end_time, km)
                return end_time, km

    cand: List[Path] = []
    cand.append(root / "logs" / "actual10" / "latest" / f"session_{sid}.json")

    try:
        cand.extend(sorted(root.glob(f"logs/actual*/latest/session_{sid}.json")))
    except Exception:
        pass

    cand.append(root / "_debug" / f"session_{sid}.json")

    for sp in cand:
        if sp.exists() and sp.is_file():
            print("[LIST/ALL][C4] fallback session file:", str(sp))
            sdoc = _json_load_any(sp)
            if isinstance(sdoc, dict):
                ss = sdoc.get("samples")
                if isinstance(ss, list) and len(ss) > 0:
                    end_time, km = _extract_end_and_km_from_samples(ss)
                    if km is None:
                        dk = sdoc.get("distance_km")
                        if isinstance(dk, (int, float)):
                            km = float(dk)
                    print("[LIST/ALL][C4 RETURN]", end_time, km)
                    return end_time, km

    print("[LIST/ALL][C4 RETURN] None None")
    return None, None


def _extract_end_time_and_km(session_id: str) -> tuple[Optional[str], Optional[float]]:
    root = _repo_root_from_here()
    return _compute_end_time_and_km(root, session_id)


# -------------------------------
# PATCH E: Les fra session_<sid>.json (actual10/latest) og beregn km + end_time
# -------------------------------


def _pick_session_path(session_id: str, uid: Optional[str] = None) -> Optional[Path]:
    root = _repo_root_from_here()

    if uid:
        cand = root / "state" / "users" / uid / "sessions" / f"session_{session_id}.json"
        if cand.exists():
            return cand

    cand = root / "logs" / "actual10" / "latest" / f"session_{session_id}.json"
    if cand.exists():
        return cand

    try:
        for p in root.glob(f"logs/actual*/latest/session_{session_id}.json"):
            if p.exists():
                return p
    except Exception:
        pass

    cand = root / "_debug" / f"session_{session_id}.json"
    if cand.exists():
        return cand

    return None


def _extract_end_time_and_km_from_session(
    session_id: str, uid: Optional[str] = None
) -> Tuple[Optional[str], Optional[float]]:
    sp = _pick_session_path(session_id, uid=uid)
    if not sp:
        print("[LIST/ALL][E] no session file sid=", session_id)
        return None, None

    try:
        try:
            txt = sp.read_text(encoding="utf-8-sig")
        except Exception:
            txt = sp.read_text(encoding="utf-8", errors="replace")
        obj = json.loads(txt)
    except Exception as e:
        print(
            "[LIST/ALL][E] session json load failed sid=",
            session_id,
            "err=",
            repr(e),
            "file=",
            str(sp),
        )
        return None, None

    samples = obj.get("samples")
    if not isinstance(samples, list) or not samples:
        print(
            "[LIST/ALL][E] session has no samples sid=",
            session_id,
            "file=",
            str(sp),
            "keys=",
            list(obj.keys())[:30],
        )
        return None, None

    last = samples[-1] if isinstance(samples[-1], dict) else None
    end_time = last.get("t_abs") if last else None

    dist_m = 0.0
    prev_t = None
    prev_v = None

    for s in samples:
        if not isinstance(s, dict):
            continue
        t = s.get("t")
        v = s.get("v_ms")
        if not isinstance(t, (int, float)) or not isinstance(v, (int, float)):
            continue

        if prev_t is not None and prev_v is not None:
            dt = float(t) - float(prev_t)
            if dt > 0 and dt < 60:
                dist_m += 0.5 * (float(prev_v) + float(v)) * dt

        prev_t = t
        prev_v = v

    km = dist_m / 1000.0 if dist_m > 0 else None
    return end_time, km


def _needs_start_time_fix(st: object) -> bool:
    if not isinstance(st, str):
        return True
    s = st.strip()
    if not s:
        return True
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return True
    return False


# -----------------------------------
# Existing helpers
# -----------------------------------

_RE_RESULT_SID = re.compile(r"^result_(\d+)")


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
        for pth in path:
            if isinstance(cur, dict) and pth in cur:
                cur = cur[pth]
            else:
                ok = False
                break
        if ok and cur is not None:
            return str(cur)

    return None


def _sid_from_filename(p: Path) -> Optional[str]:
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


# -------------------------------
# PATCH D1 — Låst "truth": liste-watt = detalj-watt
# -------------------------------
def _pick_precision_watt_avg(doc: Dict[str, Any], metrics: Dict[str, Any]) -> Optional[float]:
    pw_avg = _to_float(doc.get("precision_watt_avg"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("precision_watt_avg"))

    if pw_avg is None:
        pw_avg = _to_float(metrics.get("precision_watt_pedal"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("precision_watt"))

    return pw_avg

def _row_from_doc(doc: Dict[str, Any], source_path: Path, fallback_sid: str) -> Dict[str, Any]:
    """
    Listing-only row builder:
    - Ingen enrichment/derivering (ingen start_time fallback, ingen trend lookup).
    - Ingen "distance_m -> km" eller "strava.distance -> km" fallback.
    - Leser kun det som allerede finnes i doc (og evt metrics hvis du ønsker).
    """
    metrics = _safe_get_metrics(doc)
    strava = doc.get("strava") or {}

    # ID
    sid = str(doc.get("session_id") or doc.get("ride_id") or doc.get("id") or fallback_sid)
    
    # ========== DEBUG START ==========
    import sys
    # Log ALL rides (remove if-check)
    ws = metrics.get('weather_source') if isinstance(metrics, dict) else None
    print(f"[WX_ALL] sid={sid} weather_source={ws}", file=sys.stderr)
    # ========== DEBUG END ==========

    # distance_km: les kun eksisterende felt (ingen derive)
    distance_km = _to_float(doc.get("distance_km"))
    # Hvis du vil tillate "resultdoc metrics.distance_km" som samme kilde-doc, behold denne:
    if distance_km is None and isinstance(metrics, dict):
        distance_km = _to_float(metrics.get("distance_km"))

    # power: bare plukk fra doc/metrics (ingen andre kilder)
    pw_avg = _pick_precision_watt_avg(doc, metrics)

    # ---------------------------------------------------------------------
    # Weather (deterministic read; NO enrichment, only prioritize existing fields)
    #
    # Root cause (S7):
    # - Newer result docs often store canonical weather on metrics.weather_source
    # - Older code only looked at metrics.weather_meta.provider/source -> null in list/all
    #
    # Priority order:
    # 1) metrics.weather_source (canonical string)
    # 2) metrics.weather_meta.provider|source
    # 3) metrics.weather_used.meta.source|provider
    # 4) doc.weather_source / doc.weather_meta.provider / doc.weather.source (legacy)
    # ---------------------------------------------------------------------
    weather_source = None

    # 1) Prefer canonical metrics.weather_source
    if isinstance(metrics, dict):
        ws = metrics.get("weather_source")
        if isinstance(ws, str) and ws.strip():
            weather_source = ws.strip()

    # 2) Fallback: metrics.weather_meta.provider|source
    if weather_source is None and isinstance(metrics, dict):
        wm = metrics.get("weather_meta")
        if isinstance(wm, dict):
            ws = wm.get("provider") or wm.get("source")
            if isinstance(ws, str) and ws.strip():
                weather_source = ws.strip()

    # 3) Fallback: metrics.weather_used.meta.source|provider
    if weather_source is None and isinstance(metrics, dict):
        wu = metrics.get("weather_used")
        if isinstance(wu, dict):
            meta = wu.get("meta")
            if isinstance(meta, dict):
                ws = meta.get("source") or meta.get("provider")
                if isinstance(ws, str) and ws.strip():
                    weather_source = ws.strip()

    # 4) Legacy fallbacks from doc (top-level)
    if weather_source is None:
        ws = doc.get("weather_source")
        if isinstance(ws, str) and ws.strip():
            weather_source = ws.strip()

    if weather_source is None:
        dm = doc.get("weather_meta")
        if isinstance(dm, dict):
            ws = dm.get("provider") or dm.get("source")
            if isinstance(ws, str) and ws.strip():
                weather_source = ws.strip()

    if weather_source is None:
        dw = doc.get("weather")
        if isinstance(dw, dict):
            ws = dw.get("source") or dw.get("provider")
            if isinstance(ws, str) and ws.strip():
                weather_source = ws.strip()

    row: Dict[str, Any] = {
        "session_id": sid,
        "ride_id": str(doc.get("ride_id")) if doc.get("ride_id") is not None else sid,
        "start_time": doc.get("start_time"),  # ingen fallback
        "end_time": doc.get("end_time"),
        "distance_km": distance_km,
        "precision_watt_avg": pw_avg,
        "profile_label": doc.get("profile_label")
        or (doc.get("profile_used") or {}).get("profile_label"),
        "weather_source": weather_source,
        "debug_source_path": str(source_path).replace("\\", "/"),
        "analyzed": True,
        "elevation_gain_m": (
            _to_float(metrics.get("elevation_gain_m") if isinstance(metrics, dict) else None)
            or _to_float(strava.get("total_elevation_gain"))
        ),
    }
    return row

def _read_user_sessions_index(root: Path, uid: str) -> Tuple[Path, set[str], dict | list | None, list[str]]:
    """
    ✅ Scope-minimum for /list/all:
    - vi bruker sessions_index.json som SSOT for hvilke ride_ids som tilhører user_id
    """
    index_path = state_root() / "users" / uid / "sessions_index.json"

    idx = None
    wanted: set[str] = set()
    idx_keys: list[str] = []

    if not index_path.exists():
        return index_path, wanted, None, idx_keys

    try:
        idx = _read_json_utf8_sig(index_path)

        if isinstance(idx, dict):
            idx_keys = list(idx.keys())

            cand = None
            for key in ("rides", "ride_ids", "session_ids", "sessions", "ids"):
                v = idx.get(key)
                if isinstance(v, list) and v:
                    cand = v
                    break

            if cand is None:
                v = idx.get("value")
                if isinstance(v, list) and v:
                    cand = v

            if isinstance(cand, list):
                wanted = set(str(x) for x in cand)

        elif isinstance(idx, list):
            wanted = set(str(x) for x in idx)
    except Exception:
        wanted = set()

    return index_path, wanted, idx, idx_keys


# ============================================================
# PATCH: sessions_meta.json + Strava activity fallback + cache
# ============================================================

def _user_dir(uid: str) -> Path:
    # Use state_root() for portability (Fly volume mounted at /app/state)
    return state_root() / "users" / uid


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_user_strava_tokens(uid: str) -> dict | None:
    # per your patch: /app/state/users/<uid>/strava_tokens.json
    p = _user_dir(uid) / "strava_tokens.json"
    doc = _load_json(p)
    return doc if isinstance(doc, dict) else None


def _strava_get_activity(uid: str, sid: str) -> dict | None:
    tokens = _load_user_strava_tokens(uid)
    if not tokens:
        return None
    access = tokens.get("access_token")
    if not access:
        return None

    url = f"https://www.strava.com/api/v3/activities/{sid}"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {access}"}, timeout=15)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except Exception:
        return None


def _extract_precision_watt_avg(doc: dict) -> float | None:
    """
    Accept both shapes:
      - top-level precision_watt_avg
      - metrics.precision_watt_avg
      - metrics.precision_watt_pedal / metrics.precision_watt (legacy)
    """
    if not isinstance(doc, dict):
        return None

    v = doc.get("precision_watt_avg")
    if isinstance(v, (int, float)):
        return float(v)

    m = doc.get("metrics") or {}
    if not isinstance(m, dict):
        m = {}

    v2 = m.get("precision_watt_avg")
    if isinstance(v2, (int, float)):
        return float(v2)

    v3 = m.get("precision_watt_pedal")
    if isinstance(v3, (int, float)):
        return float(v3)

    v4 = m.get("precision_watt")
    if isinstance(v4, (int, float)):
        return float(v4)

    return None


def _safe_load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as e:
        logger.info(f"[LIST] result_read_failed path={path} err={e!r}")
        return None


# ============================================================
# PATCH B2.1 - New helpers for precision_watt_avg hydration
# ============================================================

def _extract_precision_watt_from_result(doc: Dict[str, Any]) -> Optional[float]:
    """
    SSOT:
      - result top-level precision_watt_avg
      - fallback: metrics.precision_watt_avg
      - fallback: metrics.precision_watt_pedal
    """
    v = _to_float(doc.get("precision_watt_avg"))
    if v is not None:
        return v

    metrics = doc.get("metrics") or {}
    if isinstance(metrics, dict):
        v = _to_float(metrics.get("precision_watt_avg"))
        if v is not None:
            return v
        v = _to_float(metrics.get("precision_watt_pedal"))
        if v is not None:
            return v

    return None


def _ensure_meta_precision_watt(
    *,
    uid_root: Path,
    sid: str,
    meta: Dict[str, Any],
) -> Tuple[Optional[float], bool]:
    """
    Returnerer (precision_watt_avg, meta_updated?)
    meta forventes å være dict keyed by sid -> dict(fields)
    """
    cur = meta.get(sid)
    if not isinstance(cur, dict):
        cur = {}

    existing = _to_float(cur.get("precision_watt_avg"))
    if existing is not None:
        return existing, False

    # hydrate fra SSOT result_<sid>.json
    # SSOT: /app/state/users/<uid>/results/result_<sid>.json
    # (ikke /sessions/result_*.json)
    res_p = uid_root / "results" / f"result_{sid}.json"
    res_doc = _read_json_if_exists(res_p)
    if not isinstance(res_doc, dict):
        return None, False

    pw = _extract_precision_watt_from_result(res_doc)
    if pw is None:
        return None, False

    cur["precision_watt_avg"] = pw
    meta[sid] = cur
    return pw, True


def _distance_km_from_session_samples(uid: str, sid: str) -> Optional[float]:
    """
    Les session_<sid>.json for brukeren og beregn distanse fra samples.
    """
    session_path = state_root() / "users" / uid / "sessions" / f"session_{sid}.json"
    if not session_path.exists():
        return None

    try:
        doc = json.loads(session_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    samples = doc.get("samples") or []
    return _distance_km_from_samples(samples)


# ============================================================
# PATCH 1 — Gjør list/all til samme SSOT-loader som SessionView
# ============================================================

def _build_rows_from_state(uid: str, debug: bool = False) -> Tuple[list[dict], Dict[str, Any]]:
    """
    SSOT list/all:
      - ownership: sessions_index.json
      - data: result_<sid>.json (SSOT) else logs/results fallback
      - NO hydration / NO meta writes
    """
    import logging

    logger = logging.getLogger(__name__)

    udir = _user_dir(uid)
    index_path, wanted, idx_doc, idx_keys = _read_user_sessions_index(udir, uid)

    # -------------------------------
    # PATCH S6-A: Load and update sessions_meta.json
    # -------------------------------
    meta_path = udir / "sessions_meta.json"
    meta = _load_sessions_meta(meta_path)
    meta_changed = False

    # Lazy meta rebuild: deterministisk HR + elapsed for eksisterende sessions
    for sid in sorted(list(wanted), reverse=True):
        sid = str(sid).strip()
        cur = meta.get(sid) or {}

        # Vi trenger bare å derivere hvis mangler (best-effort)
        need_hr = (cur.get("hr_avg") is None) and (cur.get("hr_max") is None)
        need_time = (cur.get("elapsed_s") is None) and (cur.get("end_time") is None)
        need_dist = (cur.get("distance_km") is None)

        if not (need_hr or need_time or need_dist):
            continue

        sp = udir / "sessions" / f"session_{sid}.json"
        if not sp.exists():
            continue

        try:
            doc = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue

        samples = doc.get("samples") or []
        d = _derive_meta_from_samples(samples)

        before = dict(cur)
        # Merge bare inn når cur mangler (ikke overskriv)
        for k, v in d.items():
            if cur.get(k) is None and v is not None:
                cur[k] = v

        if cur != before:
            meta[sid] = cur
            meta_changed = True

    if meta_changed:
        _atomic_write_json(meta_path, meta)

    rows: list[dict] = []
    dbg = {"checked": 0, "ssot_hits": 0, "logs_hits": 0, "debug_hits": 0}

    # stable order
    sessions = sorted(list(wanted), reverse=True)

    for sid in sessions:
        dbg["checked"] += 1

        sid = str(sid).strip()
        doc: Optional[Dict[str, Any]] = None
        source_path = None

        ssot_p = _ssot_user_result_path(uid, sid)
        if ssot_p.exists():
            doc = _read_json_if_exists(ssot_p)

            # DEBUG: verify doc shape + watt fields from SSOT
            if isinstance(doc, dict):
                try:
                    pw = doc.get("precision_watt_avg")
                    metrics_obj = doc.get("metrics") if isinstance(doc.get("metrics"), dict) else {}
                    mpw = (metrics_obj or {}).get("precision_watt_pedal")
                    logger.info(
                        "[LIST_DEBUG] sid=%s doc_keys=%s pw=%s mpw=%s",
                        sid,
                        list(doc.keys())[:5],
                        pw,
                        mpw,
                    )
                except Exception as e:
                    logger.warning("[LIST_DEBUG] sid=%s debug_extract_failed err=%s", sid, repr(e))
            else:
                logger.warning("[LIST_DEBUG] sid=%s doc is not dict: %s", sid, type(doc))

            if isinstance(doc, dict):
                source_path = "state/users/*/results"
                dbg["ssot_hits"] += 1

        if doc is None:
            logs_p = _logs_result_path(sid)
            if logs_p.exists():
                doc = _read_json_if_exists(logs_p)
                if isinstance(doc, dict):
                    source_path = "logs/results"
                    dbg["logs_hits"] += 1

        if doc is None and debug:
            dp = _debug_result_path(sid)
            if dp is not None and dp.exists():
                doc = _read_json_if_exists(dp)
                if isinstance(doc, dict):
                    source_path = "_debug"
                    dbg["debug_hits"] += 1

        if not isinstance(doc, dict):
            # No doc found => still return row, but power is None
            doc = {}
            source_path = "none"

        metrics = doc.get("metrics") if isinstance(doc.get("metrics"), dict) else {}
        start_time = doc.get("start_time")
        end_time = doc.get("end_time")
        distance_km = doc.get("distance_km")
        profile_label = doc.get("profile_label") or (doc.get("profile_used") or {}).get("profile_label")
        weather_meta = metrics.get("weather_meta") if isinstance(metrics, dict) else None
        weather_source = None
        if isinstance(weather_meta, dict):
            weather_source = weather_meta.get("provider") or weather_meta.get("source")

        # Use same extraction semantics as sessions.py helper
        precision_watt_avg = _extract_precision_watt_avg(doc)

        status = _compute_status(uid, sid)
        analyzed = bool(_ssot_user_result_path(uid, sid).exists() or _logs_result_path(sid).exists())

        row = {
            "session_id": sid,
            "ride_id": sid,
            "start_time": start_time,
            "end_time": end_time,
            "distance_km": distance_km,
            "precision_watt_avg": precision_watt_avg,
            "profile_label": profile_label,
            "weather_source": weather_source,
            "debug_source_path": source_path,
            "analyzed": analyzed,
            "status": status,
            "elevation_gain_m": None,
        }

        # -------------------------------
        # PATCH S6-B: Merge meta inn i hver row
        # -------------------------------
        m = meta.get(str(sid)) or {}
        for k in ["hr_avg", "hr_max", "elapsed_s", "end_time", "distance_km", "start_time", "elevation_gain_m"]:
            if row.get(k) is None and m.get(k) is not None:
                row[k] = m.get(k)

        rows.append(row)

    return rows, dbg


# -----------------------------------
# Routes
# -----------------------------------


@router.get("")        # ✅ ALIAS: /api/sessions
@router.get("/list")   # ✅ Original: /api/sessions/list
async def list_sessions(
    req: Request,
    response: Response,
    user_id: str = Depends(require_auth),
    debug: int = Query(0, ge=0, le=1),
) -> List[Dict[str, Any]]:
    """
    Returnerer en liste over økter for innlogget bruker (scopet til sessions_index.json),
    og beriker radene med data fra result_*.json der de finnes:
      1) SSOT: state/users/<uid>/results/result_<sid>.json
      2) Fallback: logs/results/result_<sid>.json
    """
    uid = str(user_id)

    index_path = state_root() / "users" / uid / "sessions_index.json"
    index_doc: Any = _read_json_utf8_sig(index_path) if index_path.exists() else {"sessions": []}
    ride_ids = _allowed_ids_list_from_index_doc(index_doc)

    out: List[Dict[str, Any]] = []

    for sid_raw in ride_ids:
        sid = str(sid_raw).strip()
        if not sid:
            continue

        ssot_p = _ssot_user_result_path(uid, sid)
        doc = _read_json_if_exists(ssot_p)

        logs_p = _logs_result_path(sid)
        if doc is None:
            doc = _read_json_if_exists(logs_p)

        item = _extract_list_item(sid, doc)

        if debug:
            item["debug"] = {
                "has_ssot_result": ssot_p.exists(),
                "has_logs_result": logs_p.exists(),
                "logs_results_dir": str(_logs_results_dir()).replace("\\", "/"),
            }

        # S6-E: deterministisk distance fra session samples (SSOT)
        if item.get("distance_km") is None:
            dk = _distance_km_from_session_samples(uid, sid)
            if dk is not None:
                item["distance_km"] = dk

        out.append(item)

    return out



@router.get("/list/all")
async def list_all(
    req: Request,
    response: Response,
    user_id: str = Depends(require_auth),
    debug: int = Query(0),
) -> Dict[str, Any]:
    """
    🔒 Auth + scope-minimum:
    - Ingen cg_uid-cookie identitet
    - Returnerer kun sessions som ligger i state/users/<user_id>/sessions_index.json
    - PATCH: Bruk sessions_meta.json som cache for start_time + distance_km,
      og fallback til Strava activity én gang per session hvis mangler.
    - PATCH: precision_watt_avg berikes fra /logs/results/result_<sid>.json ✅
    - PATCH S6: Deriver HR + elapsed fra session samples og cache i meta
    """
    uid = str(user_id)
    
    # PATCH 1 - Build rows with SSOT loader (includes S6 meta derivation)
    rows, dbg = _build_rows_from_state(uid, debug=bool(debug))

    resp: Dict[str, Any] = {"value": rows, "Count": len(rows)}
    
    # --- DEBUG FINGERPRINT (TEMP) ---
    resp["_fingerprint"] = "sessions_list_all::B2.5+S6"
    # -------------------------------

    if debug:
        # PATCH 1 - Debug result sources
        with_pw = 0
        with_hr = 0
        with_elapsed = 0
        for r in rows:
            try:
                v = r.get("precision_watt_avg", None)
                if isinstance(v, (int, float)):
                    with_pw += 1
                if r.get("hr_avg") is not None:
                    with_hr += 1
                if r.get("elapsed_s") is not None:
                    with_elapsed += 1
            except Exception:
                pass

        # Original debug info preserved
        udir = _user_dir(uid)
        null_power_count = sum(1 for r in rows if r.get("precision_watt_avg") is None)
        
        resp["debug"] = {
            "uid": uid,
            "index_path": str((udir / "sessions_index.json")).replace("\\", "/"),
            "index_exists": (udir / "sessions_index.json").exists(),
            "rows_returned": len(rows),
            "null_power_count": null_power_count,
            "logs_results_dir": str(_logs_results_dir()).replace("\\", "/"),
            "repo_root": str(_repo_root_from_here()).replace("\\", "/"),
        }
        
        # PATCH 1 - New debug result sources
        resp["_debug"] = {
            "rows_total": len(rows),
            "rows_with_precision_watt_avg": with_pw,
            "rows_without_precision_watt_avg": len(rows) - with_pw,
            "rows_with_hr_avg": with_hr,
            "rows_with_elapsed_s": with_elapsed,
            "result_sources": dbg,
            "allow_debug_inputs": _allow_debug_inputs(),
            "meta_path": str((udir / "sessions_meta.json")).replace("\\", "/"),
            "meta_exists": (udir / "sessions_meta.json").exists(),
        }

    return resp


@router.get("/list/_debug_paths")
async def _debug_paths(
    user_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """
    🔒 Auth + scope-minimum:
    - Ikke lek ut absolutt filstruktur (ingen cwd/root/router_file)
    - Returnér kun relative paths for current user (state/users/<uid>/...)
    """
    uid = str(user_id)

    return {
        "uid": uid,
        "paths": {
            "sessions_index": f"state/users/{uid}/sessions_index.json",
            "auth": f"state/users/{uid}/auth.json",
            "user_sessions_dir": f"state/users/{uid}/sessions/",
            "results_dir": "logs/results/",
            "debug_dir": "_debug/",
        },
        "note": "Relative paths only. No absolute filesystem paths are exposed.",
    }