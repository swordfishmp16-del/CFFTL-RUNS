// OLD SCHOOL JEWELRY TRAY APP - stand-alone Windows program.
//
// Double-click the .exe: it opens the app in its own window (Edge or Chrome app mode)
// and lets the app save the day's board files straight into a folder the person picks
// on their computer. The L: drive is always refused (see folders.go); people move the
// finished folders to L: themselves. Nothing is sent over the internet: the program only
// listens on this computer (127.0.0.1).
package main

import (
	"bytes"
	"crypto/rand"
	_ "embed"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
)

//go:embed app.html
var appHTML []byte

// A fixed port keeps the app's remembered settings (last order, stock sizes) between runs.
const port = 47391

var version = "dev"

type settings struct {
	SaveFolder string `json:"saveFolder"`
}

type server struct {
	mu       sync.Mutex
	token    string
	dir      string
	set      settings
	lastPing time.Time
	started  time.Time
	hostOK   map[string]bool
}

func main() {
	dir := settingsDir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		fail("Can't make the settings folder " + dir + ": " + err.Error())
	}
	if f, err := os.OpenFile(filepath.Join(dir, "app.log"), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644); err == nil {
		log.SetOutput(f)
	}

	ln, err := net.Listen("tcp", "127.0.0.1:"+strconv.Itoa(port))
	if err != nil {
		// Another copy is already running (see instance.go): the newer revision wins.
		if other, ok := runningVersion(port); ok {
			if ln = handOver(dir, other); ln == nil {
				return
			}
		} else if ln, err = net.Listen("tcp", "127.0.0.1:0"); err != nil {
			fail("Can't start: " + err.Error())
		}
	}
	p := ln.Addr().(*net.TCPAddr).Port
	s := &server{token: newToken(), dir: dir, started: time.Now(), hostOK: map[string]bool{
		fmt.Sprintf("127.0.0.1:%d", p): true, fmt.Sprintf("localhost:%d", p): true,
	}}
	s.load()
	s.writeInstance(p)
	url := fmt.Sprintf("http://127.0.0.1:%d/", p)
	log.Printf("version %s listening on %s", version, url)
	go s.watchdog()
	if os.Getenv("JTD_NO_WINDOW") == "" {
		// Any app window still open now has no program behind it (left from before the
		// computer slept, or from an older revision); an old one would still print the old
		// layout, so close them before opening this copy's window.
		if n := closeStaleWindows(); n > 0 {
			log.Printf("closed %d old app window(s)", n)
		}
	}
	show(url, dir)
	if err := http.Serve(ln, s.routes()); err != nil {
		fail(err.Error())
	}
}

func fail(msg string) {
	log.Print(msg)
	if os.Getenv("JTD_NO_WINDOW") != "" { // tests: no message box to click
		fmt.Fprintln(os.Stderr, msg)
	} else {
		showError(msg)
	}
	os.Exit(1)
}

func newToken() string {
	b := make([]byte, 24)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	return hex.EncodeToString(b)
}

// The window pings every 15 seconds. Once it has been closed for 10 minutes the program
// exits, so nothing is left running in the background. (Generous, because Windows slows
// timers in a minimized window.)
func (s *server) watchdog() {
	prev := time.Now()
	for range time.Tick(15 * time.Second) {
		now := time.Now()
		s.mu.Lock()
		if now.Sub(prev) > 2*time.Minute {
			// The computer was asleep, so the window couldn't ping. Give it time to ping
			// again instead of quitting under a window that is still open (10/11/2026).
			s.lastPing = now
		}
		prev = now
		stop := shouldStop(now, s.lastPing, s.started)
		s.mu.Unlock()
		if stop {
			s.exit("window closed, exiting")
		}
	}
}

func (s *server) load() {
	b, err := os.ReadFile(filepath.Join(s.dir, "settings.json"))
	if err == nil {
		_ = json.Unmarshal(b, &s.set)
	}
}

func (s *server) save() error {
	b, _ := json.MarshalIndent(s.set, "", "  ")
	return os.WriteFile(filepath.Join(s.dir, "settings.json"), b, 0o644)
}

