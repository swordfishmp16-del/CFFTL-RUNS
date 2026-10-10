// OLD SCHOOL JEWELRY TRAY APP - core rules (no screen code here).
// Works in the browser (window.JTD) and in Node (require) so the rules can be tested.
// Every rule below comes from docs/HANDOFF.md; section numbers are noted.
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.JTD = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // Bottoms are the tray size minus 9/16" (HANDOFF 5.1, daily sheet A61).
  var BOTTOM_DEDUCT_IN = 0.5625;

  // Strip pitch on the board (HANDOFF 5.5): 76 mm on _2 TALL, 101 mm on _3 TALL.
  var FIRST_STRIP_Y = 8;

  // Line items that never get sides cut (HANDOFF 2). Matched against Lineitem Title.
  var NOT_A_TRAY = [
    ['flat liner', 'Flat liner (no sides)'],
    ['tray insert', 'Insert (goes inside a tray)'],
    ['watch pillow', 'Add-on'],
    ['ring cushion', 'Add-on'],
    ['measurement charge', 'Charge, not a tray']
  ];

  // Standard (stock) trays: 13 3/8" deep, 21-34" wide (HANDOFF 4, STOCK 21IN-34IN boards).
  var STOCK_SIZES = [21, 22, 27, 28, 33, 34].map(function (w) {
    return { name: 'STOCK ' + w + 'IN', w: w, d: 13.375 };
  });

  // ---------- sizes ----------

  // "21 5/16", "21-5/16", "24 7/8\"", "13.375", "28" -> inches as a number. Bad text -> null.
  function parseInches(raw) {
    if (raw == null) return null;
    var s = String(raw).trim()
      .replace(/[″“”"]/g, '')
      .replace(/\s*(inches|inch|in)\.?$/i, '')
      .trim();
    if (!s) return null;
    var m;
    if (/^\d+(\.\d+)?$/.test(s) || /^\.\d+$/.test(s)) return parseFloat(s);
    m = s.match(/^(\d+)(?:\s+|\s*-\s*)(\d+)\s*\/\s*(\d+)$/);
    if (m) return +m[3] ? +m[1] + +m[2] / +m[3] : null;
    m = s.match(/^(\d+)\s*\/\s*(\d+)$/);
    if (m) return +m[2] ? +m[1] / +m[2] : null;
    return null;
  }

  // Inches -> mm rounded to 2 decimals (HANDOFF 5.1 E/G block + 5.3).
  // x * 2540 / 100 instead of x * 25.4 keeps 1/16" sizes exact, so 13.375 -> 339.73 like Excel.
  function inToMm(inches) {
    return Math.round(inches * 2540) / 100;
  }

  // Bottom size in mm: (inches - 0.5625) * 25.4, 2 decimals (HANDOFF 5.1 M/N block).
  function bottomMm(inches) {
    return Math.round((inches - BOTTOM_DEDUCT_IN) * 2540) / 100;
  }

  function mm2(x) {
    return x.toFixed(2);
  }

  // 21.3125 -> "21 5/16" for display. Rounds to the nearest 1/64.
  function inchesText(x) {
    if (x == null || isNaN(x)) return '';
    var whole = Math.floor(x + 1e-9);
    var n = Math.round((x - whole) * 64);
    if (n === 64) { whole += 1; n = 0; }
    if (!n) return String(whole);
    var d = 64;
    while (n % 2 === 0) { n /= 2; d /= 2; }
    return whole + ' ' + n + '/' + d;
  }

  // ---------- Shopify CSV ----------

  function parseCsv(text) {
    var rows = [], row = [], field = '', i = 0, q = false, c;
    text = String(text).replace(/^﻿/, '');
    while (i < text.length) {
      c = text[i];
      if (q) {
        if (c === '"') {
          if (text[i + 1] === '"') { field += '"'; i += 2; continue; }
          q = false; i++; continue;
        }
        field += c; i++; continue;
      }
      if (c === '"') { q = true; i++; continue; }
      if (c === ',') { row.push(field); field = ''; i++; continue; }
      if (c === '\r') { i++; continue; }
      if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; i++; continue; }
      field += c; i++;
    }
    if (field !== '' || row.length) { row.push(field); rows.push(row); }
    return rows.filter(function (r) { return r.some(function (f) { return f.trim() !== ''; }); });
  }

  // Shopify export header (HANDOFF 10.10):
  // Order ID,Order Number,Lineitem Name,Lineitem Quantity,Lineitem Title,Width,Height,Depth
  function readShopifyCsv(text) {
    var rows = parseCsv(text);
    if (!rows.length) throw new Error('The file is empty.');
    var head = rows[0].map(function (h) { return h.trim().toLowerCase(); });
    function col(name) { return head.indexOf(name); }
    var c = {
      id: col('order id'), num: col('order number'), name: col('lineitem name'),
      qty: col('lineitem quantity'), title: col('lineitem title'),
      w: col('width'), h: col('height'), d: col('depth')
    };
    var missing = [];
    if (c.num < 0) missing.push('Order Number');
    if (c.name < 0) missing.push('Lineitem Name');
    if (c.w < 0) missing.push('Width');
    if (c.d < 0) missing.push('Depth');
    if (missing.length) {
      throw new Error('This does not look like the Shopify tray export. Missing column(s): ' + missing.join(', ') + '.');
    }
    function get(r, i) { return i < 0 ? '' : (r[i] || '').trim(); }
    var prev = null;
    return rows.slice(1).map(function (r) {
      var id = get(r, c.id), num = get(r, c.num).replace(/^#/, '');
      // Some exports only print the order number on an order's first line.
      if (!num && prev && id && id === prev.orderId) num = prev.orderNumber;
      return prev = {
        orderId: id,
        orderNumber: num,
        name: get(r, c.name),
        qty: parseInt(get(r, c.qty), 10) || 1,
        title: get(r, c.title),
        rawW: get(r, c.w),
        rawH: get(r, c.h),
        rawD: get(r, c.d)
      };
    });
  }

  // 'Small 22"W x 13 3/8"D' -> {w: 22, d: 13.375}
  function sizeFromName(name) {
    var m = String(name).match(/(\d+(?:\.\d+)?(?:\s+\d+\/\d+)?)\s*"?\s*W\s*x\s*(\d+(?:\.\d+)?(?:\s+\d+\/\d+)?)\s*"?\s*D/i);
    if (!m) return null;
    var w = parseInches(m[1]), d = parseInches(m[2]);
    return w && d ? { w: w, d: d } : null;
  }

  // Turns Shopify line items into tray rows the screen can edit.
  // include=false rows stay visible with a reason so nothing disappears silently.
  function traysFromItems(items) {
    var extraHeight = {};
    items.forEach(function (it) {
      if (/measurement charge/i.test(it.title) && /height/i.test(it.name)) {
        var m = it.name.match(/\((\d+)\s*"?\s*\)/);
        extraHeight[it.orderNumber] = m ? +m[1] : true;
      }
    });

    var trays = items.map(function (it, idx) {
      var t = {
        id: 'csv' + idx,
        source: 'csv',
        orderNumber: it.orderNumber,
        name: it.name,
        title: it.title,
        qty: it.qty,
        widthText: it.rawW,
        depthText: it.rawD,
        height: parseInt(it.rawH, 10) || null,
        label: it.orderNumber,
        include: true,
        kind: 'custom',
        reason: '',
        warnings: []
      };
      var low = (it.title || it.name).toLowerCase();
      for (var i = 0; i < NOT_A_TRAY.length; i++) {
        if (low.indexOf(NOT_A_TRAY[i][0]) >= 0) {
          t.include = false; t.kind = 'addon'; t.reason = NOT_A_TRAY[i][1];
          return t;
        }
      }
      if (!it.rawW && !it.rawD) {
        var s = sizeFromName(it.name);
        if (s) {
          t.kind = 'stock';
          t.widthText = inchesText(s.w);
          t.depthText = inchesText(s.d);
          t.reason = 'Standard size';
        } else {
          t.kind = 'nosize';
          t.include = false;
          t.reason = 'No size on this line';
        }
      }
      if (!t.height) {
        t.height = 2;
        if (t.kind === 'custom') t.warnings.push('Height was blank, using 2"');
      }
      var eh = extraHeight[it.orderNumber];
      if (eh && t.kind !== 'addon' && t.height === 2) {
        t.warnings.push('Order has an Extra Tray Height' + (eh === true ? '' : ' (' + eh + '")') + ' charge: check the height');
      }
      return t;
    });

    // Lowest order number first, like the daily sheet; keeps file order inside an order.
    return trays
      .map(function (t, i) { return { t: t, i: i }; })
      .sort(function (a, b) {
        var na = parseInt(a.t.orderNumber, 10), nb = parseInt(b.t.orderNumber, 10);
        if (isNaN(na) || isNaN(nb) || na === nb) return a.i - b.i;
        return na - nb;
      })
      .map(function (x) { return x.t; });
  }

  // ---------- WOODWOP templates ----------

  function bytesToBin(u8) {
    var s = '';
    for (var i = 0; i < u8.length; i += 0x8000) {
      s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
    }
    return s;
  }

  function binToBytes(s) {
    var u = new Uint8Array(s.length);
    for (var i = 0; i < s.length; i++) u[i] = s.charCodeAt(i) & 0xff;
    return u;
  }

  // Finds the [001 variable table. The file is handled byte-for-byte (as a "binary string")
  // so German characters like the a-umlaut in "Fraesen" and the CRLF line ends survive.
  function varSection(bin) {
    var start = bin.search(/(^|\n)\[001/);
    if (start < 0) return null;
    if (bin[start] === '\n') start++;
    var rest = bin.slice(start + 4);
    var end = rest.search(/\n[\[\]<!]/);
    end = end < 0 ? bin.length : start + 4 + end + 1;
    return { start: start, end: end, text: bin.slice(start, end) };
  }

  function parseTemplate(bin, fileName) {
    var sec = varSection(bin);
    if (!sec) throw new Error('This is not a WOODWOP tray template: it has no variable table ([001).');
    var vars = {};
    sec.text.replace(/^([A-Za-z_]\w*)="([^"]*)"/gm, function (_, k, v) {
      if (k !== 'KM') vars[k] = v;
    });
    var slots = 0;
    while (('tr' + (slots + 1) + 'w') in vars && ('tr' + (slots + 1) + 'd') in vars) slots++;
    if (!slots) throw new Error('This template has no tray slots (tr1w / tr1d).');
    var bsx = (bin.match(/^_BSX=([\d.]+)/m) || [])[1];
    var bsy = (bin.match(/^_BSY=([\d.]+)/m) || [])[1];
    var t = {
      fileName: fileName || '',
      slots: slots,
      th: parseFloat(vars.th),
      v: parseFloat(vars.v),
      l: parseFloat(vars.l) || parseFloat(bsx) || 2438,
      w: parseFloat(vars.w) || parseFloat(bsy) || 1219.2,
      warnings: []
    };
    if (isNaN(t.th)) t.warnings.push('No tray height (th) found.');
    if (isNaN(t.v)) { t.warnings.push('No velvet allowance (v) found, using 4.76.'); t.v = 4.76; }
    if (/^INCH="1"/m.test(bin)) t.warnings.push('This file is set to inches (INCH="1"). The tray programs are metric.');
    t.heightClass = t.th < 60 ? 2 : t.th < 90 ? 3 : null;
    t.pitch = t.heightClass === 2 ? 76 : t.heightClass === 3 ? 101 : Math.floor((t.w - 2 * FIRST_STRIP_Y) / slots);
    return t;
  }

  // Puts tray sizes into a copy of the template. Only the value inside trNw="..."/trNd="..."
  // changes; KM comments, contours and macros are left alone. Exact names, so tr1 never
  // touches tr10-tr16 (HANDOFF 11 #4). Empty slots keep the template's 102 placeholder.
  function fillTemplate(bin, slots) {
    var sec = varSection(bin);
    if (!sec) throw new Error('Template has no variable table.');
    var bySlot = {};
    slots.forEach(function (s) { bySlot[s.slot] = s; });
    var text = sec.text.replace(/^tr(\d+)([wd])="[^"]*"/gm, function (all, n, wd) {
      var s = bySlot[+n];
      if (!s) return all;
      var val = wd === 'w' ? mm2(s.wMm) : s.dRaw != null ? s.dRaw : mm2(s.dMm);
      return 'tr' + n + wd + '="' + val + '"';
    });
    return bin.slice(0, sec.start) + text + bin.slice(sec.end);
  }

  // ---------- one tray strip (HANDOFF 5.5) ----------

  function strip(wMm, dMm, v) {
    var len = wMm + dMm + wMm + dMm + 40 - v * 4;
    var cuts = [20];
    [wMm, dMm, wMm, dMm].forEach(function (x) { cuts.push(cuts[cuts.length - 1] + (x - v)); });
    return {
      length: Math.round(len * 100) / 100,
      cuts: cuts.map(function (x) { return Math.round(x * 100) / 100; })
    };
  }

  // ---------- boards ----------

  // A tray too long for one strip is cut as two strips in side-by-side slots, the way
  // Mike did order 4356 on 10/2 (HANDOFF 11 #5, approved 10/8/2026):
  //   slot A: width  = tray width, depth = 102  -> gives the 2 width sides
  //   slot B: width  = tray depth, depth = 102  -> gives the 2 depth sides
  var SPLIT_FILL = '102';

  // Puts a pair in the next two slots. If only one slot is left on the board, the next
  // single tray in line fills it so no slot is wasted; if there is none, the slot stays empty.
  function packSlots(units, perBoard) {
    var boards = [], cur = null, pending = units.slice();
    function place(u) {
      u.slots.forEach(function (s) {
        s = Object.assign({}, s);
        s.slot = cur.length + 1;
        cur.push(s);
      });
    }
    while (pending.length) {
      if (!cur || cur.length >= perBoard) { cur = []; boards.push(cur); }
      var free = perBoard - cur.length;
      if (pending[0].slots.length <= free) { place(pending.shift()); continue; }
      var j = -1;
      for (var k = 0; k < pending.length; k++) if (pending[k].slots.length <= free) { j = k; break; }
      if (j >= 0) { place(pending.splice(j, 1)[0]); continue; }
      cur = null;
    }
    return boards;
  }

  // Splits the day's trays onto boards. 2" and 3" never share a board (HANDOFF 5.4).
  // Trays per board = slots in that template (16 on _2 TALL, 12 on _3 TALL).
  function planBoards(trays, templates, opts) {
    opts = opts || {};
    var date = opts.date || '';
    var n = opts.startNumber || 1;
    var unassigned = [];
    var split = [];
    var queues = { 2: [], 3: [] };
    var fillers = { 2: [], 3: [] };   // "Fill with stock" trays: only go into empty slots

    trays.forEach(function (t) {
      if (!t.include) return;
      var wIn = parseInches(t.widthText), dIn = parseInches(t.depthText);
      if (!wIn || !dIn) { unassigned.push({ tray: t, reason: 'Size not readable' }); return; }
      var h = t.height;
      if (h !== 2 && h !== 3) {
        unassigned.push({ tray: t, reason: 'No WOODWOP template for ' + h + '" trays: do by hand' });
        return;
      }
      var tpl = templates[h];
      if (!tpl) { unassigned.push({ tray: t, reason: 'Load the ' + h + '" template in Step 1' }); return; }
      var wMm = inToMm(wIn), dMm = inToMm(dIn);
      var label = t.label || t.orderNumber;
      var st = strip(wMm, dMm, tpl.v);
      var unit;
      if (st.length <= tpl.l) {
        unit = [{ tray: t, wIn: wIn, dIn: dIn, wMm: wMm, dMm: dMm, label: label, strip: st }];
      } else {
        var fill = parseFloat(SPLIT_FILL);
        var stW = strip(wMm, fill, tpl.v), stD = strip(dMm, fill, tpl.v);
        if (Math.max(stW.length, stD.length) > tpl.l || tpl.slots < 2) {
          unassigned.push({ tray: t, reason: 'Too long for the board even split in two: ' + mm2(Math.max(stW.length, stD.length)) + ' mm strip, board ' + tpl.l + ' mm' });
          return;
        }
        unit = [
          { tray: t, part: 'W', wIn: wIn, dIn: dIn, wMm: wMm, dMm: fill, dRaw: SPLIT_FILL, label: label, strip: stW },
          { tray: t, part: 'D', wIn: dIn, dIn: dIn, wMm: dMm, dMm: fill, dRaw: SPLIT_FILL, label: label, strip: stD }
        ];
        split.push({ tray: t, note: 'Too long for one strip: split into 2 slots (widths, then depths)' });
      }
      var qty = Math.max(1, t.qty | 0);
      for (var i = 0; i < qty; i++) (t.filler ? fillers[h] : queues[h]).push({ tray: t, slots: unit });
    });

    var boards = [];
    [2, 3].forEach(function (h) {
      if (!queues[h].length) return;
      var tpl = templates[h];
      packSlots(queues[h], tpl.slots).forEach(function (slots) {
        boards.push({
          number: n,
          height: h,
          template: tpl,
          fileName: date + ' DAILY TRAYS ' + n + (h === 3 ? ' 3IN' : '') + '.mpr',
          slots: slots
        });
        n++;
      });
    });

    // Stock fill never starts a board; it only takes slots the orders left empty.
    var fillerPlaced = {}, fillerUnused = {};
    [2, 3].forEach(function (h) {
      var left = fillers[h];
      boards.forEach(function (b) {
        if (b.height !== h) return;
        var k = 0;
        while (k < left.length && b.slots.length < b.template.slots) {
          var u = left[k];
          if (u.slots.length > b.template.slots - b.slots.length) { k++; continue; }
          u.slots.forEach(function (s) {
            s = Object.assign({}, s);
            s.slot = b.slots.length + 1;
            s.stock = true;
            b.slots.push(s);
          });
          fillerPlaced[u.tray.id] = (fillerPlaced[u.tray.id] || 0) + 1;
          left.splice(k, 1);
        }
      });
      left.forEach(function (u) { fillerUnused[u.tray.id] = (fillerUnused[u.tray.id] || 0) + 1; });
    });

    var orderNums = [];
    boards.forEach(function (b) {
      b.slots.forEach(function (s) {
        var x = parseInt(s.tray.orderNumber, 10);
        if (!isNaN(x)) orderNums.push(x);
      });
    });
    var folder = date + ' DAILY TRAYS';
    if (orderNums.length) {
      folder += ' #' + Math.min.apply(null, orderNums) + '-' + Math.max.apply(null, orderNums);
    }
    return {
      boards: boards, unassigned: unassigned, split: split, folder: folder,
      fillerPlaced: fillerPlaced, fillerUnused: fillerUnused
    };
  }

  // ---------- tray bottoms (HANDOFF 7C) ----------

  var BOTTOM_COLUMNS = ['DESCRIPTION', 'PART TYPE', 'UNIT #', 'MATERIAL', 'QTY', 'WIDTH', 'DEPTH', 'GRAIN', 'COMPANY'];

  // One row per tray line. Every tray being made gets a bottom, even ones that
  // could not go on a board (4"/5", too long). Stock fill gets a bottom for each
  // tray that actually landed on a board (plan.fillerPlaced), with UNIT # "STOCK".
  function bottomRows(trays, plan) {
    var rows = [];
    trays.forEach(function (t) {
      if (!t.include) return;
      var wIn = parseInches(t.widthText), dIn = parseInches(t.depthText);
      if (!wIn || !dIn) return;
      var qty = Math.max(1, t.qty | 0);
      if (t.filler) {
        qty = (plan && plan.fillerPlaced && plan.fillerPlaced[t.id]) || 0;
        if (!qty) return;
      }
      rows.push({
        description: t.label || t.orderNumber,
        partType: 'TRAY BOTTOM',
        unit: t.filler ? 'STOCK' : t.orderNumber,
        material: '1/4 MELAMINE',
        qty: qty,
        widthMm: bottomMm(wIn),
        depthMm: bottomMm(dIn),
        grain: 'N',
        company: 'JEWELRY TRAYS DIRECT'
      });
    });
    return rows;
  }

  function csvField(v) {
    v = String(v);
    return /[",\r\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
  }

  function bottomsCsv(rows) {
    var lines = [BOTTOM_COLUMNS.join(',')];
    rows.forEach(function (r) {
      lines.push([r.description, r.partType, r.unit, r.material, r.qty, mm2(r.widthMm), mm2(r.depthMm), r.grain, r.company]
        .map(csvField).join(','));
    });
    return lines.join('\r\n') + '\r\n';
  }

  // ---------- zip (no compression, no library, works offline) ----------

  var CRC_TABLE = (function () {
    var t = new Uint32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();

  function crc32(u8) {
    var c = 0xffffffff;
    for (var i = 0; i < u8.length; i++) c = CRC_TABLE[(c ^ u8[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }

  // files: [{name, data: Uint8Array}]
  function makeZip(files, when) {
    when = when || new Date();
    var dosTime = (when.getHours() << 11) | (when.getMinutes() << 5) | (when.getSeconds() >> 1);
    var dosDate = ((when.getFullYear() - 1980) << 9) | ((when.getMonth() + 1) << 5) | when.getDate();
    var enc = new TextEncoder();
    var locals = [], centrals = [], offset = 0;

    files.forEach(function (f) {
      var name = enc.encode(f.name), data = f.data, crc = crc32(data);
      var lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true);
      lh.setUint16(8, 0, true); lh.setUint16(10, dosTime, true); lh.setUint16(12, dosDate, true);
      lh.setUint32(14, crc, true); lh.setUint32(18, data.length, true); lh.setUint32(22, data.length, true);
      lh.setUint16(26, name.length, true); lh.setUint16(28, 0, true);
      locals.push(new Uint8Array(lh.buffer), name, data);

      var ch = new DataView(new ArrayBuffer(46));
      ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true);
      ch.setUint16(8, 0x0800, true); ch.setUint16(10, 0, true); ch.setUint16(12, dosTime, true);
      ch.setUint16(14, dosDate, true); ch.setUint32(16, crc, true); ch.setUint32(20, data.length, true);
      ch.setUint32(24, data.length, true); ch.setUint16(28, name.length, true);
      ch.setUint32(42, offset, true);
      centrals.push(new Uint8Array(ch.buffer), name);
      offset += 30 + name.length + data.length;
    });

    var cdSize = centrals.reduce(function (a, b) { return a + b.length; }, 0);
    var end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true);
    end.setUint16(10, files.length, true); end.setUint32(12, cdSize, true); end.setUint32(16, offset, true);

    var parts = locals.concat(centrals, [new Uint8Array(end.buffer)]);
    var out = new Uint8Array(parts.reduce(function (a, b) { return a + b.length; }, 0));
    var p = 0;
    parts.forEach(function (b) { out.set(b, p); p += b.length; });
    return out;
  }

  // 2026-10-02 -> "100226" (the shop's MMDDYY file prefix)
  function mmddyy(isoDate) {
    var m = String(isoDate).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    return m ? m[2] + m[3] + m[1].slice(2) : '';
  }

  return {
    parseInches: parseInches,
    inToMm: inToMm,
    bottomMm: bottomMm,
    mm2: mm2,
    inchesText: inchesText,
    parseCsv: parseCsv,
    readShopifyCsv: readShopifyCsv,
    sizeFromName: sizeFromName,
    traysFromItems: traysFromItems,
    bytesToBin: bytesToBin,
    binToBytes: binToBytes,
    parseTemplate: parseTemplate,
    fillTemplate: fillTemplate,
    strip: strip,
    planBoards: planBoards,
    FIRST_STRIP_Y: FIRST_STRIP_Y,
    STOCK_SIZES: STOCK_SIZES,
    BOTTOM_COLUMNS: BOTTOM_COLUMNS,
    bottomRows: bottomRows,
    bottomsCsv: bottomsCsv,
    crc32: crc32,
    makeZip: makeZip,
    mmddyy: mmddyy
  };
});
