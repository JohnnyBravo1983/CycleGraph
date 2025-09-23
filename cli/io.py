# cli/io.py
from __future__ import annotations

import csv
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# ----------------------------
# Delimiter & utils
# ----------------------------
def _detect_delimiter(sample: str) -> str:
    # enkel heuristikk før Sniffer (som kan feile på små filer)
    if ";" in sample and "," not in sample:
        return ";"
    if "," in sample and ";" not in sample:
        return ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        return dialect.delimiter
    except Exception:
        return ","

def _to_float(x) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def _norm_headers(fieldnames: Optional[List[str]]) -> Dict[str, str]:
    return {(h or "").lower().strip(): h for h in (fieldnames or [])}

def _pick(row: Dict[str, Any], field_map: Dict[str, str], keys: tuple[str, ...]):
    for k in keys:
        if k in field_map:
            v = row.get(field_map[k])
            if v is not None and v != "":
                return v
    return None

# ----------------------------
# Session CSV (for analyze session)
# ----------------------------
def read_session_csv(path: str, debug: bool = False) -> List[Dict[str, Any]]:
    """
    Leser CSV og returnerer liste av dict med normaliserte nøkler:
      - 't' (sekunder eller timestamp-string)
      - 'watts' (float eller None)
      - 'hr' (float eller None)
    Godtar typiske alias for kraft/puls/tid.
    """
    if not os.path.exists(path):
        if debug:
            print(f"DEBUG: {path} finnes ikke", file=sys.stderr)
        return []

    with open(path, "r", encoding="utf-8") as f:
        head = f.read(2048)
    delim = _detect_delimiter(head)
    if debug:
        print(f"DEBUG: {path} delimiter='{delim}'", file=sys.stderr)

    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delim)
        field_map = _norm_headers(reader.fieldnames)
        if debug:
            print(f"DEBUG: headers_norm={list(field_map.keys())}", file=sys.stderr)

        time_keys = ("t", "time", "timestamp", "date", "datetime")
        power_keys = ("watts", "watt", "power", "power_w", "pwr")
        hr_keys = ("hr", "heartrate", "heart_rate", "bpm", "pulse")

        idx = 0
        for raw in reader:
            t_val = _pick(raw, field_map, time_keys)
            if t_val is None:
                t = idx
            else:
                try:
                    t = float(t_val)
                except Exception:
                    t = str(t_val)

            pw = _to_float(_pick(raw, field_map, power_keys))
            hr = _to_float(_pick(raw, field_map, hr_keys))

            rows.append({"t": t, "watts": pw, "hr": hr})
            idx += 1

    if debug:
        total = len(rows)
        have_pw = sum(1 for r in rows if isinstance(r.get("watts"), (int, float)))
        have_hr = sum(1 for r in rows if isinstance(r.get("hr"), (int, float)))
        both = sum(1 for r in rows if isinstance(r.get("watts"), (int, float)) and isinstance(r.get("hr"), (int, float)))
        print(
            f"DEBUG: read {total} rows from {path}; with_watts={have_pw} with_hr={have_hr} with_both={both}",
            file=sys.stderr
        )
        if rows:
            print(f"DEBUG: first_row_norm={rows[0]}", file=sys.stderr)

    return rows

# ----------------------------
# Efficiency CSV (for efficiency subcommand)
# Gir power[], hr[], hz
# ----------------------------
def read_efficiency_csv(path: str, debug: bool = False) -> Tuple[List[float], List[float], float]:
    """
    Leser en CSV med minst (time|timestamp|t), (watt|watts|power|pwr), (hr|heartrate|heart_rate|bpm|pulse).
    Returnerer (power_list, hr_list, hz).
    hz anslås fra tidsstempler (sekunder) – fallback 1.0.
    """
    if not os.path.exists(path):
        if debug:
            print(f"DEBUG: {path} finnes ikke", file=sys.stderr)
        return [], [], 1.0

    with open(path, "r", encoding="utf-8") as f:
        head = f.read(2048)
    delim = _detect_delimiter(head)
    if debug:
        print(f"DEBUG[eff]: {path} delimiter='{delim}'", file=sys.stderr)

    times: List[float] = []
    power: List[float] = []
    hr: List[float] = []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delim)
        field_map = _norm_headers(reader.fieldnames)
        if debug:
            print(f"DEBUG[eff]: headers_norm={list(field_map.keys())}", file=sys.stderr)

        time_keys = ("t", "time", "timestamp", "sec", "seconds")
        power_keys = ("watts", "watt", "power", "power_w", "pwr")
        hr_keys = ("hr", "heartrate", "heart_rate", "bpm", "pulse")

        idx = 0
        for raw in reader:
            t_val = _pick(raw, field_map, time_keys)
            if t_val is None:
                t = float(idx)
            else:
                try:
                    t = float(str(t_val).replace(",", "."))
                except Exception:
                    # forsøk å parse ISO-timestamp → la som indeks hvis ikke
                    t = float(idx)

            pw = _to_float(_pick(raw, field_map, power_keys))
            h = _to_float(_pick(raw, field_map, hr_keys))

            if pw is None or h is None:
                idx += 1
                continue

            times.append(t)
            power.append(float(pw))
            hr.append(float(h))
            idx += 1

    # estimer hz fra tidsdifferanser (sekunder)
    hz = 1.0
    if len(times) >= 3:
        diffs = []
        for i in range(1, len(times)):
            dt = times[i] - times[i-1]
            if dt > 0:
                diffs.append(dt)
        if diffs:
            diffs_sorted = sorted(diffs)
            mid = len(diffs_sorted)//2
            med_dt = diffs_sorted[mid] if len(diffs_sorted) % 2 == 1 else (diffs_sorted[mid-1] + diffs_sorted[mid]) / 2.0
            if med_dt > 0:
                hz = float(round(1.0 / med_dt, 3))

    if debug:
        print(
            f"DEBUG[eff]: rows={len(power)} hz≈{hz} sample0="
            f"{ {'t': times[0], 'watts': power[0], 'hr': hr[0]} if power and hr else None }",
            file=sys.stderr
        )

    return power, hr, hz