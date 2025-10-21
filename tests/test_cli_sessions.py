import json, sys
from pathlib import Path
from click.testing import CliRunner
import importlib

# Pek til repo-roten slik at 'import cli' funker
REPO_ROOT = Path(r"C:\Users\easy2\OneDrive\Skrivebord\Archieve\Karriere\CycleGraph")

def write_row(session_id: str, **metrics):
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "schema_version": "0.7.3",
        "session_id": session_id,
        "saved_at": "2025-10-18T10:00:00Z",
        "metrics": {
            "precision_watt": metrics.get("precision_watt"),
            "precision_watt_ci": metrics.get("precision_watt_ci"),
            "publish_state": metrics.get("publish_state", "draft"),
            "publish_time": metrics.get("publish_time"),
            "crr_used": metrics.get("crr_used"),
            "CdA": metrics.get("CdA"),
            "reason": metrics.get("reason"),
        },
        "profile": {
            "consent_accepted": True,
            "consent_version": "1.0",
            "consent_time": "2025-10-01T12:00:00Z",
            "bike_name": "AeroX",
        },
    }
    with open(data_dir / "session_metrics.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")

def test_cli_sessions_list():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Sørg for at repo-roten er på sys.path (for import cli)
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))

        # Dropp eventuelle tidligere imports slik at DATA_DIR bindes til *isolert* cwd
        for mod in ("cli.session_storage", "cli.session", "cli"):
            sys.modules.pop(mod, None)

        # Importer cli først NÅ (etter vi er inne i isolert FS)
        from cli import cli as app

        # Skriv testdata i denne (isolerte) cwd
        Path("data").mkdir(parents=True, exist_ok=True)
        write_row(
            "S1",
            precision_watt=255.3,
            precision_watt_ci=[240.0, 270.0],
            publish_state="draft",
            crr_used=0.004,
            CdA=0.28,
            reason="baseline",
        )
        write_row(
            "S2",
            precision_watt=None,
            precision_watt_ci=None,
            publish_state="published",
            publish_time="2025-10-18T11:00:00Z",
        )

        # Kjør CLI direkte i-prosess
        result = runner.invoke(app, ["sessions", "list", "--limit", "2"])
        # Debug ved behov:
        # print("EXIT:", result.exit_code)
        # print("OUTPUT:\n", result.output)

        assert result.exit_code == 0
        out = result.output
        assert "S2" in out and "published" in out
        assert "S1" in out and "255.3" in out and "0.28" in out
