"""Laptop version of the unit decoder used in the Oct 2026 KCD deep dive (see ../kcd-deep-dive-notes.md).

It expects the test-laptop layout: this file next to kcdjob.py and probe_names.json in %TEMP%\\kcdsplit,
the unit library extracted to %TEMP%\\kcdlib\\C-KCD23\\NEW CFFL UNIT LIBRARY and a pricing update extracted
to %TEMP%\\kcdprice. Output goes to .\\out\\. Untested anywhere else; kept as a record of what was done.

Writes: (1) catalog_cabs.tsv + catalog_slots.txt (every .cab, every size slot with labels),
        (2) sizes_<job>.txt per job: units decoded with .cab slot labels, settings pairs (options),
            room defaults (Set Unit Info), handles, notes.
usage: python report.py SUBSTR [SUBSTR ...] [path\\to\\file.job ...]
"""
import os, sys, glob, struct, zipfile, json, collections, re
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import kcdjob
T = os.environ['TEMP']
LIB = os.path.join(T, 'kcdlib', 'C-KCD23', 'NEW CFFL UNIT LIBRARY')
PRICE = os.path.join(T, 'kcdprice')
OUT = os.path.join(here, 'out')
os.makedirs(OUT, exist_ok=True)

def txt(b):
    return b.decode('cp1252', 'replace') if isinstance(b, (bytes, bytearray)) else b

def parse_cab(path):
    lines = open(path, 'rb').read().decode('cp1252', 'replace').splitlines()
    low = [l.strip().lower() for l in lines]
    def find(prefix):
        for i, l in enumerate(low):
            if l.startswith(prefix):
                return i
        return -1
    c = {'file': os.path.basename(path), 'dir': os.path.relpath(os.path.dirname(path), T), 'head': lines[:4], 'sizes': {}, 'order': [],
         'prt': '', 'pcb': '', 'T': '', 'code': '', 'choose': [], 'nfaces_dd': 0}
    k = find('#code')
    if k >= 0 and ',' in lines[k]:
        c['code'] = lines[k].split(',', 1)[1].strip()
    i = find('#sizes')
    if i >= 0:
        try:
            n = int(lines[i + 1].strip())
        except Exception:
            n = 0
        for ln in lines[i + 2:i + 2 + n]:
            parts = [p.strip() for p in ln.split(',')]
            if len(parts) >= 3:
                try:
                    item = int(parts[0])
                except Exception:
                    continue
                c['sizes'][item] = (parts[1], parts[2], parts[3] if len(parts) > 3 else '')
                c['order'].append(item)
        j = i + 2 + n
        for key, off in (('prt', 0), ('pcb', 1), ('T', 2)):
            if j + off < len(lines):
                c[key] = lines[j + off].strip()
    ch = find('#choose file')
    if ch >= 0:
        try:
            n = int(lines[ch + 1].strip())
        except Exception:
            n = 0
        c['choose'] = lines[ch + 2:ch + 2 + n]
    f = find('#faces')
    if f >= 0:
        try:
            n = int(lines[f + 1].strip())
        except Exception:
            n = 0
        c['nfaces_dd'] = sum(1 for ln in lines[f + 2:f + 2 + n] if 'door' in ln.lower() or 'drawer' in ln.lower())
    return c

cabs = {}
for root in (LIB, PRICE):
    for p in sorted(glob.glob(os.path.join(root, '**', '*.cab'), recursive=True)):
        k = os.path.basename(p).lower()
        if k in cabs:
            continue
        try:
            cabs[k] = parse_cab(p)
        except Exception as e:
            cabs[k] = {'file': os.path.basename(p), 'dir': '', 'head': ['', '', '', ''], 'sizes': {}, 'order': [], 'prt': '', 'pcb': '', 'T': '', 'code': 'ERR ' + str(e), 'choose': [], 'nfaces_dd': 0}

# ---- catalog TSV ----
with open(os.path.join(OUT, 'catalog_cabs.tsv'), 'w', encoding='utf-8') as f:
    f.write('file\tdir\tversion_label\tdoor\tcode\tT\tprt\tpcb\tnsizes\tnchoose\tfaces_dd\n')
    for k in sorted(cabs):
        c = cabs[k]
        h = c['head'] + ['', '', '', '']
        lab = h[0].split('Version', 1)[1].strip() if 'Version' in h[0] else h[0].strip()
        f.write('\t'.join([c['file'], c['dir'], lab, h[3].strip(), c['code'], c['T'], c['prt'], c['pcb'], str(len(c['sizes'])), str(len(c['choose'])), str(c['nfaces_dd'])]) + '\n')

# ---- global slot dictionary ----
def norm(label):
    s = re.sub(r'\s+', ' ', label.strip())
    s = s.strip('*').strip()
    s = re.sub(r'\{\d+\}', '', s).strip()
    return s
