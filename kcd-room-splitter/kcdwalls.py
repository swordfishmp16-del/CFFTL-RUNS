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
    Ld = (int(round(new_length * d[0])), int(round(new_length * d[1])))
    if anchor == 'start':                                        # the edited wall gets P1 = P0 + L*d exactly (KCD drops an old skew)
        P1n = (k['P0'][0] + Ld[0], k['P0'][1] + Ld[1])
        v = (P1n[0] - k['P1'][0], P1n[1] - k['P1'][1])          # displacement of the moving END
    else:
        P0n = (k['P1'][0] - Ld[0], k['P1'][1] - Ld[1])
        v = (k['P0'][0] - P0n[0], k['P0'][1] - P0n[1])          # minus the displacement of the moving START
    warnings = []
    skew = math.hypot(dL * d[0] - v[0], dL * d[1] - v[1])        # raw 0.1 mm: rounding, or an old skew in the drawing
    if skew > 10:
        warnings.append("skew: the designer's drawing had the %s of this wall %.1f mm off its length; it is now exactly on the length"
                        % ('end' if anchor == 'start' else 'start', skew / 10.0))
    updated = {}
    unit_shift = {}
    absorbed = None
    if anchor not in ('start', 'end'):
        raise ResizeError("anchor must be 'start' or 'end'")
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
                                     P1=P1n, P2=(k['P2'][0] + v[0], k['P2'][1] + v[1]))
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
                                     P0=P0n, P3=(k['P3'][0] + w[0], k['P3'][1] + w[1]))
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
        warnings.append("the START of walls " + str(sorted(unit_shift)) + " moved (" + ", ".join(f"{i}:{s:+d}" for i, s in unit_shift.items()) + "); units there keep their X, so they move with the start, as KCD does")
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
    import kcdmesh
except ImportError:                       # imported from another folder
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kcdjob
    import kcdunits
    import kcdmesh

TOL_PRINTED = IN // 32                    # 1/32": the printed length on the remeasure must match the file this closely
ANGLE_TOL_DEG = 1.0                     # a corner measured within this of the drawing is left as drawn
OPENING_TOL = IN // 8                   # a doorway opening that works out within 1/8" of the measured one is fine

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
                            'type': u.T, 'x_raw': u.raw(1), 'w_raw': u.raw(2), 'd_raw': u.raw(4),
                            'ls_raw': u.raw(5), 'rs_raw': u.raw(7)})
    for lst in out.values():
        lst.sort(key=lambda d: d['x_raw'])
    return out, None


# ----------------------------------------------------------------------------- units on the walls
# Owner's rule for the unit step (Oct 19, 2026, after the first COYNE test in KCD): fillers stay 3/4" wide;
# the cabinet against the end of the wall changes width; the units on the wall must add up to the wall length.
ACCESSORY_TYPES = {1000, 20}             # unit type code (Int16 at byte 64 of the 86-byte block): accessories,
                                         # obstructions, outlets (1000) and door/window openings (20) are not cabinets
DECOR_TYPES = {890}                      # show-only items (890nc baseboards): no price, the engineers remove them
SHELF_TYPES = {640, 641}                 # connecting shelves drawn inside a cabinet's opening (CLO-SH, Csetsh/CSTopandBottom)
TOL_END = IN // 16                       # a unit "ends at the wall end" within 1/16"
REACH = IN // 4                          # a cabinet "reaches" the end filler when it ends within 1/4" of the filler's start


def unit_index(data):
    """{unit id: {'start', 'f86_at', 'wall'}} for every live unit record (from kcdjob.parse)."""
    for name, start, end, info in kcdjob.parse(data):
        if name == 'units':
            return {u['id']: {'start': u['start'], 'f86_at': u['f86_at'], 'wall': u['wall']} for u in info['list'] if u['wall']}
    return {}


def is_filler(u):
    cab = (u.get('cab') or '').lower(); name = (u.get('name') or '').lower()
    return 'filler' in name or cab.startswith(('234', '231', '131'))


def is_cabinet(u):
    return u.get('type') not in ACCESSORY_TYPES and u.get('type') not in DECOR_TYPES


def is_decor(u):
    return u.get('type') in DECOR_TYPES


def snap16(raw):
    """Raw 0.1 mm to the nearest 1/16" (KCD keeps positions and sizes on that grid; 3/4" is 190, not 191)."""
    return int(round(round(raw / IN * 16) / 16.0 * IN))


def unit_xw(data, uinfo):
    return struct.unpack_from('<i', data, uinfo['start'] + 6)[0], struct.unpack_from('<i', data, uinfo['start'] + 12)[0]


def set_unit_xw(data, uinfo, x=None, w=None):
    """Write a unit's X (size slot 1) and/or W (slot 2 and the copy at byte 12 of the 86-byte block) in place.
    Only the Int32 values change; the state bytes stay. No stored size slot of the cabs seen so far depends on W
    (shelf and drawer widths are computed from W by KCD and by the price scripts), so nothing else is touched."""
    if x is not None:
        struct.pack_into('<i', data, uinfo['start'] + 6 * 1, int(x))
    if w is not None:
        struct.pack_into('<i', data, uinfo['start'] + 6 * 2, int(w))
        struct.pack_into('<i', data, uinfo['f86_at'] + 12, int(w))


def unit_points(data, uinfo):
    """The two room-coordinate points of the unit in its 86-byte block: A at byte 40, B at byte 52 (3 x Int32)."""
    f = uinfo['f86_at']
    return struct.unpack_from('<3i', data, f + 40), struct.unpack_from('<3i', data, f + 52)


def set_unit_points(data, uinfo, A, B):
    struct.pack_into('<3i', data, uinfo['f86_at'] + 40, *A)
    struct.pack_into('<3i', data, uinfo['f86_at'] + 52, *B)


def _along_depth(P, wall):
    d, n = unit_vectors(wall['angle_deg'])
    vx, vy = P[0] - wall['P0'][0], P[1] - wall['P0'][1]
    return vx * d[0] + vy * d[1], vx * n[0] + vy * n[1]


def moved_unit_points(A, B, wall_old, wall_new, x_old, w_old, x_new, w_new):
    """Where the unit's two room points go when its wall moved and/or its X or W changed.
    Measured on 30 COYNE units and KCD's own re-save: both points sit at X + W/2 along the wall (B also on the
    WERNER units), at a fixed distance from the wall (D/2, 3/4 D, From Wall + D/2 on fillers) and a fixed height.
    The distance from the wall and the height are kept; the place along the wall keeps the unit's own fraction
    of its width (1/2 on every unit seen). KCD recomputes these for cabinets when it opens the job but left
    fillers and accessories stale in the test-1 re-save, which is why units looked off the wall until each wall
    was opened and closed in KCD."""
    d, n = unit_vectors(wall_new['angle_deg'])
    out = []
    for P in (A, B):
        along, depth = _along_depth(P, wall_old)
        f = (along - x_old) / w_old if w_old else 0.5
        along_new = x_new + f * w_new
        out.append((int(round(wall_new['P0'][0] + along_new * d[0] + depth * n[0])),
                    int(round(wall_new['P0'][1] + along_new * d[1] + depth * n[1])), P[2]))
    return out[0], out[1]


