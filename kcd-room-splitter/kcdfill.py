#!/usr/bin/env python3
"""kcdfill.py - the owner's filler rule inside the main run (Oct 20, 2026).

Owner, Oct 19: "WHEN UNITS GO BETWEEN 2 WALLS THERE NEEDS TO BE FILLERS ON BOTH SIDES". Fillers stay 3/4; the units
change; the hanging sections of the wall share the change so they come out the same size; drawer and catalog units keep
their width; the units add up to the wall length.

    apply_fillers(job_in, job_out, width_in=0.75) -> dict
        Runs experiments/po/fillers.missing_fillers on job_in. For every FIX finding (a run of cabinets touches a closed
        wall end, no filler there, nothing doubtful), in (wall, end) order: picks a 3/4 filler of the job to copy
        (source_fillers), makes 3/4 of room at that end (reserve.reserve_end for the END, reserve_start for the START),
        checks the room came out right, clones the filler there (addfiller.add_filler) and goes on with the result.
        Anything that goes wrong for one finding becomes a CHECK line and the run goes on with the next finding; a
        half-done file is never left behind. job_out is written once, at the end; when no filler was added it is job_in
        byte for byte. job_out=None: report only, nothing written.
        Returns {'lines': the owner's report lines, 'checks': CHECK lines, 'findings': the rule's findings as dicts,
                 'added': [{'unit_id', 'wall', 'end', 'x_raw', 'source_id'}], 'written': path or None, 'changed': bool}

    reserve_start(job, wall, out, width_in=0.75) -> (lines, checks, touched)
        The mirror of reserve.reserve_end: the wall does not move; its units make 3/4 of room at the START by the
        same-size rule (kcdwalls.unit_step with anchor='end' on a pseudo wall 3/4 shorter, as if the start had moved 3/4
        along the wall). unit_step then measures X from that pseudo start, so every X it left is put back into the real
        wall's frame (+3/4); the features of the room (obstructions, outlets, openings: kcdwalls.is_feature) stay exactly
        where they were; the result is checked (first box at 3/4, no X before the wall, fillers still 3/4, the far end
        of the run unchanged) before the room points and the 3-D cache are updated by reserve.finish, the same code
        reserve_end uses. A failed check raises FillError and writes nothing.

    source_fillers(job, wall) -> (candidates, others)
        The live fillers of the job that can be copied: type 230 and 3/4 wide within 1/16 (the designers' way: W = 3/4,
        D = the face). Nearest first: on the wall, then in its room, then anywhere; unit-id order within each group.
        `others` are the fillers that cannot serve (face-wide, the engineers' way, or not 3/4).

The three prototypes stay in experiments/po (fillers.py, reserve.py, addfiller.py; the chain reserve + addfiller is
proven by the NEDDIE TEST3 round trip through KCD) and are imported when needed. Everything written is a TEST file
until KCD has opened it.

    python3 kcdfill.py JOB [--out NEW.job]                         the filler step alone (= kcdwalls.py JOB --fillers --out NEW.job)
    python3 kcdfill.py JOB --reserve-start WALL --out NEW.job      the START room step alone, for tests
"""
import importlib
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kcdjob      # noqa: E402
import kcdwalls as W   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PO = os.path.join(HERE, 'experiments', 'po')
IN = W.IN
FILLER_TYPE = 230
FILLER_W = W.snap16(int(round(0.75 * IN)))      # 190 raw = 3/4" as KCD stores it
TOL = IN // 16                                  # 1/16"
NUM = {2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine'}
HEADER = 'Fillers (your rule: a run between two walls gets a 3/4 filler at each end):'


class FillError(Exception):
    """A filler step that must not go on; the message is plain English for the CHECK line."""


def _proto(name):
    """One of the experiments/po prototypes, imported late (fillers.py imports kcdwalls, which imports this module late)."""
    if PO not in sys.path:
        sys.path.insert(0, PO)
    return importlib.import_module(name)


def fr(raw):
    """Inches as the owner writes them: 3/4, not 0 3/4."""
    s = W.frac_inches(raw)
    return s[2:] if s.startswith('0 ') and len(s) > 2 else s


def _i32(b, o):
    return struct.unpack_from('<i', b, o)[0]


# --------------------------------------------------------------------------------------------- the source filler
def source_fillers(job_path, wall_id):
    data = open(job_path, 'rb').read()
    walls = {r.parsed['id']: r.parsed for r in W.job_walls(data)}
    units, err = W.units_by_wall(job_path)
    if err:
        raise FillError('the units could not be read (%s)' % err)
    room = walls[wall_id]['room'] if wall_id in walls else None
    cands, others = [], []
    for wid, lst in units.items():
        if not wid or wid not in walls or not walls[wid]['is_live']:
            continue
        for u in lst:
            if not W.is_filler(u):
                continue
            if u.get('type') == FILLER_TYPE and abs(u['w_raw'] - FILLER_W) <= TOL:
                rank = 0 if wid == wall_id else (1 if walls[wid]['room'] == room else 2)
                cands.append((rank, u['id'], u))
            else:
                others.append(u)
    cands.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in cands], others


