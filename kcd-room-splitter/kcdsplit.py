"""Split a multi-room KCD v23 .job into one file per room.

Rooms are deleted the way KCD deletes them: the walls and cabinets of the other rooms stay
in the file as deleted entries (so no wall or cabinet number changes), their notes are
removed, and the kept room becomes room 1. The rules were matched byte for byte against a
file KCD itself saved after deleting rooms.

Each room is named from its sidebar, the "ROOM DETAILS <name>" note. A room that only holds
another room's sidebar (a SIDEBAR / NOTES / Specs room with no cabinets) goes into that
room's file instead of getting a file of its own.

Every file is checked against the original before anything is saved, the files are checked
against each other so that every wall, cabinet and note lands in exactly one room file, and
every saved file is read back from disk.
"""
import datetime
import hashlib
import os
import re
import shutil
import socket
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kcdjob  # noqa: E402

APP_NAME = 'KCD ROOM SPLITTER'
OUT_ROOT = r'C:\KCD ROOM SPLITTER'

# Wall record bytes KCD keeps when it deletes a wall (colour and type fields);
# every other byte from 16 to 112 is zeroed, and the room (129) is set to 0.
WALL_KEEP = {32, 33, 34, 35, 46, 47, 48, 49, 82, 83, 84, 85}
WALL_ROOM = 129
# Unit fields (offsets in the 86-byte block) KCD zeroes when it deletes a cabinet:
# the wall number, its placement, and one flag.
UNIT_F86_ZERO = list(range(0, 4)) + list(range(16, 40)) + [66]
VIEW_CAMERA = 52             # bytes of the room record copied into the 82-byte view block
VIEW_NOTES_AT = 60           # note count inside the view block

CHECK = 'CHECK'              # something a person should look at
NOTE = 'NOTE'                # for information only

ROOM_DETAILS = re.compile(r'(?:^|[\r\n])[ \t]*ROOM[ \t]*DETAILS?', re.I)
SIDEBAR_WORDS = r'side[ \t]*ba?r|sidebr|notes?|specs?|details?'
SIDEBAR_ROOM = re.compile(r'\b(?:%s)\b' % SIDEBAR_WORDS, re.I)
SIDEBAR_SUFFIX = re.compile(r'^(.*?)[\s\-:]*\b(?:%s)\b' % SIDEBAR_WORDS, re.I)
GENERIC_ROOM = re.compile(r'^room\s*\d+$', re.I)
QUESTION_WORDS = re.compile(
    r"\b(old|copy|option|opt|alt|alternate|test|delete|deleted|void|backup|duplicate|scrap|unused|"
    r"do not use|dont use|don't use|not used)\b", re.I)
BAD_FILE_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


class SplitError(Exception):
    """The job cannot be split safely. Nothing is saved."""


# ---------------------------------------------------------------------------------------
# small helpers

def _i16(v):
    return struct.pack('<h', v)


def _i32(v):
    return struct.pack('<i', v)


def _str(s):
    return struct.pack('<H', len(s)) + s


def text(b):
    return b.decode('cp1252', 'replace')


def clean(s):
    return re.sub(r'\s+', ' ', s).strip()


def key(s):
    """Compare names without case, spaces or punctuation."""
    return re.sub(r'[^a-z0-9]', '', s.lower())


def file_part(s):
    s = BAD_FILE_CHARS.sub('-', s)
    return clean(s).rstrip(' .')


def sidebar_name(note_text):
    """The room name after ROOM DETAILS in a sidebar note, '' if none, None if not a sidebar."""
    t = text(note_text)
    m = ROOM_DETAILS.search(t)
    if not m:
        return None
    line = re.split(r'[\r\n]', t[m.end():], 1)[0]
    return clean(re.sub(r'^[\s\-:\u2013\u2014]+', '', line)).rstrip(' -:\u2013\u2014')


# ---------------------------------------------------------------------------------------
# what KCD does to a deleted wall or cabinet

def deleted_wall(rec):
    r = bytearray(rec)
    for k in range(16, 113):
        if k not in WALL_KEEP:
            r[k] = 0
    r[WALL_ROOM:WALL_ROOM + 4] = _i32(0)
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


# ---------------------------------------------------------------------------------------
# reading a job

