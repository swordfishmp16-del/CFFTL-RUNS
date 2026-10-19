#!/usr/bin/env python3
"""
kcdwalls.py  --  decoder / editor for the 205-byte WALL record of KCD Software v23 ".job" files, and the
"apply remeasure" command that sets wall lengths in a job (notes section 14).

Built from three independent decodes (bytewise / topology / diffpairs) and re-verified on all 178 wall
records of the ten job sets (22 jobs: 120 live walls, 58 dead records); experiments/walls_selftest.py
re-runs that check.  Files written by this module have NOT yet been round-tripped through KCD itself:
every output is a TEST file until the owner opens it in KCD and saves it back (notes section 14).

Public API
----------
    parse_wall(rec: bytes) -> dict          every decoded field, raw (0.1 mm) and inches
    pack_wall(rec: bytes, **changes) -> bytes
                                            write length / height / angle / points / ids / colour back
    check_room(records) -> list[str]        consistency issues of one room's wall records
    rebuild_points(records, ...) -> dict    recompute P0..P3 of a room from L + angle + left/right
    resize_wall(rec, new_length, room_records, anchor='start', absorb_id=None, allow_absorb=True,
                units=None) -> dict         updated records that keep the room's polygon consistent,
                                            or raises ResizeError with a clear message
    job_walls(data) -> list of WallRec       the wall records of a .job with their file offsets
    set_wall_lengths(job_path, changes, out_path, ...) -> report
                                            patch wall lengths (and heights) in place and write a new .job
    apply_rem(job_path, rem_json_path, out_path, ...) -> report
                                            the same from a remeasure read-out JSON (room name + KCD wall number)

Units: raw integers are 0.1 mm, 254 raw = 1 inch.  T = 1143 raw = 4.5 in wall thickness.

Byte layout (offset: size type = meaning)        confidence
  0  16  preamble: on the FIRST record of a file Int32 38494, Int32 102|119|136, Int32 65..377,
         Int32 7646 (4433 in GODDARD design); on every other record bytes 0-10 = 0, byte 11 = 1,
         bytes 12-14 = 0, byte 15 = 0|1 flag (unknown; sticks with the record slot)   high(values)/low(meaning)
 16   4  float32  direction angle of START->END in degrees * 254 (0, 90, 180, 220, 270, 360 seen)  high
 20   4  Int32    L  nominal length (0.1 mm); units are laid out against this                       high
 24   4  Int32    thickness with side sign: -1143 (-4.5 in) on all live walls                        high
 28   4  Int32    H  wall height (0.1 mm); per wall (BINDLER design has 2 heights in one room)       high
 32   4  u8 x3+0  colour bytes R,G,B,0 : e1e1e1 grey, fcfcfc white (PRIEM), 000000 unused            high
 36   4  Int32    left_id : wall whose END meets this wall's START (P0); 0 = open                    high
 40   4  Int32    right_id: wall whose START meets this wall's END (P1); 0 = open                    high
 44   2  Int16    0 always                                                                           medium
 46   2  Int16    3048 = 12.000 in  constant (kept on delete; meaning unknown, maybe default depth)  high/low
 48   2  Int16    6096 = 24.000 in  constant (kept on delete; meaning unknown)                       high/low
 50   8  2xInt32  P0 = START point of the room-side (inner) face  (x@50, y@54)                       high
 58   8  2xInt32  P1 = END point of the inner face = P0 + L*d      (x@58, y@62)                       high
 66   8  2xInt32  P2 = outer corner at END  = P1 + T*n + T*tan(turn_next/2)*d                        high
 74   8  2xInt32  P3 = outer corner at START= P0 + T*n - T*tan(turn_prev/2)*d                        high
 82   4  Int32    4 = number of outline points (set even on blank records)                           high
 86  10  bytes    0 always                                                                           medium
 96   4  Int32    copy of H                                                                          high
100   4  Int32    copy of L                                                                          high
104   4  Int32    copy of H                                                                          high
108   4  Int32    copy of L                                                                          high
112   5  bytes    0 always                                                                           medium
117   8  4xInt16  wall id, four copies (117, 119, 121, 123)                                          high
125   4  Int32    wall id                                                                            high
129   4  Int32    room number, 0 = deleted / unused record                                            high
133  24  3xf64    colour as R/255, G/255, B/255 (0.0 on 30 live walls: not kept in sync)             high
157  48  6xf64    0.0, 0.001, 0.81, 0.02, 0.02, 27.5 (render/material constants)                     high/low
"""
import math
import re
import struct
import sys

RECORD_SIZE = 205
IN = 254                 # 0.1 mm per inch
T = 1143                 # wall thickness, 0.1 mm (4.5 in)
DEG_SCALE = 254.0        # float32@16 is degrees * 254

# ----------------------------------------------------------------------------- low level
_i32 = struct.Struct('<i')
_i16 = struct.Struct('<h')
_f32 = struct.Struct('<f')
_f64 = struct.Struct('<d')


def i32(b, o): return _i32.unpack_from(b, o)[0]
def i16(b, o): return _i16.unpack_from(b, o)[0]
def f32(b, o): return _f32.unpack_from(b, o)[0]
def f64(b, o): return _f64.unpack_from(b, o)[0]


def inches(raw):
    """raw 0.1 mm -> inches (float)."""
    return raw / IN