def notes_on_walls(data):
    """{wall id: [(kind, text)]} for the notes attached to a wall (Int16 at byte 24 of the 30-byte note header;
    kind at byte 28: 4 text, 5 dimension string, 6 leader, 2 arrow). Dimension strings carry a measured length."""
    out = collections.defaultdict(list)
    for name, start, end, info in kcdjob.parse(data):
        if name == 'notes':
            for n in info['list']:
                wall = struct.unpack_from('<h', data, n['start'] + 24)[0]
                kind = struct.unpack_from('<h', data, n['start'] + 28)[0]
                if wall:
                    out[wall].append((kind, n['text'].decode('cp1252', 'replace') if isinstance(n['text'], bytes) else str(n['text'])))
    return out


def room_main_wall(records):
    """The wall KCD treats as the room's origin: the 0-degree wall that starts at (0,0) when there is one, else the
    lowest-numbered 0-degree wall, else the first wall of the first chain. In the ten engineered jobs this wall's
    START never moved when the engineers changed lengths (audit over 8 design/engineered pairs, Oct 2026)."""
    idx = {i: p for i, p in _room_index(records).items() if p['is_live']}
    zero = [i for i, p in sorted(idx.items()) if abs(wrap180(p['angle_deg'])) < 1e-6]
    at_origin = [i for i in zero if tuple(idx[i]['P0']) == (0, 0)]
    if at_origin:
        return at_origin[0]
    if zero:
        return zero[0]
    chains = room_chains(records)
    return chains[0][0][0] if chains else None


def auto_anchor(records, wid):
    """How the engineers (and KCD's wall dialog) change a wall: a wall upstream of the room's main wall (reached from it
    along left_id) moves its START ('end' anchor); the main wall and the walls downstream move their END ('start')."""
    idx = {i: p for i, p in _room_index(records).items() if p['is_live']}
    m = room_main_wall(records)
    if m is None or m == wid or wid not in idx:
        return 'start'
    up, closed = chain_from(idx, m, 'left')
    if closed:
        return 'start'
    return 'end' if wid in up[1:] else 'start'


WALL_FEATURE = re.compile(r'obstruction|outlet|switch|sprinkler|panel|vent|window|door|pipe|column|beam|soffit|thermostat|register', re.I)


def is_feature(u):
    """A thing of the room drawn on the wall (obstruction, outlet, switch, opening): it keeps its place in the room
    whatever the units do."""
    return u.get('type') == 20 or (not is_cabinet(u) and bool(WALL_FEATURE.search(u.get('name') or '')))


