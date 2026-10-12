"""Compare two KCD v23 jobs section by section (e.g. our split vs a KCD-made split)."""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kcdjob  # noqa: E402


def summary(d):
    S = kcdjob.parse(d)
    sec = {n: (a, b, i) for n, a, b, i in S}
    J = sec['header'][2]
    out = {}
    out['size'] = len(d)
    out['sections'] = {n: b - a for n, a, b, i in S}
    out['cust'] = J['cust']
    out['rtf'] = J['rtf']
    out['L'] = J['L']
    R = sec['rooms'][2]
    out['rooms'] = [r['name'] for r in R['list']]
    out['cur'] = R['cur']
    out['room_recs'] = [d[r['start']:r['end']] for r in R['list']]
    out['handle_sets'] = [d[a:b] for a, b in sec['handles'][2]['sets']]
    walls = sec['walls'][2]['list']
    out['walls'] = [(w['id'], w['room'], d[w['start']:w['end']]) for w in walls]
    units = sec['units'][2]['list']
    out['units'] = [(u['id'], u['wall'], u['cat'], u['name'], d[u['start']:u['end']]) for u in units]
    out['notes'] = [(n['room'], n['text'], d[n['start']:n['end']]) for n in sec['notes'][2]['list']]
    out['mesh'] = sec['mesh'][2]
    out['defaults'] = [d[a:b] for a, b in sec['defaults'][2]['sets']]
    T = sec['settings'][2]
    out['pairs'] = [struct.unpack_from('<hh', d, T['npair_at'] + 2 + 4 * i) for i in range(T['npair'])]
    out['shapes'] = [len(s['items']) for s in sec['roomshapes'][2]['slots']]
    return out


def compare(a, b):
    A, B = summary(a), summary(b)
    print('size', A['size'], B['size'])
    for k in sorted(set(A['sections']) | set(B['sections'])):
        print('  section %-11s %10s %10s' % (k, A['sections'].get(k), B['sections'].get(k)))
    for k in ('cust', 'rtf', 'L', 'rooms', 'cur', 'mesh', 'pairs', 'shapes'):
        print('%-8s A=%r\n         B=%r' % (k, A[k], B[k]))
    print('room record equal:', [x == y for x, y in zip(A['room_recs'], B['room_recs'])])
    print('handle sets A', len(A['handle_sets']), 'B', len(B['handle_sets']),
          'match matrix', [[x == y for y in B['handle_sets']] for x in A['handle_sets']])
    print('defaults A', len(A['defaults']), 'B', len(B['defaults']),
          'match', [[x == y for y in B['defaults']] for x in A['defaults']])
    print('walls A', [(i, r) for i, r, _ in A['walls']])
    print('walls B', [(i, r) for i, r, _ in B['walls']])
    for (ia, ra, wa), (ib, rb, wb) in zip(A['walls'], B['walls']):
        if wa != wb:
            diffs = [k for k in range(min(len(wa), len(wb))) if wa[k] != wb[k]]
            print('   wall', ia, 'differs at', diffs[:20], 'len', len(wa), len(wb))
    print('units A', len(A['units']), 'B', len(B['units']))
    bset = {}
    for u in B['units']:
        bset.setdefault((u[2], u[3]), []).append(u)
    for u in A['units'][:400]:
        cand = bset.get((u[2], u[3]), [])
        same = [c for c in cand if c[4] == u[4]]
        if not same:
            best = None
            for c in cand:
                if len(c[4]) == len(u[4]):
                    nd = sum(1 for k in range(len(c[4])) if c[4][k] != u[4][k])
                    if best is None or nd < best[0]:
                        best = (nd, c[0], [k for k in range(len(c[4])) if c[4][k] != u[4][k]][:12])
            print('   unit A#%d %s %s: no exact match in B; closest %s' % (u[0], u[2][:20], u[3], best))
    print('notes A', len(A['notes']), 'B', len(B['notes']))
    btxt = [n[2] for n in B['notes']]
    miss = [n for n in A['notes'] if n[2] not in btxt]
    print('   notes in A not byte-identical in B:', len(miss), [m[1][:20] for m in miss[:10]])


if __name__ == '__main__':
    compare(open(sys.argv[1], 'rb').read(), open(sys.argv[2], 'rb').read())
