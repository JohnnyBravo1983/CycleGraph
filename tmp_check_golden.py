from pathlib import Path
from tests.test_utils import count_samples

files = [
    Path("tests/data/golden_indoor.csv"),
    Path("tests/data/golden_outdoor.csv"),
    Path("tests/data/golden_hr_only.csv"),
]
for f in files:
    n = count_samples(f)
    print(f"{f}: {n} samples")
    assert n >= 30, f"{f} has only {n} samples"
print("OK: All golden datasets have ≥30 samples.")