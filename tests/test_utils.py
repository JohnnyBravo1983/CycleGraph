# tests/test_utils.py
from __future__ import annotations

import csv
import math
import re
import statistics
import subprocess
import sys
import json
from pathlib import Path
from typing import Iterable, List, Dict, Optional, Any


# ------------------------------
# CSV helpers (ingen eksterne deps)
# ------------------------------

def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    """
    Leser en CSV med header og returnerer liste av rader (dict).
    Feiler tydelig hvis fil mangler.
    """
    if not path.exists():
        raise FileNotFoundError(f"Mangler datasett: {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def count_samples(path: Path) -> int:
    """Antall rader i CSV (ekskl. header)."""
    return len(load_csv_rows(path))


def read_numeric_column(path: Path, col: str) -> List[float]:
    """
    Leser numerisk kolonne fra CSV (tillater tomme celler).
    Ikke-numeriske/tomme verdier ignoreres.
    """
    rows = load_csv_rows(path)
    out: List[float] = []
    for r in rows:
        val = (r.get(col) or "").strip()
        if not val:
            continue
        try:
            x = float(val)
        except ValueError:
            continue
        out.append(x)
    return out


# ------------------------------
# Datasettkrav
# ------------------------------

def assert_min_samples(path: Path, min_samples: int = 30) -> None:
    """Asserter at CSV har minst min_samples rader."""
    n = count_samples(path)
    assert n >= min_samples, f"{path} har {n} samples (< {min_samples})."


# ------------------------------
# HR-plausibilitet (HR-only sanity)
# ------------------------------

def no_nan_inf_neg(values: Iterable[float]) -> bool:
    """True hvis ingen NaN/Inf/negative i sekvensen."""
    for v in values:
        if math.isnan(v) or math.isinf(v) or v < 0:
            return False
    return True


def hr_plausibility_basic(
    hr_series: List[float],
    *,
    hr_min: float = 40.0,
    hr_max: float = 220.0,
    require_variation: bool = False,
    min_std_tol: float = 0.5,
) -> None:
    """
    Enkle plausibilitetschecks for HR-only golden:
      - ingen NaN/Inf/negative
      - alle verdier i [hr_min, hr_max]
      - valgfritt krav om minimal variasjon (stddev >= min_std_tol)
    """
    assert hr_series, "Tom HR-serie."
    assert no_nan_inf_neg(hr_series), "HR-serien inneholder NaN/Inf/negativ."

    for v in hr_series:
        assert hr_min <= v <= hr_max, f"Urealistisk HR-verdi: {v}"

    if require_variation and len(hr_series) > 1:
        std = statistics.pstdev(hr_series) if len(hr_series) > 2 else 0.0
        assert std >= min_std_tol, f"HR-serien mangler variasjon (std={std:.3f} < {min_std_tol})."


def pa_hr_value_plausible(
    pa_hr: float,
    *,
    min_ratio: float = 0.9,
    max_ratio: float = 2.5,
) -> None:
    """
    Sjekker at Pa:Hr ligger innenfor et rimelig intervall.
    Merk: Selve Pa:Hr beregnes av kjernen; her validerer vi kun output.
    """
    assert not math.isnan(pa_hr) and not math.isinf(pa_hr), "Pa:Hr er NaN/Inf."
    assert pa_hr >= 0.0, "Pa:Hr kan ikke være negativ."
    assert min_ratio <= pa_hr <= max_ratio, f"Pa:Hr {pa_hr:.3f} utenfor [{min_ratio}, {max_ratio}]."


# ------------------------------
# Nye helpers for TRINN 5
# ------------------------------

def _is_finite_number(x: Any) -> bool:
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return False
    return math.isfinite(xf)


def is_valid_hr(values: Any) -> bool:
    """
    Godtar:
      - enkeltall: 30–230 bpm, finite
      - liste/iterable: alle verdier 30–230 bpm, finite
    """
    def _ok(v: Any) -> bool:
        if not _is_finite_number(v):
            return False
        v = float(v)
        return 30.0 <= v <= 230.0

    if isinstance(values, (int, float)):
        return _ok(values)

    if isinstance(values, Iterable):
        got_any = False
        for v in values:
            if not _ok(v):
                return False
            got_any = True
        return got_any

    return False


def is_reasonable_pa_hr(value: float) -> bool:
    """
    'Rule-of-thumb' intervall for HR-only økter:
      1.0 <= Pa:Hr <= 2.5
    """
    if not _is_finite_number(value):
        return False
    v = float(value)
    return 1.0 <= v <= 2.5


def extract_last_json(text: str) -> dict:
    """
    Finn siste JSON-objekt i stdout (linje-basert + regex fallback).
    """
    candidates = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("{") and ln.strip().endswith("}")]
    for raw in reversed(candidates):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    # fallback: siste {...}-blokk
    m = list(re.finditer(r"\{.*\}", text, flags=re.DOTALL))
    if m:
        try:
            return json.loads(m[-1].group(0))
        except json.JSONDecodeError:
            pass
    raise AssertionError("Fant ikke gyldig JSON i stdout")