class Job:
    """A parsed job plus what each room holds."""

    def __init__(self, d):
        if d[2:14] != b'Version # 23':
            raise SplitError('This is not a KCD version 23 job file.')
        try:
            S = kcdjob.parse(d)
        except Exception as e:
            raise SplitError('This job uses a layout the splitter cannot read yet (%s). '
                             'Split it in KCD by hand.' % type(e).__name__)
        self.d = d
        self.S = S
        self.sec = {n: (a, b, i) for n, a, b, i in S}
        R = self.sec['rooms'][2]
        self.n = R['n']
        self.walls = self.sec['walls'][2]['list']
        self.units = self.sec['units'][2]['list']
        self.notes = self.sec['notes'][2]['list']
        self.wall_room = {w['id']: w['room'] for w in self.walls}
        self.heading = [clean(text(c)) for c in self.sec['header'][2]['cust']]
        n = self.n
        self.rooms = [{'num': k, 'list_name': clean(text(R['list'][k - 1]['name'])),
                       'walls': 0, 'cabinets': 0, 'notes': 0, 'sidebars': []} for k in range(1, n + 1)]
        self.bad_walls = [w for w in self.walls if not 0 <= w['room'] <= n]
        for w in self.walls:
            if 1 <= w['room'] <= n:
                self.rooms[w['room'] - 1]['walls'] += 1
        self.orphan_units = []
        for u in self.units:
            if not u['wall']:
                continue
            r = self.wall_room.get(u['wall'])
            if r is not None and 1 <= r <= n:
                self.rooms[r - 1]['cabinets'] += 1
            else:
                self.orphan_units.append(u)
        self.bad_notes = [nt for nt in self.notes if not 0 <= nt['room'] <= n]
        self.job_notes = sum(1 for nt in self.notes if nt['room'] == 0)
        for nt in self.notes:
            if 1 <= nt['room'] <= n:
                rm = self.rooms[nt['room'] - 1]
                rm['notes'] += 1
                sb = sidebar_name(nt['text'])
                if sb is not None:
                    rm['sidebars'].append(sb)

    def live_wall_ids(self):
        return {w['id'] for w in self.walls if 1 <= w['room'] <= self.n}

    def live_unit_ids(self):
        return {u['id'] for u in self.units
                if u['wall'] and 1 <= self.wall_room.get(u['wall'], 0) <= self.n}


def guess_job_and_name(path, job):
    """Job number and last name from the file name or the KCD job heading, if they are there."""
    base = os.path.splitext(os.path.basename(path))[0]
    m = re.match(r'\s*(\d{5,8})\s+([A-Za-z][A-Za-z\'\-]*)', base)
    if m:
        return m.group(1), m.group(2)
    h = job.heading
    if h:
        m = re.match(r'(\d{5,8})\s+([A-Za-z][A-Za-z\'\-]*)$', h[0])
        if m:
            return m.group(1), m.group(2)
        if re.match(r'\d{5,8}$', h[0]) and len(h) > 1 and re.match(r'[A-Za-z][A-Za-z\'\-]*$', h[1]):
            return h[0], h[1]
    return '', ''


# ---------------------------------------------------------------------------------------
# deciding which rooms go in which file, what each file is called, and what to flag