# --------------------------------------------------------------------------------------------- room at the START
def reserve_start(job_path, wid, out_path, width_in=0.75):
    R = _proto('reserve')
    data, original, names, units, by_id, uidx, p, rn = R.load(job_path, wid)
    fw = W.snap16(int(round(width_in * IN)))
    L = p['length_raw']
    pseudo = dict(p); pseudo['length_raw'] = L - fw
    ulist = units.get(wid, [])
    before = {u['id']: (u['x_raw'], u['w_raw']) for u in ulist}
    lines, checks, touched = [], [], {}
    lines.append('wall %d (%s): %s long, unchanged; its units make room for a %s filler at the START' % (wid, rn, W.frac_inches(L), W.frac_inches(fw)))
    # the step works as if the wall START had moved 3/4 along the wall (anchor 'end' = the start moved)
    W.unit_step(data, wid, rn, p, pseudo, ulist, uidx, lines, checks, touched, anchor='end', spread=True)
    lines.append('   (X values above count from %s past the wall start, where the step put the pseudo start)' % fr(fw))
    # back into the real wall's frame: +3/4 on every unit, except the features of the room, which stay put
    real, stay = {}, []
    for u in ulist:
        uid = u['id']
        if uid not in uidx:
            continue
        x0, w0 = before[uid]
        x_now, w_now = W.unit_xw(data, uidx[uid])
        x_new = x0 if W.is_feature(u) else x_now + fw
        if x_new != x_now:
            W.set_unit_xw(data, uidx[uid], x=x_new)
        u['x_raw'], u['w_raw'] = x_new, w_now
        if W.is_feature(u):
            stay.append(u)
        if (x_new, w_now) != (x0, w0):
            real[uid] = (x0, w0, x_new, w_now)
    touched.clear(); touched.update(real)
    # the step's remarks about features on a moved start do not apply: the wall did not move
    checks[:] = [c for c in checks if 'from the moved start of the wall' not in c and 'left where it/they are' not in c]
    for u in ulist:
        if u['id'] in real:
            x0, w0, x1, w1 = real[u['id']]
            lines.append('   on the real wall: %r (unit %d) X %s -> %s, W %s -> %s' % (u['name'], u['id'], fr(x0), fr(x1), fr(w0), fr(w1)))
    if stay:
        lines.append('   stays where it is on the wall: %s' % ', '.join('%r X %s' % (u['name'], fr(u['x_raw'])) for u in stay))
    # checks before anything is written
    problems = []
    cabs = [u for u in ulist if u['id'] in uidx and W.is_cabinet(u) and not W.is_feature(u)]
    if not cabs:
        problems.append('no cabinets on the wall')
    else:
        first = min(u['x_raw'] for u in cabs)
        if abs(first - fw) > TOL:
            problems.append('the first unit now starts at %s, not %s' % (fr(first), fr(fw)))
        end0 = max(before[u['id']][0] + before[u['id']][1] for u in cabs)
        end1 = max(u['x_raw'] + u['w_raw'] for u in cabs)
        if abs(end1 - end0) > 2:
            problems.append('the far end of the run moved from %s to %s' % (fr(end0), fr(end1)))
    for u in ulist:
        if u['id'] not in uidx:
            continue
        x0, w0 = before[u['id']]
        if x0 >= -TOL and u['x_raw'] < -TOL:
            problems.append('%r would start before the wall (X %s)' % (u['name'], fr(u['x_raw'])))
        if W.is_filler(u) and u['w_raw'] != w0:
            problems.append('filler %r changed width (%s -> %s)' % (u['name'], fr(w0), fr(u['w_raw'])))
        if W.is_feature(u) and u['x_raw'] != x0:
            problems.append('%r moved (X %s -> %s)' % (u['name'], fr(x0), fr(u['x_raw'])))
    if problems:
        raise FillError('; '.join(problems))
    R.finish(data, original, p, ulist, uidx, touched, lines, checks, out_path)
    return lines, checks, touched


