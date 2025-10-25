# scripts/start-api.ps1
# Formål: sette env riktig (inkl. støtte for .env), og starte Uvicorn med --reload

# Gå til repo-roten uansett hvor scriptet kjøres fra
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# 1) Last .env (valgfritt). Enkel parser: KEY=VALUE, ignorerer tomme linjer og kommentarer (#)
$envPath = Join-Path $repoRoot ".env"
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $kv = $line -split "=", 2
        if ($kv.Count -eq 2) {
            $k = $kv[0].Trim()
            $v = $kv[1].Trim()
            # Fjern evt. innpakkende anførselstegn
            if ($v.StartsWith('"') -and $v.EndsWith('"')) { $v = $v.Substring(1, $v.Length-2) }
            if ($v.StartsWith("'") -and $v.EndsWith("'")) { $v = $v.Substring(1, $v.Length-2) }
            if (-not [string]::IsNullOrWhiteSpace($k)) { $env:$k = $v }
        }
    }
}

# 2) Manuelle defaults (bare hvis ikke satt allerede via .env eller eksisterende miljø)
if (-not $env:CG_PUBLISH_TOGGLE)   { $env:CG_PUBLISH_TOGGLE = "true" }
# Sett token her hvis du ikke bruker .env (ANBEFALES: legg STRAVA_ACCESS_TOKEN i .env)
# if (-not $env:STRAVA_ACCESS_TOKEN) { $env:STRAVA_ACCESS_TOKEN = "<SETT_TOKEN_HER>" }

# 3) Sørg for at Python finner moduler fra repo-roten
$env:PYTHONPATH = $repoRoot

# 4) Liten statuslogg (uten å printe token)
Write-Host "[CycleGraph] Repo:" $repoRoot
Write-Host "[CycleGraph] CG_PUBLISH_TOGGLE =" $env:CG_PUBLISH_TOGGLE
Write-Host "[CycleGraph] STRAVA_ACCESS_TOKEN set? " ([bool]$env:STRAVA_ACCESS_TOKEN)

# 5) Start Uvicorn med --reload
python -m uvicorn app:app --reload --host 127.0.0.1 --port 5175
