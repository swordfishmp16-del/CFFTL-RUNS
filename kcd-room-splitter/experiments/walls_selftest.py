"""Self-test of kcdwalls.py against the wall dump of the ten job sets (walls10.txt, made by walldump2.py on the
laptop: one WALL line per record with the 205 bytes in hex, one UNIT line per unit). Re-runs every field
identity and geometry check behind the byte layout in kcdwalls.py and prints the counts.
usage: python walls_selftest.py WALLS10.txt"""
import sys, os, math, re, struct
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kcdwalls import *          # noqa: the checks use the module's helpers by name
import kcdwalls

# ----------------------------------------------------------------------------- data file loader (walls10.txt)
def load_walls10(path):
    """Parse the tab-separated walls10.txt dump.  Returns {job_n: {'path','rooms','walls':[dict],'units':[dict]}}."""
    jobs = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.rstrip('\n')
        if not line: continue
        p = line.split('\t'); kind, n = p[0].split(' ', 1); n = int(n)
        j = jobs.setdefault(n, {'rooms': {}, 'walls': [], 'units': [], 'path': ''})
        if kind == 'JOB':
            j['path'] = p[1]
        elif kind == 'ROOM':
            j['rooms'][int(p[1])] = p[2]
        elif kind == 'WALL':
            w = {k: int(v) for k, v in re.findall(r'(\w+)=(-?\d+)', p[1])}
            w['bytes'] = bytes.fromhex([x for x in p if x.startswith('hex=')][0][4:])
            w['tex'] = [x for x in p if x.startswith('tex=')][0][4:]
            j['walls'].append(w)
        elif kind == 'UNIT':
            u = {k: (int(v) if re.fullmatch(r'-?\d+', v) else v) for k, v in re.findall(r'(\w+)=(\S+)', p[1])}
            u['name'] = p[2][5:]
            for x in p[3:]:
                for m in re.finditer(r'(\w+)=(-?[\d.]+)', x):
                    u[m.group(1)] = float(m.group(2)) if '.' in m.group(2) else int(m.group(2))
            j['units'].append(u)
    return jobs