# --------------------------------------------------------------------------------------------- one FIX finding
def _verify_reserved(ul0, ul1, p, end, fw):
    """Plain-English problems with the room step (empty = fine): ul0 / ul1 = the wall's units before / after."""
    L = p['length_raw']
    b = {u['id']: u for u in ul0}; a = {u['id']: u for u in ul1}
    if set(b) != set(a):
        return ['the units on the wall are not the same set as before']
    probs = []
    cabs = [i for i, u in a.items() if W.is_cabinet(u) and not W.is_feature(u)]
    if not cabs:
        return ['no cabinets on the wall']
    if end == 'end':
        got = max(a[i]['x_raw'] + a[i]['w_raw'] for i in cabs)
        if abs(got - (L - fw)) > TOL:
            probs.append('the run now ends at %s, not %s' % (fr(got), fr(L - fw)))
        s0, s1 = min(b[i]['x_raw'] for i in cabs), min(a[i]['x_raw'] for i in cabs)
        if abs(s0 - s1) > 2:
            probs.append('the start of the run moved from %s to %s' % (fr(s0), fr(s1)))
    else:
        got = min(a[i]['x_raw'] for i in cabs)
        if abs(got - fw) > TOL:
            probs.append('the run now starts at %s, not %s' % (fr(got), fr(fw)))
        e0, e1 = max(b[i]['x_raw'] + b[i]['w_raw'] for i in cabs), max(a[i]['x_raw'] + a[i]['w_raw'] for i in cabs)
        if abs(e0 - e1) > 2:
            probs.append('the far end of the run moved from %s to %s' % (fr(e0), fr(e1)))
    for i, u in a.items():
        if W.is_filler(u) and u['w_raw'] != b[i]['w_raw']:
            probs.append('filler %r changed width' % u['name'])
        if W.is_feature(u) and u['x_raw'] != b[i]['x_raw']:
            probs.append('%r (a feature of the room) moved' % u['name'])
        if b[i]['x_raw'] >= -TOL and u['x_raw'] < -TOL:
            probs.append('%r now starts before the wall' % u['name'])
    return probs