def frac_inches(raw, denom=16):
    """raw -> string like 162 5/8 (nearest 1/denom in)."""
    v = raw / IN
    sign = '-' if v < 0 else ''
    v = abs(v)
    whole = int(v)
    n = round((v - whole) * denom)
    if n == denom:
        whole += 1; n = 0
    if n == 0:
        return f"{sign}{whole}"
    g = math.gcd(n, denom)
    return f"{sign}{whole} {n // g}/{denom // g}".strip()


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def unit_vectors(angle_deg):
    """d = direction START->END, n = right-hand normal (the side the wall body / outer face is on)."""
    a = math.radians(angle_deg)
    d = (math.cos(a), math.sin(a))
    n = (d[1], -d[0])
    return d, n


# ----------------------------------------------------------------------------- parse
def parse_wall(rec):
    """Decode one 205-byte wall record into a dict (raw values + inches + derived geometry)."""
    if len(rec) != RECORD_SIZE:
        raise ValueError(f"wall record must be {RECORD_SIZE} bytes, got {len(rec)}")
    b = bytes(rec)
    pts = [(i32(b, 50 + 8 * k), i32(b, 54 + 8 * k)) for k in range(4)]
    angle_raw = f32(b, 16)
    angle = angle_raw / DEG_SCALE
    L = i32(b, 20)
    H = i32(b, 28)
    room = i32(b, 129)
    d, n = unit_vectors(angle)
    dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
    span = math.hypot(dx, dy)
    first_record = b[0:2] == b'\x5e\x96'
    out = {
        # --- preamble
        'preamble_hex': b[0:16].hex(),
        'is_first_record': first_record,
        'list_header': (i32(b, 0), i32(b, 4), i32(b, 8), i32(b, 12)) if first_record else None,
        'byte11': b[11],
        'flag15': b[15],
        # --- geometry block 16..112
        'angle_raw': angle_raw,            # float32, degrees*254 as stored (360 may appear instead of 0)
        'angle_deg': angle,
        'angle_deg_norm': angle % 360.0,
        'length_raw': L, 'length_in': inches(L), 'length_frac': frac_inches(L),
        'thickness_raw': i32(b, 24), 'thickness_in': inches(i32(b, 24)),
        'height_raw': H, 'height_in': inches(H), 'height_frac': frac_inches(H),
        'colour_rgb': (b[32], b[33], b[34]), 'colour_hex': b[32:35].hex(), 'byte35': b[35],
        'left_id': i32(b, 36),             # wall meeting the START (P0)
        'right_id': i32(b, 40),            # wall meeting the END (P1)
        'i16_44': i16(b, 44),
        'i16_46_raw': i16(b, 46), 'i16_46_in': inches(i16(b, 46)),   # 3048 = 12 in constant
        'i16_48_raw': i16(b, 48), 'i16_48_in': inches(i16(b, 48)),   # 6096 = 24 in constant
        'P0': pts[0], 'P1': pts[1], 'P2': pts[2], 'P3': pts[3],
        'P0_in': (inches(pts[0][0]), inches(pts[0][1])),
        'P1_in': (inches(pts[1][0]), inches(pts[1][1])),
        'P2_in': (inches(pts[2][0]), inches(pts[2][1])),
        'P3_in': (inches(pts[3][0]), inches(pts[3][1])),
        'npts': i32(b, 82),
        'zero_86_95': b[86:96],
        'height_copy_96': i32(b, 96), 'length_copy_100': i32(b, 100),
        'height_copy_104': i32(b, 104), 'length_copy_108': i32(b, 108),
        'zero_112_116': b[112:117],
        # --- identity
        'id16': tuple(i16(b, o) for o in (117, 119, 121, 123)),
        'id': i32(b, 125),
        'room': room,
        'is_live': room != 0,
        # --- material tail
        'colour_f64': (f64(b, 133), f64(b, 141), f64(b, 149)),
        'consts_f64': tuple(f64(b, o) for o in (157, 165, 173, 181, 189, 197)),
        # --- derived
        'dir': d, 'normal_right': n,
        'span_raw': span,                               # |P1-P0|
        'span_minus_length': span - L,
        'vec_error': (dx - L * d[0], dy - L * d[1]),    # P1-P0 minus L*d
        'angle_from_points': (math.degrees(math.atan2(dy, dx)) % 360.0) if (dx or dy) else None,
    }
    return out


# ----------------------------------------------------------------------------- pack
def pack_wall(rec, **changes):
    """Return a copy of rec with the given fields written.  Accepted keys:
         length (raw)        -> @20, @100, @108
         height (raw)        -> @28, @96, @104
         angle_deg           -> float32 @16 = deg*254
         thickness (raw)     -> @24
         left_id, right_id   -> @36, @40
         P0, P1, P2, P3      -> (x,y) raw int tuples @50.., @58.., @66.., @74..
         id                  -> @117,@119,@121,@123 (Int16) and @125 (Int32)
         room                -> @129
         colour_rgb          -> bytes 32-34 and the three f64 at 133/141/149 (R/255 ...)
         flag15              -> byte 15
    """
    b = bytearray(rec)
    if len(b) != RECORD_SIZE:
        raise ValueError("bad record size")
    for k, v in changes.items():
        if k == 'length':
            for o in (20, 100, 108): _i32.pack_into(b, o, int(v))
        elif k == 'height':
            for o in (28, 96, 104): _i32.pack_into(b, o, int(v))
        elif k == 'angle_deg':
            _f32.pack_into(b, 16, float(v) * DEG_SCALE)
        elif k == 'thickness':
            _i32.pack_into(b, 24, int(v))
        elif k == 'left_id':
            _i32.pack_into(b, 36, int(v))
        elif k == 'right_id':
            _i32.pack_into(b, 40, int(v))
        elif k in ('P0', 'P1', 'P2', 'P3'):
            o = 50 + 8 * int(k[1])
            _i32.pack_into(b, o, int(round(v[0]))); _i32.pack_into(b, o + 4, int(round(v[1])))
        elif k == 'id':
            for o in (117, 119, 121, 123): _i16.pack_into(b, o, int(v))
            _i32.pack_into(b, 125, int(v))
        elif k == 'room':
            _i32.pack_into(b, 129, int(v))
        elif k == 'colour_rgb':
            b[32], b[33], b[34], b[35] = int(v[0]), int(v[1]), int(v[2]), 0
            for o, c in zip((133, 141, 149), v): _f64.pack_into(b, o, c / 255.0)
        elif k == 'flag15':
            b[15] = int(v)
        else:
            raise KeyError(f"pack_wall: unknown field {k!r}")
    return bytes(b)


