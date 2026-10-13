"""Compare engine output with the workbook paste blocks (keys_all.txt). Names are normalised; dims compared as
sixteenths; for the lines that match, the pasted price is compared with the engine's cost (see PRICE_TOL and
PRICE_TOL_CENTS). usage: compare_keys.py CAT PRICEDIR[;PACKDIR;...] KEYS JOB=KEYNAME ..."""
import sys, re, collections, math
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kcdunits, kcdprice

# How close a pasted price must be to the engine's cost to count as "the same price", in dollars.
# The pastes are mostly whole dollars (1126 of the 1242 lines in keys_all.txt) while the engine keeps cents, so
# for those a gap of up to half a dollar is rounding, not a real price difference. Exactly half a dollar counts
# as the same too (60.50 can be shown as 61); the tiny extra added in the code only absorbs float noise.
PRICE_TOL = 0.5
# When the pasted price shows cents (the other 116 lines, like 214.24) the two sides can be compared to the
# cent, so a 36-cent gap is a real difference there. One cent of slack covers the two sides rounding a half
# cent differently (30.25 against 30.26).
PRICE_TOL_CENTS = 0.01


def key_lines(keys, section):
    """Pull the pasted price lines of one workbook section out of the key file (keys = its text split into lines).
    Each line comes back as (unit number, part name, (dim, dim, dim) as pasted, price text as pasted)."""
    out = []; on = False; inblock = False
    for ln in keys:
        if ln.startswith('=== '):
            on = (ln[4:].strip() == section); inblock = False; continue
        if not on: continue
        if ln.startswith('K_price'): inblock = True; continue
        if ln.startswith('$') or ln.startswith('#'): inblock = False; continue
        if inblock and '\t' in ln:
            f = ln.split('\t') + [''] * 6
            if f[1].strip().isdigit():
                out.append((int(f[1]), f[2].strip(), tuple(x.strip() for x in (f[3], f[4], f[5])), f[0].strip()))
    return out

def norm(name):
    n = name.lower().strip()
    n = re.sub(r'^rm\d+\s+', '', n)
    n = re.sub(r'\s+', ' ', n)
    m = re.match(r'^([\d /]+)" drawer box-(.*)$', n)          # 2024: 7 1/2" Drawer Box-x ; 2026: Drawer Box-7 1/2"-x
    if m: n = 'drawer box-%s"-%s' % (m.group(1).strip(), m.group(2))
    n = n.replace('opt-', 'opt-')
    return n

def dims(l):
    return tuple(sorted(x for x in (kcdunits.sixteenths(l.dim1) if l.dim1 is not None else '', kcdunits.sixteenths(l.dim2) if l.dim2 is not None else '') if x))

def key_of(u, n, d):
    """What a pasted line is matched on: unit number, normalised name, and its dims sorted (blanks dropped)."""
    return (u, norm(n), tuple(sorted(x for x in d if x)))

def parse_price(text):
    """The pasted price cell as a number, or None when it is blank or not a number (then the line is "unpriced")."""
    t = (text or '').strip().replace('$', '').replace(',', '')
    if not t:
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return v if math.isfinite(v) else None        # the words "nan" or "inf" would otherwise poison the sums

def tolerance(text):
    """The allowed gap for one pasted price: to the cent when the paste shows cents, half a dollar otherwise."""
    return PRICE_TOL_CENTS if '.' in (text or '') else PRICE_TOL

def money(x):
    """Print a dollar amount the way the pastes do: 240 for whole dollars, 214.24 when there are cents."""
    return ('%.2f' % x).rstrip('0').rstrip('.')

def line_cost(l):
    """An engine line's cost as a number (a missing cost counts as 0)."""
    return float(l.cost) if l.cost is not None else 0.0

def price_check(K, lines):
    """Pair up the matched lines and compare their prices.
    A pasted line and an engine line match on (unit, normalised name, dims). When one key has several lines
    (say four identical shelves), each pasted line takes the engine line, not yet used, whose cost is closest to
    its price, so the result does not depend on the order the two sides list identical parts in. Pairs are made
    up to the smaller of the two counts, so the number of pairs equals the exact-match count of the room. An
    engine line with quantity 3 counts as three lines, because KCD prints it three times and the paste shows it
    three times. Pairs whose pasted price is blank or not a number are counted as "unpriced" and left out of the
    sums, so "sum paste" and "sum engine" always cover the same lines and can be compared."""
    eby = collections.defaultdict(list)    # key -> the engine lines not yet paired
    for l in lines:
        for _ in range(int(l.qty)):
            eby[(l.unit, norm(l.name), dims(l))].append(l)
    r = dict(matched=0, same=0, diff=0, unpriced=0, sum_paste=0.0, sum_engine=0.0, diffs=[])
    for u, n, d, ptext in K:               # paste order, so the differences are listed as they appear in the paste
        key = key_of(u, n, d)
        els = eby.get(key)
        if not els:
            continue                       # no engine line left for this key: it is not a match
        price = parse_price(ptext)
        if price is None:                  # an unpriced paste line takes whichever engine line is left first
            l = els.pop(0)
        else:
            l = els.pop(min(range(len(els)), key=lambda i: abs(price - line_cost(els[i]))))
        r['matched'] += 1
        if price is None:
            r['unpriced'] += 1
            continue
        cost = line_cost(l)
        r['sum_paste'] += price; r['sum_engine'] += cost
        if abs(price - cost) <= tolerance(ptext) + 1e-9:
            r['same'] += 1
        else:
            r['diff'] += 1
            r['diffs'].append((u, key[1], price, cost, l.script, l.lineno))
    return r