def _owner_lines(ul0, ul1, touched, fw, L):
    """The room step in the owner's words, from what changed (touched = {id: (x_old, w_old, x_new, w_new)})."""
    by = {u['id']: u for u in ul0}
    out = []
    sized = sorted([(by[i], t) for i, t in touched.items() if i in by and t[3] != t[1]], key=lambda it: it[1][0])
    slid = sorted([(by[i], t) for i, t in touched.items() if i in by and t[3] == t[1] and t[2] != t[0]], key=lambda it: it[1][0])
    members = [(u, t) for u, t in sized if W.unit_kind(u)]
    kinds = {W.unit_kind(u) for u, t in members}
    if len(members) >= 2 and len(kinds) == 1:
        kind = kinds.pop()
        what = 'hanging sections' if kind == 'hang' else 'open talls'
        out.append('   the %s %s share the %s so they stay the same size: %s -> %s' % (
            NUM.get(len(members), str(len(members))), what, fr(fw),
            ', '.join(fr(t[1]) for u, t in members), ', '.join(fr(t[3]) for u, t in members)))
        rest = [(u, t) for u, t in sized if (u, t) not in members]
    else:
        rest = sized
    shelves_followed = []
    for u, t in rest:
        if u.get('type') in W.SHELF_TYPES or u.get('type') == 645:
            shelves_followed.append('%s -> %s' % (fr(t[1]), fr(t[3])))
        elif W.is_decor(u):
            out.append('   the show-only %s now runs %s to %s' % (u['name'], fr(t[2]), fr(t[2] + t[3])))
        else:
            out.append('   the %s takes the %s: %s -> %s wide%s' % (u['name'], fr(fw), fr(t[1]), fr(t[3]),
                       (', X %s -> %s' % (fr(t[0]), fr(t[2]))) if t[2] != t[0] else ''))
    if shelves_followed:
        out.append('   %d shelf/shelves inside follow the opening: %s' % (len(shelves_followed), ', '.join(shelves_followed)))
    inside = 0
    for u, t in slid:
        if W.is_filler(u):
            out.append('   the filler %s moves %s -> %s, still %s wide' % (u['name'], fr(t[0]), fr(t[2]), fr(t[1])))
        elif W.is_cabinet(u) and u.get('type') not in W.SHELF_TYPES and not W.is_decor(u):
            out.append('   the %s keeps its width and slides %s -> %s' % (u['name'], fr(t[0]), fr(t[2])))
        else:
            inside += 1
    if inside:
        out.append('   %d shelf/shelves or accessories drawn inside them moved with them' % inside)
    cabs = [u for u in ul1 if W.is_cabinet(u) and not W.is_feature(u)]
    if cabs:
        out.append('   the units now run from %s to %s on the %s wall' % (fr(min(u['x_raw'] for u in cabs)), fr(max(u['x_raw'] + u['w_raw'] for u in cabs)), fr(L)))
    return out


def _shelf_checks(ul0, ul1, touched):
    """Shelves drawn inside a cabinet that changed width and did not follow it (the reserve step does not re-fit
    interior shelves; the engineer sets them)."""
    out = []
    a = {u['id']: u for u in ul1}
    for cid, t in touched.items():
        c = a.get(cid)
        if c is None or t[3] == t[1] or c.get('type') in W.SHELF_TYPES or W.is_filler(c):
            continue
        x0, w0, x1, w1 = t
        for s in ul1:
            if s.get('type') not in W.SHELF_TYPES or s['id'] == cid:
                continue
            was_inside = s['id'] in touched and touched[s['id']][0] >= x0 - TOL and touched[s['id']][0] + touched[s['id']][1] <= x0 + w0 + TOL
            was_inside = was_inside or (s['id'] not in touched and s['x_raw'] >= x0 - TOL and s['x_raw'] + s['w_raw'] <= x0 + w0 + TOL)
            if not was_inside:
                continue
            if s['x_raw'] < x1 - TOL or s['x_raw'] + s['w_raw'] > x1 + w1 + TOL:
                out.append('the shelf %r (unit %d) inside %r is %s wide and sticks out of the %s opening now; set it to the opening in KCD'
                           % (s['name'], s['id'], c['name'], fr(s['w_raw']), fr(w1)))
    return out