def unit_step(data, wid, rn, wall_old, wall_new, ulist, uidx, lines, checks, touched, anchor='start'):
    """Apply the owner's unit rule to one changed wall (Oct 19, 2026, after the COYNE tests): fillers keep their
    width; the cabinet against the wall end that moved changes width by the wall's change; the fillers at that
    end stay against it; every other unit stays where it is in the room. When that cabinet cannot change (a
    drawer unit, or it is unclear which unit it is) the cabinet against the OTHER end takes up the change and the
    whole run slides with the moved end instead (COYNE test 4, Guest wall 11, approved by the owner).
      anchor 'start': the END of the wall moved.   anchor 'end': the START moved.
    Units keep their X from the wall start, so "stays where it is in the room" means X + dL on a wall whose start
    moved and X unchanged on a wall whose end moved. A connecting shelf drawn across the moved end (into a corner)
    counts as the unit against that end and keeps its overhang. Obstructions, outlets and openings always keep
    their place in the room. Anything unclear is flagged and left alone. Records are patched in `data`; `touched`
    collects {unit id: (x_old, w_old, x_new, w_new)} for the room-point and 3-D cache update."""
    L_old, L_new = wall_old['length_raw'], wall_new['length_raw']
    dL = L_new - L_old
    if not ulist:
        return                                          # the caller says 'no units on this wall'
    M = 'start' if anchor == 'end' else 'end'           # the wall end that moved
    O = 'end' if M == 'start' else 'start'
    sdL = '%s%s' % ('+' if dL > 0 else '-', frac_inches(abs(dL)))
    keep = set()                                        # unit ids that never shift
    features = [u for u in ulist if is_feature(u)]
    keep.update(u['id'] for u in features)
    for u in ulist:
        if is_decor(u) and u['id'] in uidx:
            if abs(u['x_raw']) <= TOL_END and abs(u['x_raw'] + u['w_raw'] - L_old) <= TOL_END:
                set_unit_xw(data, uidx[u['id']], w=L_new)
                touched[u['id']] = (u['x_raw'], u['w_raw'], u['x_raw'], L_new)
                lines.append('   %r (unit %d, show-only item along the whole wall): %s -> %s wide' % (u['name'], u['id'], frac_inches(u['w_raw']), frac_inches(L_new)))
                u['w_raw'] = L_new
                keep.add(u['id'])
    cabs = sorted([u for u in ulist if is_cabinet(u)], key=lambda u: u['x_raw'])
    max_end = max((u['x_raw'] + u['w_raw'] for u in cabs), default=0)
    min_x = min((u['x_raw'] for u in cabs), default=0)

    def shift(units, why):
        """X + dL on these units (they keep their place in the room when the start moved, or slide with the end)."""
        for u in units:
            nx = u['x_raw'] + dL
            set_unit_xw(data, uidx[u['id']], x=nx)
            touched[u['id']] = (u['x_raw'], u['w_raw'], nx, u['w_raw'])
            u['x_raw'] = nx
        if units:
            lines.append('   %d unit(s) got X %s %s (%s)' % (len(units), sdL, why, ', '.join('%r X %s' % (u['name'], frac_inches(u['x_raw'])) for u in units)))

    def cannot_shift(units):
        bad = [u for u in units if u['x_raw'] + dL < -TOL_END]
        if bad:
            return '%s would land before the wall start' % ', '.join('%r (X %s)' % (u['name'], frac_inches(u['x_raw'])) for u in bad)
        missing = [u for u in units if u['id'] not in uidx]
        if missing:
            return 'the record of %s could not be located' % ', '.join(repr(u['name']) for u in missing)
        return None

    def edge_units(side):
        if side == 'start':
            return [u for u in cabs if u['x_raw'] <= TOL_END and u['x_raw'] + u['w_raw'] > TOL_END]
        return [u for u in cabs if u['x_raw'] < L_old - TOL_END and u['x_raw'] + u['w_raw'] >= L_old - TOL_END]

    def plan(S):
        """How the cabinet against wall end S takes up the change. Returns a dict, or a string saying why it cannot."""
        edge = edge_units(S)
        fill = [u for u in edge if is_filler(u)]
        cabe = [u for u in edge if not is_filler(u)]
        if cabe:
            if len(cabe) > 1:
                return '%d cabinets stand against the wall %s (%s)' % (len(cabe), S, ', '.join(repr(u['name']) for u in cabe))
            target = cabe[0]
        else:
            if S == 'start':
                fe = max(u['x_raw'] + u['w_raw'] for u in fill)
                cands = [u for u in cabs if not is_filler(u) and u['x_raw'] + u['w_raw'] > fe and u['x_raw'] <= fe + REACH]
                best = min((u['x_raw'] for u in cands), default=0)
                top = [u for u in cands if abs(u['x_raw'] - best) <= TOL_END]
            else:
                fx = min(u['x_raw'] for u in fill)
                cands = [u for u in cabs if not is_filler(u) and u['x_raw'] < fx and u['x_raw'] + u['w_raw'] >= fx - REACH]
                best = max((u['x_raw'] + u['w_raw'] for u in cands), default=0)
                top = [u for u in cands if abs(u['x_raw'] + u['w_raw'] - best) <= TOL_END]
            if not cands:
                return 'only the filler %r stands against the wall %s and no cabinet reaches it' % (fill[0]['name'], S)
            if len(top) > 1:
                return '%d units reach the %s filler (%s)' % (len(top), S, ', '.join(repr(u['name']) for u in top))
            target = top[0]
        if 'drawer' in (target['name'] or '').lower():
            return 'the cabinet at the wall %s is %r and drawer units keep their width (engineers\' rule)' % (S, target['name'])
        t0, t1 = target['x_raw'], target['x_raw'] + target['w_raw']
        inside = [u for u in cabs if u is not target and u not in fill and u['x_raw'] >= t0 - TOL_END and u['x_raw'] + u['w_raw'] <= t1 + TOL_END]
        # shelves drawn in the cabinet's opening run from the inside of its left panel to the inside of its right
        # panel, so they change with it; any other unit inside the cabinet is the engineer's call
        rs = target.get('rs_raw', 0)
        followers = [u for u in inside if u['type'] in SHELF_TYPES and abs((u['x_raw'] + u['w_raw']) - (t1 - rs)) <= TOL_END]
        others = [u for u in inside if u not in followers]
        if others:
            return '%r has units inside it (%s) that would have to change with it' % (target['name'], ', '.join(repr(u['name']) for u in others))
        # the cabinet fills exactly from the filler stack at end S (or the wall end) to its far side, which keeps
        # its place relative to the other end O; positions snap to the 1/16 grid as KCD stores them
        new_fill = {}
        if S == 'start':
            new_x = snap16(max(u['x_raw'] + u['w_raw'] for u in fill)) if fill else (0 if abs(t0) <= TOL_END else t0)
            new_end = t1 + dL                           # the far side keeps its distance from the wall END
            old_gap = 0 if (not fill and t0 < -TOL_END) else t0 - (new_x if fill else 0)
        else:
            new_fill = {u['id']: snap16(L_new - (L_old - u['x_raw'])) for u in fill}
            new_x = t0                                  # the far side keeps its distance from the wall START
            new_end = min(new_fill.values()) if fill else (L_new if abs(t1 - L_old) <= TOL_END else t1 + dL)
            old_gap = 0 if (not fill and t1 > L_old + TOL_END) else (min(u['x_raw'] for u in fill) if fill else L_old) - t1
        new_w = snap16(new_end - new_x)
        if new_w <= IN:
            return '%r would become %s wide' % (target['name'], frac_inches(new_w))
        attached = [u for u in ulist if not is_cabinet(u) and u['id'] not in keep and u['x_raw'] >= t0 - TOL_END and u['x_raw'] + u['w_raw'] <= t1 + TOL_END]
        kept = keep | {target['id']} | {u['id'] for u in fill} | {u['id'] for u in followers} | {u['id'] for u in attached}
        movers = [u for u in ulist if u['id'] not in kept] if S == 'start' else []
        bad = cannot_shift(movers) if movers else None
        if bad:
            return bad
        if any(u['id'] not in uidx for u in [target] + fill + followers + attached):
            return 'unit records could not be located'
        return dict(S=S, target=target, fill=fill, followers=followers, movers=movers, attached=attached,
                    new_x=new_x, new_w=new_w, new_end=new_end, new_fill=new_fill, old_gap=old_gap, t0=t0, t1=t1)

    def apply(pl):
        S, target, t0, t1 = pl['S'], pl['target'], pl['t0'], pl['t1']
        new_x, new_w, new_end = pl['new_x'], pl['new_w'], pl['new_end']
        dx, dW = new_x - t0, new_w - target['w_raw']
        set_unit_xw(data, uidx[target['id']], x=new_x if dx else None, w=new_w)
        touched[target['id']] = (t0, target['w_raw'], new_x, new_w)
        for u in pl['followers']:
            fx = u['x_raw'] + dx
            fw = (u['x_raw'] + u['w_raw'] + (new_end - t1)) - fx
            set_unit_xw(data, uidx[u['id']], x=fx if dx else None, w=fw)
            touched[u['id']] = (u['x_raw'], u['w_raw'], fx, fw)
            u['x_raw'], u['w_raw'] = fx, fw
        why = ''
        if abs(pl['old_gap']) > 2:
            why = ' (it now meets the %s exactly; the designer\'s file had a %s %s there)' % (
                'filler' if pl['fill'] else 'wall ' + S, frac_inches(abs(pl['old_gap'])), 'gap' if pl['old_gap'] > 0 else 'overlap')
        lines.append('   %r (unit %d, against the wall %s): %s -> %s wide%s%s' % (target['name'], target['id'], S, frac_inches(target['w_raw']), frac_inches(new_w),
                     (', X %s -> %s' % (frac_inches(t0), frac_inches(new_x))) if dx else '', why))
        if target['type'] in SHELF_TYPES or target['type'] == 645:
            checks.append('CHECK wall %d (%s): the unit against the wall %s is the connecting shelf %r; it was made %s wide so it still reaches the unit around the corner; look at that corner in KCD'
                          % (wid, rn, S, target['name'], frac_inches(new_w)))
        if pl['followers']:
            lines.append('   %d shelf/shelves inside it (units %s): %s -> %s wide' % (len(pl['followers']), ', '.join(str(u['id']) for u in pl['followers']),
                         frac_inches(pl['followers'][0]['w_raw'] - (new_end - t1) + dx), frac_inches(pl['followers'][0]['w_raw'])))
        # accessories drawn in the cabinet (rods, racks, hampers, trays): a rack on the left panel stays with that
        # panel, one on the right panel moves with it; something centred in the opening must be re-fitted by the engineer
        placed = []
        for u in pl['attached']:
            ld, rd = u['x_raw'] - t0, t1 - (u['x_raw'] + u['w_raw'])
            if abs(ld - rd) <= IN // 2:
                nx, how = u['x_raw'] + dx, 'fills or is centred in the opening: re-fit it in KCD'
            elif ld < rd:
                nx, how = u['x_raw'] + dx, 'kept on the left panel'
            else:
                nx, how = u['x_raw'] + (new_end - t1), 'kept on the right panel'
            if nx != u['x_raw']:
                set_unit_xw(data, uidx[u['id']], x=nx)
                touched[u['id']] = (u['x_raw'], u['w_raw'], nx, u['w_raw'])
                u['x_raw'] = nx
            placed.append('%r X %s (%s)' % (u['name'], frac_inches(nx), how))
        if placed and (dW or dx):
            checks.append('CHECK wall %d (%s): drawn in %r, which changed width: %s' % (wid, rn, target['name'], '; '.join(placed)))
        target['x_raw'], target['w_raw'] = new_x, new_w
        for u in pl['fill']:
            if S == 'start':
                continue                                    # start fillers stay at X 0
            nx = pl['new_fill'][u['id']]                    # end fillers keep their distance from the wall end
            set_unit_xw(data, uidx[u['id']], x=nx)
            touched[u['id']] = (u['x_raw'], u['w_raw'], nx, u['w_raw'])
            lines.append('   %r (unit %d): moved from X %s to X %s, still %s wide' % (u['name'], u['id'], frac_inches(u['x_raw']), frac_inches(nx), frac_inches(u['w_raw'])))
            u['x_raw'] = nx
        if S == 'start' and pl['fill']:
            lines.append('   %s stay(s) at the wall start, still %s wide' % (', '.join('%r (unit %d)' % (u['name'], u['id']) for u in pl['fill']), frac_inches(pl['fill'][0]['w_raw'])))
        shift(pl['movers'], 'so they stay where they are in the room' if M == 'start' else 'and slide with the moved wall end')

    def coverage():
        tops = [u for u in cabs if not any(v is not u and v['x_raw'] - TOL_END <= u['x_raw'] and u['x_raw'] + u['w_raw'] <= v['x_raw'] + v['w_raw'] + TOL_END for v in cabs)]
        tops.sort(key=lambda u: u['x_raw'])
        first, last = tops[0]['x_raw'], max(u['x_raw'] + u['w_raw'] for u in tops)
        total = sum(u['w_raw'] for u in tops)
        gaps = []
        for a, b in zip(tops, tops[1:]):
            g = b['x_raw'] - (a['x_raw'] + a['w_raw'])
            if abs(g) > 2:
                gaps.append('%s of %s between %r and %r' % ('gap' if g > 0 else 'overlap', frac_inches(abs(g)), a['name'], b['name']))
        span = last - first
        over_end, over_start = last - L_new, -first
        ends_ok = abs(over_end) <= 2 or (over_end > 2 and abs(over_end - (max_end - L_old)) <= 2) or last < L_new - 2
        starts_ok = abs(over_start) <= 2 or first > 2 or (over_start > 2 and abs(over_start + min_x) <= 2)
        if not (ends_ok and starts_ok):
            checks.append('CHECK wall %d (%s): after the change the units run from %s to %s but the wall is %s' % (wid, rn, frac_inches(first), frac_inches(last), frac_inches(L_new)))
            return
        s = '   units now run from %s to %s' % (frac_inches(first), frac_inches(last))
        if abs(over_end) <= 2 and abs(first) <= 2:
            s += ' = the wall length'
        else:
            bits = []
            if first > 2: bits.append('the wall is empty before %s' % frac_inches(first))
            if over_start > 2: bits.append('the first unit reaches %s past the wall start into the corner, as drawn' % frac_inches(over_start))
            if abs(over_end) <= 2: bits.append('the last unit ends at the wall end')
            elif over_end > 2: bits.append('the last unit reaches %s past the wall end into the corner, as drawn' % frac_inches(over_end))
            else: bits.append('the wall is empty after %s' % frac_inches(last))
            s += ' (%s)' % '; '.join(bits)
        s += '; widths add up to %s' % frac_inches(total)
        s += '' if abs(total - span) <= 2 else ' (%s)' % '; '.join(gaps)
        lines.append(s)

    def place_features():
        """Obstructions, outlets and openings keep their place in the room: X + dL when the start moved."""
        if M != 'start' or not features:
            return
        bad = cannot_shift(features)
        if bad:
            checks.append('CHECK wall %d (%s): the start moved %s and %s; left where it/they are' % (wid, rn, sdL, bad)); return
        shift(features, 'so they stay where they are in the room')
        checks.append('CHECK wall %d (%s): %s now sit(s) at %s from the moved start of the wall; check the place against the remeasure sheet'
                      % (wid, rn, ', '.join(repr(u['name']) for u in features), ', '.join(frac_inches(u['x_raw']) for u in features)))

    if not cabs:
        rest = [u for u in ulist if u['id'] not in keep]
        if M == 'start' and rest:
            bad = cannot_shift(rest)
            if bad:
                checks.append('CHECK wall %d (%s): the start moved %s and %s; nothing was changed on the units' % (wid, rn, sdL, bad))
            else:
                shift(rest, 'so they stay where they are in the room (no cabinets on this wall)')
        elif not features:
            lines.append('   no cabinets on this wall (accessories only); none changed')
        place_features()
        return
    if not edge_units(M):
        # nothing stands against the moved end: no cabinet changes; the units keep their place in the room
        if M == 'start':
            rest = [u for u in ulist if u['id'] not in keep]
            bad = cannot_shift(rest)
            if bad:
                checks.append('CHECK wall %d (%s): nothing stands against the start of the wall, which moved %s, but %s; nothing was changed on the units' % (wid, rn, sdL, bad))
            else:
                lines.append('   nothing stands against the start of this wall (the first unit was at X %s)' % frac_inches(min_x))
                shift(rest, 'so they stay where they are in the room')
        elif max_end > L_new + TOL_END:
            checks.append('CHECK wall %d (%s): the units end at %s, past the new wall end %s; nothing was changed on them'
                          % (wid, rn, frac_inches(max_end), frac_inches(L_new)))
        else:
            lines.append('   units stop at %s, %s short of the new wall end; none changed' % (frac_inches(max_end), frac_inches(L_new - max_end)))
        place_features()
        return
    first_try = plan(M)
    if isinstance(first_try, dict):
        apply(first_try)
        coverage()
    else:
        second = plan(O) if edge_units(O) else 'nothing stands against the wall %s' % O
        if isinstance(second, str) and second.replace('wall ' + O, 'wall ' + M) == first_try:
            second = 'it is the only cabinet on the wall'
        if isinstance(second, dict):
            lines.append('   note: %s; so the units %s and %r at the wall %s takes up the change'
                         % (first_try, 'keep their distance from the moved start, as KCD does' if M == 'start' else 'slide with the moved end',
                            second['target']['name'], O))
            apply(second)
            coverage()
        else:
            checks.append('CHECK wall %d (%s): %s; and at the other end: %s; the engineer decides how the wall change of %s is taken up (nothing was changed on the units%s)'
                          % (wid, rn, first_try, second, sdL, '; they moved with the wall start, as KCD does' if M == 'start' else ''))
    place_features()


