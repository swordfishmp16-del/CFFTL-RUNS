#!/usr/bin/env python3
"""Study C: tabulate every wall (ten sets + local jobs), compare designer vs engineer, run the prototype rule.
usage: python3 fillers_study.py  > fillers_tabulate.txt"""
import os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'rules'))
import fillers
from fillers import IN, frac_inches, unit_type
import absorb, parse_walls

S = os.path.join(HERE, '..')
W10 = os.path.join(S, 'walls10.txt')
JOBS = os.path.join(S, 'jobs')
LOCAL_DESIGN = ['RENEE werner home office.job', 'Cathy Coyne.job', 'Bayle DCL - Daughters Room.job', 'Lynn Neddie.job']
LOCAL_ENG = ['1089471 WERNER OFFICE.job']


def f(raw):
    return frac_inches(raw) if raw is not None else '-'


def ustr(u):
    if not u:
        return '-'
    return '%s[%s t%s X %s W %s D %s]' % (u['name'][:26], u['kind'], unit_type(u) or '?', f(u['x_raw']), f(u['w_raw']), ('%g' % u['d_in']))


def end_str(st):
    if not st['closed']:
        c = 'OPEN'
    else:
        c = 'closed(%+.0f)' % st['turn']
        c += '/' + fillers.corner_class(st, 0)
    if not st['run']:
        return '%-13s no boxes' % c
    r = 'reach' if st['reach'] else ('short %s' % f(st['gap']) if st['gap'] > 0 else 'over %s' % f(-st['gap']))
    fl = ('filler W %s D %g at X %s' % (f(st['filler']['w_raw']), st['filler']['d_in'], f(st['filler']['x_raw']))) if st['filler'] else 'no filler'
    cab = ustr(st['cabinet'])
    extra = ''
    if st['cab_gap'] is not None and abs(st['cab_gap']) > fillers.END_TOL:
        extra += ' cab_gap %s%s' % ('+' if st['cab_gap'] > 0 else '-', f(abs(st['cab_gap'])))
    if st['shelf_over']:
        extra += ' SHELF-OVER:' + ','.join(u['name'][:20] for u in st['shelf_over'])
    if st['shelf_at']:
        extra += ' SHELF-AT:' + ','.join(u['name'][:20] for u in st['shelf_at'])
    if st.get('nb'):
        nb = st['nb']
        if nb['reach_box'] is not None:
            extra += ' NB-IN-CORNER:%s(D %s)' % (nb['reach_box']['name'][:16], f(st['bound']))
        elif nb['box'] is not None:
            extra += ' NB-BOX:%s@%s' % (nb['box']['name'][:16], f(nb['box_dist']))
        else:
            extra += ' NB-EMPTY'
        if nb['shelf'] is not None and nb['shelf_dist'] <= fillers.ZONE_MAX:
            extra += ' NB-SHELF:%s@%s' % (nb['shelf']['name'][:14], f(nb['shelf_dist']))
        if nb['opening_dist'] is not None and nb['opening_dist'] <= 6 * IN:
            extra += ' NB-OPENING@%s' % f(nb['opening_dist'])
    return '%-18s %-11s %-34s cab %s%s' % (c, r, fl, cab, extra)


def tabulate(m, tag):
    rows = fillers.wall_table(m)
    print('\n=== %s %s' % (tag, m.name))
    for row in rows:
        w = row['wall']
        print('  room %d %-18s wall %2d L %-9s ang %5.1f left %2d right %2d  boxes %d' % (
            w['room'], (w['room_name'] or '')[:18], w['id'], f(w['length_raw']), w['angle_deg_norm'], w['left_id'], w['right_id'], len(row['start']['tops'])))
        print('      START ' + end_str(row['start']))
        print('      END   ' + end_str(row['end']))
    return rows


