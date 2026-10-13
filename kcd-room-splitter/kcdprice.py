"""Interpreter for KCD price-list scripts (.pcb), the language behind KCD's UNIT PRICE REVIEW.

Runs a price-list folder (for example C:\\KCD23-STDPLIST\\_26-08-03 AUG CFFL PRICING) against the units of
a room read by kcdunits.py, and returns the price lines the way KCD would print them. Everything the
engine is unsure about is written to its `flags` list so an engineer can verify instead of trusting it.

The language is documented in scratchpad notes/pricing/pcb-language-spec.md (Oct 2026). Short version:
one statement per line, comma-separated fields, a leading comma is a comment, `(cond):` may prefix a
field, `#Var` values are stored as text and resolved when used, `[expr]` evaluates now, `{expr}` formats a
dimension, `Do/Skip {}` blocks, `Load` includes another file in the same variable space, `End` leaves the
current file, `Price` emits a line.

Usage:
    eng = Engine(pricelist_dir, catalog)
    lines = eng.price_job(job)            # job from kcdunits.read_job
    for ln in lines: print(ln.unit, ln.qty, ln.name, ln.cost, ln.dim1, ln.dim2, ln.order)
"""
import os, re, sys, math, glob, fnmatch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kcdunits

MAX_DEPTH = 40          # recursion guard for lazy variable resolution
MAX_LOAD_DEPTH = 60
PAIR_WIDTH = 27.0       # fallback only: a door face wider than this is a pair when the unit record gives no hint


class PriceLine:
    __slots__ = ('unit', 'room', 'qty', 'name', 'cost', 'dim1', 'dim2', 'order', 'script', 'lineno', 'seq')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def __repr__(self):
        return 'PriceLine(unit=%r qty=%r name=%r cost=%r dim1=%r dim2=%r order=%r %s:%s)' % (
            self.unit, self.qty, self.name, self.cost, self.dim1, self.dim2, self.order, self.script, self.lineno)


class EndFile(Exception):
    pass


# ----------------------------------------------------------------------------- parsing

class Stmt:
    __slots__ = ('kind', 'raw', 'fields', 'lineno', 'block', 'tail')

    def __init__(self, kind, raw, fields, lineno):
        self.kind = kind
        self.raw = raw
        self.fields = fields
        self.lineno = lineno
        self.block = None
        self.tail = None


KEYWORDS = {'set', 'displayset', 'setonly', 'do', 'skip', 'load', 'loan', 'price', 'end', 'erase', 'setremove',
            'sendtofile', 'askquestion', 'len', 'left', 'right', 'readcsvfile', 'readcsvvalue', 'priceoptions', 'part', 'use'}


def quote_mask(s):
    """True at the positions that are inside a quoted literal. A '"' opens a literal only when the previous
    non-blank character is one of = < > ( : , * | & or the string start; otherwise it is an inch mark."""
    mask = [False] * len(s)
    q = False
    prev = ''
    for i, ch in enumerate(s):
        if ch == '"':
            if q:
                q = False
                continue
            if prev in ('', '=', '<', '>', '(', ':', ',', '*', '|', '&'):
                q = True
                continue
        if q:
            mask[i] = True
        if not ch.isspace():
            prev = ch
    return mask


def split_fields(s):
    """Split on commas (text values never contain commas; quoted literals may, so those are protected)."""
    mask = quote_mask(s)
    out, cur = [], []
    for i, ch in enumerate(s):
        if ch == ',' and not mask[i]:
            out.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append(''.join(cur))
    return out


def parse_script(text, name=''):
    """Parse a script into a list of Stmt; Do/Skip statements carry their block."""
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    top = []
    stack = [top]            # list of statement lists
    pending = []             # Do/Skip statements waiting for their '{' (one per nesting level)
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s:
            continue
        if s.startswith(','):
            continue
        if s.startswith('{'):
            if pending:
                st = pending.pop()
                st.block = []
                stack.append(st.block)
            else:
                stack.append([])        # orphan block: executes unconditionally
            continue
        if s.startswith('}'):
            if len(stack) > 1:
                stack.pop()
            continue
        # keyword = text before the first comma (Do may omit the comma: Do(cond):1)
        m = re.match(r'\s*([A-Za-z]+)\s*(?:,|(?=\()|$|(?=\s))(.*)$', s, re.S)
        if not m:
            continue
        kw = m.group(1).lower()
        if kw not in KEYWORDS:
            continue
        rest = m.group(2)
        tail = None
        if kw == 'price' and ';' in rest:
            cut = rest.find(';')
            tail = [t.strip() for t in rest[cut + 1:].split(';') if t.strip()]
            rest = rest[:cut]
        fields = [f.strip() for f in split_fields(rest)]
        st = Stmt(kw, s, fields, i)
        st.tail = tail
        stack[-1].append(st)
        if kw in ('do', 'skip'):
            pending.append(st)
    return top


# ----------------------------------------------------------------------------- helpers

def find_close(s, start):
    """Index of the parenthesis closing the one at s[start], quote-aware; -1 if unbalanced."""
    depth = 0
    mask = quote_mask(s)
    for i in range(start, len(s)):
        ch = s[i]
        if mask[i]:
            continue
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
            if depth == 0:
                return i
    return -1