def shelf_fit(data, ulist, uidx, rn, wid, lines, checks, touched):
    """Owner's rule (Oct 19, 2026): the shelves drawn inside a cabinet (their own unit numbers) must match the
    cabinet's opening width and its depth. For every cabinet on the wall, each shelf (type 640/641) lying inside
    its span is checked: X must be the inside of the left panel, X + W the inside of the right panel, D the
    cabinet's depth. A shelf that is off by more than 1/16 is set to the opening (slot 1, 2 and 4 plus the width
    copy); a shelf that straddles two cabinets or sits in no cabinet is flagged. Returns the number changed."""
    cabs = [u for u in ulist if is_cabinet(u) and u['type'] not in SHELF_TYPES and not is_filler(u)]
    shelves = [u for u in ulist if u['type'] in SHELF_TYPES]
    n = 0
    for sh in shelves:
        hosts = [c for c in cabs if c['x_raw'] - TOL_END <= sh['x_raw'] and sh['x_raw'] + sh['w_raw'] <= c['x_raw'] + c['w_raw'] + TOL_END]
        if not hosts:
            continue                                    # a connecting shelf between cabinets, not an interior shelf
        if len(hosts) > 1:
            hosts.sort(key=lambda c: c['w_raw'])        # the smallest cabinet that contains it
        c = hosts[0]
        x_want = snap16(c['x_raw'] + c.get('ls_raw', 0))                       # on KCD's 1/16 grid
        w_want = snap16(c['w_raw'] - c.get('ls_raw', 0) - c.get('rs_raw', 0))
        d_want = c['d_raw']
        dx, dw, dd = x_want - sh['x_raw'], w_want - sh['w_raw'], d_want - sh['d_raw']
        if abs(dx) <= 2 and abs(dw) <= 2 and abs(dd) <= 2:
            continue
        if sh['id'] not in uidx:
            checks.append('CHECK wall %d (%s): shelf %r (unit %d) inside %r is off its opening but could not be located' % (wid, rn, sh['name'], sh['id'], c['name'])); continue
        if abs(dd) > 2:
            checks.append('CHECK wall %d (%s): shelf %r (unit %d) is %s deep inside %r which is %s deep; depth left for the engineer'
                          % (wid, rn, sh['name'], sh['id'], frac_inches(sh['d_raw']), c['name'], frac_inches(d_want)))
        if abs(dx) > 2 or abs(dw) > 2:
            set_unit_xw(data, uidx[sh['id']], x=x_want if abs(dx) > 2 else None, w=w_want if abs(dw) > 2 else None)
            x_want = x_want if abs(dx) > 2 else sh['x_raw']
            w_want = w_want if abs(dw) > 2 else sh['w_raw']
            touched[sh['id']] = (sh['x_raw'], sh['w_raw'], x_want, w_want)
            what = []
            if abs(dx) > 2: what.append('X %s -> %s' % (frac_inches(sh['x_raw']), frac_inches(x_want)))
            if abs(dw) > 2: what.append('%s -> %s wide' % (frac_inches(sh['w_raw']), frac_inches(w_want)))
            lines.append('   shelf %r (unit %d) inside %r (unit %d): %s, to match the opening' % (sh['name'], sh['id'], c['name'], c['id'], ', '.join(what)))
            sh['x_raw'], sh['w_raw'] = x_want, w_want
            n += 1
    return n


