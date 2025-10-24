param(
  [int]$Port = 5175
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "[CycleGraph] Stopper prosesser på port $Port ..."

try {
  $pids = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
          Select-Object -ExpandProperty OwningProcess -Unique
} catch {
  $pids = @()
}

if (-not $pids -or $pids.Count -eq 0) {
  Write-Host "[CycleGraph] Ingen prosesser fant på port $Port."
  exit 0
}

$p = @()
foreach ($pid in $pids) {
  try { $p += Get-Process -Id $pid -ErrorAction Stop } catch { }
}

if ($p.Count -gt 0) {
  Write-Warning ("[CycleGraph] Stopper: {0} (PID: {1})" -f ($p.ProcessName -join ', '), ($p.Id -join ', '))
  foreach ($proc in $p) {
    try { Stop-Process -Id $proc.Id -Force -ErrorAction Stop } catch { }
  }
  Start-Sleep -Milliseconds 500
}

# Verifiser at porten er ledig
try {
  $still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if ($still) {
    throw "Klarte ikke frigjøre port $Port. Lukk manuelt."
  }
} catch { }

Write-Host "[CycleGraph] Port $Port er frigjort."
