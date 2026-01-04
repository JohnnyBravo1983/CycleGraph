# frontend/server/routes/sessions_list_router.py
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Cookie, Query, Request, Response
from server.routes.auth_strava import _get_or_set_uid

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# -------------------------------
# PATCH B2/B3: start_time fra resultfil + fingerprint/debug
# -------------------------------
_TABS_RE = re.compile(r'"t_abs"\s*:\s*"([^"]+)"')

# PATCH: end_time seek-from-end (siste t_abs)  (legacy / kan ryddes senere)
_LAST_TABS_RE = re.compile(r'"t_abs"\s*:\s*"([^"]+)"')


def _pick_result_path(session_id: str) -> Optional[Path]:
    # Bruk eksisterende repo-root helper i denne fila
    root = _repo_root_from_here()
    cand = [
        root / "_debug" / f"result_{session_id}.json",
        root / "logs" / "results" / f"result_{session_id}.json",
    ]
    for p in cand:
        if p.exists() and p.is_file():
            return p
    return None


def _extract_first_t_abs_fast(path: Path) -> Optional[str]:
    """
    Les kun starten av resultfilen og plukk første forekomst av "t_abs": "...."
    Unngår å parse hele JSON / samples-arrayet.
    """
    try:
        with path.open("rb") as f:
            chunk = f.read(64_000)  # PATCH: lettvekts-lesing
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
    Dette funker selv om det er store blokker etter samples.
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

                # Prepend ny chunk foran eksisterende tekst
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
    # behold ISO med timezone
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_end_time_and_km(session_id: str) -> tuple[Optional[str], Optional[float]]:
    """
    ✅ PATCH C4 (BOM-safe + robust fallback)
    - Les JSON BOM-safe
    - distance_km fra metrics/top-level
    - end_time: samples[-1].t_abs hvis samples finnes
    - fallback: start_time + duration fra metrics hvis samples mangler
    """
    p = _pick_result_path(session_id)
    if not p:
        print("[LIST/ALL][C4] no result file for sid=", session_id)
        return None, None

    print("[LIST/ALL][C4] using file:", str(p))

    try:
        try:
            txt = p.read_text(encoding="utf-8-sig")  # ✅ BOM safe
        except Exception:
            txt = p.read_text(encoding="utf-8", errors="replace")
        obj = json.loads(txt)
    except Exception as e:
        print("[LIST/ALL][C4] json load failed sid=", session_id, "err=", repr(e))
        return None, None

    km: Optional[float] = None
    metrics = obj.get("metrics")
    if isinstance(obj.get("distance_km"), (int, float)):
        km = float(obj["distance_km"])
    elif isinstance(metrics, dict):
        for k in ("distance_km", "dist_km", "distance", "distance_m", "dist_m", "total_distance_m"):
            v = metrics.get(k)
            if isinstance(v, (int, float)) and v > 0:
                km = float(v) / 1000.0 if k.endswith("_m") else float(v)
                break

        if km is None:
            dist_keys = [k for k in metrics.keys() if "dist" in k.lower()]
            if dist_keys:
                print("[LIST/ALL][C4] metrics dist_keys:", dist_keys)

    samples = obj.get("samples")
    if isinstance(samples, list) and samples:
        last = samples[-1]
        end_abs = last.get("t_abs") if isinstance(last, dict) else None
        print("[LIST/ALL][C4 RETURN]", end_abs, km)
        return end_abs, km

    st = obj.get("start_time")
    dt0 = _parse_dt(st) if isinstance(st, str) else None

    dur_s: Optional[float] = None
    if isinstance(metrics, dict):
        for k in ("duration_s", "duration_sec", "elapsed_s", "elapsed_sec", "time_s", "moving_time_s"):
            v = metrics.get(k)
            if isinstance(v, (int, float)) and v > 0:
                dur_s = float(v)
                break

    if dt0 and dur_s:
        dt1 = dt0 + timedelta(seconds=dur_s)
        end_abs = _fmt_dt(dt1)
        print("[LIST/ALL][C4 RETURN]", end_abs, km)
        return end_abs, km

    print("[LIST/ALL][C4] no samples + no duration fallback sid=", session_id, "keys=", list(obj.keys())[:30])
    print("[LIST/ALL][C4 RETURN]", None, km)
    return None, km


