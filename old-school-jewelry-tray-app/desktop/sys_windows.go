//go:build windows

package main

import (
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"unsafe"
)

const appFolder = "OldSchoolJewelryTrayApp"

func settingsDir() string {
	if d := os.Getenv("JTD_HOME"); d != "" { // used by test-on-windows.ps1 so a test never touches real settings
		return d
	}
	if d := os.Getenv("LOCALAPPDATA"); d != "" {
		return filepath.Join(d, appFolder)
	}
	return filepath.Join(os.TempDir(), appFolder)
}

var (
	mpr                    = syscall.NewLazyDLL("mpr.dll")
	procWNetGetConnectionW = mpr.NewProc("WNetGetConnectionW")
	user32                 = syscall.NewLazyDLL("user32.dll")
	procMessageBoxW        = user32.NewProc("MessageBoxW")
)

// driveUNC returns the network share a mapped drive letter points to, e.g. \\server\shop.
func driveUNC(letter byte) string {
	local, _ := syscall.UTF16PtrFromString(string([]byte{letter, ':'}))
	buf := make([]uint16, 1024)
	n := uint32(len(buf))
	r, _, _ := procWNetGetConnectionW.Call(uintptr(unsafe.Pointer(local)), uintptr(unsafe.Pointer(&buf[0])), uintptr(unsafe.Pointer(&n)))
	if r != 0 {
		return ""
	}
	return syscall.UTF16ToString(buf)
}

func validateFolder(p string) (string, error) { return checkFolder(p, driveUNC) }

// recheckReal follows shortcut folders (junctions/links) and checks where they really go.
func recheckReal(p string) error {
	real, err := filepath.EvalSymlinks(p)
	if err != nil {
		return nil
	}
	_, err = checkFolder(real, driveUNC)
	return err
}

func inside(path, base string) bool {
	p, err1 := normalizeWinPath(path)
	b, err2 := normalizeWinPath(base)
	return err1 == nil && err2 == nil && under(p, b)
}

const createNoWindow = 0x08000000

// pickFolder shows the normal Windows "Browse For Folder" box.
func pickFolder(start string) (string, bool, error) {
	script := `[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true; $owner.ShowInTaskbar = $false; $owner.Opacity = 0
$owner.StartPosition = 'CenterScreen'; $owner.Show()
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = 'Pick where the app saves each day''s folder. Not the L: drive.'
$d.ShowNewFolderButton = $true
if ($env:JTD_START -and (Test-Path -LiteralPath $env:JTD_START)) { $d.SelectedPath = $env:JTD_START }
if ($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($d.SelectedPath) }
$owner.Close()`
	cmd := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass", "-Command", script)
	cmd.Env = append(os.Environ(), "JTD_START="+start)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: createNoWindow}
	out, err := cmd.Output()
	if err != nil {
		return "", false, errors.New("the folder picker didn't open; type the folder path instead")
	}
	path := strings.TrimSpace(string(out))
	if path == "" {
		return "", true, nil
	}
	return path, false, nil
}

func openFolder(p string) { _ = exec.Command("explorer.exe", p).Start() }

// openWindow opens the app in its own window (Edge, or Chrome) with its own profile,
// so it looks like a program and keeps its settings. Falls back to the default browser.
func openWindow(url, dir string) {
	args := []string{"--app=" + url, "--user-data-dir=" + filepath.Join(dir, "window"),
		"--no-first-run", "--no-default-browser-check", "--window-size=1400,950"}
	var candidates []string
	for _, env := range []string{"ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"} {
		root := os.Getenv(env)
		if root == "" {
			continue
		}
		candidates = append(candidates,
			filepath.Join(root, `Microsoft\Edge\Application\msedge.exe`),
			filepath.Join(root, `Google\Chrome\Application\chrome.exe`))
	}
	for _, exe := range candidates {
		if _, err := os.Stat(exe); err == nil {
			if exec.Command(exe, args...).Start() == nil {
				return
			}
		}
	}
	_ = exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
}

func showError(msg string) {
	t, _ := syscall.UTF16PtrFromString("Old School Jewelry Tray App")
	m, _ := syscall.UTF16PtrFromString(msg)
	procMessageBoxW.Call(0, uintptr(unsafe.Pointer(m)), uintptr(unsafe.Pointer(t)), 0x10)
}
