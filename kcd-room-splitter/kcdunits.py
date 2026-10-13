"""Room sheet reader for KCD v23 .job files.

Turns a .job into plain data that pricing and the engineering workbook need: the job heading, rooms,
walls, the sidebar notes, per-room Set Unit Info defaults, handles, shop-standard sizes, and every unit
with its size slots labelled from the unit library (.cab files), its materials, its options and its
unit type code. Nothing is guessed: a value that cannot be labelled is reported as unlabelled.

Layout facts come from kcd-deep-dive-notes.md. Depends on kcdjob.py (section reader) only.

Usage:
    cat = Catalog.from_library_root(r'C:\\KCD23')            # scans every *.cab under the root
    cat = Catalog.from_json('cat_compact.json')             # or the compact catalog made by catjson.py
    job = read_job('1087543 TILLIS HER CO.job', cat)
    for u in job.units: print(u.seq, u.cab, u.W, u.H, u.D, u.material)
    print(job.text_report())
"""
import os, sys, glob, json, struct, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # so python -I finds kcdjob next to this file
import kcdjob

INCH = 254.0            # size slots are stored in 0.1 mm; 254 of them make one inch
NSLOTS = 301            # 301 six-byte slots in the 1806-byte unit prefix


def txt(b):
    return b.decode('cp1252', 'replace') if isinstance(b, (bytes, bytearray)) else (b or '')