def set_wall_lengths(job_path, changes, out_path, anchor='auto', heights=None, allow_absorb=True, units_step=True, shelves=True):
    """Change wall lengths (and optionally wall heights) in a .job and write out_path.

    changes     {wall id: new length in raw 0.1 mm}  (use round(inches * 254))
    heights     {room number: new wall height raw} applied to every live wall of that room, or
                {('wall', id): raw} for one wall
    anchor      'auto' (the engineers' way: the room's main wall keeps its start; walls upstream of it move their
                start, every other wall moves its end), or 'start' / 'end' for every wall
    units_step  True: on each changed wall, fillers keep their width, the cabinet at the wall end changes width and
                the end fillers slide to the new end (owner's rule); the units' room points are updated so KCD
                draws them on the wall. False: wall records only.
    shelves     True: on every wall, the shelves drawn inside a cabinet are set to its opening width (owner's rule);
                a depth that differs is flagged.
    Returns a dict: 'lines' (plain-English report lines), 'checks' (things the engineer must look at),
    'changed_walls', 'changed_units', 'written' (out_path or None).
    The edit is in place: the file keeps its size; outside the wall records and the touched unit fields every
    byte is the original.
    """
    data = bytearray(open(job_path, 'rb').read())
    original = bytes(data)
    names = room_names(original)
    units, uerr = units_by_wall(job_path)
    lines, checks, changed = [], [], set()
    if uerr:
        checks.append('CHECK units could not be read (%s): no unit was changed or checked' % uerr)
        units_step = False
    recs = job_walls(data)
    by_id = {r.parsed['id']: r for r in recs}
    walls_before = {i: dict(r.parsed) for i, r in by_id.items()}
    uidx = unit_index(original)
    touched = {}                                     # unit id -> (x_old, w_old, x_new, w_new)
    mesh_ranges = []                                 # byte ranges of the 3-D cache entries that were moved
    try:
        wall_notes = notes_on_walls(original)
    except Exception:
        wall_notes = {}

    def room_records(room, exclude_id=None):
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
        anc = auto_anchor(room_records(p['room']), wid) if anchor == 'auto' else anchor
        try:
            res = resize_wall(r.raw, new_len, room_records(p['room'], wid), anchor=anc, allow_absorb=allow_absorb)
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
        lines.append('wall %d (%s): %s -> %s (%s%s), its %s moved%s' % (
            wid, rn, frac_inches(p['length_raw']), frac_inches(new_len), '+' if dL > 0 else '-', frac_inches(abs(dL)),
            'start' if anc == 'end' else 'end', ('; walls %s moved with it' % moved) if moved else ''))
        if res['absorbed_by']:
            lines.append('   closed room: wall %d changed by the same amount so the room stays closed' % res['absorbed_by'])
        for w in res['warnings']:
            if w.startswith('skew'):
                lines.append('   note: ' + w[6:])
        if anc == 'end' and units.get(wid) and not units_step:
            lines.append('   the start of this wall moved; its %d unit(s) keep their distance from the start, as KCD does' % len(units[wid]))
            for u in units[wid]:
                if not is_cabinet(u):
                    checks.append('CHECK wall %d (%s): %r sits %s from the start of the wall, which moved %s%s; check its place against the remeasure'
                                  % (wid, rn, u['name'], frac_inches(u['x_raw']), '+' if dL > 0 else '-', frac_inches(abs(dL))))
        if units_step:
            unit_step(data, wid, rn, p, by_id[wid].parsed, units.get(wid, []), uidx, lines, checks, touched, anchor=anc)
        elif units.get(wid):
            ends = [u for u in units[wid] if abs(u['x_raw'] + u['w_raw'] - p['length_raw']) <= TOL_END]
            for u in ends:
                checks.append('CHECK wall %d (%s): %r ends at the old wall end (X %s, W %s); it needs %s%s to fit the new length'
                              % (wid, rn, u['name'], frac_inches(u['x_raw']), frac_inches(u['w_raw']), '+' if dL > 0 else '-', frac_inches(abs(dL))))
        if not units.get(wid):
            lines.append('   no units on this wall')
        dims = [t for k, t in wall_notes.get(wid, []) if k == 5]
        texts = [t for k, t in wall_notes.get(wid, []) if k == 4 and t.strip()]
        if dims:
            checks.append('CHECK wall %d (%s): %d dimension string(s) are drawn on this wall; they were not changed and may show the old size'
                          % (wid, rn, len(dims)))
        if texts:
            lines.append('   notes on this wall were left where they are: %s' % '; '.join(repr(' '.join(t.split()))[:40] for t in texts))
    # interior shelves on every wall (not only the changed ones)
    if units_step and shelves:
        fitted = 0
        for wid, lst in sorted(units.items()):
            r = by_id.get(wid)
            if not r or not r.parsed['is_live']:
                continue
            before = len(lines)
            fitted += shelf_fit(data, lst, uidx, names.get(r.parsed['room'], ''), wid, lines, checks, touched)
            if len(lines) > before:
                lines.insert(before, 'wall %d (%s): interior shelves' % (wid, names.get(r.parsed['room'], '')))
        if fitted:
            lines.append('shelves: %d interior shelf/shelves set to the opening of the cabinet they sit in' % fitted)
    # heights
    for key, h in (heights or {}).items():
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
    # room points of the units on walls that moved or whose own X/W changed
    repointed = 0
    if units_step:
        for wid, r in by_id.items():
            before, after = walls_before[wid], r.parsed
            wall_moved = before['P0'] != after['P0'] or abs(before['angle_deg'] - after['angle_deg']) > 1e-9
            for u in units.get(wid, []):
                if u['id'] not in uidx:
                    continue
                if not wall_moved and u['id'] not in touched:
                    continue
                x_old, w_old, x_new, w_new = touched.get(u['id'], (u['x_raw'], u['w_raw'], u['x_raw'], u['w_raw']))
                if u['id'] not in touched:
                    x_old = x_new = struct.unpack_from('<i', original, uidx[u['id']]['start'] + 6)[0]
                    w_old = w_new = struct.unpack_from('<i', original, uidx[u['id']]['start'] + 12)[0]
                A, Bp = unit_points(original, uidx[u['id']])
                An, Bn = moved_unit_points(A, Bp, before, after, x_old, w_old, x_new, w_new)
                if (An, Bn) != (A, Bp):
                    set_unit_points(data, uidx[u['id']], An, Bn)
                    repointed += 1
        if repointed:
            lines.append('drawing: the room position of %d unit(s) was moved with their walls so KCD draws them on the wall' % repointed)
    # the cached 3-D shape of every unit that moved or changed width (KCD draws from this cache and does not rebuild
    # it when the job opens; see kcdmesh.py)
    if units_step:
        try:
            mesh = kcdmesh.Mesh(original)
        except Exception as e:
            mesh = None
            checks.append('CHECK the 3-D cache could not be read (%s); units on moved walls will show at their old place until each wall is opened in KCD' % e)
        moved_shapes = stretched = 0
        for wid, r in by_id.items():
            before, after = walls_before[wid], r.parsed
            wall_moved = before['P0'] != after['P0'] or abs(before['angle_deg'] - after['angle_deg']) > 1e-9
            for u in units.get(wid, []):
                if mesh is None or u['id'] not in uidx or (not wall_moved and u['id'] not in touched):
                    continue
                sl = kcdmesh.Mesh.unit_slice(original, uidx[u['id']]['f86_at'])
                if not mesh.check_slice(sl):
                    checks.append('CHECK unit %d %r: its 3-D cache entry is out of range; its drawing was not moved' % (u['id'], u['name'])); continue
                if abs(before['angle_deg'] - after['angle_deg']) > 1e-9:
                    checks.append('CHECK unit %d %r: its wall turned; its drawing was not moved' % (u['id'], u['name'])); continue
                x_old, w_old, x_new, w_new = touched.get(u['id'], (None, None, None, None))
                if x_old is None:
                    x_old = x_new = struct.unpack_from('<i', original, uidx[u['id']]['start'] + 6)[0]
                    w_old = w_new = struct.unpack_from('<i', original, uidx[u['id']]['start'] + 12)[0]
                d, n = unit_vectors(after['angle_deg'])
                o_old = (before['P0'][0] + x_old * d[0], before['P0'][1] + x_old * d[1])
                o_new = (after['P0'][0] + x_new * d[0], after['P0'][1] + x_new * d[1])
                v = (int(round(o_new[0] - o_old[0])), int(round(o_new[1] - o_old[1])))
                ext0 = mesh.extent(original, sl, o_old, d, n)
                if v != (0, 0):
                    mesh.translate_unit(data, sl, v); moved_shapes += 1
                if w_new != w_old:
                    mesh.stretch_unit(data, sl, o_new, d, w_old, w_new); stretched += 1
                mesh_ranges += mesh.ranges(sl)
                ext = mesh.extent(data, sl, o_new, d, n)
                # the shape must sit where it sat before, relative to its own X corner, plus the width change at its far end
                if ext and ext0 and (abs(ext[0] - ext0[0]) > 1 or abs(ext[1] - (ext0[1] + (w_new - w_old))) > 1
                                     or abs(ext[2] - ext0[2]) > 1 or abs(ext[3] - ext0[3]) > 1):
                    checks.append('CHECK unit %d %r: its drawing did not move cleanly (along the wall %s..%s before, %s..%s after, width %s -> %s); open it in KCD'
                                  % (u['id'], u['name'], frac_inches(ext0[0]), frac_inches(ext0[1]), frac_inches(ext[0]), frac_inches(ext[1]), frac_inches(w_old), frac_inches(w_new)))
        if moved_shapes or stretched:
            lines.append('drawing: the cached 3-D shape of %d unit(s) was moved with its wall%s, so KCD shows them in place when the job opens'
                         % (moved_shapes, (' and %d resized unit(s) stretched to the new width (handles and hanger symbols are approximate until the unit is opened in KCD)' % stretched) if stretched else ''))
    # final checks: every room still consistent, nothing but wall records and the touched unit fields changed
    for room in sorted({x.parsed['room'] for x in recs if x.parsed['is_live']}):
        issues = check_room([x.raw for x in recs if x.parsed['room'] == room])
        hard = [s for s in issues if 'does not point back' in s or '!= P' in s]
        for s in hard:
            checks.append('CHECK room %d after the edit: %s' % (room, s))
    allowed = [(r.offset, r.offset + RECORD_SIZE) for r in recs]
    for ui in uidx.values():
        allowed += [(ui['start'] + 6, ui['start'] + 10), (ui['start'] + 12, ui['start'] + 16),
                    (ui['f86_at'] + 12, ui['f86_at'] + 16), (ui['f86_at'] + 40, ui['f86_at'] + 64)]
    allowed += mesh_ranges
    allowed.sort()
    diff_outside = []
    k = 0
    for i in range(len(data)):
        if data[i] == original[i]:
            continue
        while k < len(allowed) and allowed[k][1] <= i:
            k += 1
        if not (k < len(allowed) and allowed[k][0] <= i < allowed[k][1]):
            diff_outside.append(i)
            if len(diff_outside) > 5:
                break
    if diff_outside:
        raise RuntimeError('internal error: bytes outside the wall records and the unit fields changed (first at %d)' % diff_outside[0])
    written = None
    if (changed or touched) and out_path:
        if os.path.abspath(out_path) == os.path.abspath(job_path):
            raise ValueError('refusing to overwrite the input job; give another output name')
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        open(out_path, 'wb').write(bytes(data))
        written = out_path
        back = open(out_path, 'rb').read()
        if back != bytes(data) or len(back) != len(original):
            raise RuntimeError('internal error: the written file does not read back')
    return {'lines': lines, 'checks': checks, 'changed_walls': sorted(changed), 'changed_units': sorted(touched), 'written': written,
            'mesh_note': 'The print pages in the file are not rebuilt; KCD redraws them when it prints.'}


