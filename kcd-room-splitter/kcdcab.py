"""Full KCD .cab reader and the face geometry of a unit: doors, drawer fronts and open faces with their sizes.

A .cab file (text) holds, after a 4-line head: #Code, #Options, #Extra Variable (pre), #Sizes (then the .prt,
.pcb and unit-type lines), #Choose File Questions, #Extra Variables, #Center point, #Pts (point coordinates as
formulas of the sizes), #Faces (face type code, colour, point count, point numbers, name) and load statements.
KCD builds the 3D unit from the points and faces; the price scripts read every door/drawer face as D1..D12
(DnW, DnH, DnT, DnDR, DnHG). This module recomputes those faces from a unit's stored sizes.

Face type codes (8 digits, from the library survey, Oct 2026): digit 1 = face kind (0 open, 1 upper door,
2 lower door, 3 drawer front), digits 4-5 = face number n, the other digits are not understood yet.
A door face wider than `pair_width` is split by KCD into a pair; the threshold is not stored in the library
(calibrated against the engineers' reviews, see kcd-deep-dive-notes.md) so doors near it are flagged.
"""
import os, re, sys, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

INCH = 254.0


def norm_lines(text):
    return text.replace('\r\n', '\n').replace('\r', '\n').split('\n')


def depth0_colon(s):
    """Index of the first ':' outside parentheses, or -1."""
    depth = 0
    for i, ch in enumerate(s):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        elif ch == ':' and depth == 0:
            return i
    return -1


def header_kind(s):
    l = s.lower().strip()
    if l.startswith('#code'):
        return 'code'
    if 'load statement' in l:
        return 'loads'
    if '#extra variables' in l:
        return 'extra'
    if '#extra variable' in l:
        return 'extra_pre'
    if '#sizes' in l:
        return 'sizes'
    if '#choose' in l:
        return 'choose'
    if '#center' in l:
        return 'center'
    if '#faces' in l:
        return 'faces'
    if '#pts' in l:
        return 'pts'
    if '#option' in l:
        return 'options'
    return None


def parse_face(line):
    """'[(cond):]code, draw-order expr, colour, npts, p1..pn, name' -> dict or None."""
    s = line.strip()
    cond = None
    if s.startswith('('):
        k = depth0_colon(s)
        if k > 0:
            cond, s = s[:k].strip(), s[k + 1:].strip()
    parts = [p.strip() for p in s.split(',')]
    if len(parts) < 5:
        return None
    try:
        npts = int(float(parts[3]))
        if npts <= 0:
            return None
        pts = [int(float(p)) for p in parts[4:4 + npts]]
    except ValueError:
        return None
    return {'cond': cond, 'code': parts[0], 'order': parts[1], 'color': parts[2], 'pts': pts, 'name': ','.join(parts[4 + npts:]).strip()}


def parse_cab_full(text, name=''):
    lines = norm_lines(text)
    cab = {'file': name, 'head': [l.strip() for l in lines[:4]], 'code': '', 'options': [], 'extra_pre': [], 'sizes': {},
           'order': [], 'prt': '', 'pcb': '', 'T': '', 'choose': [], 'extra': [], 'center': [], 'pts': {}, 'faces': [], 'loads': []}
    n = len(lines)
    i = 4
    while i < n:
        kind = header_kind(lines[i])
        if kind is None:
            i += 1
            continue
        if kind == 'code':
            cab['code'] = lines[i].split(',', 1)[1].strip() if ',' in lines[i] else ''
            i += 1
            continue
        if kind == 'center':
            i += 1
            while i < n and header_kind(lines[i]) is None and lines[i].strip():
                cab['center'].append(lines[i].strip())
                i += 1
            continue
        if kind == 'loads':
            cab['loads'] = [l.strip() for l in lines[i + 2:] if l.strip()]
            break
        m = re.match(r'\s*(\d+)', lines[i + 1]) if i + 1 < n else None
        if not m:
            i += 1
            continue
        cnt = int(m.group(1))
        body = lines[i + 2:i + 2 + cnt]
        i = i + 2 + cnt
        if kind == 'sizes':
            for l in body:
                parts = [p.strip() for p in l.split(',')]
                if len(parts) < 2 or not re.match(r'^\d+$', parts[0]):
                    continue
                item = int(parts[0])
                cab['sizes'][item] = (parts[1], parts[2] if len(parts) > 2 else '', parts[3] if len(parts) > 3 else '0')
                cab['order'].append(item)
            if i < n:
                cab['prt'] = lines[i].strip()
            if i + 1 < n:
                cab['pcb'] = lines[i + 1].strip()
            if i + 2 < n:
                cab['T'] = lines[i + 2].strip()
            i += 3
        elif kind == 'pts':
            for l in body:
                parts = [p.strip() for p in l.split(',', 3)]
                if len(parts) == 4 and re.match(r'^\d+$', parts[0]):
                    cab['pts'][int(parts[0])] = (parts[1], parts[2], parts[3])
        elif kind == 'faces':
            for l in body:
                f = parse_face(l)
                if f:
                    cab['faces'].append(f)
        else:
            cab[kind] = [l.strip() for l in body if l.strip()]
    return cab


