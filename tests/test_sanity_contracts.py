import inspect, subprocess, sys

def test_cli_analyze_session_signature():
    from cli import analyze_session
    assert str(inspect.signature(analyze_session)) == "(watts, hr, device_watts=None)"

def test_python_m_cli_and_sessions_help_work():
    assert subprocess.run([sys.executable, "-m", "cli", "--help"]).returncode == 0
    assert subprocess.run([sys.executable, "-m", "cli", "sessions", "--help"]).returncode == 0
