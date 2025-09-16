#!/usr/bin/env python3
import csv
import os
import sys
import json
from typing import Optional

# Valgfri import av vær-loader
try:
    from weather_metrics import load_weather_context  # forventer dict/dataklasse
except ImportError:
    load_weather_context = None

# Valgfri Rust-FFI
try:
    from rust_bindings import adjusted_efficiency as rs_adjusted_efficiency  # (watt, hr, weather_dict)
except ImportError:
    rs_adjusted_efficiency = None


# --- Debug toggle (miljøvariabel eller flagg i argv) ---
DEBUG_WEATHER = os.environ.get("CG_DEBUG_WEATHER") == "1" or "--debug-weather" in sys.argv


def project_paths():
    script_path = os.path.abspath(__file__)
    cli_dir = os.path.dirname(script_path)
    project_root = os.path.dirname(cli_dir)
    data_dir = os.path.join(project_root, "data")
    input_path = os.path.join(data_dir, "strava_ride_clean.csv")
    watts_only_path = os.path.join(data_dir, "strava_ride_watts_only.csv")
    return input_path, watts_only_path

def _resolve_data_dir() -> str:
    script_path = os.path.abspath(__file__)
    cli_dir = os.path.dirname(script_path)
    project_root = os.path.dirname(cli_dir)
    return os.path.join(project_root, "data")

def _is_nonempty(s: Optional[str]) -> bool:
    return s is not None and str(s).strip() != ""

def _infer_activity_id(row: dict) -> Optional[str]:
    cand = row.get("activity_id") or row.get("activityId")
    if not _is_nonempty(cand):
        return None
    return str(cand).strip()

def _find_weather_json(data_dir: str, activity_id: Optional[str]) -> Optional[str]:
    # 1) Match på aktivitets-ID
    if activity_id:
        p = os.path.join(data_dir, f"{activity_id}_weather.json")
        if os.path.exists(p):
            return p
    # 2) Fallback: nyeste *_weather.json i data/
    try:
        candidates = [
            os.path.join(data_dir, f) for f in os.listdir(data_dir)
            if f.endswith("_weather.json")
        ]
        if candidates:
            return max(candidates, key=os.path.getmtime)
    except FileNotFoundError:
        pass
    return None

