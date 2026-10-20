#!/usr/bin/env python3
"""
fillers.py  --  prototype for the owner's rule "WHEN UNITS GO BETWEEN 2 WALLS THERE NEEDS TO BE FILLERS ON BOTH SIDES".

It only REPORTS. Nothing is written to any file.

    missing_fillers(job) -> list of Finding
        job = a .job path, or a model from load_job() / load_walls10()
        one Finding per wall end where a run of cabinets touches a CLOSED wall end and no filler stands there:
        (room, wall, end 'start'/'end', why, the cabinet that would give up 3/4, its new width, the filler's X)

    wall_table(job) -> list of dict      the per-wall tabulation used by the study (closed/open, reach, filler, end cabinet)

Definitions (from the wall records, notes 14.2):
    a wall END is CLOSED when another wall of the room continues from it (left_id for the START, right_id for the END,
    kcdwalls.free_end), OPEN when the wall simply stops (doorway, a return that ends in the room, or a wall drawn alone).
    The corner turn is signed: with the room on the left of START->END, a left turn (+90) is an inside corner
    (the two runs meet in the room's corner); a right turn is a reentrant corner (the run end is exposed).
    a RUN reaches a wall end when its outermost box ends within REACH_TOL (1/8") of it, or past it (designers overlap).
    a run is BETWEEN TWO WALLS when it reaches a closed START and a closed END.
    a FILLER is a unit of type 230/130 or cab 234/231/131* or 'filler' in its name (kcdwalls.is_filler), 3/4 wide as
    the owner wants; designers also draw W = 3/4, D = face width (notes 14.4), engineers W = face width, D = 3/4.

Each closed end is also classified by what the NEIGHBOUR wall holds at the shared corner (corner_class): 'wall' (no
cabinet within 30" of the corner: a bare return, a door stub), 'zone' (the neighbour's run is set back ~24" with a
connecting shelf in the corner: the designers' corner convention; engineers leave these without a filler, C_fillers.md
section 2), 'side' (a neighbour cabinet stands in the corner, the run butts against its side), 'casing' (an opening on the
neighbour starts at the corner), 'angled' (inside angle not 90). Only 'wall'/'casing' corners give FIX findings.

Everything that is not certain is reported with a 'hold' flag so the engineer decides; the later fix step would only
act on findings with hold == ''. Known limits: no notion of levels (stacked uppers, bases and their fillers share one X
line); the 30" zone threshold and 1/8" reach tolerance are the study's choices.
"""
import collections
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))   # the repo's kcd-room-splitter, wherever it is checked out
import kcdjob, kcdunits, kcdwalls                                     # noqa: E402
from kcdwalls import IN, frac_inches, wrap180, snap16, parse_wall    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FILLER_W = 190                     # 3/4" as KCD stores it (0.748")
REACH_TOL = IN // 8                # a box "touches" the wall end within 1/8"
END_TOL = IN // 16                 # a unit "is at" the wall end within 1/16"
NEAR_END = 2 * IN                  # a filler within 2" of the wall end counts as the end filler (engineers park them at 1/16 or 3/4)
SHORT_GAP = 3 * IN                 # a run stopping less than 3" short of a closed end is reported as 'short' (information)

# ------------------------------------------------------------------------------------------- unit kinds
_T = {}                            # cab (lower) -> type code, from the library bundle (ref/cab_types_walls10.json)
try:
    _T = {k.lower(): int(v) for k, v in json.load(open(os.path.join(HERE, 'ref', 'cab_types_walls10.json'))).items() if v}
except Exception:
    pass

FEATURE_RE = re.compile(r'obstruction|outlet|switch|sprinkler|vent|pipe|column|beam|soffit|thermostat|register|'
                        r'water ?heater|laundry|washer|dryer|refri|electric box|tv\b|screen|picture|bowl|clock|books?\b|'
                        r'soda can|utility|mantel|cutout|wiring hole|obstruction cut', re.I)   # not 'door'/'window': 'Upper w Doors' is a cabinet; openings come by type/cab