func (s *server) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/", s.page)
	mux.HandleFunc("/api/info", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, map[string]string{"app": "jtd", "version": version})
	})
	api := map[string]func(*http.Request) (any, error){
		"/api/ping":        s.ping,
		"/api/settings":    s.settings,
		"/api/pick-folder": s.pickFolder,
		"/api/set-folder":  s.setFolder,
		"/api/save":        s.saveFiles,
		"/api/open-folder": s.openFolder,
		"/api/quit":        s.quit,
	}
	for path, fn := range api {
		fn := fn
		mux.HandleFunc(path, func(w http.ResponseWriter, r *http.Request) {
			// Only the app's own page may call these: it has the secret token. Other web
			// pages can't read it, and the custom header blocks cross-site requests.
			if r.Method != http.MethodPost || r.Header.Get("X-JTD-Token") != s.token {
				http.Error(w, "forbidden", http.StatusForbidden)
				return
			}
			r.Body = http.MaxBytesReader(w, r.Body, 64<<20)
			out, err := fn(r)
			if err != nil {
				writeJSON(w, map[string]string{"error": err.Error()})
				return
			}
			writeJSON(w, out)
		})
	}
	return s.guard(mux)
}

// guard refuses requests that don't come to this computer's own address (stops other
// web pages reaching the program through a look-alike host name).
func (s *server) guard(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !s.hostOK[r.Host] {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}
		h.ServeHTTP(w, r)
	})
}

func (s *server) page(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	native, _ := json.Marshal(map[string]string{"token": s.token, "version": version})
	body := bytes.Replace(appHTML, []byte("/*NATIVE*/null"), native, 1)
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Frame-Options", "DENY")
	_, _ = w.Write(body)
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	_ = json.NewEncoder(w).Encode(v)
}

func readJSON(r *http.Request, v any) error {
	b, err := io.ReadAll(r.Body)
	if err != nil {
		return errors.New("the request was too big or broken")
	}
	if len(bytes.TrimSpace(b)) == 0 {
		return nil
	}
	return json.Unmarshal(b, v)
}

func (s *server) ping(*http.Request) (any, error) {
	s.mu.Lock()
	s.lastPing = time.Now()
	s.mu.Unlock()
	return map[string]any{"ok": true, "version": version}, nil
}

// quit is how a newer revision takes over (see askToQuit). It needs this copy's token.
func (s *server) quit(*http.Request) (any, error) {
	go func() {
		time.Sleep(200 * time.Millisecond) // let the answer go out first
		s.exit("a newer copy took over, exiting")
	}()
	return map[string]bool{"ok": true}, nil
}

func (s *server) folderState() map[string]string {
	out := map[string]string{"saveFolder": s.set.SaveFolder}
	if s.set.SaveFolder != "" {
		if _, err := validateFolder(s.set.SaveFolder); err != nil {
			out["problem"] = err.Error()
		}
	}
	return out
}

func (s *server) settings(*http.Request) (any, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.folderState(), nil
}

func (s *server) pickFolder(*http.Request) (any, error) {
	s.mu.Lock()
	start := s.set.SaveFolder
	s.mu.Unlock()
	path, cancelled, err := pickFolder(start)
	if err != nil {
		return nil, err
	}
	if cancelled {
		return map[string]bool{"cancelled": true}, nil
	}
	return s.useFolder(path)
}

func (s *server) setFolder(r *http.Request) (any, error) {
	var in struct{ Path string }
	if err := readJSON(r, &in); err != nil {
		return nil, err
	}
	return s.useFolder(in.Path)
}