# --------------------------------------------------------------------------- remeasure read-out JSON
WALL_LABEL = re.compile(r'^(?P<room>[^#]+?)\s+#\s*(?P<wall>\d+)\s*(?:\(printed\s+(?P<printed>[^)]+)\))?\s*$', re.I)
FACT_LABEL = re.compile(r'^(?P<room>.+?)\s+(?P<key>H|HO|HD|BB|F|Door|Molding|HOLES)\s*$', re.I)
ANGLE_LABEL = re.compile(r'^(?P<room>[^#]+?)\s+corner\s+#\s*(?P<a>\d+)\s*/\s*#\s*(?P<b>\d+)\s+angle\s*$', re.I)
OPENING_LABEL = re.compile(r'^(?P<room>[^#]+?)\s+opening\s+between\s+#\s*(?P<a>\d+)\s+and\s+#\s*(?P<b>\d+)\s*$', re.I)


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
    """The remeasure read-out (Grok's format, or one written by hand/by Claude from the scan): agreed wall lengths,
    walls held for review, corner angles ("<room> corner #a/#b angle" in degrees), doorway openings ("<room> opening
    between #a and #b"), room facts (H, HD, BB, F, Door, Molding ...) and the lines it could not use."""
    d = json.load(open(path, encoding='utf-8'))
    walls, review, facts, skipped, angles, openings = [], [], [], [], [], []
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
        a = ANGLE_LABEL.match(lab)
        if a:
            try:
                deg = float(str(val).replace('°', '').strip())
            except ValueError:
                skipped.append('%s = %s (value is not an angle)' % (lab, val)); continue
            angles.append({'room': a.group('room').strip(), 'a': int(a.group('a')), 'b': int(a.group('b')), 'deg': deg, 'label': lab})
            continue
        o = OPENING_LABEL.match(lab)
        if o:
            v = parse_inches(val)
            if v is None:
                skipped.append('%s = %s (value is not a length)' % (lab, val)); continue
            openings.append({'room': o.group('room').strip(), 'a': int(o.group('a')), 'b': int(o.group('b')), 'measured_in': v, 'label': lab})
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
    return {'job': d.get('job'), 'walls': walls, 'walls_review': review, 'facts': facts, 'skipped': skipped,
            'angles': angles, 'openings': openings, 'notes': d.get('notes', ''), 'reader': d.get('reader', '')}


