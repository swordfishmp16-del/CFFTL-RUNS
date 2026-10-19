"""Where would the owner's rule 'units between two walls need fillers on both sides' fire? For every live wall that
meets another wall at BOTH ends and carries cabinets: is there a 3/4 filler at the start and at the end?"""
import sys
sys.path.insert(0, '/home/user/CFFTL-WORKING-/kcd-room-splitter')
import kcdwalls
IN = 254; TOL = IN // 16
for path in sys.argv[1:]:
    d = open(path, 'rb').read()
    names = kcdwalls.room_names(d)
    units, err = kcdwalls.units_by_wall(path)
    print('==', path.split('/')[-1])
    for r in kcdwalls.job_walls(d):
        p = r.parsed
        if not p['is_live']: continue
        lst = units.get(p['id'], [])
        cabs = [u for u in lst if kcdwalls.is_cabinet(u) and not kcdwalls.is_filler(u) and u.get('type') not in kcdwalls.SHELF_TYPES]
        if not cabs: continue
        fil = [u for u in lst if kcdwalls.is_filler(u)]
        at_start = any(abs(u['x_raw']) <= TOL for u in fil)
        at_end = any(abs(u['x_raw'] + u['w_raw'] - p['length_raw']) <= TOL for u in fil)
        first = min(lst, key=lambda u: u['x_raw']); last = max(lst, key=lambda u: u['x_raw'] + u['w_raw'])
        run0 = min(u['x_raw'] for u in lst if kcdwalls.is_cabinet(u)); run1 = max(u['x_raw'] + u['w_raw'] for u in lst if kcdwalls.is_cabinet(u))
        both = p['left_id'] and p['right_id']
        if not both: continue
        need = []
        if not at_start: need.append('start (run begins at %s, wall meets wall %d there)' % (kcdwalls.frac_inches(run0), p['left_id']))
        if not at_end: need.append('end (run ends at %s of %s, wall meets wall %d there)' % (kcdwalls.frac_inches(run1), p['length_frac'], p['right_id']))
        if need:
            print('   wall %2d %-14s L %-9s between walls %2d and %2d: NO FILLER at %s; cabinets: %s' % (
                p['id'], names.get(p['room'], '')[:14], p['length_frac'], p['left_id'], p['right_id'], ' and '.join(need),
                ', '.join('%s %s..%s' % (u['name'][:20], kcdwalls.frac_inches(u['x_raw']), kcdwalls.frac_inches(u['x_raw'] + u['w_raw'])) for u in cabs)))
        else:
            print('   wall %2d %-14s L %-9s between walls %2d and %2d: fillers at both ends' % (p['id'], names.get(p['room'], '')[:14], p['length_frac'], p['left_id'], p['right_id']))
