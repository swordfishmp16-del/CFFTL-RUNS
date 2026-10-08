// Makes the one file people copy to each shop computer:
//   OLD SCHOOL JEWELRY TRAY APP.html
// = src/app.html + src/core.js + the WOODWOP templates in templates/ (listed in templates.json).
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

const out = html
  .replace(tag, () => '<script>\n' + core + '</script>')
  .replace(marker, () => JSON.stringify(builtin));
const file = path.join(here, 'OLD SCHOOL JEWELRY TRAY APP.html');
fs.writeFileSync(file, out);
console.log('Wrote ' + path.relative(process.cwd(), file) + ' (' + Math.round(out.length / 1024) + ' KB, templates: ' +
  Object.keys(builtin).map(h => h + '"').join(', ') + ')');