# ----------------------------------------------------------------------------- self test
def self_test(path):
    jobs = load_walls10(path)
    allw = [(jn, w) for jn in sorted(jobs) for w in jobs[jn]['walls']]
    P = {}
    for jn, w in allw:
        p = parse_wall(w['bytes']); p['_raw'] = w['bytes']; P[(jn, w['id'])] = p
    live = [(jn, w) for jn, w in allw if P[(jn, w['id'])]['is_live']]
    dead = [(jn, w) for jn, w in allw if not P[(jn, w['id'])]['is_live']]
    print(f"kcdwalls_draft self-test on {path}")
    print(f"  records: {len(allw)}  live: {len(live)}  dead: {len(dead)}  jobs: {len(jobs)}")

    def count(label, pred, pool=allw):
        fails = [(jn, w['id']) for jn, w in pool if not pred(P[(jn, w['id'])], w)]
        print(f"  {label:68s} {len(pool) - len(fails):3d}/{len(pool):3d}" + (f"  FAIL: {fails}" if fails else ""))
        return fails

    print("\n[1] field identities (all records unless noted)")
    count("Int32@20 == dump length", lambda p, w: p['length_raw'] == w['length'])
    count("Int32@100 == Int32@108 == Int32@20", lambda p, w: p['length_copy_100'] == p['length_copy_108'] == p['length_raw'])
    count("Int32@96 == Int32@104", lambda p, w: p['height_copy_96'] == p['height_copy_104'])
    count("Int32@96 == Int32@28 (fails only on 4 half-initialised dead walls)", lambda p, w: p['height_copy_96'] == p['height_raw'])
    count("Int32@36 == left, Int32@40 == right", lambda p, w: p['left_id'] == w['left'] and p['right_id'] == w['right'])
    count("Int16@117/119/121/123 == Int32@125 == id", lambda p, w: set(p['id16']) == {w['id']} and p['id'] == w['id'])
    count("Int32@129 == room", lambda p, w: p['room'] == w['room'])
    count("Int32@82 == 4", lambda p, w: p['npts'] == 4)
    count("Int16@44 == 0, bytes 86-95 == 0, bytes 112-116 == 0", lambda p, w: p['i16_44'] == 0 and not any(p['zero_86_95']) and not any(p['zero_112_116']))
    count("byte 35 == 0, bytes 127,128,131,132 == 0", lambda p, w: p['byte35'] == 0 and all(w['bytes'][o] == 0 for o in (127, 128, 131, 132)))
    count("Int32@24 == -1143 (live)", lambda p, w: p['thickness_raw'] == -T, live)
    count("Int16@46 == 3048 and Int16@48 == 6096 (live)", lambda p, w: p['i16_46_raw'] == 3048 and p['i16_48_raw'] == 6096, live)
    count("Int16@46/48 == 3048/6096 on every record with non-zero colour", lambda p, w: (p['i16_46_raw'], p['i16_48_raw']) == (3048, 6096) or p['colour_hex'] == '000000')
    count("float32@16 is an exact multiple of 254 (whole degrees) (live)", lambda p, w: p['angle_raw'] % 254 == 0, live)
    count("float32@16 == 0 on dead records", lambda p, w: p['angle_raw'] == 0, dead)
    count("angle@16 within 0.05 deg of atan2(P1-P0) (live)", lambda p, w: abs(wrap180(p['angle_from_points'] - p['angle_deg'])) <= 0.05, live)
    count("colour bytes in {e1e1e1, fcfcfc, 000000}", lambda p, w: p['colour_hex'] in ('e1e1e1', 'fcfcfc', '000000'))
    count("f64 colour triple == bytes/255 or all zero", lambda p, w: p['colour_f64'] == (0.0, 0.0, 0.0) or all(abs(p['colour_f64'][i] - p['colour_rgb'][i] / 255) < 1e-9 for i in range(3)))
    count("f64@157..197 == 0, .001, .81, .02, .02, 27.5 (live)", lambda p, w: p['consts_f64'] == (0.0, 0.001, 0.81, 0.02, 0.02, 27.5), live)
    count("first record of each job carries 0x965E list header; others byte11==1", lambda p, w: p['is_first_record'] == (w['id'] == 1) and (p['is_first_record'] or p['byte11'] == 1))
    print("  first-record headers (Int32@0,@4,@8,@12):", sorted(set(P[(jn, 1)]['list_header'] for jn in jobs)))
    print("  byte-15 flag on live walls: 1 on", sum(1 for jn, w in live if P[(jn, w['id'])]['flag15']), "of", len(live), "(meaning unknown; identical by record slot in design vs engineered PRIEM 2/12 although walls were renumbered)")

    print("\n[2] geometry on live walls")
    stats = {'closed starts': 0, 'P0 == P1(left)': 0, 'P3 == P2(left)': 0, 'closed ends': 0, 'P1 == P0(right)': 0,
             'outer offset == T (|err|<=1.5)': 0, 'mitre formula (|err|<=1.5)': 0, 'mitre exact': 0,
             'P1-P0 == L*d exact': 0, '|err| <= 2': 0, '|err| <= 4': 0}
    lenmis = []; mitre_worst = (0, None)
    for jn, w in live:
        p = P[(jn, w['id'])]
        room = {x['id']: P[(jn, x['id'])] for x in jobs[jn]['walls'] if x['room'] == w['room']}
        left = room.get(p['left_id']) if p['left_id'] else None
        right = room.get(p['right_id']) if p['right_id'] else None
        if left is not None:
            stats['closed starts'] += 1
            stats['P0 == P1(left)'] += left['P1'] == p['P0']
            stats['P3 == P2(left)'] += left['P2'] == p['P3']
        if right is not None:
            stats['closed ends'] += 1
            stats['P1 == P0(right)'] += right['P0'] == p['P1']
        d, n = p['dir'], p['normal_right']
        offe = (p['P2'][0] - p['P1'][0]) * n[0] + (p['P2'][1] - p['P1'][1]) * n[1]
        offs = (p['P3'][0] - p['P0'][0]) * n[0] + (p['P3'][1] - p['P0'][1]) * n[1]
        stats['outer offset == T (|err|<=1.5)'] += abs(offe - T) <= 1.5 and abs(offs - T) <= 1.5
        e2, e3 = expected_outer(p, left, right)
        err = max(math.hypot(e2[0] - p['P2'][0], e2[1] - p['P2'][1]), math.hypot(e3[0] - p['P3'][0], e3[1] - p['P3'][1]))
        stats['mitre formula (|err|<=1.5)'] += err <= 1.5
        stats['mitre exact'] += err < 1e-6
        if err > mitre_worst[0]: mitre_worst = (err, (jn, w['id']))
        ex = p['vec_error']; m = max(abs(ex[0]), abs(ex[1]))
        stats['P1-P0 == L*d exact'] += m < 0.5
        stats['|err| <= 2'] += m <= 2.0
        stats['|err| <= 4'] += m <= 4.0
        if m >= 0.5: lenmis.append((jn, w['id'], p['length_raw'], round(p['span_raw'], 1), (round(ex[0]), round(ex[1]))))
    for k_, v_ in stats.items(): print(f"  {k_:36s} {v_}")
    print(f"  worst mitre error {mitre_worst[0]:.2f} raw at job/wall {mitre_worst[1]}")
    print(f"  walls where P1-P0 != L*d (job, id, L, |P1-P0|, (ex,ey)): {len(lenmis)}")
    for r in lenmis: print("    ", r)
    turns = {}
    for jn, w in live:
        p = P[(jn, w['id'])]
        if p['right_id']:
            r = P[(jn, p['right_id'])]; t = round(wrap180(r['angle_deg'] - p['angle_deg'])); turns[t] = turns.get(t, 0) + 1
    print("  turn angles at the", stats['closed ends'], "closed corners:", dict(sorted(turns.items())))

    print("\n[3] check_room() over every room (live walls)")
    nrooms = 0; clean = 0
    for jn in sorted(jobs):
        for rn in sorted(jobs[jn]['rooms']):
            recs = [x['bytes'] for x in jobs[jn]['walls'] if x['room'] == rn]
            if not recs: continue
            nrooms += 1
            iss = check_room(recs)
            if iss:
                print(f"  job {jn:2d} room {rn}: " + " | ".join(iss))
            else:
                clean += 1
    print(f"  rooms: {nrooms}, with no issue at the default tolerances (2.5 raw length, 1.5 raw mitre): {clean}")

    print("\n[4] rebuild_points(): recompute all points from L + angle + topology, compare with stored")
    tot = ok2 = 0; bad = []
    for jn in sorted(jobs):
        for rn in sorted(jobs[jn]['rooms']):
            recs = [x['bytes'] for x in jobs[jn]['walls'] if x['room'] == rn]
            if not recs: continue
            new = rebuild_points(recs)
            for wid, nb in new.items():
                tot += 1
                a = parse_wall(nb); b = P[(jn, wid)]
                worst = max(max(abs(a[k][0] - b[k][0]), abs(a[k][1] - b[k][1])) for k in ('P0', 'P1', 'P2', 'P3'))
                if worst <= 2: ok2 += 1
                else: bad.append((jn, wid, worst))
    print(f"  {ok2}/{tot} live walls reproduced within 2 raw; exceptions (job, id, max dev): {bad}")

    print("\n[5] resize_wall(): +1 in then -1 in round trip on every live wall (anchor start and end)")
    n_ok = n_rt = n_raise = n_skew = 0; raised = []
    for jn, w in live:
        room = [x['bytes'] for x in jobs[jn]['walls'] if x['room'] == w['room'] and x['id'] != w['id']]
        for anchor in ('start', 'end'):
            try:
                r1 = resize_wall(w['bytes'], w['length'] + IN, room, anchor=anchor)
            except ResizeError as e:
                n_raise += 1; raised.append((jn, w['id'], anchor, str(e).splitlines()[0][:90])); continue
            n_ok += 1
            new_room = {x['id']: r1['updated'].get(x['id'], x['bytes']) for x in jobs[jn]['walls'] if x['room'] == w['room']}
            iss = [s for s in check_room(list(new_room.values())) if 'mitre' in s or '!=' in s or 'not a live' in s]
            if iss: print(f"  job {jn} wall {w['id']} {anchor}: post-check issues {iss}")
            others = [b for i, b in new_room.items() if i != w['id']]
            r2 = resize_wall(new_room[w['id']], w['length'], others, anchor=anchor, absorb_id=r1['absorbed_by'])
            back = {x['id']: r2['updated'].get(x['id'], new_room[x['id']]) for x in jobs[jn]['walls'] if x['room'] == w['room']}
            if all(back[x['id']] == x['bytes'] for x in jobs[jn]['walls'] if x['room'] == w['room']): n_rt += 1
            else:
                # the edited wall gets P1 = P0 + L*d exactly (KCD does the same, MIRANDA eng wall 3), so a wall that
                # carried a designer's skew comes back without it: expected, counted apart
                pw = parse_wall(w['bytes'])
                if max(abs(pw['vec_error'][0]), abs(pw['vec_error'][1])) > 0.5: n_skew += 1
                else: print(f"  job {jn} wall {w['id']} {anchor}: round trip NOT byte-exact")
    print(f"  {n_ok} resizes succeeded, {n_rt} round-tripped byte-exact, {n_skew} came back without their old skew (expected), {n_raise} raised: {raised}")

    print("\n[6] worked examples")
    def show(jn, wid, nl, anchor='start', **kw):
        w = next(x for x in jobs[jn]['walls'] if x['id'] == wid)
        room = [x['bytes'] for x in jobs[jn]['walls'] if x['room'] == w['room'] and x['id'] != wid]
        units = [u for u in jobs[jn]['units'] if u['room'] == w['room']]
        print(f"  job {jn} wall {wid}: {w['length']} ({frac_inches(w['length'])} in) -> {nl} ({frac_inches(nl)} in), anchor={anchor}")
        try:
            r = resize_wall(w['bytes'], nl, room, anchor=anchor, units=units, **kw)
        except ResizeError as e:
            print("    REFUSED:", e); return None
        print(f"    translation {r['translation']}, absorbed_by {r['absorbed_by']}, changed walls {sorted(r['updated'])}")
        for i in sorted(r['updated']):
            a = parse_wall(r['updated'][i]); b = P[(jn, i)]
            ch = [f"{k}: {b[k]} -> {a[k]}" for k in ('length_raw', 'P0', 'P1', 'P2', 'P3') if a[k] != b[k]]
            print(f"    wall {i}: " + "; ".join(ch))
        for s in r['warnings']: print("    warning:", s)
        return r
    print(" GODDARD design (job 1, closed rectangle): apply remeasure 163 9/16 -> 162 5/8 to wall 5")
    r = show(1, 5, 41307)
    print(" GODDARD design: wall 6 90 3/4 -> 88 7/8 (opposite wall 7 must follow)")
    show(1, 6, 22574)
    print(" GODDARD design: wall 7 90 3/4 -> 89 1/8 with allow_absorb=False (remeasure gives 88 7/8 and 89 1/8: a rectangle cannot do that)")
    show(1, 7, 22638, allow_absorb=False)
    print(" HUMPHREY eng (job 17, open U): wall 1 145 -> 144 3/8")
    show(17, 1, 36671)
    print(" PRIEM eng (job 12, open): wall 3 166 -> 165 3/4 keeping the (0,0) corner, so anchor='end'")
    show(12, 3, 42101, anchor='end')
    print(" PRIEM eng: wall 5 57 1/4 -> 57 1/8")
    show(12, 5, 14510)
    print(" ROBERTS WIC eng (job 20): angled wall 5 (220 deg) 31 -> 32")
    show(20, 5, 7874 + IN)
    print(" MIRANDA eng (job 16): wall 1 156 3/4 -> 156 (units overhang warning expected)")
    show(16, 1, 39624)

    print("\n[7] pack_wall round trip: parse -> pack same values -> identical bytes")
    same = 0; diff = []
    for jn, w in allw:
        p = P[(jn, w['id'])]
        nb = pack_wall(w['bytes'], length=p['length_raw'], height=p['height_raw'], left_id=p['left_id'], right_id=p['right_id'],
                       P0=p['P0'], P1=p['P1'], P2=p['P2'], P3=p['P3'], id=p['id'], room=p['room'], thickness=p['thickness_raw'],
                       angle_deg=p['angle_deg'])
        if nb == w['bytes']: same += 1
        else: diff.append((jn, w['id'], [o for o in range(RECORD_SIZE) if nb[o] != w['bytes'][o]]))
    print(f"  {same}/{len(allw)} records identical after re-packing their own values (angle, length, height, ids, points)")
    print(f"  differing records (job, id, byte offsets): {diff}")
    print("   -> expected: the 4 half-initialised dead walls hold a height at @28 but 0 at @96/@104; pack_wall(height=) writes all three copies")


