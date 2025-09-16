#!/usr/bin/env python3
import json
import os
import re
import sys
import subprocess
from typing import Any, Dict, List, Optional, Tuple

DEBUG = os.environ.get("CG_DEBUG_WEATHER") == "1"

try:
    import argparse
    import requests  # pip install requests
except Exception:
    print("❌ Mangler avhengigheter. Kjør: pip install requests", file=sys.stderr)
    sys.exit(1)

# Felter vi validerer mot når vi sjekker "realistisk"
FIELDS = [
    ("temperature_2m", "temperature"),
    ("relative_humidity_2m", "humidity"),
    ("wind_speed_10m", "wind_speed"),
    ("wind_direction_10m", "wind_direction"),
    ("surface_pressure", "pressure"),
]

def _project_dirs() -> Tuple[str, str]:
    script = os.path.abspath(__file__)
    cli_dir = os.path.dirname(script)
    root = os.path.dirname(cli_dir)
    data_dir = os.path.join(root, "data")
    return root, data_dir

def _norm_env_path(val: str, base_dir: str) -> str:
    p = os.path.normpath(val)
    if os.path.isabs(p):
        return p
    parts = p.split(os.sep)
    if parts and parts[0].lower() == "data":
        parts = parts[1:]
        p = os.path.join(*parts) if parts else ""
    return os.path.join(base_dir, p)

def _latest_weather_file(data_dir: str) -> Optional[str]:
    cands = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith("_weather.json")]
    return max(cands, key=os.path.getmtime) if cands else None

def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        return float(s) if s else None
    except Exception:
        return None

def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _get_hourly(data: Dict[str, Any]) -> Dict[str, List[Any]]:
    hourly = data.get("hourly")
    if not isinstance(hourly, dict):
        raise RuntimeError("Ingen 'hourly' i responsen.")
    return hourly

def _iter_indices(hourly: Dict[str, List[Any]]) -> List[int]:
    times = hourly.get("time") or []
    if isinstance(times, list) and times:
        return list(range(len(times)))
    # fallback: maks lengde av de feltene vi bryr oss om
    mx = 0
    for src, _dst in FIELDS:
        arr = hourly.get(src, [])
        if isinstance(arr, list):
            mx = max(mx, len(arr))
    return list(range(mx)) if mx > 0 else []

def _collect_ctx(hourly: Dict[str, List[Any]], idx: int) -> Tuple[Dict[str, Optional[float]], Optional[str]]:
    ctx: Dict[str, Optional[float]] = {}
    for src, dst in FIELDS:
        arr = hourly.get(src, [])
        v = arr[idx] if isinstance(arr, list) and idx < len(arr) else None
        ctx[dst] = _safe_float(v)
    ts = None
    times = hourly.get("time", [])
    if isinstance(times, list) and idx < len(times):
        ts = str(times[idx])
    return ctx, ts

def _is_complete(ctx: Dict[str, Optional[float]]) -> bool:
    return all(ctx[k] is not None for _, k in FIELDS)

def _is_nonzero(ctx: Dict[str, Optional[float]]) -> bool:
    return all((ctx[k] or 0.0) != 0.0 for _, k in FIELDS)

def _is_realistic(ctx: Dict[str, Optional[float]]) -> bool:
    t = ctx["temperature"]; h = ctx["humidity"]; ws = ctx["wind_speed"]; wd = ctx["wind_direction"]; p = ctx["pressure"]
    if None in (t, h, ws, wd, p):
        return False
    if not (-60.0 <= t <= 60.0): return False
    if not (0.0 <= h <= 100.0): return False
    if not (0.0 <= ws <= 70.0): return False
    if not (0.0 <= wd <= 360.0): return False
    if not (850.0 <= p <= 1100.0): return False
    return True

def _print_ctx(label: str, ts: Optional[str], ctx: Dict[str, Optional[float]]):
    print(f"{label} {('[' + ts + ']') if ts else ''}: {ctx}")

