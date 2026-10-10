# Self-test for OLD SCHOOL JEWELRY TRAY APP.exe on a real Windows computer.
#
#   powershell -ExecutionPolicy Bypass -File test-on-windows.ps1 [-Exe "path\to\OLD SCHOOL JEWELRY TRAY APP.exe"]
#
# Without -Exe it looks next to this script, then one folder up.
#
# Starts the program WITHOUT a window, using a throw-away settings folder and a test save
# folder under %TEMP%, then checks: the page loads; the L: drive is refused (the letter, and
# the network share behind it when L: is mapped, and any other letter mapped to that share);
# a normal folder works; saving makes the day folder, never overwrites, and writes the
# exact bytes. Nothing is written to L: or to the real app settings. Prints PASS/FAIL lines.
param([string]$Exe = '')

$ErrorActionPreference = 'Stop'
if (-not $Exe) {
  $Exe = @((Join-Path $PSScriptRoot 'OLD SCHOOL JEWELRY TRAY APP.exe'), (Join-Path $PSScriptRoot '..\OLD SCHOOL JEWELRY TRAY APP.exe')) |
    Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
  if (-not $Exe) { Write-Output 'Put this script next to OLD SCHOOL JEWELRY TRAY APP.exe, or give -Exe "path".'; exit 2 }
}
$fails = 0
function Check($name, $ok, $detail = '') {
  if ($ok) { Write-Output "PASS  $name" } else { $script:fails++; Write-Output "FAIL  $name  $detail" }
}

