package main

import "testing"

func fakeShares(m map[byte]string) func(byte) string {
	return func(d byte) string { return m[d] }
}

func TestNormalize(t *testing.T) {
	cases := map[string]string{
		`c:\Jewelry Trays\Boards`:        `C:\Jewelry Trays\Boards`,
		`"C:/Jewelry Trays/Boards/"`:     `C:\Jewelry Trays\Boards`,
		`C:\a\.\b\..\c`:                  `C:\a\c`,
		`D:`:                             `D:\`,
		`\\pc2\share\trays`:              `\\pc2\share\trays`,
		`\\?\C:\x`:                       `C:\x`,
		`\\?\UNC\srv\shop\cut`:           `\\srv\shop\cut`,
		`  C:\Users\Mike\Desktop\Trays `: `C:\Users\Mike\Desktop\Trays`,
	}
	for in, want := range cases {
		got, err := normalizeWinPath(in)
		if err != nil || got != want {
			t.Errorf("normalizeWinPath(%q) = %q, %v; want %q", in, got, err, want)
		}
	}
	for _, bad := range []string{``, `Trays`, `C:Trays`, `\\server`, `\\server\`, `/home/x`} {
		if _, err := normalizeWinPath(bad); err == nil {
			t.Errorf("normalizeWinPath(%q) should fail", bad)
		}
	}
}

func TestLDriveIsRefused(t *testing.T) {
	shares := fakeShares(map[byte]string{'L': `\\fileserver\shop`, 'M': `\\fileserver\shop`, 'N': `\\fileserver\other`})
	refused := []string{
		`L:\`, `l:\JEWELRY TRAYS BOARDS TO BE CUT`, `L:/JEWELRY TRAYS DIRECT FILES`, `"L:\x"`,
		`\\?\L:\x`,
		`\\fileserver\shop`, `\\FILESERVER\Shop\JEWELRY TRAYS BOARDS TO BE CUT`, `\\?\UNC\fileserver\shop\x`,
		`M:\anything`, // another letter mapped to the same share as L:
	}
	for _, p := range refused {
		if _, err := checkFolder(p, shares); err == nil {
			t.Errorf("checkFolder(%q) should refuse the L: drive", p)
		}
	}
	allowed := []string{
		`C:\Jewelry Trays\Boards`, `C:\Users\Mike\Desktop\TRAYS`, `D:\Shop`, `N:\other share folder`,
		`\\fileserver\other\trays`, `\\fileserver\shopping\x`, // a different share whose name starts the same
	}
	for _, p := range allowed {
		if _, err := checkFolder(p, shares); err != nil {
			t.Errorf("checkFolder(%q) refused: %v", p, err)
		}
	}
	// With no network info (L: not mapped), L: is still refused by letter.
	if _, err := checkFolder(`L:\x`, nil); err != errLDrive {
		t.Errorf("L: must be refused even when it is not mapped, got %v", err)
	}
}

func TestSafeName(t *testing.T) {
	cases := map[string]string{
		`101026 DAILY TRAYS #4354-4377`: `101026 DAILY TRAYS #4354-4377`,
		`101026 DAILY TRAYS 1.mpr`:      `101026 DAILY TRAYS 1.mpr`,
		`..\..\Windows\evil.mpr`:        `.._.._Windows_evil.mpr`,
		`a:b*c?.csv`:                    `a_b_c_.csv`,
		`CON.txt`:                       `_CON.txt`,
		`name. `:                        `name`,
		`..`:                            `_`,
	}
	for in, want := range cases {
		if got := safeName(in); got != want {
			t.Errorf("safeName(%q) = %q; want %q", in, got, want)
		}
	}
}
