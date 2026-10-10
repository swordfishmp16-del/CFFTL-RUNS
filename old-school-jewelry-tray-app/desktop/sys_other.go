//go:build !windows

package main

// Stand-ins so the program can be run and tested on Linux. The real program is the
// Windows build (sys_windows.go). JTD_HOME sets the settings folder and JTD_BLOCKED a
// folder treated like the L: drive.

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func settingsDir() string {
	if d := os.Getenv("JTD_HOME"); d != "" {
		return d
	}
	return filepath.Join(os.TempDir(), "OldSchoolJewelryTrayApp")
}

func validateFolder(p string) (string, error) {
	p = strings.TrimSpace(p)
	if !filepath.IsAbs(p) {
		return "", errNotFull
	}
	p = filepath.Clean(p)
	if b := os.Getenv("JTD_BLOCKED"); b != "" && inside(p, b) {
		return "", errLDrive
	}
	return p, nil
}

func recheckReal(p string) error {
	real, err := filepath.EvalSymlinks(p)
	if err != nil {
		return nil
	}
	_, err = validateFolder(real)
	return err
}

func inside(path, base string) bool {
	rel, err := filepath.Rel(filepath.Clean(base), filepath.Clean(path))
	return err == nil && rel != ".." && !strings.HasPrefix(rel, "../")
}

func pickFolder(string) (string, bool, error) {
	return "", false, errors.New("the folder picker only works on Windows; type the folder path instead")
}

func openFolder(p string) { fmt.Println("open folder:", p) }

func openWindow(url, dir string) { fmt.Println("open:", url) }

func showError(msg string) { fmt.Fprintln(os.Stderr, msg) }
