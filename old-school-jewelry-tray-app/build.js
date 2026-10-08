// Makes the one file people copy to each shop computer:
//   OLD SCHOOL JEWELRY TRAY APP.html  (src/app.html with src/core.js put inside it)
'use strict';
const fs = require('fs');
const path = require('path');

const here = __dirname;
const html = fs.readFileSync(path.join(here, 'src', 'app.html'), 'utf8');
const core = fs.readFileSync(path.join(here, 'src', 'core.js'), 'utf8');
const tag = '<script src="core.js"></script>';

if (!html.includes(tag)) throw new Error('src/app.html is missing ' + tag);
if (/<\/script/i.test(core)) throw new Error('src/core.js must not contain a closing script tag');

const out = html.replace(tag, () => '<script>\n' + core + '</script>');
const file = path.join(here, 'OLD SCHOOL JEWELRY TRAY APP.html');
fs.writeFileSync(file, out);
console.log('Wrote ' + path.relative(process.cwd(), file) + ' (' + Math.round(out.length / 1024) + ' KB)');
