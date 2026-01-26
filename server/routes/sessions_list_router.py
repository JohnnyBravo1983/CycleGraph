# frontend/server/routes/sessions_list_router.py
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query, Request, Response
from server.auth_guard import require_auth
from server.user_state import state_root


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# -------------------------------
# PATCH B2/B3: start_time fra resultfil + fingerprint/debug
# -------------------------------
_TABS_RE = re.compile(r'"t_abs"\s*:\s*"([^"]+)"')

# PATCH: end_time seek-from-end (siste t_abs)  (legacy / kan ryddes senere)
_LAST_TABS_RE = re.compile(r'"t_abs"\s*:\s*"([^"]+)"')


# -------------------------------
# NEW HELPERS (activity distance fallback)
# -------------------------------
def _repo_root_from_here() -> Path:
    # .../frontend/server/routes/sessions_list_router.py -> repo root = CycleGraph
    return Path(__file__).resolve().parents[2]


def _safe_sid(sid: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "", str(sid or ""))


def _ssot_user_result_path(uid: str, sid: str) -> Path:
    sid2 = _safe_sid(sid)
    return state_root() / "users" / uid / "results" / f"result_{sid2}.json"


def _logs_result_path(sid: str) -> Path:
    sid2 = _safe_sid(sid)
    return _repo_root_from_here() / "logs" / "results" / f"result_{sid2}.json"


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
        # vanligste: {"sessions":[...]} eller {"ride_ids":[...]} osv
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
                # ikke overdriv presisjon i UI
                return round(km, 3)
        except Exception:
            pass

    return None


def _pick_result_path(sid: str, uid: Optional[str] = None) -> Path | None:
    """
    Return best matching result json for a session id.
    Supports both legacy + self-healed naming/layouts.
    """
    # In Fly container, repo root is /app
    root = Path("/app")

    cand_dirs: list[Path] = [
        # ✅ PROD SSOT (confirmed by find)
        root / "logs" / "results",
    ]

    # Optional user-scoped candidates (keep, but after prod SSOT)
    if uid:
        cand_dirs += [
            root / "state" / "users" / str(uid) / "results",
            root / "state" / "users" / str(uid) / "logs" / "results",
            root / "state" / "users" / str(uid) / "_debug",
        ]

    # Legacy / other fallbacks
    cand_dirs += [
        root / "state" / "results",
        root / "_debug",
        root / "logs" / "_debug",
    ]

    patterns = [
        f"result_{sid}.json",
        f"{sid}.json",
        f"result_{sid}_*.json",
        f"*{sid}*.json",  # last resort
    ]

    for d in cand_dirs:
        try:
            if not d.exists():
                continue

            # exact first
            exact = d / f"result_{sid}.json"
            if exact.exists() and exact.is_file():
                return exact

            # then globs by recency
            for pat in patterns[1:]:
                hits = sorted(d.glob(pat), key=lambda x: x.stat().st_mtime, reverse=True)
                if hits:
                    return hits[0]
        except Exception:
            continue

    return None


