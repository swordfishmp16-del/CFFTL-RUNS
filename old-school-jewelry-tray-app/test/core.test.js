'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const os = require('node:os');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const J = require('../src/core.js');
const { makeTemplate, SAMPLE_CSV } = require('./helpers.js');

const T2 = () => J.parseTemplate(makeTemplate(16, 49.21), '_2 TALL DAILY TRAY TEMPLATE.mpr');
const T3 = () => J.parseTemplate(makeTemplate(12, 73.03), '_3 TALL DAILY TRAY TEMPLATE.mpr');

function tray(order, w, d, h, qty, extra) {
  return Object.assign({
    id: 'x' + order, source: 'hand', orderNumber: String(order), name: '', title: '',
    qty: qty || 1, widthText: w, depthText: d, height: h || 2, label: String(order),
    include: true, kind: 'custom', reason: '', warnings: []
  }, extra);
}

test('reads Shopify fraction sizes', () => {
  assert.equal(J.parseInches('21 5/16'), 21.3125);
  assert.equal(J.parseInches('21-5/16'), 21.3125);
  assert.equal(J.parseInches('24 7/8"'), 24.875);
  assert.equal(J.parseInches('13.375'), 13.375);
  assert.equal(J.parseInches('28'), 28);
  assert.equal(J.parseInches('3/4'), 0.75);
  assert.equal(J.parseInches(''), null);
  assert.equal(J.parseInches('abc'), null);
  assert.equal(J.parseInches('21 5/0'), null);
});

test('WOODWOP mm = full size converted (HANDOFF example 2 and stock board)', () => {
  assert.equal(J.mm2(J.inToMm(21.3125)), '541.34');
  assert.equal(J.mm2(J.inToMm(14.125)), '358.78');
  assert.equal(J.mm2(J.inToMm(27.375)), '695.33');
  assert.equal(J.mm2(J.inToMm(34)), '863.60');
  assert.equal(J.mm2(J.inToMm(13.375)), '339.73');
  assert.equal(J.mm2(J.inToMm(31.3125)), '795.34');
  assert.equal(J.mm2(J.inToMm(19.75)), '501.65');
});

test('bottoms = size minus 9/16" (HANDOFF example 1 and 2)', () => {
  assert.equal(J.mm2(J.bottomMm(14.75)), '360.36');
  assert.equal(J.mm2(J.bottomMm(19.625)), '484.19');
  assert.equal(J.mm2(J.bottomMm(21.3125)), '527.05');
  assert.equal(J.mm2(J.bottomMm(14.125)), '344.49');
});

test('strip length and cut lines match HANDOFF worked examples', () => {
  const a = J.strip(541.34, 358.78, 4.76);
  assert.equal(a.length, 1821.2);
  assert.deepEqual(a.cuts, [20, 556.58, 910.6, 1447.18, 1801.2]);
  const b = J.strip(360.36, 484.19, 4.76);
  assert.equal(b.length, 1710.06);
  assert.deepEqual(b.cuts, [20, 375.6, 855.03, 1210.63, 1690.06]);
  assert.equal(J.strip(863.6, 339.73, 4.76).length, 2427.62);
});

test('inches shown as shop fractions', () => {
  assert.equal(J.inchesText(21.3125), '21 5/16');
  assert.equal(J.inchesText(13.375), '13 3/8');
  assert.equal(J.inchesText(28), '28');
});

test('template reading finds slots, tray height and velvet allowance', () => {
  const t2 = T2(), t3 = T3();
  assert.equal(t2.slots, 16);
  assert.equal(t2.th, 49.21);
  assert.equal(t2.heightClass, 2);
  assert.equal(t2.pitch, 76);
  assert.equal(t3.slots, 12);
  assert.equal(t3.heightClass, 3);
  assert.equal(t3.pitch, 101);
  assert.equal(t2.v, 4.76);
  assert.equal(t2.l, 2438);
  assert.throws(() => J.parseTemplate('hello'), /not a WOODWOP/);
});

