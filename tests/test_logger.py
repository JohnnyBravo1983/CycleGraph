# tests/test_logger.py
import json
import os
import subprocess
import sys
from typing import List, Tuple, Dict, Any, Optional

INPUT_CSV = os.path.join("tests", "test_golden_segment.csv")

def _parse_json_logs(stderr_text: str) -> List[Dict[str, Any]]:
    """Plukk ut JSON-linjer fra stderr og parse dem til dicts (ignorerer ikke-JSON)."""
    logs = []
    for line in stderr_text.splitlines():
        line = line.strip()
        if not line.startswith("{") or not line.endswith("}"):
            continue
        try:
            obj = json.loads(line)
            # kun linjer som ser ut som logger-records (har 'level' og 'step' eller 'metric')
            if isinstance(obj, dict) and ("level" in obj) and ("step" in obj or "metric" in obj):
                logs.append(obj)
        except Exception:
            continue
    return logs

def _run_cli(log_level_flag: Optional[str] = None, env_level: Optional[str] = None) -> Tuple[str, str, List[Dict[str, Any]]]:
    """Kjør CLI og returner (stdout, stderr, parsed_json_logs)."""
    cmd = [
        sys.executable, "-m", "cli.analyze",
        "session",
        "--input", INPUT_CSV,
        "--format", "json",
        "--dry-run",
        "--debug",
    ]
    if log_level_flag:
        cmd += ["--log-level", log_level_flag]

    env = os.environ.copy()
    if env_level is not None:
        env["LOG_LEVEL"] = env_level
    else:
        # Sørg for at eksisterende env ikke påvirker testen
        env.pop("LOG_LEVEL", None)

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, f"CLI returnerte {proc.returncode}\nSTDERR:\n{proc.stderr}"
    logs = _parse_json_logs(proc.stderr)
    return proc.stdout, proc.stderr, logs

def test_log_fields_and_cachehit_and_component_at_info():
    """
    Logger skal inneholde:
    - INFO-linjer med 'step'
    - 'compute_power_with_wind' med 'cache_hit' (True/False)
    - metrikklinje for 'sessions_no_power_total' med 'component' og 'value':1
    """
    out, err, logs = _run_cli(log_level_flag="info")

    assert any(l.get("level") == "INFO" and "step" in l for l in logs), "Fant ingen INFO-linjer med 'step'."

    cpw = [l for l in logs if l.get("step") == "compute_power_with_wind"]
    assert cpw, f"Mangler logg for step='compute_power_with_wind'.\nAlle logger:\n{logs}"
    assert any("cache_hit" in l for l in cpw), "compute_power_with_wind mangler 'cache_hit'."

    metric_lines = [l for l in logs if l.get("metric") == "sessions_no_power_total"]
    assert metric_lines, "Mangler metrikklinje for 'sessions_no_power_total'."
    assert any(l.get("value") == 1 for l in metric_lines), "sessions_no_power_total skal ha value=1."
    assert any(l.get("component") == "cli/session" for l in metric_lines), "Mangler 'component' på metrikklinje."

def test_log_level_control_via_flag_and_env():
    """
    Prioritet: --log-level > LOG_LEVEL.
    - Når LOG_LEVEL=warning (uten flagg) -> INFO skal filtreres bort.
    - Når LOG_LEVEL=warning og --log-level info -> INFO skal komme gjennom.
    - Når LOG_LEVEL=debug men --log-level warning -> INFO skal filtreres bort.
    """
    # 1) Kun env: warning -> ingen INFO
    _, _, logs_env_warning = _run_cli(env_level="warning")
    assert not any(l.get("level") == "INFO" for l in logs_env_warning), \
        f"INFO-linjer skulle vært filtrert bort når LOG_LEVEL=warning.\n{logs_env_warning}"

    # 2) Env: warning, men flagg: info -> INFO skal være med
    _, _, logs_flag_info = _run_cli(log_level_flag="info", env_level="warning")
    assert any(l.get("level") == "INFO" for l in logs_flag_info), \
        "INFO-linjer mangler når --log-level info skal overstyre LOG_LEVEL=warning."

    # 3) Env: debug, men flagg: warning -> INFO skal bort
    _, _, logs_flag_warning = _run_cli(log_level_flag="warning", env_level="debug")
    assert not any(l.get("level") == "INFO" for l in logs_flag_warning), \
        "INFO-linjer skulle vært filtrert bort når --log-level warning overstyrer LOG_LEVEL=debug."