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
from cli.strava_client import publish_to_strava
# =========================
#  Felles: importer kjernen
# =========================
# Støtter flere varianter av API:
# 1) Api.analyze_session(...) / Api.analyze_session_json(...) (statisk/klassemetode)
# 2) analyze_session(...)
# 3) calculate_efficiency_series(...) (legacy)
_analyze_session_bridge = None
_calc_eff_series = None

try:
    from cyclegraph_core import Api  # pyo3-eksport uten konstruktør

    def _analyze_session(samples, meta, cfg):
        return Api.analyze_session(samples, meta, cfg)

    def _analyze_session_json(samples_json: str, meta_json: str, cfg_json: str | None):
        return Api.analyze_session_json(samples_json, meta_json, cfg_json)

    def _analyze_session_bridge(samples, meta, cfg):
        # Prøv JSON-varianten først; fall tilbake til dict-API hvis nødvendig
        try:
            out_json = _analyze_session_json(
                json.dumps(samples),
                json.dumps(meta),
                json.dumps(cfg) if cfg else None
            )
            return json.loads(out_json)
        except Exception:
            return _analyze_session(samples, meta, cfg)

    def _calc_eff_series(watts: List[float], pulses: List[float]):
        return Api.calculate_efficiency_series(watts, pulses)

except ImportError:
    try:
        from cyclegraph_core import analyze_session as _func_analyze_session
        try:
            from cyclegraph_core import calculate_efficiency_series as _func_calc_eff
        except ImportError:
            _func_calc_eff = None

        def _analyze_session_bridge(samples, meta, cfg):
            return _func_analyze_session(samples, meta, cfg)

        def _calc_eff_series(watts: List[float], pulses: List[float]):
            if _func_calc_eff is None:
                raise ImportError(
                    "cyclegraph_core.calculate_efficiency_series mangler. "
                    "Bygg kjernen i core/: 'maturin develop --release'."
                )
            return _func_calc_eff(watts, pulses)

    except ImportError:
        from cyclegraph_core import calculate_efficiency_series as _legacy_calc_eff

        def _analyze_session_bridge(samples, meta, cfg):
            raise ImportError(
                "Ingen analyze_session tilgjengelig i cyclegraph_core. "
                "Bygg kjernen i core/: 'maturin develop --release'."
            )

        def _calc_eff_series(watts: List[float], pulses: List[float]):
            return _legacy_calc_eff(watts, pulses)
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


def cmd_efficiency(args: argparse.Namespace) -> int:
    if args.validate:
        conforms, report = validate_rdf()
        print("SHACL validation:", "OK ✅" if conforms else "FAILED ❌")
        if not conforms:
            print(report)
            return 2

    watts, pulses = read_efficiency_csv(args.file)
    avg_eff, session_status, per_point_eff, per_point_status = _calc_eff_series(watts, pulses)

    print("\n📊 CycleGraph Report (Efficiency)")
    print("=================================")
    print(f"Snitteffektivitet: {avg_eff:.2f} watt/puls")
    print(f"Øktstatus: {session_status}\n")

    print("Per datapunkt:")
    for i, (eff, status) in enumerate(zip(per_point_eff, per_point_status), start=1):
        print(f"  Punkt {i}: {eff:.2f} watt/puls – {status}")

    if args.json:
        report_data = {
            "average_efficiency": round(avg_eff, 2),
            "session_status": session_status,
            "points": [
                {"point": i + 1, "efficiency": round(eff, 2), "status": status}
                for i, (eff, status) in enumerate(zip(per_point_eff, per_point_status))
            ],
        }
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Rapport lagret som JSON: {args.json}")
    return 0


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


def publish_to_strava_stub(report: Dict[str, Any], dry_run: bool):
    """
    Ekte Strava-publish (navnet beholdes for bakoverkompabilitet).
    Bruker build_publish_texts -> PublishPieces -> publish_to_strava.
    """
    # Finn språk dersom det ligger i report.args; ellers default "no"
    lang = (report.get("args", {}) or {}).get("lang", "no")

    try:
        res = build_publish_texts(report, lang=lang)
        # Håndter både PublishPieces-objekt og ev. (comment, header, body)-tuple
        if hasattr(res, "comment"):
            comment_text = getattr(res, "comment", "") or ""
            desc_header_text = getattr(res, "desc_header", "") or ""
            desc_body_text = getattr(res, "desc_body", "") or ""
        else:
            # antas å være tuple/list
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
        aid, status = publish_to_strava(pieces, lang=lang, dry_run=dry_run)
        print(f"[strava] activity_id={aid} status={status}")
        return aid, status
    except Exception as e:
        print(f"[strava] publisering feilet: {e}")
        return None


    pieces = PublishPieces(
        comment=comment_text,
        desc_header=desc_header_text,
        desc_body=desc_body_text
    )

    try:
        aid, status = publish_to_strava(pieces, lang=lang, dry_run=dry_run)
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


