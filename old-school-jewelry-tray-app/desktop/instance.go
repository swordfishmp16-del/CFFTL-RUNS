package main

// Only one copy of the program runs at a time, on the fixed port. When another copy is
// already running, the newer revision wins:
//   - the same or a newer revision keeps running and just gets another window;
//   - an older copy from REV 3 on is asked to quit (with the token it left in the
//     settings folder) and this copy takes over;
//   - an older copy from before revision numbers (1.0.0, 1.1.0) can't be asked, so the
//     person is told how to close it. Nothing ever shows an old page by surprise.

import (
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// The program stops once no window has pinged it for this long.
const idleLimit = 10 * time.Minute

var revRE = regexp.MustCompile(`^REV (\d+)\b`)

// revOf returns the revision number in a version like "REV 3 (2026-10-12)". Versions from
// before revision numbers ("1.0.0 (2026-10-10)", "dev") count as 0.
func revOf(v string) int {
	m := revRE.FindStringSubmatch(v)
	if m == nil {
		return 0
	}
	n, _ := strconv.Atoi(m[1])
	return n
}

// revName is how the program names itself to people, e.g. "REV 3".
func revName() string {
	if n := revOf(version); n > 0 {
		return "REV " + strconv.Itoa(n)
	}
	return "version " + version
}

var appTitleRE = regexp.MustCompile(`^Old School Jewelry Tray App( REV \d+)?$`)

// isAppWindowTitle tells the app's own windows apart from everything else. An app window
// is titled exactly like the page; a normal browser tab showing the .html version has
// " - Google Chrome" (or similar) after it and doesn't match.
func isAppWindowTitle(t string) bool { return appTitleRE.MatchString(t) }

type instance struct {
	Port    int    `json:"port"`
	Token   string `json:"token"`
	Version string `json:"version"`
}

func instanceFile(dir string) string { return filepath.Join(dir, "instance.json") }

// writeInstance leaves this copy's token where a newer copy on this computer can find it.
func (s *server) writeInstance(p int) {
	b, _ := json.Marshal(instance{Port: p, Token: s.token, Version: version})
	if err := os.WriteFile(instanceFile(s.dir), b, 0o600); err != nil {
		log.Print("can't write instance.json: ", err)
	}
}

// exit stops the program, removing its instance file unless a newer copy has replaced it.
func (s *server) exit(why string) {
	log.Print(why)
	if b, err := os.ReadFile(instanceFile(s.dir)); err == nil {
		var in instance
		if json.Unmarshal(b, &in) == nil && in.Token == s.token {
			_ = os.Remove(instanceFile(s.dir))
		}
	}
	os.Exit(0)
}

// shouldStop is the watchdog's rule: no ping from a window for idleLimit.
func shouldStop(now, lastPing, started time.Time) bool {
	if lastPing.IsZero() {
		return now.Sub(started) > idleLimit
	}
	return now.Sub(lastPing) > idleLimit
}

// runningVersion asks whatever answers on the port which app and version it is.
func runningVersion(p int) (string, bool) {
	c := http.Client{Timeout: 2 * time.Second}
	r, err := c.Get(fmt.Sprintf("http://127.0.0.1:%d/api/info", p))
	if err != nil {
		return "", false
	}
	defer r.Body.Close()
	var info map[string]string
	if json.NewDecoder(r.Body).Decode(&info) != nil || info["app"] != "jtd" {
		return "", false
	}
	return info["version"], true
}

// askToQuit tells the running copy to stop, using the token it left in the settings
// folder, and waits for the port to come free. Copies from before REV 3 have no token
// file and no quit, so this fails for them.
func askToQuit(dir string, p int) (net.Listener, bool) {
	var in instance
	b, err := os.ReadFile(instanceFile(dir))
	if err != nil || json.Unmarshal(b, &in) != nil || in.Token == "" {
		return nil, false
	}
	req, _ := http.NewRequest(http.MethodPost, fmt.Sprintf("http://127.0.0.1:%d/api/quit", p), strings.NewReader("{}"))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-JTD-Token", in.Token)
	c := http.Client{Timeout: 3 * time.Second}
	r, err := c.Do(req)
	if err != nil {
		return nil, false
	}
	r.Body.Close()
	if r.StatusCode != http.StatusOK {
		return nil, false
	}
	for i := 0; i < 40; i++ {
		time.Sleep(125 * time.Millisecond)
		if ln, err := net.Listen("tcp", "127.0.0.1:"+strconv.Itoa(p)); err == nil {
			return ln, true
		}
	}
	return nil, false
}

// handOver deals with another copy already running on the port. It returns the port to
// serve on when this copy takes over, or nil when the running copy stays (a window was
// opened on it).
func handOver(dir, other string) net.Listener {
	url := fmt.Sprintf("http://127.0.0.1:%d/", port)
	mine, theirs := revOf(version), revOf(other)
	if other == version || theirs > mine {
		log.Printf("%s is already running; opening a window on it", other)
		show(url, dir)
		return nil
	}
	if ln, ok := askToQuit(dir, port); ok {
		log.Printf("took over from %s", other)
		return ln
	}
	if theirs == mine { // the same revision built twice: keep the one that's running
		log.Printf("%s is already running; opening a window on it", other)
		show(url, dir)
		return nil
	}
	fail(fmt.Sprintf("An older copy of the app (%s) is still running, so %s can't start yet.\n\n"+
		"Close every Old School Jewelry Tray App window, then wait about 10 minutes for the old copy to stop. "+
		"To do it right away, open Task Manager and end \"OLD SCHOOL JEWELRY TRAY APP\".\n\n"+
		"Then open %s again.", other, revName(), revName()))
	return nil
}

// show opens an app window, or just prints the address when JTD_NO_WINDOW is set (tests).
func show(url, dir string) {
	if os.Getenv("JTD_NO_WINDOW") != "" {
		fmt.Println(url)
		return
	}
	openWindow(url, dir)
}