def corner_angle(by_id, a, b):
    """The inside angle drawn at the corner where walls a and b meet (degrees), or None when they do not meet."""
    pa, pb = by_id.get(a), by_id.get(b)
    if not pa or not pb:
        return None
    if pa['right_id'] == b:
        prev, nxt = pa, pb
    elif pb['right_id'] == a:
        prev, nxt = pb, pa
    else:
        return None
    return 180.0 - abs(wrap180(nxt['angle_deg'] - prev['angle_deg']))


def free_end(p):
    """The room point of a wall's open end (a doorway side), or None when both ends meet other walls."""
    if p['left_id'] == 0:
        return p['P0']
    if p['right_id'] == 0:
        return p['P1']
    return None


def opening_between(by_id, a, b):
    """Distance between the open ends of walls a and b (raw), or None."""
    pa, pb = by_id.get(a), by_id.get(b)
    if not pa or not pb:
        return None
    A, B = free_end(pa), free_end(pb)
    if A is None or B is None:
        return None
    return math.hypot(A[0] - B[0], A[1] - B[1])


def apply_rem(job_path, rem_path, out_path, anchor='auto', allow_absorb=True, units_step=True, heights_from_rem=False, shelves=True):
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
    # a length written next to a room name but no wall number (WERNER: "HOME OFFICE 205 1/8")
    rooms_by_name = {v: k for k, v in names.items()}
    for sk in list(rem['skipped']):
        lab, _, val = sk.partition(' = ')
        v = parse_inches(val.split(' (')[0]) if val else None
        if v is not None and lab.strip().lower() in rooms_by_name:
            checks.append('CHECK %s: the sheet has a length %s for the room but no wall number; which wall is it? (walls in that room: %s)'
                          % (lab.strip(), frac_inches(round(v * IN)), ', '.join('%d = %s' % (i, p['length_frac']) for i, p in sorted(by_id.items()) if p['is_live'] and p['room'] == rooms_by_name[lab.strip().lower()])))
    heights = {}
    if heights_from_rem:
        for f in rem['facts']:
            if f['key'] == 'H':
                v = parse_inches(f['value'])
                rn = rooms_by_name.get(f['room'].lower())
                if v is None or rn is None:
                    checks.append('CHECK %s H = %s: could not be matched to a room or is not a height' % (f['room'], f['value'])); continue
                heights[rn] = int(round(v * IN))
                pre.append('room %s: wall heights set to the measured ceiling %s' % (f['room'], frac_inches(heights[rn])))
    rep = set_wall_lengths(job_path, changes, out_path, anchor=anchor, allow_absorb=allow_absorb, heights=heights, units_step=units_step, shelves=shelves) if (changes or heights or shelves) else {
        'lines': [], 'checks': [], 'changed_walls': [], 'changed_units': [], 'written': None, 'mesh_note': ''}
    # corner angles: the tool never turns a wall, so a corner measured off the drawing is the engineer's
    post = []
    for a in rem['angles']:
        drawn = corner_angle(by_id, a['a'], a['b'])
        if drawn is None:
            checks.append('CHECK %s corner #%d/#%d: measured %.1f degrees, but walls %d and %d do not meet in the job' % (a['room'], a['a'], a['b'], a['deg'], a['a'], a['b'])); continue
        if abs(drawn - a['deg']) <= ANGLE_TOL_DEG:
            post.append('corner %d/%d (%s): drawn %g degrees, measured %.1f; within %g degree(s), left as drawn' % (a['a'], a['b'], a['room'], round(drawn, 2), a['deg'], ANGLE_TOL_DEG))
        else:
            checks.append('CHECK %s corner #%d/#%d: drawn %g degrees, measured %.1f (%+.1f); the tool does not turn walls, so the engineer redraws this corner in KCD'
                          % (a['room'], a['a'], a['b'], round(drawn, 2), a['deg'], a['deg'] - drawn))
    # doorway openings: compared on the file as written (the wall ends have moved)
    if rem['openings']:
        geo = open(rep['written'], 'rb').read() if rep.get('written') else data
        after = {r.parsed['id']: r.parsed for r in job_walls(geo)}
        for o in rem['openings']:
            was, now = opening_between(by_id, o['a'], o['b']), opening_between(after, o['a'], o['b'])
            meas = int(round(o['measured_in'] * IN))
            if now is None:
                checks.append('CHECK %s opening between #%d and #%d: measured %s, but in the job those walls do not both have an open end' % (o['room'], o['a'], o['b'], frac_inches(meas))); continue
            if abs(now - meas) <= OPENING_TOL:
                post.append('opening between walls %d and %d (%s): measured %s; the file has %s after the change (was %s)' % (o['a'], o['b'], o['room'], frac_inches(meas), frac_inches(int(round(now))), frac_inches(int(round(was)))))
            else:
                checks.append('CHECK %s opening between #%d and #%d: measured %s, but the file has %s after the change (was %s before); the open ends of walls %d and %d (or the corner angles) need the engineer'
                              % (o['room'], o['a'], o['b'], frac_inches(meas), frac_inches(int(round(now))), frac_inches(int(round(was))), o['a'], o['b']))
    rep['lines'] = pre + rep['lines'] + post
    rep['checks'] = checks + rep['checks']
    rep['facts'] = ['%s %s = %s' % (f['room'], f['key'], f['value']) for f in rem['facts']]
    # other lines written against a room name (obstructions, boxes drawn on an elevation ...) are listed as facts
    rest = []
    for sk in rem['skipped']:
        lab = sk.partition(' = ')[0].strip().lower()
        if any(lab.startswith(n) and lab != n for n in names.values() if n):
            rep['facts'].append(sk)
        else:
            rest.append(sk)
    rep['skipped'] = rest
    rep['rem_job'] = rem['job']
    rep['rem_notes'] = rem.get('notes', '')
    rep['rem_reader'] = rem.get('reader', '')
    return rep