def cmd_session(args: argparse.Namespace) -> int:
    cfg = load_cfg(args.cfg)
    history_dir = cfg.get("history_dir", "history")
    outdir = getattr(args, "out", "output")
    fmt = getattr(args, "format", "json")

    paths = sorted(glob.glob(args.input))
    if getattr(args, "debug", False):
        print("DEBUG: input filer:", paths, file=sys.stderr)
    if not paths:
        print(f"Ingen filer for pattern: {args.input}", file=sys.stderr)
        return 2

    reports: List[Dict[str, Any]] = []

    for path in paths:
        samples = read_session_csv(path, debug=getattr(args, "debug", False))
        if getattr(args, "debug", False):
            print(f"DEBUG: {path} -> {len(samples)} samples", file=sys.stderr)
        if not samples:
            print(f"ADVARSEL: {path} har ingen gyldige samples.", file=sys.stderr)
            continue

        sid = session_id_from_path(path)
        duration_sec = infer_duration_sec(samples)
        meta = {
            "session_id": sid,
            "duration_sec": duration_sec,
            "ftp": None,
            "hr_max": cfg.get("hr_max"),
            "start_time_utc": None
        }

        # FTP prioritet: --set-ftp > --auto-ftp > cfg.ftp
        if getattr(args, "set_ftp", None) is not None:
            meta["ftp"] = float(args.set_ftp)
        elif getattr(args, "auto_ftp", False):
            ftp_est = estimate_ftp_20min95(samples)
            if ftp_est > 0:
                meta["ftp"] = round(ftp_est, 1)
        elif "ftp" in cfg:
            meta["ftp"] = cfg.get("ftp")

        # KJØR KJERNEANALYSE via bridge (støtter både JSON- og dict-API)
        report = _analyze_session_bridge(samples, meta, cfg)

        # 28d baseline + Big Engine (post-prosess)
        baseline = load_baseline_wpb(history_dir, sid, report.get("duration_min", 0.0))
        if baseline is not None:
            report["w_per_beat_baseline"] = round(baseline, 4)
        maybe_apply_big_engine_badge(report)

        reports.append(report)

        # Skriv nå hvis ikke batch
        if not getattr(args, "batch", False):
            if getattr(args, "dry_run", False):
                print(json.dumps(report, ensure_ascii=False, indent=2))
                pieces = build_publish_texts(report, lang=getattr(args, "lang", "no"))
                print(f"[DRY-RUN] COMMENT: {pieces.comment}")
                print(f"[DRY-RUN] DESC: {pieces.desc_header}")
            else:
                write_report(outdir, sid, report, fmt)
                # NEW: seed history når vi IKKE er i dry-run
                write_history_copy(history_dir, report)

            if getattr(args, "publish_to_strava", False):
                publish_to_strava_stub(report, getattr(args, "dry_run", False))

    # Batch etterbehandling
    if getattr(args, "batch", False) and reports:
        if getattr(args, "with_trend", False):
            apply_trend_last3(reports)

        for r in reports:
            sid = r.get("session_id", "session")
            # baseline/badge også her (i tilfelle history fylles underveis)
            baseline = load_baseline_wpb(history_dir, sid, r.get("duration_min", 0.0))
            if baseline is not None:
                r["w_per_beat_baseline"] = round(baseline, 4)
            maybe_apply_big_engine_badge(r)

            if getattr(args, "dry_run", False):
                print(json.dumps(r, ensure_ascii=False, indent=2))
                pieces = build_publish_texts(r, lang=getattr(args, "lang", "no"))
                print(f"[DRY-RUN] COMMENT: {pieces.comment}")
                print(f"[DRY-RUN] DESC: {pieces.desc_header}")
            else:
                write_report(outdir, sid, r, fmt)
                # NEW: seed history når vi IKKE er i dry-run
                write_history_copy(history_dir, r)

        if getattr(args, "publish_to_strava", False):
            publish_to_strava_stub(reports[-1], getattr(args, "dry_run", False))

    return 0


# ===============
#  Argparse setup
# ===============
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CycleGraph CLI (efficiency | session)")
    sub = p.add_subparsers(dest="command", required=True)

    pe = sub.add_parser("efficiency", help="Analyser watt/puls-effektivitet fra CSV (kolonner: watt,puls).")
    pe.add_argument("--file", required=True, help="Path til CSV med kolonner 'watt' og 'puls'.")
    pe.add_argument("--validate", action="store_true", help="Valider RDF mot SHACL før analyse.")
    pe.add_argument("--json", help="Lagre efficiency-rapport som JSON.")
    pe.set_defaults(func=cmd_efficiency)

    ps = sub.add_parser("session", help="Analyser treningsøkter (NP/IF/VI/Pa:Hr/WpB/CGS) fra CSV.")
    ps.add_argument("--input", required=True, help="Glob for CSV, f.eks. data/*.csv")
    ps.add_argument("--out", default="output", help="Output-mappe (default: output/)")
    ps.add_argument("--cfg", default="", help="Path til config.json")
    ps.add_argument("--format", choices=["json", "csv", "both"], default="json", help="Rapportformat")
    ps.add_argument("--batch", action="store_true", help="Analyser alle filer i én batch")
    ps.add_argument("--with-trend", action="store_true", help="Legg til minitrend (siste 3) i batch")
    ps.add_argument("--set-ftp", type=float, default=None, help="Overstyr FTP for alle sessions")
    ps.add_argument("--auto-ftp", action="store_true", help="Estimer FTP (20min*0.95) hvis mulig")
    ps.add_argument("--publish-to-strava", action="store_true", help="(Stub) Publiser kort/tekst til Strava")
    ps.add_argument("--dry-run", action="store_true", help="Skriv kun til stdout (ingen filer)")
    ps.add_argument("--debug", action="store_true", help="Print diagnostikk om CSV-parsing pr. fil")
    ps.add_argument("--lang", choices=["no", "en"], default="no", help="Språk for publiseringstekster (no/en)")
    ps.set_defaults(func=cmd_session)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
