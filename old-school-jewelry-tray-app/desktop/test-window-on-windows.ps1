# Window + folder-picker test for OLD SCHOOL JEWELRY TRAY APP REV <n>.exe on a real Windows computer.
#
#   powershell -ExecutionPolicy Bypass -File test-window-on-windows.ps1 [-Exe "path\to\OLD SCHOOL JEWELRY TRAY APP REV <n>.exe"]
#
# Uses a throw-away settings folder under %TEMP%. First opens a stand-in for an old app window
# left open (REV 1 and 2 windows were titled exactly "Old School Jewelry Tray App") and checks
# the program closes it when it starts. Then checks that the app opens in its own Chrome/Edge
# window titled with its REV, opens the Windows "Browse For Folder" box twice through the program
# and presses OK (the current save folder is pre-selected) and Cancel, checking what the app does.
# The windows and the picker flash on screen for a few seconds; everything is closed again.
param([string]$Exe = '')
$ErrorActionPreference = 'Stop'
if (-not $Exe) {
  # the highest REV next to this script, or one folder up
  $Exe = @($PSScriptRoot, (Join-Path $PSScriptRoot '..')) | ForEach-Object { Get-ChildItem -LiteralPath $_ -Filter 'OLD SCHOOL JEWELRY TRAY APP*.exe' -ErrorAction SilentlyContinue } |
    Sort-Object { if ($_.BaseName -match 'REV (\d+)$') { [int]$Matches[1] } else { 0 } } -Descending | Select-Object -First 1 -ExpandProperty FullName
  if (-not $Exe) { Write-Output 'Put this script next to OLD SCHOOL JEWELRY TRAY APP REV <n>.exe, or give -Exe "path".'; exit 2 }
}
try { $null = Invoke-RestMethod 'http://127.0.0.1:47391/api/info' -TimeoutSec 2; Write-Output 'The app is already running. Close it first.'; exit 2 } catch {}
Add-Type @'
using System; using System.Text; using System.Runtime.InteropServices;
public static class JtdWin { delegate bool P(IntPtr h, IntPtr l);
 [DllImport("user32.dll")] static extern bool EnumWindows(P p, IntPtr l);
 [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr h);
 public static string Title(IntPtr h) { var t = new StringBuilder(256); GetWindowText(h, t, 256); return t.ToString(); }
 [DllImport("user32.dll")] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
 public static IntPtr Find(string cls, string title, bool exact) { IntPtr f = IntPtr.Zero; EnumWindows((h, l) => {
   var t = new StringBuilder(256); var c = new StringBuilder(64); GetWindowText(h, t, 256); GetClassName(h, c, 64);
   if (IsWindowVisible(h) && (string.IsNullOrEmpty(cls) || c.ToString() == cls) && (exact ? t.ToString() == title : t.ToString().Contains(title))) { f = h; return false; } return true; }, IntPtr.Zero); return f; } }
'@
$fails = 0
function Check($name, $ok, $detail = '') { if ($ok) { "PASS  $name" } else { $script:fails++; "FAIL  $name  $detail" } }
function Wait-Window($cls, $title, $exact = $false) { for ($i = 0; $i -lt 120; $i++) { Start-Sleep -Milliseconds 250; $h = [JtdWin]::Find($cls, $title, $exact); if ($h -ne [IntPtr]::Zero) { return $h } }; return [IntPtr]::Zero }

$work = Join-Path $env:TEMP ('JTD-WINTEST-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path (Join-Path $work 'home') | Out-Null

# A stand-in old app window, in the same browser profile the app uses.
$browserExe = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
                "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe", "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
                "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
$oldPage = Join-Path $work 'old-window.html'
Set-Content -LiteralPath $oldPage -Value '<!doctype html><title>Old School Jewelry Tray App</title><p>stand-in for an old window' -Encoding ascii
Start-Process $browserExe -ArgumentList ('--app=file:///' + $oldPage.Replace('\', '/')), ('--user-data-dir="' + (Join-Path $work 'home\window') + '"'), '--no-first-run', '--no-default-browser-check'
$stale = Wait-Window 'Chrome_WidgetWin_1' 'Old School Jewelry Tray App' $true
Check 'stand-in old app window is open' ($stale -ne [IntPtr]::Zero)

$psi = New-Object System.Diagnostics.ProcessStartInfo (Resolve-Path -LiteralPath $Exe).Path
$psi.UseShellExecute = $false
$psi.EnvironmentVariables['JTD_HOME'] = (Join-Path $work 'home')
$proc = [System.Diagnostics.Process]::Start($psi)
try {
  $win = Wait-Window '' 'Old School Jewelry Tray App REV'   # a new window profile can take a while the first time
  Check 'the app opens in its own window' ($win -ne [IntPtr]::Zero)
  $title = if ($win -ne [IntPtr]::Zero) { [JtdWin]::Title($win) } else { '' }
  Check 'the window title shows the REV' ($title -match '^Old School Jewelry Tray App REV \d+$') $title
  Check 'the old app window was closed' (($stale -ne [IntPtr]::Zero) -and -not [JtdWin]::IsWindow($stale))
  $browser = Get-CimInstance Win32_Process -Filter "Name='chrome.exe' OR Name='msedge.exe'" | Where-Object { $_.CommandLine -like '*--app=http://127.0.0.1:47391/*' } | Select-Object -First 1
  if ($browser) { "Window browser: $($browser.Name)" }

  $page = Invoke-WebRequest 'http://127.0.0.1:47391/' -UseBasicParsing
  $token = [regex]::Match($page.Content, 'var NATIVE = \{"token":"([0-9a-f]+)"').Groups[1].Value
  $h = @{ 'X-JTD-Token' = $token }
  $start = Join-Path $work 'Picked Folder'
  $null = Invoke-RestMethod 'http://127.0.0.1:47391/api/set-folder' -Method Post -Headers $h -ContentType 'application/json' -Body (@{ path = $start } | ConvertTo-Json)
  foreach ($case in @(@{ name = 'OK'; button = 1 }, @{ name = 'Cancel'; button = 2 })) {
    $job = Start-Job -ScriptBlock { param($t) Invoke-RestMethod 'http://127.0.0.1:47391/api/pick-folder' -Method Post -Headers @{ 'X-JTD-Token' = $t } -ContentType 'application/json' -Body '{}' } -ArgumentList $token
    $dlg = Wait-Window '#32770' 'Browse For Folder'
    if ($dlg -ne [IntPtr]::Zero) { [void][JtdWin]::PostMessage($dlg, 0x0111, [IntPtr]$case.button, [IntPtr]::Zero) }
    $r = Receive-Job $job -Wait -AutoRemoveJob
    if ($case.name -eq 'OK') { Check 'folder picker opens; OK sets the save folder' (($dlg -ne [IntPtr]::Zero) -and $r.saveFolder -eq $start) ($r | ConvertTo-Json -Compress) }
    else { Check 'folder picker opens; Cancel changes nothing' (($dlg -ne [IntPtr]::Zero) -and $r.cancelled) ($r | ConvertTo-Json -Compress) }
  }
}
finally {
  Get-CimInstance Win32_Process -Filter "Name='chrome.exe' OR Name='msedge.exe'" | Where-Object { $_.CommandLine -like ('*' + $work + '*') } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  if ($proc -and -not $proc.HasExited) { $proc.Kill() }
  Start-Sleep -Seconds 1
  Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}
if ($fails) { "$fails check(s) FAILED"; exit 1 } else { 'ALL CHECKS PASSED' }