test('filling a template changes only tray values and keeps every other byte', () => {
  const bin = makeTemplate(16, 49.21);
  const slots = [];
  for (let i = 1; i <= 12; i++) slots.push({ slot: i, wMm: 500 + i, dMm: 300 + i });
  const out = J.fillTemplate(bin, slots);

  assert.match(out, /\r\ntr1w="501.00"\r\nKM="tray 1 width"\r\ntr1d="301.00"\r\n/);
  assert.match(out, /\r\ntr10w="510.00"\r\n/);
  assert.match(out, /\r\ntr12d="312.00"\r\n/);
  assert.match(out, /\r\ntr13w="102"\r\n/, 'empty slots keep the 102 placeholder');
  assert.match(out, /\r\ntr16d="102"\r\n/);
  assert.match(out, /X=tr1w\+tr1d\+tr1w\+tr1d\+40-\(v\*4\)/, 'contour formulas untouched');
  assert.ok(out.includes('KAT="Fräsen"'), 'Latin-1 byte survives');

  // Put the original values back: the result must be byte-identical to the template.
  const back = out.replace(/^tr(\d+)([wd])="[^"]*"/gm, (_, n, wd) => `tr${n}${wd}="102"`);
  assert.equal(back, bin);

  const bytes = J.binToBytes(out);
  assert.equal(J.bytesToBin(bytes), out);
});

test('Shopify export becomes tray rows with the right defaults', () => {
  const items = J.readShopifyCsv(SAMPLE_CSV);
  assert.equal(items.length, 8);
  assert.equal(items[1].name, 'Standard Jewelry Tray - Blush / Small 22"W x 13 3/8"D');

  const trays = J.traysFromItems(items);
  const byOrder = (n, title) => trays.find(t => t.orderNumber === n && (!title || t.title === title));
  assert.deepEqual(trays.map(t => t.orderNumber), ['4354', '4355', '4356', '4356', '4357', '4358', '4359', '4360']);

  const custom = byOrder('4354');
  assert.equal(custom.include, true);
  assert.equal(custom.qty, 3);

  const stock = byOrder('4357');
  assert.equal(stock.include, false);
  assert.equal(stock.kind, 'stock');
  assert.equal(stock.widthText, '22');
  assert.equal(stock.depthText, '13 3/8');

  assert.equal(byOrder('4355').include, false);
  assert.equal(byOrder('4356', 'Tray Measurement Charge').include, false);
  assert.equal(byOrder('4360').reason, 'Flat liner (no sides)');

  const blankHeight = byOrder('4359');
  assert.equal(blankHeight.height, 2);
  assert.equal(blankHeight.widthText, '24 7/8"');
  assert.match(blankHeight.warnings[0], /blank/);

  assert.throws(() => J.readShopifyCsv('a,b\n1,2'), /Missing column/);
});

test('a blank order number on a later line of the same order is filled in', () => {
  const csv = [
    'Order ID,Order Number,Lineitem Name,Lineitem Quantity,Lineitem Title,Width,Height,Depth',
    '77,#5001,Standard Jewelry Tray,1,Standard Jewelry Tray,20,2,12',
    '77,,Earrings Tray,1,Earrings Tray,18,2,12',
    '78,,Plain Tray,1,Plain Tray,16,2,12'
  ].join('\n');
  assert.deepEqual(J.readShopifyCsv(csv).map(i => i.orderNumber), ['5001', '5001', '']);
});