def format_report(rep, title):
    out = [title, '']
    if rep.get('rem_reader'):
        out += ['Read-out: ' + rep['rem_reader'], '']
    if rep.get('rem_notes'):
        out += ['Sheet notes: ' + rep['rem_notes'], '']
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
            out.append('        %-28s X %-9s W %-9s ends %-9s unit %-3d type %-4d%s' % (u['name'][:28], frac_inches(u['x_raw']), frac_inches(u['w_raw']), frac_inches(end), u['id'], u.get('type', 0), flag))
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
    ap.add_argument('--anchor', default='auto', choices=['auto', 'start', 'end'],
                    help="auto (default): the engineers' way, the room's main wall keeps its start; start/end: that end stays on every wall")
    ap.add_argument('--no-absorb', action='store_true', help='refuse to change a second wall of a closed room')
    ap.add_argument('--walls-only', action='store_true', help='change the wall records only; leave every unit alone and just flag the ones at the wall ends')
    ap.add_argument('--no-shelf-fit', action='store_true', help='do not set the shelves drawn inside a cabinet to its opening width')
    ap.add_argument('--heights-from-rem', action='store_true', help='with --rem: set every wall of a room to the measured ceiling height H')
    a = ap.parse_args(argv)
    if a.list or not (a.set or a.height or a.rem):
        print(list_job(a.job)); return 0
    if a.rem:
        rep = apply_rem(a.job, a.rem, a.out, anchor=a.anchor, allow_absorb=not a.no_absorb, units_step=not a.walls_only, heights_from_rem=a.heights_from_rem, shelves=not a.no_shelf_fit)
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
    rep = set_wall_lengths(a.job, changes, a.out, anchor=a.anchor, heights=heights, allow_absorb=not a.no_absorb, units_step=not a.walls_only, shelves=not a.no_shelf_fit)
    print(format_report(rep, 'Wall changes in %s' % os.path.basename(a.job)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
