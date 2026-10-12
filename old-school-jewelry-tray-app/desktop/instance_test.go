package main

import (
	"testing"
	"time"
)

func TestRevOf(t *testing.T) {
	for v, want := range map[string]int{
		"REV 3 (2026-10-12)":  3,
		"REV 12 (2027-01-05)": 12,
		"REV 3":               3,
		"1.0.0 (2026-10-10)":  0, // before revision numbers
		"1.1.0 (2026-10-12)":  0,
		"dev":                 0,
		"":                    0,
		"REVISION 4":          0,
	} {
		if got := revOf(v); got != want {
			t.Errorf("revOf(%q) = %d, want %d", v, got, want)
		}
	}
}

func TestIsAppWindowTitle(t *testing.T) {
	for title, want := range map[string]bool{
		"Old School Jewelry Tray App":                                   true, // REV 1 and 2 windows
		"Old School Jewelry Tray App REV 3":                             true,
		"Old School Jewelry Tray App REV 14":                            true,
		"Old School Jewelry Tray App - Google Chrome":                   false, // the .html in a normal browser tab
		"Old School Jewelry Tray App REV 3 - Google Chrome":             false,
		"Old School Jewelry Tray App - Microsoft Edge":                  false,
		"Old School Jewelry Tray App REV 3 - Personal - Microsoft Edge": false,
		"Jewelry Tray Calculator":                                       false,
		"":                                                              false,
	} {
		if got := isAppWindowTitle(title); got != want {
			t.Errorf("isAppWindowTitle(%q) = %v, want %v", title, got, want)
		}
	}
}

func TestShouldStop(t *testing.T) {
	start := time.Date(2026, 10, 12, 9, 0, 0, 0, time.UTC)
	cases := []struct {
		name      string
		now, ping time.Time
		want      bool
	}{
		{"just started, no window yet", start.Add(time.Minute), time.Time{}, false},
		{"never got a window", start.Add(11 * time.Minute), time.Time{}, true},
		{"window pinging", start.Add(time.Hour), start.Add(time.Hour - 15*time.Second), false},
		{"window closed 9 minutes ago", start.Add(time.Hour), start.Add(51 * time.Minute), false},
		{"window closed 11 minutes ago", start.Add(time.Hour), start.Add(49 * time.Minute), true},
	}
	for _, c := range cases {
		if got := shouldStop(c.now, c.ping, start); got != c.want {
			t.Errorf("%s: shouldStop = %v, want %v", c.name, got, c.want)
		}
	}
}
