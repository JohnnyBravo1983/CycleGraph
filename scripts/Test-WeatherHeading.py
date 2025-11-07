# -------------------------------------------------------------
# Test-WeatherHeading.py
# Formål: Teste heading-beregning fra ride-data (lat/lon -> heading_deg)
# -------------------------------------------------------------
import pandas as pd
import numpy as np
from math import atan2, degrees
import json
import os

# -------------------------------------------------------------
# 1) Konfigurasjon
# -------------------------------------------------------------
# Her kan du bytte til en faktisk ride-fil senere (eks. data/session_x.json)
TEST_FILE = "testdata/ride_sample.json"

# -------------------------------------------------------------
# 2) Dummydata (hvis ingen fil finnes)
# -------------------------------------------------------------
if not os.path.exists(TEST_FILE):
    print(f"[INFO] Fant ikke {TEST_FILE}, bruker dummydata.")
    data = [
        {"t": 0.0,  "lat_deg": 59.0,      "lon_deg": 10.0,      "v_ms": 0.0},
        {"t": 1.0,  "lat_deg": 59.00005,  "lon_deg": 10.00010,  "v_ms": 5.8},
        {"t": 2.0,  "lat_deg": 59.00010,  "lon_deg": 10.00020,  "v_ms": 5.6},
        {"t": 3.0,  "lat_deg": 59.00020,  "lon_deg": 10.00035,  "v_ms": 5.3},
        {"t": 4.0,  "lat_deg": 59.00030,  "lon_deg": 10.00050,  "v_ms": 5.1},
        {"t": 5.0,  "lat_deg": 59.00045,  "lon_deg": 10.00070,  "v_ms": 4.8},
    ]
else:
    with open(TEST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

df = pd.DataFrame(data)

# -------------------------------------------------------------
# 3) Heading-beregning
# -------------------------------------------------------------
def calculate_heading(lat1, lon1, lat2, lon2):
    """Returnerer heading (grader 0–360) mellom to punkter."""
    d_lon = np.radians(lon2 - lon1)
    y = np.sin(d_lon) * np.cos(np.radians(lat2))
    x = (np.cos(np.radians(lat1)) * np.sin(np.radians(lat2)) -
         np.sin(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.cos(d_lon))
    brng = np.degrees(np.arctan2(y, x))
    return (brng + 360) % 360

df["heading_deg"] = np.nan
for i in range(1, len(df)):
    df.loc[i, "heading_deg"] = calculate_heading(
        df.loc[i - 1, "lat_deg"], df.loc[i - 1, "lon_deg"],
        df.loc[i, "lat_deg"], df.loc[i, "lon_deg"]
    )
df["heading_deg"] = df["heading_deg"].fillna(method="ffill")

# -------------------------------------------------------------
# 4) Resultatvisning
# -------------------------------------------------------------
print(df[["t", "v_ms", "heading_deg"]].to_string(index=False))

# -------------------------------------------------------------
# 5) Validering
# -------------------------------------------------------------
n_nan = df["heading_deg"].isna().sum()
outside = df[(df["heading_deg"] < 0) | (df["heading_deg"] > 360)]

print(f"\n[CHECK] heading_deg NaN: {n_nan}/{len(df)}")
print(f"[CHECK] heading_deg utenfor 0–360: {len(outside)}")
if n_nan == 0 and len(outside) == 0:
    print("[OK] Alle heading-verdier er gyldige.")
    print(df["heading_deg"].describe())
else:
    print("[WARN] Fant ugyldige verdier:")
    print(outside.head())