package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestWriteNewNeverOverwrites(t *testing.T) {
	dir := t.TempDir()
	for i, want := range []string{"a.mpr", "a (2).mpr", "a (3).mpr"} {
		got, err := writeNew(dir, "a.mpr", []byte{byte(i)})
		if err != nil || got != want {
			t.Fatalf("write %d: got %q, %v; want %q", i, got, err, want)
		}
	}
	b, _ := os.ReadFile(filepath.Join(dir, "a.mpr"))
	if len(b) != 1 || b[0] != 0 {
		t.Fatalf("first file was changed: %v", b)
	}
}

func TestUniqueDayFolder(t *testing.T) {
	dir := t.TempDir()
	day := "101026 DAILY TRAYS #4354-4377"
	if p := uniquePath(dir, day); filepath.Base(p) != day {
		t.Fatalf("got %q", p)
	}
	os.Mkdir(filepath.Join(dir, day), 0o755)
	if p := uniquePath(dir, day); filepath.Base(p) != day+" (2)" {
		t.Fatalf("got %q", p)
	}
}