# ----------------------------------------------------------------------------- expressions

class ExprEval:
    """The formula language of .cab files: + - * / \\ % ^, comparisons = <> < > <= >=, & |, (cond):a:b,
    abs() int() sqrt() round(), identifiers looked up (case-insensitively) in `vars`."""
    TOK = re.compile(r'\s*(?:(\d+\.?\d*|\.\d+)|([A-Za-z_][A-Za-z0-9_]*)|(<>|<=|>=|=>|[-+*/\\%^()=<>&|:,])|(.))')
    FUNCS = {'abs': abs, 'int': lambda v: float(int(v)), 'sqrt': lambda v: math.sqrt(v) if v >= 0 else 0.0,
             'round': lambda v: float(round(v))}

    def __init__(self, vars):
        self.vars = vars
        self.unknown = {}
        self.errors = []

    def eval(self, text):
        s = (text or '').strip()
        if not s:
            return 0.0
        k = depth0_colon(s)
        if k >= 0:
            cond, rest = s[:k], s[k + 1:]
            k2 = depth0_colon(rest)
            a, b = (rest[:k2], rest[k2 + 1:]) if k2 >= 0 else (rest, '')
            if self.truth(cond):
                return self.eval(a)
            return self.eval(b) if b.strip() else 0.0
        return self.expr(s)

    def truth(self, s):
        return self.expr(s) != 0

    def tokenize(self, s):
        toks = []
        pos = 0
        while pos < len(s):
            m = self.TOK.match(s, pos)
            if not m or m.end() == pos:
                break
            if m.group(1) is not None:
                toks.append(('n', float(m.group(1)), m.start(1), m.end(1)))
            elif m.group(2):
                toks.append(('i', m.group(2), m.start(2), m.end(2)))
            elif m.group(3):
                toks.append(('o', m.group(3), m.start(3), m.end(3)))
            else:
                self.errors.append('stray %r in %r' % (m.group(4), s[:60]))
            pos = m.end()
        return toks

    def expr(self, s):
        self._s = s
        self._t = self.tokenize(s)
        self._p = 0
        try:
            v = self._or()
        except Exception as e:
            self.errors.append('%s in %r' % (e, s[:60]))
            return 0.0
        return float(v)

    def _peek(self):
        return self._t[self._p] if self._p < len(self._t) else (None, None, 0, 0)

    def _op(self, *ops):
        k, v, a, b = self._peek()
        if k == 'o' and v in ops:
            self._p += 1
            return v
        return None

    def _or(self):
        v = self._and()
        while self._op('|'):
            r = self._and()
            v = 1.0 if (v != 0 or r != 0) else 0.0
        return v

    def _and(self):
        v = self._cmp()
        while self._op('&'):
            r = self._cmp()
            v = 1.0 if (v != 0 and r != 0) else 0.0
        return v

    def _cmp(self):
        v = self._arith()
        op = self._op('=', '<>', '<', '>', '<=', '>=', '=>')
        if op:
            r = self._arith()
            eps = 1e-9
            if op == '=':
                return 1.0 if abs(v - r) < eps else 0.0
            if op == '<>':
                return 1.0 if abs(v - r) >= eps else 0.0
            if op == '<':
                return 1.0 if v < r - eps else 0.0
            if op == '>':
                return 1.0 if v > r + eps else 0.0
            if op == '<=':
                return 1.0 if v <= r + eps else 0.0
            return 1.0 if v >= r - eps else 0.0
        return v

    def _arith(self):
        v = self._term()
        while True:
            op = self._op('+', '-')
            if not op:
                return v
            r = self._term()
            v = v + r if op == '+' else v - r

    def _term(self):
        v = self._power()
        while True:
            op = self._op('*', '/', '\\', '%')
            if not op:
                return v
            r = self._power()
            if op == '*':
                v = v * r
            elif op == '/':
                v = v / r if r else 0.0
            elif op == '\\':
                v = float(int(v / r)) if r else 0.0
            else:
                v = math.fmod(v, r) if r else 0.0

    def _power(self):
        v = self._unary()
        if self._op('^'):
            r = self._unary()
            try:
                v = v ** r
            except Exception:
                v = 0.0
        return v

    def _unary(self):
        op = self._op('-', '+')
        if op:
            v = self._unary()
            return -v if op == '-' else v
        return self._atom()

    def _group(self):
        """Consume '(' ... ')' and evaluate the inner text (which may hold a ternary)."""
        k, v, a, b = self._peek()
        self._p += 1
        depth = 1
        start = b
        end = len(self._s)
        while self._p < len(self._t):
            k2, v2, a2, b2 = self._t[self._p]
            self._p += 1
            if k2 == 'o' and v2 == '(':
                depth += 1
            elif k2 == 'o' and v2 == ')':
                depth -= 1
                if depth == 0:
                    end = a2
                    break
        inner = self._s[start:end]
        sub = ExprEval(self.vars)
        val = sub.eval(inner)
        for kk, vv in sub.unknown.items():
            self.unknown[kk] = self.unknown.get(kk, 0) + vv
        self.errors.extend(sub.errors)
        # restore parser state (sub-evaluation clobbers nothing of ours: it has its own instance)
        return val

    def _atom(self):
        k, v, a, b = self._peek()
        if k == 'n':
            self._p += 1
            return v
        if k == 'i':
            self._p += 1
            name = v.lower()
            k2, v2, _, _ = self._peek()
            if name in self.FUNCS and k2 == 'o' and v2 == '(':
                arg = self._group()
                return float(self.FUNCS[name](arg))
            if name in self.vars:
                val = self.vars[name]
                return float(val[0]) if isinstance(val, list) else float(val)
            self.unknown[name] = self.unknown.get(name, 0) + 1
            return 0.0
        if k == 'o' and v == '(':
            return self._group()
        if k == 'o' and v == ')':
            self._p += 1
            return 0.0
        if k is None:
            return 0.0
        raise ValueError('unexpected %r' % (v,))


