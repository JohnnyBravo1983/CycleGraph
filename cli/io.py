from typing import List, Dict, Any

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