def _fix_one(cur, f, t1, t2, width_in, R, A):
    """Reserve the room at (f.wall, f.end) in `cur` into t1, clone a filler there into t2. Returns the block for the
    report; raises FillError (or lets an unexpected error through) when nothing could be done."""
    wid, end = f.wall, f.end
    fw = W.snap16(int(round(width_in * IN)))
    cands, others = source_fillers(cur, wid)
    if not cands:
        why = 'no 3/4 filler in this job to copy'
        if others:
            why += " (the job's %d filler(s) are face-wide, the engineers' way, or not 3/4: %s)" % (
                len(others), ', '.join('%r %s wide' % (u['name'], fr(u['w_raw'])) for u in others[:4]))
        raise FillError(why + '; the engineer adds this one in KCD')
    units0, err = W.units_by_wall(cur)
    if err:
        raise FillError('the units could not be read (%s)' % err)
    ul0 = [dict(u) for u in units0.get(wid, [])]
    # 1. the room
    if end == 'end':
        rl, rc, touched = R.reserve_end(cur, wid, t1, width_in)
    else:
        rl, rc, touched = reserve_start(cur, wid, t1, width_in)
    d1 = open(t1, 'rb').read()
    p = {r.parsed['id']: r.parsed for r in W.job_walls(d1)}[wid]
    units1, err = W.units_by_wall(t1)
    if err:
        raise FillError('the units could not be read back after the room step (%s)' % err)
    ul1 = units1.get(wid, [])
    problems = _verify_reserved(ul0, ul1, p, end, fw)
    if problems:
        raise FillError('the room for the filler did not come out right (%s)' % '; '.join(problems))
    # 2. the filler, from the nearest usable source
    last = None
    for src in cands:
        try:
            al, ac, _ = A.add_filler(t1, src['id'], wid, end, t2)
            break
        except SystemExit as e:
            if str(e).startswith('REFUSED'):
                last = str(e); continue
            raise FillError(str(e))
    else:
        raise FillError("none of the job's %d fillers could be copied (%s)" % (len(cands), last))
    d2 = open(t2, 'rb').read()
    ulist = [i for n, a, b, i in kcdjob.parse(d2) if n == 'units'][0]['list']
    nu = ulist[-1]
    X, Wd, H, FW = _i32(d2, nu['start'] + 6), _i32(d2, nu['start'] + 12), _i32(d2, nu['start'] + 18), _i32(d2, nu['start'] + 84)
    if nu['wall'] != wid or len(ulist) != len([i for n, a, b, i in kcdjob.parse(d1) if n == 'units'][0]['list']) + 1:
        raise FillError('the new file does not read back with one more unit on wall %d' % wid)
    head = 'wall %d (%s): the units reach the %s of the wall with no filler there, so they make %s of room at the %s' % (wid, f.room, end, fr(fw), end)
    lines = [head] + _owner_lines(ul0, ul1, touched, fw, p['length_raw'])
    lines.append('   new filler: unit %d, a copy of unit %d, X %s, %s wide, %s high, %s from the wall' % (nu['id'], src['id'], fr(X), fr(Wd), fr(H), fr(FW)))
    tag = 'CHECK fillers, wall %d (%s) %s: ' % (wid, f.room, end)
    checks = []
    for c in rc + ac:
        c = c[6:].strip() if c.startswith('CHECK ') else c
        if 'ambiguous drawing value' in c:
            c += ' (numbers in its drawing that could be its width or a fixed size; open the unit once in KCD so it redraws)'
        checks.append(tag + c)
    checks += [tag + c for c in _shelf_checks(ul0, ul1, touched)]
    return {'lines': lines, 'checks': checks, 'added': {'unit_id': nu['id'], 'wall': wid, 'end': end, 'x_raw': X, 'source_id': src['id']}}


# --------------------------------------------------------------------------------------------- the step
def _finding_lines(F, findings, title):
    out = ['', title]
    out += F.format_findings(findings).splitlines()
    return out