def plan(job, job_no, last_name):
    """Return (files, job_flags). Each file is a dict with rooms, name, file and flags."""
    job_no = clean(job_no)
    last_name = clean(last_name)
    if not job_no:
        raise SplitError('Type the job number.')
    if not last_name:
        raise SplitError('Type the customer last name.')
    if file_part(job_no) != job_no or file_part(last_name) != last_name:
        raise SplitError('The job number and name cannot contain \\ / : * ? " < > |')

    rooms = [dict(r) for r in job.rooms]
    job_flags = []

    # rooms that only hold another room's sidebar
    for r in rooms:
        named_other = [s for s in r['sidebars'] if key(s) and key(s) != key(r['list_name'])]
        r['sidebar_only'] = r['cabinets'] == 0 and bool(
            named_other or SIDEBAR_ROOM.search(r['list_name'])
            or (GENERIC_ROOM.match(r['list_name']) and r['walls'] <= 1))
    real = [r for r in rooms if not r['sidebar_only']]
    if not real:
        for r in rooms:
            r['sidebar_only'] = False
        real = list(rooms)

    files = {r['num']: {'rooms': [r['num']], 'main': r, 'flags': [], 'extra_sidebars': []} for r in real}
    for s in rooms:
        if not s['sidebar_only']:
            continue
        target, how = match_sidebar_room(s, real)
        if target is None:
            files[s['num']] = {'rooms': [s['num']], 'main': s, 'flags': [], 'extra_sidebars': []}
            files[s['num']]['flags'].append((CHECK, 'Room "%s" has no cabinets and looks like a sidebar/notes '
                                                    'room, but it could not be matched to a room. It was made '
                                                    'as its own file. Check which room it belongs to.'
                                             % s['list_name']))
            continue
        f = files[target['num']]
        f['rooms'].append(s['num'])
        f['extra_sidebars'] += [x for x in s['sidebars'] if key(x)]
        f['flags'].append((NOTE, 'Sidebar room "%s" is in this file with it (%s).' % (s['list_name'], how)))

    out = []
    for num in sorted(files):
        f = files[num]
        f['rooms'].sort()
        r = f['main']
        flags = f['flags']
        names = []
        for s in r['sidebars'] + f['extra_sidebars']:
            if key(s) and key(s) not in [key(x) for x in names]:
                names.append(s)
        specific = [x for x in names if not GENERIC_ROOM.match(x)]
        if not names:
            if r['sidebars']:
                flags.append((CHECK, 'The sidebar has no room name after ROOM DETAILS. The file uses the '
                                     'KCD room list name "%s".' % r['list_name']))
            else:
                flags.append((CHECK, 'No sidebar (ROOM DETAILS note) was found for this room. The file uses '
                                     'the KCD room list name "%s".' % r['list_name']))
            name = r['list_name']
        elif not specific and not GENERIC_ROOM.match(r['list_name']):
            name = r['list_name']
            flags.append((CHECK, 'The sidebar only says "%s", so the file uses the KCD room list name "%s".'
                          % (names[0], name)))
        else:
            names = specific or names
            same = [x for x in names if key(x) == key(r['list_name'])]
            name = same[0] if same else names[0]
            if len(names) > 1:
                flags.append((CHECK, 'This room has more than one sidebar with different names: %s. '
                                     'The file uses "%s".' % (', '.join('"%s"' % x for x in names), name)))
            if key(name) != key(r['list_name']):
                flags.append((CHECK, 'KCD room list says "%s" but the sidebar says "%s". The file uses the '
                                     'sidebar name.' % (r['list_name'], name)))
        if not key(name):
            name = 'ROOM %d' % num
            flags.append((CHECK, 'This room has no name. The file is called "%s".' % name))
        elif GENERIC_ROOM.match(name):
            flags.append((CHECK, 'This room is only called "%s". Give it a real name in KCD and split again, '
                                 'or rename the file.' % name))
        for word in sorted({m.group(0).upper() for x in (name, r['list_name']) for m in QUESTION_WORDS.finditer(x)}):
            flags.append((CHECK, 'The room name has "%s" in it. Make sure this is the version that should '
                                 'have its own file.' % word))
        if r['walls'] == 0:
            flags.append((CHECK, 'This room has no walls.'))
        if r['cabinets'] == 0:
            flags.append((CHECK, 'This room has no cabinets.'))
        base = file_part('%s %s %s' % (job_no, last_name, name))
        if base != clean('%s %s %s' % (job_no, last_name, name)):
            flags.append((NOTE, 'Characters Windows does not allow in file names were changed to "-".'))
        counts = {'walls': sum(rooms[k - 1]['walls'] for k in f['rooms']),
                  'cabinets': sum(rooms[k - 1]['cabinets'] for k in f['rooms']),
                  'notes': sum(rooms[k - 1]['notes'] for k in f['rooms'])}
        out.append({'rooms': f['rooms'], 'name': name, 'list_name': r['list_name'], 'base': base,
                    'flags': flags, **counts})

    seen = {}
    for f in out:
        k = f['base'].lower()
        if k in seen:
            seen[k] += 1
            f['flags'].append((CHECK, 'Another room has the same name, so this file got "(%d)" added.' % seen[k]))
            f['base'] = '%s (%d)' % (f['base'], seen[k])
        else:
            seen[k] = 1
    for f in out:
        f['file'] = f['base'] + '.job'
        if len(f['file']) > 150:
            raise SplitError('The file name for room "%s" is too long.' % f['name'])

    if job.orphan_units:
        job_flags.append((CHECK, '%d cabinet(s) are on a wall that is not in any room, so they are not in any '
                                 'room file.' % len(job.orphan_units)))
    if job.bad_walls:
        job_flags.append((CHECK, '%d wall(s) point to a room that does not exist, so they are not in any room '
                                 'file.' % len(job.bad_walls)))
    if job.bad_notes:
        job_flags.append((NOTE, '%d note(s) belong to a room that is no longer in the job (KCD does not show '
                                'them), so they are not in any room file.' % len(job.bad_notes)))
    if len(out) == 1:
        job_flags.append((NOTE, 'This job has only one room, so there is only one room file.'))
    return out, job_flags