def sixteenths(x):
    """Inches to the nearest 1/16 as KCD prints them: 29.811 -> '29 13/16', 16.0 -> '16', 0.748 -> '3/4'.
    Use round(x*16)/16, not Fraction.limit_denominator, which gives thirds and sevenths."""
    n = int(round(x * 16))
    whole, r = divmod(abs(n), 16)
    sign = '-' if n < 0 else ''
    if r == 0:
        return '%s%d' % (sign, whole)
    from math import gcd
    g = gcd(r, 16)
    frac = '%d/%d' % (r // g, 16 // g)
    return ('%s%d %s' % (sign, whole, frac)) if whole else sign + frac


# --------------------------------------------------------------------------- unit library (.cab)

def parse_cab_text(text, name=''):
    """Parse the text of one .cab file. Returns a dict with sizes {item: (default, label, flag)}, prt,
    pcb, T (unit type code), code (name formula), choose, extra, option, head."""
    lines = text.splitlines()
    low = [l.strip().lower() for l in lines]

    def find(prefix):
        for i, l in enumerate(low):
            if l.startswith(prefix):
                return i
        return -1

    def block(tag):
        i = find(tag)
        if i < 0:
            return []
        try:
            n = int(lines[i + 1].strip())
        except Exception:
            return []
        return lines[i + 2:i + 2 + n]

    c = {'file': name, 'head': lines[:4], 'sizes': {}, 'order': [], 'prt': '', 'pcb': '', 'T': '', 'code': '',
         'choose': block('#choose file'), 'extra': block('#extra variables'), 'option': block('#option'), 'faces': block('#faces')}
    k = find('#code')
    if k >= 0 and ',' in lines[k]:
        c['code'] = lines[k].split(',', 1)[1].strip()
    c['extra_items'] = parse_extra_items(c['extra'])
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
    return c


def parse_extra_items(extra_lines):
    """'#Extra Variables' lines: kind, item, formula, label. Kinds U / UI / UIQ / I set size slot <item>
    (UIQ = integer item); E sets an E-variable, not a slot. Returns {item: (kind, formula, label)}."""
    out = {}
    for ln in extra_lines:
        parts = [p.strip() for p in ln.split(',')]
        if len(parts) < 3:
            continue
        kind = parts[0].upper()
        if kind not in ('U', 'UI', 'UIQ', 'I'):
            continue
        try:
            item = int(parts[1])
        except Exception:
            continue
        label = parts[3] if len(parts) > 3 else ''
        if item not in out or (label and not out[item][2]):
            out[item] = (kind, parts[2], label)
    return out


class Catalog:
    """All known .cab files, looked up by file name (case-insensitive), plus options.dat."""

    def __init__(self):
        self.cabs = {}          # lower-case file name -> parsed cab
        self.options = {}       # option number -> (name, cost, enabled)
        self.sizes_lst = {}     # shop size item -> (value raw, label)
        self.source = ''
        self.raw = {}           # lower-case file name -> full .cab text (for kcdcab face geometry)
        self.fulls = {}         # lower-case file name -> parsed full cab (kcdcab.parse_cab_full)

    @classmethod
    def from_library_root(cls, root):
        """Scan every *.cab under root (for example C:\\KCD23). First hit wins for duplicate names."""
        cat = cls()
        cat.source = root
        for p in sorted(glob.glob(os.path.join(root, '**', '*.cab'), recursive=True) +
                        glob.glob(os.path.join(root, '**', '*.CAB'), recursive=True)):
            k = os.path.basename(p).lower()
            if k in cat.cabs:
                continue
            try:
                text = open(p, 'rb').read().decode('cp1252', 'replace')
                cat.raw[k] = text
                cat.cabs[k] = parse_cab_text(text, os.path.basename(p))
            except Exception as e:
                cat.cabs[k] = {'file': os.path.basename(p), 'error': str(e), 'sizes': {}, 'order': [], 'prt': '', 'pcb': '', 'T': '', 'code': '', 'head': []}
        for p in glob.glob(os.path.join(root, '**', 'options.dat'), recursive=True):
            cat.load_options_text(open(p, 'rb').read().decode('cp1252', 'replace'))
            break
        for p in glob.glob(os.path.join(root, '**', 'Sizes.Lst'), recursive=True):
            cat.load_sizes_lst_text(open(p, 'rb').read().decode('cp1252', 'replace'))
            break
        return cat

    @classmethod
    def from_json(cls, path):
        """Load the compact catalog written by experiments/catjson.py (laptop)."""
        d = json.load(open(path, encoding='utf-8'))
        cat = cls()
        cat.source = path
        for name, c in d['cabs'].items():
            if 'err' in c:
                cat.cabs[name.lower()] = {'file': name, 'error': c['err'], 'sizes': {}, 'order': [], 'prt': '', 'pcb': '', 'T': '', 'code': '', 'head': []}
                continue
            sizes = {}
            order = []
            for item, dflt, label, flag in c.get('sizes', []):
                sizes[int(item)] = (dflt, label, flag)
                order.append(int(item))
            cat.cabs[name.lower()] = {'file': name, 'head': c.get('head', []), 'sizes': sizes, 'order': order, 'prt': c.get('prt', ''),
                                      'pcb': c.get('pcb', ''), 'T': c.get('T', ''), 'code': c.get('code', ''), 'choose': c.get('choose', []),
                                      'extra': c.get('extra', []), 'option': c.get('option', []), 'faces': c.get('faces', []),
                                      'extra_items': parse_extra_items(c.get('extra', []))}
        files = d.get('files', {})
        if 'options.dat' in files:
            cat.load_options_text(files['options.dat'])
        if 'Sizes.Lst' in files:
            cat.load_sizes_lst_text(files['Sizes.Lst'])
        return cat

    def load_rawlib_json(self, path):
        """Load the full library texts bundled by the laptop script rawlib.py ({relative path: text})."""
        files = json.load(open(path, encoding='utf-8'))
        for rel, text in files.items():
            base = rel.replace('\\', '/').rsplit('/', 1)[-1]
            if base.lower().endswith('.cab') and base.lower() not in self.raw:
                self.raw[base.lower()] = text
            elif base.lower() == 'sizes.lst' and not self.sizes_lst:
                self.load_sizes_lst_text(text)
            elif base.lower() == 'options.dat' and not self.options:
                self.load_options_text(text)

    def full(self, cabname):
        """The fully parsed .cab (points and faces) or None when the raw text is not loaded."""
        k = txt(cabname).strip().lower()
        if k in self.fulls:
            return self.fulls[k]
        text = self.raw.get(k)
        if text is None:
            return None
        import kcdcab
        self.fulls[k] = kcdcab.parse_cab_full(text, k)
        return self.fulls[k]

    def load_options_text(self, text):
        """options.dat: header lines, then 'number, name, cost, TRUE/FALSE' per option."""
        for ln in text.splitlines():
            parts = [p.strip() for p in ln.split(',')]
            if len(parts) >= 4 and parts[0].isdigit():
                try:
                    cost = float(parts[2])
                except Exception:
                    cost = None
                self.options[int(parts[0])] = (parts[1], cost, parts[3].upper() == 'TRUE')

    def load_sizes_lst_text(self, text):
        """Sizes.Lst: 'item, value, n) label' per shop-standard size."""
        for ln in text.splitlines():
            parts = [p.strip() for p in ln.split(',')]
            if len(parts) >= 3 and parts[0].isdigit() and re.match(r'-?\d+$', parts[1]):
                self.sizes_lst[int(parts[0])] = (int(parts[1]), re.sub(r'^\d+\)\s*', '', parts[2]))

    def get(self, cabname):
        return self.cabs.get(txt(cabname).strip().lower())

    def option_name(self, number):
        o = self.options.get(number)
        return o[0] if o else ''


# --------------------------------------------------------------------------- units

# Standard slot numbers. Labels vary a little by unit type, so the slot number is the key, not the label.
SLOT = {'X': 1, 'W': 2, 'H': 3, 'D': 4, 'LS': 5, 'MS': 6, 'RS': 7, 'TR': 8, 'MR': 9, 'BR': 10, 'K': 11,
        'CT': 12, 'OFFFLOOR': 13, 'FROMWALL': 14, 'ANGLE': 15, 'LCB': 16, 'RCB': 17, 'NSHELVES': 19,
        'OPEN1': 20, 'LMR': 21, 'OPEN2': 22, 'OPEN3': 23, 'OPEN4': 24, 'OPEN5': 25, 'OPEN6': 26,
        'SH_TOP': 31, 'SH_BOT': 32, 'SH_MID': 33, 'DOOR_OPENINGS': 36, 'DRAWER_OPENINGS': 37,
        'DH1': 41, 'DH2': 42, 'DH3': 43, 'DH4': 44, 'DH5': 45, 'DH6': 46, 'DH7': 147, 'DH8': 148, 'DH9': 149,
        'GAP_DD': 52, 'REV_TOP': 53, 'GAP_LOWER': 54, 'REV_BOT': 55, 'REV_L': 56, 'REV_R': 57, 'GAP_DOORS': 58,
        'HANGER_SPACE': 61, 'MLD_FRONT': 70, 'MLD_LEFT': 71, 'MLD_RIGHT': 72, 'MLD_BACK': 73, 'MLD_OVERLAP': 75,
        'NO_KICK_NOTCH': 119, 'SHOW_BACKS': 121, 'ROD1': 251, 'ROD2': 252, 'ROD3': 253, 'FULL_DOORS': 254}

# Unit type codes seen so far (byte 64 of the 86-byte block). Others exist; report the number when unknown.
TYPE_NAMES = {10: 'window', 20: 'door', 53: 'appliance', 100: 'upper with doors', 170: 'upper L corner', 200: 'base',
              230: 'filler', 300: 'tall 1 opening', 320: 'tall 3 openings', 500: 'backing', 550: 'custom or finish panel',
              640: 'top and bottom connecting shelves', 641: 'shelf', 645: 'top connecting shelf', 651: 'single hang',
              652: 'double hang', 670: 'L-shape', 770: 'slatwall', 880: 'leg leveler', 899: 'TAG rack accessory',
              1000: 'accessory or obstruction', 1101: 'light'}

SET_UNIT_INFO = ['material', 'door type', 'edgeband', 'rod type', 'base', 'crown', 'backing', 'drawer box',
                 'notch 1', 'notch 2', 'handles', 'contrast', 'countertop', 'finishing', 'insert']


class Unit:
    def __init__(self, job, raw, seq, catalog):
        d = job.data
        self.seq = seq                                  # 1-based position among live units (KCD's unit number)
        self.id = raw['id']
        self.wall = raw['wall']
        self.room = job.wall_room.get(self.wall, 0)
        self.cat = txt(raw['cat'])
        self.cab = txt(raw['cab'])
        self.lib = txt(raw['lib'])
        self.prt = txt(raw['prt'])
        self.pcb = txt(raw['pcb'])
        self.name = txt(raw['name'])
        self.edge = txt(raw['edge'])
        self.shp = txt(raw['shp'])
        self.profile = txt(raw['profile'])
        self.mats = [txt(m) for m in raw['mats']]
        self.more = [txt(m) for m in raw['more']]
        self.unw = txt(raw['unw'])
        self.unwname = txt(raw['unwname'])
        f86 = raw['f86']
        self.f86 = f86
        self.T = struct.unpack_from('<h', f86, 64)[0]
        self.qty = struct.unpack_from('<h', f86, 66)[0]           # unit quantity: KCD prints the unit's lines qty times
        self.nsizes = struct.unpack_from('<h', f86, 10)[0]
        self.width_raw = struct.unpack_from('<i', f86, 12)[0]
        pre = d[raw['start']:raw['start'] + kcdjob.UNIT_PREFIX]
        self.slots = {}                                 # item -> (raw value, state byte)
        for n in range(NSLOTS):
            rec = pre[6 * n:6 * n + 6]
            if any(rec):
                self.slots[n] = (struct.unpack_from('<i', rec, 0)[0], rec[4])
        self.cabdef = catalog.get(self.cab) if catalog else None
        self.options = []                               # option numbers from the settings pairs (code + 1)

    # -- values ---------------------------------------------------------------------------------
    def raw(self, item):
        return self.slots.get(item, (0, 0))[0]

    def inch(self, item):
        return self.raw(item) / INCH

    def count(self, item):
        return self.raw(item)

    def state(self, item):
        return self.slots.get(item, (0, 0))[1]

    def label(self, item):
        if self.cabdef and item in self.cabdef['sizes']:
            return self.cabdef['sizes'][item][1]
        if self.cabdef and item in self.cabdef.get('extra_items', {}):
            kind, formula, lab = self.cabdef['extra_items'][item]
            return lab or ('%s %s' % (kind, formula))
        return ''

    def defined(self, item):
        """True when the unit's .cab defines this slot (in #Sizes or as a U/UI/UIQ/I extra variable).
        Undefined slots can still hold leftovers from another cab and must not be read as sizes."""
        if not self.cabdef:
            return None
        return item in self.cabdef['sizes'] or item in self.cabdef.get('extra_items', {})

    def is_integer_item(self, item):
        if self.cabdef and item in self.cabdef['sizes']:
            return self.cabdef['sizes'][item][2] == '1'
        if self.cabdef and item in self.cabdef.get('extra_items', {}):
            return self.cabdef['extra_items'][item][0] == 'UIQ' or self.state(item) == 1
        return self.state(item) == 1

    def default_formula(self, item):
        """The .cab default for the slot ('' when unknown). A non-numeric default means the stored value is a
        result KCD computed; it can lag behind values the user typed later."""
        if self.cabdef and item in self.cabdef['sizes']:
            return self.cabdef['sizes'][item][0]
        if self.cabdef and item in self.cabdef.get('extra_items', {}):
            return self.cabdef['extra_items'][item][1]
        return ''

    def is_computed(self, item):
        f = self.default_formula(item)
        return bool(f) and self.state(item) == 0 and not re.match(r'^[-+]?[\d.]+(mm|in)?$', f.replace(' ', ''))

    def value(self, item):
        """Inches for size items, plain number for count/yes-no items (cab flag 1)."""
        return self.count(item) if self.is_integer_item(item) else self.inch(item)

    @property
    def X(self): return self.inch(1)
    @property
    def W(self): return self.inch(2)
    @property
    def H(self): return self.inch(3)
    @property
    def D(self): return self.inch(4)
    @property
    def LS(self): return self.inch(5)
    @property
    def MS(self): return self.inch(6)
    @property
    def RS(self): return self.inch(7)
    @property
    def TR(self): return self.inch(8)
    @property
    def MR(self): return self.inch(9)
    @property
    def BR(self): return self.inch(10)
    @property
    def K(self): return self.inch(11)
    @property
    def rods(self):
        return [self.inch(n) for n in (251, 252, 253) if self.raw(n) > 0]
    @property
    def door_heights(self):
        """Door, drawer-front and opening heights in slots I41..I46 and I147..I149. A value here does not mean
        the unit has a door: door presence comes from the .cab face rules and the price script."""
        return [self.inch(n) for n in (41, 42, 43, 44, 45, 46, 147, 148, 149) if self.raw(n) > 0]
    def shelf_counts(self):
        """{item: count} for the count slots whose .cab label speaks of shelves (I19, I31, I32, I33, I160, I161...)."""
        out = {}
        for n in (19, 31, 32, 33, 122, 160, 161):
            lab = self.label(n).lower()
            if n in self.slots and self.is_integer_item(n) and ('shel' in lab or 'shelves' in lab):
                out[n] = self.count(n)
        return out
    def side(self, item):
        """Inches for a side/rail slot, or None when the .cab does not define it (fillers, custom panels)."""
        if self.defined(item) is False:
            return None
        return self.inch(item)
    @property
    def type_name(self):
        return TYPE_NAMES.get(self.T, 'type %d' % self.T)

    @property
    def set_unit_info(self):
        """The 15 Set Unit Info texts: 1 material (name then price multiplier), 2 door type, 3 edgeband, ..."""
        return self.mats + self.more

    @property
    def material(self):
        """Material name without the trailing multiplier numbers of text 1."""
        return re.sub(r'(\s+[-\d.]+)+\s*$', '', self.mats[0]).strip() if self.mats else ''

    @property
    def material_multiplier(self):
        m = re.search(r'([-\d.]+)\s*$', self.mats[0]) if self.mats else None
        try:
            return float(m.group(1)) if m else None
        except Exception:
            return None

    def labelled_slots(self):
        """Every non-zero slot as (item, label, value, raw, state). Unlabelled slots get label '??'."""
        out = []
        for n in sorted(self.slots):
            lab = self.label(n) or '??'
            out.append((n, lab, self.value(n), self.raw(n), self.state(n)))
        return out

    def computed_slots(self):
        return [n for n in sorted(self.slots) if self.is_computed(n)]

    def missing_cab_items(self):
        """Items the .cab lists that are all-zero in the job (zero is a real value for many of them)."""
        if not self.cabdef:
            return []
        return [n for n in self.cabdef['order'] if n not in self.slots]

    def to_dict(self):
        return {'seq': self.seq, 'id': self.id, 'wall': self.wall, 'room': self.room, 'cab': self.cab, 'cat': self.cat, 'qty': self.qty,
                'name': self.name, 'lib': self.lib, 'prt': self.prt, 'pcb': self.pcb, 'T': self.T, 'type': self.type_name,
                'nsizes': self.nsizes, 'X': self.X, 'W': self.W, 'H': self.H, 'D': self.D, 'LS': self.LS, 'MS': self.MS,
                'RS': self.RS, 'TR': self.TR, 'MR': self.MR, 'BR': self.BR, 'K': self.K, 'rods': self.rods,
                'door_heights': self.door_heights, 'material': self.material, 'material_multiplier': self.material_multiplier,
                'set_unit_info': self.set_unit_info, 'edge': self.edge, 'options': self.options,
                'slots': {n: {'label': lab, 'value': v, 'raw': r, 'state': s, 'computed': self.is_computed(n)} for n, lab, v, r, s in self.labelled_slots()},
                'cab_known': self.cabdef is not None}


# --------------------------------------------------------------------------- job

class Job:
    def __init__(self, data, catalog=None, name=''):
        self.data = data
        self.name = name
        self.catalog = catalog
        S = kcdjob.parse(data)
        self.sections = S
        info = {n: i for n, a, b, i in S}
        span = {n: (a, b) for n, a, b, i in S}
        hdr = info['header']
        self.version = txt(hdr['version'])
        self.heading = [txt(c) for c in hdr['cust']]
        self.dates = (txt(hdr['date1']), txt(hdr['date2']))
        self.rtf = txt(hdr['rtf'])
        self.rooms = [txt(r['name']) for r in info['rooms']['list']]       # index 0 = room 1
        self.current_room = info['rooms']['cur']
        self.walls = info['walls']['list']
        self.wall_room = {w['id']: w['room'] for w in self.walls}
        # settings: handle group, 9 door styles, colour table, library shop sizes, option pairs
        r = kcdjob.R(data, span['settings'][0])
        self.handle_group = txt(r.str())
        self.door_styles = [txt(r.str()) for _ in range(9)]
        nc = r.i16()
        self.colour_table = r.raw((nc + 1) * 6)
        nlo = r.i16()
        self.shop_sizes = {}                                                  # library name -> {item: raw value}
        for _ in range(nlo):
            lib = txt(r.str())
            k = r.i16()
            blk = r.raw(k * 6)
            self.shop_sizes[lib] = {struct.unpack_from('<h', blk, 6 * j)[0]: struct.unpack_from('<i', blk, 6 * j + 2)[0] for j in range(k)}
        npair = r.i16()
        self.option_pairs = [(r.i16(), r.i16()) for _ in range(npair)]       # (unit id, code); option number = code + 1
        # defaults: 15 Set Unit Info texts per room
        r = kcdjob.R(data, span['defaults'][0])
        r.str(); a = r.i32(); b = r.i32()
        self.room_defaults = [[txt(r.str()) for _ in range(a + 1)] for _ in range(b + 1)]   # index 0 = room 1
        # handles: set 0 = job default, set k = room k; 9 slots of (name, 28 bytes, file)
        r = kcdjob.R(data, span['handles'][0])
        self.handles = []
        for _ in range(len(self.rooms) + 1):
            items = []
            for _ in range(9):
                s1 = txt(r.str()); raw28 = r.raw(28); s2 = txt(r.str())
                items.append((s1, s2, raw28))
            self.handles.append(items)
        # notes
        self.notes = []
        r = kcdjob.R(data, span['notes'][0])
        r.str(); nn = r.i16()
        for _ in range(nn):
            h = r.raw(30); text = txt(r.str()); font = txt(r.str()); size = txt(r.str()); tr = r.raw(36)
            self.notes.append({'text': text, 'font': font, 'size': size, 'room': struct.unpack_from('<i', tr, 4)[0],
                               'wall': struct.unpack_from('<h', h, 24)[0]})
        # units (live ones only; deleted units have wall 0)
        self.units = []
        seq = 0
        for u in info['units']['list']:
            if not u['wall']:
                continue
            seq += 1
            self.units.append(Unit(self, u, seq, catalog))
        by_id = {u.id: u for u in self.units}
        for uid, code in self.option_pairs:
            if uid in by_id:
                by_id[uid].options.append(code + 1)

    # -- helpers -------------------------------------------------------------------------------
    def room_name(self, k):
        return self.rooms[k - 1] if 1 <= k <= len(self.rooms) else ''

    def units_in_room(self, k):
        return [u for u in self.units if u.room == k]

    def sidebar_notes(self):
        return [n for n in self.notes if n['text'].lstrip().upper().startswith('ROOM DETAILS')]

    def sidebar_fields(self):
        """Parse 'LABEL- value' lines of the sidebar notes. Returns [(room, {label: value})]."""
        out = []
        for n in self.sidebar_notes():
            fields = {}
            for ln in n['text'].splitlines():
                m = re.match(r'\s*([A-Z][A-Z /&]+?)\s*[-:]\s*(.*)$', ln)
                if m:
                    fields[m.group(1).strip()] = m.group(2).strip()
                elif ln.strip().upper().startswith('ROOM DETAILS'):
                    fields['ROOM DETAILS'] = ln.strip()[12:].strip()
            out.append((n['room'], fields))
        return out

    def option_name(self, number):
        return self.catalog.option_name(number) if self.catalog else ''

    def to_dict(self):
        return {'name': self.name, 'version': self.version, 'heading': self.heading, 'dates': self.dates, 'rooms': self.rooms,
                'walls': [(w['id'], w['room']) for w in self.walls], 'handle_group': self.handle_group,
                'door_styles': self.door_styles, 'shop_sizes': self.shop_sizes, 'room_defaults': self.room_defaults,
                'handles': [[(a, b) for a, b, _ in s] for s in self.handles], 'notes': self.notes,
                'units': [u.to_dict() for u in self.units]}

    def text_report(self, slots=True):
        P = []
        P.append('JOB %s  (%s)  heading=%s  dates=%s' % (self.name, self.version, self.heading, self.dates))
        P.append('rooms: ' + ', '.join('%d=%s' % (i + 1, r) for i, r in enumerate(self.rooms)))
        P.append('handle group: %s   door styles: %s' % (self.handle_group, [s for s in self.door_styles if s]))
        for lib, sz in self.shop_sizes.items():
            P.append('shop sizes %s: %s' % (lib, {k: ('%.3f' % (v / INCH) if abs(v) >= 100 else v) for k, v in sorted(sz.items()) if v}))
        for i, dflt in enumerate(self.room_defaults):
            P.append('room %d Set Unit Info defaults: %s' % (i + 1, ['%s=%s' % (SET_UNIT_INFO[j], t) for j, t in enumerate(dflt) if t]))
        for k, hs in enumerate(self.handles):
            used = [(a, b) for a, b, _ in hs if a or b]
            if used:
                P.append('handles set %d: %s' % (k, used))
        for rm, fields in self.sidebar_fields():
            P.append('sidebar (room %d): %s' % (rm, fields))
        for n in self.notes:
            if n['text'].strip() and not n['text'].lstrip().upper().startswith('ROOM DETAILS'):
                P.append('note room %d wall %d: %r' % (n['room'], n['wall'], n['text'][:300]))
        P.append('')
        P.append('seq\tid\troom\tqty\ttype\tcab\tpcb\tname\tX\tW\tH\tD\tLS\tMS\tRS\tTR\tMR\tBR\tK\tshelf counts\trods\tI41-46 heights (doors, fronts or openings)\toptions\tmaterial')
        def sd(u, item):
            v = u.side(item)
            return '-' if v is None else '%.2f' % v
        for u in self.units:
            P.append('\t'.join(str(x) for x in [u.seq, u.id, u.room, u.qty, u.type_name, u.cab, u.pcb, u.name,
                      '%.3f' % u.X, '%.3f' % u.W, '%.3f' % u.H, '%.3f' % u.D, sd(u, 5), sd(u, 6), sd(u, 7),
                      sd(u, 8), sd(u, 9), sd(u, 10), sd(u, 11),
                      ' '.join('I%d=%d' % (n, c) for n, c in u.shelf_counts().items()),
                      '/'.join('%.2f' % r for r in u.rods), '/'.join('%.2f' % h for h in u.door_heights),
                      ' '.join('%d:%s' % (o, self.option_name(o)) for o in u.options), u.mats[0]]))
        if slots:
            for u in self.units:
                P.append('')
                P.append('--- unit %d (id %d) %s  qty=%d  cab=%s  cat=%r name=%r prt=%r pcb=%r  T=%d nsizes=%d  cab %s' % (
                    u.seq, u.id, u.type_name, u.qty, u.cab, u.cat, u.name, u.prt, u.pcb, u.T, u.nsizes, 'known' if u.cabdef else 'NOT IN CATALOG'))
                P.append('    set unit info: %s' % ['%s=%s' % (SET_UNIT_INFO[j], t) for j, t in enumerate(u.set_unit_info) if t])
                P.append('    edge=%r shp=%r profile=%r unw=%r' % (u.edge, u.shp, u.profile, u.unw))
                for n, lab, v, raw, st in u.labelled_slots():
                    tag = '  computed from %s' % u.default_formula(n) if u.is_computed(n) else ''
                    P.append('    I%-3d %-40s %10s  (raw %d, state %d)%s' % (n, lab, ('%d' % v) if isinstance(v, int) else ('%.4f' % v), raw, st, tag))
                miss = u.missing_cab_items()
                if miss:
                    P.append('    cab items with no record (zero): %s' % miss)
        return '\n'.join(P)


def read_job(path, catalog=None):
    data = open(path, 'rb').read()
    return Job(data, catalog, os.path.basename(path))


if __name__ == '__main__':
    import sys, argparse
    ap = argparse.ArgumentParser(description='Print the room sheet of KCD .job files.')
    ap.add_argument('jobs', nargs='+')
    ap.add_argument('--lib', help='KCD library root (for example C:\\KCD23) or a compact catalog .json')
    ap.add_argument('--json', action='store_true', help='print JSON instead of text')
    ap.add_argument('--no-slots', action='store_true', help='summary table only')
    a = ap.parse_args()
    cat = None
    if a.lib:
        cat = Catalog.from_json(a.lib) if a.lib.lower().endswith('.json') else Catalog.from_library_root(a.lib)
    for p in a.jobs:
        job = read_job(p, cat)
        if a.json:
            print(json.dumps(job.to_dict(), indent=1, default=str))
        else:
            print(job.text_report(slots=not a.no_slots))
            print()
