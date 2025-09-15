# -*- coding: utf-8 -*-
"""
CycleGraph CLI
- Subcommand 'efficiency': Bevarer eksisterende watt/puls-analyse + SHACL-validering
- Subcommand 'session':   NP/IF/VI/Pa:Hr/W/beat/CGS + batch/trend/formatters + 28d WpB-baseline
"""

import argparse
import csv
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Formatter for publiseringstekster (M7 4.1)
from cli.formatters.strava_publish import PublishPieces, build_publish_texts
from cli.strava_client import StravaClient

# =========================
#  Felles: importer kjernen
# =========================
# Støtter flere varianter av API:
# 1) Api.analyze_session(...) / Api.analyze_session_json(...) (statisk/klassemetode)
# 2) analyze_session(...)
# 3) calculate_efficiency_series(...) (legacy)

_analyze_session_bridge = None
_calc_eff_series = None

# === IMPORTER FUNKSJONER FRA KJERNEMODULEN ===
try:
    from cyclegraph_core import analyze_session as rust_analyze_session
except ImportError:
    rust_analyze_session = None

try:
    from cyclegraph_core import calculate_efficiency_series as _func_calc_eff
except ImportError:
    _func_calc_eff = None  # Hvis du har en legacy-versjon, importer den her

# === ANALYSEFUNKSJON ===
def _analyze_session_bridge(samples, meta, cfg):
    if rust_analyze_session is None:
        raise ImportError(
            "Ingen analyze_session tilgjengelig i cyclegraph_core. "
            "Bygg kjernen i core/: 'maturin develop --release'."
        )

    try:
        valid = [
            s for s in samples
            if "watts" in s and "hr" in s and s["watts"] is not None and s["hr"] is not None
        ]
        watts = [s["watts"] for s in valid]
        pulses = [s["hr"] for s in valid]
    except Exception as e:
        raise ValueError(f"Feil ved uthenting av watt/puls: {e}")

    try:
        result = rust_analyze_session(watts, pulses)
        print(f"DEBUG: rust_analyze_session output = {result}", file=sys.stderr)
        return result
    except ValueError as e:
        print("⚠️ Ingen effekt-data registrert – enkelte metrikker begrenset.")
        print(f"DEBUG: rust_analyze_session feilet med: {e}", file=sys.stderr)
        return {
            "mode": "hr_only",
            "status": "LIMITED",
            "avg_pulse": np.mean(pulses) if pulses else None
        }

# === EFFEKTIVITETSFUNKSJON ===
def _calc_eff_series(watts: List[float], pulses: List[float]):
    if _func_calc_eff is None:
        raise ImportError(
            "cyclegraph_core.calculate_efficiency_series mangler. "
            "Bygg kjernen i core/: 'maturin develop --release'."
        )
    return _func_calc_eff(watts,pulses)

# =====================================================


# ===================================
#  Subcommand: efficiency (BEHOLDER)
# ===================================

def validate_rdf(shape_path="shapes/session_shape.ttl", data_path="data/sample.ttl"):
    try:
        from pyshacl import validate
        from rdflib import Graph
    except ImportError:
        return False, "pyshacl/rdflib er ikke installert. Kjør: pip install pyshacl rdflib"

    sg = Graph().parse(shape_path, format="turtle")
    dg = Graph().parse(data_path, format="turtle")
    conforms, _vgraph, vtext = validate(
        dg,
        shacl_graph=sg,
        inference="rdfs",
        abort_on_first=False,
    )
    return bool(conforms), str(vtext)


def read_efficiency_csv(file_path: str):
    watts, pulses = [], []
    with open(file_path, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]

        def pick(row, *keys):
            for k in keys:
                if k in row and row[k] not in ("", None):
                    return row[k]
            return None

        for row in reader:
            row = {(k.strip().lower() if isinstance(k, str) else k): v for k, v in row.items()}
            w = pick(row, "watt", "watts", "power")
            p = pick(row, "puls", "pulse", "hr", "heart_rate")
            if w is None or p is None:
                continue
            try:
                watts.append(float(str(w).replace(",", ".")))
                pulses.append(float(str(p).replace(",", ".")))
            except ValueError:
                continue

    if not watts or not pulses:
        raise ValueError(
            "Fant ikke gyldige kolonner/verdier for watt/puls. "
            "Sjekk at CSV har kolonner som 'watt'/'watts' og 'puls'/'hr'."
        )
    return watts, pulses