def _ensure_weather_ctx(weather_json_path: str) -> dict:
    """
    Gir et plain dict med feltene:
    temperature, humidity, wind_speed, wind_direction, pressure
    """
    if load_weather_context is not None:
        ctx = load_weather_context(weather_json_path)
        if hasattr(ctx, "__dict__"):
            ctx = ctx.__dict__
        weather = {
            "temperature": float(ctx["temperature"]),
            "humidity": float(ctx["humidity"]),
            "wind_speed": float(ctx["wind_speed"]),
            "wind_direction": float(ctx["wind_direction"]),
            "pressure": float(ctx["pressure"]),
        }
    else:
        with open(weather_json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        weather = {
            "temperature": float(raw["temperature"]),
            "humidity": float(raw["humidity"]),
            "wind_speed": float(raw["wind_speed"]),
            "wind_direction": float(raw["wind_direction"]),
            "pressure": float(raw["pressure"]),
        }

    # Debug/verifikasjon: ingen None-verdier
    for k, v in weather.items():
        if v is None:
            raise ValueError(f"Weather field '{k}' is None")
    return weather

def _python_adjusted_efficiency(watt: float, hr: float, weather: dict) -> float:
    """
    Python-speiling av Rust-implementasjonen:
    - humidity > 80%  => *0.95
    - temperature > 25 => *0.97
    - pressure < 1000  => *0.98
    """
    if hr <= 0:
        return 0.0
    factor = 1.0
    if weather["humidity"] > 80.0:
        factor *= 0.95
    if weather["temperature"] > 25.0:
        factor *= 0.97
    if weather["pressure"] < 1000.0:
        factor *= 0.98
    return (watt / hr) * factor


def main():
    input_path, watts_only_path = project_paths()

    # --- Overstyr input/ weather via miljøvariabler for enkel debugging ---
    data_dir = _resolve_data_dir()
    env_input = os.environ.get("CG_INPUT")
    if env_input:
      # bruk absolutt sti hvis gitt, ellers relativt til data/
      input_path = os.path.abspath(env_input) if os.path.isabs(env_input) else os.path.join(data_dir, env_input)

    env_weather = os.environ.get("CG_WEATHER")
    explicit_weather_path = None
    if env_weather:
      explicit_weather_path = os.path.abspath(env_weather) if os.path.isabs(env_weather) else os.path.join(data_dir, env_weather)

    if not os.path.exists(input_path):
        sys.stderr.write(f"❌ Fant ikke inputfilen: {os.path.abspath(input_path)}\n")
        sys.exit(1)

    only_hr = 0
    only_watts = 0
    both = 0
    none = 0
    watts_rows = []

    # Aggregater for værjustert effektivitet
    sum_watts_both = 0.0
    sum_hr_both = 0.0
    n_both_for_eff = 0
    first_activity_id: Optional[str] = None

    if DEBUG_WEATHER:
        print(f"[DBG] Input CSV: {input_path}")
        if explicit_weather_path:
            print(f"[DBG] Weather override: {explicit_weather_path}")

    with open(input_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            sys.stderr.write("❌ Fant ingen kolonneheader i CSV.\n")
            sys.exit(2)

        fieldnames = reader.fieldnames
        for row in reader:
            has_hr = _is_nonempty(row.get("hr"))
            has_watts = _is_nonempty(row.get("watts"))

            # Ta vare på en activity_id (første vi ser)
            if first_activity_id is None:
                aid = _infer_activity_id(row)
                if aid:
                    first_activity_id = aid

            if has_hr and has_watts:
                both += 1
                # Samle til snitt for w/beat
                try:
                    w = float(str(row.get("watts")).strip())
                    h = float(str(row.get("hr")).strip())
                    if h > 0:
                        sum_watts_both += w
                        sum_hr_both += h
                        n_both_for_eff += 1
                except (TypeError, ValueError):
                    pass
            elif has_hr and not has_watts:
                only_hr += 1
            elif has_watts and not has_hr:
                only_watts += 1
                watts_rows.append(row)
            else:
                none += 1

    # 📋 Skriv rapport
    print("📊 Data-tilstedeværelse i filen:")
    print(f"  • Begge hr+watts : {both}")
    print(f"  • Kun hr         : {only_hr}")
    print(f"  • Kun watts      : {only_watts}")
    print(f"  • Ingen av delene: {none}")

    # 📌 Foreslå neste steg
    if both == 0 and only_watts < 100 and only_hr < 100:
        print("\n⚠️  Ingen nok data til analyse. Vurder å hente en annen økt med sensordata.")
    elif both == 0 and only_watts >= 100:
        print("\nℹ️  Ingen kombinerte data, men mange watt-verdier — kan kjøre watt-effekt analyse.")
    elif both == 0 and only_hr >= 100:
        print("\nℹ️  Ingen kombinerte data, men mange pulsverdier — kan kjøre puls-basert analyse.")
    else:
        print("\n✅ Det finnes kombinerte data — bruk filter_valid_rows.py og kjør vanlig CLI-analyse.")

    # 🎁 Bonus: lag watts-only-fil hvis nok data
    if only_watts >= 100:
        os.makedirs(os.path.dirname(watts_only_path), exist_ok=True)
        with open(watts_only_path, "w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(watts_rows)
        print(f"💾 Watts-only fil lagret: {os.path.abspath(watts_only_path)}")

    # ⚡ Værbasert justert watt/puls-effektivitet (debug-steg)
    if n_both_for_eff > 0:
        avg_w = sum_watts_both / n_both_for_eff
        avg_hr = sum_hr_both / n_both_for_eff

        # Velg weather-fil: eksplisitt (CG_WEATHER) > match via activity_id > fallback nyeste
        if explicit_weather_path and os.path.exists(explicit_weather_path):
            weather_json = explicit_weather_path
        else:
            weather_json = _find_weather_json(_resolve_data_dir(), first_activity_id)

        if weather_json and os.path.exists(weather_json):
            try:
                weather_ctx = _ensure_weather_ctx(weather_json)

                # Debug: vis værdata, rå w/hr
                if DEBUG_WEATHER:
                    print("Weather context:", weather_ctx)
                    try:
                        raw_ratio = avg_w / avg_hr if avg_hr > 0 else 0.0
                    except Exception:
                        raw_ratio = "n/a"
                    print("Raw watt/hr:", raw_ratio)

                # Kall Rust-FFI om tilgjengelig, ellers fallback
                if rs_adjusted_efficiency is not None:
                    eff = float(rs_adjusted_efficiency(avg_w, avg_hr, weather_ctx))
                else:
                    eff = _python_adjusted_efficiency(avg_w, avg_hr, weather_ctx)

                if DEBUG_WEATHER:
                    print("Adjusted:", eff)

                # Endelig rapportlinje
                print(f"⚡ Justert watt/puls-effektivitet: {eff:.2f} (basert på værforhold)")

            except Exception as e:
                print(f"ℹ️  Klarte ikke å beregne værjustert effektivitet ({weather_json}): {e}")
        else:
            print("ℹ️  Værdata ikke funnet – hopper over værbasert effektivitet.")

if __name__ == "__main__":
    main()