def compare_room(K, lines):
    """Compare one room's pasted lines (from key_lines) with the engine's PriceLine list. Returns a dict with
    everything the report prints: the two multisets, the match counts, the leftovers and the price check."""
    kset = collections.Counter(key_of(u, n, d) for u, n, d, p in K)
    eset = collections.Counter()
    for l in lines:
        for _ in range(int(l.qty)):
            eset[(l.unit, norm(l.name), dims(l))] += 1
    # exact matches (unit, name, dims)
    exact = sum((kset & eset).values())
    # name-only matches among the rest (dims differ)
    rk = kset - eset; re_ = eset - kset
    kn = collections.Counter((u, n) for (u, n, d), c in rk.items() for _ in range(c)); en = collections.Counter((u, n) for (u, n, d), c in re_.items() for _ in range(c))
    namematch = sum((kn & en).values())
    return dict(kset=kset, eset=eset, exact=exact, namematch=namematch, rk=rk, re_=re_, kn=kn, en=en, prices=price_check(K, lines))

def price_summary(label, P):
    """One line of price results, used per room and for the total."""
    return '%s matched %d, same price %d, different %d, unpriced in paste %d (sum paste %s, sum engine %s)' % (
        label, P['matched'], P['same'], P['diff'], P['unpriced'], money(P['sum_paste']), money(P['sum_engine']))

def print_room(section, R, flags):
    """Print one room's report. The lines up to 'flags:' are the original report and must stay as they are;
    the PRICES lines after them are the price check."""
    kset, eset, rk, re_, kn, en = R['kset'], R['eset'], R['rk'], R['re_'], R['kn'], R['en']
    print('=== %s: key %d lines, engine %d lines, exact %d, same name other dims %d, key-only %d, engine-only %d' % (
        section, sum(kset.values()), sum(eset.values()), R['exact'], R['namematch'], sum((kn - en).values()), sum((en - kn).values())))
    for (u, n), c in sorted((kn - en).items()):
        d = [k[2] for k in rk if k[0] == u and k[1] == n]
        print('   KEY ONLY   unit %-3d x%d %s %s' % (u, c, n, d[:2]))
    for (u, n), c in sorted((en - kn).items()):
        d = [k[2] for k in re_ if k[0] == u and k[1] == n]
        print('   ENGINE ONLY unit %-3d x%d %s %s' % (u, c, n, d[:2]))
    for (u, n) in sorted(set((kn & en).keys()))[:12]:
        print('   DIMS DIFFER unit %-3d %s key=%s engine=%s' % (u, n, [k[2] for k in rk if k[0] == u and k[1] == n][:2], [k[2] for k in re_ if k[0] == u and k[1] == n][:2]))
    if flags:
        print('   flags:', '; '.join(flags)[:600])
    P = R['prices']
    print('   ' + price_summary('PRICES:', P))
    for u, n, price, cost, script, lineno in P['diffs'][:15]:
        src = ('%s:%s' % (script, lineno)) if script and lineno is not None else (script or '?')
        print('   PRICE DIFF unit %-3d  %s  paste %s engine %s (%s)' % (u, n, money(price), money(cost), src))

def main(argv):
    cat = kcdunits.Catalog.from_json(argv[1]) if argv[1].lower().endswith('.json') else kcdunits.Catalog.from_library_root(argv[1]); keys = open(argv[3], encoding='utf-8').read().split('\n')
    # PRICEDIR may be several folders joined with ';' (the full base list first, then each update pack);
    # the engine layers them in that order, a later folder's file replacing an earlier one with the same name.
    pdirs = [p.strip() for p in argv[2].split(';') if p.strip()]
    pdir = pdirs if len(pdirs) > 1 else pdirs[0]
    if os.environ.get('KCD_RAWLIB'):
        cat.load_rawlib_json(os.environ['KCD_RAWLIB'])      # full .cab texts -> door and drawer faces
    tot_k = tot_m = 0
    T = dict(matched=0, same=0, diff=0, unpriced=0, sum_paste=0.0, sum_engine=0.0)
    for arg in argv[4:]:
        job_path, section = arg.split('=', 1)
        job = kcdunits.read_job(job_path, cat)
        eng = kcdprice.Engine(pdir, cat)
        eng.price_job(job)
        K = key_lines(keys, section)
        R = compare_room(K, eng.lines)
        print_room(section, R, eng.flags)
        tot_k += sum(R['kset'].values()); tot_m += R['exact']
        for k in T:
            T[k] += R['prices'][k]
    # This line is read by other tooling: keep its wording.
    print('TOTAL key lines %d, exact matches %d (%.1f%%)' % (tot_k, tot_m, 100.0 * tot_m / max(tot_k, 1)))
    print(price_summary('TOTAL PRICES:', T))

if __name__ == '__main__':
    main(sys.argv)
