# scripts/patch_cli_session_power.py
import io, os, re, sys, json

PATH = "cli/session.py"

TRY_IMPORT = r'''
try:
    from cyclegraph_core import compute_power_with_wind_json as rs_power_json
except Exception:
    rs_power_json = None
'''.strip()+"\n"

NORMALIZER = r'''
def _normalize_sample_for_core(s: dict) -> dict:
    """Map CSV/sample-dict til core Sample-felter."""
    from datetime import datetime

    # tid (sekunder eller ISO)
    t = s.get("t") or s.get("time") or s.get("timestamp")
    if isinstance(t, str):
        try:
            t = datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp()
        except Exception:
            try:
                t = float(t)
            except Exception:
                t = None

    # fart (m/s)
    v = s.get("v_ms")
    if v is None:
        v = s.get("speed") or s.get("speed_ms") or s.get("velocity")
    if isinstance(v, (int, float)) and v > 50:  # km/t → m/s
        v = v / 3.6

    # høyde
    alt = s.get("altitude_m")
    if alt is None:
        alt = s.get("altitude") or s.get("elev") or s.get("elevation")

    # GPS
    lat = s.get("latitude") or s.get("lat")
    lon = s.get("longitude") or s.get("lon") or s.get("lng")
    try:
        lat = None if lat is None or lat == "" else float(lat)
    except Exception:
        lat = None
    try:
        lon = None if lon is None or lon == "" else float(lon)
    except Exception:
        lon = None

    # device_watts (valgfri)
    devw = s.get("device_watts") or s.get("watts") or s.get("power")
    try:
        devw = None if devw is None or devw == "" else float(devw)
    except Exception:
        devw = None

    return {
        "t": float(t) if isinstance(t, (int, float)) else 0.0,
        "v_ms": float(v) if isinstance(v, (int, float)) else 0.0,
        "altitude_m": float(alt) if isinstance(alt, (int, float)) else 0.0,
        "heading_deg": float(s.get("heading_deg", 0.0)),
        "moving": bool(s.get("moving", True)),
        "device_watts": devw,
        "latitude": lat,
        "longitude": lon,
    }
'''.strip()+"\n"

CALL_BLOCK = r'''
        # ── S5: Populer watts/wind_rel/v_rel fra core (via PyO3-binding) ──
        try:
            if rs_power_json is not None:
                core_samples = [_normalize_sample_for_core(s) for s in samples]
                profile_for_core = {
                    "total_weight": report.get("weight") or cfg.get("total_weight") or cfg.get("weight") or 78.0,
                    "bike_type": report.get("bike_type") or cfg.get("bike_type") or "road",
                    "crr": report.get("crr"),
                    "cda": report.get("cda"),
                    "calibrated": bool(report.get("calibrated")) if isinstance(report.get("calibrated"), bool) else False,
                    "calibration_mae": report.get("mae"),
                    "estimat": True,
                }
                weather_for_core = _load_weather_for_cal(args)

                power_json = rs_power_json(
                    json.dumps(core_samples, ensure_ascii=False),
                    json.dumps(profile_for_core, ensure_ascii=False),
                    json.dumps(weather_for_core, ensure_ascii=False),
                )
                power_obj = json.loads(power_json) if isinstance(power_json, str) else power_json
                if isinstance(power_obj, dict):
                    for k in ("watts", "wind_rel", "v_rel"):
                        if k in power_obj:
                            report[k] = power_obj[k]
            else:
                if getattr(args, "debug", False):
                    print("DEBUG: rs_power_json is None (binding mangler) – viser fallback []", file=sys.stderr)
        except Exception as e:
            if getattr(args, "debug", False):
                print(f"DEBUG: compute_power_with_wind_json feilet: {e}", file=sys.stderr)
'''.rstrip()+"\n"

def main():
    if not os.path.isfile(PATH):
        print(f"[ERR] Fant ikke {PATH}", file=sys.stderr)
        sys.exit(1)

    with io.open(PATH, "r", encoding="utf-8") as f:
        src = f.read()

    changed = False

    # 1) try-import
    if "rs_power_json = None" not in src and "compute_power_with_wind_json" not in src:
        # legg etter andre try-imports (bruk en enkel anker: rust_analyze_session)
        anchor = "rust_analyze_session = None"
        pos = src.find(anchor)
        if pos != -1:
            insert_at = src.find("\n", pos) + 1
            src = src[:insert_at] + "\n" + TRY_IMPORT + src[insert_at:]
            changed = True
            print("[OK] La til try-import for compute_power_with_wind_json")

    # 2) normalizer
    if "def _normalize_sample_for_core" not in src:
        # legg før cmd_session
        anchor = "def cmd_session(args: argparse.Namespace)"
        pos = src.find(anchor)
        if pos == -1:
            # fallback: legg før slutten
            src = src + "\n\n" + NORMALIZER
        else:
            src = src[:pos] + "\n" + NORMALIZER + src[pos:]
        changed = True
        print("[OK] La til helper _normalize_sample_for_core")

    # 3) call-block i cmd_session – før "Baseline/badge/skriving"
    if "compute_power_with_wind_json" not in src or "Populer watts/wind_rel/v_rel" not in src:
        anchor = "Baseline/badge/skriving"
        pos = src.find(anchor)
        if pos == -1:
            # fallback: prøv før "reports.append(report)"
            anchor2 = "reports.append(report)"
            pos2 = src.find(anchor2)
            if pos2 != -1:
                src = src[:pos2] + CALL_BLOCK + src[pos2:]
                changed = True
                print("[OK] La til kallet til rs_power_json (fallback-anker)")
            else:
                print("[WARN] Fant ikke passende anker; ingen injeksjon for call-block")
        else:
            # finn starten av linjen med anchor og sett call-block rett før
            line_start = src.rfind("\n", 0, pos) + 1
            src = src[:line_start] + CALL_BLOCK + src[line_start:]
            changed = True
            print("[OK] La til kallet til rs_power_json før Baseline/badge/skriving")

    if changed:
        with io.open(PATH, "w", encoding="utf-8") as f:
            f.write(src)
        print(f"[DONE] Patch oppdatert: {PATH}")
    else:
        print("[SKIP] Ingen endringer nødvendig")

if __name__ == "__main__":
    main()