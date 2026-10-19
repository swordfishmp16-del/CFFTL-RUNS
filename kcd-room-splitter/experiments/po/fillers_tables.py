#!/usr/bin/env python3
"""Markdown tables for C_fillers.md: every closed wall end that a run touches, designer files first, with the
engineer's state of the same end where an engineered room exists (ten sets) or the local WERNER pair."""
import os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'rules'))
import fillers, absorb, parse_walls
from fillers import frac_inches as fr, unit_type

S = os.path.join(HERE, '..')
W10 = os.path.join(S, 'walls10.txt'); JOBS = os.path.join(S, 'jobs')
LOCAL = {'COYNE': 'Cathy Coyne.job', 'DRUBEL': 'Bayle DCL - Daughters Room.job', 'NEDDIE': 'Lynn Neddie.job', 'WERNER': 'RENEE werner home office.job'}
w10 = fillers.load_walls10(W10)
pj = parse_walls.load(W10)
local = {k: fillers.load_job(os.path.join(JOBS, v)) for k, v in LOCAL.items()}
werner_eng = fillers.load_job(os.path.join(JOBS, '1089471 WERNER OFFICE.job'))

# map (design job, design wall id) -> (eng job, eng wall id) through absorb's chain matching
emap = {}
for d, es in absorb.PAIRS.items():
    for e in es:
        _, _, pairs, _ = absorb.match_walls(pj, d, e)
        for dw, ews in pairs:
            if ews:
                emap[(d, dw['id'])] = (e, ews[0]['id'])


def fstate(st):
    if not st['run']:
        return 'no units'
    if st['filler']:
        return 'filler %s' % fr(st['filler']['w_raw']) + ('' if abs(st['filler']['d_in'] * 254 - 190) < 20 or abs(st['filler']['w_raw'] - 190) < 20 else '')
    if st['reach'] or st['reach_bound']:
        return 'NO filler (touches)'
    return 'no filler, %s short' % fr(st['gap'] - st['bound'])


rows = []
def collect(tag, m, jobno=None):
    for row in fillers.wall_table(m):
        w = row['wall']
        for Sd in ('start', 'end'):
            st = row[Sd]
            if not st['run'] or not st['closed']:
                continue
            if not (st['reach'] or st['reach_bound']):
                continue
            cls = fillers.corner_class(st, 0)
            c = st['cabinet']
            eng = ''
            if jobno is not None and (jobno, w['id']) in emap:
                e, eid = emap[(jobno, w['id'])]
                er = {r['wall']['id']: r for r in fillers.wall_table(w10[e])}.get(eid)
                if er:
                    eng = fstate(er[Sd]) + ' (eng wall %d)' % eid
            elif tag == 'WERNER':
                er = fillers.wall_table(werner_eng)[0]
                eng = fstate(er[Sd]) + ' (eng wall 1)'
            rows.append((tag, w['room_name'][:16], w['id'], fr(w['length_raw']), Sd, st['neighbour'], cls, st['inside_angle'],
                         fstate(st), ('%s %s (D %g)' % (c['name'], fr(c['w_raw']), c['d_in'])) if c else '-', eng))

for n in range(1, 11):
    collect(absorb.NAMES[n], w10[n], n)
for k in ('COYNE', 'DRUBEL', 'NEDDIE', 'WERNER'):
    collect(k, local[k])

print('| job | room | wall | length | end | meets wall | corner class | angle | designer | end cabinet | engineer |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for r in rows:
    print('| %s | %s | %d | %s | %s | %d | %s | %.0f | %s | %s | %s |' % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10]))

print()
C = collections.Counter((r[6], r[8].startswith('filler')) for r in rows)
print('| corner class | designer has a filler | designer has none |')
print('|---|---|---|')
for cls in ('wall', 'zone', 'side', 'casing', 'angled'):
    print('| %s | %d | %d |' % (cls, C[(cls, True)], C[(cls, False)]))
print()
# engineer verdicts where an engineered room exists
V = collections.Counter()
for r in rows:
    if not r[10]:
        continue
    d_has = r[8].startswith('filler'); e_has = r[10].startswith('filler')
    V[(r[6], 'designer filler' if d_has else 'designer none', 'engineer filler' if e_has else 'engineer none')] += 1
print('| corner class | designer | engineer | ends |')
print('|---|---|---|---|')
for k in sorted(V):
    print('| %s | %s | %s | %d |' % (k[0], k[1], k[2], V[k]))
