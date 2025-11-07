param([string]$TxtFile)

# 1) Finn riktig filbane til TXT
if ($TxtFile -and (Test-Path $TxtFile)) {
  $Path = (Resolve-Path $TxtFile).Path
} else {
  $cand = Get-ChildItem -Recurse -File |
    Where-Object {
      $_.Name -ieq 'Manuell_Cyclegraph_5Økter.txt' -or
      $_.Name -like 'Manuell_Cyclegraph_5?kter.txt'
    } | Select-Object -First 1
  if ($cand) { $Path = $cand.FullName }
}

if (-not $Path) {
  Write-Error "Fant ikke Manuell_Cyclegraph_5Økter.txt. Tips: -TxtFile 'C:\full\sti\Manuell_Cyclegraph_5Økter.txt'"
  exit 1
}

# 2) Kjør Python: last 'cli/profile_binding.py' via filbane (unngår cli/__init__.py & click)
python -c "import json,sys,re,os,importlib.util
# last modul direkte fra fil
mb = os.path.join('cli','profile_binding.py')
spec = importlib.util.spec_from_file_location('profile_binding', mb)
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

# last profil, lag versjon, les ride-IDs fra gitt TXT, skriv bindings
p = mod.load_user_profile()
ver = mod.compute_profile_version(p)

with open(sys.argv[1], 'r', encoding='utf-8') as f:
    txt = f.read()
ride_ids = sorted(set(re.findall(r'\b\d{6,}\b', txt)))
bindings = mod.write_bindings(ride_ids, ver)

print('PROFILE_VERSION', ver, 'RIDES', len(ride_ids))
print(json.dumps(bindings, indent=2, ensure_ascii=False))" "$Path"