def match_sidebar_room(s, real):
    """Find the room a sidebar-only room belongs to. Returns (room, reason) or (None, None)."""
    names = [x for x in s['sidebars'] if key(x)]

    def own_names(r):
        return {key(r['list_name'])} | {key(x) for x in r['sidebars'] if key(x)}

    for nm in names:
        c = [r for r in real if key(nm) in own_names(r)]
        if len(c) == 1:
            return c[0], 'its ROOM DETAILS says "%s"' % nm
    m = SIDEBAR_SUFFIX.match(s['list_name'])
    stem = m.group(1) if m else ''
    if key(stem):
        c = [r for r in real if key(stem) in own_names(r)]
        if len(c) == 1:
            return c[0], 'its name starts with "%s"' % clean(stem)
    if len(real) == 1:
        return real[0], 'it is the only other room'
    for nm in names + ([stem] if key(stem) else []):
        c = [r for r in real if any(key(nm) in x or x in key(nm) for x in own_names(r) if x)]
        if len(c) == 1:
            return c[0], 'its name is close to "%s"' % c[0]['list_name']
    return None, None


# ---------------------------------------------------------------------------------------
# building one room file

def keep_rooms(job, keep, rtf=None):
    """Return a job holding only the rooms in `keep` (1-based, original order), renumbered 1..n.

    rtf, if given, is the new notes-file name KCD stores in the job (KCD sets it to the job's
    own name when you use Save As).
    """
    d = job.d
    sec = job.sec
    rooms = sec['rooms'][2]
    keep = sorted(set(keep))
    if not keep or keep[0] < 1 or keep[-1] > rooms['n']:
        raise ValueError('room numbers must be 1..%d' % rooms['n'])
    newnum = {old: i + 1 for i, old in enumerate(keep)}
    wall_room = job.wall_room
    units = job.units

    def unit_kept(u):
        return wall_room.get(u['wall'], 0) in newnum

    notes = [n for n in job.notes if n['room'] in newnum or n['room'] == 0]
    out = []

    # ---- header: current-room camera, note count, notes-file name -----------------------
    a, b, J = sec['header']
    h = bytearray(d[a:b])
    v = J['view_at'] - a
    first = rooms['list'][keep[0] - 1]
    h[v:v + VIEW_CAMERA] = d[first['start']:first['start'] + VIEW_CAMERA]
    h[v + VIEW_NOTES_AT:v + VIEW_NOTES_AT + 4] = _i32(len(notes))
    if rtf is not None:
        o = J['rtf_at'] - a
        h[o:o + 2 + len(J['rtf'])] = _str(rtf)
    out.append(bytes(h))

    # ---- rooms ----------------------------------------------------------------------------
    a, b, R = sec['rooms']
    out.append(_i16(len(keep)) + d[a + 2:a + 4] + _i32(1)
               + b''.join(d[R['list'][k - 1]['start']:R['list'][k - 1]['end']] for k in keep))

    # ---- handle sets: set 0 is the default, set k belongs to room k -----------------------
    sets = sec['handles'][2]['sets']
    out.append(b''.join(d[sets[k][0]:sets[k][1]] for k in [0] + keep))

    # ---- settings: drop (unit, code) pairs whose cabinet is deleted -----------------------
    a, b, T = sec['settings']
    by_id = {u['id']: u for u in units}
    pairs = [struct.unpack_from('<hh', d, T['npair_at'] + 2 + 4 * i) for i in range(T['npair'])]
    pairs = [(u, c) for u, c in pairs if u in by_id and unit_kept(by_id[u])]
    out.append(d[a:T['npair_at']] + _i16(len(pairs)) + b''.join(struct.pack('<hh', u, c) for u, c in pairs))

    # ---- walls: kept rooms renumbered, other rooms' walls deleted -------------------------
    for w in job.walls:
        rec = d[w['start']:w['end']]
        if w['room'] in newnum:
            r = bytearray(rec)
            r[WALL_ROOM:WALL_ROOM + 4] = _i32(newnum[w['room']])
            rec = bytes(r)
        elif w['room'] != 0:
            rec = deleted_wall(rec)
        out.append(rec)

    a, b, _ = sec['postwall']
    out.append(d[a:b])

    # ---- units: cabinets on deleted walls become deleted entries --------------------------
    for u in units:
        if u['wall'] and not unit_kept(u):
            out.append(deleted_unit(d, u))
        else:
            out.append(d[u['start']:u['end']])

    # ---- 3D view cache: copied (KCD rebuilds it when the job is saved) --------------------
    a, b, _ = sec['mesh']
    out.append(d[a:b])

    # ---- notes ----------------------------------------------------------------------------
    blk = [_str(b'** Notes **'), _i16(len(notes))]
    for n in notes:
        r = bytearray(d[n['start']:n['end']])
        if n['room']:
            o = n['room_at'] - n['start']
            r[o:o + 4] = _i32(newnum[n['room']])
        blk.append(bytes(r))
    out.append(b''.join(blk))

    # ---- room shapes: one slot per room plus one ------------------------------------------
    a, b, X = sec['roomshapes']
    slots = X['slots']
    if any(s['items'] for s in slots[1:]):
        raise SplitError('This job has room shapes the splitter does not handle yet. Split it in KCD by hand.')
    items = []
    for s0, s1, tag, tag_off in slots[0]['items']:
        if tag in newnum:
            r = bytearray(d[s0:s1])
            r[tag_off:tag_off + 4] = _i32(newnum[tag])
            items.append(bytes(r))
    out.append(d[a:a + 2] + _i32(len(items)) + b''.join(items) + _i32(0) * len(keep))

    # ---- job-wide sections copied unchanged -------------------------------------------------
    for name in ('materials', 'errlog', 'gap', 'pictemp'):
        a, b, _ = sec[name]
        out.append(d[a:b])

    # ---- unit-info defaults: set k-1 belongs to room k --------------------------------------
    a, b, D = sec['defaults']
    out.append(_str(b'Start-UnitInfoDefaults') + _i32(D['a']) + _i32(len(keep) - 1)
               + b''.join(d[D['sets'][k - 1][0]:D['sets'][k - 1][1]] for k in keep))
    return b''.join(out)