# ----------------------------------------------------------------------------- room geometry
def _room_index(records):
    """records: iterable of 205-byte records (or parsed dicts).  Returns {id: (bytes, parsed)}."""
    idx = {}
    for r in records:
        p = r if isinstance(r, dict) else parse_wall(r)
        raw = p.get('_raw') if isinstance(r, dict) else bytes(r)
        if isinstance(r, dict) and raw is None:
            raise ValueError("parsed dict without _raw bytes")
        p = dict(p); p['_raw'] = raw
        if p['id'] in idx:
            raise ValueError(f"duplicate wall id {p['id']}")
        idx[p['id']] = p
    return idx


def expected_outer(p, left, right):
    """Predicted P2, P3 of parsed wall p given parsed neighbours (None = open end)."""
    d, n = unit_vectors(p['angle_deg'])
    tn = wrap180(right['angle_deg'] - p['angle_deg']) if right else 0.0
    tp = wrap180(p['angle_deg'] - left['angle_deg']) if left else 0.0
    k2 = math.tan(math.radians(tn) / 2.0)
    k3 = math.tan(math.radians(tp) / 2.0)
    P1, P0 = p['P1'], p['P0']
    P2 = (P1[0] + T * n[0] + T * k2 * d[0], P1[1] + T * n[1] + T * k2 * d[1])
    P3 = (P0[0] + T * n[0] - T * k3 * d[0], P0[1] + T * n[1] - T * k3 * d[1])
    return P2, P3


def check_room(records, tol_len=2.5, tol_mitre=1.5):
    """Consistency checks on the live walls of ONE room.  Returns a list of issue strings (empty = OK)."""
    idx = _room_index(records)
    live = {i: p for i, p in idx.items() if p['is_live']}
    issues = []
    for i, p in sorted(live.items()):
        tag = f"wall {i}"
        if p['thickness_raw'] != -T: issues.append(f"{tag}: thickness {p['thickness_raw']} != -{T}")
        if p['npts'] != 4: issues.append(f"{tag}: npts {p['npts']} != 4")
        if not (p['length_copy_100'] == p['length_copy_108'] == p['length_raw']):
            issues.append(f"{tag}: length copies @100/@108 differ from @20")
        if not (p['height_copy_96'] == p['height_copy_104'] == p['height_raw']):
            issues.append(f"{tag}: height copies @96/@104 differ from @28")
        if set(p['id16']) != {p['id']}: issues.append(f"{tag}: Int16 id copies differ")
        ex = p['vec_error']
        if max(abs(ex[0]), abs(ex[1])) > tol_len:
            issues.append(f"{tag}: P1-P0 differs from L*d by ({ex[0]:+.1f},{ex[1]:+.1f}) raw (L={p['length_raw']}, |P1-P0|={p['span_raw']:.1f})")
        left = live.get(p['left_id']) if p['left_id'] else None
        right = live.get(p['right_id']) if p['right_id'] else None
        if p['left_id'] and left is None: issues.append(f"{tag}: left_id {p['left_id']} is not a live wall of this room")
        if p['right_id'] and right is None: issues.append(f"{tag}: right_id {p['right_id']} is not a live wall of this room")
        if left is not None:
            if left['P1'] != p['P0']: issues.append(f"{tag}: P0 {p['P0']} != P1 of left wall {left['id']} {left['P1']}")
            if left['P2'] != p['P3']: issues.append(f"{tag}: P3 {p['P3']} != P2 of left wall {left['id']} {left['P2']}")
            if left['right_id'] != p['id']: issues.append(f"{tag}: left wall {left['id']} does not point back (right_id={left['right_id']})")
        if right is not None:
            if right['P0'] != p['P1']: issues.append(f"{tag}: P1 {p['P1']} != P0 of right wall {right['id']} {right['P0']}")
            if right['left_id'] != p['id']: issues.append(f"{tag}: right wall {right['id']} does not point back (left_id={right['left_id']})")
        e2, e3 = expected_outer(p, left, right)
        err = max(math.hypot(e2[0] - p['P2'][0], e2[1] - p['P2'][1]), math.hypot(e3[0] - p['P3'][0], e3[1] - p['P3'][1]))
        if err > tol_mitre: issues.append(f"{tag}: outer corners off the mitre formula by {err:.2f} raw (P2={p['P2']} exp {tuple(round(v,1) for v in e2)}, P3={p['P3']} exp {tuple(round(v,1) for v in e3)})")
    return issues


def chain_from(idx, start_id, direction='right'):
    """Follow right_id (or left_id) from start_id over live walls.  Returns (chain_ids, closed)."""
    key = 'right_id' if direction == 'right' else 'left_id'
    chain = []
    cur = start_id
    seen = set()
    while cur and cur not in seen:
        seen.add(cur); chain.append(cur)
        nxt = idx[cur][key]
        if nxt == start_id:
            return chain, True
        if nxt and nxt not in idx:
            raise KeyError(f"wall {cur} points to wall {nxt} which is not among the supplied room records")
        cur = nxt
    return chain, False


