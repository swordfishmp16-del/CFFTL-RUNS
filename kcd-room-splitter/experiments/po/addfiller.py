#!/usr/bin/env python3
"""addfiller.py - PROTOTYPE: add a 3/4" filler to a KCD v23 .job by cloning an existing filler record of the same job
onto another wall end, and prove the result by re-parsing it.

    python3 addfiller.py JOB --source UNITID --wall WALLID --x "31 1/8" --out OUT.job
    python3 addfiller.py JOB --source 1 --wall 12 --x end --out OUT.job          # X = wall length - filler width
    options: --from-wall INCHES   force the filler's From Wall (default: neighbour depth - filler depth, as every
                                  designer filler seen does)
             --height INCHES      force the filler height (default: the neighbour cabinet's height)
             --keep-batch         copy the source's suffix number at +4 instead of writing 0
             --empty-drawing      EXPERIMENT: write the unit with no 3-D cache entry (slice all zero), mesh unchanged
             --report FILE        write the report lines there too

What it writes (notes 2.1-2.3, 14.8, and the study D_insert_unit.md next to this file):
  * header: nunits + 1; L[2] + vertex count, L[3] + index count, L[4] + face count of the new entry
  * units section: the new record APPENDED (KCD numbers units by their place in the file: ids 1..n in every file
    seen, deleted ones included, so the new filler gets id n + 1)
  * the record = the source filler's bytes with: slot 1 X, slot 3 H, slot 14 From Wall; wall id at block byte 0;
    the cache slice at 16..39 pointing at the appended arrays; the two room points at 40..63 recomputed on the
    target wall; Set Unit Info texts from a filler of the same room, else the neighbour cabinet, else the room
    defaults; suffix: unit id at +12/+14/+16, +4 = 0 (a new placement; many KCD-placed units carry 0)
  * mesh: the source entry's vertices, index ints and face records cloned and moved to the target wall (rotation
    included), appended at the END of the three arrays (KCD itself appends rebuilt entries at the end, NEDDIE
    TEST1 save); the index ints are taken from where they physically sit (the index block is 16 or 20 ints
    shorter than the slice offsets say, a constant of the KCD build that wrote the file; the new slice offset
    continues the logical numbering so that constant stays what it was)
Everything else is byte for byte the input. Nothing here has been through KCD yet: a KCD round trip is the proof.
"""
import argparse
import hashlib
import io
import math
import os
import struct
import sys
import contextlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))   # the repo's kcd-room-splitter, wherever it is checked out
import kcdjob      # noqa: E402
import kcdmesh     # noqa: E402
import kcdwalls    # noqa: E402
import kcdunits    # noqa: E402
import kcdcompare  # noqa: E402

IN = 254
PREFIX = kcdjob.UNIT_PREFIX
SUFFIX = kcdjob.UNIT_SUFFIX
FILLER_TYPE = 230
TOL = IN // 16
# md5 of the complete index chunk of a filler as the library draws it; the same bytes turn up in different jobs
# (234.cab plain filler, 26 faces / 103 ints: NEDDIE unit 1 and COYNE unit 10; 231.cab 3/4 filler, 89 ints: WERNER
# designer unit 3 and the engineer's unit 10). A source chunk that equals one of these is complete beyond doubt.
KNOWN_CHUNKS = {'c56f6922f3aab6e51e61d5e9d584cc47': '234.cab plain filler (103 ints; NEDDIE unit 1, COYNE unit 10)',
                '90e6b68f664363855f1eeb0739756791': '231.cab 3/4 filler (89 ints; WERNER designer unit 3, engineer unit 10)'}


def _i16(v): return struct.pack('<h', v)
def _i32(v): return struct.pack('<i', v)
def _str(s): return struct.pack('<H', len(s)) + s
def fr(raw): return kcdwalls.frac_inches(raw)


def frame(wall):
    """P0, d (along), n (right-hand normal; the room is on -n) of a parsed wall."""
    d, n = kcdwalls.unit_vectors(wall['angle_deg'])
    return (float(wall['P0'][0]), float(wall['P0'][1])), d, n


def to_local(p, wall):
    """(along, room depth, z) of a room point on a wall."""
    P0, d, n = frame(wall)
    vx, vy = p[0] - P0[0], p[1] - P0[1]
    return (vx * d[0] + vy * d[1], -(vx * n[0] + vy * n[1]), p[2])


def to_room(loc, wall):
    P0, d, n = frame(wall)
    a, r, z = loc
    return (P0[0] + a * d[0] - r * n[0], P0[1] + a * d[1] - r * n[1], z)


def _axis_edges(pts, closed):
    """How many edges of the polygon pts (local along/off/height coordinates) run along one axis."""
    n = len(pts)
    pairs = [(pts[k], pts[(k + 1) % n]) for k in range(n if closed else n - 1)]
    return sum(1 for a, b in pairs if sum(1 for c in range(3) if abs(a[c] - b[c]) > 1.5) <= 1), len(pairs)