# ----------------------------------------------------------------------------- shop sizes

# KCD's S-codes as used in .cab formulas -> item number in Sizes.Lst (matched by label, Oct 2026; verify)
S_CODES = {'sch': 2, 'stch': 3, 'stcd': 4, 'sbch': 5, 'sbcd': 6, 'sls': 9, 'srs': 10, 'sms': 11, 'sttr': 12, 'stbr': 13,
           'stmr': 14, 'sbtr': 15, 'sbbr': 16, 'sbmr': 17, 'sdrh': 18, 'sk': 19, 'skd': 20, 'sct': 21, 'swt': 36,
           'spch': 37, 'spcd': 38, 'scet': 44, 'sdet': 45, 'sbdg': 50, 'stsrv': 51, 'sttrv': 52, 'stbrv': 53,
           'stdg': 54, 'sbsrv': 55, 'sbtrv': 56, 'sbbrv': 57, 'sddrg': 58, 'slgp': 59, 'sctoh': 65, 'skbh': 79,
           'sdt': 80, 'sbof': 81, 'sgpctr': 82, 'slgpctr': 83}


def shop_value(item, job, catalog):
    """Shop size in inches from the job's settings (preferred) or the catalog's Sizes.Lst; None if unknown."""
    if job is not None:
        ss = getattr(job, 'shop_sizes', None)
        if isinstance(ss, dict):
            if item in ss:
                v = ss[item]
                return (v[0] if isinstance(v, (list, tuple)) else v) / INCH
            for lib, d in ss.items():
                if isinstance(d, dict) and item in d:
                    return d[item] / INCH
        elif isinstance(ss, (list, tuple)):
            for entry in ss:
                if isinstance(entry, (list, tuple)) and len(entry) >= 2 and entry[0] == item:
                    return entry[1] / INCH
    if catalog is not None and item in getattr(catalog, 'sizes_lst', {}):
        return catalog.sizes_lst[item][0] / INCH
    return None