test('extra-height charge warns when the tray still says 2"', () => {
  const csv = [
    'Order ID,Order Number,Lineitem Name,Lineitem Quantity,Lineitem Title,Width,Height,Depth',
    '1,5000,Standard Jewelry Tray,1,Standard Jewelry Tray,20,2,12',
    '1,5000,"Tray Measurement Charge - Extra Tray Height (3"")",1,Tray Measurement Charge,,,'
  ].join('\n');
  const t = J.traysFromItems(J.readShopifyCsv(csv))[0];
  assert.match(t.warnings.join(' '), /Extra Tray Height \(3"\)/);
});

test('boards: 16 per 2" board, 12 per 3" board, never mixed, numbered in order', () => {
  const trays = [
    tray(4354, '21 5/16', '14 1/8', 2, 20),
    tray(4391, '20', '12', 3, 13),
    tray(4400, '20', '12', 5, 1),
    tray(4401, '50', '30', 2, 1)
  ];
  const plan = J.planBoards(trays, { 2: T2(), 3: T3() }, { date: '100226', startNumber: 1 });
  assert.deepEqual(plan.boards.map(b => [b.fileName, b.slots.length]), [
    ['100226 DAILY TRAYS 1.mpr', 16],
    ['100226 DAILY TRAYS 2.mpr', 4],
    ['100226 DAILY TRAYS 3 3IN.mpr', 12],
    ['100226 DAILY TRAYS 4 3IN.mpr', 1]
  ]);
  assert.ok(plan.boards.every(b => b.slots.every(s => s.tray.height === b.height)));
  assert.equal(plan.boards[0].slots[0].wMm, 541.34);
  assert.equal(plan.boards[0].slots[0].dMm, 358.78);
  assert.deepEqual(plan.unassigned.map(u => u.tray.orderNumber), ['4400', '4401']);
  assert.match(plan.unassigned[0].reason, /5" trays/);
  assert.match(plan.unassigned[1].reason, /Too long/);
  assert.equal(plan.folder, '100226 DAILY TRAYS #4354-4391');
});

test('boards: missing template and unreadable size are reported, not dropped', () => {
  const plan = J.planBoards([tray(1, '20', '12', 3), tray(2, 'abc', '12', 2)], { 2: T2(), 3: null }, { date: '100226' });
  assert.equal(plan.boards.length, 0);
  assert.match(plan.unassigned[0].reason, /Load the 3" template/);
  assert.equal(plan.unassigned[1].reason, 'Size not readable');
});

test('bottoms list follows the daily sheet columns', () => {
  const rows = J.bottomRows([tray(4354, '21 5/16', '14 1/8', 2, 3), tray(9, '20', '12', 2, 1, { include: false })]);
  assert.equal(rows.length, 1);
  const csv = J.bottomsCsv(rows);
  assert.equal(csv,
    'DESCRIPTION,PART TYPE,UNIT #,MATERIAL,QTY,WIDTH,DEPTH,GRAIN,COMPANY\r\n' +
    '4354,TRAY BOTTOM,4354,1/4 MELAMINE,3,527.05,344.49,N,JEWELRY TRAYS DIRECT\r\n');
});

test('MMDDYY file date', () => {
  assert.equal(J.mmddyy('2026-10-02'), '100226');
  assert.equal(J.mmddyy(''), '');
});

test('zip opens in a standard unzip tool with every byte intact', () => {
  const mpr = J.binToBytes(makeTemplate(16, 49.21));
  const csv = new TextEncoder().encode('a,b\r\n1,2\r\n');
  const zip = J.makeZip([
    { name: '100226 DAILY TRAYS #4354-4391/100226 DAILY TRAYS 1.mpr', data: mpr },
    { name: '100226 DAILY TRAYS #4354-4391/100226 TRAY BOTTOMS.csv', data: csv }
  ]);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'jtdzip-'));
  const file = path.join(dir, 'boards.zip');
  fs.writeFileSync(file, zip);
  const out = execFileSync('python3', ['-I', '-c',
    'import sys,zipfile,hashlib\n' +
    'z=zipfile.ZipFile(sys.argv[1])\n' +
    'assert z.testzip() is None\n' +
    'for i in z.infolist(): print(i.filename, i.file_size, hashlib.sha256(z.read(i)).hexdigest())',
    file]).toString();
  const crypto = require('node:crypto');
  const sha = b => crypto.createHash('sha256').update(b).digest('hex');
  assert.equal(out,
    `100226 DAILY TRAYS #4354-4391/100226 DAILY TRAYS 1.mpr ${mpr.length} ${sha(mpr)}\n` +
    `100226 DAILY TRAYS #4354-4391/100226 TRAY BOTTOMS.csv ${csv.length} ${sha(csv)}\n`);
  fs.rmSync(dir, { recursive: true, force: true });
});