# -------------------------------
# PATCH E: Les fra session_<sid>.json (actual10/latest) og beregn km + end_time
# -------------------------------

def _pick_session_path(session_id: str, uid: Optional[str] = None) -> Optional[Path]:
    root = _repo_root_from_here()

    # 1) per-user sessions mappe (framtidsrettet)
    if uid:
        cand = root / "state" / "users" / uid / "sessions" / f"session_{session_id}.json"
        if cand.exists():
            return cand

    # 2) bevis fra logg: logs/actual10/latest/session_<sid>.json
    cand = root / "logs" / "actual10" / "latest" / f"session_{session_id}.json"
    if cand.exists():
        return cand

    # 3) bredere: logs/actual*/latest/session_<sid>.json
    try:
        for p in root.glob(f"logs/actual*/latest/session_{session_id}.json"):
            if p.exists():
                return p
    except Exception:
        pass

    # 4) _debug fallback
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
        print("[LIST/ALL][E] session json load failed sid=", session_id, "err=", repr(e), "file=", str(sp))
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

    # end_time = siste t_abs
    last = samples[-1] if isinstance(samples[-1], dict) else None
    end_time = last.get("t_abs") if last else None

    # distance_km: integrer v_ms over tid (t-differanser)
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
            if dt > 0 and dt < 60:  # sanity guard
                dist_m += 0.5 * (float(prev_v) + float(v)) * dt

        prev_t = t
        prev_v = v

    km = dist_m / 1000.0 if dist_m > 0 else None
    return end_time, km


def _needs_start_time_fix(st: object) -> bool:
    """
    PATCH C3.1: Fix hvis:
    - None/null
    - ikke string
    - tom string
    - bare YYYY-MM-DD (len=10)
    """
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


def _repo_root_from_here() -> Path:
    # .../CycleGraph/frontend/server/routes/sessions_list_router.py → repo root = CycleGraph
    # parents[0]=routes, parents[1]=server, parents[2]=frontend, parents[3]=CycleGraph (i mange oppsett)
    # MEN: i ditt tilfelle peker parents[3] feil (Karriere). Vi bruker parents[2] som SSOT iht PATCH C2.
    return Path(__file__).resolve().parents[2]


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
    """
    Fallback: bruk filnavnet result_<digits>*.json som session_id.
    Eksempel: result_16127771071_direct.json -> 16127771071
    """
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