def apply_fillers(job_in, job_out=None, width_in=0.75):
    if job_out is not None and os.path.abspath(job_out) == os.path.abspath(job_in):
        raise ValueError('refusing to overwrite the input job; give another output name')
    F = _proto('fillers'); R = _proto('reserve'); A = _proto('addfiller')
    lines, checks, added, temps = [HEADER], [], [], []
    rep = {'lines': lines, 'checks': checks, 'findings': [], 'added': added, 'written': None, 'changed': False}
    try:
        findings = F.missing_fillers(job_in)
    except (Exception, SystemExit) as e:
        checks.append('CHECK fillers: the rule could not be checked on this job (%s); no filler was added' % e)
        lines.append('   the rule could not be checked on this job (see the CHECK list)')
        findings = []
    rep['findings'] = [dict(f._asdict()) for f in findings]
    fixes = sorted([f for f in findings if f.hold == ''], key=lambda f: (f.wall, f.end))
    holds = [f for f in findings if f.hold == 'hold']
    notes = [f for f in findings if f.hold == 'info']
    cur = job_in
    try:
        if job_out is None:
            for f in fixes:
                lines.append('   FIX wall %d (%s) %s: %s; a %s filler would be added here (no output file was given, so nothing was done)'
                             % (f.wall, f.room, f.end, f.why, fr(FILLER_W)))
        else:
            folder = os.path.dirname(os.path.abspath(job_out))
            stem = os.path.splitext(os.path.basename(job_out))[0]
            os.makedirs(folder, exist_ok=True)
            for k, f in enumerate(fixes, 1):
                t1 = os.path.join(folder, '~%s.fillers%d.job' % (stem, 2 * k - 1))
                t2 = os.path.join(folder, '~%s.fillers%d.job' % (stem, 2 * k))
                temps += [t1, t2]
                try:
                    blk = _fix_one(cur, f, t1, t2, width_in, R, A)
                except (Exception, SystemExit) as e:
                    msg = str(e) or type(e).__name__
                    lines.append('wall %d (%s): the units reach the %s of the wall with no filler there, but no filler was added: %s' % (f.wall, f.room, f.end, msg))
                    checks.append('CHECK fillers, wall %d (%s) %s: no filler was added; %s' % (f.wall, f.room, f.end, msg))
                    continue
                lines += blk['lines']; checks += blk['checks']; added.append(blk['added'])
                cur = t2
            if added:
                try:
                    still = [g for g in F.missing_fillers(cur) if g.hold == '']
                except (Exception, SystemExit) as e:
                    still = []
                    checks.append('CHECK fillers: the rule could not be re-checked on the new file (%s)' % e)
                for g in still:
                    checks.append('CHECK fillers, wall %d (%s) %s: after adding %d filler(s) the rule still finds this end without a filler: %s' % (g.wall, g.room, g.end, len(added), g.why))
        if not fixes and not holds:
            lines.append('   no run of units is missing an end filler by the rule')
        if holds:
            lines += _finding_lines(F, holds, 'For the engineer to decide (the rule found these but did not act):')
            for f in holds:
                reason = f.detail.split('HOLD: ', 1)[1] if 'HOLD: ' in (f.detail or '') else (f.detail or '')
                checks.append('CHECK fillers, wall %d (%s) %s: %s; %s; the engineer decides' % (f.wall, f.room, f.end, f.why, reason))
        if notes:
            lines += _finding_lines(F, notes, 'Notes on the fillers that are there:')
        if job_out is not None:
            if cur != job_in:
                final = open(cur, 'rb').read()
                os.replace(cur, job_out)
                temps.remove(cur)
            else:
                final = open(job_in, 'rb').read()
                shutil.copyfile(job_in, job_out)
            back = open(job_out, 'rb').read()
            if back != final:
                raise RuntimeError('internal error: the written file does not read back')
            rep['written'] = job_out
            rep['changed'] = bool(added)
            if added:
                lines.append('%d filler(s) added; this is a TEST file until KCD has opened it' % len(added))
            else:
                lines.append('no filler added; the file is the input, byte for byte')
    finally:
        for t in temps:
            try:
                if os.path.exists(t):
                    os.remove(t)
            except OSError:
                pass
    return rep


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="The owner's filler rule: a run between two walls gets a 3/4 filler at each end.")
    ap.add_argument('job')
    ap.add_argument('--out', help='new .job (never the input); without it the step only reports')
    ap.add_argument('--reserve-start', type=int, metavar='WALL', help='test: only make 3/4 of room at the START of this wall')
    a = ap.parse_args(argv)
    if a.reserve_start:
        if not a.out:
            ap.error('--reserve-start needs --out')
        if os.path.abspath(a.out) == os.path.abspath(a.job):
            ap.error('refusing to overwrite the input')
        lines, checks, touched = reserve_start(a.job, a.reserve_start, a.out)
        print('\n'.join(lines)); print('CHECKS (%d)' % len(checks)); print('\n'.join('   ' + c for c in checks)); print('touched', touched)
        return 0
    rep = apply_fillers(a.job, a.out)
    print('\n'.join(rep['lines']))
    if rep['checks']:
        print(); print('TO CHECK (%d):' % len(rep['checks'])); print('\n'.join('  ' + c for c in rep['checks']))
    print(); print('Written: %s' % (rep['written'] or 'nothing'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