# ---------------------------------------------------------------------------------------
# checking a room file against the original

def _without_room(rec):
    r = bytearray(rec)
    r[WALL_ROOM:WALL_ROOM + 4] = bytes(4)
    return bytes(r)


def verify(job, res, keep, rtf=None):
    """Read the new file back and check it against the original. Returns what it holds.

    Raises AssertionError with a reason if anything is off.
    """
    d = job.d
    keep = sorted(set(keep))
    newnum = {old: i + 1 for i, old in enumerate(keep)}
    try:
        T = kcdjob.parse(res)
    except Exception as e:
        raise AssertionError('the new file does not read back (%s)' % e)
    A = job.sec
    B = {n: (a, b, i) for n, a, b, i in T}

    def raw(sec, name):
        a, b, _ = sec[name]
        return (d if sec is A else res)[a:b]

    # sections that must be byte for byte the same as the original
    for name in ('postwall', 'mesh', 'materials', 'errlog', 'gap', 'pictemp'):
        assert raw(A, name) == raw(B, name), '%s changed' % name

    # header: only the camera, note count and notes-file name may change
    ha, hb = A['header'][2], B['header'][2]
    for f in ('version', 'cust', 'date1', 'date2', 'L', 'nwalls', 'nunits'):
        assert ha[f] == hb[f], 'header %s changed' % f
    assert hb['rtf'] == (ha['rtf'] if rtf is None else rtf), 'notes-file name wrong'
    va, vb = ha['view_at'], hb['view_at']
    first = A['rooms'][2]['list'][keep[0] - 1]
    assert res[vb:vb + VIEW_CAMERA] == d[first['start']:first['start'] + VIEW_CAMERA], 'camera wrong'
    assert res[vb + VIEW_CAMERA:vb + VIEW_NOTES_AT] == d[va + VIEW_CAMERA:va + VIEW_NOTES_AT], 'view block changed'
    assert res[vb + VIEW_NOTES_AT + 4:vb + 82] == d[va + VIEW_NOTES_AT + 4:va + 82], 'view block changed'
    assert res[:hb['rtf_at']] == d[:ha['rtf_at']], 'header changed'
    assert res[hb['rtf_at'] + 2 + len(hb['rtf']):vb] == d[ha['rtf_at'] + 2 + len(ha['rtf']):va], 'header changed'

    # rooms: exactly the kept rooms, unchanged, first one opens
    ra, rb = A['rooms'][2], B['rooms'][2]
    assert rb['n'] == len(keep) and rb['cur'] == 1, 'room count wrong'
    for k, x in zip(keep, rb['list']):
        y = ra['list'][k - 1]
        assert res[x['start']:x['end']] == d[y['start']:y['end']], 'room record changed'

    # handle sets and unit-info defaults belong to the kept rooms
    sa, sb = A['handles'][2]['sets'], B['handles'][2]['sets']
    assert len(sb) == len(keep) + 1, 'handle sets wrong'
    for k, (x0, x1) in zip([0] + keep, sb):
        assert res[x0:x1] == d[sa[k][0]:sa[k][1]], 'handle set changed'
    da, db = A['defaults'][2], B['defaults'][2]
    assert db['a'] == da['a'] and db['b'] == len(keep) - 1, 'defaults wrong'
    for k, (x0, x1) in zip(keep, db['sets']):
        assert res[x0:x1] == d[da['sets'][k - 1][0]:da['sets'][k - 1][1]], 'defaults changed'

    # walls: kept rooms' walls unchanged except the room number; other rooms' walls deleted
    wa, wb = job.walls, B['walls'][2]['list']
    assert [w['id'] for w in wa] == [w['id'] for w in wb], 'wall numbers changed'
    live_walls = set()
    for x, y in zip(wa, wb):
        rx, ry = d[x['start']:x['end']], res[y['start']:y['end']]
        if x['room'] in newnum:
            assert y['room'] == newnum[x['room']] and _without_room(rx) == _without_room(ry), 'kept wall changed'
            live_walls.add(x['id'])
        elif x['room'] == 0:
            assert rx == ry, 'deleted wall changed'
        else:
            assert y['room'] == 0, 'other room wall still in file'
            assert all(ry[k] == 0 for k in range(16, 113) if k not in WALL_KEEP), 'other room wall not blank'
            assert ry[:16] == rx[:16] and ry[113:WALL_ROOM] == rx[113:WALL_ROOM] and ry[133:] == rx[133:] \
                and all(ry[k] == rx[k] for k in WALL_KEEP), 'wall record damaged'

    # cabinets: kept rooms' cabinets unchanged; other rooms' cabinets deleted
    wroom_b = {w['id']: w['room'] for w in wb}
    ua, ub = job.units, B['units'][2]['list']
    assert [u['id'] for u in ua] == [u['id'] for u in ub], 'cabinet numbers changed'
    live_units = set()
    for x, y in zip(ua, ub):
        if not x['wall']:
            assert d[x['start']:x['end']] == res[y['start']:y['end']], 'deleted cabinet changed'
        elif job.wall_room.get(x['wall'], 0) in newnum:
            assert d[x['start']:x['end']] == res[y['start']:y['end']], 'kept cabinet changed'
            assert wroom_b.get(y['wall']) == newnum[job.wall_room[x['wall']]], 'kept cabinet lost its wall'
            live_units.add(x['id'])
        else:
            assert y['wall'] == 0 and y['cab'] == b'' and y['lib'] == b'', 'other room cabinet still in file'
            assert y['cat'] == x['cat'] and y['id'] == x['id'], 'cabinet record damaged'

    # settings pairs: only for kept cabinets, in the original order
    def pairs(dd, sec):
        T2 = sec['settings'][2]
        return [struct.unpack_from('<hh', dd, T2['npair_at'] + 2 + 4 * i) for i in range(T2['npair'])]
    want = [p for p in pairs(d, A) if p[0] in live_units]
    assert pairs(res, B) == want, 'cabinet settings wrong'
    sa0, sb0 = A['settings'], B['settings']
    assert d[sa0[0]:sa0[2]['npair_at']] == res[sb0[0]:sb0[2]['npair_at']], 'job settings changed'

    # notes: the kept rooms' notes and the job-wide notes, unchanged except the room number
    na = [x for x in job.notes if x['room'] in newnum or x['room'] == 0]
    nb = B['notes'][2]['list']
    assert len(na) == len(nb), 'note count wrong'
    for x, y in zip(na, nb):
        rx, ry = bytearray(d[x['start']:x['end']]), bytearray(res[y['start']:y['end']])
        assert y['room'] == (newnum[x['room']] if x['room'] else 0), 'note in wrong room'
        ox, oy = x['room_at'] - x['start'], y['room_at'] - y['start']
        rx[ox:ox + 4] = ry[oy:oy + 4] = bytes(4)
        assert rx == ry, 'note changed'
    assert struct.unpack_from('<i', res, vb + VIEW_NOTES_AT)[0] == len(nb), 'note count in view wrong'

    # room shapes of the kept rooms only
    sha = [it for it in A['roomshapes'][2]['slots'][0]['items'] if it[2] in newnum]
    shb = B['roomshapes'][2]['slots'][0]['items']
    assert len(sha) == len(shb), 'room shapes wrong'
    for x, y in zip(sha, shb):
        assert y[2] == newnum[x[2]], 'room shape in wrong room'
        sx, sy = bytearray(d[x[0]:x[1]]), bytearray(res[y[0]:y[1]])
        sx[x[3]:x[3] + 4] = sy[y[3]:y[3] + 4] = bytes(4)
        assert sx == sy, 'room shape changed'
    assert all(not s['items'] for s in B['roomshapes'][2]['slots'][1:]), 'room shapes wrong'

    room_notes = {i for i, x in enumerate(job.notes) if x['room'] in newnum}
    return {'walls': live_walls, 'units': live_units, 'notes': room_notes}


