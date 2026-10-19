"""kcdmesh.py - the 3-D drawing cache (the `mesh` section) of a KCD v23 .job, enough to move a unit's cached
shape when its wall moved or its width changed.

KCD draws the plan, the elevations and the 3-D view from this cache. It regenerates a unit's entry only when
that unit or its wall is edited in KCD, not when the job opens: a file whose walls or unit sizes were changed
outside KCD shows the units at their old place until each wall is opened and closed (COYNE test 1 and 3,
Oct 19, 2026). Moving the cached shape along with the record fixes that.

Layout (checked on the COYNE job and two KCD re-saves of it):
  mesh = Int32 n1, 4*n1 bytes (unknown, kept as is),
         nverts x 12 bytes: float32 x, y, z in 0.1 mm, ROOM coordinates (same frame as the wall points),
         nidx x Int32: vertex numbers, 1-based and local to the unit's slice,
         nfaces x 66 bytes: Int32 @0 (unknown), Int32 @4 style, Int32 @8 start in the unit's index slice (1-based),
         Int32 @12 corner count (3 or 4), Int32 @16 and @20 face sizes in raw, float32 @24 @28 @32 face centre in
         room coordinates, 12 zero bytes, 18 constant bytes.
  Each unit's slice is in bytes 16..39 of its 86-byte block: vcount, voffset, foffset, fcount, ioffset, icount
  (offsets 1-based; the vertex and face slices tile the arrays exactly).
KCD re-serialises the faces in a new order on every save. Translating a unit = every vertex and every face centre
of its slice + v: this reproduces KCD's own moves byte for byte as multisets (3358 + 83 + 78 + 166 faces,
1692 + 527 + 429 + 414 vertices). A width change is a stretch about the unit's middle: vertices and face centres
past the middle move by dW, those at the middle (door meeting edges, a centre divider) by dW/2, the rest stay;
against KCD's own regeneration of a Tall 1 Opening (451 vertices) only 17 handle vertices differ.
"""
import struct
import math

try:
    import kcdjob
except ImportError:                       # imported from another folder
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kcdjob

VERTEX = 12
FACE = 66
IN = 254


class Mesh:
    """Offsets of the mesh arrays of one job. The data must not change size while a Mesh is in use."""

    def __init__(self, data):
        for name, start, end, info in kcdjob.parse(data):
            if name == 'mesh':
                self.start, self.end, self.info = start, end, info
                break
        else:
            raise ValueError('no mesh section')
        self.n1 = struct.unpack_from('<i', data, self.start)[0]
        self.voff0 = self.start + 4 + 4 * self.n1
        self.nverts, self.nidx, self.nfaces = info['nverts'], info['nidx'], info['nfaces']
        self.ioff0 = self.voff0 + VERTEX * self.nverts
        self.foff0 = self.ioff0 + 4 * self.nidx

    # -- slices ---------------------------------------------------------------------------------
    @staticmethod
    def unit_slice(data, f86_at):
        """(vcount, voffset, foffset, fcount, ioffset, icount) of a unit from its 86-byte block."""
        return struct.unpack_from('<6i', data, f86_at + 16)

    def vertex_at(self, k):
        return self.voff0 + VERTEX * (k - 1)

    def face_at(self, j):
        return self.foff0 + FACE * (j - 1)

    def ranges(self, sl):
        """Byte ranges (start, end) of the unit's vertices and faces, for a change guard."""
        vc, vo, fo, fc, io, ic = sl
        return [(self.vertex_at(vo), self.vertex_at(vo) + VERTEX * vc), (self.face_at(fo), self.face_at(fo) + FACE * fc)]

    def check_slice(self, sl):
        vc, vo, fo, fc, io, ic = sl
        return (vc >= 0 and fc >= 0 and 1 <= vo and vo - 1 + vc <= self.nverts and 1 <= fo and fo - 1 + fc <= self.nfaces)

    # -- reading ----------------------------------------------------------------------------------
    def vertices(self, data, sl):
        vc, vo = sl[0], sl[1]
        return [struct.unpack_from('<3f', data, self.vertex_at(vo + i)) for i in range(vc)]

    def face_centres(self, data, sl):
        fo, fc = sl[2], sl[3]
        return [struct.unpack_from('<3f', data, self.face_at(fo + j) + 24) for j in range(fc)]

    # -- editing ----------------------------------------------------------------------------------
    def _map_points(self, data, sl, fn):
        """Apply fn((x, y, z)) -> (x, y, z) to every vertex and every face centre of the slice. Returns the count."""
        vc, vo, fo, fc, io, ic = sl
        n = 0
        for i in range(vc):
            o = self.vertex_at(vo + i)
            p = struct.unpack_from('<3f', data, o)
            q = fn(p)
            if q != p:
                struct.pack_into('<3f', data, o, *q); n += 1
        for j in range(fc):
            o = self.face_at(fo + j) + 24
            p = struct.unpack_from('<3f', data, o)
            q = fn(p)
            if q != p:
                struct.pack_into('<3f', data, o, *q)
        return n

    def translate_unit(self, data, sl, v):
        """Move the unit's cached shape by v = (dx, dy) raw (room coordinates)."""
        dx, dy = float(v[0]), float(v[1])
        if dx == 0 and dy == 0:
            return 0
        return self._map_points(data, sl, lambda p: (p[0] + dx, p[1] + dy, p[2]))

    def stretch_unit(self, data, sl, origin, d, w_old, w_new, tol=IN // 2):
        """Change the cached width of a unit that starts at `origin` (room coordinates of its X corner) and runs
        along the unit vector d. Points past the middle move by dW, points at the middle (within tol) by dW/2."""
        dW = float(w_new - w_old)
        if dW == 0:
            return 0
        mid = w_old / 2.0
        ox, oy = float(origin[0]), float(origin[1])

        def fn(p):
            along = (p[0] - ox) * d[0] + (p[1] - oy) * d[1]
            if abs(along - mid) <= tol:
                s = dW / 2.0
            elif along > mid:
                s = dW
            else:
                return p
            return (p[0] + s * d[0], p[1] + s * d[1], p[2])
        return self._map_points(data, sl, fn)

    def extent(self, data, sl, origin, d, n):
        """(min along, max along, min depth, max depth) of the unit's vertices, measured from origin along d and n."""
        pts = self.vertices(data, sl)
        if not pts:
            return None
        ox, oy = float(origin[0]), float(origin[1])
        al = [(p[0] - ox) * d[0] + (p[1] - oy) * d[1] for p in pts]
        de = [(p[0] - ox) * n[0] + (p[1] - oy) * n[1] for p in pts]
        return (min(al), max(al), min(de), max(de))


def unit_vectors(angle_deg):
    a = math.radians(angle_deg)
    return (math.cos(a), math.sin(a)), (math.sin(a), -math.cos(a))