RESIZE_NOTES = """
What a wall-length rewrite must touch (inside the 205-byte records):
  wall k:    Int32@20, @100, @108 = L' ; P1 (@58,@62) and P2 (@66,@70) += v  (anchor='start', v = round(dL*d))
             or P0 (@50,@54) and P3 (@74,@78) -= v (anchor='end', and units on k need X += dL)
  every wall downstream along right_id (or upstream along left_id for anchor='end') until an open end:
             all four points += v  (pure translation: lengths, angles, mitres unchanged)
  closed loop: one antiparallel wall m also changes length by dL (its moved-side point pair shifts by v);
             if no antiparallel wall exists the loop cannot stay closed by changing lengths alone.
  Nothing else in the record depends on L (angle, thickness, height, colour, ids stay).
Still unknown (needs a KCD round trip on the sandbox laptop):
  - whether KCD re-derives P1/P2/P3 from L+angle on load or trusts the stored points (MIRANDA stores both,
    inconsistent by 16 raw, so both persist; write them consistently anyway)
  - whether other objects (unit world positions, door/window openings, elevation views, dimensions, the
    list header Int32s at 0..15 of the first record) reference the wall geometry and must be updated too
  - meaning of byte 15, Int16@46 = 3048 (12 in), Int16@48 = 6096 (24 in), the six constant doubles
  - whether the file holds a checksum / size table anywhere (unknown: the records were extracted, not written)
"""



if __name__ == '__main__':
    self_test(sys.argv[1])
