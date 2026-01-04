# frontend/server/routes/sessions_list_router.py
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Query, Request, Response
from server.routes.auth_strava import _get_or_set_uid

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# -------------------------------
# PATCH B2/B3: start_time fra resultfil + fingerprint/debug
# -------------------------------
_TABS_RE = re.compile(r'"t_abs"\s*:\s*"([^"]+)"')

# PATCH C2: end_time fra resultfil (siste t_abs i fil-tail)
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


def _extract_last_t_abs_fast(p: Path) -> Optional[str]:
    """
    PATCH C2: Leser siste forekomst av "t_abs": "..." ved å lese bare slutten av fila.
    Dette er raskt nok og unngår å parse hele JSON.
    """
    try:
        data = p.read_bytes()
    except Exception:
        return None

    # Les bare siste ~256k for speed (nok til å fange siste samples-blokk)
    tail = data[-262144:] if len(data) > 262144 else data
    try:
        txt = tail.decode("utf-8", errors="ignore")
    except Exception:
        return None

    matches = list(_LAST_TABS_RE.finditer(txt))
    if not matches:
        return None
    return matches[-1].group(1)


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
        for p in path:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
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
    """
    Velg "avg" i riktig rekkefølge.

    Viktig: legacy docs kan ha doc.watts som ikke er "precision/model/total".
    Derfor bruker vi ALDRI watts-mean som fallback før vi har en verifisert kontrakt.
    """
    pw_avg = _to_float(doc.get("precision_watt_avg"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("precision_watt_avg"))

    # Foretrekk modell/total før precision_watt i legacy
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("model_watt_wheel"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("total_watt"))
    if pw_avg is None:
        pw_avg = _to_float(metrics.get("precision_watt"))

    return pw_avg


def _row_from_doc(doc: Dict[str, Any], source_path: Path, fallback_sid: str) -> Dict[str, Any]:
    """
    Bygger rad. Bruker fallback_sid hvis doc mangler id.
    """
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

    # PATCH C-final (safe): never break listing
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
        # FIX: filtrer bort "_direct" så vi ikke får dobbelt/rare varianter
        files.extend(sorted([p for p in dbg.glob("result_*.json") if "_direct" not in p.name]))

    lr = root / "logs" / "results"
    if lr.exists():
        files.extend(sorted(lr.glob("result_*.json")))

    out = root / "out"
    if out.exists():
        files.extend(sorted(out.glob("result_*.json")))

    return files


def _prefer_path(a: Path, b: Path) -> Path:
    """
    Velg "beste" path for samme rid.

    Primærregel: NYESTE fil (mtime) vinner.
    Tie-break #1: logs/results foretrekkes fremfor _debug, deretter out.
    Tie-break #2: størst fil vinner (ofte full doc vs stub).
    """

    def tier(p: Path) -> int:
        s = str(p).replace("\\", "/")
        if "/logs/results/" in s:
            return 0
        if "/_debug/" in s:
            return 1
        if "/out/" in s:
            return 2
        return 9

    # 1) Nyeste mtime vinner
    try:
        ma = a.stat().st_mtime
        mb = b.stat().st_mtime
        if ma != mb:
            return a if ma > mb else b
    except Exception:
        pass

    # 2) Tier hvis mtime feiler/lik
    ta, tb = tier(a), tier(b)
    if ta != tb:
        return a if ta < tb else b

    # 3) Størst fil hvis fortsatt likt
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
    # ✅ PATCH C2: fjernet C1 early return, så listing kjører igjen.

    # ✅ PATCH A: Én enkel backend-print som gir oss fasit
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
            idx = udir / "sessions_index.json"
            print(
                "[/list/all]",
                FP_DIAG,
                "index_path=",
                idx,
                "exists=",
                idx.exists(),
                "size=",
                (idx.stat().st_size if idx.exists() else None),
            )
    except Exception as e:
        print("[/list/all]", FP_DIAG, "users_dir debug error:", repr(e))

    # PATCH B3: fingerprint helt øverst (beholdt)
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

    rows: List[Dict[str, Any]] = []
    for sid, p in best_by_sid.items():
        try:
            raw = _read_json_utf8_sig(p)
            doc = _normalize_doc(raw)
            item = _row_from_doc(doc, p, fallback_sid=sid)

            sid_item = str(item.get("session_id") or item.get("ride_id") or "")

            # PATCH: Minimal debug kun for én sid (B3-loop debug)
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
                    item.get("start_time"),
                    "exists_dbg=",
                    p_dbg.exists(),
                    "exists_logs=",
                    p_logs.exists(),
                    "root=",
                    str(root3),
                )

            # --- C3.1: Backfill start_time fra resultfil (UTC ISO), kun når missing/DATE-only ---
            try:
                st = item.get("start_time")
                if _needs_start_time_fix(st):
                    rp = _pick_result_path(sid_item or sid)
                    if rp:
                        t_abs = _extract_first_t_abs_fast(rp)
                        if t_abs:
                            item["start_time"] = t_abs
                            print("[/list/all]", "START_TIME_BACKFILL", "sid=", (sid_item or sid), "t_abs=", t_abs)
            except Exception as e:
                print("[/list/all]", "START_TIME_BACKFILL_ERR", "sid=", (sid_item or sid), "err=", repr(e))

            # --- PATCH C2: Backfill end_time fra resultfil (siste t_abs), kun når mangler ---
            try:
                end_time = item.get("end_time")
                if end_time is None:
                    rp2 = _pick_result_path(sid_item or sid)
                    if rp2 is not None:
                        last_abs = _extract_last_t_abs_fast(rp2)
                        if last_abs:
                            item["end_time"] = last_abs
                            print("[/list/all]", "END_TIME_BACKFILL", "sid=", (sid_item or sid), "t_abs=", last_abs)
            except Exception as e:
                print("[/list/all]", "END_TIME_BACKFILL_ERR", "sid=", (sid_item or sid), "err=", repr(e))

            rows.append(item)
        except Exception:
            continue

    # FIX: dropp helt tomme placeholder-resultater (typisk 0.0 i logs/results)
    rows = [r for r in rows if (_to_float(r.get("precision_watt_avg")) or 0.0) > 0.0]

    rows.sort(key=lambda r: str(r.get("start_time") or ""), reverse=True)

    # SAFE CAP (backend): keep it bounded but not UI-hardcoded
    rows = rows[:200]

    if debug:
        print(f"[list_all] rows={len(rows)}", file=sys.stderr)

    # -------------------------------
    # Sprint 4: per-user filtering
    # -------------------------------
    uid = cg_uid or _get_or_set_uid(req, response)

    # ✅ bruk repo-root (SSOT), ikke cwd
    root = _repo_root_from_here()
    index_path = root / "state" / "users" / uid / "sessions_index.json"

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
            "uid": uid,
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
    files = _gather_result_files(root)  # eksisterende (typisk _debug/result_*.json)

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