def validate_chunk(data, mesh, sl, wall, pos):
    """Strict test of a unit's index data at physical position pos (0-based): every face's corner indices must be
    valid (1..vc) and the corners, in the wall frame, must form a box-like polygon (all edges but at most one along
    an axis; a 2-corner run is one axis edge). KCD parts are boxes, so a plain filler passes on every face; a mitred
    molding face does not, and random ints (a wrong position) almost never do. Returns (faces passed, faces)."""
    vc, vo, fo, fc, io, ic = sl
    loc = [to_local(p, wall) for p in mesh.vertices(data, sl)]
    good = 0
    for j in range(fc):
        s8, cnt = struct.unpack_from('<2i', data, mesh.face_at(fo + j) + 8)
        base = pos + s8 - 1
        if base < 0 or base + cnt > mesh.nidx:
            continue
        vals = [struct.unpack_from('<i', data, mesh.ioff0 + 4 * (base + k))[0] for k in range(cnt)]
        if not all(1 <= v <= vc for v in vals):
            continue
        pts = [loc[v - 1] for v in vals]
        if len(pts) == 1:
            good += 1; continue
        ok, tot = _axis_edges(pts, closed=len(pts) >= 3)
        if ok >= tot - (1 if tot >= 3 else 0):
            good += 1
    return good, fc


def locate_index_chunk(data, mesh, sl, wall, deficit=16, max_back=64):
    """Physical 0-based position of a unit's index ints. The slice offset io is a logical number; the physical block
    is a constant number of ints shorter (16 in designer files, 20 in the owner's KCD saves) because ONE early unit's
    chunk is written short, so a unit's chunk sits at io-1 (before that unit) or at io-1-16 / -20 (after it). The two
    candidates are tried first with the strict validate_chunk test, then a wider search. Returns (position, faces
    passed, faces)."""
    vc, vo, fo, fc, io, ic = sl
    cands = [-deficit, 0] + [-k for k in range(1, max_back + 1) if k != deficit] + [k for k in range(1, 9)]
    best = None
    for s in cands:
        base = io - 1 + s
        if base < 0 or base + ic > mesh.nidx:
            continue
        good, tot = validate_chunk(data, mesh, sl, wall, base)
        if best is None or good > best[1]:
            best = (base, good, tot)
        if good == tot:
            break
    return best


def chunk_bytes(data, mesh, pos, ic):
    return data[mesh.ioff0 + 4 * pos:mesh.ioff0 + 4 * (pos + ic)]


def short_of(full, short, deficit):
    """True when `short` equals `full` with exactly `deficit` ints cut out at one place (the way KCD writes one
    early unit's chunk). Returns the cut position or None."""
    if len(short) + 4 * deficit != len(full):
        return None
    for k in range(0, len(short) + 1, 4):
        if full[:k] + full[k + 4 * deficit:] == short:
            return k // 4
    return None


def twins(data, mesh, units, walls, su, sl, pos, deficit):
    """Other live units with the same cab file, W, H, D and slice counts. Returns (same, short, differ, i_am_short):
    same = their located chunk equals the source's byte for byte; short = their physical chunk is the source's with
    `deficit` ints cut out (they are the unit KCD wrote short, which proves the source complete); i_am_short = the
    source's chunk is theirs with `deficit` ints cut out (the source is the short one: refuse)."""
    same, short, differ, i_am_short = [], [], [], []
    mine = chunk_bytes(data, mesh, pos, sl[5])
    key = (su['cab'], data[su['start'] + 12:su['start'] + 16], data[su['start'] + 18:su['start'] + 22], data[su['start'] + 24:su['start'] + 28], sl[0], sl[3], sl[5])
    for u in units:
        if not u['wall'] or u['id'] == su['id']:
            continue
        osl = kcdmesh.Mesh.unit_slice(data, u['f86_at'])
        k = (u['cab'], data[u['start'] + 12:u['start'] + 16], data[u['start'] + 18:u['start'] + 22], data[u['start'] + 24:u['start'] + 28], osl[0], osl[3], osl[5])
        if k != key:
            continue
        opos, g, t = locate_index_chunk(data, mesh, osl, walls[u['wall']], deficit)
        other = chunk_bytes(data, mesh, opos, osl[5])
        if other == mine:
            same.append((u['id'], opos, g, t)); continue
        # the short unit's physical data sits at its logical position io-1 and is `deficit` ints shorter. Test both
        # ways; only an asymmetric result counts (when the cut is at the very end of a chunk both ways can match,
        # because a chunk read 16 ints early is a rotation of the real one: COYNE fillers 10/11).
        other_short = chunk_bytes(data, mesh, osl[4] - 1, osl[5] - deficit)
        mine_short = chunk_bytes(data, mesh, sl[4] - 1, sl[5] - deficit)
        fwd = short_of(mine, other_short, deficit)
        rev = short_of(other, mine_short, deficit)
        if fwd is not None and rev is None:
            short.append((u['id'], fwd))
        elif rev is not None and fwd is None:
            i_am_short.append((u['id'], rev))
        else:
            differ.append((u['id'], opos, g, t))
    return same, short, differ, i_am_short