ACC_RE = re.compile(r'led|light|rack|valet|belt|tie\b|hook|jt |earring|lock|hamper|tilt|shoes|mens|strip|power|remote|file|'
                    r'stiffener|slatwall frame|sw\d|cleat|bracket', re.I)
CATALOG_RE = re.compile(r'wall ?bed|murphy|cielo|shoe|hutch|refri|l[- ]shape|l shv|corner|slat ?wall|laundry|drawer', re.I)


def unit_type(u):
    t = u.get('type')
    if t:
        return t
    cab = (u.get('cab') or '').lower()
    return _T.get(cab) or _T.get(cab + '.cab') or 0


def classify(u):
    """filler / panel / endpanel / cab / shelf / backing / opening / decor / platform / leg / feature / acc."""
    cab = (u.get('cab') or '').lower(); name = (u.get('name') or '').lower(); t = unit_type(u)
    if kcdwalls.is_filler(u) or t in (230, 130):
        return 'filler'
    if cab.startswith('custom') or (t == 550):
        return 'panel'
    if 'endpanel' in cab or 'end panel' in name or t == 400:
        return 'endpanel'
    if t in (10, 20) or cab in ('010.cab', '020.cab') or re.match(r'02\dl?\.cab$', cab):
        return 'opening'
    if t == 500 or 'backing' in cab:
        return 'backing'
    if t == 890 or cab.startswith('890'):
        return 'decor'
    if 'platform' in cab or 'seperator' in name or 'separator' in name:
        return 'platform'
    if t == 880 or cab.startswith('lleg') or 'leg leveler' in name:
        return 'leg'
    if t in (640, 641, 644, 645, 646, 647) or cab.startswith(('cset', 'cstop', '260-sliding')) or name in ('shelf', 'skin shelf', 'rod and shelf', 'rod', 'euro shelf', 'sliding shelf'):
        return 'shelf'
    if t == 1000 or (u.get('w_raw', 0) <= 32 and (u.get('h_in') or 1) <= 0.2):
        return 'feature' if FEATURE_RE.search(name) or FEATURE_RE.search(cab) else 'acc'
    if FEATURE_RE.search(name) or FEATURE_RE.search(cab):
        return 'feature'
    if ACC_RE.search(name) and t == 0:
        return 'acc'
    return 'cab'


def is_box(u):
    return u['kind'] in ('cab', 'filler', 'panel', 'endpanel')


# ------------------------------------------------------------------------------------------- the model
class Model:
    """rooms {n: name}; walls {id: parsed wall dict (kcdwalls.parse_wall + 'room_name')}; units {wall id: [unit dicts]}."""
    def __init__(self, name, source):
        self.name, self.source = name, source
        self.rooms, self.walls, self.units = {}, {}, collections.defaultdict(list)

    def live_walls(self):
        return [w for w in self.walls.values() if w['is_live']]

    def room_name(self, n):
        return self.rooms.get(n, '')


def _mk_unit(**k):
    u = dict(k)
    u['end'] = u['x_raw'] + u['w_raw']
    u['kind'] = classify(u)
    return u


def load_job(path):
    """A .job file -> Model (type codes from the unit records)."""
    data = open(path, 'rb').read()
    m = Model(os.path.basename(path), path)
    m.rooms = kcdwalls.room_names(data)
    for r in kcdwalls.job_walls(data):
        p = dict(r.parsed); p['room_name'] = m.rooms.get(p['room'], '')
        m.walls[p['id']] = p
    job = kcdunits.read_job(path, None)
    for u in job.units:
        m.units[u.wall].append(_mk_unit(id=u.id, seq=u.seq, name=u.kcd_name or u.cab, cab=u.cab, type=u.T, x_raw=u.raw(1), w_raw=u.raw(2),
                                        h_in=u.inch(3), d_in=u.inch(4), ls_raw=u.raw(5), rs_raw=u.raw(7), qty=u.qty))
    for lst in m.units.values():
        lst.sort(key=lambda d: (d['x_raw'], d['seq']))
    return m


