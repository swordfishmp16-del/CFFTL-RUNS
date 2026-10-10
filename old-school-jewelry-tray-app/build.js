// Makes the one file people copy to each shop computer:
//   OLD SCHOOL JEWELRY TRAY APP.html
// = src/app.html + src/core.js + the WOODWOP templates in templates/ (listed in templates.json)
//   + the Jewelry Trays Direct logo, if assets/logo.png (or .jpg/.svg/.webp) exists.
'use strict';
const fs = require('fs');
const path = require('path');

const here = __dirname;
const html = fs.readFileSync(path.join(here, 'src', 'app.html'), 'utf8');
const core = fs.readFileSync(path.join(here, 'src', 'core.js'), 'utf8');
const tag = '<script src="core.js"></script>';
const marker = '/*BUILTIN_TEMPLATES*/null';

if (!html.includes(tag)) throw new Error('src/app.html is missing ' + tag);
if (!html.includes(marker)) throw new Error('src/app.html is missing ' + marker);
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
  .replace('/*LOGO*/null', () => JSON.stringify(logo));
const file = path.join(here, 'OLD SCHOOL JEWELRY TRAY APP.html');
fs.writeFileSync(file, out);
console.log('Wrote ' + path.relative(process.cwd(), file) + ' (' + Math.round(out.length / 1024) + ' KB, templates: ' +
  Object.keys(builtin).map(h => h + '"').join(', ') + ', logo: ' + (logoFile ? path.basename(logoFile) : 'none yet') + ')');