slots = collections.defaultdict(collections.Counter)
slotdef = collections.defaultdict(collections.Counter)
slotflag = collections.defaultdict(collections.Counter)
for c in cabs.values():
    for item, (dflt, label, flag) in c['sizes'].items():
        slots[item][norm(label)] += 1
        slotdef[item][dflt] += 1
        slotflag[item][flag] += 1
with open(os.path.join(OUT, 'catalog_slots.txt'), 'w', encoding='utf-8') as f:
    f.write('item\tcabs\tflag\tlabels (count)\t| default formulas (count)\n')
    for item in sorted(slots):
        labs = ', '.join('%s (%d)' % (l, n) for l, n in slots[item].most_common(5))
        dfs = ', '.join('%s (%d)' % (l, n) for l, n in slotdef[item].most_common(4))
        fl = ','.join('%s:%d' % (a, b) for a, b in slotflag[item].most_common(3))
        f.write('%d\t%d\t%s\t%s\t| %s\n' % (item, sum(slots[item].values()), fl, labs, dfs))

# ---- jobs ----
def load(p):
    if '|' in p:
        z, n = p.split('|', 1)
        return zipfile.ZipFile(z).read(n)
    return open(p, 'rb').read()

def inch(v):
    return v / 254.0

want = [a.lower() for a in sys.argv[1:] if not a.lower().endswith('.job')]
direct = []
for a in sys.argv[1:]:
    if a.lower().endswith('.job'):
        direct.extend(glob.glob(a) or [a])