# ----------------------------------------------------------------------------- unit faces

class UnitFaces:
    """Doors, drawer fronts and openings of one unit, from its .cab face rules and stored sizes."""

    def __init__(self, cab, unit, job=None, catalog=None, pair_width=27.0, apply_rules=False):
        self.cab = cab
        self.unit = unit
        self.flags = []
        # Int16 at byte 6 of the unit's 86-byte block reads 1 on units whose door is single and 2 where the
        # engineers' reviews show a pair (checked on 14 doored units, Oct 2026); 0 on units without doors.
        import struct
        f86 = getattr(unit, 'f86', None)
        self.pair_hint = struct.unpack_from('<h', f86, 6)[0] if f86 and len(f86) >= 8 else 0
        v = {}
        inch = unit.inch
        v.update({'w': unit.W, 'h': unit.H, 'd': unit.D, 'ls': unit.LS, 'ms': unit.MS, 'rs': unit.RS, 'tr': unit.TR,
                  'mr': unit.MR, 'br': unit.BR, 'k': unit.K, 'z': inch(13), 'lmr': inch(21)})
        v['lf'] = inch(16) if unit.defined(16) else 0.0
        v['rf'] = unit.W - (inch(17) if unit.defined(17) else 0.0)
        v['fw'] = v['rf'] - v['lf']
        v['lk'] = v['lf']
        v['rk'] = v['rf']
        v['ct'] = 1.0 if (unit.defined(12) and inch(12) > 0) else 0.0
        for nm in ('ctl', 'ctr', 'ctf', 'ctb', 'ctbl', 'ctbr', 'lfct', 'rfct', 'lbct', 'rbct', 'lp', 'mh', 'mldh', 'slsdcr', 'dsf', 'acv', 'cci'):
            v[nm] = 0.0
        v['yes'] = 1.0
        for item, (raw, state) in unit.slots.items():
            v['i%d' % item] = float(unit.value(item))
        for item in cab['order']:
            if ('i%d' % item) not in v:
                dflt = cab['sizes'][item][0].replace(' ', '')
                v['i%d' % item] = float(dflt) if re.match(r'^[-+]?[\d.]+$', dflt) else 0.0
        self.shop_used = {}
        for code, item in S_CODES.items():
            val = shop_value(item, job, catalog)
            if val is not None:
                v[code] = val
        drh = shop_value(18, job, catalog)
        v['drh'] = drh if drh is not None else 4.5
        self.ev = ExprEval(v)
        self.vars = v
        for line in cab['extra']:
            parts = [p.strip() for p in line.split(',', 3)]
            if len(parts) < 3:
                continue
            kind = parts[0].upper()
            try:
                item = int(parts[1])
            except ValueError:
                continue
            formula = parts[2]
            if kind == 'E':
                v['e%d' % item] = self.ev.eval(formula)
            elif kind in ('U', 'UI', 'UIQ', 'I') and apply_rules:
                val = self.ev.eval(formula)
                v['i%d' % item] = float(int(val)) if kind == 'UIQ' else val
        self.pts = {}
        for n, (x, y, z) in cab['pts'].items():
            self.pts[n] = (self.ev.eval(x), self.ev.eval(y), self.ev.eval(z))
        gap = inch(58) if (unit.defined(58) and 58 in unit.slots) else (v.get('sbdg') or 0.126)
        self.faces = []
        seen = {}
        for f in cab['faces']:
            code = f['code']
            if not re.fullmatch(r'\d{8}', code) or code[0] not in '0123':
                continue
            if f['cond'] and not self.ev.truth(f['cond']):
                continue
            n = int(code[3:5])
            if n == 0:
                continue
            xs = [self.pts[p][0] for p in f['pts'] if p in self.pts]
            zs = [self.pts[p][2] for p in f['pts'] if p in self.pts]
            if not xs or not zs:
                self.flags.append('face %s of %s has unknown points' % (code, cab['file']))
                continue
            t = int(code[0])
            kind = 'drawer' if t == 3 else ('door' if t in (1, 2) else 'open')
            face = {'n': n, 't': t, 'kind': kind, 'w': max(xs) - min(xs), 'h': max(zs) - min(zs), 'code': code,
                    'name': f['name'], 'pair': False, 'each_w': None}
            if kind == 'door':
                by_width = face['w'] > pair_width
                if self.pair_hint in (1, 2):
                    face['pair'] = (self.pair_hint == 2)
                    if face['pair'] != by_width:
                        self.flags.append('unit %s door D%d: record says %s, width %.3f" suggests %s; verify' % (
                            getattr(unit, 'seq', '?'), n, 'pair' if face['pair'] else 'single', face['w'], 'pair' if by_width else 'single'))
                else:
                    face['pair'] = by_width
                    if abs(face['w'] - pair_width) <= 2.0:
                        self.flags.append('unit %s door D%d is %.3f" wide, near the pair threshold %.2f" and the record gives no hint; verify single vs pair' % (
                            getattr(unit, 'seq', '?'), n, face['w'], pair_width))
                if face['pair']:
                    face['each_w'] = face['w'] / 2.0      # KCD halves the face; the pair gap is not subtracted (checked on 4 pairs)
            if n in seen:
                self.flags.append('unit %s: two live faces numbered D%d (%s and %s); second ignored' % (
                    getattr(unit, 'seq', '?'), n, seen[n]['code'], code))
                continue
            seen[n] = face
            self.faces.append(face)
        self.by_n = seen
        if self.ev.unknown:
            self.flags.append('unit %s (%s): unknown names in cab formulas: %s' % (
                getattr(unit, 'seq', '?'), cab['file'], ', '.join(sorted(self.ev.unknown))[:120]))

    def builtins(self, maxn=12):
        """D1..Dn builtins for the price scripts: DnW DnH DnT DnDR DnHG (0 when the face does not exist)."""
        b = {}
        for n in range(1, maxn + 1):
            for suf in ('', 'h', 'w', 't', 'hg', 'dr', 'hl', 'hk', 'hkn'):
                b['d%d%s' % (n, suf)] = 0.0
            f = self.by_n.get(n)
            if not f or f['kind'] == 'open':
                continue
            b['d%d' % n] = float(n)
            b['d%dw' % n] = round(f['w'] * 16) / 16.0         # KCD gives the scripts sizes to 1/16"
            b['d%dh' % n] = round(f['h'] * 16) / 16.0
            b['d%dt' % n] = float(f['t'])
            b['d%ddr' % n] = 1.0 if f['kind'] == 'drawer' else 0.0
            b['d%dhg' % n] = 1.0 if f['kind'] == 'door' else 0.0
        return b

    def describe(self):
        out = []
        for f in self.faces:
            s = 'D%d %s %s %.4f x %.4f' % (f['n'], f['kind'], f['code'], f['w'], f['h'])
            if f['pair']:
                s += ' PAIR each %.4f' % f['each_w']
            out.append(s)
        return out