def reconcile(job, held):
    """Check that every room, wall, cabinet and note is in exactly one room file."""
    rooms = [k for h in held for k in h['rooms']]
    assert sorted(rooms) == list(range(1, job.n + 1)), 'a room is missing or in two files'
    for what, everything in (('walls', job.live_wall_ids()), ('units', job.live_unit_ids()),
                             ('notes', {i for i, x in enumerate(job.notes) if 1 <= x['room'] <= job.n})):
        got = [x for h in held for x in h[what]]
        assert len(got) == len(set(got)), 'a %s is in two files' % what[:-1]
        assert set(got) == everything, 'a %s is missing from the room files' % what[:-1]


# ---------------------------------------------------------------------------------------
# the whole job

def job_folder(out_root, job_no, last_name):
    return os.path.join(out_root, file_part('%s %s' % (clean(job_no), clean(last_name))))


def existing_files(files, folder):
    return [f['file'] for f in files if os.path.exists(os.path.join(folder, f['file']))]


def split_job(path, job_no, last_name, out_root=OUT_ROOT, replace=False, progress=None):
    """Make the room files. Returns a result dict. Raises SplitError if nothing was made."""
    def say(msg):
        if progress:
            progress(msg)

    say('Reading the job...')
    try:
        d = open(path, 'rb').read()
    except OSError as e:
        raise SplitError('The job file could not be opened (%s).' % e.strerror)
    job = Job(d)
    files, job_flags = plan(job, job_no, last_name)
    folder = job_folder(out_root, job_no, last_name)
    there = existing_files(files, folder)
    if there and not replace:
        raise SplitError('Room files for this job are already in %s. Nothing was made.' % folder)

    # build and check every file in a work folder first
    os.makedirs(out_root, exist_ok=True)
    work = os.path.join(out_root, '_working %s' % os.path.basename(folder))
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work)
    try:
        held = []
        for i, f in enumerate(files, 1):
            say('Making room %d of %d: %s' % (i, len(files), f['name']))
            rtf = (f['base'] + '.RTF').encode('cp1252', 'replace')
            data = keep_rooms(job, f['rooms'], rtf)
            try:
                got = verify(job, data, f['rooms'], rtf)
            except AssertionError as e:
                raise SplitError('Room "%s" did not check out (%s). Nothing was made.' % (f['name'], e))
            got['rooms'] = f['rooms']
            held.append(got)
            p = os.path.join(work, f['file'])
            with open(p, 'wb') as fh:
                fh.write(data)
            f['md5'] = hashlib.md5(data).hexdigest()
            f['size'] = len(data)
            del data
        say('Checking that every wall, cabinet and note is in exactly one file...')
        try:
            reconcile(job, held)
        except AssertionError as e:
            raise SplitError('The room files do not add up to the whole job (%s). Nothing was made.' % e)
        for f in files:
            with open(os.path.join(work, f['file']), 'rb') as fh:
                if hashlib.md5(fh.read()).hexdigest() != f['md5']:
                    raise SplitError('A file did not save correctly (%s). Nothing was made.' % f['file'])

        # move the checked files into the job folder
        say('Saving...')
        os.makedirs(folder, exist_ok=True)
        for f in files:
            dest = os.path.join(folder, f['file'])
            try:
                os.replace(os.path.join(work, f['file']), dest)
            except OSError:
                raise SplitError('%s could not be saved. If it is open in KCD, close it and try again.' % dest)
            with open(dest, 'rb') as fh:
                if hashlib.md5(fh.read()).hexdigest() != f['md5']:
                    raise SplitError('%s did not save correctly. Delete it and try again.' % dest)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    # KCD keeps a job's notes in an .RTF file named in the job; Save As gives it the new name
    rtf_copied = 0
    old_rtf = os.path.join(os.path.dirname(os.path.abspath(path)), text(job.sec['header'][2]['rtf']))
    if os.path.isfile(old_rtf):
        for f in files:
            try:
                shutil.copyfile(old_rtf, os.path.join(folder, f['base'] + '.RTF'))
                rtf_copied += 1
            except OSError:
                pass
        if rtf_copied < len(files):
            job_flags.append((CHECK, 'The job notes file (%s) could not be copied for every room.'
                              % os.path.basename(old_rtf)))

    made = {f['file'].lower() for f in files}
    others = sorted(x for x in os.listdir(folder) if x.lower().endswith('.job') and x.lower() not in made)
    if others:
        job_flags.append((CHECK, 'The folder also has .job files this split did not make: %s. If they are '
                                 'from an older split, delete them.' % ', '.join(others)))

    result = {'path': path, 'job_no': clean(job_no), 'last_name': clean(last_name), 'folder': folder,
              'files': files, 'job_flags': job_flags, 'replaced': there, 'job': job,
              'rtf_copied': rtf_copied}
    result['report'] = write_report(result)
    return result