// useFolder checks the folder (never L:), makes it if needed, and remembers it.
func (s *server) useFolder(path string) (any, error) {
	clean, err := validateFolder(path)
	if err != nil {
		return nil, err
	}
	if err := os.MkdirAll(clean, 0o755); err != nil {
		return nil, fmt.Errorf("can't use %s: %v", clean, err)
	}
	if err := recheckReal(clean); err != nil { // a shortcut folder that really points into L:
		return nil, err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.set.SaveFolder = clean
	if err := s.save(); err != nil {
		return nil, fmt.Errorf("can't remember the folder: %v", err)
	}
	return s.folderState(), nil
}

type saveFile struct {
	Name string `json:"name"`
	Data string `json:"data"` // base64
}

// saveFiles writes the day's files into <save folder>\<day folder>.
// mode "new": a new day folder each time (adds " (2)" if the name is taken).
// mode "add": into the day folder, made if missing (for a single board).
// An existing file is never overwritten: the new one gets " (2)" added.
func (s *server) saveFiles(r *http.Request) (any, error) {
	var in struct {
		DayFolder string     `json:"dayFolder"`
		Mode      string     `json:"mode"`
		Files     []saveFile `json:"files"`
	}
	if err := readJSON(r, &in); err != nil {
		return nil, err
	}
	s.mu.Lock()
	base := s.set.SaveFolder
	s.mu.Unlock()
	if base == "" {
		return nil, errors.New("pick a save folder first (step 1)")
	}
	base, err := validateFolder(base)
	if err != nil {
		return nil, err
	}
	if err := recheckReal(base); err != nil {
		return nil, err
	}
	if len(in.Files) == 0 {
		return nil, errors.New("nothing to save")
	}
	day := safeName(in.DayFolder)
	target := filepath.Join(base, day)
	if in.Mode == "new" {
		target = uniquePath(base, day)
	}
	if err := os.MkdirAll(target, 0o755); err != nil {
		return nil, fmt.Errorf("can't make %s: %v", target, err)
	}
	var names []string
	for _, f := range in.Files {
		data, err := base64.StdEncoding.DecodeString(f.Data)
		if err != nil {
			return nil, fmt.Errorf("file %s is damaged", f.Name)
		}
		name, err := writeNew(target, safeName(f.Name), data)
		if err != nil {
			return nil, err
		}
		names = append(names, name)
	}
	log.Printf("saved %d files to %s", len(names), target)
	return map[string]any{"dir": target, "files": names}, nil
}

// uniquePath returns dir\name, or dir\name (2), (3)... if that already exists.
func uniquePath(dir, name string) string {
	p := filepath.Join(dir, name)
	for i := 2; exists(p); i++ {
		p = filepath.Join(dir, fmt.Sprintf("%s (%d)", name, i))
	}
	return p
}

// writeNew creates dir\name without ever replacing a file: "x.mpr" becomes "x (2).mpr".
func writeNew(dir, name string, data []byte) (string, error) {
	ext := filepath.Ext(name)
	stem := strings.TrimSuffix(name, ext)
	for i := 1; i < 1000; i++ {
		n := name
		if i > 1 {
			n = fmt.Sprintf("%s (%d)%s", stem, i, ext)
		}
		f, err := os.OpenFile(filepath.Join(dir, n), os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o644)
		if errors.Is(err, os.ErrExist) {
			continue
		}
		if err != nil {
			return "", fmt.Errorf("can't save %s: %v", n, err)
		}
		_, werr := f.Write(data)
		cerr := f.Close()
		if werr != nil || cerr != nil {
			return "", fmt.Errorf("can't save %s: %v", n, errors.Join(werr, cerr))
		}
		return n, nil
	}
	return "", fmt.Errorf("too many copies of %s", name)
}

func exists(p string) bool {
	_, err := os.Stat(p)
	return err == nil
}

// openFolder shows a folder in File Explorer. Only the save folder or folders inside it.
func (s *server) openFolder(r *http.Request) (any, error) {
	var in struct{ Path string }
	if err := readJSON(r, &in); err != nil {
		return nil, err
	}
	s.mu.Lock()
	base := s.set.SaveFolder
	s.mu.Unlock()
	path := in.Path
	if path == "" {
		path = base
	}
	if base == "" || !inside(path, base) {
		return nil, errors.New("can only open the save folder")
	}
	openFolder(path)
	return map[string]bool{"ok": true}, nil
}