def load_walls10(path, which=None):
    """The laptop dump walls10.txt (notes 14.4) -> {job number: Model}. Type codes come from the library bundle."""
    sys.path.insert(0, os.path.join(HERE, '..', 'rules'))
    import parse_walls
    out = {}
    for n, j in parse_walls.load(path).items():
        if which and n not in which:
            continue
        m = Model(j['path'].split('\\')[-1], path)
        m.n = n
        m.rooms = dict(j['rooms'])
        for w in j['walls']:
            p = parse_wall(bytes.fromhex(w['hex'])); p['room_name'] = m.rooms.get(p['room'], '')
            m.walls[p['id']] = p
        for u in j['units']:
            m.units[u['wall']].append(_mk_unit(id=u['id'], seq=u['seq'], name=u['name'], cab=u['cab'], type=None, x_raw=u['x_raw'], w_raw=u['w_raw'],
                                               h_in=u['H'], d_in=u['D'], ls_raw=int(round(u['LS'] * IN)), rs_raw=int(round(u['RS'] * IN)), qty=u['qty']))
        for lst in m.units.values():
            lst.sort(key=lambda d: (d['x_raw'], d['seq']))
        out[n] = m
    return out


def as_model(job):
    if isinstance(job, Model):
        return job
    if isinstance(job, str) and job.lower().endswith('.job'):
        return load_job(job)
    raise TypeError('job must be a .job path or a Model')


# ------------------------------------------------------------------------------------------- geometry of one wall
def top_boxes(units, L):
    """The width-taking units of a wall (cabinets, fillers, panels) that are not drawn inside another one and not parked
    past the wall end, in X order."""
    boxes = [u for u in units if is_box(u) and u['x_raw'] < L + END_TOL and u['end'] > -NEAR_END]
    tops = []
    for u in boxes:
        nested = False
        for v in boxes:
            if v is u or u['kind'] == 'filler' or v['kind'] == 'filler':
                continue
            if v['x_raw'] - END_TOL <= u['x_raw'] and u['end'] <= v['end'] + END_TOL:
                if v['w_raw'] > u['w_raw'] + END_TOL:          # strictly inside a wider box (a sliding shelf in a base, a pull-out)
                    nested = True; break
                # the same extent = a stack (a base and the upper on it): both stay top-level
        if not nested:
            tops.append(u)
    return tops


def corner_turn(m, w, S):
    """Signed turn at wall end S (degrees) and the neighbour wall, or (None, None) when the end is open."""
    nid = w['left_id'] if S == 'start' else w['right_id']
    nb = m.walls.get(nid) if nid else None
    if not nb or not nb['is_live']:
        return None, None
    turn = wrap180(w['angle_deg'] - nb['angle_deg']) if S == 'start' else wrap180(nb['angle_deg'] - w['angle_deg'])
    return turn, nb


def neighbour_corner_units(m, nb, at):
    """Units of the neighbour wall that reach into the shared corner: within NEAR_END of its END (at='end') or START."""
    out = []
    for u in m.units.get(nb['id'], []):
        if u['kind'] in ('acc', 'decor', 'leg', 'opening', 'feature', 'platform'):
            continue
        if at == 'end' and u['end'] >= nb['length_raw'] - NEAR_END and u['x_raw'] < nb['length_raw'] + END_TOL:
            out.append(u)
        if at == 'start' and u['x_raw'] <= NEAR_END and u['end'] > -END_TOL:
            out.append(u)
    return out