seen = set()
R = json.load(open(os.path.join(here, 'probe_names.json')))
R = [{'path': p} for p in direct] + R
for rec in R:
    p = rec['path']
    nm = os.path.basename(p.split('|')[-1])
    if p not in direct and (not any(w in nm.lower() for w in want) or nm in seen):
        continue
    if nm in seen:
        continue
    seen.add(nm)
    d = load(p)
    try:
        S = kcdjob.parse(d)
    except Exception as e:
        print('ERR', nm, e)
        continue
    info = {n: i for n, a, b, i in S}
    span = {n: (a, b) for n, a, b, i in S}
    out = []
    P = out.append
    rooms = [txt(x['name']) for x in info['rooms']['list']]
    P('=== %s  size=%d' % (nm, len(d)))
    P('heading=%s' % [txt(c) for c in info['header']['cust']])
    P('rooms=%s' % rooms)
    walls = info['walls']['list']
    wall_room = {w['id']: w['room'] for w in walls}
    P('walls: ' + ', '.join('%d->room%d' % (w['id'], w['room']) for w in walls))
    # settings: handle group, 9 door styles, colour table, library shop sizes, option pairs
    a, b = span['settings']
    r = kcdjob.R(d, a)
    s0 = txt(r.str()); s9 = [txt(r.str()) for _ in range(9)]
    nc = r.i16(); ncblk = r.raw((nc + 1) * 6)
    nlo = r.i16(); los = []
    for _ in range(nlo):
        name = txt(r.str()); k = r.i16(); blk = r.raw(k * 6)
        los.append((name, k, blk.hex()))
    npair = r.i16()
    pairs = [(r.i16(), r.i16()) for _ in range(npair)]
    P('--- settings: s0=%r s9=%r' % (s0, s9))
    P('  nc=%d ncblk=%s' % (nc, ncblk.hex()))
    for name, k, hx in los:
        P('  lo %r k=%d %s' % (name, k, hx[:400]))
    P('  pairs (unit id, code) n=%d: %s' % (npair, pairs))
    # defaults: 15 Set Unit Info strings per room
    a, b = span['defaults']
    r = kcdjob.R(d, a)
    r.str(); r.i32(); nr = r.i32() + 1
    for k in range(nr):
        P('--- defaults room %d: %r' % (k + 1, [txt(r.str()) for _ in range(15)]))
    # handles: 9 hardware slots per set
    a, b = span['handles']
    r = kcdjob.R(d, a)
    try:
        for k in range(len(rooms) + 1):
            items = []
            for _ in range(9):
                s1 = txt(r.str()); raw = r.raw(28); s2 = txt(r.str())
                items.append((s1, s2, raw.hex()))
            P('--- handles set %d: %s' % (k, [(x[0], x[1]) for x in items]))
            if k == 0:
                P('    raw28: %s' % [x[2] for x in items])
    except Exception as e:
        P('handles parse err %s' % e)
    # notes
    a, b = span['notes']
    r = kcdjob.R(d, a)
    r.str(); n = r.i16()
    for _ in range(n):
        hdr = r.raw(30); text = txt(r.str()); font = txt(r.str()); size = txt(r.str()); tr = r.raw(36)
        room = struct.unpack_from('<i', tr, 4)[0]; wall = struct.unpack_from('<h', hdr, 24)[0]
        if text.strip():
            P('--- note room=%d wall=%d font=%r size=%r text=%r' % (room, wall, font, size, text[:1500]))
    # units summary table
    P('--- units summary')
    P('id\twall\troom\tcab\tcat\tT\tnsz\tX"\tW"\tH"\tD"\tLS\tRS\tMS\tK\tshelves\trods\tdoorsI36\tdrwI37\tDH41-45\tmat')
    units = info['units']['list']
    for u in units:
        if not u['wall']:
            continue
        pre = d[u['start']:u['start'] + kcdjob.UNIT_PREFIX]
        f86 = u['f86']
        def v(n):
            return struct.unpack_from('<i', pre, 6 * n)[0]
        rm = wall_room.get(u['wall'], 0)
        P('\t'.join(str(x) for x in [u['id'], u['wall'], rm, txt(u['cab']), txt(u['cat']), struct.unpack_from('<h', f86, 64)[0], struct.unpack_from('<h', f86, 10)[0],
            '%.3f' % inch(v(1)), '%.3f' % inch(v(2)), '%.3f' % inch(v(3)), '%.3f' % inch(v(4)), '%.2f' % inch(v(5)), '%.2f' % inch(v(7)), '%.2f' % inch(v(6)), '%.2f' % inch(v(11)),
            '%d/%d/%d/%d' % (v(19), v(31), v(33), v(32)), '%.2f/%.2f/%.2f' % (inch(v(251)), inch(v(252)), inch(v(253))), v(36), v(37),
            '/'.join('%.2f' % inch(v(n)) for n in (41, 42, 43, 44, 45)), txt(u['mats'][0])]))
    # unit details
    for u in units:
        if not u['wall']:
            continue
        pre = d[u['start']:u['start'] + kcdjob.UNIT_PREFIX]
        f86 = u['f86']
        cab = cabs.get(txt(u['cab']).lower())
        P('')
        P('--- unit id=%d wall=%d cab=%s cat=%r name=%r prt=%r pcb=%r unw=%r' % (u['id'], u['wall'], txt(u['cab']), txt(u['cat']), txt(u['name']), txt(u['prt']), txt(u['pcb']), txt(u['unw'])))
        P('  lib=%r edge=%r shp=%r profile=%r' % (txt(u['lib']), txt(u['edge']), txt(u['shp']), txt(u['profile'])))
        P('  mats=%r' % [txt(m) for m in u['mats']])
        P('  more=%r' % [txt(m) for m in u['more']])
        P('  cab.T=%s cab.nsizes=%d cab.code=%r cab.door=%r cab.choose=%r' % ((cab['T'], len(cab['sizes']), cab['code'], cab['head'][3] if len(cab['head']) > 3 else '', cab['choose']) if cab else ('?', 0, '', '', '')))
        i16 = lambda o: struct.unpack_from('<h', f86, o)[0]
        i32 = lambda o: struct.unpack_from('<i', f86, o)[0]
        P('  f86: wall=%d flag=%d [4]=%d [6]=%d [8]=%d nsizes=%d W=%d | six=%s | c1=(%d,%d,%d) c2=(%d,%d,%d) | T=%d [66]=%d [68]=%d [70]=%d [72]=%d rest=%s' % (
            i16(0), i16(2), i16(4), i16(6), i16(8), i16(10), i32(12), [i32(16 + 4 * k) for k in range(6)],
            i32(40), i32(44), i32(48), i32(52), i32(56), i32(60), i16(64), i16(66), i16(68), i16(70), i16(72), f86[74:].hex()))
        P('  f10=%s suffix=%s' % (u['f10'].hex(), [struct.unpack_from('<h', d, u['suffix_at'] + j)[0] for j in range(0, 26, 2)] + [d[u['suffix_at'] + 26]]))
        P('  slots (item: value raw / inches [flag b4,b5] label = default):')
        for n in range(301):
            recb = pre[6 * n:6 * n + 6]
            lab = cab['sizes'].get(n) if cab else None
            if not any(recb):
                continue
            val = struct.unpack_from('<i', recb, 0)[0]
            b4, b5 = recb[4], recb[5]
            if lab:
                P('    I%-3d %7d  %8.3f  [%d,%d]  %s = %s  (cabflag %s)' % (n, val, inch(val), b4, b5, lab[1], lab[0], lab[2]))
            else:
                g = slots.get(n)
                P('    I%-3d %7d  %8.3f  [%d,%d]  ?? %s' % (n, val, inch(val), b4, b5, (g.most_common(1)[0][0] if g else '')))
        if cab:
            missing = [n for n in cab['order'] if not any(pre[6 * n:6 * n + 6])]
            P('  cab items with all-zero record: %s' % missing)
    fn = os.path.join(OUT, 'sizes_' + ''.join(c if c.isalnum() else '_' for c in nm) + '.txt')
    open(fn, 'w', encoding='utf-8').write('\n'.join(out))
    print('wrote', fn, len(out))
print('cabs', len(cabs))
