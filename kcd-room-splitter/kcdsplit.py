"""Split a multi-room KCD v23 .job into one file per room.

This does what KCD does when you delete rooms: the walls and cabinets of the other rooms
stay in the file as deleted entries (so no wall or cabinet number changes), their notes
are removed, and the kept room becomes room 1. The rules were matched byte for byte
against a file KCD itself saved after deleting rooms.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kcdjob  # noqa: E402

# Wall record bytes KCD keeps when it deletes a wall (colour and type fields);
# every other byte from 16 to 112 is zeroed, and the room (129) is set to 0.
WALL_KEEP = {32, 33, 34, 35, 46, 47, 48, 49, 82, 83, 84, 85}
# Unit fields (offsets in the 86-byte block) KCD zeroes when it deletes a cabinet:
# the wall number, its placement, and one flag.
UNIT_F86_ZERO = list(range(0, 4)) + list(range(16, 40)) + [66]
VIEW_NOTES_AT = 60           # note count inside the 82-byte view block


def _i16(v):
    return struct.pack('<h', v)


def _i32(v):
    return struct.pack('<i', v)


def _str(s):
    return struct.pack('<H', len(s)) + s


def deleted_wall(rec):
    r = bytearray(rec)
    for k in range(16, 113):
        if k not in WALL_KEEP:
            r[k] = 0
    r[129:133] = _i32(0)
    return bytes(r)


def deleted_unit(d, u):
    f = bytearray(u['f86'])
    for k in UNIT_F86_ZERO:
        f[k] = 0
    body = (_str(u['cat']) + _str(b'') * 4 + _str(u['name'].strip()) + _str(u['edge'])
            + _str(b'SQ3.shp') + _str(b'3" Square') + bytes(f) + _str(b'') * 15
            + bytes(10) + _str(b'') + _str(b''))
    sfx = bytearray(d[u['suffix_at']:u['end']])
    sfx[0:8] = bytes(8)
    return bytes(kcdjob.UNIT_PREFIX) + body + bytes(sfx)


def keep_rooms(d, keep):
    """Return a job holding only the rooms in `keep` (1-based, original order), renumbered 1..n."""
    S = kcdjob.parse(d)
    sec = {n: (a, b, i) for n, a, b, i in S}
    rooms = sec['rooms'][2]
    keep = sorted(set(keep))
    if not keep or keep[0] < 1 or keep[-1] > rooms['n']:
        raise ValueError('room numbers must be 1..%d' % rooms['n'])
    newnum = {old: i + 1 for i, old in enumerate(keep)}

    walls = sec['walls'][2]['list']
    wall_room = {w['id']: w['room'] for w in walls}
    units = sec['units'][2]['list']

    def unit_kept(u):
        return wall_room.get(u['wall'], 0) in newnum

    notes = [n for n in sec['notes'][2]['list'] if n['room'] in newnum or n['room'] == 0]
    out = []

    # ---- header: current-room camera and the note count in the view block ------
    a, b, J = sec['header']
    h = bytearray(d[a:b])
    v = J['view_at'] - a
    first = rooms['list'][keep[0] - 1]
    h[v:v + 52] = d[first['start']:first['start'] + 52]
    h[v + VIEW_NOTES_AT:v + VIEW_NOTES_AT + 4] = _i32(len(notes))
    out.append(bytes(h))

    # ---- rooms ----------------------------------------------------------------
    a, b, R = sec['rooms']
    out.append(_i16(len(keep)) + d[a + 2:a + 4] + _i32(1)
               + b''.join(d[R['list'][k - 1]['start']:R['list'][k - 1]['end']] for k in keep))

    # ---- handle sets: set 0 is the default, set k belongs to room k -------------------
    sets = sec['handles'][2]['sets']
    out.append(b''.join(d[sets[k][0]:sets[k][1]] for k in [0] + keep))

    # ---- settings: drop (unit, code) pairs whose cabinet is deleted -------------------
    a, b, T = sec['settings']
    by_id = {u['id']: u for u in units}
    pairs = [struct.unpack_from('<hh', d, T['npair_at'] + 2 + 4 * i) for i in range(T['npair'])]
    pairs = [(u, c) for u, c in pairs if u in by_id and unit_kept(by_id[u])]
    out.append(d[a:T['npair_at']] + _i16(len(pairs)) + b''.join(struct.pack('<hh', u, c) for u, c in pairs))

    # ---- walls: kept rooms renumbered, other rooms' walls deleted --------------------
    for w in walls:
        rec = d[w['start']:w['end']]
        if w['room'] in newnum:
            r = bytearray(rec)
            r[129:133] = _i32(newnum[w['room']])
            rec = bytes(r)
        elif w['room'] != 0:
            rec = deleted_wall(rec)
        out.append(rec)

    a, b, _ = sec['postwall']
    out.append(d[a:b])

    # ---- units: cabinets on deleted walls become deleted entries ----------------------
    for u in units:
        if u['wall'] and not unit_kept(u):
            out.append(deleted_unit(d, u))
        else:
            out.append(d[u['start']:u['end']])

    # ---- 3D view cache: copied (KCD rebuilds it when the job is saved) ----------------
    a, b, _ = sec['mesh']
    out.append(d[a:b])

    # ---- notes ----------------------------------------------------------------------
    blk = [_str(b'** Notes **'), _i16(len(notes))]
    for n in notes:
        r = bytearray(d[n['start']:n['end']])
        if n['room']:
            o = n['room_at'] - n['start']
            r[o:o + 4] = _i32(newnum[n['room']])
        blk.append(bytes(r))
    out.append(b''.join(blk))

    # ---- room shapes: one slot per room plus one ---------------------------------------
    a, b, X = sec['roomshapes']
    slots = X['slots']
    if any(s['items'] for s in slots[1:]):
        raise ValueError('room shapes outside the first slot are not supported yet')
    items = []
    for s0, s1, tag, tag_off in slots[0]['items']:
        if tag in newnum:
            r = bytearray(d[s0:s1])
            r[tag_off:tag_off + 4] = _i32(newnum[tag])
            items.append(bytes(r))
    out.append(d[a:a + 2] + _i32(len(items)) + b''.join(items) + _i32(0) * len(keep))

    # ---- job-wide sections copied unchanged ---------------------------------------------
    for name in ('materials', 'errlog', 'gap', 'pictemp'):
        a, b, _ = sec[name]
        out.append(d[a:b])

    # ---- unit-info defaults: set k-1 belongs to room k -------------------------------------
    a, b, D = sec['defaults']
    out.append(_str(b'Start-UnitInfoDefaults') + _i32(D['a']) + _i32(len(keep) - 1)
               + b''.join(d[D['sets'][k - 1][0]:D['sets'][k - 1][1]] for k in keep))

    res = b''.join(out)
    check(d, res, keep)
    return res


def check(src, res, keep):
    """Re-read the new file and confirm it holds exactly the kept rooms' content."""
    A = {n: i for n, a, b, i in kcdjob.parse(src)}
    B = {n: i for n, a, b, i in kcdjob.parse(res)}
    newnum = {old: i + 1 for i, old in enumerate(sorted(keep))}
    assert [r['name'] for r in B['rooms']['list']] == [A['rooms']['list'][k - 1]['name'] for k in sorted(keep)]
    wa, wb = A['walls']['list'], B['walls']['list']
    assert [w['id'] for w in wa] == [w['id'] for w in wb]
    assert all(y['room'] == newnum.get(x['room'], 0) for x, y in zip(wa, wb))
    room_a = {w['id']: w['room'] for w in wa}
    ua, ub = A['units']['list'], B['units']['list']
    assert [u['id'] for u in ua] == [u['id'] for u in ub]
    for x, y in zip(ua, ub):
        if room_a.get(x['wall'], 0) in newnum:
            assert x['wall'] == y['wall'] and x['cab'] == y['cab'] and x['f86'] == y['f86']
        else:
            assert y['wall'] == 0
    want = sorted(newnum[n['room']] for n in A['notes']['list'] if n['room'] in newnum)
    assert sorted(n['room'] for n in B['notes']['list'] if n['room']) == want
    assert B['defaults']['b'] == len(keep) - 1
    assert len(B['handles']['sets']) == len(keep) + 1


def split_room(d, k):
    return keep_rooms(d, [k])


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