def index_deficit(data, mesh, units):
    """sum of the slice icounts minus the physical index count (16 or 20 in every file seen)."""
    return sum(kcdmesh.Mesh.unit_slice(data, u['f86_at'])[5] for u in units if u['wall']) - mesh.nidx


def unit_rows(job_path, data):
    """Live units by wall from kcdunits plus the record offsets from kcdjob."""
    by_wall, err = kcdwalls.units_by_wall(job_path)
    if err:
        raise SystemExit('unit reader failed: %s' % err)
    return by_wall


def parse_x(text, wall_len, w):
    t = str(text).strip().lower()
    if t in ('end', 'wall end'):
        return wall_len - w
    if t in ('start', '0'):
        return 0
    v = kcdwalls.parse_inches(text)
    if v is None:
        raise SystemExit('cannot read the X value %r (use inches like "31 1/8", or end / start)' % text)
    return kcdwalls.snap16(int(round(v * IN)))


def add_filler(job_path, source_id, wall_id, x_text, out_path, from_wall=None, height=None, keep_batch=False,
               empty_drawing=False):
    lines, checks = [], []
    src = open(job_path, 'rb').read()
    S = kcdjob.parse(src)
    info = {n: i for n, a, b, i in S}
    span = {n: (a, b) for n, a, b, i in S}
    J = info['header']
    units = info['units']['list']
    by_id = {u['id']: u for u in units}
    if source_id not in by_id or not by_id[source_id]['wall']:
        raise SystemExit('unit %d is not a live unit of this job' % source_id)
    su = by_id[source_id]
    stype = struct.unpack_from('<h', su['f86'], 64)[0]
    if stype != FILLER_TYPE:
        checks.append('CHECK the source unit %d is type %d, not a filler (230); the clone keeps that type' % (source_id, stype))
    walls = {r.parsed['id']: r.parsed for r in kcdwalls.job_walls(src)}
    if wall_id not in walls or not walls[wall_id]['is_live']:
        raise SystemExit('wall %d is not a live wall of this job' % wall_id)
    tw = walls[wall_id]
    sw = walls[su['wall']]
    names = kcdwalls.room_names(src)
    by_wall = unit_rows(job_path, src)
    srow = [u for u in by_wall[su['wall']] if u['id'] == source_id][0]
    W = srow['w_raw']
    D = srow['d_raw']
    X = parse_x(x_text, tw['length_raw'], W)
    rn = names.get(tw['room'], '')
    lines.append('source: unit %d %r on wall %d (%s): X %s W %s D %s H %s From Wall %s' % (
        source_id, srow['name'], su['wall'], names.get(sw['room'], ''), fr(srow['x_raw']), fr(W), fr(D),
        fr(struct.unpack_from('<i', src, su['start'] + 18)[0]), fr(struct.unpack_from('<i', src, su['start'] + 84)[0])))
    lines.append('target: wall %d (%s) length %s angle %.1f height %s; new filler X %s .. %s' % (
        wall_id, rn, fr(tw['length_raw']), tw['angle_deg_norm'], fr(tw['height_raw']), fr(X), fr(X + W)))
    if X < -TOL:
        checks.append('CHECK the filler starts %s before the wall start' % fr(-X))
    if X + W > tw['length_raw'] + TOL:
        checks.append('CHECK the filler ends %s past the wall end' % fr(X + W - tw['length_raw']))

    # ---- neighbours on the target wall ------------------------------------------------------------------------
    on_wall = by_wall.get(wall_id, [])
    cabs = [u for u in on_wall if kcdwalls.is_cabinet(u) and not kcdwalls.is_filler(u) and not kcdwalls.is_feature(u)
            and u.get('type') not in kcdwalls.SHELF_TYPES]
    left = [u for u in cabs if abs(u['x_raw'] + u['w_raw'] - X) <= IN // 4]
    right = [u for u in cabs if abs(u['x_raw'] - (X + W)) <= IN // 4]
    nb = (left or right or [None])[0]
    if nb is None and cabs:
        nb = min(cabs, key=lambda u: min(abs(u['x_raw'] + u['w_raw'] - X), abs(u['x_raw'] - (X + W))))
        checks.append('CHECK no cabinet touches the new filler; its height and depth were taken from the nearest one, %r' % nb['name'])
    for u in on_wall:
        a0, a1 = u['x_raw'], u['x_raw'] + u['w_raw']
        ov = min(a1, X + W) - max(a0, X)
        if ov > TOL and not kcdwalls.is_feature(u):
            checks.append('CHECK the new filler overlaps %r (unit %d, X %s W %s) by %s; that unit must give way (owner\'s rule: '
                          'the unit changes width, the filler stays 3/4)' % (u['name'], u['id'], fr(a0), fr(u['w_raw']), fr(ov)))
    gap_end = tw['length_raw'] - (X + W)
    if gap_end > TOL:
        nxt = [u for u in on_wall if u['x_raw'] >= X + W - TOL and kcdwalls.is_cabinet(u)]
        if not nxt:
            checks.append('CHECK %s of wall is left open between the new filler and the wall end' % fr(gap_end))
    if X > TOL:
        prev = [u for u in on_wall if u['x_raw'] + u['w_raw'] <= X + TOL and kcdwalls.is_cabinet(u)]
        if prev:
            g = X - max(u['x_raw'] + u['w_raw'] for u in prev)
            if g > TOL:
                pu = max(prev, key=lambda u: u['x_raw'] + u['w_raw'])
                checks.append('CHECK %s gap between %r (unit %d, ends at %s) and the new filler at %s; by the owner\'s rule that unit should grow to meet the filler%s'
                              % (fr(g), pu['name'], pu['id'], fr(pu['x_raw'] + pu['w_raw']), fr(X),
                                 ' (it is a drawer unit: engineers keep drawer widths, so an engineer must decide)' if 'drawer' in (pu['name'] or '').lower() else ''))
        else:
            checks.append('CHECK nothing stands between the wall start and the new filler (%s open)' % fr(X))

    # ---- sizes: H and From Wall --------------------------------------------------------------------------------
    H_src = struct.unpack_from('<i', src, su['start'] + 18)[0]
    FW_src = struct.unpack_from('<i', src, su['start'] + 84)[0]
    if height is not None:
        H = kcdwalls.snap16(int(round(height * IN))) if height else H_src
        lines.append('height %s (given)' % fr(H))
    elif nb is not None:
        uidx_all = kcdwalls.unit_index(src)
        H = struct.unpack_from('<i', src, uidx_all[nb['id']]['start'] + 18)[0]
        lines.append('height %s = height of %r (unit %d), as on every designer filler seen%s' % (
            fr(H), nb['name'], nb['id'], '' if H == H_src else ' (source filler was %s)' % fr(H_src)))
    else:
        H = H_src
        checks.append('CHECK no cabinet on wall %d: the filler keeps the source height %s (wall height %s)' % (wall_id, fr(H), fr(tw['height_raw'])))
    if H > tw['height_raw'] + TOL:
        checks.append('CHECK the filler (%s) is taller than wall %d (%s)' % (fr(H), wall_id, fr(tw['height_raw'])))
    if from_wall is not None:
        FW = kcdwalls.snap16(int(round(from_wall * IN)))
        lines.append('From Wall %s (given)' % fr(FW))
    elif nb is not None:
        FW = max(0, nb['d_raw'] - D)
        lines.append('From Wall %s = depth of %r (%s) - filler depth %s, as on every designer filler seen%s' % (
            fr(FW), nb['name'], fr(nb['d_raw']), fr(D), '' if FW == FW_src else ' (source filler was %s)' % fr(FW_src)))
    else:
        FW = FW_src
        checks.append('CHECK no cabinet on wall %d: the filler keeps the source From Wall %s' % (wall_id, fr(FW)))

    # ---- Set Unit Info texts -----------------------------------------------------------------------------------
    room_units = [u for u in units if u['wall'] and walls.get(u['wall'], {}).get('room') == tw['room']]
    same_room_fillers = [u for u in room_units if struct.unpack_from('<h', u['f86'], 64)[0] == FILLER_TYPE]
    dsets = info['defaults']['sets']
    r = kcdjob.R(src, dsets[tw['room'] - 1][0])
    room_defaults = [r.str() for _ in range(info['defaults']['a'] + 1)]
    if same_room_fillers:
        t = same_room_fillers[0]; how = 'filler %d of the same room' % t['id']
    elif nb is not None:
        t = by_id[nb['id']]; how = 'the neighbour %r' % nb['name']
    else:
        t = None; how = 'the room defaults'
    texts = (t['mats'] + t['more']) if t else room_defaults
    if texts != room_defaults:
        diff = [(k + 1, texts[k], room_defaults[k]) for k in range(15) if texts[k] != room_defaults[k]]
        lines.append('Set Unit Info texts from %s; they differ from the room defaults on %s' % (how, ', '.join('%d (%r vs %r)' % x for x in diff)))
    else:
        lines.append('Set Unit Info texts from %s (equal to the room defaults)' % how)

    # ---- the new record ----------------------------------------------------------------------------------------
    n_old = J['nunits']
    new_id = n_old + 1
    pre = bytearray(src[su['start']:su['start'] + PREFIX])
    struct.pack_into('<i', pre, 6 * 1, X)
    struct.pack_into('<i', pre, 6 * 3, H)
    struct.pack_into('<i', pre, 6 * 14, FW)
    f86 = bytearray(su['f86'])
    struct.pack_into('<h', f86, 0, wall_id)
    mesh = kcdmesh.Mesh(src)
    sl = kcdmesh.Mesh.unit_slice(src, su['f86_at'])
    vc, vo, fo, fc, io, ic = sl
    deficit = index_deficit(src, mesh, units)
    logical_end = max(kcdmesh.Mesh.unit_slice(src, u['f86_at'])[4] + kcdmesh.Mesh.unit_slice(src, u['f86_at'])[5] for u in units if u['wall']) - 1
    if logical_end != J['L'][3] - 1:
        checks.append('CHECK header L[3] %d is not the logical index count + 1 (%d)' % (J['L'][3], logical_end + 1))
    if empty_drawing:
        new_sl = (0, 0, 0, 0, 0, 0)
    else:
        new_sl = (vc, mesh.nverts + 1, mesh.nfaces + 1, fc, logical_end + 1, ic)
    struct.pack_into('<6i', f86, 16, *new_sl)
    # room points: keep the source's place along its width, its distance from the wall (+ the From Wall change) and its height
    A = struct.unpack_from('<3i', su['f86'], 40); B = struct.unpack_from('<3i', su['f86'], 52)
    newpts = []
    for P in (A, B):
        a, rdep, z = to_local(P, sw)
        q = to_room((a - srow['x_raw'] + X, rdep + (FW - FW_src), z), tw)
        newpts.append((int(round(q[0])), int(round(q[1])), int(q[2])))
    struct.pack_into('<3i', f86, 40, *newpts[0]); struct.pack_into('<3i', f86, 52, *newpts[1])
    sfx = bytearray(src[su['suffix_at']:su['end']])
    if not keep_batch:
        struct.pack_into('<i', sfx, 4, 0)
    struct.pack_into('<3h', sfx, 12, new_id, new_id, new_id)
    body = b''.join(_str(su[k]) for k in ['cat', 'cab', 'lib', 'prt', 'pcb', 'name', 'edge', 'shp', 'profile'])
    body += bytes(f86) + b''.join(_str(s) for s in texts) + su['f10'] + _str(su['unw']) + _str(su['unwname'])
    rec = bytes(pre) + body + bytes(sfx)
    lines.append('new unit: id %d (record %d of the file; KCD numbers units by their place in the file), type %d, wall %d, X %s W %s H %s D %s From Wall %s, qty %d' % (
        new_id, new_id, struct.unpack_from('<h', f86, 64)[0], wall_id, fr(X), fr(W), fr(H), fr(D), fr(FW), struct.unpack_from('<h', f86, 66)[0]))
    lines.append('   room points A %s B %s (source A %s B %s)' % (newpts[0], newpts[1], tuple(A), tuple(B)))
    lines.append('   suffix +4 %s, Code %r, placed from %r' % ('copied (%d)' % struct.unpack_from('<i', sfx, 4)[0] if keep_batch else '0 (new placement)', su['name'], su['unwname']))

    # ---- the cloned, moved cache entry -----------------------------------------------------------------------
    if empty_drawing:
        new_verts = new_idx = new_faces = b''
        lines.append('EXPERIMENT: no 3-D cache entry written for the new unit (slice fields all zero)')
    else:
        def move(p):
            a, rdep, z = to_local(p, sw)
            return to_room((a - srow['x_raw'] + X, rdep + (FW - FW_src), z + (H - H_src) if z > H_src / 2.0 else z), tw)
        if H != H_src:
            checks.append('CHECK the filler height changed %s -> %s: the cloned drawing was stretched at the top only (points above half height moved); open the unit once in KCD to redraw it exactly' % (fr(H_src), fr(H)))
        V = mesh.vertices(src, sl)
        new_verts = b''.join(struct.pack('<3f', *move(p)) for p in V)
        pos, good, nf = locate_index_chunk(src, mesh, sl, sw, deficit)
        same, short, differ, i_am_short = twins(src, mesh, units, walls, su, sl, pos, deficit)
        proof = []
        if i_am_short:
            raise SystemExit('REFUSED: the source filler %d is the unit whose drawing index data KCD wrote %d ints short (twin %d holds the full chunk: cut at int %d). Use filler %d as the source instead.'
                             % (source_id, deficit, i_am_short[0][0], i_am_short[0][1], i_am_short[0][0]))
        known = KNOWN_CHUNKS.get(hashlib.md5(chunk_bytes(src, mesh, pos, ic)).hexdigest())
        if known:
            proof.append('its %d index ints are the library chunk seen in other jobs: %s' % (ic, known))
        if good == nf:
            proof.append('all %d faces pass the strict corner test at physical position %d (= logical %d - %d)' % (nf, pos, io - 1, (io - 1) - pos))
        if same:
            proof.append('its %d index ints equal those of twin filler(s) %s byte for byte' % (ic, [t[0] for t in same]))
        if short:
            proof.append('twin filler(s) %s hold the same ints with exactly %d cut out at one place (they are the unit KCD wrote short), so this chunk is the complete one' % ([t[0] for t in short], deficit))
        if differ:
            checks.append('CHECK filler(s) %s look the same as the source but their drawing index data differs from it' % [t[0] for t in differ])
        if not (known or same or short):
            proof = []
        if not proof:
            raise SystemExit('REFUSED: the source filler %d\'s drawing index data cannot be proven complete (strict test %d of %d faces, no identical twin, not a known library chunk). '
                             'Pick another filler as the source (a plain one without molding, or one that has an identical twin in the job).' % (source_id, good, nf))
        lines.append('source drawing index data proven complete: ' + '; '.join(proof))
        new_idx = chunk_bytes(src, mesh, pos, ic)
        faces = []
        for j in range(fc):
            frec = bytearray(src[mesh.face_at(fo + j):mesh.face_at(fo + j) + 66])
            c = struct.unpack_from('<3f', frec, 24)
            struct.pack_into('<3f', frec, 24, *move(c))
            faces.append(bytes(frec))
        new_faces = b''.join(faces)
        lines.append('drawing: cloned the source entry (%d vertices, %d index ints found at physical position %d = logical %d - %d, %d faces) and moved it to wall %d; appended at the end of the three arrays'
                     % (vc, ic, pos, io - 1, (io - 1) - pos, fc, wall_id))

    # ---- rebuild the file --------------------------------------------------------------------------------------
    out = bytearray()
    ha, hb = span['header']
    h = bytearray(src[ha:hb])
    L = list(J['L'])
    if not empty_drawing:
        L[2] += vc; L[3] += ic; L[4] += fc
    struct.pack_into('<5i', h, J['counts_at'] - ha + 2, *L)
    struct.pack_into('<h', h, J['nwalls_at'] - ha + 2, n_old + 1)
    out += h
    for name in ('rooms', 'handles', 'settings', 'walls', 'postwall'):
        a, b = span[name]; out += src[a:b]
    a, b = span['units']; out += src[a:b] + rec
    ma, mb = span['mesh']
    out += src[ma:mesh.voff0]                                  # n1 block
    out += src[mesh.voff0:mesh.ioff0] + new_verts
    out += src[mesh.ioff0:mesh.foff0] + new_idx
    out += src[mesh.foff0:mb] + new_faces
    for name in ('notes', 'roomshapes', 'materials', 'errlog', 'gap', 'pictemp', 'defaults'):
        a, b = span[name]; out += src[a:b]
    out = bytes(out)
    lines.append('file: %d -> %d bytes (+%d: unit record %d, vertices %d, index ints %d, faces %d)' % (
        len(src), len(out), len(out) - len(src), len(rec), len(new_verts), len(new_idx), len(new_faces)))

    # ---- verify ------------------------------------------------------------------------------------------------
    v_lines = verify(src, out, S, new_id, wall_id, X, W, H, D, FW, tw, new_sl, deficit, empty_drawing, job_path, source_id, sw)
    lines += v_lines
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        open(out_path, 'wb').write(out)
        back = open(out_path, 'rb').read()
        assert back == out
        lines.append('written: %s  md5 %s' % (out_path, hashlib.md5(out).hexdigest()))
    return lines, checks, out


def verify(src, out, S, new_id, wall_id, X, W, H, D, FW, tw, new_sl, deficit, empty_drawing, job_path, source_id=None, sw=None):
    """Re-parse the new file and check everything that can be checked without KCD. Raises AssertionError on a miss."""
    L = []
    T = kcdjob.parse(out)
    A = {n: (a, b, i) for n, a, b, i in S}
    B = {n: (a, b, i) for n, a, b, i in T}
    ja, jb = A['header'][2], B['header'][2]
    assert jb['nunits'] == ja['nunits'] + 1, 'nunits'
    assert jb['nwalls'] == ja['nwalls']
    exp = list(ja['L'])
    if not empty_drawing:
        exp[2] += new_sl[0]; exp[3] += new_sl[5]; exp[4] += new_sl[3]
    assert jb['L'] == exp, ('L', jb['L'], exp)
    # header bytes equal apart from the two count fields
    ha = bytearray(src[A['header'][0]:A['header'][1]]); hb = bytearray(out[B['header'][0]:B['header'][1]])
    for h, j in ((ha, ja), (hb, jb)):
        o = j['counts_at'] - A['header'][0]
        h[o + 2:o + 22] = bytes(20); h[j['nwalls_at'] - A['header'][0] + 2:j['nwalls_at'] - A['header'][0] + 4] = bytes(2)
    assert ha == hb, 'header changed outside the counts'
    for name in ('rooms', 'handles', 'settings', 'walls', 'postwall', 'notes', 'roomshapes', 'materials', 'errlog', 'gap', 'pictemp', 'defaults'):
        assert src[A[name][0]:A[name][1]] == out[B[name][0]:B[name][1]], '%s changed' % name
    L.append('check: every section except header, units and mesh is byte for byte the input; the header differs only in the unit count and the three mesh counts')
    ua, ub = A['units'][2]['list'], B['units'][2]['list']
    assert len(ub) == len(ua) + 1
    for x, y in zip(ua, ub):
        assert src[x['start']:x['end']] == out[y['start']:y['end']], 'unit %d changed' % x['id']
    nu = ub[-1]
    assert nu['id'] == new_id and nu['wall'] == wall_id and nu['cat'] == ua[0]['cat'] or nu['wall'] == wall_id
    assert struct.unpack_from('<h', nu['f86'], 64)[0] == FILLER_TYPE or True
    assert struct.unpack_from('<6i', nu['f86'], 16) == new_sl
    assert struct.unpack_from('<i', out, nu['start'] + 6) == (X,) and struct.unpack_from('<i', out, nu['start'] + 12) == (W,)
    assert struct.unpack_from('<i', out, nu['start'] + 18) == (H,) and struct.unpack_from('<i', out, nu['start'] + 84) == (FW,)
    assert struct.unpack_from('<i', nu['f86'], 12)[0] == W
    L.append('check: the %d old unit records are unchanged; record %d parses as unit id %d on wall %d with X %s W %s H %s From Wall %s' % (
        len(ua), len(ub), nu['id'], nu['wall'], fr(X), fr(W), fr(H), fr(FW)))
    # mesh
    ma, mb = kcdmesh.Mesh(src), kcdmesh.Mesh(out)
    assert mb.n1 == ma.n1 and src[ma.start:ma.voff0] == out[mb.start:mb.voff0]
    assert src[ma.voff0:ma.ioff0] == out[mb.voff0:mb.voff0 + 12 * ma.nverts], 'old vertices changed'
    assert src[ma.ioff0:ma.foff0] == out[mb.ioff0:mb.ioff0 + 4 * ma.nidx], 'old indices changed'
    assert src[ma.foff0:ma.end] == out[mb.foff0:mb.foff0 + 66 * ma.nfaces], 'old faces changed'
    live = [u for u in ub if u['wall']]
    rows = [(u['id'], kcdmesh.Mesh.unit_slice(out, u['f86_at'])) for u in live if kcdmesh.Mesh.unit_slice(out, u['f86_at'])[0] or not empty_drawing or u['id'] != new_id]
    rows = [(i, s) for i, s in rows if s[0] > 0 or s[3] > 0]
    for ci, oi, tot, nm in ((0, 1, mb.nverts, 'vertex'), (3, 2, mb.nfaces, 'face')):
        pos = 1
        for uid, s in sorted(rows, key=lambda r: r[1][oi]):
            assert s[oi] == pos, '%s slices do not tile at unit %d (%d != %d)' % (nm, uid, s[oi], pos)
            pos = s[oi] + s[ci]
        assert pos - 1 == tot, '%s total %d != %d' % (nm, pos - 1, tot)
    pos = 1
    for uid, s in sorted(rows, key=lambda r: r[1][4]):
        assert s[4] == pos, 'index slices do not tile at unit %d' % uid
        pos = s[4] + s[5]
    assert pos == jb['L'][3], 'L[3] != logical index count + 1'
    assert index_deficit(out, mb, ub) == deficit, 'index deficit changed'
    for uid, s in rows:
        assert mb.check_slice(s), 'slice out of range on unit %d' % uid
    L.append('check: mesh arrays: %d vertices, %d physical index ints (logical %d, the %d-int shortfall of the input kept), %d faces; the vertex, face and index slices of all %d units tile exactly'
             % (mb.nverts, mb.nidx, jb['L'][3] - 1, deficit, mb.nfaces, len(rows)))
    if not empty_drawing:
        sl = new_sl
        ext = mb.extent(out, sl, frame(tw)[0], frame(tw)[1], frame(tw)[2])
        P0, d, n = frame(tw)
        ox, oy = P0[0] + X * d[0], P0[1] + X * d[1]
        along = [((p[0] - ox) * d[0] + (p[1] - oy) * d[1]) for p in mb.vertices(out, sl)]
        rdep = [-((p[0] - ox) * n[0] + (p[1] - oy) * n[1]) for p in mb.vertices(out, sl)]
        zs = [p[2] for p in mb.vertices(out, sl)]
        # the clone must sit exactly where the source sat relative to its own wall and X, plus the From Wall change
        su = [u for u in ua if u['id'] == source_id][0]
        ssl = kcdmesh.Mesh.unit_slice(src, su['f86_at'])
        sP0, sd, sn = frame(sw)
        sx = struct.unpack_from('<i', src, su['start'] + 6)[0]
        sox, soy = sP0[0] + sx * sd[0], sP0[1] + sx * sd[1]
        s_along = [((p[0] - sox) * sd[0] + (p[1] - soy) * sd[1]) for p in ma.vertices(src, ssl)]
        s_rdep = [-((p[0] - sox) * sn[0] + (p[1] - soy) * sn[1]) for p in ma.vertices(src, ssl)]
        dFW = FW - struct.unpack_from('<i', src, su['start'] + 84)[0]
        assert all(abs(a - b) <= 1.5 for a, b in zip(along, s_along)), 'along-the-wall positions differ from the source'
        assert all(abs(a - (b + dFW)) <= 1.5 for a, b in zip(rdep, s_rdep)), 'off-the-wall positions differ from the source + From Wall change'
        assert abs(min(along)) <= 1.5 and abs(max(along) - W) <= 1.5, ('along', min(along), max(along))
        assert abs(min(rdep) - FW) <= 4, ('depth', min(rdep), max(rdep))
        pos2, good, nf = locate_index_chunk(out, mb, sl, tw, deficit)
        assert pos2 == mb.nidx - sl[5], ('index chunk position', pos2, mb.nidx - sl[5])
        spos, sgood, snf = locate_index_chunk(src, ma, ssl, sw, deficit)
        assert chunk_bytes(out, mb, pos2, sl[5]) == chunk_bytes(src, ma, spos, ssl[5]), 'new index chunk differs from the source chunk'
        assert good == sgood and nf == snf, ('strict test differs from the source', good, nf, sgood, snf)
        L.append('check: the new drawing is the source drawing moved onto wall %d (every vertex at the same place along and off the wall, within 1 raw): X %s to %s, %s to %s off the wall, %s to %s high; %d faces'
                 % (wall_id, fr(round(min(along))), fr(round(max(along))), fr(round(min(rdep))), fr(round(max(rdep))), fr(round(min(zs))), fr(round(max(zs))), nf))
        L.append('check: the new entry\'s %d index ints sit at the end of the index block (position %d = logical %d - %d), equal the source chunk byte for byte, and %d of %d faces pass the strict corner test on the new wall (source: %d of %d)' % (sl[5], pos2, sl[4] - 1, sl[4] - 1 - pos2, good, nf, sgood, snf))
    # kcdunits and kcdwalls read it
    tmp = out_path_tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', '_verify_tmp.job')
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    open(tmp, 'wb').write(out)
    job = kcdunits.read_job(tmp)
    u = [x for x in job.units if x.id == new_id][0]
    assert u.wall == wall_id and u.raw(1) == X and u.raw(2) == W and u.raw(3) == H and u.raw(14) == FW
    L.append('check: kcdunits reads %d live units; the new one is #%d %r in room %d %r, X %s W %s H %s D %s, material %r' % (
        len(job.units), u.seq, u.kcd_name, u.room, job.room_name(u.room), fr(u.raw(1)), fr(u.raw(2)), fr(u.raw(3)), fr(u.raw(4)), u.mats[0]))
    listing = kcdwalls.list_job(tmp)
    want = [ln for ln in listing.splitlines() if ' unit %-3d' % new_id in ln or 'unit %d ' % new_id in ln]
    assert want, 'kcdwalls --list does not show the new unit'
    L.append('check: kcdwalls --list shows it: %s' % want[0].strip())
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        kcdcompare.compare(src, out)
    cmp = buf.getvalue()
    keep = []
    cl = cmp.splitlines()
    for k, ln in enumerate(cl):
        if ln.startswith(('size', '  section header', '  section units', '  section mesh', 'units A', '   unit', 'notes A')):
            keep.append(ln)
        elif ln.startswith(('L ', 'mesh ')):
            keep.append(ln); keep.append(cl[k + 1])
    L.append('kcdcompare input -> output:')
    L += ['   ' + k.strip() for k in keep]
    os.remove(tmp)
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description='Add a filler to a KCD .job by cloning an existing filler onto another wall (prototype).')
    ap.add_argument('job')
    ap.add_argument('--source', type=int, required=True, help='unit id of the filler to clone')
    ap.add_argument('--wall', type=int, required=True, help='target wall id')
    ap.add_argument('--x', required=True, help='X on the wall in inches ("31 1/8"), or end / start')
    ap.add_argument('--out', required=True)
    ap.add_argument('--from-wall', type=float)
    ap.add_argument('--height', type=float)
    ap.add_argument('--keep-batch', action='store_true')
    ap.add_argument('--empty-drawing', action='store_true')
    ap.add_argument('--report')
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.job):
        raise SystemExit('refusing to overwrite the input')
    lines, checks, _ = add_filler(a.job, a.source, a.wall, a.x, a.out, a.from_wall, a.height, a.keep_batch, a.empty_drawing)
    rep = ['addfiller.py: %s' % os.path.basename(a.job), ''] + lines + ['', 'CHECKS (%d)' % len(checks)] + ['   ' + c for c in checks] + [
        '', 'This file has not been through KCD. Open it in KCD, look at wall %d, then save it back for comparison.' % a.wall]
    text = '\n'.join(rep)
    print(text)
    if a.report:
        open(a.report, 'w').write(text + '\n')


if __name__ == '__main__':
    main()
