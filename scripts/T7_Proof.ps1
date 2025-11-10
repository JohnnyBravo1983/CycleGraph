# scripts/T7_Proof.ps1  (ASCII-safe, no BOM)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

param([string]$OutDir = "logs")

# 1) Ensure output dir
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# 2) Write temp Python verifier
$PyPath = Join-Path $env:TEMP "trinn7_proof.py"
$PyCode = @'
import os, json, glob

def latest_json(path="logs"):
    files = sorted(glob.glob(os.path.join(path, "trinn7-observability_*.json")), key=os.path.getmtime)
    return files[-1] if files else None

def read_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

out = {"ok": False, "missing": [], "bad_types": [], "csv_ok": False, "csv_tail": "", "error": None, "json_file": None}

try:
    jfile = latest_json()
    if not jfile:
        out["error"] = "No JSON logs found"
    else:
        out["json_file"] = os.path.basename(jfile)
        data = read_json(jfile)
        m = data.get("metrics") or {}
        p = (m.get("profile_used") or {})
        dbg = data.get("debug") or {}

        required = [
            "precision_watt","total_watt","weather_applied","crank_eff_pct",
            "calibration_mae","calibrated","calibration_status",
            "source","repr_kind","profile_version","debug_reason"
        ]

        for f in required:
            val = None
            if f in ("precision_watt","total_watt","calibration_mae","calibrated","calibration_status"):
                val = m.get(f)
            elif f in ("crank_eff_pct","profile_version"):
                val = p.get(f)
            elif f == "debug_reason":
                val = dbg.get("reason")
            else:
                val = data.get(f)
            if val is None:
                out["missing"].append(f)

        if not out["missing"]:
            out["ok"] = True

        def type_ok(v, types): return any(isinstance(v, t) for t in types)
        checks = {
            "precision_watt": (m.get("precision_watt"), (int,float)),
            "total_watt": (m.get("total_watt"), (int,float)),
            "weather_applied": (data.get("weather_applied"), (bool,)),
            "calibrated": (m.get("calibrated"), (bool,))
        }
        for k, (v, tps) in checks.items():
            if not type_ok(v, tps):
                out["bad_types"].append(k)

        csv_path = os.path.join("logs","trinn7-observability.csv")
        if os.path.exists(csv_path):
            out["csv_ok"] = True
            try:
                with open(csv_path, encoding="utf-8") as f:
                    lines = f.read().strip().splitlines()
                    out["csv_tail"] = lines[-1] if lines else ""
            except Exception as e:
                out["csv_tail"] = str(e)
except Exception as e:
    out["error"] = str(e)

print("JSON:" + json.dumps(out, ensure_ascii=False))
'@
Set-Content -Path $PyPath -Value $PyCode -Encoding UTF8

# 3) Run Python and parse the single JSON line
$pyOut = python "$PyPath"
$jsonLine = $pyOut | Where-Object { $_ -like 'JSON:*' } | Select-Object -Last 1
if (-not $jsonLine) {
  Write-Host "ERROR: Missing JSON line from Python. Full output follows:"
  Write-Host $pyOut
  exit 1
}
$result = $jsonLine.Substring(5) | ConvertFrom-Json

# 4) Evaluate result
if ($result.error) {
  Write-Host ("ERROR: " + $result.error)
  exit 1
}

if ($result.ok -and $result.bad_types.Count -eq 0) {
  Write-Host ("OK: All required fields present and types look correct. File=" + $result.json_file)
} elseif ($result.ok) {
  Write-Host ("WARN: Fields present but type issues for: " + ($result.bad_types -join ', ') + ". File=" + $result.json_file)
} else {
  Write-Host ("WARN: Missing fields: " + ($result.missing -join ', ') + ". File=" + $result.json_file)
}

if ($result.csv_ok) {
  Write-Host "OK: CSV present. Last row:"
  Write-Host $result.csv_tail
} else {
  Write-Host "ERROR: CSV not found in logs/"
  exit 1
}

Write-Host "=== Trinn 7 Proof done ==="