def _probe_forecast(lat: float,
                    lon: float,
                    tz: str = "Europe/Oslo",
                    fields: Optional[str] = None,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Kall forecast-endpoint med *minimale* parametere for å unngå 400-feil:
      - latitude, longitude, hourly, timezone
      - (valgfritt) start_date/end_date
    """
    base = "https://api.open-meteo.com/v1/forecast"
    hourly = fields or "temperature_2m"  # minimal
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "hourly": hourly,
        "timezone": tz,
    }
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date

    # Bygg URL for logging
    from urllib.parse import urlencode
    url = f"{base}?{urlencode(params)}"
    if DEBUG:
        print("[DBG] Probe URL:", url)

    r = requests.get(base, params=params, timeout=30)
    if DEBUG:
        try:
            print("[DBG] Probe status:", r.status_code)
            print("[DBG] Probe response (trunkert):", r.text[:2000])
        except Exception:
            pass
    r.raise_for_status()
    data = r.json()

    # Sanity: hourly finnes og har verdier
    hourly_block = data.get("hourly")
    if not isinstance(hourly_block, dict) or not hourly_block.get("time"):
        raise RuntimeError("Forecast-respons mangler 'hourly.time'")
    # Sjekk at minst ett felt har tall ved første timestamp
    idx = 0
    ok = False
    for key in (fields.split(",") if fields else ["temperature_2m"]):
        arr = hourly_block.get(key, [])
        if isinstance(arr, list) and len(arr) > idx and _safe_float(arr[idx]) is not None:
            ok = True
            break
    if not ok:
        raise RuntimeError("Forecast 'hourly' inneholder ikke tallverdier ved første timestamp.")
    return data

def _try_regenerate_with_probe(lat: float, lon: float, tz: str, out_path: str) -> bool:
    """Hent minimal forecast og lagre til out_path."""
    try:
        data = _probe_forecast(lat, lon, tz=tz, fields=",".join(f[0] for f in FIELDS))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"💾 Lagret hentet forecast til: {out_path}")
        return True
    except Exception as e:
        print(f"ℹ️  Probe-forecast feilet: {e}")
        return False

def main():
    root, data_dir = _project_dirs()

    ap = argparse.ArgumentParser(description="Valider værfil, og/eller probe Open-Meteo forecast uten 400-feil.")
    ap.add_argument("--weather", "-w", help="Valgfri sti til *_weather.json (default: siste i data/)")
    ap.add_argument("--probe-forecast", action="store_true",
                    help="Kall forecast-endpoint direkte med minimale parametere (krever --lat og --lon).")
    ap.add_argument("--lat", type=float, help="Latitude for probe-forecast (f.eks. 59.41721)")
    ap.add_argument("--lon", type=float, help="Longitude for probe-forecast (f.eks. 10.48343)")
    ap.add_argument("--tz", default="Europe/Oslo", help="Timezone for probe (default: Europe/Oslo)")
    ap.add_argument("--fields", default="temperature_2m",
                    help="CSV med hourly-felter for probe (default: temperature_2m)")
    ap.add_argument("--start-date", help="Valgfri start_date (YYYY-MM-DD) for probe")
    ap.add_argument("--end-date", help="Valgfri end_date (YYYY-MM-DD) for probe")
    ap.add_argument("--out", help="Lagre responsen til fil")
    ap.add_argument("--debug", action="store_true", help="Ekstra logging")
    args = ap.parse_args()

    if args.debug:
        global DEBUG
        DEBUG = True

    # Hvis --probe-forecast: hent data -> valider -> (lagre) -> exit
    if args.probe_forecast:
        if args.lat is None or args.lon is None:
            print("❌ --probe-forecast krever --lat og --lon", file=sys.stderr)
            sys.exit(1)
        try:
            data = _probe_forecast(
                lat=args.lat, lon=args.lon, tz=args.tz,
                fields=args.fields, start_date=args.start_date, end_date=args.end_date
            )
            # Valider at dataene har komplette/realistiske verdier (best effort)
            hourly = _get_hourly(data)
            idxs = _iter_indices(hourly)
            if not idxs:
                raise RuntimeError("Ingen timestamps i forecast-responsen.")
            # finn første realistiske
            ok = False
            for i in idxs:
                ctx, ts = _collect_ctx(hourly, i)
                if _is_complete(ctx) and _is_realistic(ctx):
                    _print_ctx("✅ Første realistiske (probe)", ts, ctx)
                    ok = True
                    break
            if not ok:
                print("⚠️  Fant ikke realistisk timestamp i probe-responsen, men hourly finnes.")
            if args.out:
                out_path = _norm_env_path(args.out, data_dir)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                print(f"💾 Lagret forecast til: {os.path.abspath(out_path)}")
            print("✅ Probe-forecast OK.")
            sys.exit(0)
        except requests.HTTPError as e:
            print(f"❌ Forecast HTTP-feil: {e.response.status_code} {e.response.text[:500]}", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"❌ Forecast feilet: {e}", file=sys.stderr)
            sys.exit(2)

    # Ellers: valider eksisterende værfil (som før)
    if args.weather:
        weather_path = _norm_env_path(args.weather, data_dir)
    else:
        latest = _latest_weather_file(data_dir)
        if not latest:
            print("❌ Fant ingen *_weather.json i data/.", file=sys.stderr)
            sys.exit(1)
        weather_path = latest

    weather_path = os.path.abspath(weather_path)
    if DEBUG:
        print(f"[DBG] Weather file: {weather_path}")

    if not os.path.exists(weather_path):
        print(f"❌ Værfil finnes ikke: {weather_path}", file=sys.stderr)
        sys.exit(1)

    try:
        data = _load_json(weather_path)
    except Exception as e:
        print(f"❌ Klarte ikke å lese JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        hourly = _get_hourly(data)
        idxs = _iter_indices(hourly)
        if not idxs:
            raise RuntimeError("Ingen timeserier i weather JSON (hourly).")
        total = len(idxs)
        # finn første realistiske
        ok = False
        for i in idxs:
            ctx, ts = _collect_ctx(hourly, i)
            if _is_complete(ctx) and _is_realistic(ctx):
                _print_ctx("✅ Første realistiske", ts, ctx)
                ok = True
                break

        print("📊 Værdata-kvalitet:")
        print(f"  • Timestamps totalt : {total}")
        print(f"  • Realistisk funnet : {'ja' if ok else 'nei'}")

        if ok:
            print("✅ Minst én timestamp har komplette og realistiske verdier.")
            sys.exit(0)
        else:
            print("⚠️  Ingen realistiske timestamps. Vurder å hente på nytt med --probe-forecast.")
            if args.out:
                # hint: prøv å hente og lagre nå
                lat = 59.41721; lon = 10.48343; tz = "Europe/Oslo"
                print("ℹ️  Eksempel probe (Horten): --probe-forecast --lat 59.41721 --lon 10.48343 --tz Europe/Oslo")
            sys.exit(3)

    except Exception as e:
        print(f"❌ Validering feilet: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()