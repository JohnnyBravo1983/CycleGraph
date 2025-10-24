param(
  [int]$Port = 5175,
  [switch]$Reload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Finn repo-roten
$cwd = (Get-Location).Path
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { $cwd }

function Find-RepoRoot([string]$start) {
    $d = Get-Item -LiteralPath $start
    while ($null -ne $d) {
        $hasApp = Test-Path (Join-Path $d.FullName 'app.py')
        $hasPkg = Test-Path (Join-Path $d.FullName 'cyclegraph')
        if ($hasApp -or $hasPkg) { return $d.FullName }
        $parent = Split-Path -Parent $d.FullName
        if (-not $parent -or $parent -eq $d.FullName) { break }
        $d = Get-Item -LiteralPath $parent
    }
    return $start
}

$repoRoot = Find-RepoRoot $scriptDir
Set-Location $repoRoot

# 1) Stopp gammel server
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\stop-api.ps1") -Port $Port

# 2) Velg hvilket startscript som skal brukes
$startNoReload = Join-Path $repoRoot "scripts\start-api-no-reload.ps1"
$startReload   = Join-Path $repoRoot "scripts\start-api.ps1"

if ($Reload) {
  if (-not (Test-Path $startReload)) { throw "Finner ikke $startReload" }
  Write-Host "[CycleGraph] Starter API med --reload på port $Port ..."
  powershell -NoProfile -ExecutionPolicy Bypass -File $startReload
} else {
  if (-not (Test-Path $startNoReload)) { throw "Finner ikke $startNoReload" }
  Write-Host "[CycleGraph] Starter API uten reload på port $Port ..."
  powershell -NoProfile -ExecutionPolicy Bypass -File $startNoReload
}
