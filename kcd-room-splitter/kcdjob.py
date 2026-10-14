"""Reader for KCD v23 .job files (VB-style binary: 2-byte length strings, Int16/Int32 fields).

parse(data) returns a list of sections; each section is (name, start, end, info) and the
sections tile the file exactly from byte 0 to EOF, so a writer can rebuild a file by
concatenating section bytes (edited or copied).
"""
import struct

UNIT_PREFIX = 1806   # unit bytes that come before the category string
UNIT_SUFFIX = 27     # unit bytes after the UNW name string (holds the unit id)


class R:
    def __init__(s, d, p=0):
        s.d = d
        s.p = p

    def str(s):
        n = struct.unpack_from('<H', s.d, s.p)[0]
        v = s.d[s.p + 2:s.p + 2 + n]
        if s.p + 2 + n > len(s.d):
            raise ValueError('string past EOF at %d' % s.p)
        s.p += 2 + n
        return v

    def raw(s, n):
        v = s.d[s.p:s.p + n]
        s.p += n
        return v

    def i16(s):
        v = struct.unpack_from('<h', s.d, s.p)[0]
        s.p += 2
        return v

    def i32(s):
        v = struct.unpack_from('<i', s.d, s.p)[0]
        s.p += 4
        return v


def unit_body(r):
    """Strings + fixed fields between a unit's prefix and suffix."""
    u = {}
    for k in ['cat', 'cab', 'lib', 'prt', 'pcb', 'name', 'edge', 'shp', 'profile']:
        u[k] = r.str()
    u['f86_at'] = r.p
    u['f86'] = r.raw(86)
    u['mats'] = [r.str() for _ in range(8)]
    u['more'] = [r.str() for _ in range(7)]
    u['f10'] = r.raw(10)
    u['unw'] = r.str()
    u['unwname'] = r.str()
    u['wall'] = struct.unpack_from('<h', u['f86'], 0)[0]
    u['wallflag'] = struct.unpack_from('<h', u['f86'], 2)[0]
    return u


LAST = []