def room_chains(records):
    """Split the live walls of a room into ordered chains [(ids, closed), ...] following right_id."""
    idx = {i: p for i, p in _room_index(records).items() if p['is_live']}
    out = []; used = set()
    # open chains start at a wall with left_id == 0
    for i, p in sorted(idx.items()):
        if p['left_id'] == 0 and i not in used:
            ch, closed = chain_from(idx, i)
            out.append((ch, closed)); used.update(ch)
    for i in sorted(idx):
        if i not in used:
            ch, closed = chain_from(idx, i)
            out.append((ch, closed)); used.update(ch)
    return out


def rebuild_points(records, anchor_id=None):
    """Recompute P0..P3 of every live wall of a room from L, angle, left/right only.
    The anchor wall keeps its stored P0 (default: first wall of each chain).  Returns {id: new_bytes}."""
    idx = {i: p for i, p in _room_index(records).items() if p['is_live']}
    new = {}
    for ch, closed in room_chains(records):
        a0 = anchor_id if (anchor_id in ch) else ch[0]
        # rotate chain so it starts at the anchor
        k = ch.index(a0); order = ch[k:] + ch[:k] if closed else ch
        if not closed and a0 != ch[0]:
            raise ValueError("anchor of an open chain must be its first wall (left_id == 0)")
        P = idx[a0]['P0']
        pts = {}
        for wid in order:
            p = idx[wid]; d, n = unit_vectors(p['angle_deg'])
            P1 = (P[0] + p['length_raw'] * d[0], P[1] + p['length_raw'] * d[1])
            pts[wid] = [P, P1]
            P = P1
        for wid in order:
            p = idx[wid]
            left = idx.get(p['left_id']) if p['left_id'] else None
            right = idx.get(p['right_id']) if p['right_id'] else None
            q = dict(p); q['P0'] = pts[wid][0]; q['P1'] = pts[wid][1]
            P2, P3 = expected_outer(q, left, right)
            r = lambda v: (int(round(v[0])), int(round(v[1])))
            new[wid] = pack_wall(p['_raw'], P0=r(q['P0']), P1=r(q['P1']), P2=r(P2), P3=r(P3))
    return new


# ----------------------------------------------------------------------------- resize
class ResizeError(Exception):
    pass


def _translate(p, v):
    return pack_wall(p['_raw'], **{k: (p[k][0] + v[0], p[k][1] + v[1]) for k in ('P0', 'P1', 'P2', 'P3')})


