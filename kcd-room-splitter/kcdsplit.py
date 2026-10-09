"""Split a multi-room KCD v23 .job into one file per room.

Each output keeps exactly one room: its walls, the cabinets on those walls, its notes,
its handle set and its unit-info defaults. Walls and units are renumbered 1..N and every
reference to them is updated. Job-wide sections are copied byte for byte.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kcdjob  # noqa: E402


def _i16(v):
    return struct.pack('<h', v)


def _i32(v):
    return struct.pack('<i', v)


def split_room(d, keep):
    """Return the bytes of a job containing only room number `keep` (1-based)."""
    S = kcdjob.parse(d)
    sec = {n: (a, b, i) for n, a, b, i in S}
    out = []

    rooms = sec['rooms'][2]
    if not 1 <= keep <= rooms['n']:
        raise ValueError('room %d out of range 1..%d' % (keep, rooms['n']))

    # ---- walls to keep, old id -> new id ---------------------------------
    walls = sec['walls'][2]['list']
    kept_walls = [w for w in walls if w['room'] == keep]
    wmap = {w['id']: i + 1 for i, w in enumerate(kept_walls)}

    # ---- units to keep (placed on one of the kept walls) -------------------
    units = sec['units'][2]['list']
    kept_units = [u for u in units if u['wall'] in wmap]
    umap = {u['id']: i + 1 for i, u in enumerate(kept_units)}

    # ---- header: patch wall/unit counts -------------------------------------
    a, b, J = sec['header']
    h = bytearray(d[a:b])
    off = J['nwalls_at'] - a
    h[off:off + 4] = _i16(len(kept_walls)) + _i16(len(kept_units))
    out.append(bytes(h))

    # ---- rooms: one room, current room = 1 -----------------------------------
    a, b, R = sec['rooms']
    rec = R['list'][keep - 1]
    out.append(_i16(1) + d[a + 2:a + 4] + _i32(1) + d[rec['start']:rec['end']])

    # ---- handle sets: default set (0) + the kept room's set -------------------
    sets = sec['handles'][2]['sets']
    out.append(d[sets[0][0]:sets[0][1]] + d[sets[keep][0]:sets[keep][1]])

    # ---- settings: filter the (unit id, code) pair list --------------------------
    a, b, T = sec['settings']
    pairs = [struct.unpack_from('<hh', d, T['npair_at'] + 2 + 4 * i) for i in range(T['npair'])]
    pairs = [(umap[u], c) for u, c in pairs if u in umap]
    out.append(d[a:T['npair_at']] + _i16(len(pairs)) + b''.join(struct.pack('<hh', u, c) for u, c in pairs))

    # ---- walls ------------------------------------------------------------------
    for w in kept_walls:
        r = bytearray(d[w['start']:w['end']])
        new = wmap[w['id']]
        for o in (117, 119, 121, 123):
            r[o:o + 2] = _i16(new)
        r[125:129] = _i32(new)
        r[129:133] = _i32(1)
        for o in (36, 40):
            v = struct.unpack_from('<i', r, o)[0]
            r[o:o + 4] = _i32(wmap.get(v, 0))
        out.append(bytes(r))

    a, b, _ = sec['postwall']
    out.append(d[a:b])

    # ---- units ------------------------------------------------------------------
    for u in kept_units:
        r = bytearray(d[u['start']:u['end']])
        o = u['f86_at'] - u['start']
        r[o:o + 2] = _i16(wmap[u['wall']])
        o = u['suffix_at'] - u['start']
        new = umap[u['id']]
        for k in (12, 14, 16):
            r[o + k:o + k + 2] = _i16(new)
        out.append(bytes(r))

    # ---- 3D mesh cache: copied unchanged ---------------------------------------
    a, b, _ = sec['mesh']
    out.append(d[a:b])

    # ---- notes --------------------------------------------------------------------
    notes = [n for n in sec['notes'][2]['list'] if n['room'] == keep]
    blk = [b'\x0b\x00** Notes **', _i16(len(notes))]
    for n in notes:
        r = bytearray(d[n['start']:n['end']])
        wall = struct.unpack_from('<h', r, 24)[0]
        if wall:
            r[24:26] = _i16(wmap.get(wall, 0))
        o = n['room_at'] - n['start']
        r[o:o + 4] = _i32(1)
        blk.append(bytes(r))
    out.append(b''.join(blk))

    # ---- per-room shapes: keep shapes tagged with this room ------------------------
    a, b, X = sec['roomshapes']
    items = []
    for slot in X['slots']:
        for s0, s1, tag, tag_off in slot['items']:
            if tag == keep:
                r = bytearray(d[s0:s1])
                r[tag_off:tag_off + 4] = _i32(1)
                items.append(bytes(r))
    out.append(d[a:a + 2] + _i32(len(items)) + b''.join(items) + _i32(0))

    # ---- job-wide sections copied unchanged -------------------------------------------
    for name in ('materials', 'errlog', 'gap', 'pictemp'):
        a, b, _ = sec[name]
        out.append(d[a:b])

    # ---- unit-info defaults: one set (0-based room index) --------------------------------
    a, b, D = sec['defaults']
    s0, s1 = D['sets'][keep - 1]
    out.append(b'\x16\x00Start-UnitInfoDefaults' + _i32(D['a']) + _i32(0) + d[s0:s1])

    res = b''.join(out)
    check(res, rooms['list'][keep - 1]['name'], len(kept_walls), len(kept_units), len(notes))
    return res


def check(data, name, nwalls, nunits, nnotes):
    """Re-parse the output and confirm it holds exactly what we meant to write."""
    S = kcdjob.parse(data)
    sec = {n: i for n, a, b, i in S}
    assert sec['rooms']['n'] == 1 and sec['rooms']['list'][0]['name'] == name
    assert len(sec['walls']['list']) == nwalls and len(sec['units']['list']) == nunits
    assert len(sec['notes']['list']) == nnotes
    assert all(w['room'] == 1 for w in sec['walls']['list'])
    ids = {w['id'] for w in sec['walls']['list']}
    assert all(u['wall'] in ids for u in sec['units']['list'])
    assert [u['id'] for u in sec['units']['list']] == list(range(1, nunits + 1))
    assert all(n['room'] == 1 for n in sec['notes']['list'])


def safe_name(s):
    s = re.sub(r'[\\/:*?"<>|]', '-', s)
    return re.sub(r'\s+', ' ', s).strip()


def split_job(path, job_no, out_dir, prefix=''):
    """Write one file per room. Every room is built and checked before anything is written."""
    d = open(path, 'rb').read()
    rooms = {n: i for n, a, b, i in kcdjob.parse(d)}['rooms']['list']
    names = [safe_name('%s %s%s' % (job_no, prefix, rm['name'].decode('latin1'))) + '.job' for rm in rooms]
    if len(set(n.lower() for n in names)) != len(names):
        raise ValueError('two rooms would get the same file name: %s' % names)
    for fname in names:
        if os.path.exists(os.path.join(out_dir, fname)):
            raise FileExistsError(os.path.join(out_dir, fname))
    datas = [split_room(d, k) for k in range(1, len(rooms) + 1)]
    os.makedirs(out_dir, exist_ok=True)
    for fname, data in zip(names, datas):
        with open(os.path.join(out_dir, fname), 'wb') as f:
            f.write(data)
    return [(fname, len(data)) for fname, data in zip(names, datas)]


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('usage: kcdsplit.py JOBFILE JOBNUMBER OUTDIR [NAMEPREFIX]')
        sys.exit(2)
    try:
        made = split_job(sys.argv[1], sys.argv[2], sys.argv[3], *(sys.argv[4:5]))
    except FileExistsError as e:
        print('Stopped: %s already exists. Move or delete the old room files first. Nothing was made.' % e)
        sys.exit(1)
    except Exception as e:  # unreadable layout or failed self-check
        print('Stopped: this job could not be split safely (%s: %s). Nothing was made.' % (type(e).__name__, e))
        sys.exit(1)
    for fname, size in made:
        print('%-50s %10d bytes' % (fname, size))
