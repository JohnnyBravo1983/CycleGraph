# tests/test_utils.py
from __future__ import annotations

import csv
import math
import re
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Dict, Optional


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
            # Ignorer åpenbart ikke-numerisk
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

    Reiser AssertionError ved brudd.
    """
    assert hr_series, "Tom HR-serie."
    assert no_nan_inf_neg(hr_series), "HR-serien inneholder NaN/Inf/negativ."

    for v in hr_series:
        assert hr_min <= v <= hr_max, f"Urealistisk HR-verdi: {v}"

    if require_variation and len(hr_series) > 1:
        # Robust stddev: tåler konstante serier
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
# Semver validering
# ------------------------------

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

def is_semver(s: str) -> bool:
    return bool(SEMVER_RE.match(s or ""))


def assert_semver(s: Optional[str]) -> None:
    assert s is not None and is_semver(s), f"schema_version ugyldig: {s!r} (forventet X.Y.Z)"


# ------------------------------
# Valgfri CLI-helper (kan brukes i tester)
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

    import json
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

    raise AssertionError(
        "CLI returnerte ikke gyldig JSON i stdout.\n"
        f"FULL STDOUT:\n{s}\n\nSTDERR:\n{proc.stderr}"
    )