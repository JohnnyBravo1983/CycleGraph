from pathlib import Path
import json, re

def _latest_export_dir() -> Path:
    base = Path("export")
    dates = [p for p in base.glob("*") if p.is_dir() and re.fullmatch(r"\d{8}", p.name)]
    assert dates, "No dated export folders under export/"
    return sorted(dates, key=lambda p: p.stat().st_mtime, reverse=True)[0]

def test_sessions_jsonl_exists_and_shape():
    d = _latest_export_dir()
    f = d / "sessions.jsonl"
    assert f.exists(), f"Missing {f}"
    lines = f.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 5, f"Need >=5 lines, got {len(lines)}"
    for ln in lines:
        j = json.loads(ln)
        # top-level
        for k in ("ride_id","profile_version","weather_source","metrics"):
            assert k in j, f"missing {k}"
        m = j["metrics"]
        for k in ("precision_watt","drag_watt","rolling_watt","total_watt","calibration_mae","weather_source"):
            assert k in m, f"metrics missing {k}"
        # basic numeric sanity (allow 0 for now, but not None except MAE)
        for k in ("precision_watt","drag_watt","rolling_watt","total_watt"):
            assert m[k] is not None, f"{k} is None"
        # profile_used present + version mirror
        assert "profile_used" in j and isinstance(j["profile_used"], dict)
        assert j["profile_used"].get("profile_version") == j["profile_version"]