$Exe = (Resolve-Path -LiteralPath $Exe).Path
$work = Join-Path $env:TEMP ("JTD-SELFTEST-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path (Join-Path $work 'home') | Out-Null
Write-Output "Program: $Exe"
Write-Output "Test folder: $work"

# Is the real app already running on the fixed port? Then the test can't start its own copy.
try { $null = Invoke-RestMethod 'http://127.0.0.1:47391/api/info' -TimeoutSec 2; Write-Output 'The app is already running. Close its window, wait 10 minutes (or end it in Task Manager), then run this test again.'; exit 2 } catch {}

$psi = New-Object System.Diagnostics.ProcessStartInfo $Exe
$psi.UseShellExecute = $false
$psi.EnvironmentVariables['JTD_NO_WINDOW'] = '1'
$psi.EnvironmentVariables['JTD_HOME'] = (Join-Path $work 'home')
$proc = [System.Diagnostics.Process]::Start($psi)
try {
  $base = 'http://127.0.0.1:47391'
  $page = $null
  for ($i = 0; $i -lt 40 -and -not $page; $i++) { Start-Sleep -Milliseconds 250; try { $page = Invoke-WebRequest "$base/" -UseBasicParsing -TimeoutSec 2 } catch {} }
  Check 'program starts and serves the app page' ($page -and $page.Content -match 'OLD SCHOOL JEWELRY TRAY APP|Old School Jewelry Tray App')
  $token = [regex]::Match($page.Content, 'var NATIVE = \{"token":"([0-9a-f]+)"').Groups[1].Value
  Check 'page carries the save token' ($token.Length -eq 48)
  $h = @{ 'X-JTD-Token' = $token }
  function Api($path, $body) { Invoke-RestMethod "$base$path" -Method Post -Headers $h -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 5) }

  try { Invoke-RestMethod "$base/api/settings" -Method Post -ContentType 'application/json' -Body '{}' | Out-Null; Check 'calls without the token are refused' $false 'got through' }
  catch { Check 'calls without the token are refused' ($_.Exception.Response.StatusCode.value__ -eq 403) }

  # --- the L: drive ---
  $r = Api '/api/set-folder' @{ path = 'L:\JEWELRY TRAYS BOARDS TO BE CUT' }
  Check 'L:\ is refused' ($r.error -match 'L: drive') $r.error
  $r = Api '/api/set-folder' @{ path = 'l:/some folder' }
  Check 'l:/ (lower case, forward slash) is refused' ($r.error -match 'L: drive') $r.error
  $l = Get-PSDrive -Name L -ErrorAction SilentlyContinue
  $share = if ($l) { $l.DisplayRoot } else { $null }
  if ($share -and $share.StartsWith('\\')) {
    Write-Output "L: is mapped to $share"
    $r = Api '/api/set-folder' @{ path = (Join-Path $share 'JTD-SELFTEST-should-not-exist') }
    Check 'the network share behind L: is refused' ($r.error -match 'L: drive|network share') $r.error
    Check 'nothing was made on L:' (-not (Test-Path (Join-Path $share 'JTD-SELFTEST-should-not-exist')))
    $twins = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -ne 'L' -and $_.DisplayRoot -and $_.DisplayRoot.TrimEnd('\') -ieq $share.TrimEnd('\') }
    foreach ($t in $twins) {
      $r = Api '/api/set-folder' @{ path = "$($t.Name):\JTD-SELFTEST-should-not-exist" }
      Check "$($t.Name): (same share as L:) is refused" ($r.error -match 'network share') $r.error
    }
  } else {
    Write-Output 'L: is not a mapped network drive on this computer (share checks skipped; the letter is still refused).'
  }

  # --- a normal folder ---
  $save = Join-Path $work 'Jewelry Trays\Boards'
  $r = Api '/api/set-folder' @{ path = $save }
  Check 'a normal folder is accepted and made' ((-not $r.error) -and (Test-Path $save)) $r.error
  $r = Api '/api/set-folder' @{ path = 'Boards' }
  Check 'a path that is not full is refused' ($r.error -match 'full folder path') $r.error

  # --- saving ---
  $mpr = [byte[]](0x5B,0x48,0x0D,0x0A,0x4B,0x41,0x54,0x3D,0x22,0x46,0x72,0xE4,0x73,0x65,0x6E,0x22,0x0D,0x0A)  # [H / KAT="Fräsen" in Latin-1 with CRLF
  $files = @(@{ name = '101026 DAILY TRAYS 1.mpr'; data = [Convert]::ToBase64String($mpr) })
  $day = '101026 DAILY TRAYS #4354-4377'
  $r1 = Api '/api/save' @{ dayFolder = $day; mode = 'new'; files = $files }
  $r2 = Api '/api/save' @{ dayFolder = $day; mode = 'new'; files = $files }
  $r3 = Api '/api/save' @{ dayFolder = $day; mode = 'add'; files = $files }
  Check 'save makes the day folder' ((Split-Path $r1.dir -Leaf) -eq $day) "$($r1.error) $($r1.dir)"
  Check 'saving again makes "(2)", nothing overwritten' ((Split-Path $r2.dir -Leaf) -eq "$day (2)") "$($r2.error) $($r2.dir)"
  Check 'one board into an existing day folder gets "(2)" in its name' ($r3.files[0] -eq '101026 DAILY TRAYS 1 (2).mpr') "$($r3.error) $($r3.files)"
  $back = [IO.File]::ReadAllBytes((Join-Path $r1.dir '101026 DAILY TRAYS 1.mpr'))
  Check 'saved file has the exact bytes (CRLF and the a-umlaut kept)' ([Convert]::ToBase64String($back) -eq [Convert]::ToBase64String($mpr))

  # --- what the window needs ---
  $edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
            "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe", "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
            "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
  Check 'Edge or Chrome found for the app window' ([bool]$edge) 'the app would open in the default browser instead'
  if ($edge) { Write-Output "Window browser: $edge" }
  $ps = $true
  try { Add-Type -AssemblyName System.Windows.Forms } catch { $ps = $false }
  Check 'Windows folder picker is available (Choose folder...)' $ps 'people can still type the folder path'
}
finally {
  if ($proc -and -not $proc.HasExited) { $proc.Kill() }
  Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}
if ($fails) { Write-Output "$fails check(s) FAILED"; exit 1 } else { Write-Output 'ALL CHECKS PASSED' }