def resize_wall(rec, new_length, room_records, anchor='start', absorb_id=None, allow_absorb=True, units=None):
    """Change the length of one wall and return every record that must change with it.

    rec           the 205-byte record of the wall to resize
    new_length    new nominal length in raw 0.1 mm (use round(inches*254))
    room_records  all other wall records of the same room (bytes); dead records are ignored
    anchor        'start': P0 stays, the END (P1) moves and every wall downstream along right_id
                           is translated by the same vector
                  'end'  : P1 stays, the START moves and every wall upstream along left_id is translated;
                           units on this wall then need X += dL to stay where they are
    absorb_id     for a CLOSED loop: id of the wall that takes the opposite change (must be antiparallel).
                  Default: the first antiparallel wall found along the chain.
    allow_absorb  False -> refuse to touch a closed loop (raise instead of changing a second wall)
    units         optional list of dicts with 'wall', 'x_raw', 'w_raw' (and 'name') to produce
                  overhang warnings; unit records themselves are NOT rewritten here.

    Returns dict:
      updated      {wall_id: new_bytes} for every changed wall (the resized wall included)
      translation  (vx, vy) raw vector applied to the moved end / chain
      absorbed_by  id of the wall whose length changed by the same dL (closed loop), else None
      unit_x_shift {wall_id: dX} X correction units on that wall need to stay physically in place
      warnings     list of strings
    Raises ResizeError when the request cannot be satisfied consistently.
    """
    k = parse_wall(rec); k['_raw'] = bytes(rec)
    if not k['is_live']:
        raise ResizeError(f"wall {k['id']} is not live (room = 0)")
    new_length = int(new_length)
    if new_length <= 0:
        raise ResizeError("new length must be positive")
    idx = {i: p for i, p in _room_index(list(room_records)).items() if p['is_live']}
    if k['id'] in idx:
        raise ResizeError(f"wall {k['id']} appears in room_records too; pass only the OTHER walls")
    idx[k['id']] = k
    pre = check_room([p['_raw'] for p in idx.values()])
    hard = [s for s in pre if 'not a live wall' in s or 'does not point back' in s or '!= P' in s]
    if hard:
        raise ResizeError("room is inconsistent before the edit:\n  " + "\n  ".join(hard))
    dL = new_length - k['length_raw']
    d, n = unit_vectors(k['angle_deg'])
    v = (int(round(dL * d[0])), int(round(dL * d[1])))          # displacement of the moving END
    warnings = []
    if abs(dL * d[0] - v[0]) > 1e-9 or abs(dL * d[1] - v[1]) > 1e-9:
        warnings.append(f"non-axis wall ({k['angle_deg']:.1f} deg): displacement rounded to {v}; |P1-P0| will differ from L by <= 0.71 raw")
    updated = {}
    unit_shift = {}
    absorbed = None
    if dL == 0:
        return {'updated': {}, 'translation': (0, 0), 'absorbed_by': None, 'unit_x_shift': {}, 'warnings': ['length unchanged']}

    if anchor == 'start':
        chain, closed = chain_from(idx, k['id'], 'right')      # chain[0] == k
        down = chain[1:]
        if closed:
            if not allow_absorb:
                raise ResizeError(f"wall {k['id']} is part of a closed loop {chain}: changing its length alone cannot keep the polygon closed (allow_absorb=False)")
            cands = [i for i in down if abs(abs(wrap180(idx[i]['angle_deg'] - k['angle_deg'])) - 180.0) < 1e-6]
            if absorb_id is not None:
                if absorb_id not in cands:
                    raise ResizeError(f"absorb_id {absorb_id} is not an antiparallel wall of the loop; candidates: {cands}")
                m = absorb_id
            elif cands:
                m = cands[0]
            else:
                raise ResizeError(f"closed loop {chain} has no wall antiparallel to wall {k['id']} ({k['angle_deg']:.1f} deg); "
                                  "the room cannot be kept closed by changing lengths alone (angles would have to change)")
            absorbed = m
            between = down[:down.index(m)]
            for i in between:
                updated[i] = _translate(idx[i], v)
            pm = idx[m]
            updated[m] = pack_wall(pm['_raw'], length=pm['length_raw'] + dL,
                                   P0=(pm['P0'][0] + v[0], pm['P0'][1] + v[1]), P3=(pm['P3'][0] + v[0], pm['P3'][1] + v[1]))
            unit_shift[m] = dL      # m's START moved; its units keep X from the start
            if pm['length_raw'] + dL <= 0:
                raise ResizeError(f"absorbing wall {m} would get length {pm['length_raw'] + dL} <= 0")
        else:
            for i in down:
                updated[i] = _translate(idx[i], v)
        updated[k['id']] = pack_wall(k['_raw'], length=new_length,
                                     P1=(k['P1'][0] + v[0], k['P1'][1] + v[1]), P2=(k['P2'][0] + v[0], k['P2'][1] + v[1]))
    elif anchor == 'end':
        chain, closed = chain_from(idx, k['id'], 'left')
        up = chain[1:]
        w = (-v[0], -v[1])                                       # displacement of the moving START
        if closed:
            if not allow_absorb:
                raise ResizeError(f"wall {k['id']} is part of a closed loop {chain}: changing its length alone cannot keep the polygon closed (allow_absorb=False)")
            cands = [i for i in up if abs(abs(wrap180(idx[i]['angle_deg'] - k['angle_deg'])) - 180.0) < 1e-6]
            if absorb_id is not None:
                if absorb_id not in cands:
                    raise ResizeError(f"absorb_id {absorb_id} is not an antiparallel wall of the loop; candidates: {cands}")
                m = absorb_id
            elif cands:
                m = cands[0]
            else:
                raise ResizeError(f"closed loop {chain} has no wall antiparallel to wall {k['id']}; cannot stay closed by changing lengths alone")
            absorbed = m
            for i in up[:up.index(m)]:
                updated[i] = _translate(idx[i], w)
            pm = idx[m]
            if pm['length_raw'] + dL <= 0:
                raise ResizeError(f"absorbing wall {m} would get length {pm['length_raw'] + dL} <= 0")
            updated[m] = pack_wall(pm['_raw'], length=pm['length_raw'] + dL,
                                   P1=(pm['P1'][0] + w[0], pm['P1'][1] + w[1]), P2=(pm['P2'][0] + w[0], pm['P2'][1] + w[1]))
        else:
            for i in up:
                updated[i] = _translate(idx[i], w)
        updated[k['id']] = pack_wall(k['_raw'], length=new_length,
                                     P0=(k['P0'][0] + w[0], k['P0'][1] + w[1]), P3=(k['P3'][0] + w[0], k['P3'][1] + w[1]))
        unit_shift[k['id']] = dL
    else:
        raise ResizeError("anchor must be 'start' or 'end'")

    # post-check
    after = {i: (updated.get(i) or p['_raw']) for i, p in idx.items()}
    post = check_room(list(after.values()))
    hard = [s for s in post if 'not a live wall' in s or 'does not point back' in s or '!= P' in s]
    if hard:
        raise ResizeError("internal error: room inconsistent after edit:\n  " + "\n  ".join(hard))
    # unit warnings
    if units:
        for u in units:
            wid = u.get('wall')
            if wid not in after: continue
            Lnew = parse_wall(after[wid])['length_raw']
            x = u['x_raw'] + unit_shift.get(wid, 0)
            if x + u['w_raw'] > Lnew + 1:
                warnings.append(f"unit {u.get('name', '?')!r} on wall {wid}: X+W = {x + u['w_raw']} > new L {Lnew} ({frac_inches(x + u['w_raw'] - Lnew)} in overhang)")
            if x < 0:
                warnings.append(f"unit {u.get('name', '?')!r} on wall {wid}: X = {x} < 0")
    if unit_shift:
        warnings.append("units on walls " + str(sorted(unit_shift)) + " need X += dL (" + ", ".join(f"{i}:{s:+d}" for i, s in unit_shift.items()) + ") to stay physically in place; unit records are not rewritten here")
    return {'updated': updated, 'translation': v, 'absorbed_by': absorbed, 'unit_x_shift': unit_shift, 'warnings': warnings}




# =============================================================================== job files
# Everything below works on a whole .job: it finds the wall records with kcdjob, changes them in place
# (same size, so no other offset in the file moves) and writes a new file next to a plain-English report.
import os
import json
import collections

try:
    import kcdjob
    import kcdunits
except ImportError:                       # imported from another folder
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kcdjob
    import kcdunits

TOL_PRINTED = IN // 32                    # 1/32": the printed length on the remeasure must match the file this closely