def neighbour_view(m, nb, at):
    """What the neighbour wall holds near the shared corner. at='end' when the corner is the neighbour's END.
    Returns dict(box=nearest width-taking unit, box_dist, shelf=nearest connecting shelf, shelf_dist, opening_dist,
    reach_box=the neighbour's box that stands in the corner itself (dist <= REACH_TOL), bound=its depth in raw)."""
    Ln = nb['length_raw']
    def dist(u):
        return (Ln - u['end']) if at == 'end' else u['x_raw']
    tops = top_boxes(m.units.get(nb['id'], []), Ln)
    shelves = [u for u in m.units.get(nb['id'], []) if u['kind'] == 'shelf' and unit_type(u) in (640, 645, 641, 670)]
    opens = [u for u in m.units.get(nb['id'], []) if u['kind'] == 'opening']
    v = {'box': None, 'box_dist': None, 'shelf': None, 'shelf_dist': None, 'opening_dist': None, 'reach_box': None, 'bound': 0, 'n_boxes': len(tops)}
    if tops:
        b = min(tops, key=lambda u: max(dist(u), 0))
        v['box'], v['box_dist'] = b, max(dist(b), 0)
        if dist(b) <= REACH_TOL:
            v['reach_box'] = b
            v['bound'] = int(round(b['d_in'] * IN))
    if shelves:
        sh = min(shelves, key=lambda u: max(dist(u), 0))
        v['shelf'], v['shelf_dist'] = sh, max(dist(sh), 0)
    if opens:
        v['opening_dist'] = min(max(dist(u), 0) for u in opens)
    return v


def end_state(m, w, S):
    """Everything the rule needs to know about one wall end."""
    L = w['length_raw']
    units = m.units.get(w['id'], [])
    tops = top_boxes(units, L)
    turn, nb = corner_turn(m, w, S)
    st = {'end': S, 'closed': nb is not None, 'turn': turn, 'neighbour': nb['id'] if nb else 0, 'tops': tops,
          'inside_angle': (180.0 - abs(turn)) if turn is not None else None}
    if nb:
        st['corner_units'] = neighbour_corner_units(m, nb, 'end' if S == 'start' else 'start')
        st['nb'] = neighbour_view(m, nb, 'end' if S == 'start' else 'start')
    else:
        st['corner_units'] = []
        st['nb'] = None
    if not tops:
        st.update(run=False, gap=None, filler=None, cabinet=None, shelf_over=None)
        return st
    bound = st['nb']['bound'] if st['nb'] else 0               # a neighbour's cabinet standing in the corner takes this much of our wall
    if S == 'start':
        first = min(tops, key=lambda u: u['x_raw'])
        gap = first['x_raw']                                   # > 0 empty wall before the run, < 0 run past the start
        fillers = [u for u in tops if u['kind'] == 'filler' and u['x_raw'] <= bound + NEAR_END]
        cabs = sorted([u for u in tops if u['kind'] != 'filler'], key=lambda u: u['x_raw'])
    else:
        first = max(tops, key=lambda u: u['end'])
        gap = L - first['end']
        fillers = [u for u in tops if u['kind'] == 'filler' and u['end'] >= L - bound - NEAR_END]
        cabs = sorted([u for u in tops if u['kind'] != 'filler'], key=lambda u: -u['end'])
    st['run'] = True
    st['gap'] = gap
    st['bound'] = bound
    st['gap_to_bound'] = gap - bound                            # the room left between the run and the corner cabinet's side
    st['reach'] = gap <= REACH_TOL
    st['reach_bound'] = bound > 0 and abs(gap - bound) <= REACH_TOL
    st['filler'] = fillers[0] if fillers else None
    st['fillers'] = fillers
    st['cabinet'] = cabs[0] if cabs else None
    st['outer'] = first
    # the cabinet's distance to the filler (or to the wall end): > 0 gap, < 0 overlap
    c = st['cabinet']
    if c:
        if fillers:
            st['cab_gap'] = (c['x_raw'] - max(f['end'] for f in fillers)) if S == 'start' else (min(f['x_raw'] for f in fillers) - c['end'])
        else:
            st['cab_gap'] = c['x_raw'] if S == 'start' else L - c['end']
    else:
        st['cab_gap'] = None
    # connecting / corner shelves drawn across this wall end
    sh = [u for u in units if u['kind'] == 'shelf' and ((S == 'start' and u['x_raw'] < -END_TOL) or (S == 'end' and u['end'] > L + END_TOL))]
    st['shelf_over'] = sh
    # a connecting shelf that starts/ends exactly at this end (the engineers' corner zone)
    st['shelf_at'] = [u for u in units if u['kind'] == 'shelf' and unit_type(u) in (640, 645) and
                      ((S == 'start' and abs(u['x_raw']) <= END_TOL) or (S == 'end' and abs(u['end'] - L) <= END_TOL))]
    return st