if __name__ == '__main__':
    import argparse, kcdunits
    ap = argparse.ArgumentParser(description='List the door / drawer faces of every unit of a KCD job.')
    ap.add_argument('job')
    ap.add_argument('--lib', required=True, help='library root, compact catalog .json')
    ap.add_argument('--raw', help='rawlib.json (full library texts) when --lib is a compact catalog')
    ap.add_argument('--room', type=int)
    ap.add_argument('--pair', type=float, default=27.0)
    ap.add_argument('--rules', action='store_true', help='re-apply the U/UI/UIQ rules to the stored sizes')
    a = ap.parse_args()
    cat = kcdunits.Catalog.from_json(a.lib) if a.lib.lower().endswith('.json') else kcdunits.Catalog.from_library_root(a.lib)
    if a.raw:
        cat.load_rawlib_json(a.raw)
    job = kcdunits.read_job(a.job, cat)
    for u in job.units:
        if a.room and u.room != a.room:
            continue
        full = cat.full(u.cab)
        if not full:
            print('unit %d %s: no full cab' % (u.seq, u.cab))
            continue
        uf = UnitFaces(full, u, job, cat, pair_width=a.pair, apply_rules=a.rules)
        print('unit %d %s W=%.3f H=%.3f: %s' % (u.seq, u.cab, u.W, u.H, '; '.join(uf.describe()) or '-'))
        for fl in uf.flags:
            print('    VERIFY', fl)
