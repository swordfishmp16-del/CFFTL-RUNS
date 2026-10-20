#!/usr/bin/env python3
"""kcdfill.py - the owner's filler rule inside the main run (Oct 20, 2026).

Owner, Oct 19: "WHEN UNITS GO BETWEEN 2 WALLS THERE NEEDS TO BE FILLERS ON BOTH SIDES". Fillers stay 3/4; the units
change; the hanging sections of the wall share the change so they come out the same size; drawer and catalog units keep
their width; the units add up to the wall length.

    apply_fillers(job_in, job_out, width_in=0.75, after_walls=False) -> dict
        Runs experiments/po/fillers.missing_fillers on job_in. For every FIX finding (a run of cabinets touches a closed
        wall end, no filler there, nothing doubtful), in (wall, end) order: picks a 3/4 filler of the job to copy
        (source_fillers), makes 3/4 of room at that end (reserve.reserve_end for the END, reserve_start for the START),
        checks the room came out right, clones the filler there (addfiller.add_filler) and goes on with the result.
        Anything that goes wrong for one finding becomes a CHECK line and the run goes on with the next finding; a
        half-done file is never left behind. job_out is written once, at the end; when no filler was added it is job_in
        byte for byte. job_out=None: report only, nothing written. after_walls=True says the input is the file the wall
        step just wrote (the report's wording for 'nothing added' changes).
        Returns {'lines': the owner's report lines, 'checks': CHECK lines, 'findings': the rule's findings as dicts,
                 'added': [{'unit_id', 'wall', 'end', 'x_raw', 'source_id'}], 'written': path or None, 'changed': bool}
        Every sentence is for the owner: the corner classes, hold reasons and filler notes of the rule are worded here
        (fillers.py keeps its study wording for its own CLI).

    reserve_start(job, wall, out, width_in=0.75) -> (lines, checks, touched)
        The mirror of reserve.reserve_end: the wall does not move; its units make 3/4 of room at the START by the
        same-size rule (kcdwalls.unit_step with anchor='end' on a pseudo wall 3/4 shorter, as if the start had moved 3/4
        along the wall). unit_step measures X from that pseudo start, so it is told to word its sentences 3/4 further
        along (x_offset) and every X it left is put back into the real wall's frame (+3/4); the features of the room
        (obstructions, outlets, openings: kcdwalls.is_feature) stay exactly where they were; the result is checked (first
        box at 3/4, no X before the wall, fillers still 3/4, the far end of the run unchanged) before the room points and
        the 3-D cache are updated by reserve.finish, the same code reserve_end uses. A failed check raises FillError and
        writes nothing.

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
import re
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


_ZERO_FRAC = re.compile(r'(?<![\d/])0 (\d+/\d+)')


def _plain(text):
    """A sentence from kcdwalls/reserve in the owner's style: '0 3/4' -> '3/4' (10 3/4 stays)."""
    return _ZERO_FRAC.sub(r'\1', text)


def _err(e):
    """What went wrong, for a CHECK line: a FillError is already a plain sentence; anything else is named with its
    kind ('KeyError: 6'), never a bare number."""
    if isinstance(e, FillError) and str(e).strip():
        return str(e).strip()
    return W.err_text(e)


def _n(n, one, many):
    return '%d %s' % (n, one if n == 1 else many)


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
    lines.append('wall %d (%s): %s long, unchanged; its units make room for a %s filler at the START' % (wid, rn, W.frac_inches(L), fr(fw)))
    # the step works as if the wall START had moved 3/4 along the wall (anchor 'end' = the start moved); it measures
    # every new X from that pseudo start, so it is told to write its sentences 3/4 further along (x_offset), in the
    # real wall's frame
    W.unit_step(data, wid, rn, p, pseudo, ulist, uidx, lines, checks, touched, anchor='end', spread=True, x_offset=fw)
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
    lines[:] = [_plain(x) for x in lines]
    checks[:] = [_plain(x) for x in checks]
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
            probs.append('the filler %s changed width' % u['name'])
        if W.is_feature(u) and u['x_raw'] != b[i]['x_raw']:
            probs.append('the %s (a feature of the room) moved' % u['name'])
        if b[i]['x_raw'] >= -TOL and u['x_raw'] < -TOL:
            probs.append('the %s now starts before the wall' % u['name'])
    return probs


