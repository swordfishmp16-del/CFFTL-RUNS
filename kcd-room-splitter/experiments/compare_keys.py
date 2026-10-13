"""Compare engine output with the workbook paste blocks (keys_all.txt). Prices are ignored (different list
versions); names are normalised; dims compared as sixteenths. usage: compare_keys.py CAT PRICEDIR KEYS JOB=KEYNAME ..."""
import sys, re, collections
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kcdunits, kcdprice
cat = kcdunits.Catalog.from_json(sys.argv[1]) if sys.argv[1].lower().endswith('.json') else kcdunits.Catalog.from_library_root(sys.argv[1]); pdir = sys.argv[2]; keys = open(sys.argv[3], encoding='utf-8').read().split('\n')
if os.environ.get('KCD_RAWLIB'):
    cat.load_rawlib_json(os.environ['KCD_RAWLIB'])      # full .cab texts -> door and drawer faces

def key_lines(section):
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

tot_k = tot_m = 0
for arg in sys.argv[4:]:
    job_path, section = arg.split('=', 1)
    job = kcdunits.read_job(job_path, cat)
    eng = kcdprice.Engine(pdir, cat)
    eng.price_job(job)
    K = key_lines(section)
    kset = collections.Counter((u, norm(n), tuple(sorted(x for x in d if x))) for u, n, d, p in K)
    eset = collections.Counter()
    for l in eng.lines:
        for _ in range(int(l.qty)):
            eset[(l.unit, norm(l.name), dims(l))] += 1
    # exact matches (unit, name, dims)
    exact = sum((kset & eset).values())
    # name-only matches among the rest (dims differ)
    rk = kset - eset; re_ = eset - kset
    kn = collections.Counter((u, n) for (u, n, d), c in rk.items() for _ in range(c)); en = collections.Counter((u, n) for (u, n, d), c in re_.items() for _ in range(c))
    namematch = sum((kn & en).values())
    print('=== %s: key %d lines, engine %d lines, exact %d, same name other dims %d, key-only %d, engine-only %d' % (
        section, sum(kset.values()), sum(eset.values()), exact, namematch, sum((kn - en).values()), sum((en - kn).values())))
    for (u, n), c in sorted((kn - en).items()):
        d = [k[2] for k in rk if k[0] == u and k[1] == n]
        print('   KEY ONLY   unit %-3d x%d %s %s' % (u, c, n, d[:2]))
    for (u, n), c in sorted((en - kn).items()):
        d = [k[2] for k in re_ if k[0] == u and k[1] == n]
        print('   ENGINE ONLY unit %-3d x%d %s %s' % (u, c, n, d[:2]))
    for (u, n) in sorted(set((kn & en).keys()))[:12]:
        print('   DIMS DIFFER unit %-3d %s key=%s engine=%s' % (u, n, [k[2] for k in rk if k[0] == u and k[1] == n][:2], [k[2] for k in re_ if k[0] == u and k[1] == n][:2]))
    if eng.flags:
        print('   flags:', '; '.join(eng.flags)[:600])
    tot_k += sum(kset.values()); tot_m += exact
print('TOTAL key lines %d, exact matches %d (%.1f%%)' % (tot_k, tot_m, 100.0 * tot_m / max(tot_k, 1)))