WallRec = collections.namedtuple('WallRec', 'offset raw parsed')


def job_walls(data):
    """All wall records of a .job (live and dead) with their byte offset, in file order."""
    secs = kcdjob.parse(data)
    for name, start, end, info in secs:
        if name == 'walls':
            return [WallRec(w['start'], bytes(data[w['start']:w['start'] + RECORD_SIZE]),
                            parse_wall(data[w['start']:w['start'] + RECORD_SIZE])) for w in info['list']]
    raise ValueError('no walls section in this job')


def room_names(data):
    """{room number: name} from the rooms section."""
    for name, start, end, info in kcdjob.parse(data):
        if name == 'rooms':
            return {i + 1: kcdunits.txt(r['name']) if hasattr(kcdunits, 'txt') else r['name'] for i, r in enumerate(info['list'])}
    return {}


def units_by_wall(job_path):
    """{wall id: [unit dicts]} from kcdunits (X and W raw, name, cab); empty when the reader cannot load it."""
    out = collections.defaultdict(list)
    try:
        job = kcdunits.read_job(job_path, None)
    except Exception as e:                                           # the wall edit must not depend on the unit reader
        return out, 'unit reader failed: %s' % e
    for u in job.units:
        out[u.wall].append({'wall': u.wall, 'seq': u.seq, 'id': u.id, 'name': u.kcd_name or u.cab, 'cab': u.cab,
                            'x_raw': u.raw(1), 'w_raw': u.raw(2), 'd_raw': u.raw(4)})
    for lst in out.values():
        lst.sort(key=lambda d: d['x_raw'])
    return out, None