def parse(d):
    r = R(d)
    S = []                      # (name, start, end, info)
    global LAST
    LAST = S

    def sec(name, start, info=None):
        S.append((name, start, r.p, info or {}))

    J = {}
    # ---- header -------------------------------------------------------------
    st = r.p
    J['version'] = r.str()
    r.raw(12)
    n = struct.unpack_from('<H', d, r.p)[0]
    r.p += 2
    r.raw(n)                                  # opaque save blob
    assert r.str() == b'** Job Heading **'
    J['cust_at'] = r.p
    J['cust'] = [r.str() for _ in range(5)]
    J['date1'] = r.str()
    J['date2'] = r.str()
    J['counts_at'] = r.p
    r.raw(2)
    J['L'] = list(struct.unpack_from('<5i', d, r.p))   # L[0]=38100 ... L[2]=verts+1, L[3]=idx-ish, L[4]=faces+1
    r.raw(20)
    J['nwalls_at'] = r.p
    J['nwalls'] = r.i16()
    J['nunits'] = r.i16()
    J['rtf_at'] = r.p
    J['rtf'] = r.str()
    nl = r.i16()
    [(r.str(), r.i16()) for _ in range(nl)]
    r.str()
    J['view_at'] = r.p                        # 82 bytes: current room's camera, note count, ...
    r.raw(82)
    assert r.str() == b'** Rooms **'
    sec('header', st, J)

    # ---- rooms --------------------------------------------------------------
    st = r.p
    nrooms = r.i16()
    r.raw(2)
    cur_at = r.p
    cur = r.i32()
    rooms = []
    for _ in range(nrooms):
        a = r.p
        r.raw(62)
        nm = r.str()
        r.raw(14)
        [r.str() for _ in range(10)]
        rooms.append({'start': a, 'end': r.p, 'name': nm})
    sec('rooms', st, {'n': nrooms, 'cur': cur, 'cur_at': cur_at, 'list': rooms})

    # ---- handle sets: (nrooms+1) x 9 ---------------------------------------
    st = r.p
    sets = []
    for k in range(nrooms + 1):
        a = r.p
        for _ in range(9):
            r.str()
            r.raw(28)
            r.str()
        sets.append((a, r.p))
    sec('handles', st, {'sets': sets})

    # ---- job settings --------------------------------------------------------
    st = r.p
    r.str()
    [r.str() for _ in range(9)]
    nc = r.i16()
    r.raw((nc + 1) * 6)
    nlo = r.i16()
    for _ in range(nlo):
        r.str()
        k = r.i16()
        r.raw(k * 6)
    npair_at = r.p
    npair = r.i16()
    r.raw(npair * 4)
    sec('settings', st, {'npair_at': npair_at, 'npair': npair})

    # ---- walls ---------------------------------------------------------------
    st = r.p
    walls = []
    for _ in range(J['nwalls']):
        a = r.p
        r.raw(205)
        r.str()
        r.raw(5)
        walls.append({'start': a, 'end': r.p,
                      'id': struct.unpack_from('<i', d, a + 125)[0],
                      'room': struct.unpack_from('<i', d, a + 129)[0],
                      # wall length in 0.1 mm (checked on NOTIK 2ND LIN and ELLA: equals the last unit's X + W when
                      # that unit ends at the wall), and the ids of the walls meeting its left and right end (0 = none)
                      'length': struct.unpack_from('<i', d, a + 20)[0],
                      'left': struct.unpack_from('<i', d, a + 36)[0],
                      'right': struct.unpack_from('<i', d, a + 40)[0]})
    sec('walls', st, {'list': walls})

    # ---- post-wall block -----------------------------------------------------
    st = r.p
    r.raw(16)
    r.str()
    sec('postwall', st)

    # ---- units: prefix(1806) + body + suffix(27) -----------------------------
    st = r.p
    units = []
    for _ in range(J['nunits']):
        a = r.p
        r.raw(UNIT_PREFIX)
        u = unit_body(r)
        sfx = r.p
        r.raw(UNIT_SUFFIX)
        u.update({'start': a, 'end': r.p, 'suffix_at': sfx,
                  'id': struct.unpack_from('<h', d, sfx + 12)[0]})
        units.append(u)
    sec('units', st, {'list': units})

    # ---- 3D mesh cache --------------------------------------------------------
    st = r.p
    n1 = r.i32()
    r.raw(4 * n1)
    nverts = J['L'][2] - 1
    r.raw(12 * nverts)
    nfaces = J['L'][4] - 1
    notes_at = d.find(b'\x0b\x00** Notes **', r.p)
    faces_at = notes_at - 66 * nfaces
    nidx = (faces_at - r.p) // 4
    assert (faces_at - r.p) % 4 == 0 and nidx >= 0, 'mesh index block misaligned'
    r.raw(4 * nidx)
    r.raw(66 * nfaces)
    assert r.p == notes_at
    sec('mesh', st, {'n1': n1, 'nverts': nverts, 'nidx': nidx, 'nfaces': nfaces})

    # ---- notes ---------------------------------------------------------------
    st = r.p
    assert r.str() == b'** Notes **'
    nn = r.i16()
    notes = []
    for _ in range(nn):
        a = r.p
        r.raw(30)
        txt = r.str()
        r.str()
        r.str()
        tr = r.p
        r.raw(36)
        notes.append({'start': a, 'end': r.p, 'text': txt, 'room_at': tr + 4,
                      'room': struct.unpack_from('<i', d, tr + 4)[0]})
    sec('notes', st, {'list': notes})

    # ---- per-room shapes: Int16 + (nrooms+1) slots of [Long n; n x shape] -----
    #      shape = Long npts + npts x 24 + bbox 16 + 16 bytes (tag first) + Long m + m x 4
    st = r.p
    r.raw(2)
    slots = []
    for _ in range(nrooms + 1):
        a = r.p
        cnt = r.i32()
        items = []
        for _k in range(cnt):
            b0 = r.p
            npts = r.i32()
            r.raw(npts * 24)
            r.raw(16)                       # bounding box
            tag_at = r.p
            r.raw(16)
            m = r.i32()
            r.raw(4 * m)
            items.append((b0, r.p, struct.unpack_from('<i', d, tag_at)[0], tag_at - b0))
        slots.append({'start': a, 'end': r.p, 'items': items})
    sec('roomshapes', st, {'slots': slots})

    # ---- material table (Long 1008 + 1009 x 72) and texture table ------------
    st = r.p
    m = r.i32()
    r.raw((m + 1) * 72)
    t = r.i32()
    for _ in range(t + 1):
        r.str()
        r.raw(20)
    sec('materials', st)

    # ---- error log ---------------------------------------------------------------
    st = r.p
    r.raw(4)
    ne = r.i16()
    for _ in range(ne + 1):
        r.str()
    sec('errlog', st)

    # ---- zero block up to PicTemp marker -------------------------------------------
    st = r.p
    z = d.find(b'\x14\x00Start-PicTempZipFile', r.p)
    assert z >= 0
    r.p = z
    sec('gap', st, {'len': z - st})

    # ---- print pages ---------------------------------------------------------------
    st = r.p
    e = d.find(b'\x12\x00End-PicTempZipFile', r.p)
    assert e >= 0
    r.p = e
    r.str()
    r.raw(4)
    sec('pictemp', st)

    # ---- unit info defaults: Long 14, Long nrooms-1, nrooms x 15 STR ------------------
    st = r.p
    assert r.str() == b'Start-UnitInfoDefaults'
    a = r.i32()
    b = r.i32()
    dsets = []
    for _ in range(b + 1):
        x = r.p
        for _k in range(a + 1):
            r.str()
        dsets.append((x, r.p))
    sec('defaults', st, {'a': a, 'b': b, 'sets': dsets})
    assert r.p == len(d), 'trailing bytes: %d' % (len(d) - r.p)

    # sanity: sections tile the file
    pos = 0
    for name, a, b2, _ in S:
        assert a == pos, (name, a, pos)
        pos = b2
    assert pos == len(d)
    return S


if __name__ == '__main__':
    import sys
    for f in sys.argv[1:]:
        d = open(f, 'rb').read()
        S = parse(d)
        info = {n: i for n, a, b, i in S}
        print(f.split('/')[-1], 'OK', 'rooms', info['rooms']['n'], 'walls', len(info['walls']['list']),
              'units', len(info['units']['list']), 'notes', len(info['notes']['list']),
              'gap', info['gap']['len'], 'mesh', {k: info['mesh'][k] for k in ('n1', 'nverts', 'nidx', 'nfaces')})