def wall_table(job):
    """One row per live wall with the two end states; used by the study and by missing_fillers()."""
    m = as_model(job)
    rows = []
    for w in sorted(m.live_walls(), key=lambda w: (w['room'], w['id'])):
        rows.append({'model': m, 'wall': w, 'start': end_state(m, w, 'start'), 'end': end_state(m, w, 'end')})
    return rows


# ------------------------------------------------------------------------------------------- the rule
Finding = collections.namedtuple('Finding', 'room wall end why cabinet new_width filler_x hold detail')

# how a closed wall end is classified (see C_fillers.md section 2):
#   'wall'    the run butts against the bare wall: the neighbour wall has no cabinet near the corner  -> the owner's rule
#   'zone'    the neighbour's run is set back from the corner (a corner zone with connecting shelves) -> engineers leave no filler
#   'side'    a neighbour cabinet stands in the corner itself; the run butts against its side          -> fillers seen here too (POLONSKA)
#   'angled'  the inside angle is not 90 degrees
#   'casing'  a door/window opening on the neighbour starts at the corner
ZONE_MAX = 30 * IN                 # a neighbour cabinet within 30" of the corner makes it a corner zone


def corner_class(st, our_depth_raw):
    if not st['closed']:
        return 'open'
    if st['inside_angle'] is not None and abs(st['inside_angle'] - 90) > 2:
        return 'angled'
    nb = st['nb']
    if nb is None:
        return 'wall'
    if nb['reach_box'] is not None:
        return 'side'
    if nb['opening_dist'] is not None and nb['opening_dist'] <= 2 * IN:
        return 'casing'
    near_box = nb['box_dist'] is not None and nb['box_dist'] <= ZONE_MAX
    near_shelf = nb['shelf_dist'] is not None and nb['shelf_dist'] <= ZONE_MAX
    if near_box or near_shelf:
        return 'zone'
    return 'wall'


def _hold_reason(st, w, S):
    """Why the fix step must NOT touch this end on its own (the engineer decides)."""
    c = st['cabinet']
    if c is None:
        return 'only fillers/panels stand on this wall'
    nm = (c['name'] or '').lower(); t = unit_type(c)
    if c['kind'] in ('panel', 'endpanel'):
        return 'the unit at the wall end is a %s (%r): the designer chose a panel there' % (c['kind'].replace('endpanel', 'finished end panel'), c['name'])
    if 'drawer' in nm:
        return 'the cabinet at the wall end is a drawer unit (%r): engineers keep drawer widths' % c['name']
    if CATALOG_RE.search(nm) or t in (670, 270, 630, 770):
        return 'the cabinet at the wall end is a catalog product (%r): its width does not change' % c['name']
    if c['w_raw'] - FILLER_W < 12 * IN:
        return '%r would come out under 12 inches' % c['name']
    L = w['length_raw']
    if (S == 'start' and c['x_raw'] - st['bound'] > REACH_TOL) or (S == 'end' and L - st['bound'] - c['end'] > REACH_TOL):
        return 'the cabinet does not itself reach the wall end (%s away)' % frac_inches(abs(st['cab_gap']))
    inside = [u for u in st['tops'] if u is not c and u['kind'] != 'filler' and u['x_raw'] >= c['x_raw'] - END_TOL and u['end'] <= c['end'] + END_TOL]
    if inside:
        return '%r has other units drawn inside it (%s)' % (c['name'], ', '.join(repr(u['name']) for u in inside))
    at_end = [u for u in st['tops'] if u['kind'] != 'filler' and ((S == 'start' and u['x_raw'] <= st['bound'] + REACH_TOL) or (S == 'end' and u['end'] >= L - st['bound'] - REACH_TOL))]
    if len(at_end) > 1:
        return 'a stack of units stands against this wall end (%s): all of them would have to give up the 3/4' % ', '.join('%r %s' % (u['name'], frac_inches(u['w_raw'])) for u in at_end)
    return ''