def check_job(path, job_no='0000000', last_name='TEST'):
    """Plan, build and check every room file in memory without saving anything (for testing)."""
    job = Job(open(path, 'rb').read())
    files, job_flags = plan(job, job_no, last_name)
    held = []
    for f in files:
        rtf = (f['base'] + '.RTF').encode('cp1252', 'replace')
        got = verify(job, keep_rooms(job, f['rooms'], rtf), f['rooms'], rtf)
        got['rooms'] = f['rooms']
        held.append(got)
    reconcile(job, held)
    return job, files, job_flags


def all_flags(result):
    out = list(result['job_flags'])
    for f in result['files']:
        out += [(lvl, '%s: %s' % (f['name'], msg)) for lvl, msg in f['flags']]
    return sorted(out, key=lambda x: x[0] != CHECK)


def write_report(result):
    job = result['job']
    files = result['files']
    lines = ['%s report' % APP_NAME,
             'Made:          %s on %s' % (datetime.datetime.now().strftime('%Y-%m-%d %I:%M %p'),
                                          socket.gethostname()),
             'Original job:  %s' % result['path'],
             'Job:           %s %s' % (result['job_no'], result['last_name']),
             'Rooms in job:  %d      Room files made: %d' % (job.n, len(files)),
             '']
    w = max(len(f['file']) for f in files) + 2
    lines.append('%-*s %-6s %-9s %-6s %s' % (w, 'FILE', 'WALLS', 'CABINETS', 'NOTES', 'KCD ROOM(S)'))
    for f in files:
        lines.append('%-*s %-6d %-9d %-6d %s' % (w, f['file'], f['walls'], f['cabinets'], f['notes'],
                                                  ' + '.join(job.rooms[k - 1]['list_name'] for k in f['rooms'])))
    tw = sum(f['walls'] for f in files)
    tc = sum(f['cabinets'] for f in files)
    tn = sum(f['notes'] for f in files)
    lines += ['%-*s %-6d %-9d %-6d' % (w, 'TOTAL', tw, tc, tn), '',
              'DOUBLE CHECK',
              '  Every room file was read back and compared with the original job.',
              '  Each holds its own room unchanged; every other room is deleted the way KCD deletes a room.',
              '  The job has %d walls, %d cabinets and %d room notes. Every one of them is in exactly'
              % (len(job.live_wall_ids()), len(job.live_unit_ids()),
                 sum(1 for x in job.notes if 1 <= x['room'] <= job.n)),
              '  one room file (totals above).',
              '  Every file was read back from disk after saving and matches what was made.']
    if job.job_notes:
        lines.append('  %d note(s) are not tied to a room. KCD keeps those in every room file, so they are in '
                     'every file.' % job.job_notes)
    if result['rtf_copied']:
        lines.append('  The job notes file (.RTF) next to the original job was copied for each room file.')
    if result['replaced']:
        lines.append('  These files replaced older ones: %s' % ', '.join(result['replaced']))
    lines += ['', 'FLAGS']
    flags = all_flags(result)
    if flags:
        lines += ['  %-6s %s' % (lvl, msg) for lvl, msg in flags]
    else:
        lines.append('  None.')
    p = os.path.join(result['folder'], '%s %s SPLIT REPORT.txt' % (result['job_no'], result['last_name']))
    p = os.path.join(result['folder'], file_part(os.path.basename(p)))
    with open(p, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    return p
