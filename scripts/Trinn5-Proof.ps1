param([string]$OutDir = "logs")

# 1) Lag output-katalog
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# 2) Skriv et midlertidig Python-skript til %TEMP%
$PyPath = Join-Path $env:TEMP "trinn5_proof.py"
$PyCode = @'
import json, importlib, sys, os
sys.path.insert(0, os.getcwd())
from fastapi.testclient import TestClient

# Start API i miniklient
m = importlib.import_module("server.routes.sessions")
try:
    app = importlib.import_module("server.main").app
except Exception:
    from fastapi import FastAPI
    app = FastAPI(); app.include_router(m.router)
c = TestClient(app)

cases = [
  {"name":"baseline","cda":0.30,"crr":0.004,"w":78.0,"eff":95.5},
  {"name":"cda_up", "cda":0.32,"crr":0.004,"w":78.0,"eff":95.5},
  {"name":"crr_up", "cda":0.30,"crr":0.006,"w":78.0,"eff":95.5},
  {"name":"w_up",   "cda":0.30,"crr":0.004,"w":90.0,"eff":95.5},
  {"name":"eff_dn", "cda":0.30,"crr":0.004,"w":78.0,"eff":92.0},
]

rows = []
for cs in cases:
    profile = {"cda":cs["cda"],"crr":cs["crr"],"weight_kg":cs["w"],"crank_eff_pct":cs["eff"]}
    payload = {
        "samples":[
            {"t":0,"v_ms":10.0,"altitude_m":0.0,"moving":True},
            {"t":1,"v_ms":10.0,"altitude_m":0.1,"moving":True}
        ],
        "profile":profile,
        "weather":None
    }
    j = c.post("/api/sessions/proof/analyze", json=payload).json()
    mtr = j.get("metrics",{})
    rows.append({
        "name": cs["name"],
        "drag": mtr.get("drag_watt"),
        "roll": mtr.get("rolling_watt"),
        "prec": mtr.get("precision_watt"),
        "device": (mtr.get("profile_used") or {}).get("device"),
    })

# Viktig: skriv KUN én linje som starter med 'JSON:' slik at PowerShell kan filtrere
print("JSON:" + json.dumps(rows, separators=(",",":")))
'@
Set-Content -Path $PyPath -Value $PyCode -Encoding UTF8

# 3) Kjør Python og filtrer kun JSON-linjen
$pyOut = python "$PyPath"
$jsonLine = $pyOut | Where-Object { $_ -like 'JSON:*' } | Select-Object -Last 1
if (-not $jsonLine) {
  Write-Error "Missing JSON line from Python. Full output:`n$pyOut"
  exit 1
}
$rows = $jsonLine.Substring(5) | ConvertFrom-Json

# 4) Skriv CSV
$CsvPath = Join-Path $OutDir "trinn5-proof.csv"
$rows | Select-Object name,drag,roll,prec,device | Export-Csv -NoTypeInformation -Path $CsvPath -Encoding UTF8
Write-Host "Wrote $CsvPath"

# 5) Monotoni-sjekker
$base  = $rows | Where-Object { $_.name -eq 'baseline' }
$cdaUp = $rows | Where-Object { $_.name -eq 'cda_up' }
$crrUp = $rows | Where-Object { $_.name -eq 'crr_up' }
$wUp   = $rows | Where-Object { $_.name -eq 'w_up' }
$effDn = $rows | Where-Object { $_.name -eq 'eff_dn' }

if ($null -eq $base -or $null -eq $cdaUp -or $null -eq $crrUp -or $null -eq $wUp -or $null -eq $effDn) {
  $got = (($rows | ForEach-Object { $_.name }) -join ', ')
  Write-Error "Missing rows in proof output. Got: $got"
  exit 1
}

if ($cdaUp.drag -le $base.drag) { Write-Host "Fail: CdA up but drag did not increase" -ForegroundColor Red } else { Write-Host "OK: CdA up -> drag up" -ForegroundColor Green }
if ($crrUp.roll -le $base.roll) { Write-Host "Fail: Crr up but rolling did not increase" -ForegroundColor Red } else { Write-Host "OK: Crr up -> rolling up" -ForegroundColor Green }
if ($wUp.roll   -le $base.roll) { Write-Host "Fail: Weight up but rolling did not increase" -ForegroundColor Red } else { Write-Host "OK: Weight up -> rolling up" -ForegroundColor Green }
if ($effDn.prec -le $base.prec) { Write-Host "Fail: CrankEff down but precision_watt did not increase" -ForegroundColor Red } else { Write-Host "OK: CrankEff down -> precision_watt up" -ForegroundColor Green }
Get-Content $CsvPath