def split_depth0(s, sep):
    """Split on sep at bracket depth 0, outside quotes."""
    out, cur, depth = [], [], 0
    mask = quote_mask(s)
    for i, ch in enumerate(s):
        q = mask[i]
        if not q:
            if ch in '([{':
                depth += 1
            elif ch in ')]}':
                depth = max(0, depth - 1)
            elif ch == sep and depth == 0:
                out.append(''.join(cur))
                cur = []
                continue
        cur.append(ch)
    out.append(''.join(cur))
    return out


def split_cond(field):
    """'(cond):rest' -> (cond, rest); otherwise (None, field)."""
    f = field.strip()
    if not f.startswith('('):
        return None, f
    j = find_close(f, 0)
    if j >= 0:
        k = f.find(':', j + 1)
        if k >= 0 and not f[j + 1:k].strip():
            return f[:j + 1], f[k + 1:].strip()
        # a parenthesised expression with no colon after it is a value, not a condition
        if k < 0:
            return None, f
    # unbalanced: first colon outside quotes followed by something plausible
    mask = quote_mask(f)
    for i, ch in enumerate(f):
        if ch == ':' and not mask[i]:
            if re.match(r'\s*[#\w(\[{\-.*@<"]', f[i + 1:] or ' ') or f[i + 1:].strip() == '':
                return f[:i], f[i + 1:].strip()
    return None, f


def balance_parens(s):
    """Drop closers with no opener and add the missing closers at the end (the scripts contain both)."""
    mask = quote_mask(s)
    out, depth = [], 0
    for i, ch in enumerate(s):
        if not mask[i]:
            if ch == '(':
                depth += 1
            elif ch == ')':
                if depth == 0:
                    continue
                depth -= 1
        out.append(ch)
    return ''.join(out) + ')' * depth


NUM_RE = re.compile(r'^[-+]?(\d+\.?\d*|\.\d+)$')


def is_number(s):
    return bool(NUM_RE.match(s.strip())) if isinstance(s, str) else isinstance(s, (int, float))


def fmt_num(v):
    """KCD stores [ ] results with two decimals."""
    if isinstance(v, float) and v == int(v) and abs(v) < 1e12:
        return '%d.00' % int(v)
    return '%.2f' % v


# ----------------------------------------------------------------------------- engine

