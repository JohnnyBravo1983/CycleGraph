import json

with open("data/session_2025-09-16_weather.json", "r", encoding="utf-8") as f:
    data = json.load(f)

hourly = data.get("hourly", {})
times = hourly.get("time", [])
temps = hourly.get("temperature_2m", [])
humidity = hourly.get("relative_humidity_2m", [])
wind = hourly.get("wind_speed_10m", [])
dir = hourly.get("wind_direction_10m", [])
pressure = hourly.get("surface_pressure", [])

def is_valid(val):
    return isinstance(val, (int, float)) and val != 0

for i, ts in enumerate(times):
    if i >= len(temps) or i >= len(humidity) or i >= len(wind) or i >= len(dir) or i >= len(pressure):
        continue
    if all(map(is_valid, [temps[i], humidity[i], wind[i], dir[i], pressure[i]])):
        print(f"✅ Gyldig timestamp: {ts}")
        print(f"  Temperatur: {temps[i]}")
        print(f"  Luftfuktighet: {humidity[i]}")
        print(f"  Vind: {wind[i]} m/s")
        print(f"  Retning: {dir[i]}°")
        print(f"  Trykk: {pressure[i]} hPa")
        break
else:
    print("⚠️ Fant ingen gyldig timestamp med komplette værdata.")