def run_cli_on_path(csv_path: Path, extra_args: Optional[List[str]] = None) -> tuple[subprocess.CompletedProcess, dict]:
    """
    Kjører: python -m cli.analyze session --input <csv> --format json --dry-run
    HR-only: ingen --weather, ingen --calibrate.
    Returnerer (proc, siste_json_objekt).
    """
    cmd = [
        sys.executable, "-m", "cli.analyze", "session",
        "--input", str(csv_path),
        "--format", "json",
        "--dry-run",
    ]
    if extra_args:
        cmd.extend(extra_args)

    proc = subprocess.run(cmd, capture_output=True, text=True)
    obj = extract_last_json(proc.stdout or "")
    return proc, obj


def get_metric(data: dict, *keys: str, default: Any = None) -> Any:
    """
    Hent metrikker robust. Prøver både top-level og data.get("metrics", {}).
    keys kan være f.eks. "Pa:Hr" eller "pa_hr".
    """
    metrics = data.get("metrics", {})
    for k in keys:
        if k in metrics:
            return metrics[k]
        if k in data:
            return data[k]
    return default


# ------------------------------
# Semver validering
# ------------------------------

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

def is_semver(s: str) -> bool:
    return bool(SEMVER_RE.match(s or ""))


def assert_semver(s: Optional[str]) -> None:
    assert s is not None and is_semver(s), f"schema_version ugyldig: {s!r} (forventet X.Y.Z)"


# ------------------------------
# Eksisterende CLI-helper (beholdes)
# ------------------------------

def run_cli_json(args: List[str]) -> Dict:
    """
    Kjører CLI og returnerer JSON-objektet.
    Scanner stdout og plukker første gyldige JSON-dokument innebygd i teksten.
    """
    cmd = [sys.executable, "-m", "cli.analyze"] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if proc.returncode != 0:
        raise AssertionError(
            f"CLI feilet (rc={proc.returncode}):\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    decoder = json.JSONDecoder()
    s = proc.stdout

    for i, ch in enumerate(s):
        if ch in "{[":
            try:
                obj, end = decoder.raw_decode(s, i)
                if isinstance(obj, (dict, list)):
                    return obj
            except json.JSONDecodeError:
                continue

    # hvis vi kom hit, fant vi ikke gyldig JSON
    raise AssertionError(
        "CLI returnerte ikke gyldig JSON i stdout.\n"
        f"FULL STDOUT:\n{s}\n\nSTDERR:\n{proc.stderr}"
    )


# ------------------------------
# HR-only fallbacks (for tester)
# ------------------------------

def get_hr_values_from_csv(path: Path) -> list[float]:
    """
    Leser HR-serien fra CSV. Tåler kolonnenavn:
    hr, heartrate, heart_rate, bpm, pulse.
    Ignorerer tomme/ikke-numeriske rader.
    """
    rows = load_csv_rows(path)
    if not rows:
        return []
    # map header -> original
    fieldnames = list(rows[0].keys())
    name_map = {(h or "").strip().lower(): h for h in fieldnames}
    for key in ("hr", "heartrate", "heart_rate", "bpm", "pulse"):
        if key in name_map:
            col = name_map[key]
            break
    else:
        return []

    out: list[float] = []
    for r in rows:
        raw = (r.get(col) or "").strip()
        if not raw:
            continue
        try:
            v = float(raw)
        except ValueError:
            continue
        out.append(v)
    return out


def compute_pa_hr_from_series(hr_series: list[float]) -> Optional[float]:
    """
    Enkel HR-only 'Pa:Hr'-approks: mean(last 25%) / mean(first 25%).
    Returnerer None hvis for få samples.
    """
    n = len(hr_series)
    if n < 8:
        return None
    q = max(1, n // 4)
    first = hr_series[:q]
    last = hr_series[-q:]
    m1 = sum(first) / len(first) if first else 0.0
    m2 = sum(last) / len(last) if last else 0.0
    if m1 <= 0.0 or not math.isfinite(m1) or not math.isfinite(m2):
        return None
    ratio = m2 / m1
    if not math.isfinite(ratio):
        return None
    return ratio


def compute_avg_hr(hr_series: list[float]) -> Optional[float]:
    """
    Gjennomsnittlig HR (float) eller None ved tom serie.
    """
    if not hr_series:
        return None
    return float(sum(hr_series) / len(hr_series))