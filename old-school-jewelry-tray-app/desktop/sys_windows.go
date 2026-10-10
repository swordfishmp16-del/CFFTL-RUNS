//go:build windows

package main

import (
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
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

const (
	bifReturnOnlyFSDirs = 0x0001
	bifEditBox          = 0x0010
	bifNewDialogStyle   = 0x0040
	bffmInitialized     = 1
	bffmSetSelectionW   = 0x0467
	coinitApartment     = 0x2
)

var (
	shell32                  = syscall.NewLazyDLL("shell32.dll")
	procSHBrowseForFolderW   = shell32.NewProc("SHBrowseForFolderW")
	procSHGetPathFromIDListW = shell32.NewProc("SHGetPathFromIDListW")
	procShellExecuteW        = shell32.NewProc("ShellExecuteW")
	ole32                    = syscall.NewLazyDLL("ole32.dll")
	procCoInitializeEx       = ole32.NewProc("CoInitializeEx")
	procCoUninitialize       = ole32.NewProc("CoUninitialize")
	procCoTaskMemFree        = ole32.NewProc("CoTaskMemFree")
	procGetForegroundWindow  = user32.NewProc("GetForegroundWindow")
	procSendMessageW         = user32.NewProc("SendMessageW")
)

// BROWSEINFOW (shlobj_core.h); Go lays it out the same way as Windows does on 64-bit.
type browseInfo struct {
	hwndOwner      uintptr
	pidlRoot       uintptr
	pszDisplayName *uint16
	lpszTitle      *uint16
	ulFlags        uint32
	lpfn           uintptr
	lParam         uintptr
	iImage         int32
}

// Starts the box on the current save folder.
var browseCallback = syscall.NewCallback(func(hwnd, msg, lParam, data uintptr) uintptr {
	if msg == bffmInitialized && data != 0 {
		procSendMessageW.Call(hwnd, bffmSetSelectionW, 1, data)
	}
	return 0
})

// pickFolder shows the normal Windows "Browse For Folder" box, straight from Windows
// (shell32), on top of the app window. Returns cancelled=true when the person cancels.
func pickFolder(start string) (string, bool, error) {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	if r, _, _ := procCoInitializeEx.Call(0, coinitApartment); int32(r) >= 0 {
		defer procCoUninitialize.Call()
	}
	title, _ := syscall.UTF16PtrFromString("Pick where the app saves each day's folder. Not the L: drive.")
	name := make([]uint16, syscall.MAX_PATH)
	var startPtr *uint16
	if start != "" {
		if _, err := os.Stat(start); err == nil {
			startPtr, _ = syscall.UTF16PtrFromString(start)
		}
	}
	owner, _, _ := procGetForegroundWindow.Call()
	bi := browseInfo{
		hwndOwner:      owner,
		pszDisplayName: &name[0],
		lpszTitle:      title,
		ulFlags:        bifReturnOnlyFSDirs | bifNewDialogStyle | bifEditBox,
		lpfn:           browseCallback,
		lParam:         uintptr(unsafe.Pointer(startPtr)),
	}
	pidl, _, _ := procSHBrowseForFolderW.Call(uintptr(unsafe.Pointer(&bi)))
	runtime.KeepAlive(startPtr)
	runtime.KeepAlive(title)
	if pidl == 0 {
		return "", true, nil
	}
	defer procCoTaskMemFree.Call(pidl)
	buf := make([]uint16, 32768)
	if ok, _, _ := procSHGetPathFromIDListW.Call(pidl, uintptr(unsafe.Pointer(&buf[0]))); ok == 0 {
		return "", false, errors.New("that isn't a folder on disk; pick a normal folder or type the path instead")
	}
	return syscall.UTF16ToString(buf), false, nil
}

// shellOpen opens a file, folder or web address the way double-clicking it would.
func shellOpen(target string) {
	verb, _ := syscall.UTF16PtrFromString("open")
	t, _ := syscall.UTF16PtrFromString(target)
	procShellExecuteW.Call(0, uintptr(unsafe.Pointer(verb)), uintptr(unsafe.Pointer(t)), 0, 0, 1)
}

func openFolder(p string) { shellOpen(p) }

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
	shellOpen(url)
}

func showError(msg string) {
	t, _ := syscall.UTF16PtrFromString("Old School Jewelry Tray App")
	m, _ := syscall.UTF16PtrFromString(msg)
	procMessageBoxW.Call(0, uintptr(unsafe.Pointer(m)), uintptr(unsafe.Pointer(t)), 0x10)
}
