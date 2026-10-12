package main

// Save-folder rules. Files may go anywhere on the computer EXCEPT the L: drive
// (the shop's cut queue). People move the finished day folders to L: themselves.
//
// These rules use Windows path rules on every system so they can be tested here.

import (
	"errors"
	"strings"
)

var (
	errNotFull = errors.New(`Use a full folder path, like C:\Jewelry Trays\Boards.`)
	errLDrive  = errors.New(`That's the L: drive. Pick a folder on this computer instead (for example C:\Jewelry Trays\Boards), then move the finished folders to L: yourself.`)
	errLShare  = errors.New(`That folder is on the same network share as the L: drive. Pick a folder on this computer instead, then move the finished folders to L: yourself.`)
)

// normalizeWinPath turns what someone typed or picked into a clean absolute Windows path:
// quotes and spaces trimmed, / turned into \, . and .. resolved, drive letter upper-cased.
func normalizeWinPath(p string) (string, error) {
	p = strings.TrimSpace(p)
	p = strings.Trim(p, `"`)
	p = strings.TrimSpace(p)
	p = strings.ReplaceAll(p, "/", `\`)
	switch {
	case strings.HasPrefix(strings.ToUpper(p), `\\?\UNC\`):
		p = `\\` + p[len(`\\?\UNC\`):]
	case strings.HasPrefix(p, `\\?\`), strings.HasPrefix(p, `\\.\`):
		p = p[4:]
	}

	var root, rest string
	switch {
	case len(p) >= 2 && isLetter(p[0]) && p[1] == ':':
		if len(p) > 2 && p[2] != '\\' {
			return "", errNotFull // "C:folder" is relative to the current folder on C:
		}
		root = strings.ToUpper(p[:1]) + `:\`
		rest = p[2:]
	case strings.HasPrefix(p, `\\`):
		parts := strings.Split(strings.TrimLeft(p, `\`), `\`)
		if len(parts) < 2 || parts[0] == "" || parts[1] == "" {
			return "", errNotFull
		}
		root = `\\` + parts[0] + `\` + parts[1] + `\`
		rest = strings.Join(parts[2:], `\`)
	default:
		return "", errNotFull
	}

	var out []string
	for _, seg := range strings.Split(rest, `\`) {
		seg = strings.TrimRight(seg, " ")
		switch seg {
		case "", ".":
			continue
		case "..":
			if len(out) > 0 {
				out = out[:len(out)-1]
			}
			continue
		}
		out = append(out, seg)
	}
	return root + strings.Join(out, `\`), nil
}

// checkFolder cleans the path and refuses the L: drive. driveUNC tells which network
// share a mapped drive letter points to (\\server\share), or "" for a local drive; it
// catches another letter, or a \\server\share path, that leads to the same place as L:.
func checkFolder(p string, driveUNC func(letter byte) string) (string, error) {
	clean, err := normalizeWinPath(p)
	if err != nil {
		return "", err
	}
	lShare := ""
	if driveUNC != nil {
		lShare = driveUNC('L')
	}
	if isLetter(clean[0]) {
		d := clean[0]
		if d == 'L' {
			return "", errLDrive
		}
		if lShare != "" && driveUNC != nil {
			if share := driveUNC(d); share != "" && under(strings.TrimRight(share, `\`)+clean[2:], lShare) {
				return "", errLShare
			}
		}
		return clean, nil
	}
	if lShare != "" && under(clean, lShare) {
		return "", errLShare
	}
	return clean, nil
}

// under reports whether path is root or inside it (Windows: not case-sensitive).
func under(path, root string) bool {
	p := strings.ToLower(strings.TrimRight(path, `\`))
	r := strings.ToLower(strings.TrimRight(root, `\`))
	return r != "" && (p == r || strings.HasPrefix(p, r+`\`))
}

func isLetter(c byte) bool { return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') }

// safeName makes a file or folder name Windows accepts: no \ / : * ? " < > | or control
// characters, no trailing dots or spaces, and no reserved device names like CON or LPT1.
func safeName(name string) string {
	var b strings.Builder
	for _, r := range name {
		if r < 32 || strings.ContainsRune(`<>:"/\|?*`, r) {
			b.WriteRune('_')
			continue
		}
		b.WriteRune(r)
	}
	s := strings.TrimRight(strings.TrimSpace(b.String()), ". ")
	if s == "" || s == "." || s == ".." {
		return "_"
	}
	base := strings.ToUpper(s)
	if i := strings.IndexByte(base, '.'); i >= 0 {
		base = base[:i]
	}
	switch base {
	case "CON", "PRN", "AUX", "NUL",
		"COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
		"LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9":
		return "_" + s
	}
	return s
}
