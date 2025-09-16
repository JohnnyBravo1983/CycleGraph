import argparse
import requests
import os
import json
from datetime import datetime, timedelta

def geocode_location(location):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1"
    response = requests.get(url)
    data = response.json()
    if "results" in data and len(data["results"]) > 0:
        result = data["results"][0]
        return result["latitude"], result["longitude"]
    else:
        raise ValueError(f"Fant ikke koordinater for '{location}'")

def fetch_weather(lat, lon, start, duration):
    start_dt = datetime.fromisoformat(start)
    end_dt = start_dt + timedelta(seconds=duration)
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}"
        f"&start_date={start_dt.date()}&end_date={end_dt.date()}"
        f"&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,surface_pressure"
        f"&timezone=auto"
    )
    response = requests.get(url)
    return response.json()

def save_weather(data, location, start):
    date_str = start.split("T")[0]
    filename = f"weather_{location.lower().replace(',','_').replace(' ','_')}_{date_str}.json"
    path = os.path.join("data", filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Værdata lagret: {path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--location", required=True, help="F.eks. 'Horten,Norway'")
    parser.add_argument("--start", required=True, help="ISO-tidspunkt, f.eks. '2025-09-16T18:00:00'")
    parser.add_argument("--duration", type=int, default=3600, help="Varighet i sekunder")
    args = parser.parse_args()

    try:
        lat, lon = geocode_location(args.location)
        print(f"📍 Koordinater for {args.location}: {lat}, {lon}")
        weather = fetch_weather(lat, lon, args.start, args.duration)
        save_weather(weather, args.location, args.start)
    except Exception as e:
        print(f"❌ Feil: {e}")

if __name__ == "__main__":
    main()