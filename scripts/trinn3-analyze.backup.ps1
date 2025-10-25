param(
  [string] $SidBase = "ride3",
  [int]    $Port    = 5179,
  [string] $ApiHost = "127.0.0.1",
  [string] $OutDir  = "logs",
  [string] $CasesPath
)

# Kall malen med riktige flagg for trinn 3
& "$PSScriptRoot\trinn-test-template.ps1" `
  -TrinnName "trinn3" `
  -SidBase $SidBase `
  -Port $Port `
  -ApiHost $ApiHost `
  -OutDir $OutDir `
  -UniqueSidPerCase `
  -IncludeWeather:$false `
  -CasesPath $CasesPath