# scripts/Import-Tools.ps1
# Robust resolve av modulsti, funker både ved direkte kjøring og dot-sourcing
$scriptDir = if ($PSScriptRoot) { 
  $PSScriptRoot 
} elseif ($MyInvocation.MyCommand.Path) { 
  Split-Path -Path $MyInvocation.MyCommand.Path -Parent 
} else { 
  (Get-Location).Path 
}

$mod = Join-Path $scriptDir "Tools/CycleGraph.Tools.psm1"
if (-not (Test-Path $mod)) { throw "[CG] Module not found: $mod" }

Import-Module $mod -Force
Write-Host "[CG] Tools imported. Use: Rebuild-Core, Start-API, Sanity, Sanity-Force, Call-Analyze, Call-DebugRB, Git-Snapshot, Set-CGApi"