def main():
    w10 = fillers.load_walls10(W10)
    local = {n: fillers.load_job(os.path.join(JOBS, n)) for n in LOCAL_DESIGN + LOCAL_ENG}

    print('#' * 100 + '\n# PART 1: TABULATION OF EVERY LIVE WALL\n' + '#' * 100)
    allrows = {}
    for n in sorted(w10):
        kind = 'DESIGN' if n <= 10 else 'ENG'
        allrows[('w10', n)] = tabulate(w10[n], '[%s job %d]' % (kind, n))
    for n, m in local.items():
        allrows[('local', n)] = tabulate(m, '[LOCAL %s]' % ('ENG' if n in LOCAL_ENG else 'DESIGN'))

    # ---- counts
    print('\n' + '#' * 100 + '\n# PART 2: COUNTS OVER ALL WALL ENDS\n' + '#' * 100)
    C = collections.Counter()
    turns = collections.Counter()
    for key, rows in allrows.items():
        src = 'design' if (key[0] == 'w10' and key[1] <= 10) or (key[0] == 'local' and key[1] in LOCAL_DESIGN) else 'eng'
        for row in rows:
            for S in ('start', 'end'):
                st = row[S]
                if st['closed']:
                    turns[(src, 'turn %+.0f' % st['turn'])] += 1
                if not st['run']:
                    C[(src, 'no boxes', st['closed'])] += 1; continue
                state = 'reach' if (st['reach'] or st.get('reach_bound')) else ('short' if st['gap'] > 0 else 'over')
                C[(src, state, 'closed' if st['closed'] else 'open', fillers.corner_class(st, 0), 'filler' if st['filler'] else 'no filler')] += 1
    for k in sorted(C, key=str):
        print('  %-70s %d' % (k, C[k]))
    print('  turn signs at closed ends:', dict(turns))

    # ---- designer vs engineer on the same rooms (ten sets)
    print('\n' + '#' * 100 + '\n# PART 3: DESIGNER vs ENGINEER, SAME ROOMS (walls matched by chain position, absorb.py)\n' + '#' * 100)
    pj = parse_walls.load(W10)
    stats = collections.Counter()
    for d, es in absorb.PAIRS.items():
        for e in es:
            d_room, e_room, pairs, extra = absorb.match_walls(pj, d, e)
            dm, em = w10[d], w10[e]
            drows = {r['wall']['id']: r for r in fillers.wall_table(dm)}
            erows = {r['wall']['id']: r for r in fillers.wall_table(em)}
            print('\n--- %s: design job %d room %d %r  ->  eng job %d room %d %r' % (absorb.NAMES[d], d, d_room, dm.rooms.get(d_room), e, e_room, em.rooms.get(e_room)))
            for dw, ews in pairs:
                dr = drows.get(dw['id'])
                if not ews:
                    print('  design wall %2d L %-9s -> (removed by the engineer)' % (dw['id'], f(dw['length'])))
                    continue
                for ew in ews:
                    er = erows.get(ew['id'])
                    print('  design wall %2d L %-9s -> eng wall %2d L %-9s' % (dw['id'], f(dw['length']), ew['id'], f(ew['length'])))
                    for S in ('start', 'end'):
                        ds, es_ = dr[S], er[S]
                        print('     %-5s D: %s' % (S, end_str(ds)))
                        print('           E: %s' % end_str(es_))
                        if ds['run'] and es_['run']:
                            dfl, efl = bool(ds['filler']), bool(es_['filler'])
                            verdict = {(False, True): 'ENGINEER ADDED', (True, False): 'ENGINEER REMOVED', (True, True): 'kept', (False, False): 'none either'}[(dfl, efl)]
                            if es_['closed'] and (ds['reach'] or es_['reach']):
                                stats[(verdict, 'closed')] += 1
                            else:
                                stats[(verdict, 'open/short')] += 1
                            more = ''
                            if ds['cabinet'] and es_['cabinet']:
                                more = ' | end cabinet %r %s -> %r %s' % (ds['cabinet']['name'][:22], f(ds['cabinet']['w_raw']), es_['cabinet']['name'][:22], f(es_['cabinet']['w_raw']))
                            print('           => %s (end %s in the eng file)%s' % (verdict, 'closed' if es_['closed'] else 'open', more))
            for ew in extra:
                er = erows.get(ew['id'])
                print('  (eng-only wall %2d L %s)' % (ew['id'], f(ew['length'])))
                for S in ('start', 'end'):
                    print('     %-5s E: %s' % (S, end_str(er[S])))
    print('\n  summary of filler verdicts (runs present on both sides):')
    for k in sorted(stats, key=str):
        print('   %-40s %d' % (k, stats[k]))

    # ---- WERNER local pair
    print('\n--- WERNER (local): designer wall 1 vs engineer wall 1')
    for n in ['RENEE werner home office.job', '1089471 WERNER OFFICE.job']:
        r = fillers.wall_table(local[n])[0]
        print('  %s wall %d L %s' % (n, r['wall']['id'], f(r['wall']['length_raw'])))
        for S in ('start', 'end'):
            print('     %-5s %s' % (S, end_str(r[S])))

    # ---- the prototype rule
    print('\n' + '#' * 100 + '\n# PART 4: missing_fillers() ON THE DESIGNER JOBS (and, for contrast, the engineered rooms)\n' + '#' * 100)
    for n in LOCAL_DESIGN:
        print(fillers.format_findings(fillers.missing_fillers(local[n]), '\n== LOCAL DESIGN %s' % n))
    for n in sorted(w10):
        if n <= 10:
            print(fillers.format_findings(fillers.missing_fillers(w10[n]), '\n== DESIGN job %d %s' % (n, w10[n].name)))
    print('\n---- for contrast: the engineered rooms')
    for n in LOCAL_ENG:
        print(fillers.format_findings(fillers.missing_fillers(local[n]), '\n== LOCAL ENG %s' % n))
    for n in sorted(w10):
        if n > 10:
            print(fillers.format_findings(fillers.missing_fillers(w10[n]), '\n== ENG job %d %s' % (n, w10[n].name)))


if __name__ == '__main__':
    main()