def _owner_lines(ul0, ul1, touched, fw, L):
    """The room step in the owner's words, from what changed (touched = {id: (x_old, w_old, x_new, w_new)})."""
    by = {u['id']: u for u in ul0}
    out = []
    sized = sorted([(by[i], t) for i, t in touched.items() if i in by and t[3] != t[1]], key=lambda it: it[1][0])
    slid = sorted([(by[i], t) for i, t in touched.items() if i in by and t[3] == t[1] and abs(t[2] - t[0]) >= TOL], key=lambda it: it[1][0])
    members = [(u, t) for u, t in sized if W.unit_kind(u)]
    kinds = {W.unit_kind(u) for u, t in members}
    if len(members) >= 2 and len(kinds) == 1:
        kind = kinds.pop()
        what = 'hanging sections' if kind == 'hang' else 'open talls'
        interior = lambda u, w: fr(w - u.get('ls_raw', 0) - u.get('rs_raw', 0))
        out.append('   the %s %s share the %s so they come out the same size (as near as sixteenths allow): widths %s -> %s (interiors %s -> %s)' % (
            NUM.get(len(members), str(len(members))), what, fr(fw),
            ', '.join(fr(t[1]) for u, t in members), ', '.join(fr(t[3]) for u, t in members),
            ', '.join(interior(u, t[1]) for u, t in members), ', '.join(interior(u, t[3]) for u, t in members)))
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
        out.append('   %s inside follow%s the opening: %s' % (_n(len(shelves_followed), 'shelf', 'shelves'), 's' if len(shelves_followed) == 1 else '', ', '.join(shelves_followed)))
    inside = 0
    for u, t in slid:
        if W.is_filler(u):
            out.append('   the filler %s moves %s -> %s, still %s wide' % (u['name'], fr(t[0]), fr(t[2]), fr(t[1])))
        elif W.is_cabinet(u) and u.get('type') not in W.SHELF_TYPES and not W.is_decor(u):
            out.append('   the %s keeps its width and slides %s -> %s' % (u['name'], fr(t[0]), fr(t[2])))
        else:
            inside += 1
    if inside:
        out.append('   %s drawn inside them moved with them' % _n(inside, 'shelf or accessory', 'shelves or accessories'))
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
                out.append('the shelf %s (unit %d) inside the %s is %s wide and sticks out of its %s opening now; set it to the opening in KCD'
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
            why += " (the job's %s %s face-wide, the engineers' way, or not 3/4: %s)" % (
                _n(len(others), 'filler', 'fillers'), 'is' if len(others) == 1 else 'are', ', '.join('%s %s wide' % (u['name'], fr(u['w_raw'])) for u in others[:4]))
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
        raise FillError("none of the job's %s could be copied (%s)" % (_n(len(cands), 'filler', 'fillers'), last))
    d2 = open(t2, 'rb').read()
    ulist = [i for n, a, b, i in kcdjob.parse(d2) if n == 'units'][0]['list']
    nu = ulist[-1]
    X, Wd, H, FW = _i32(d2, nu['start'] + 6), _i32(d2, nu['start'] + 12), _i32(d2, nu['start'] + 18), _i32(d2, nu['start'] + 84)
    if nu['wall'] != wid or len(ulist) != len([i for n, a, b, i in kcdjob.parse(d1) if n == 'units'][0]['list']) + 1:
        raise FillError('the new file does not read back with one more unit on wall %d' % wid)
    head = 'wall %d (%s): the units reach the %s of the wall with no filler there, so they make %s of room at the %s' % (wid, f.room, end, fr(fw), end)
    lines = [head] + _owner_lines(ul0, ul1, touched, fw, p['length_raw'])
    where = 'starting at the wall start' if abs(X) <= TOL else 'starting %s in from the wall start' % fr(X)
    lines.append('   new filler: unit %d (a copy of unit %d), %s wide, %s high, %s, set %s in from the wall face' % (nu['id'], src['id'], fr(Wd), fr(H), where, fr(FW)))
    tag = 'CHECK %s wall %d, %s: ' % (f.room, wid, end)
    checks = []
    for c in rc + ac:
        c = c[6:].strip() if c.startswith('CHECK ') else c
        checks.append(tag + _plain(c))
    checks += [tag + c for c in _shelf_checks(ul0, ul1, touched)]
    return {'lines': lines, 'checks': checks, 'added': {'unit_id': nu['id'], 'wall': wid, 'end': end, 'x_raw': X, 'source_id': src['id']}}


# --------------------------------------------------------------------------------------------- the owner's words
def _why(f):
    """The rule's reason without its class tag: 'between two walls, no filler at the end [zone]' -> 'between two walls, no filler at the end'."""
    return re.sub(r'\s*\[\w+\]\s*$', '', f.why or '')


def _nb_sentence(F, st):
    """'around the corner on wall 11 the Tall 2 Opening starts 23 in, under a Top Connecting Shelf' (or '' when the
    neighbour wall holds nothing near the corner)."""
    nb = st['nb']
    if not nb:
        return ''
    bits = []
    if nb['box'] is not None:
        bits.append('around the corner on wall %d the %s starts %s in' % (st['neighbour'], nb['box']['name'], fr(nb['box_dist'])))
        if nb['shelf'] is not None and nb['shelf_dist'] <= F.ZONE_MAX:
            bits[-1] += ', under a %s' % nb['shelf']['name']
    elif nb['shelf'] is not None and nb['shelf_dist'] <= F.ZONE_MAX:
        bits.append('around the corner on wall %d a %s runs %s from the corner' % (st['neighbour'], nb['shelf']['name'], fr(nb['shelf_dist'])))
    return '; '.join(bits)


def _owner_hold(F, f, row):
    """One hold finding (the rule found the end but did not act) in the owner's words: what stands there, why the tool
    did nothing, who decides and what to do in KCD if a filler is wanted."""
    S = f.end; st = row[S]; w = row['wall']
    cls = F.corner_class(st, 0)
    c = st['cabinet']
    code, info = F.hold_code(st, w, S)
    shelf_here = st['shelf_over'] or st['shelf_at']
    at = 'end' if S == 'end' else 'start'
    opening = {'zone': 'no filler where the run turns the corner.',
               'angled': 'no filler where the run meets the angled corner.',
               'side': 'no filler where the run meets the unit around the corner.',
               'casing': 'no filler where the run meets the door casing.'}.get(cls, 'no filler where the run meets the wall %s.' % at)
    S1 = [opening]
    if c is not None:
        s = ('The last %s (%s wide) ends at the wall end' if S == 'end' else 'The first %s (%s wide) starts at the wall start') % (c['name'], fr(c['w_raw']))
        if st['gap'] < -F.END_TOL:
            s += ' (drawn %s past it)' % fr(-st['gap'])
        nbs = _nb_sentence(F, st) if cls == 'zone' else ''
        S1.append(s + ('; ' + nbs if nbs else '') + '.')
    elif cls == 'zone':
        nbs = _nb_sentence(F, st)
        if nbs:
            S1.append(nbs[0].upper() + nbs[1:] + '.')
    # why the tool did nothing, and who decides
    decide = []
    if cls == 'zone':
        decide.append('Engineers usually leave such a corner without a filler. Mike decides: filler here or not.')
    elif cls == 'angled':
        decide.append("The corner is %.0f degrees, not 90: a filler here is the engineer's call." % st['inside_angle'])
    elif cls == 'side':
        decide.append('The run %s against the side of the %s on wall %d, not against the wall; the engineer decides.'
                      % ('ends' if S == 'end' else 'starts', st['nb']['reach_box']['name'], st['neighbour']))
    elif cls == 'casing':
        decide.append('A door or window opening on wall %d starts at this corner; the engineer decides.' % st['neighbour'])
    if code == 'none':
        decide.append('Only fillers or panels stand on this wall; the engineer decides.')
    elif code == 'panel':
        decide.append("The unit at the wall %s is a %s, the designer's choice; the engineer decides." % (at, info['what']))
    elif code == 'drawer':
        decide.append('The unit at the wall %s is a drawer unit, which keeps its width; the engineer decides where the 3/4 comes from.' % at)
    elif code == 'catalog':
        decide.append('The unit at the wall %s is a catalog product (%s), which keeps its width; the engineer decides where the 3/4 comes from.' % (at, c['name']))
    elif code == 'under12':
        decide.append('Taking 3/4 off the %s would leave it under 12 inches; the engineer decides where the 3/4 comes from.' % c['name'])
    elif code == 'not_reaching':
        decide.append('The %s stops %s short of the wall %s; the engineer decides.' % (c['name'], fr(info['gap']), at))
    elif code == 'inside':
        decide.append('The %s has other units drawn inside it (%s) that would have to change with it; the engineer decides.'
                      % (c['name'], ', '.join(u['name'] for u in info['units'])))
    elif code == 'stack':
        decide.append('A stack of units stands against this wall %s (%s): all of them would have to give up 3/4; the engineer decides.'
                      % (at, ', '.join('%s %s wide' % (u['name'], fr(u['w_raw'])) for u in info['units'])))
    if shelf_here and cls in ('wall', 'zone') and code == '':
        decide.append('A connecting shelf (%s) crosses this wall %s: the corner belongs to the run around the corner; the engineer decides.'
                      % (', '.join(u['name'] for u in shelf_here), at))
    if not decide:
        decide.append('The engineer decides.')
    if code == '' and c is not None and cls in ('zone', 'angled', 'side', 'casing'):
        decide.append('If yes: add a 3/4 filler at the %s of wall %d in KCD and take 3/4 off that %s.' % (at, f.wall, c['name']))
    return ' '.join(S1 + decide)


def _owner_note(F, f, row):
    """One information finding (a filler that is there, a run short of the wall, an open end) in the owner's words."""
    S = f.end; st = row[S]; w = row['wall']
    cls = F.corner_class(st, 0)
    why = f.why or ''
    if why.startswith('filler present'):
        fl = st['filler']
        fwid, fdep = fl['w_raw'], int(round(fl['d_in'] * IN))
        s = ('a 3/4 filler (%s) is there' if abs(fwid - F.FILLER_W) <= F.END_TOL else 'a filler (%s) is there') % fl['name']
        notes = []
        if abs(fwid - F.FILLER_W) > F.END_TOL and abs(fdep - F.FILLER_W) <= F.END_TOL:
            notes.append("drawn the engineers' way: its %s face given as the width, 3/4 deep" % fr(fwid))
        elif abs(fwid - F.FILLER_W) <= F.END_TOL and fdep > F.FILLER_W + F.END_TOL:
            notes.append("drawn the designers' way: 3/4 wide, its %s face given as the depth" % fr(fdep))
        elif abs(fwid - F.FILLER_W) > F.END_TOL:
            notes.append('but it is %s wide, not 3/4' % fr(fwid))
        if st['gap'] - st['bound'] > F.END_TOL:
            notes.append('it stands %s from the %s' % (fr(st['gap'] - st['bound']), 'wall %s' % S if not st['bound'] else 'corner cabinet'))
        if st['cab_gap'] is not None and abs(st['cab_gap']) > F.END_TOL and st['cabinet'] is not None:
            notes.append('%s of %s between it and the %s' % ('a gap' if st['cab_gap'] > 0 else 'an overlap', fr(abs(st['cab_gap'])), st['cabinet']['name']))
        if cls == 'side' and st['nb'] and st['nb']['reach_box'] is not None:
            notes.append('it is against the side of the %s (wall %d), not the wall' % (st['nb']['reach_box']['name'], st['neighbour']))
        return s + (', ' + '; '.join(notes) if notes else '')
    if why.startswith('open end'):
        fl = st['filler']
        return ('no wall is drawn at this %s, yet a %s filler (%s) stands there; a wall drawn alone may still be between two real walls'
                % (S, fr(fl['w_raw']), fl['name'])) if fl else 'no wall is drawn at this %s' % S
    if why.startswith('reentrant'):
        return 'the wall turns away here (an outside corner): the run end is exposed, a finished end rather than a filler'
    if why.startswith('short of the wall'):
        s = 'the run stops %s short of the wall %s (last unit %s)' % (fr(st['gap'] - st['bound']), S, st['outer']['name'])
        if cls == 'angled':
            s += '; the corner is %.0f degrees' % st['inside_angle']
        elif cls == 'zone':
            nbs = _nb_sentence(F, st)
            if nbs:
                s += '; ' + nbs
        elif cls == 'side' and st['nb'] and st['nb']['reach_box'] is not None:
            s += '; the %s on wall %d stands in the corner' % (st['nb']['reach_box']['name'], st['neighbour'])
        sh = st['shelf_over'] or st['shelf_at']
        if sh:
            s += '; a connecting shelf (%s) is drawn at this end' % ', '.join(u['name'] for u in sh)
        return s
    return _plain(_why(f) + ((': ' + f.detail) if f.detail else ''))


def _owner_block(F, findings, rows, kind):
    """The hold (kind='hold') or note (kind='info') findings as owner lines; a finding whose wall is unknown falls
    back to the rule's own text, cleaned of its tags."""
    out = []
    for f in findings:
        row = rows.get(f.wall)
        try:
            body = (_owner_hold if kind == 'hold' else _owner_note)(F, f, row) if row else None
        except Exception:
            body = None
        if body is None:
            body = _plain(_why(f) + ((': ' + f.detail.replace('HOLD: ', '').replace(' (notes 14.4); owner to decide', '')) if f.detail else ''))
        out.append('   wall %d (%s), %s: %s' % (f.wall, f.room, f.end, body))
    return out


# --------------------------------------------------------------------------------------------- the step
def apply_fillers(job_in, job_out=None, width_in=0.75, after_walls=False):
    if job_out is not None and W.same_file(job_out, job_in):
        raise ValueError('refusing to overwrite the input job; give another output name')
    F = _proto('fillers'); R = _proto('reserve'); A = _proto('addfiller')
    lines, checks, added, temps = [HEADER], [], [], []
    rep = {'lines': lines, 'checks': checks, 'findings': [], 'added': added, 'written': None, 'changed': False}
    rows = {}
    try:
        model = F.load_job(job_in)
        findings = F.missing_fillers(model)
        rows = {row['wall']['id']: row for row in F.wall_table(model)}
    except (Exception, SystemExit) as e:
        checks.append('CHECK fillers: the rule could not be checked on this job (%s); no filler was added' % _err(e))
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
                lines.append('   wall %d (%s), %s: no filler where the run meets the wall %s; a %s filler would be added here (no output file was given, so nothing was done)'
                             % (f.wall, f.room, f.end, f.end, fr(FILLER_W)))
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
                    msg = _err(e)
                    lines.append('wall %d (%s): the units reach the %s of the wall with no filler there, but no filler was added: %s' % (f.wall, f.room, f.end, msg))
                    checks.append('CHECK %s wall %d, %s: no filler was added; %s' % (f.room, f.wall, f.end, msg))
                    continue
                lines += blk['lines']; checks += blk['checks']; added.append(blk['added'])
                cur = t2
            if added:
                try:
                    still = [g for g in F.missing_fillers(cur) if g.hold == '']
                except (Exception, SystemExit) as e:
                    still = []
                    checks.append('CHECK fillers: the rule could not be re-checked on the new file (%s)' % _err(e))
                for g in still:
                    checks.append('CHECK %s wall %d, %s: after adding %s the rule still finds this end without a filler: %s'
                                  % (g.room, g.wall, g.end, _n(len(added), 'filler', 'fillers'), _why(g)))
        if not fixes and not holds:
            lines.append('   no run of units is missing an end filler by the rule')
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
                lines.append('%s added. This is a TEST file until KCD has opened it.' % _n(len(added), 'filler', 'fillers'))
            else:
                bits = []
                failed = len(fixes) - len(added)
                if failed:
                    bits.append('%s where a filler belongs could not be done (see the CHECK list)' % _n(failed, 'wall end', 'wall ends'))
                if holds:
                    bits.append('%s for the engineer to decide' % _n(len(holds), 'wall end', 'wall ends'))
                if not bits:
                    bits.append('the job after the wall step was kept as it is' if after_walls else 'the job was kept as it is')
                lines.append('no filler added; ' + '; '.join(bits))
        # the corner and opening notes follow the block, after a blank line
        if holds:
            lines += ['', 'For the engineer to decide (the rule found these but did not act):'] + _owner_block(F, holds, rows, 'hold')
            for f in holds:
                row = rows.get(f.wall)
                try:
                    body = _owner_hold(F, f, row) if row else None
                except Exception:
                    body = None
                if body is None:
                    body = _plain(_why(f) + ((': ' + f.detail.replace('HOLD: ', '').replace(' (notes 14.4); owner to decide', '')) if f.detail else '')) + '; the engineer decides'
                checks.append('CHECK %s wall %d, %s: %s' % (f.room, f.wall, f.end, body))
        if notes:
            lines += ['', 'Notes on the fillers that are there:'] + _owner_block(F, notes, rows, 'info')
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
    if a.out and W.same_file(a.out, a.job):
        print('Stopped: the output must not be the input job; give another name with --out'); return 2
    if a.reserve_start:
        if not a.out:
            ap.error('--reserve-start needs --out')
        try:
            lines, checks, touched = reserve_start(a.job, a.reserve_start, a.out)
        except ValueError as e:                     # reserve.load: not a live wall of this job
            print('Stopped: %s.' % str(e).rstrip('.')); return 2
        except FillError as e:
            print('Stopped: the room for the filler could not be made (%s); nothing was written.' % e); return 2
        print('\n'.join(lines)); print('CHECKS (%d)' % len(checks)); print('\n'.join('   ' + c for c in checks)); print('touched', touched)
        return 0
    try:
        rep = apply_fillers(a.job, a.out)
    except ValueError as e:
        print('Stopped: %s.' % str(e).rstrip('.')); return 2
    print('\n'.join(rep['lines']))
    if rep['checks']:
        print(); print('TO CHECK (%d):' % len(rep['checks'])); print('\n'.join('  ' + c for c in rep['checks']))
    print(); print('Written: %s' % (rep['written'] or 'nothing'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