def set_wall_lengths(job_path, changes, out_path, anchor='start', heights=None, allow_absorb=True):
    """Change wall lengths (and optionally wall heights) in a .job and write out_path.

    changes   {wall id: new length in raw 0.1 mm}  (use round(inches * 254))
    heights   {room number: new wall height raw} applied to every live wall of that room, or
              {('wall', id): raw} for one wall
    Returns a dict: 'lines' (plain-English report lines), 'checks' (things the engineer must look at),
    'changed_walls' (ids whose record changed), 'written' (out_path or None).
    The edit is in place: the file keeps its size, every other section is byte for byte the original.
    """
    data = bytearray(open(job_path, 'rb').read())
    original = bytes(data)
    names = room_names(original)
    units, uerr = units_by_wall(job_path)
    lines, checks, changed = [], [], set()
    if uerr:
        checks.append('CHECK units could not be read (%s): no overhang check was done' % uerr)
    recs = job_walls(data)
    by_id = {r.parsed['id']: r for r in recs}

    def room_records(room, exclude_id):
        return [r.raw for r in job_walls(data) if r.parsed['room'] == room and r.parsed['id'] != exclude_id]

    for wid, new_len in sorted(changes.items()):
        r = by_id.get(wid)
        if r is None:
            checks.append('CHECK wall %d is not in this job; nothing changed for it' % wid); continue
        p = r.parsed
        if not p['is_live']:
            checks.append('CHECK wall %d is a deleted wall (room 0); nothing changed for it' % wid); continue
        rn = names.get(p['room'], '')
        if new_len == p['length_raw']:
            lines.append('wall %d (%s): already %s, no change' % (wid, rn, frac_inches(new_len))); continue
        ulist = [u for lst in units.values() for u in lst if u['wall'] in {w.parsed['id'] for w in recs if w.parsed['room'] == p['room']}]
        try:
            res = resize_wall(r.raw, new_len, room_records(p['room'], wid), anchor=anchor, allow_absorb=allow_absorb, units=ulist)
        except ResizeError as e:
            checks.append('CHECK wall %d (%s) %s -> %s was NOT changed: %s' % (wid, rn, frac_inches(p['length_raw']), frac_inches(new_len), e))
            continue
        for cid, nb in res['updated'].items():
            off = by_id[cid].offset
            data[off:off + RECORD_SIZE] = nb
            changed.add(cid)
        recs = job_walls(data); by_id = {x.parsed['id']: x for x in recs}
        moved = sorted(i for i in res['updated'] if i != wid)
        dL = new_len - p['length_raw']
        lines.append('wall %d (%s): %s -> %s (%s%s)%s' % (
            wid, rn, frac_inches(p['length_raw']), frac_inches(new_len), '+' if dL > 0 else '-', frac_inches(abs(dL)),
            ('; walls %s moved with it' % moved) if moved else ''))
        if res['absorbed_by']:
            lines.append('   closed room: wall %d changed by the same amount so the room stays closed' % res['absorbed_by'])
        for w in res['warnings']:
            if w.startswith('unit '):
                m = re.match(r"unit (.+?) on wall (\d+): (.*)$", w)
                c = 'CHECK wall %s: %s %s' % (m.group(2), m.group(1), m.group(3)) if m else 'CHECK ' + w
                if c not in checks:                     # the same unit is seen again when a later wall of the room moves
                    checks.append(c)
            elif w != 'length unchanged':
                lines.append('   note: ' + w)
        # units that end exactly at the old wall end are the sections the engineer will shrink or grow
        ends = [u for u in units.get(wid, []) if abs(u['x_raw'] + u['w_raw'] - p['length_raw']) <= IN // 16]
        for u in ends:
            c = ('CHECK wall %d: %r ends at the old wall end (X %s, W %s); it needs %s%s to fit the new length'
                 % (wid, u['name'], frac_inches(u['x_raw']), frac_inches(u['w_raw']), '+' if dL > 0 else '-', frac_inches(abs(dL))))
            checks[:] = [x for x in checks if not (x.startswith('CHECK wall %d: %r X+W' % (wid, u['name'])))] + [c]
        if not units.get(wid):
            lines.append('   no units on this wall')
    # heights
    for key, h in (heights or {}).items():
        targets = []
        if isinstance(key, tuple) and key[0] == 'wall':
            targets = [key[1]]
        else:
            targets = [x.parsed['id'] for x in recs if x.parsed['room'] == key and x.parsed['is_live']]
        for wid in targets:
            r = by_id.get(wid)
            if r is None or not r.parsed['is_live']:
                checks.append('CHECK height: wall %s not live; skipped' % (wid,)); continue
            if r.parsed['height_raw'] == h:
                continue
            data[r.offset:r.offset + RECORD_SIZE] = pack_wall(r.raw, height=h)
            changed.add(wid)
            lines.append('wall %d (%s): height %s -> %s' % (wid, names.get(r.parsed['room'], ''), frac_inches(r.parsed['height_raw']), frac_inches(h)))
        recs = job_walls(data); by_id = {x.parsed['id']: x for x in recs}
    # final checks: every room still consistent, nothing but wall records changed
    for room in sorted({x.parsed['room'] for x in recs if x.parsed['is_live']}):
        issues = check_room([x.raw for x in recs if x.parsed['room'] == room])
        hard = [s for s in issues if 'does not point back' in s or '!= P' in s]
        for s in hard:
            checks.append('CHECK room %d after the edit: %s' % (room, s))
    diff_outside = [i for i in range(len(data)) if data[i] != original[i] and not any(r.offset <= i < r.offset + RECORD_SIZE for r in recs)]
    if diff_outside:
        raise RuntimeError('internal error: bytes outside the wall records changed')
    written = None
    if changed and out_path:
        if os.path.abspath(out_path) == os.path.abspath(job_path):
            raise ValueError('refusing to overwrite the input job; give another output name')
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        open(out_path, 'wb').write(bytes(data))
        written = out_path
        # read back
        back = open(out_path, 'rb').read()
        if back != bytes(data) or len(back) != len(original):
            raise RuntimeError('internal error: the written file does not read back')
    return {'lines': lines, 'checks': checks, 'changed_walls': sorted(changed), 'written': written,
            'mesh_note': 'The 3-D cache and the print pages in the file are not rebuilt; KCD redraws them when it opens the job.'}


# --------------------------------------------------------------------------- remeasure read-out JSON
WALL_LABEL = re.compile(r'^(?P<room>.+?)\s+#\s*(?P<wall>\d+)\s*(?:\(printed\s+(?P<printed>[^)]+)\))?\s*$', re.I)
FACT_LABEL = re.compile(r'^(?P<room>.+?)\s+(?P<key>H|HO|HD|BB|F|Door|Molding|HOLES)\s*$', re.I)


def parse_inches(text):
    """'25 1/8' -> 25.125, '95' -> 95.0, '0"' -> 0.0; None when the text is not a plain length."""
    t = str(text).strip().replace('"', '').strip()
    m = re.match(r'^(?:(\d+)\s+)?(\d+)/(\d+)$', t)
    if m:
        return int(m.group(1) or 0) + int(m.group(2)) / int(m.group(3))
    m = re.match(r'^(\d+)(?:\.(\d+))?$', t)
    if m:
        return float(t)
    return None


def read_rem_json(path):
    """The Grok read-out: agreed wall lengths, walls held for review, room facts, and lines it could not use."""
    d = json.load(open(path, encoding='utf-8'))
    walls, review, facts, skipped = [], [], [], []
    for item in d.get('consensus', []):
        lab, val = item.get('label', ''), item.get('value', '')
        m = WALL_LABEL.match(lab)
        if m:
            v = parse_inches(val)
            if v is None:
                skipped.append('%s = %s (value is not a length)' % (lab, val)); continue
            walls.append({'room': m.group('room').strip(), 'wall': int(m.group('wall')),
                          'printed_in': parse_inches(m.group('printed')) if m.group('printed') else None,
                          'measured_in': v, 'label': lab})
            continue
        f = FACT_LABEL.match(lab)
        if f:
            facts.append({'room': f.group('room').strip(), 'key': f.group('key').upper(), 'value': val, 'label': lab})
        else:
            skipped.append('%s = %s' % (lab, val))
    for item in d.get('needs_review', []):
        m = WALL_LABEL.match(item.get('label', ''))
        if m:
            review.append({'room': m.group('room').strip(), 'wall': int(m.group('wall')),
                           'possible': item.get('possible_values', []), 'reason': item.get('reason', ''), 'label': item['label']})
    return {'job': d.get('job'), 'walls': walls, 'walls_review': review, 'facts': facts, 'skipped': skipped}


def apply_rem(job_path, rem_path, out_path, anchor='start', allow_absorb=True):
    """Set the agreed wall lengths of a remeasure read-out in the job. Each agreed wall must exist, must sit in
    the room the label names, and (when the label carries the printed length) the printed length must equal
    the file's length within 1/32"; otherwise it is flagged and left alone. Review items are never applied."""
    rem = read_rem_json(rem_path)
    data = open(job_path, 'rb').read()
    names = {k: v.strip().lower() for k, v in room_names(data).items()}
    by_id = {r.parsed['id']: r.parsed for r in job_walls(data)}
    changes, pre, checks = {}, [], []
    for w in rem['walls']:
        p = by_id.get(w['wall'])
        tag = '%s #%d' % (w['room'], w['wall'])
        if p is None or not p['is_live']:
            checks.append('CHECK %s: measured %s, but the job has no live wall %d' % (tag, frac_inches(round(w['measured_in'] * IN)), w['wall'])); continue
        jr = names.get(p['room'], '')
        if jr and w['room'].lower() not in jr and jr not in w['room'].lower():
            checks.append('CHECK %s: wall %d is in room %d %r in the job, not %r; not changed' % (tag, w['wall'], p['room'], jr, w['room'])); continue
        if w['printed_in'] is not None and abs(round(w['printed_in'] * IN) - p['length_raw']) > TOL_PRINTED:
            checks.append('CHECK %s: the remeasure sheet was printed from a file where this wall was %s, the job has %s; not changed (wrong file version?)'
                          % (tag, frac_inches(round(w['printed_in'] * IN)), p['length_frac'])); continue
        if w['printed_in'] is None:
            pre.append('note %s: no printed length on the sheet; the job has %s' % (tag, p['length_frac']))
        changes[w['wall']] = int(round(w['measured_in'] * IN))
    for w in rem['walls_review']:
        p = by_id.get(w['wall'])
        checks.append('CHECK %s #%d: NOT applied, the readers did not agree: %s (%s); the job has %s'
                      % (w['room'], w['wall'], ' or '.join(w['possible']), w['reason'], p['length_frac'] if p else 'no such wall'))
    rep = set_wall_lengths(job_path, changes, out_path, anchor=anchor, allow_absorb=allow_absorb) if changes else {
        'lines': [], 'checks': [], 'changed_walls': [], 'written': None, 'mesh_note': ''}
    rep['lines'] = pre + rep['lines']
    rep['checks'] = checks + rep['checks']
    rep['facts'] = ['%s %s = %s' % (f['room'], f['key'], f['value']) for f in rem['facts']]
    rep['skipped'] = rem['skipped']
    rep['rem_job'] = rem['job']
    return rep


def format_report(rep, title):
    out = [title, '']
    out += rep['lines'] or ['(no wall changed)']
    if rep.get('checks'):
        out += ['', 'TO CHECK (%d):' % len(rep['checks'])] + ['  ' + c for c in rep['checks']]
    if rep.get('facts'):
        out += ['', 'Room facts from the remeasure (not applied to the job):'] + ['  ' + f for f in rep['facts']]
    if rep.get('skipped'):
        out += ['', 'Read-out lines not used (%d): ' % len(rep['skipped']) + '; '.join(rep['skipped'][:12]) + (' ...' if len(rep['skipped']) > 12 else '')]
    out += ['', 'Written: %s' % (rep['written'] or 'nothing'), rep.get('mesh_note', ''),
            'This is a TEST file until KCD has opened it and saved it back; compare the saved file with kcdcompare.py.']
    return '\n'.join(out)


def list_job(job_path):
    data = open(job_path, 'rb').read()
    names = room_names(data)
    units, uerr = units_by_wall(job_path)
    out = []
    for r in job_walls(data):
        p = r.parsed
        if not p['is_live']:
            continue
        out.append('wall %2d  room %d %-20s length %-10s angle %5.1f  height %-8s left %2d right %2d' % (
            p['id'], p['room'], names.get(p['room'], '')[:20], p['length_frac'], p['angle_deg_norm'], p['height_frac'], p['left_id'], p['right_id']))
        for u in units.get(p['id'], []):
            end = u['x_raw'] + u['w_raw']
            flag = '  <- ends at the wall end' if abs(end - p['length_raw']) <= IN // 16 else ('  <- past the wall end' if end > p['length_raw'] + IN // 16 else '')
            out.append('        %-28s X %-9s W %-9s ends %-9s%s' % (u['name'][:28], frac_inches(u['x_raw']), frac_inches(u['w_raw']), frac_inches(end), flag))
    if uerr:
        out.append('(units not listed: %s)' % uerr)
    return '\n'.join(out)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='KCD wall lengths: list them, or set them from a remeasure.')
    ap.add_argument('job')
    ap.add_argument('--list', action='store_true', help='list the live walls and the units on them')
    ap.add_argument('--set', action='append', default=[], metavar='WALL=INCHES', help='new length, e.g. --set 7=25.125 or --set "7=25 1/8"')
    ap.add_argument('--height', action='append', default=[], metavar='ROOM=INCHES', help='wall height for every wall of a room')
    ap.add_argument('--rem', help='remeasure read-out JSON (the Grok pipeline format)')
    ap.add_argument('--out', help='output .job (never the input)')
    ap.add_argument('--anchor', default='start', choices=['start', 'end'])
    ap.add_argument('--no-absorb', action='store_true', help='refuse to change a second wall of a closed room')
    a = ap.parse_args(argv)
    if a.list or not (a.set or a.height or a.rem):
        print(list_job(a.job)); return 0
    if a.rem:
        rep = apply_rem(a.job, a.rem, a.out, anchor=a.anchor, allow_absorb=not a.no_absorb)
        print(format_report(rep, 'Remeasure %s applied to %s' % (rep.get('rem_job'), os.path.basename(a.job))))
        return 0
    changes = {}
    for s in a.set:
        k, v = s.split('=', 1)
        inches_v = parse_inches(v)
        if inches_v is None:
            ap.error('bad length %r' % v)
        changes[int(k)] = int(round(inches_v * IN))
    heights = {}
    for s in a.height:
        k, v = s.split('=', 1)
        heights[int(k)] = int(round(parse_inches(v) * IN))
    rep = set_wall_lengths(a.job, changes, a.out, anchor=a.anchor, heights=heights, allow_absorb=not a.no_absorb)
    print(format_report(rep, 'Wall changes in %s' % os.path.basename(a.job)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
