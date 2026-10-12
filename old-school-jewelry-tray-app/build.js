// Makes the one file people copy to each shop computer:
//   OLD SCHOOL JEWELRY TRAY APP REV <n>.html
// = src/app.html + src/core.js + the WOODWOP templates in templates/ (listed in templates.json)
//   + the Jewelry Trays Direct logo, if assets/logo.png (or .jpg/.svg/.webp) exists.
// Then, if Go is installed, builds the stand-alone Windows program
//   OLD SCHOOL JEWELRY TRAY APP REV <n>.exe  (desktop/ + the same page).
// <n> is "revision" in package.json: raise it by 1 for every new build people get, and add
// a line for it under "Revisions" in README.md.
'use strict';
const fs = require('fs');
const path = require('path');

const here = __dirname;
const pkg = JSON.parse(fs.readFileSync(path.join(here, 'package.json'), 'utf8'));
if (!Number.isInteger(pkg.revision) || pkg.revision < 1) throw new Error('package.json needs "revision": a whole number');
const iso = new Date().toISOString().slice(0, 10);
const rev = { rev: pkg.revision, date: iso.slice(5, 7) + '/' + iso.slice(8, 10) + '/' + iso.slice(0, 4) };
const base = 'OLD SCHOOL JEWELRY TRAY APP REV ' + rev.rev;
const html = fs.readFileSync(path.join(here, 'src', 'app.html'), 'utf8');
const core = fs.readFileSync(path.join(here, 'src', 'core.js'), 'utf8');
const tag = '<script src="core.js"></script>';
const marker = '/*BUILTIN_TEMPLATES*/null';

if (!html.includes(tag)) throw new Error('src/app.html is missing ' + tag);
if (!html.includes(marker)) throw new Error('src/app.html is missing ' + marker);
if (!html.includes('/*REV*/null')) throw new Error('src/app.html is missing /*REV*/null');
if (/<\/script/i.test(core)) throw new Error('src/core.js must not contain a closing script tag');

const list = JSON.parse(fs.readFileSync(path.join(here, 'templates', 'templates.json'), 'utf8'));
const builtin = {};
for (const h of Object.keys(list)) {
  const bytes = fs.readFileSync(path.join(here, 'templates', list[h].file));
  builtin[h] = { name: list[h].file, saved: list[h].saved, b64: bytes.toString('base64') };
}

const types = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', svg: 'image/svg+xml', webp: 'image/webp' };
const logoFile = Object.keys(types).map(ext => path.join(here, 'assets', 'logo.' + ext)).find(f => fs.existsSync(f));
const logo = logoFile
  ? 'data:' + types[path.extname(logoFile).slice(1)] + ';base64,' + fs.readFileSync(logoFile).toString('base64')
  : null;

const out = html
  .replace(tag, () => '<script>\n' + core + '</script>')
  .replace(marker, () => JSON.stringify(builtin))
  .replace('/*LOGO*/null', () => JSON.stringify(logo))
  .replace('/*REV*/null', () => JSON.stringify(rev));

// Only the current revision is kept here, so nobody copies an old one by mistake.
for (const name of fs.readdirSync(here)) {
  if (/^OLD SCHOOL JEWELRY TRAY APP( REV \d+)?\.(html|exe)$/.test(name) && !name.startsWith(base + '.')) {
    fs.unlinkSync(path.join(here, name));
    console.log('Removed old ' + name);
  }
}
const file = path.join(here, base + '.html');
fs.writeFileSync(file, out);
console.log('Wrote ' + path.relative(process.cwd(), file) + ' (' + Math.round(out.length / 1024) + ' KB, templates: ' +
  Object.keys(builtin).map(h => h + '"').join(', ') + ', logo: ' + (logoFile ? path.basename(logoFile) : 'none yet') + ')');

// The stand-alone Windows program (desktop/) carries the same page inside it.
fs.writeFileSync(path.join(here, 'desktop', 'app.html'), out);
const { execFileSync } = require('child_process');
let go = null;
try { execFileSync('go', ['version'], { stdio: 'ignore' }); go = 'go'; } catch (e) { /* no Go here: skip the .exe */ }
if (go) {
  const ver = 'REV ' + rev.rev + ' (' + iso + ')';
  const exe = path.join(here, base + '.exe');
  const desktop = path.join(here, 'desktop');
  // The icon and the file details Windows shows (Properties > Details), with the REV in them.
  try {
    execFileSync(go, ['run', 'github.com/tc-hib/go-winres@v0.3.3', 'simply', '--icon', '../assets/icon.png', '--manifest', 'gui',
      '--product-name', 'Old School Jewelry Tray App', '--file-description', 'Old School Jewelry Tray App REV ' + rev.rev,
      '--copyright', 'Jewelry Trays Direct', '--product-version', rev.rev + '.0.0', '--file-version', rev.rev + '.0.0',
      '--original-filename', base + '.exe'], { cwd: desktop, stdio: 'ignore', timeout: 240000 });
    for (const extra of ['rsrc_windows_386.syso', 'rsrc_windows_arm64.syso']) fs.rmSync(path.join(desktop, extra), { force: true });
  } catch (e) {
    console.log('go-winres not reachable: kept the program details already in desktop/rsrc_windows_amd64.syso');
  }
  execFileSync(go, ['build', '-trimpath', '-ldflags', '-H=windowsgui -X "main.version=' + ver + '"', '-o', exe, '.'], {
    cwd: desktop,
    env: Object.assign({}, process.env, { GOOS: 'windows', GOARCH: 'amd64', CGO_ENABLED: '0' }),
    stdio: 'inherit'
  });
  console.log('Wrote ' + path.relative(process.cwd(), exe) + ' (' + Math.round(fs.statSync(exe).size / 1024 / 1024 * 10) / 10 + ' MB, version ' + ver + ')');
} else {
  console.log('Go not found: skipped ' + base + '.exe');
}
