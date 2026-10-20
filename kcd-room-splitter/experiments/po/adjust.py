#!/usr/bin/env python3
"""adjust.py - PROTOTYPE: set the X and/or W of named units (fixed-size features such as door openings measured on the
remeasure sheet), then update their room points and 3-D cache the way kcdwalls does. The wall records do not change.
    python3 adjust.py JOB.job OUT.job UNIT=X[,W] ...      sizes in inches ("68 11/16"), W optional
"""
import sys, struct, argparse
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))   # the repo's kcd-room-splitter, wherever it is checked out
import kcdwalls as W
import kcdmesh

def adjust_units(job_path, targets, out_path):
    """targets: {unit id: (x_raw or None, w_raw or None)}; returns (lines, checks)."""
    data = bytearray(open(job_path, 'rb').read()); original = bytes(data)
    units, uerr = W.units_by_wall(job_path)
    if uerr: raise SystemExit('units could not be read: %s' % uerr)
    recs = W.job_walls(data); by_id = {r.parsed['id']: r for r in recs}
    names = W.room_names(original); uidx = W.unit_index(original)
    where = {u['id']: (wid, u) for wid, lst in units.items() for u in lst}
    lines, checks, ranges = [], [], []
    mesh = kcdmesh.Mesh(original)
    for uid, (xn, wn) in targets.items():
        if uid not in where or uid not in uidx:
            checks.append('CHECK unit %d not found on a live wall; nothing changed' % uid); continue
        wid, u = where[uid]; p = by_id[wid].parsed
        x_old, w_old = u['x_raw'], u['w_raw']
        x_new = x_old if xn is None else W.snap16(xn); w_new = w_old if wn is None else W.snap16(wn)
        if (x_new, w_new) == (x_old, w_old):
            lines.append('   unit %d %r on wall %d: already X %s W %s' % (uid, u['name'], wid, W.frac_inches(x_old), W.frac_inches(w_old))); continue
        W.set_unit_xw(data, uidx[uid], x=x_new, w=w_new)
        A, B = W.unit_points(original, uidx[uid]); An, Bn = W.moved_unit_points(A, B, p, p, x_old, w_old, x_new, w_new)
        if (An, Bn) != (A, B): W.set_unit_points(data, uidx[uid], An, Bn)
        sl = kcdmesh.Mesh.unit_slice(original, uidx[uid]['f86_at'])
        drawn = ''
        if mesh.check_slice(sl) and sl[0]:
            d, n = W.unit_vectors(p['angle_deg'])
            o_old = (p['P0'][0] + x_old * d[0], p['P0'][1] + x_old * d[1]); o_new = (p['P0'][0] + x_new * d[0], p['P0'][1] + x_new * d[1])
            v = (int(round(o_new[0] - o_old[0])), int(round(o_new[1] - o_old[1])))
            if v != (0, 0): mesh.translate_unit(data, sl, v)
            if w_new != w_old:
                H = struct.unpack_from('<i', original, uidx[uid]['start'] + 18)[0]; D = struct.unpack_from('<i', original, uidx[uid]['start'] + 24)[0]
                _, nf, amb = mesh.stretch_unit(data, sl, o_new, d, w_old, w_new, fixed=(H, D)); drawn = ', drawing stretched (%d face values)' % nf
                if amb: checks.append('CHECK unit %d: %d ambiguous drawing value(s) left alone' % (uid, amb))
            else:
                drawn = ', drawing moved'
            ranges += mesh.ranges(sl)
        lines.append('   unit %d %r on wall %d (%s): X %s -> %s, W %s -> %s%s' % (uid, u['name'], wid, names.get(p['room'], ''), W.frac_inches(x_old), W.frac_inches(x_new), W.frac_inches(w_old), W.frac_inches(w_new), drawn))
    allowed = []
    for ui in uidx.values():
        allowed += [(ui['start'] + 6, ui['start'] + 10), (ui['start'] + 12, ui['start'] + 16), (ui['f86_at'] + 12, ui['f86_at'] + 16), (ui['f86_at'] + 40, ui['f86_at'] + 64)]
    allowed += ranges; allowed.sort(); k = 0
    for i in range(len(data)):
        if data[i] == original[i]: continue
        while k < len(allowed) and allowed[k][1] <= i: k += 1
        if not (k < len(allowed) and allowed[k][0] <= i < allowed[k][1]): raise RuntimeError('byte %d outside the allowed fields changed' % i)
    open(out_path, 'wb').write(bytes(data))
    return lines, checks

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('job'); ap.add_argument('out'); ap.add_argument('targets', nargs='+')
    a = ap.parse_args()
    T = {}
    for t in a.targets:
        uid, rest = t.split('=', 1); parts = rest.split(',')
        T[int(uid)] = (int(round(W.parse_inches(parts[0]) * W.IN)) if parts[0] else None, int(round(W.parse_inches(parts[1]) * W.IN)) if len(parts) > 1 and parts[1] else None)
    lines, checks = adjust_units(a.job, a.out, T) if False else adjust_units(a.job, T, a.out)
    print('\n'.join(lines)); print('CHECKS (%d)' % len(checks)); print('\n'.join('   ' + c for c in checks))