def _pick_precision_watt_avg(doc: Dict[str, Any], metrics: Dict[str, Any]) -> Optional[float]:
    pw_avg = _to_float(doc.get("precision_watt_avg"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("precision_watt_avg"))

    if pw_avg is None:
        pw_avg = _to_float(metrics.get("model_watt_wheel"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("total_watt"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("precision_watt"))

    return pw_avg


def _row_from_doc(doc: Dict[str, Any], source_path: Path, fallback_sid: str) -> Dict[str, Any]:
    metrics = _safe_get_metrics(doc)

    distance_km = _to_float(doc.get("distance_km"))
    if distance_km is None:
        dm = _to_float(doc.get("distance_m"))
        if dm is not None:
            distance_km = dm / 1000.0

    pw_avg = _pick_precision_watt_avg(doc, metrics)

    sid = str(doc.get("session_id") or doc.get("ride_id") or doc.get("id") or fallback_sid)

    row: Dict[str, Any] = {
        "session_id": sid,
        "ride_id": str(doc.get("ride_id")) if doc.get("ride_id") is not None else sid,
        "start_time": doc.get("start_time"),
        "end_time": doc.get("end_time"),
        "distance_km": distance_km,
        "precision_watt_avg": pw_avg,
        "profile_label": doc.get("profile_label") or (doc.get("profile_used") or {}).get("profile_label"),
        "weather_source": doc.get("weather_source") or (doc.get("weather") or {}).get("source"),
        "debug_source_path": str(source_path).replace("\\", "/"),
    }

    try:
        if row.get("start_time") in (None, ""):
            sid2 = row.get("session_id") or row.get("ride_id")
            if sid2:
                st = _trend_sessions_lookup_start_time(str(sid2))
                if st:
                    row["start_time"] = st
    except Exception:
        pass

    return row


def _gather_result_files(root: Path) -> List[Path]:
    files: List[Path] = []

    dbg = root / "_debug"
    if dbg.exists():
        files.extend(sorted([p for p in dbg.glob("result_*.json") if "_direct" not in p.name]))

    lr = root / "logs" / "results"
    if lr.exists():
        files.extend(sorted(lr.glob("result_*.json")))

    out = root / "out"
    if out.exists():
        files.extend(sorted(out.glob("result_*.json")))

    return files


def _prefer_path(a: Path, b: Path) -> Path:
    def tier(pth: Path) -> int:
        s = str(pth).replace("\\", "/")
        if "/logs/results/" in s:
            return 0
        if "/_debug/" in s:
            return 1
        if "/out/" in s:
            return 2
        return 9

    try:
        ma = a.stat().st_mtime
        mb = b.stat().st_mtime
        if ma != mb:
            return a if ma > mb else b
    except Exception:
        pass

    ta, tb = tier(a), tier(b)
    if ta != tb:
        return a if ta < tb else b

    try:
        sa = a.stat().st_size
        sb = b.stat().st_size
        if sa != sb:
            return a if sa > sb else b
    except Exception:
        pass

    return a


# -----------------------------------
# Routes
# -----------------------------------


@router.get("/list/all")
async def list_all(
    req: Request,
    response: Response,
    cg_uid: str | None = Cookie(default=None),
    debug: int = Query(0),
) -> Dict[str, Any]:
    FP_DIAG = "LIST_ALL_DIAG_20260103"
    uid_cookie = req.cookies.get("cg_uid")
    root_diag = _repo_root_from_here()
    print("[/list/all]", FP_DIAG, "uid=", uid_cookie, "root=", root_diag)

    try:
        users_dir = root_diag / "state" / "users"
        print("[/list/all]", FP_DIAG, "users_dir=", users_dir, "exists=", users_dir.exists())
        if uid_cookie:
            udir = users_dir / str(uid_cookie)
            print("[/list/all]", FP_DIAG, "uid_dir=", udir, "exists=", udir.exists())
            idxp = udir / "sessions_index.json"
            print(
                "[/list/all]",
                FP_DIAG,
                "index_path=",
                idxp,
                "exists=",
                idxp.exists(),
                "size=",
                (idxp.stat().st_size if idxp.exists() else None),
            )
    except Exception as e:
        print("[/list/all]", FP_DIAG, "users_dir debug error:", repr(e))

    FP = "LIST_ALL_FP_B3_20260103"
    print("[/list/all]", FP, "HIT")

    import sys

    root = _repo_root_from_here()
    files = _gather_result_files(root)

    if debug:
        print(f"[list_all] __file__={__file__}", file=sys.stderr)
        print(f"[list_all] root={root} files={len(files)}", file=sys.stderr)

    best_by_sid: Dict[str, Path] = {}
    sid_from_doc = 0
    sid_from_name = 0
    sid_missing = 0

    for p in files:
        try:
            raw = _read_json_utf8_sig(p)
            doc = _normalize_doc(raw)

            sid = _extract_session_id(doc)
            if sid is not None:
                sid_from_doc += 1
            else:
                sid = _sid_from_filename(p)
                if sid is not None:
                    sid_from_name += 1
                else:
                    sid_missing += 1
                    continue

            if sid not in best_by_sid:
                best_by_sid[sid] = p
            else:
                best_by_sid[sid] = _prefer_path(best_by_sid[sid], p)
        except Exception:
            continue

    if debug:
        print(
            f"[list_all] sid_from_doc={sid_from_doc} sid_from_name={sid_from_name} sid_missing={sid_missing} unique={len(best_by_sid)}",
            file=sys.stderr,
        )

    # ✅ hent uid én gang (brukes også i Patch E lookup)
    uid_for_session = cg_uid or _get_or_set_uid(req, response)

    rows: List[Dict[str, Any]] = []
    for sid, p in best_by_sid.items():
        try:
            sid_str = str(sid)
            if (not isinstance(sid_str, str)) or (not sid_str.isdigit()) or (len(sid_str) > 20):
                print("[LIST/ALL] skip invalid sid:", sid_str)
                continue

            raw = _read_json_utf8_sig(p)
            doc = _normalize_doc(raw)
            row = _row_from_doc(doc, p, fallback_sid=sid_str)

            print(
                "[LIST/ALL][TRACE]",
                "sid=",
                sid_str,
                "has_end=",
                "end_time" in row,
                "end_val=",
                row.get("end_time"),
                "km_val=",
                row.get("distance_km"),
            )

            sid_item = str(row.get("session_id") or row.get("ride_id") or sid_str)

            DEBUG_SID = "16597678157"
            if sid_item == DEBUG_SID:
                root3 = _repo_root_from_here()
                p_dbg = root3 / "_debug" / f"result_{sid_item}.json"
                p_logs = root3 / "logs" / "results" / f"result_{sid_item}.json"
                print(
                    "[/list/all]",
                    FP,
                    "sid=",
                    sid_item,
                    "st_before=",
                    row.get("start_time"),
                    "exists_dbg=",
                    p_dbg.exists(),
                    "exists_logs=",
                    p_logs.exists(),
                    "root=",
                    str(root3),
                )

            # --- start_time fix (UTC ISO), kun når missing/DATE-only ---
            try:
                st = row.get("start_time")
                if _needs_start_time_fix(st):
                    rp = _pick_result_path(sid_item)
                    if rp:
                        t_abs = _extract_first_t_abs_fast(rp)
                        if t_abs:
                            row["start_time"] = t_abs
                            print("[/list/all]", "START_TIME_BACKFILL", "sid=", sid_item, "t_abs=", t_abs)
            except Exception as e:
                print("[/list/all]", "START_TIME_BACKFILL_ERR", "sid=", sid_item, "err=", repr(e))

            # --- PATCH C4: end_time + distance_km (result JSON fallback) ---
            try:
                print("[LIST/ALL][C4 ENTER] sid=", sid_item)

                need_end = row.get("end_time") is None
                need_km = row.get("distance_km") is None

                if need_end or need_km:
                    end_abs, km = _extract_end_time_and_km(sid_item)
                    if need_end and end_abs:
                        row["end_time"] = end_abs
                    if need_km and km is not None:
                        row["distance_km"] = km
            except Exception as e:
                print("[/list/all]", "END_KM_BACKFILL_ERR", "sid=", sid_item, "err=", repr(e))

            # --- PATCH E: SSOT fra session_<sid>.json (actual10/latest) ---
            try:
                if row.get("end_time") is None or row.get("distance_km") is None:
                    end_t, km2 = _extract_end_time_and_km_from_session(sid_item, uid=uid_for_session)
                    if row.get("end_time") is None:
                        row["end_time"] = end_t
                    if row.get("distance_km") is None:
                        row["distance_km"] = km2
            except Exception as e:
                print("[/list/all]", "E_SESSION_BACKFILL_ERR", "sid=", sid_item, "err=", repr(e))

            rows.append(row)
        except Exception:
            continue

    rows = [r for r in rows if (_to_float(r.get("precision_watt_avg")) or 0.0) > 0.0]
    rows.sort(key=lambda r: str(r.get("start_time") or ""), reverse=True)
    rows = rows[:200]

    if debug:
        print(f"[list_all] rows={len(rows)}", file=sys.stderr)

    # -------------------------------
    # Sprint 4: per-user filtering
    # -------------------------------

    root = _repo_root_from_here()
    index_path = root / "state" / "users" / uid_for_session / "sessions_index.json"

    if not index_path.exists():
        return {"value": [], "Count": 0}

    idx = None
    wanted: set[str] = set()
    idx_keys: list[str] = []

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

    before = len(rows)
    sample_before = [str(r.get("ride_id")) for r in rows[:12]]

    rows = [r for r in rows if str(r.get("ride_id")) in wanted]

    after = len(rows)
    sample_after = [str(r.get("ride_id")) for r in rows[:12]]

    out: Dict[str, Any] = {"value": rows, "Count": len(rows)}

    if debug:
        out["debug"] = {
            "uid": uid_for_session,
            "index_path": str(index_path).replace("\\", "/"),
            "idx_type": type(idx).__name__ if idx is not None else None,
            "idx_keys": idx_keys,
            "wanted_count": len(wanted),
            "wanted": sorted(list(wanted))[:20],
            "rows_before": before,
            "rows_after": after,
            "ride_ids_before_sample": sample_before,
            "ride_ids_after_sample": sample_after,
        }

    return out


@router.get("/list/_debug_paths")
async def _debug_paths() -> Dict[str, Any]:
    root = _repo_root_from_here()
    files = _gather_result_files(root)

    logs = root / "logs"
    p_results = logs / "results"
    p_actual10 = logs / "actual10"
    p_latest_dir = p_actual10 / "latest"

    def _glob_sorted(base: Path, pattern: str, limit: int = 8) -> list[str]:
        try:
            if not base.exists():
                return []
            xs = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
            return [str(p).replace("\\", "/") for p in xs[:limit]]
        except Exception:
            return []

    def _rglob_sorted(base: Path, pattern: str, limit: int = 8) -> list[str]:
        try:
            if not base.exists():
                return []
            xs = sorted(base.rglob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
            return [str(p).replace("\\", "/") for p in xs[:limit]]
        except Exception:
            return []

    def _pick_newest(paths):
        try:
            paths = list(paths or [])
            if not paths:
                return None
            paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return paths[0]
        except Exception:
            return None

    results_samples = _glob_sorted(p_results, "result_*.json", limit=8)
    latest_result_samples = _glob_sorted(p_latest_dir, "result_*.json", limit=8)
    actual10_session_samples = _rglob_sorted(p_actual10, "session_*.json", limit=8)

    def _count_glob(base: Path, pattern: str, recursive: bool = False) -> int:
        try:
            if not base.exists():
                return 0
            return sum(1 for _ in (base.rglob(pattern) if recursive else base.glob(pattern)))
        except Exception:
            return 0

    examples = []
    try:
        if p_results.exists():
            xs = sorted(p_results.glob("result_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]
            for p in xs:
                name = p.name
                rid = name.replace("result_", "").replace(".json", "")

                p_logs = root / "logs" / "results" / f"result_{rid}.json"
                logs_results = str(p_logs).replace("\\", "/") if p_logs.exists() else None

                cand_plain = p_latest_dir / f"result_{rid}.json"
                cand_glob = list(p_latest_dir.glob(f"result_{rid}*.json")) if p_latest_dir.exists() else []
                p_latest = cand_plain if cand_plain.exists() else _pick_newest(cand_glob)

                actual10_latest_result = str(p_latest).replace("\\", "/") if p_latest else None

                ex = {
                    "rid": rid,
                    "logs_results": logs_results,
                    "actual10_latest_result": actual10_latest_result,
                    "actual10_any_session_count": 0,
                }

                try:
                    ex["actual10_any_session_count"] = (
                        sum(1 for _ in p_actual10.rglob(f"session_{rid}.json")) if p_actual10.exists() else 0
                    )
                except Exception:
                    ex["actual10_any_session_count"] = 0

                examples.append(ex)
    except Exception:
        examples = []

    return {
        "router_file": str(Path(__file__).resolve()),
        "cwd": str(Path.cwd().resolve()),
        "root_from_here": str(root.resolve()),
        "files_from_here": len(files),
        "sample_files_from_here": [str(p).replace("\\", "/") for p in files[:8]],
        "logs_results_count": _count_glob(p_results, "result_*.json", recursive=False),
        "logs_results_samples": results_samples,
        "actual10_latest_result_count": _count_glob(p_latest_dir, "result_*.json", recursive=False),
        "actual10_latest_result_samples": latest_result_samples,
        "actual10_session_count": _count_glob(p_actual10, "session_*.json", recursive=True),
        "actual10_session_samples": actual10_session_samples,
        "ssot_examples": examples,
    }