class Engine:
    def __init__(self, pricelist_dir, catalog=None, afterprice=False, trace=False):
        self.dir = pricelist_dir
        self.catalog = catalog
        self.afterprice = afterprice
        self.trace = trace
        self.files = {}                 # lower name -> path (root first, then subfolders)
        for root, dirs, fs in os.walk(pricelist_dir):
            for f in fs:
                k = f.lower()
                if k not in self.files:
                    self.files[k] = os.path.join(root, f)
        self.scripts = {}               # lower name -> parsed statements
        self.vars = {}                  # lower #name -> text or float
        self.builtins = {}              # lower name -> float or list (opt)
        self.lines = []
        self.flags = []
        self.log = []
        self.loadstack = []
        self.unit = None
        self.job = None
        self.missing_loads = set()
        self.unknown_idents = {}

    # -- bookkeeping ----------------------------------------------------------------------------
    def flag(self, text):
        if text not in self.flags:
            self.flags.append(text)

    def where(self):
        return self.loadstack[-1] if self.loadstack else '?'

    def script(self, name):
        k = name.strip().lower()
        if k in self.scripts:
            return self.scripts[k]
        path = self.files.get(k)
        if not path:
            return None
        text = open(path, 'rb').read().decode('cp1252', 'replace')
        self.scripts[k] = parse_script(text, name)
        return self.scripts[k]

    # -- variables ------------------------------------------------------------------------------
    def setvar(self, name, value):
        self.vars[name.lower().lstrip('#')] = value

    def getvar(self, name):
        return self.vars.get(name.lower().lstrip('#'))

    VAR_RE = re.compile(r'#([A-Za-z0-9_$][A-Za-z0-9_$-]*)')

    def resolve(self, text, depth=0, numeric=False):
        """Replace every #Var in text by its value (recursively). Longest defined name wins."""
        if not isinstance(text, str):
            return fmt_num(float(text)) if numeric is False else text
        if '#' not in text:
            return text
        if depth > MAX_DEPTH:
            self.flag('variable resolution too deep in %s: %s' % (self.where(), text[:60]))
            return text
        out = []
        i = 0
        while i < len(text):
            if text[i] == '#':
                m = self.VAR_RE.match(text, i)
                if not m:
                    out.append('#')
                    i += 1
                    continue
                run = m.group(1)
                # longest defined prefix (names may contain '-', so try shrinking)
                chosen = None
                for L in range(len(run), 0, -1):
                    cand = run[:L]
                    if cand.lower() in self.vars:
                        chosen = cand
                        break
                if chosen is None:
                    chosen = run.rstrip('-')
                    val = ''
                    self.unknown_idents['#' + chosen.lower()] = self.unknown_idents.get('#' + chosen.lower(), 0) + 1
                else:
                    val = self.vars[chosen.lower()]
                if isinstance(val, float):
                    val = fmt_num(val)
                elif isinstance(val, str) and '#' in val:
                    val = self.resolve(val, depth + 1)
                out.append(val)
                i += 1 + len(chosen)
            else:
                out.append(text[i])
                i += 1
        return ''.join(out)

    # -- numbers ---------------------------------------------------------------------------------
    TOKEN_RE = re.compile(r'\s*(?:(\d+\.?\d*|\.\d+)\s*(in|mm)?|([A-Za-z][A-Za-z0-9_]*)|(<>|>=|<=|=>|[-+*/\\%^()\[\]{}])|(.))', re.I)

    def builtin(self, name):
        v = self.builtins.get(name.lower())
        return v

    def eval_num(self, text, strict=False):
        """Evaluate arithmetic. Returns float, or None when the text is not numeric (unknown word)."""
        if isinstance(text, (int, float)):
            return float(text)
        s = self.resolve(text).strip()
        if s == '':
            return 0.0
        toks = []
        pos = 0
        bad = False
        while pos < len(s):
            m = self.TOKEN_RE.match(s, pos)
            if not m or m.end() == pos:
                break
            pos = m.end()
            if m.group(1) is not None:
                v = float(m.group(1))
                if (m.group(2) or '').lower() == 'mm':
                    v /= 25.4
                toks.append(('n', v))
            elif m.group(3):
                b = self.builtin(m.group(3))
                if b is None:
                    bad = True
                    self.unknown_idents[m.group(3).lower()] = self.unknown_idents.get(m.group(3).lower(), 0) + 1
                    toks.append(('n', 0.0))
                elif isinstance(b, list):
                    toks.append(('n', float(b[0]) if b else 0.0))
                else:
                    toks.append(('n', float(b)))
            elif m.group(4):
                op = m.group(4)
                toks.append(('o', op))
            else:
                bad = True        # stray character such as '"' or ':'
        if bad and strict:
            return None
        if bad and not toks:
            return None
        if not any(t[0] == 'n' for t in toks):
            return None
        self._toks = toks
        self._p = 0
        try:
            v = self._expr()
        except Exception:
            return None
        return v

    def _peek(self):
        return self._toks[self._p] if self._p < len(self._toks) else (None, None)

    def _next(self):
        t = self._peek()
        self._p += 1
        return t

    def _expr(self):
        v = self._term()
        while True:
            k, op = self._peek()
            if k == 'o' and op in '+-':
                self._next()
                r = self._term()
                v = v + r if op == '+' else v - r
            else:
                return v

    def _term(self):
        v = self._power()
        while True:
            k, op = self._peek()
            if k == 'o' and op in ('*', '/', '\\', '%'):
                self._next()
                r = self._power()
                if op == '*':
                    v = v * r
                elif op == '/':
                    v = v / r if r else 0.0
                elif op == '\\':
                    v = float(int(v / r)) if r else 0.0
                else:
                    v = math.fmod(v, r) if r else 0.0
            else:
                return v

    def _power(self):
        v = self._unary()
        k, op = self._peek()
        if k == 'o' and op == '^':
            self._next()
            r = self._unary()
            try:
                v = v ** r
            except Exception:
                v = 0.0
        return v

    def _unary(self):
        k, op = self._peek()
        if k == 'o' and op in '+-':
            self._next()
            v = self._unary()
            return -v if op == '-' else v
        if k == 'o' and op in '([{':
            self._next()
            v = self._expr()
            k2, op2 = self._peek()
            if k2 == 'o' and op2 in ')]}':
                self._next()
            return v
        if k == 'o' and op in ')]}':
            self._next()               # stray closer: ignore
            return self._unary() if self._peek()[0] is not None else 0.0
        if k == 'n':
            self._next()
            return op
        if k == 'o':                   # comparison operator inside arithmetic: stop
            raise ValueError('operator')
        return 0.0

    def fmt_dim(self, v):
        """{expr}: KCD's display form of a dimension (nearest 1/16, as a fraction)."""
        if v is None:
            return ''
        return kcdunits.sixteenths(v)

    # -- conditions ------------------------------------------------------------------------------
    CMP_RE = re.compile(r'(<>|>=|<=|=>|=|>|<)')

    def eval_cond(self, text):
        s = balance_parens(text.strip())
        if s == '':
            return True
        return self._eval_or(s)

    def _strip_parens(self, s):
        s = s.strip()
        while s.startswith('(') and find_close(s, 0) == len(s) - 1:
            s = s[1:-1].strip()
        return s

    def _eval_or(self, s):
        parts = split_depth0(s, '|')
        if len(parts) > 1:
            return any(self._eval_and(p) for p in parts)
        return self._eval_and(s)

    def _eval_and(self, s):
        parts = split_depth0(s, '&')
        if len(parts) > 1:
            return all(self._eval_cmp(p) for p in parts)
        return self._eval_cmp(s)

    def _eval_cmp(self, s):
        s0 = s
        s = self._strip_parens(s)
        if s == '':
            return True
        if ('|' in split_depth0(s, '|')[0] and False) or len(split_depth0(s, '|')) > 1 or len(split_depth0(s, '&')) > 1:
            return self._eval_or(s)
        # find a comparison operator at depth 0 outside quotes
        depth = 0
        mask = quote_mask(s)
        i = 0
        while i < len(s):
            ch = s[i]
            if not mask[i]:
                if ch in '([{':
                    depth += 1
                elif ch in ')]}':
                    depth -= 1
                elif depth <= 0 and ch in '<>=':
                    m = self.CMP_RE.match(s, i)
                    if m:
                        return self.compare(s[:i], m.group(1), s[m.end():])
            i += 1
        # bare truth test
        v = self.eval_num(s, strict=True)
        if v is not None:
            return v != 0
        t = self.resolve(s).strip().strip('"')
        return t != '' and t.lower() not in ('0', 'no', 'false', '0.00')

    def compare(self, left, op, right):
        if op == '=>':
            op = '>='
        l = left.strip()
        r = right.strip()
        # opt is multi-valued: (opt=n) means n is among the unit's options
        if l.lower() in ('opt', 'option') or r.lower() in ('opt', 'option'):
            other = r if l.lower() in ('opt', 'option') else l
            n = self.eval_num(other)
            opts = self.builtins.get('opt') or []
            inside = n is not None and any(abs(float(o) - n) < 1e-9 for o in opts)
            return inside if op == '=' else (not inside if op == '<>' else False)
        # wildcard flag: (x<>*"ESS-*")
        if r.startswith('*"'):
            r = r[1:]
        lt = self.resolve(l).strip()
        rt = self.resolve(r).strip()
        ln = self.eval_num(lt, strict=True) if not lt.startswith('"') else None
        rn = self.eval_num(rt, strict=True) if not rt.startswith('"') else None
        if ln is not None and rn is not None:
            if op == '=':
                return abs(ln - rn) < 1e-9
            if op == '<>':
                return abs(ln - rn) >= 1e-9
            if op == '>':
                return ln > rn + 1e-9
            if op == '<':
                return ln < rn - 1e-9
            if op == '>=':
                return ln >= rn - 1e-9
            if op == '<=':
                return ln <= rn + 1e-9
        a = lt.strip('"').strip().lower()
        b = rt.strip('"').strip().lower()
        if b.startswith('@'):
            b = b[1:].strip()
        if a.startswith('@'):
            a = a[1:].strip()
        # unset or empty against a number: treat as 0
        if a == '' and rn is not None:
            a = '0'
            ln = 0.0
        if b == '' and ln is not None:
            b = '0'
            rn = 0.0
        if ln is not None and rn is not None:
            return (abs(ln - rn) < 1e-9) if op == '=' else (abs(ln - rn) >= 1e-9 if op == '<>' else False)
        if '*' in a or '*' in b:
            pat = b if '*' in b else a
            val = a if '*' in b else b
            eq = fnmatch.fnmatchcase(val, pat.replace('[', '[[]'))
        else:
            eq = a == b
        if op == '=':
            return eq
        if op == '<>':
            return not eq
        # ordered text compare (rare)
        try:
            return {'>': a > b, '<': a < b, '>=': a >= b, '<=': a <= b}[op]
        except KeyError:
            return False

    # -- statements ------------------------------------------------------------------------------
    def run_file(self, name, required=True):
        stmts = self.script(name)
        if stmts is None:
            if name.strip().lower() not in self.missing_loads:
                self.missing_loads.add(name.strip().lower())
                self.flag('Load target missing: %s (from %s)' % (name.strip(), self.where()))
            return
        if name.strip().lower() in (n.lower() for n in self.loadstack):
            self.flag('recursive Load of %s skipped (from %s)' % (name, self.where()))
            return
        if len(self.loadstack) > MAX_LOAD_DEPTH:
            self.flag('Load nesting too deep at %s' % name)
            return
        self.loadstack.append(name.strip())
        try:
            self.run_block(stmts)
        except EndFile:
            pass
        finally:
            self.loadstack.pop()

    def run_block(self, stmts):
        for st in stmts:
            self.exec(st)

    def exec(self, st):
        k = st.kind
        f = st.fields
        if self.trace:
            self.log.append('%s:%d %s' % (self.where(), st.lineno, st.raw[:100]))
        if k in ('set', 'displayset', 'setonly'):
            self.do_set(f[0] if f else '', k)
        elif k in ('do', 'skip'):
            cond, count = split_cond(f[0] if f else '')
            ok = self.eval_cond(cond) if cond is not None else True
            if k == 'skip':
                ok = not ok
            if ok and st.block is not None:
                n = self.eval_num(count) if count else 1.0
                n = 1 if n is None else int(min(max(n, 0), 50))
                for _ in range(n):
                    self.run_block(st.block)
        elif k in ('load', 'loan'):
            cond, fname = split_cond(f[0] if f else '')
            if cond is None or self.eval_cond(cond):
                if fname:
                    self.run_file(self.resolve(fname).strip())
        elif k == 'end':
            raise EndFile()
        elif k == 'price':
            self.do_price(st)
        elif k in ('erase', 'setremove'):
            if f and f[0].strip().startswith('#') and '\\' not in f[0]:
                self.vars.pop(f[0].strip().lower().lstrip('#'), None)
            else:
                self.log.append('Erase file (ignored): %s' % (f[0] if f else ''))
        elif k == 'sendtofile':
            self.log.append('SendToFile %s: %s' % (self.resolve(f[0]) if f else '', self.resolve(f[1]) if len(f) > 1 else ''))
        elif k == 'askquestion':
            if len(f) >= 2:
                self.setvar(f[0], self.resolve(f[1]))
                self.flag('AskQuestion %s answered with its default (%s)' % (f[0], self.resolve(f[1])))
        elif k == 'len':
            if len(f) >= 2:
                self.setvar(f[0], float(len(self.resolve(f[1]))))
        elif k in ('left', 'right'):
            if len(f) >= 3:
                n = self.eval_num(f[1])
                src = self.resolve(f[2])
                n = int(n) if n is not None else 0
                n = max(0, min(n, len(src)))
                # KCD trims the result: Right,#x,5,"Cashmere  1 1.00" prints as "1.00" (checked on the reviews)
                self.setvar(f[0], (src[:n] if k == 'left' else (src[len(src) - n:] if n else '')).strip())
        elif k == 'readcsvfile':
            self._csv = f[0].strip() if f else ''
        elif k == 'readcsvvalue':
            self.do_readcsv(f)
        elif k == 'priceoptions':
            self.do_priceoptions(st)
        elif k in ('part', 'use'):
            pass

    def do_set(self, field, kind):
        cond, rest = split_cond(field)
        if cond is not None and not self.eval_cond(cond):
            # else branch?
            parts = self._split_assign(rest)
            if len(parts) > 1:
                self.assign(parts[1])
            return
        parts = self._split_assign(rest)
        if parts:
            self.assign(parts[0])

    def _split_assign(self, rest):
        """'#A=x:#B=y' -> ['#A=x', '#B=y'] (colon at depth 0 followed by an assignment)."""
        out, cur, depth = [], [], 0
        mask = quote_mask(rest)
        i = 0
        while i < len(rest):
            ch = rest[i]
            if not mask[i]:
                if ch in '([{<':
                    depth += 1
                elif ch in ')]}>':
                    depth = max(0, depth - 1)
                elif ch == ':' and depth == 0 and re.match(r'\s*#?[A-Za-z0-9_$][A-Za-z0-9_$-]*\s*=', rest[i + 1:]):
                    out.append(''.join(cur))
                    cur = []
                    i += 1
                    continue
            cur.append(ch)
            i += 1
        out.append(''.join(cur))
        return [p for p in out if p.strip() != '']

    def assign(self, text):
        if '=' not in text:
            return
        target, value = text.split('=', 1)
        target = target.strip()
        value = value.strip()
        if not target:
            return
        if target.lower() in ('#door', 'door') and re.match(r'^[dD](\d+)$', value):
            self.select_door_slot(int(value[1:]))
        if value.startswith('[') and find_close(value, 0) == len(value) - 1:
            v = self.eval_num(value)
            self.setvar(target, v if v is not None else 0.0)
        elif value.startswith('<') and value.endswith('>'):
            self.setvar(target, self.resolve(value[1:-1]).strip())
        elif value.startswith('{') and value.endswith('}'):
            v = self.eval_num(value[1:-1])
            self.setvar(target, self.fmt_dim(v) if v is not None else self.resolve(value[1:-1]))
        else:
            self.setvar(target, value)

    def select_door_slot(self, n):
        """Set, #Door=Dn: KCD exposes face n to the script as #DoorW/#DoorH/#doorT and marks it as a single door
        (#DoorSD), a pair (#DoorLD and #DoorRD, #DoorW = half width) or a drawer front (#DoorDR)."""
        uf = getattr(self, 'unit_faces', None)
        if uf is not None:
            f = uf.by_n.get(n)
            self.setvar('#DoorSD', 0.0)
            self.setvar('#DoorLD', 0.0)
            self.setvar('#DoorRD', 0.0)
            self.setvar('#DoorDR', 0.0)
            if not f or f['kind'] == 'open':
                self.setvar('#DoorW', 0.0)
                self.setvar('#DoorH', 0.0)
                self.setvar('#doorT', 0.0)
                self.setvar('#DoorT', 0.0)
                return
            self.setvar('#DoorH', f['h'])
            self.setvar('#doorT', float(f['t']))
            self.setvar('#DoorT', float(f['t']))
            if f['kind'] == 'drawer':
                self.setvar('#DoorW', f['w'])
                self.setvar('#DoorDR', float(n))
            elif f['pair']:
                self.setvar('#DoorW', f['each_w'])
                self.setvar('#DoorLD', float(n))
                self.setvar('#DoorRD', float(n))
            else:
                self.setvar('#DoorW', f['w'])
                self.setvar('#DoorSD', float(n))
            return
        b = self.builtins
        w = b.get('d%dw' % n, 0.0); t = b.get('d%dt' % n, 0.0); dr = b.get('d%ddr' % n, 0.0)
        self.setvar('#DoorW', w)
        self.setvar('#doorT', t)
        self.setvar('#DoorT', t)
        self.setvar('#DoorSD', float(n) if (t > 0 and not dr) else 0.0)
        self.setvar('#DoorLD', 0.0)
        self.setvar('#DoorRD', 0.0)
        self.setvar('#DoorDR', float(n) if dr else 0.0)

    def do_readcsv(self, f):
        if len(f) < 3:
            return
        path = self.files.get(f[0].strip().lower())
        key = self.resolve(f[1]).strip().lower()
        if not path:
            self.flag('CSV missing: %s' % f[0])
            return
        import csv
        for row in csv.reader(open(path, encoding='cp1252', errors='replace')):
            if row and row[0].strip().lower() == key:
                for j, var in enumerate(f[2:], 1):
                    if j < len(row):
                        self.setvar(var, row[j].strip())
                return

    def do_priceoptions(self, st):
        """KCD's built-in option pricing: one line per option of the unit, from options.dat."""
        total = 0.0
        if not self.catalog or not self.catalog.options:
            self.flag('PriceOptions: no options.dat loaded; option lines not produced')
            return
        for n in self.builtins.get('opt') or []:
            o = self.catalog.options.get(int(n))
            if not o:
                self.flag('option number %d not in options.dat (unit %s)' % (n, self.unit.seq if self.unit else '?'))
                continue
            name, cost, enabled = o
            cost = cost or 0.0
            total += cost
            self.emit(1.0, name, cost, None, None, None, st, source='options.dat')
        self.builtins['totopcst'] = total

    def do_price(self, st):
        f = st.fields + [''] * 8
        cond, qty = split_cond(f[0])
        if cond is not None and not self.eval_cond(cond):
            return
        q = self.eval_num(qty) if qty.strip() else 1.0
        if q is None:
            q = 1.0
        name = f[1]
        c2, rest = split_cond(name)
        if c2 is not None:
            parts = split_depth0(rest, ':')
            name = parts[0] if self.eval_cond(c2) else (parts[1] if len(parts) > 1 else '')
        name = re.sub(r'\s+', ' ', self.resolve(name)).strip()
        cost = self.eval_num(f[2]) if f[2].strip() else 0.0
        if cost is None:
            self.flag('cost not numeric: %r in %s:%d' % (f[2], self.where(), st.lineno))
            cost = 0.0
        dim1 = self.eval_num(f[3]) if f[3].strip() else None
        dim2 = self.eval_num(f[4]) if f[4].strip() else None
        order = self.eval_num(f[5]) if f[5].strip() else None
        if q <= 0:
            return
        self.emit(q, name, cost, dim1, dim2, order, st)
        for t in st.tail or []:
            self.assign(t)

    def emit(self, qty, name, cost, dim1, dim2, order, st, source=None):
        ln = PriceLine(unit=self.unit.seq if self.unit else 0, room=self.unit.room if self.unit else 0, qty=qty, name=name,
                       cost=round(cost + 1e-9, 2), dim1=dim1, dim2=dim2, order=order, script=source or self.where(), lineno=st.lineno,
                       seq=len(self.lines))
        self.lines.append(ln)
        if self.afterprice and source is None:
            saved = {k: self.vars.get(k) for k in ('name', 'cost', 'number', 'width', 'length', 'depth')}
            self.setvar('#Name', name)
            self.setvar('#Cost', cost)
            self.setvar('#Number', float(qty))
            self.setvar('#Width', dim1 if dim1 is not None else 0.0)
            self.setvar('#Length', dim2 if dim2 is not None else 0.0)
            self.setvar('#Depth', 0.0)
            self.run_file('XXAfterPrice.PCB')
            for k, v in saved.items():
                if v is None:
                    self.vars.pop(k, None)
                else:
                    self.vars[k] = v

    # -- unit context ----------------------------------------------------------------------------
    def set_unit(self, u, job):
        self.unit = u
        b = {}
        inch = u.inch
        def defined_inch(item):
            return inch(item) if (u.defined(item) is not False) else 0.0
        b.update({'w': inch(2), 'h': inch(3), 'd': inch(4), 'ls': defined_inch(5), 'ms': defined_inch(6), 'rs': defined_inch(7),
                  'tr': defined_inch(8), 'mr': defined_inch(9), 'br': defined_inch(10), 'k': defined_inch(11), 'z': inch(13),
                  'lmr': defined_inch(21), 'lms': defined_inch(51), 'llms': 0.0, 'bms': defined_inch(105), 'ms2': defined_inch(162),
                  'ms3': defined_inch(163), 'ms4': defined_inch(164), 'ms5': defined_inch(165), 'ms6': defined_inch(166),
                  'fw': inch(2), 'lccd': inch(28), 'rccd': inch(29), 'lcb': inch(16), 'rcb': inch(17),
                  'crodht1': inch(251), 'crodht2': inch(252), 'crodht3': inch(253),
                  'dh1': inch(20), 'dh2': inch(22), 'dh3': inch(23), 'dh4': inch(24), 'dh5': inch(25), 'dh6': inch(26),
                  'dh7': inch(135), 'dh8': inch(136), 'dh9': inch(137), 'dh10': 0.0,
                  't': float(u.T), 'num': float(u.qty or 1), 'opt': [float(o) for o in u.options],
                  'bkyn': float(u.count(121)), 'nkhyn': float(u.count(119)), 'ul': 0.0, 'ur': 0.0, 'ult': 0.0, 'urt': 0.0,
                  'uld': 0.0, 'urd': 0.0, 'ulz': 0.0, 'urz': 0.0, 'ulk': 0.0, 'urk': 0.0, 'ulfl': 0.0, 'urfr': 0.0, 'fl': 0.0, 'fr': 0.0,
                  'bbl': 0.0, 'bbr': 0.0, 'ct': 1.0 if inch(12) > 0 and u.defined(12) else 0.0, 'ctl': 0.0, 'ctr': 0.0, 'ctf': 0.0, 'ctb': 0.0,
                  'npo': float(u.count(38)) if u.defined(38) else 0.0, 'ndiv': float(u.count(60)) if u.defined(60) and u.is_integer_item(60) else 1.0,
                  'ndwr': 1.0, 'nfl': float(u.count(80)) if u.defined(80) else 0.0, 'ssn': 0.0, 'wss': 0.0, 'cdu': 0.0, 'le': 0.0,
                  'drgp': inch(58), 'lsrv': inch(56), 'rsrv': inch(57), 'stsrv': inch(56), 'h3ht': 999.0, 'h4ht': 999.0, 'h5ht': 999.0,
                  'totopcst': 0.0, 'mldnum': 0.0, 'pt': float(u.count(102)) if u.defined(102) else 0.0, 'pn': 0.0, 'pd': 0.0,
                  'doordraweronly': 0.0, 'dooronly': 0.0, 'drh': 0.0, 'i70': float(u.count(70)), 'i71': float(u.count(71)),
                  'i72': float(u.count(72)), 'i73': float(u.count(73)), 'i201': 0.0, 'i202': 0.0, 'i203': 0.0, 'i204': 0.0,
                  'codepre': 0.0, 'wb1h': 0.0, 'wb2h': 0.0, 'wb3h': 0.0, 'wb4h': 0.0, 'yes': 1.0})
        # shelf counts: SH = total adjustable shelves, SH1 top opening, SH2 bottom, SH3 middle (see notes)
        counts = u.shelf_counts()
        sh1 = counts.get(31, 0); sh2 = counts.get(32, 0); sh3 = counts.get(33, 0)
        total = counts.get(19, sh1 + sh2 + sh3)
        b.update({'sh': float(total), 'sh1': float(sh1), 'sh2': float(sh2), 'sh3': float(sh3), 'sh4': 0.0, 'sh5': float(counts.get(160, 0)), 'sh6': float(counts.get(161, 0))})
        # every I<n> slot as a builtin too
        for n, (raw, state) in u.slots.items():
            b['i%d' % n] = float(u.value(n))
        # door / drawer-front faces D1..D12: from the .cab face rules when the full library is loaded,
        # otherwise the provisional slot-based model (drawer fronts only)
        for n in range(1, 13):
            for suf in ('', 'h', 'w', 't', 'hg', 'dr', 'hl', 'hk', 'hkn'):
                b['d%d%s' % (n, suf)] = 0.0
        self.unit_faces = None
        full = self.catalog.full(u.cab) if (self.catalog is not None and hasattr(self.catalog, 'full')) else None
        if full and full.get('faces') and full.get('pts'):
            import kcdcab
            uf = kcdcab.UnitFaces(full, u, job, self.catalog, pair_width=PAIR_WIDTH)
            b.update(uf.builtins())
            self.unit_faces = uf
            for fl in uf.flags:
                self.flag(fl)
        else:
            self.faces_from_unit(u, b)
        self.builtins = b
        # KCD-supplied #-variables
        self.setvar('#UnitFileName', u.cab)
        self.setvar('#UnitLibrary', u.lib.strip('\\'))
        self.setvar('#PartFileName', u.prt)
        self.setvar('#Name', self.unit_display_name(u))
        self.setvar('#Code', u.cat)
        self.setvar('#Roomnum', str(u.room))
        self.setvar('#RoomNum', str(u.room))
        texts = u.set_unit_info
        defaults = job.room_defaults[u.room - 1] if 1 <= u.room <= len(job.room_defaults) else [''] * 15
        for i in range(15):
            t = texts[i] if i < len(texts) and texts[i] else (defaults[i] if i < len(defaults) else '')
            self.setvar('#ExtraUnitText%d' % (i + 1), t)
        self.setvar('#DisplayEdit', 0.0)
        self.setvar('#incm', '-Inch')
        self.setvar('#Comma', ',')

    def unit_display_name(self, u):
        n = u.name.strip()
        if not n or re.match(r'^=#\d+#=$', n):
            return u.cat.strip()
        return n

    def faces_from_unit(self, u, b):
        """Provisional face model. Drawer fronts: the slots whose .cab label says 'Drawer Front height'
        (or Dr/Dwr Front), in slot order, up to I37 '# Drawer Openings'. Doors: not derived yet (KCD takes them
        from the .cab face rules); flagged when a door-height slot is present."""
        fronts = []
        doors = []
        for n in (41, 42, 43, 44, 45, 46, 147, 148, 149):
            if n not in u.slots or not u.defined(n):
                continue
            lab = u.label(n).lower()
            if re.search(r'(dr|dwr|drawer)\s*fr(on)?t', lab) or 'drawer front' in lab:
                fronts.append(n)
            elif 'door' in lab:
                doors.append(n)
        ndr = u.count(37) if u.defined(37) else len(fronts)
        if fronts and ndr and ndr < len(fronts):
            fronts = fronts[:ndr]
        width = u.W - u.inch(56) - u.inch(57)
        slot = 1
        for n in fronts:
            b['d%d' % slot] = float(slot)
            b['d%dh' % slot] = u.inch(n)
            b['d%dw' % slot] = width
            b['d%dt' % slot] = 3.0
            b['d%ddr' % slot] = 1.0
            slot += 1
        if doors:
            self.flag('unit %d (%s): door-height slot present (%s); doors are not priced yet, verify' % (u.seq, u.cab, ', '.join('I%d' % n for n in doors)))
        self.setvar('#ProvisionalFronts', float(len(fronts)))

    # -- job driver -------------------------------------------------------------------------------
    def price_job(self, job, rooms=None, setup=True):
        self.job = job
        self.lines = []
        if setup:
            self.vars = {}
            self.setvar('#JobExportName', os.path.splitext(job.name)[0])
            for i, r in enumerate(job.rooms, 1):
                self.setvar('#RoomName%d' % i, r)
            self.setvar('#RoomName', job.rooms[0] if job.rooms else '')
            self.setvar('#Comma', ',')
            self.setvar('#DisplayEdit', 0.0)
            self.unit = None
            self.builtins = {'yes': 1.0, 'opt': [], 'num': 1.0, 't': 0.0, 'w': 0.0, 'h': 0.0, 'd': 0.0}
            self.run_file('A-SetUp.Pcb')
        for u in job.units:
            if rooms and u.room not in rooms:
                continue
            self.set_unit(u, job)
            self.run_file('xxbefore.pcb')
            pcb = (u.pcb or '').strip()
            if not pcb or pcb.lower() == 'none':
                self.log.append('unit %d (%s) has no price script: nothing printed' % (u.seq, u.cab))
                self.run_file('XXAfter.PCB')
                continue
            elif pcb.lower() not in self.files:
                # the job record keeps the script name from the day the unit was placed; a newer list may have
                # renamed it (CFClosetAccessory.pcb -> ClosetAccessories.pcb in 2026), so try the library's current name
                alt = (u.cabdef or {}).get('pcb', '') if getattr(u, 'cabdef', None) else ''
                if alt and alt.strip().lower() != 'none' and alt.strip().lower() in self.files:
                    self.flag('unit %d: price script %s not in the price list; the library now names %s, used that' % (u.seq, pcb, alt.strip()))
                    pcb = alt.strip()
                else:
                    self.flag('unit %d: price script %s not in the price list; Eachunit.pcb used' % (u.seq, pcb))
                    pcb = 'Eachunit.pcb'
            self.run_file(pcb)
            self.run_file('XXAfter.PCB')
        self.run_file('Xxend.pcb')
        self.run_file('XXFinal.PCB')
        return self.lines

    # -- output ------------------------------------------------------------------------------------
    def sorted_lines(self):
        """Per unit, by print order (stable), like the review."""
        return sorted(self.lines, key=lambda l: (l.unit, l.order if l.order is not None else 9999, l.seq))

    def tsv(self):
        out = ['price\tunit\tqty\tpart\tdim1\tdim2\torder\tscript']
        for l in self.sorted_lines():
            out.append('\t'.join([('%g' % l.cost), str(l.unit), ('%g' % l.qty), l.name,
                                  kcdunits.sixteenths(l.dim1) if l.dim1 is not None else '',
                                  kcdunits.sixteenths(l.dim2) if l.dim2 is not None else '',
                                  ('%g' % l.order) if l.order is not None else '', '%s:%d' % (l.script, l.lineno)]))
        return '\n'.join(out)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Price a KCD .job with a KCD price-list folder.')
    ap.add_argument('job')
    ap.add_argument('--pricelist', required=True, help='price list folder (for example C:\\KCD23-STDPLIST\\_26-08-03 AUG CFFL PRICING)')
    ap.add_argument('--lib', required=True, help='KCD library root or compact catalog .json')
    ap.add_argument('--raw', help='rawlib.json with the full .cab texts (needed for doors when --lib is a compact catalog)')
    ap.add_argument('--room', type=int, help='only this room number')
    ap.add_argument('--afterprice', action='store_true', help='also run XXAfterPrice.PCB after every line (slow, totals only)')
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--unknown', action='store_true', help='list unknown identifiers and variables')
    a = ap.parse_args()
    cat = kcdunits.Catalog.from_json(a.lib) if a.lib.lower().endswith('.json') else kcdunits.Catalog.from_library_root(a.lib)
    if a.raw:
        cat.load_rawlib_json(a.raw)
    job = kcdunits.read_job(a.job, cat)
    eng = Engine(a.pricelist, cat, afterprice=a.afterprice, trace=a.trace)
    eng.price_job(job, rooms=[a.room] if a.room else None)
    print(eng.tsv())
    print()
    print('FLAGS (%d):' % len(eng.flags))
    for fl in eng.flags:
        print('  VERIFY', fl)
    if a.unknown:
        print('unknown identifiers:', sorted(eng.unknown_idents.items(), key=lambda x: -x[1])[:60])
    if a.trace:
        print('\n'.join(eng.log[-200:]))
