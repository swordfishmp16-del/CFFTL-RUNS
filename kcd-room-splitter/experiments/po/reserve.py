#!/usr/bin/env python3
"""reserve.py - PROTOTYPE: make room for a 3/4 filler at the END of a wall whose run of units reaches the wall end,
using the owner's unit rules (kcdwalls.unit_step: the hanging sections share the 3/4 so they come out the same size,
everything else keeps its width and slides), then update the units' room points and 3-D cache like kcdwalls does.
The wall record itself is not changed. Writes OUT.job (same size as the input).

    python3 reserve.py JOB.job WALLID OUT.job [--width 0.75]

Shared with kcdfill.reserve_start (the mirror step at the START): load() reads the job for one wall, finish() does the
room points, the 3-D cache, the byte guard and the write. reserve_end() = load + unit_step(anchor='start') + finish.
"""
import os, struct, sys, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))   # the repo's kcd-room-splitter, wherever it is checked out
import kcdwalls as W
import kcdmesh


def fr(raw):
    """Inches as the owner writes them: 3/4, not 0 3/4."""
    s = W.frac_inches(raw)
    return s[2:] if s.startswith('0 ') and len(s) > 2 else s


def load(job_path, wid):
    """Read a job for a reserve step on wall `wid`: (data, original, names, units, by_id, uidx, p, rn).
    data = bytearray to edit, original = the bytes as read, names = room names, units = kcdwalls.units_by_wall,
    by_id = the wall records by id, uidx = the live unit records, p = the parsed wall, rn = its room name."""
    data = bytearray(open(job_path, 'rb').read()); original = bytes(data)
    names = W.room_names(original)
    units, uerr = W.units_by_wall(job_path)
    if uerr: raise SystemExit('units could not be read: %s' % uerr)
    recs = W.job_walls(data); by_id = {r.parsed['id']: r for r in recs}
    if wid not in by_id or not by_id[wid].parsed['is_live']:
        raise ValueError('wall %d is not a live wall of this job' % wid)
    uidx = W.unit_index(original)
    p = by_id[wid].parsed; rn = names.get(p['room'], '')
    return data, original, names, units, by_id, uidx, p, rn


def finish(data, original, p, ulist, uidx, touched, lines, checks, out_path):
    """Room points and 3-D cache of the touched units of wall p (the wall did not move), then the byte guard (only
    unit fields and the moved cache entries may differ from `original`) and the write of out_path."""
    mesh = kcdmesh.Mesh(original); ranges = []; moved = stretched = fv = 0
    for u in ulist:
        if u['id'] not in touched or u['id'] not in uidx: continue
        x_old, w_old, x_new, w_new = touched[u['id']]
        A, B = W.unit_points(original, uidx[u['id']])
        An, Bn = W.moved_unit_points(A, B, p, p, x_old, w_old, x_new, w_new)
        if (An, Bn) != (A, B): W.set_unit_points(data, uidx[u['id']], An, Bn)
        sl = kcdmesh.Mesh.unit_slice(original, uidx[u['id']]['f86_at'])
        if not mesh.check_slice(sl):
            checks.append('CHECK the %s (unit %d): its drawing could not be located in the file and was not moved; open its wall once in KCD so it redraws' % (u['name'], u['id'])); continue
        d, n = W.unit_vectors(p['angle_deg'])
        o_old = (p['P0'][0] + x_old * d[0], p['P0'][1] + x_old * d[1]); o_new = (p['P0'][0] + x_new * d[0], p['P0'][1] + x_new * d[1])
        v = (int(round(o_new[0] - o_old[0])), int(round(o_new[1] - o_old[1])))
        ext0 = mesh.extent(original, sl, o_old, d, n)
        if v != (0, 0): mesh.translate_unit(data, sl, v); moved += 1
        if w_new != w_old:
            H = struct.unpack_from('<i', original, uidx[u['id']]['start'] + 18)[0]; D = struct.unpack_from('<i', original, uidx[u['id']]['start'] + 24)[0]
            _, nf, amb = mesh.stretch_unit(data, sl, o_new, d, w_old, w_new, fixed=(H, D)); stretched += 1; fv += nf
            if amb: checks.append('CHECK the %s was made %s %s; open it once in KCD so it redraws (%d number%s in its drawing could not be told apart)'
                                 % (u['name'], fr(abs(w_new - w_old)), 'narrower' if w_new < w_old else 'wider', amb, '' if amb == 1 else 's'))
        ranges += mesh.ranges(sl)
        ext = mesh.extent(data, sl, o_new, d, n)
        if ext and ext0 and (abs(ext[0] - ext0[0]) > 1 or abs(ext[1] - (ext0[1] + (w_new - w_old))) > 1 or abs(ext[2] - ext0[2]) > 1 or abs(ext[3] - ext0[3]) > 1):
            checks.append('CHECK the %s (unit %d): its drawing did not move cleanly; open it once in KCD so it redraws' % (u['name'], u['id']))
    lines.append('drawing: %d unit shape(s) moved, %d stretched with %d face width values redone' % (moved, stretched, fv))
    # guard: only unit fields and the moved cache entries changed
    allowed = []
    for ui in uidx.values():
        allowed += [(ui['start'] + 6, ui['start'] + 10), (ui['start'] + 12, ui['start'] + 16), (ui['f86_at'] + 12, ui['f86_at'] + 16), (ui['f86_at'] + 40, ui['f86_at'] + 64)]
    allowed += ranges; allowed.sort()
    k = 0
    for i in range(len(data)):
        if data[i] == original[i]: continue
        while k < len(allowed) and allowed[k][1] <= i: k += 1
        if not (k < len(allowed) and allowed[k][0] <= i < allowed[k][1]): raise RuntimeError('byte %d outside the allowed fields changed' % i)
    open(out_path, 'wb').write(bytes(data))
    return ranges


def reserve_end(job_path, wid, out_path, width_in=0.75):
    data, original, names, units, by_id, uidx, p, rn = load(job_path, wid)
    fw = W.snap16(int(round(width_in * W.IN)))
    pseudo = dict(p); pseudo['length_raw'] = p['length_raw'] - fw
    lines, checks, touched = [], [], {}
    lines.append('wall %d (%s): %s long, unchanged; its units make room for a %s filler at the END' % (wid, rn, W.frac_inches(p['length_raw']), fr(fw)))
    W.unit_step(data, wid, rn, p, pseudo, units.get(wid, []), uidx, lines, checks, touched, anchor='start', spread=True)
    # room points and 3-D cache of the touched units (the wall did not move), guard, write
    finish(data, original, p, units.get(wid, []), uidx, touched, lines, checks, out_path)
    return lines, checks, touched

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('job'); ap.add_argument('wall', type=int); ap.add_argument('out'); ap.add_argument('--width', type=float, default=0.75)
    a = ap.parse_args()
    if W.same_file(a.out, a.job):
        raise SystemExit('Stopped: the output must not be the input job; give another name')
    try:
        lines, checks, touched = reserve_end(a.job, a.wall, a.out, a.width)
    except ValueError as e:
        raise SystemExit('Stopped: %s' % e)
    print('\n'.join(lines)); print('CHECKS (%d)' % len(checks)); print('\n'.join('   ' + c for c in checks)); print('touched', touched)