def _extract_first_t_abs_fast(path: Path) -> Optional[str]:
    """
    Les kun starten av resultfilen og plukk første forekomst av "t_abs": "...."
    Unngår å parse hele JSON / samples-arrayet.
    """
    try:
        with path.open("rb") as f:
            chunk = f.read(512_000)  # PATCH D2.1: increase to avoid missing t_abs in large files
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
                if dt > 0 and dt < 60:  # basic sanity
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
# PATCH C4-REPLACE: “siste mile”
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

    # fallback: session_<sid>.json (actual10/latest + evt andre actual*/latest)
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
# PATCH D1 — Låst “truth”: liste-watt = detalj-watt
# -------------------------------
def _pick_precision_watt_avg(doc: Dict[str, Any], metrics: Dict[str, Any]) -> Optional[float]:
    # List view must match session detail view (truth = precision_watt_avg)
    pw_avg = _to_float(doc.get("precision_watt_avg"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("precision_watt_avg"))

    # Defensive fallbacks that still represent "precision" (NOT wheel/total)
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("precision_watt_pedal"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("precision_watt"))

    return pw_avg


def _row_from_doc(doc: Dict[str, Any], source_path: Path, fallback_sid: str) -> Dict[str, Any]:
    metrics = _safe_get_metrics(doc)
    strava = doc.get("strava") or {}

    # -------------------------
    # distance_km (legacy + self-healed)
    # -------------------------
    distance_km = _to_float(doc.get("distance_km"))

    # ✅ self-healed: metrics.distance_km
    if distance_km is None and isinstance(metrics, dict):
        distance_km = _to_float(metrics.get("distance_km"))

    # legacy: distance_m in doc
    if distance_km is None:
        dm = _to_float(doc.get("distance_m"))
        if dm is not None:
            distance_km = dm / 1000.0

    # ✅ self-healed: strava.distance in meters
    if distance_km is None:
        sd = _to_float(strava.get("distance"))
        if sd is not None:
            distance_km = sd / 1000.0

    # precision watt avg (already multi-source in helper)
    pw_avg = _pick_precision_watt_avg(doc, metrics)

    sid = str(doc.get("session_id") or doc.get("ride_id") or doc.get("id") or fallback_sid)

    # PATCH 0A — Fix weather_source (SSOT from analyzer)
    # prefer metrics.weather_meta.provider, fallback to older layouts
    weather_meta = metrics.get("weather_meta") if isinstance(metrics, dict) else None
    if not isinstance(weather_meta, dict):
        weather_meta = {}

    weather_source = (
        weather_meta.get("provider")
        or (doc.get("weather_meta") or {}).get("provider")   # ✅ extra safe fallback
        or doc.get("weather_source")
        or (doc.get("weather") or {}).get("source")
    )

    row: Dict[str, Any] = {
        "session_id": sid,
        "ride_id": str(doc.get("ride_id")) if doc.get("ride_id") is not None else sid,
        "start_time": doc.get("start_time"),
        "end_time": doc.get("end_time"),
        "distance_km": distance_km,
        "precision_watt_avg": pw_avg,
        "profile_label": doc.get("profile_label") or (doc.get("profile_used") or {}).get("profile_label"),
        "weather_source": weather_source,
        "debug_source_path": str(source_path).replace("\\", "/"),
        # ✅ analyzed marker for UI
        "analyzed": True,
    }

    # PATCH D2.2: Prefer Strava start_date if present (import writes this; analysis may carry it through)
    try:
        if row.get("start_time") in (None, ""):
            st2 = (strava.get("start_date") or doc.get("start_date"))  # ✅ include doc.start_date fallback
            if isinstance(st2, str) and st2.strip():
                row["start_time"] = st2.strip()
    except Exception:
        pass

    try:
        if row.get("start_time") in (None, ""):
            sid2 = row.get("session_id") or row.get("ride_id")
            if sid2:
                st = _trend_sessions_lookup_start_time(str(sid2))
                # PATCH D2.3: Only accept if it looks like a real timestamp (not DATE-only / broken)
                if st and (not _needs_start_time_fix(st)):
                    row["start_time"] = st
    except Exception:
        pass

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
    root = _repo_root_from_here()

    # Bruk sessions_index.json som SSOT for hvilke rides som tilhører bruker
    index_path = state_root() / "users" / uid / "sessions_index.json"
    index_doc: Any = _read_json_utf8_sig(index_path) if index_path.exists() else {"sessions": []}
    ride_ids = _allowed_ids_list_from_index_doc(index_doc)

    out: List[Dict[str, Any]] = []

    for sid_raw in ride_ids:
        sid = str(sid_raw).strip()
        if not sid:
            continue

        # 1) SSOT først
        ssot_p = _ssot_user_result_path(uid, sid)
        doc = _read_json_if_exists(ssot_p)

        # 2) Fallback: logs/results
        logs_p = _logs_result_path(sid)
        if doc is None:
            doc = _read_json_if_exists(logs_p)

        item = _extract_list_item(sid, doc)

        # optional: minimal debug uten paths
        if debug:
            item["debug"] = {
                "has_ssot_result": ssot_p.exists(),
                "has_logs_result": logs_p.exists(),
            }

        # activity distance fallback (hvis vi fortsatt mangler distance)
        try:
            if item.get("distance_km") is None:
                dk = _distance_km_from_activity(sid)
                if dk is not None:
                    item["distance_km"] = dk
        except Exception:
            pass

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
    """
    uid = user_id
    FP = "LIST_ALL_AUTH_SCOPED_20260114"
    root = _repo_root_from_here()
    print("[/list/all]", FP, "uid=", uid, "root=", root)

    index_path, wanted, idx, idx_keys = _read_user_sessions_index(root, uid)

    if not wanted:
        # ingen index => ingen sessions for denne brukeren
        out: Dict[str, Any] = {"value": [], "Count": 0}
        if debug:
            out["debug"] = {
                "uid": uid,
                "index_path": str(index_path).replace("\\", "/"),
                "index_exists": index_path.exists(),
                "wanted_count": 0,
            }
        return out

    rows: List[Dict[str, Any]] = []

    # ✅ Scope: iterer kun over ride_ids i index (ikke scan globalt)
    for sid_item in sorted(wanted, reverse=True):
        try:
            sid_str = str(sid_item)
            if (not sid_str.isdigit()) or (len(sid_str) > 20):
                print("[LIST/ALL] skip invalid sid:", sid_str)
                continue

            # PATCH 0B: pass uid to find per-user results first
            rp = _pick_result_path(sid_str, uid=uid)

            if not rp:
                # ✅ NEW: include placeholder rows so UI can list all rides
                item = {
                    "session_id": sid_str,
                    "ride_id": sid_str,
                    "start_time": None,
                    "end_time": None,
                    "distance_km": None,
                    "precision_watt_avg": None,
                    "profile_label": None,
                    "weather_source": None,
                    "debug_source_path": None,
                    "analyzed": False,
                }

                # ✅ NEW: activity distance fallback
                try:
                    if item.get("distance_km") is None:
                        dk = _distance_km_from_activity(str(item.get("id") or item.get("ride_id") or ""))
                        if dk is not None:
                            item["distance_km"] = dk
                except Exception:
                    pass

                rows.append(item)
                continue

            raw = _read_json_utf8_sig(rp)
            doc = _normalize_doc(raw)
            row = _row_from_doc(doc, rp, fallback_sid=sid_str)

            # ✅ NEW: activity distance fallback (after item exists and has id/ride_id)
            try:
                if row.get("distance_km") is None:
                    dk = _distance_km_from_activity(str(row.get("id") or row.get("ride_id") or ""))
                    if dk is not None:
                        row["distance_km"] = dk
            except Exception:
                pass

            # --- start_time fix (UTC ISO), kun når missing/DATE-only ---
            try:
                st = row.get("start_time")
                if _needs_start_time_fix(st):
                    # 1) SSOT: session_<sid>.json (actual10/latest)
                    t_abs = None
                    sp = _pick_session_path(sid_str, uid=uid)
                    if sp:
                        obj = _json_load_any(sp)
                        if isinstance(obj, dict):
                            ss = obj.get("samples")
                            if isinstance(ss, list) and ss:
                                first = ss[0] if isinstance(ss[0], dict) else None
                                if first:
                                    t_abs = first.get("t_abs")

                    # 2) fallback: legacy attempt (result json)
                    if not t_abs:
                        t_abs = _extract_first_t_abs_fast(rp)

                    if t_abs:
                        row["start_time"] = t_abs
                        print("[/list/all]", "START_TIME_BACKFILL", "sid=", sid_str, "t_abs=", t_abs)
            except Exception as e:
                print("[/list/all]", "START_TIME_BACKFILL_ERR", "sid=", sid_str, "err=", repr(e))

            # --- PATCH C4: end_time + distance_km (result JSON fallback) ---
            try:
                need_end = row.get("end_time") is None
                need_km = row.get("distance_km") is None
                if need_end or need_km:
                    end_abs, km = _compute_end_time_and_km(root, sid_str)
                    if need_end and end_abs:
                        row["end_time"] = end_abs
                    if need_km and km is not None:
                        row["distance_km"] = km
            except Exception as e:
                print("[/list/all]", "END_KM_BACKFILL_ERR", "sid=", sid_str, "err=", repr(e))

            # --- PATCH E: SSOT fra session_<sid>.json (actual10/latest eller per-user sessions) ---
            try:
                if row.get("end_time") is None or row.get("distance_km") is None:
                    end_t, km2 = _extract_end_time_and_km_from_session(sid_str, uid=uid)
                    if row.get("end_time") is None:
                        row["end_time"] = end_t
                    if row.get("distance_km") is None:
                        row["distance_km"] = km2
            except Exception as e:
                print("[/list/all]", "E_SESSION_BACKFILL_ERR", "sid=", sid_str, "err=", repr(e))

            rows.append(row)
        except Exception:
            continue

    # ✅ Keep placeholders (analyzed=False) even though they have no watt yet
    rows = [
        r
        for r in rows
        if (r.get("analyzed") is False)
        or ((_to_float(r.get("precision_watt_avg")) or 0.0) > 0.0)
    ]
    rows.sort(key=lambda r: str(r.get("start_time") or ""), reverse=True)
    rows = rows[:200]

    out: Dict[str, Any] = {"value": rows, "Count": len(rows)}

    if debug:
        out["debug"] = {
            "uid": uid,
            "index_path": str(index_path).replace("\\", "/"),
            "index_exists": index_path.exists(),
            "idx_type": type(idx).__name__ if idx is not None else None,
            "idx_keys": idx_keys,
            "wanted_count": len(wanted),
            "wanted_sample": sorted(list(wanted))[:20],
            "rows_returned": len(rows),
        }

    return out


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

    # Kun relative hints (ingen samples, ingen faktiske disk-paths)
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
