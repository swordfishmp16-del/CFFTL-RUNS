# L: network-share test for a computer that has NO L: drive (e.g. a laptop).
#
#   powershell -ExecutionPolicy Bypass -File test-l-share-on-windows.ps1
#
# Briefly maps L: and N: to the same throw-away folder through \\localhost (real network drive
# mappings), runs test-on-windows.ps1 so the "share behind L:" and "another letter on the same
# share" checks run for real, then removes both letters. Stops without changing anything if
# L: or N: is already in use. Run it next to test-on-windows.ps1 and the .exe.
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:TEMP 'JTD-LSHARE-TEST'
New-Item -ItemType Directory -Force -Path $root | Out-Null
$unc = '\\localhost\' + $root.Substring(0, 1) + '$' + $root.Substring(2)
foreach ($d in 'L', 'N') { if (Get-PSDrive -Name $d -ErrorAction SilentlyContinue) { Write-Output "$d`: is already in use - stopping, nothing changed."; exit 3 } }
try {
  New-PSDrive -Name L -PSProvider FileSystem -Root $unc -Persist -Scope Global | Out-Null
  New-PSDrive -Name N -PSProvider FileSystem -Root $unc -Persist -Scope Global | Out-Null
  Get-PSDrive -Name L, N | ForEach-Object { 'mapped {0}: -> {1}' -f $_.Name, $_.DisplayRoot }
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'test-on-windows.ps1')
  $code = $LASTEXITCODE
  'files left in the L: test folder: ' + @(Get-ChildItem -Recurse -Force $root).Count
}
finally {
  foreach ($d in 'L', 'N') { Remove-PSDrive -Name $d -Force -ErrorAction SilentlyContinue }
  Remove-Item -Recurse -Force $root -ErrorAction SilentlyContinue
  'L: still mapped after cleanup: ' + [bool](Get-PSDrive -Name L -ErrorAction SilentlyContinue)
  'N: still mapped after cleanup: ' + [bool](Get-PSDrive -Name N -ErrorAction SilentlyContinue)
}
exit $code