def _nb_text(st):
    nb = st['nb']
    if not nb:
        return ''
    bits = []
    if nb['reach_box'] is not None:
        bits.append('%r on wall %d stands in the corner (%s deep)' % (nb['reach_box']['name'], st['neighbour'], frac_inches(st['bound'])))
    elif nb['box'] is not None:
        bits.append('nearest cabinet on wall %d is %r, %s from the corner' % (st['neighbour'], nb['box']['name'], frac_inches(nb['box_dist'])))
    else:
        bits.append('wall %d has no cabinets' % st['neighbour'])
    if nb['shelf'] is not None and nb['shelf_dist'] <= ZONE_MAX:
        bits.append('connecting shelf %r %s from the corner' % (nb['shelf']['name'], frac_inches(nb['shelf_dist'])))
    if nb['opening_dist'] is not None and nb['opening_dist'] <= 6 * IN:
        bits.append('a door/window opening %s from the corner' % frac_inches(nb['opening_dist']))
    return '; '.join(bits)


def missing_fillers(job):
    """The findings of the rule for every live wall of the job. Only reports."""
    m = as_model(job)
    out = []
    for row in wall_table(m):
        w = row['wall']; L = w['length_raw']; rn = w['room_name'] or ('room %d' % w['room'])
        if not row['start']['run']:
            continue
        cls = {S: corner_class(row[S], 0) for S in ('start', 'end')}
        touch = {S: row[S]['reach'] or row[S]['reach_bound'] for S in ('start', 'end')}
        both = row['start']['closed'] and row['end']['closed'] and touch['start'] and touch['end']
        for S in ('start', 'end'):
            st = row[S]; O = 'end' if S == 'start' else 'start'
            filler = st['filler']
            # ---- open ends: no rule; say what is there
            if not st['closed']:
                if filler and st['gap'] <= REACH_TOL:
                    out.append(Finding(rn, w['id'], S, 'open end with a filler', filler['name'], None, filler['x_raw'], 'info',
                                       'no wall continues here in the drawing, yet a %s filler %r stands at the %s; a wall drawn alone (no returns drawn) may still be between two real walls'
                                       % (frac_inches(filler['w_raw']), filler['name'], S)))
                continue
            if st['turn'] is not None and st['turn'] < 0:
                if touch[S] and not filler:
                    out.append(Finding(rn, w['id'], S, 'reentrant corner', st['cabinet']['name'] if st['cabinet'] else None, None, None, 'info',
                                       'the wall turns away here (outside corner): the run end is exposed, a finished end rather than a filler'))
                continue
            # ---- a filler is there: check it
            if filler:
                fw = filler['w_raw']; fd = int(round(filler['d_in'] * IN))
                notes = []
                if abs(fw - FILLER_W) > END_TOL and abs(fd - FILLER_W) <= END_TOL:
                    notes.append("drawn the engineers' way (W = face %s, D = 3/4)" % frac_inches(fw))
                elif abs(fw - FILLER_W) <= END_TOL and fd > FILLER_W + END_TOL:
                    notes.append("drawn the designers' way (W = 3/4, D = face %s)" % frac_inches(fd))
                elif abs(fw - FILLER_W) > END_TOL:
                    notes.append('filler is %s wide, not 3/4' % frac_inches(fw))
                if st['gap'] - st['bound'] > END_TOL:
                    notes.append('the filler stands %s from the %s' % (frac_inches(st['gap'] - st['bound']), 'wall end' if not st['bound'] else 'corner cabinet'))
                if st['cab_gap'] is not None and abs(st['cab_gap']) > END_TOL:
                    notes.append('%s of %s between the filler and %r' % ('gap' if st['cab_gap'] > 0 else 'overlap', frac_inches(abs(st['cab_gap'])), st['cabinet']['name']))
                if cls[S] == 'side':
                    notes.append('the filler is against the side of %r (wall %d), not the wall' % (st['nb']['reach_box']['name'], st['neighbour']))
                out.append(Finding(rn, w['id'], S, 'filler present' + (', check' if notes else ''), filler['name'], None, filler['x_raw'], 'info', '; '.join(notes)))
                continue
            # ---- closed end, no filler
            c = st['cabinet']
            if touch[S]:
                hold = _hold_reason(st, w, S)
                if cls[S] == 'zone':
                    hold = hold or 'corner zone: the run around the corner is set back here and the engineers leave this end without a filler (notes 14.4); owner to decide'
                elif cls[S] == 'angled':
                    hold = hold or 'the corner is %.0f degrees, not 90: a filler here is the engineer\'s call' % st['inside_angle']
                elif cls[S] == 'side':
                    hold = hold or 'the run butts against the side of %r (wall %d), not against the wall' % (st['nb']['reach_box']['name'], st['neighbour'])
                shelf_here = st['shelf_over'] or st['shelf_at']
                if shelf_here and not hold:
                    hold = 'a connecting shelf crosses this wall end (%s): the corner belongs to the run around the corner' % ', '.join(repr(u['name']) for u in shelf_here)
                if both:
                    why = 'between two walls, no filler at the %s' % S
                else:
                    why = 'run touches the closed %s, no filler there (the other end is %s)' % (S, 'open' if not row[O]['closed'] else 'not reached')
                why += ' [%s]' % cls[S]
                detail = ''
                if c:
                    detail = '%r X %s W %s ends %s (wall %s)' % (c['name'], frac_inches(c['x_raw']), frac_inches(c['w_raw']), frac_inches(c['end']), frac_inches(L))
                if st['gap'] < -END_TOL:
                    detail += '; the run is drawn %s past the wall end' % frac_inches(-st['gap'])
                nbt = _nb_text(st)
                if nbt:
                    detail += '; ' + nbt
                if shelf_here:
                    detail += '; connecting shelf at this end on this wall: %s' % ', '.join('%r' % u['name'] for u in shelf_here)
                if hold:
                    detail += '; HOLD: ' + hold
                new_w = snap16(c['w_raw'] - FILLER_W) if (c and not hold) else None
                fx = (0 if S == 'start' else L - FILLER_W) if not hold else None
                out.append(Finding(rn, w['id'], S, why, c['name'] if c else None, new_w, fx, 'hold' if hold else '', detail))
            elif 0 < st['gap'] - st['bound'] <= SHORT_GAP:
                detail = 'the run stops %s short of the closed %s (last unit %r)' % (frac_inches(st['gap'] - st['bound']), S, st['outer']['name'])
                nbt = _nb_text(st)
                if nbt:
                    detail += '; ' + nbt
                if st['shelf_over'] or st['shelf_at']:
                    detail += '; connecting shelf at this end: %s' % ', '.join('%r' % u['name'] for u in st['shelf_over'] + st['shelf_at'])
                out.append(Finding(rn, w['id'], S, 'short of the wall [%s]' % cls[S], st['outer']['name'], None, None, 'info', detail))
    return out


def format_findings(findings, title=''):
    P = [title] if title else []
    if not findings:
        P.append('   nothing to report')
    for f in findings:
        tag = {'': 'FIX', 'hold': 'CHECK', 'info': 'NOTE'}[f.hold]
        s = '   %-5s %-14s wall %2d %-5s %s' % (tag, f.room[:14], f.wall, f.end, f.why)
        if f.hold == '' and f.cabinet:
            s += ': %r %s -> %s wide, new filler 3/4 at X %s' % (f.cabinet, frac_inches(f.new_width + FILLER_W), frac_inches(f.new_width), frac_inches(f.filler_x))
        P.append(s)
        if f.detail:
            P.append('         ' + f.detail)
    return '\n'.join(P)


if __name__ == '__main__':
    for a in sys.argv[1:]:
        print(format_findings(missing_fillers(a), '== ' + os.path.basename(a)))