# =================================
#  Subcommand: session (M7-KJERNE)
# =================================

def read_session_csv(path: str, debug: bool = False) -> List[Dict[str, Any]]:
    """
    Robust CSV-leser for session-analysen.
    Støtter comma/semicolon, mange alias for kolonner, hh:mm:ss og ISO-tid.
    Krever i praksis HR eller Watts (begge best). Tid avledes fleksibelt.
    """
    from datetime import datetime

    def sniff_delim_and_lines(p: str):
        with open(p, "rb") as fb:
            raw = fb.read()
        text = raw.decode("utf-8-sig", errors="ignore")
        first = text.splitlines()[0] if text else ""
        delim = "," if first.count(",") >= first.count(";") else ";"
        return delim, text.splitlines()

    def to_float(x):
        try:
            return float(str(x).strip().replace(",", "."))
        except Exception:
            return None

    def parse_hms(x: str) -> float | None:
        try:
            parts = [int(p) for p in x.strip().split(":")]
            if len(parts) == 3:
                h, m, s = parts
                return float(h*3600 + m*60 + s)
            if len(parts) == 2:
                m, s = parts
                return float(m*60 + s)
            return None
        except Exception:
            return None

    def parse_iso(x: str) -> float | None:
        try:
            dt = datetime.fromisoformat(x.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return None

    delim, lines = sniff_delim_and_lines(path)
    if not lines:
        if debug: print(f"DEBUG: {path} er tom.", file=sys.stderr)
        return []

    reader = csv.reader(lines, delimiter=delim)
    rows = list(reader)
    if not rows:
        if debug: print(f"DEBUG: {path} har ingen rader.", file=sys.stderr)
        return []

    headers = [h.strip().lower() for h in rows[0]]
    data_rows = rows[1:]

    if debug:
        print(f"DEBUG: {path} delimiter='{delim}'", file=sys.stderr)
        print(f"DEBUG: headers={headers}", file=sys.stderr)
        if data_rows:
            print(f"DEBUG: first_row={data_rows[0]}", file=sys.stderr)

    def col(*names: str) -> int | None:
        for n in names:
            if n in headers:
                return headers.index(n)
        return None

    ix_time = col("time", "t", "seconds", "elapsed", "elapsed_time", "timer_s", "sec", "tid")
    ix_hr   = col("hr", "heart_rate", "puls", "pulse", "bpm")
    ix_w    = col("watts", "power", "watt")
    ix_ts   = col("timestamp", "date", "datetime", "start_time", "time_utc")
    ix_alt  = col("altitude", "elev", "elevation", "hoyde", "høyde", "højde")

    out: List[Dict[str, Any]] = []
    t0_abs = None  # for ISO‑tid

    for i, row in enumerate(data_rows):
        if not row or all((c or "").strip() == "" for c in row):
            continue

        hr = to_float(row[ix_hr]) if ix_hr is not None and ix_hr < len(row) else None
        w  = to_float(row[ix_w])  if ix_w  is not None and ix_w  < len(row) else None

        t = None
        if ix_time is not None and ix_time < len(row):
            t = to_float(row[ix_time])
            if t is None:
                t = parse_hms(row[ix_time])
        if t is None and ix_ts is not None and ix_ts < len(row):
            ts = parse_iso(row[ix_ts])
            if ts is not None:
                if t0_abs is None:
                    t0_abs = ts
                t = ts - t0_abs
        if t is None:
            t = float(i)  # fallback

        alt = to_float(row[ix_alt]) if ix_alt is not None and ix_alt < len(row) else None
        moving = True
        out.append({"t": t, "hr": hr, "watts": w, "moving": moving, "altitude": alt})

    if not any(s["hr"] is not None for s in out) and not any(s["watts"] is not None for s in out):
        if debug: print(f"DEBUG: {path} har verken HR eller Watts i data.", file=sys.stderr)
        return []
    return out


def infer_duration_sec(samples: List[Dict[str, Any]]) -> float:
    if not samples:
        return 0.0
    ts = [s["t"] for s in samples if s["t"] is not None]
    if not ts:
        return 0.0
    return float(max(ts) - min(ts) + 1.0)


def estimate_ftp_20min95(samples: List[Dict[str, Any]]) -> float:
    """Beste 20-min avg * 0.95. 0 om ikke nok data."""
    if not samples:
        return 0.0
    S = sorted([s for s in samples if isinstance(s.get("t"), (int, float))], key=lambda x: x["t"])
    if not S:
        return 0.0
    t0, tN = S[0]["t"], S[-1]["t"]
    if tN - t0 + 1.0 < 1200.0:
        return 0.0

    import math
    left = 0
    pow_sum = 0.0
    best_avg = 0.0
    t = [s["t"] for s in S]
    w = [float(s["watts"]) if s["watts"] is not None else float('nan') for s in S]
    w = [0.0 if (x is None or (isinstance(x, float) and math.isnan(x))) else x for x in w]

    for right in range(len(S)):
        pow_sum += w[right]
        while t[right] - t[left] + 1.0 > 1200.0 and left < right:
            pow_sum -= w[left]
            left += 1
        window_sec = t[right] - t[left] + 1.0
        if window_sec >= 1195.0:
            avg = pow_sum / max(1.0, (right - left + 1))
            if avg > best_avg:
                best_avg = avg
    return float(best_avg * 0.95)


def apply_trend_last3(reports: List[Dict[str, Any]]) -> None:
    scores = [r.get("scores", {}).get("cgs") for r in reports]
    for i in range(len(reports)):
        last3 = [scores[j] for j in range(max(0, i - 3), i) if isinstance(scores[j], (int, float))]
        if len(last3) >= 3:
            avg3 = sum(last3) / 3.0
            cur = reports[i].get("scores", {}).get("cgs")
            if isinstance(cur, (int, float)) and avg3 > 0:
                delta = ((cur - avg3) / avg3) * 100.0
                reports[i].setdefault("trend", {})
                reports[i]["trend"]["cgs_last3_avg"] = round(avg3, 2)
                reports[i]["trend"]["cgs_delta_vs_last3"] = round(delta, 2)


def session_id_from_path(path: str) -> str:
    base = os.path.basename(path)
    stem = os.path.splitext(base)[0]
    return stem


def load_cfg(path: str) -> Dict[str, Any]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_report(outdir: str, sid: str, report: Dict[str, Any], fmt: str):
    os.makedirs(outdir, exist_ok=True)
    if fmt in ("json", "both"):
        p = os.path.join(outdir, f"{sid}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if fmt in ("csv", "both"):
        p = os.path.join(outdir, f"{sid}.csv")
        fields = [
            "session_id", "duration_min", "avg_power", "avg_hr", "np", "if", "vi", "pa_hr_pct",
            "w_per_beat", "scores.intensity", "scores.duration", "scores.quality", "scores.cgs"
        ]
        row = {
            "session_id": report.get("session_id"),
            "duration_min": report.get("duration_min"),
            "avg_power": report.get("avg_power"),
            "avg_hr": report.get("avg_hr"),
            "np": report.get("np"),
            "if": report.get("if"),
            "vi": report.get("vi"),
            "pa_hr_pct": report.get("pa_hr_pct"),
            "w_per_beat": report.get("w_per_beat"),
            "scores.intensity": report.get("scores", {}).get("intensity"),
            "scores.duration": report.get("scores", {}).get("duration"),
            "scores.quality": report.get("scores", {}).get("quality"),
            "scores.cgs": report.get("scores", {}).get("cgs"),
        }
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerow(row)

# NEW: skriv historikk-kopi når vi ikke er i --dry-run
def write_history_copy(history_dir: str, report: Dict[str, Any]):
    """
    Skriver en historikk-kopi med dato i filnavnet.
    Filnavn: {session_id}_{YYYY-MM-DD}.json
    """
    os.makedirs(history_dir, exist_ok=True)
    sid = report.get("session_id") or "session"
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    fname = f"{sid}_{date_str}.json"
    path = os.path.join(history_dir, fname)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"ADVARSEL: Klarte ikke å skrive history-fil: {path} ({e})", file=sys.stderr)


from cli.strava_client import StravaClient  # sørg for at denne importen er øverst

def publish_to_strava_stub(report: Dict[str, Any], dry_run: bool):
    """
    Ekte Strava-publish (navnet beholdes for bakoverkompabilitet).
    Bruker build_publish_texts -> PublishPieces -> StravaClient().publish_to_strava.
    """
    lang = (report.get("args", {}) or {}).get("lang", "no")

    try:
        res = build_publish_texts(report, lang=lang)
        if hasattr(res, "comment"):
            comment_text = getattr(res, "comment", "") or ""
            desc_header_text = getattr(res, "desc_header", "") or ""
            desc_body_text = getattr(res, "desc_body", "") or ""
        else:
            comment_text, desc_header_text, desc_body_text = res
    except Exception as e:
        print(f"[strava] build_publish_texts feilet: {e}")
        return None

    pieces = PublishPieces(
        comment=comment_text,
        desc_header=desc_header_text,
        desc_body=desc_body_text
    )

    try:
        aid, status = StravaClient(lang=lang).publish_to_strava(pieces, dry_run=dry_run)
        print(f"[strava] activity_id={aid} status={status}")
        return aid, status
    except Exception as e:
        print(f"[strava] publisering feilet: {e}")
        return None



# -----------------------------
#  28d WpB-baseline + BigEngine
# -----------------------------

DATE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")

def parse_date_from_sid_or_name(name: str):
    m = DATE_RE.search(name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group("date"), "%Y-%m-%d")
    except Exception:
        return None

def median(vals: list[float]):
    v = sorted([x for x in vals if isinstance(x, (int, float))])
    if not v:
        return None
    n = len(v)
    if n % 2 == 1:
        return float(v[n // 2])
    else:
        return float((v[n // 2 - 1] + v[n // 2]) / 2.0)

# NEW: robust baseline-laster (28d, ±25%, mtime-fallback)
def load_baseline_wpb(history_dir: str, cur_sid: str, cur_dur_min: float):
    """
    Leser JSON-rapporter i history_dir og returnerer median W/beat for økter:
      - innenfor siste 28 dager (basert på dato i filnavn ELLER filens mtime)
      - med varighet innenfor ±25% av gjeldende økt
    """
    now = datetime.utcnow()
    window_start = now - timedelta(days=28)

    files = sorted(glob.glob(os.path.join(history_dir, "*.json")))
    candidates = []

    for p in files:
        # 1) Les rapport
        try:
            with open(p, "r", encoding="utf-8") as f:
                r = json.load(f)
        except Exception:
            continue

        # 2) Dato: session_id/filnavn → ellers mtime
        sid_name = r.get("session_id") or os.path.basename(p)
        dt = parse_date_from_sid_or_name(sid_name) or parse_date_from_sid_or_name(os.path.basename(p))
        if not dt:
            try:
                mtime = os.path.getmtime(p)
                dt = datetime.utcfromtimestamp(mtime)
            except Exception:
                dt = None

        if dt and dt < window_start:
            continue  # for gammel

        # 3) Felt
        wpb = r.get("w_per_beat")
        dmin = r.get("duration_min")
        if not isinstance(wpb, (int, float)) or not isinstance(dmin, (int, float)):
            continue

        # 4) Varighetsvindu ±25%
        lo = cur_dur_min * 0.75
        hi = cur_dur_min * 1.25
        if not (lo <= dmin <= hi):
            continue

        candidates.append(float(wpb))

    return median(candidates)

def maybe_apply_big_engine_badge(report: dict) -> None:
    w = report.get("w_per_beat")
    b = report.get("w_per_beat_baseline")
    if isinstance(w, (int, float)) and isinstance(b, (int, float)) and b > 0:
        delta = (w - b) / b
        if delta >= 0.10:
            badges = report.setdefault("badges", [])
            if "Big Engine" not in badges:
                badges.append("Big Engine")




from cli.parser import build_parser



import json
from pathlib import Path
from cyclegraph_core import profile_from_json
from cli.parser import build_parser  # Husk denne importen

def load_profile():
    path = Path("state/profile.sample.json")
    if not path.exists():
        return profile_from_json("{}")
    with open(path) as f:
        return profile_from_json(f.read())

def main():
    parser = build_parser()
    args = parser.parse_args()

    profile = load_profile()
    print("Profil:", profile)

    # Hvis du senere vil bruke profilen i args.func, kan du sende den inn her
    sys.exit(args.func(args))