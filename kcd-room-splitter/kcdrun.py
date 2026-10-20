#!/usr/bin/env python3
"""kcdrun.py - the one command of the production project.

It runs one remeasure end to end: apply the read-out to the designer's KCD job (walls, heights, same-size sections,
interior shelves, end fillers), split the result into one KCD file per room, fill one pricing workbook per room with
everything that is certain, and write one plain-English RUN REPORT for the engineer.

    python3 kcdrun.py JOB.job --rem REM.json --order 1084476 --name ROBERTS --client "Elizabeth Roberts" --out DIR
                      [--test N] [--no-fillers] [--no-heights] [--no-split] [--no-workbooks] [--workbooks-only]
                      [--template PATH] [--price "ROOM NAME=PRICE.tsv" ...] [--entry CELL=VALUE ...]
                      [--designer NAME] [--install YYYY-MM-DD] [--sold 5585] [--main "ROOM NAME"] [--replace]

Without --rem the job gets the filler check only (kcdwalls.fillers_only), then the split and the workbooks.
--client defaults to the job's file name without "KCD". --test N defaults to the next free TEST number in DIR.

Steps and the files they write (DIR = --out):
  1 apply      kcdwalls.apply_rem, filler step on        DIR/<Client> - REM <order> applied - TEST<N>.job  (+ " REPORT.txt")
               without --rem: kcdwalls.fillers_only       DIR/<Client> - fillers checked - TEST<N>.job      (+ " REPORT.txt")
  2 split      kcdsplit.split_job                        DIR/<order> <NAME>/<order> <NAME> <ROOM>.job  and its SPLIT REPORT
  3 workbooks  kcdbook.fill from the bundled template    DIR/<order> <NAME>/<order> <NAME> <ROOM>.xlsm  (+ " WORKBOOK REPORT.txt")
  4 report                                               DIR/<order> <NAME> RUN REPORT.txt

Rules: nothing uncertain is written as a fact; a doubtful value becomes a CHECK line for the engineer. An --entry you
type wins over everything and is reported as "typed by you". Every file written here is a TEST file until KCD has
opened it. A bad input stops the run with one plain sentence; a failure in a later step keeps the earlier outputs and
the RUN REPORT says what was not done.

THE CELL MAP (what is written where, and why that is allowed)
  Data Entry (kcdbook.py, notes section 15; proven cell by cell on the WERNER engineer's workbook, parity 274/288
  with the 14 differences all in the hand columns Q/R):
    B5  client number   = --order, as a number                 WERNER B5 = 1089471
    B7  client name     = --name in capitals (last name only)  WERNER B7 = 'WERNER' (the Salesforce page says RENEE WERNER)
    B9  room name       = the room part of the room file name, in capitals   WERNER B9 = 'OFFICE' from '1089471 WERNER OFFICE.job'
    B1  install date    = --install (serial; B1 is a date cell) WERNER B1 = 2026-11-09
    F1  designer        = --designer, exact text of the list Data Conversions G1:G69   WERNER F1 = 'AMY MENDEZ'
    F5  unit material   = sidebar MATERIAL/COLOR when it is an exact entry of Data Conversions B1:B83
    F7  banding type    = sidebar EDGE BANDING thickness when in I37:I41 (.5mm 1mm 2mm Upgraded Woodtape)
    F9  banding colour  = sidebar EDGE BANDING colour when it is an exact entry of B1:B83
    F11 face type       = sidebar DOOR/DRAWER STYLE: Melamine -> 'Melamine'; TH -> 'Thermo Foil' (owner, Oct 20: every
                          thermofoil door is Doormark unless the sidebar says CF Thermo -> 'CF Thermo Foil'); I7:I16
    F21 molding         = sidebar BASE / CROWN type: None / Melamine / Thermo Foil / CF Thermo Foil (I47:I53)
    F23 molding location= sidebar BASE and CROWN quantities -> None / Base Only / Crown Only / Base & Crown (I59:I63)
    B25 main closet     = 'YES' and B27 sold-at price = --sold, only on the main room (--main, or the only room)
    never written: F13 F15 F17 C1 D26 D27 A27 (formulas), B3 B11 B13 B15 B17 B19 B21 B23 F3 F19 F25 (not certain from
    the job; B11 'NO', B17 'V23', F19 'Closet Factory', F25 'NO' are the template's own presets)
  Purchase Order (rows 19, 20, ...; WERNER row 19 = B19 'OFFICE', C19 6, D19 'DOOR', E19 'BP36559CZ', K19 'AMEROCK';
  the template's rows 19-40 have the same plain cells with E:J merged):
    B room name (= B9), C quantity, D item, E part number, K vendor
    written for a handle line with a part number and a quantity on the sidebar (dashes removed, as WERNER typed it),
    and for an accessory RM line with a part number that agrees with the unit's own code; D only when it is certain
    which faces the handles sit on ('DOOR' when the room has no drawers at all); K only when the sidebar names the
    vendor (a vendor guessed from the number's shape is a CHECK, never written)
  Doormark A1 (WERNER: EM31 'SARASOTA SHAKER' typed, AH31 = the SHS lookup; the colour code is a lookup from EM41):
    EM31 door design = the sidebar's TH door style as an exact entry of Data Conversions X3:X36
    EM41 door colour = the sidebar's Color- as an exact entry of X41:X58 (else CHECK with the Funder code)
    never written: door rows R/Y/AR 55, 61, 67 ... (door SIZES are the door-dimensioned elevation's and are not
    settled: WERNER followed (face - 1/8) / 2 for pairs, PRIEM did not), slab fillers CS/CZ/DT 166 and CO167 (4" x
    95 1/4 is nowhere in the job), CA31 (a formula the WERNER engineer typed over)
  VJT Order, CF5 Order, CF Thermo: nothing is written; every value we can compute is inferred and goes in the report.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import socket
import sys
import traceback
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'experiments', 'po'))
import kcdwalls  # noqa: E402
import kcdsplit  # noqa: E402
import kcdbook  # noqa: E402
import kcdunits  # noqa: E402
import sidebar as sidebar_mod  # noqa: E402
import soitems  # noqa: E402

DOORMARK_REF = os.path.join(HERE, 'experiments', 'po', 'doormark_ref.json')
PO_FIRST_ROW = 19
TEST_RE = re.compile(r' - TEST(\d+)\b', re.I)
CHECK, NOTE = 'CHECK', 'NOTE'


class StopRun(Exception):
    """A bad input. One plain sentence for the user; nothing else is written."""


# ----------------------------------------------------------------------------- small helpers
def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def key(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def default_client(job_path):
    """'ELIZABETH ROBERTS KCD.job' -> 'ELIZABETH ROBERTS'; 'Lynn Neddie - TEST3 saved by KCD try3.job' -> 'Lynn Neddie'."""
    base = os.path.splitext(os.path.basename(job_path))[0]
    base = re.sub(r'\s*-\s*(TEST|REM)\b.*$', '', base, flags=re.I)
    base = re.sub(r'\bKCD\b', '', base, flags=re.I)
    return re.sub(r'\s+', ' ', base).strip(' -_')


def next_test_number(out_dir):
    n = 0
    if os.path.isdir(out_dir):
        for f in os.listdir(out_dir):
            m = TEST_RE.search(f)
            if m:
                n = max(n, int(m.group(1)))
    return n + 1


def parse_date(text):
    m = re.fullmatch(r'\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*', text or '')
    if not m:
        raise StopRun('The install date must be written as YYYY-MM-DD, for example 2026-11-04 (you gave %r).' % text)
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        raise StopRun('%r is not a real date.' % text)


def frac(x):
    return soitems.frac(x)


def one_line(s, n=110):
    s = re.sub(r'\s+', ' ', str(s)).strip()
    return s if len(s) <= n else s[:n - 3] + '...'


# ----------------------------------------------------------------------------- the template's dropdown lists
class Dropdowns:
    """The exact texts the Data Entry and order-tab dropdowns accept, read from the template's Data Conversions sheet
    (openpyxl read-only; the template is never written)."""

    def __init__(self, template):
        import openpyxl
        from openpyxl.utils import column_index_from_string
        warnings.filterwarnings('ignore')
        wb = openpyxl.load_workbook(template, read_only=True)
        ws = wb['Data Conversions']

        def col(c, lo, hi):
            ci = column_index_from_string(c)
            return [str(v).strip() for (v,) in ws.iter_rows(min_row=lo, max_row=hi, min_col=ci, max_col=ci, values_only=True) if v not in (None, '')]
        self.designers = col('G', 1, 69)
        self.materials = col('B', 1, 83)
        self.face_types = col('I', 7, 16)
        self.banding = col('I', 37, 41)
        self.moldings = col('I', 47, 53)
        self.locations = col('I', 59, 63)
        self.jewelry = col('I', 29, 31)
        self.hinges = col('I', 69, 71)
        self.yesno = col('I', 3, 4)
        self.dm_designs = col('X', 3, 36)
        names = [str(v).strip() if v not in (None, '') else '' for (v,) in ws.iter_rows(min_row=41, max_row=58, min_col=24, max_col=24, values_only=True)]
        codes = [str(v).strip() if v not in (None, '') else '' for (v,) in ws.iter_rows(min_row=41, max_row=58, min_col=25, max_col=25, values_only=True)]
        self.dm_colours = {n: c for n, c in zip(names, codes) if n}
        wb.close()
        self.lists = {'F1': self.designers, 'F5': self.materials, 'F9': self.materials, 'F7': self.banding, 'F11': self.face_types,
                      'F21': self.moldings, 'F23': self.locations, 'B13': self.jewelry, 'B15': self.hinges,
                      'B19': self.yesno, 'B21': self.yesno, 'B23': self.yesno, 'B25': self.yesno, 'B11': self.yesno}

    def exact(self, cell, value):
        """The list entry equal to value (case and spaces ignored), or None when the cell has a list and value is not in it.
        A cell without a list returns the value as given."""
        lst = self.lists.get(cell)
        if lst is None:
            return value
        k = key(str(value))
        for e in lst:
            if key(e) == k:
                return e
        return None


def funder_colours():
    """Doormark's Funder colour sheet from experiments/po/doormark_ref.json: {upper name: code}; {} when the file is missing."""
    try:
        d = json.load(open(DOORMARK_REF))
    except (OSError, ValueError):
        return {}
    out = {}
    for c in d.get('colours', []):
        nm = re.sub(r'^\d+\s+', '', c.get('name', '')).upper().replace(' SM', '').strip()
        if nm and c.get('code'):
            out[nm] = c['code']
    return out


def funder_designs():
    try:
        d = json.load(open(DOORMARK_REF))
    except (OSError, ValueError):
        return {}
    return {x['code']: x for x in d.get('designs', []) if x.get('code')}


# ----------------------------------------------------------------------------- step 1: apply the remeasure (with the filler step)
def step_apply(args, out_dir, client, test_no):
    """Returns a dict: rep (kcdwalls report or None), job (the job to split: the written TEST file, or the input when
    nothing was written), report (path), note (what happened, one sentence), fillers (how the filler step went)."""
    tag = ('REM %s applied' % args.order) if args.rem else 'fillers checked'
    out_job = os.path.join(out_dir, '%s - %s - TEST%d.job' % (client, tag, test_no))
    out_rep = os.path.join(out_dir, '%s - %s - TEST%d REPORT.txt' % (client, tag, test_no))
    res = {'rep': None, 'job': args.job, 'report': None, 'note': '', 'fillers': '', 'written': None}
    if args.workbooks_only:
        res['note'] = 'Step 1 was skipped (--workbooks-only): the job was used as it is.'
        return res
    kw = dict(heights_from_rem=not args.no_heights)
    want_fillers = not args.no_fillers
    rep = None
    if args.rem:
        try:
            rep = kcdwalls.apply_rem(args.job, args.rem, out_job, fillers=want_fillers, **kw)
            res['fillers'] = ('the filler step ran' if want_fillers else 'the filler step was turned off (--no-fillers)')
        except TypeError as e:
            if 'fillers' not in str(e):
                raise
            rep = kcdwalls.apply_rem(args.job, args.rem, out_job, **kw)
            res['fillers'] = 'the filler step did NOT run: this copy of kcdwalls.py does not have it yet'
        fn = getattr(kcdwalls, 'fillers_only', None)
        if not rep.get('written') and want_fillers and fn is not None:
            # the remeasure confirmed the drawing, so kcdwalls wrote nothing and its filler step did not run: run it alone
            rep['lines'] = [ln for ln in rep['lines'] if not str(ln).startswith('fillers: not checked')]
            fr = fn(args.job, out_job)
            rep['lines'] += [''] + list(fr['lines'])
            rep['checks'] += list(fr['checks'])
            rep['fillers'] = fr.get('fillers', fr)
            if fr.get('written') and (fr.get('fillers') or {}).get('changed', fr.get('changed')):
                rep['written'] = fr['written']
            elif fr.get('written') and os.path.exists(fr['written']):
                os.remove(fr['written'])                     # a byte-for-byte copy of the input is no TEST file
            res['fillers'] = 'the remeasure changed nothing, so the filler step ran on the job as drawn'
        if want_fillers and isinstance(rep.get('fillers'), dict):
            added = rep['fillers'].get('added') or []
            res['fillers'] += (': %d filler%s added' % (len(added), 's' if len(added) != 1 else '')) if added else ': nothing to add'
        title = 'Remeasure %s applied to %s' % (rep.get('rem_job'), os.path.basename(args.job))
    else:
        fn = getattr(kcdwalls, 'fillers_only', None)
        if fn is None or args.no_fillers:
            res['note'] = ('Step 1: no remeasure was given and the filler step was turned off (--no-fillers), so the job was used as it is.'
                           if fn is not None else
                           'Step 1: no remeasure was given, and this copy of kcdwalls.py has no filler check yet, so the job was used as it is.')
            res['fillers'] = 'the filler step did not run'
            return res
        rep = fn(args.job, out_job)
        added = (rep.get('fillers') or {}).get('added') or []
        res['fillers'] = 'the filler check ran (no remeasure given): ' + (('%d filler%s added' % (len(added), 's' if len(added) != 1 else '')) if added else 'nothing to add')
        if rep.get('written') and not (rep.get('fillers') or {}).get('changed', True) and os.path.exists(rep['written']):
            os.remove(rep['written'])                        # a byte-for-byte copy of the input is no TEST file
            rep['written'] = None
        title = 'Fillers checked in %s' % os.path.basename(args.job)
    res['rep'] = rep
    text = kcdwalls.format_report(rep, title)
    with open(out_rep, 'w', encoding='utf-8') as fh:
        fh.write(text + '\n')
    res['report'] = out_rep
    if rep.get('written'):
        res['job'] = rep['written']
        res['written'] = rep['written']
        res['note'] = ('remeasure applied' if args.rem else 'fillers checked') + ', new job written.'
    else:
        res['note'] = (('nothing changed in the job (every measured wall was already as drawn and no filler was needed), ' if args.rem else
                        'no filler was needed, ') + 'so nothing was written and the original job went on to the next steps.')
    return res


def wall_lines_only(rep):
    """rep['lines'] without the filler block that kcdwalls appends to it (fr['lines'] after a blank line)."""
    lines = list(rep.get('lines', []))
    fr = rep.get('fillers')
    if isinstance(fr, dict) and fr.get('lines') and lines[-len(fr['lines']):] == list(fr['lines']):
        lines = lines[:len(lines) - len(fr['lines'])]
    while lines and not str(lines[-1]).strip():
        lines.pop()
    return lines


def trimmed_wall_lines(rep):
    """The apply report's wall lines without the per-wall 'already X, no change' and 'height A -> B' repeats."""
    if not rep:
        return [], 0
    keep, same = [], 0
    for ln in wall_lines_only(rep):
        s = ln.strip()
        if re.search(r'already .*no change$', s):
            same += 1
            continue
        if re.match(r'^wall \d+ \(.*\): height .* -> ', s):
            continue
        keep.append(ln)
    return keep, same


def fillers_block(rep):
    """F's filler block, rendered whatever shape it has (list of lines, dict, text)."""
    if not rep or 'fillers' not in rep or rep['fillers'] in (None, '', [], {}):
        return [], []
    fb = rep['fillers']
    lines, checks = [], []
    if isinstance(fb, dict):
        lines = [str(x) for x in fb.get('lines', [])]
        checks = [str(x) for x in fb.get('checks', [])]
        added = fb.get('added') or []
        if isinstance(added, list) and added and all(isinstance(a, dict) for a in added):
            lines.append('Added: ' + '; '.join('unit %s on wall %s at the %s, X %s' % (a.get('unit_id'), a.get('wall'), a.get('end'), kcdwalls.frac_inches(a['x_raw']) if a.get('x_raw') is not None else '?') for a in added))
        if not lines:
            lines = ['the filler step ran and found nothing to add']
    elif isinstance(fb, (list, tuple)):
        for x in fb:
            s = str(x)
            (checks if s.lstrip().startswith('CHECK') else lines).append(s)
    else:
        lines = str(fb).splitlines()
    return lines, checks


# ----------------------------------------------------------------------------- step 2: split
def step_split(args, job_path, out_dir):
    job = kcdsplit.Job(open(job_path, 'rb').read())
    files, job_flags = kcdsplit.plan(job, args.order, args.name)
    folder = kcdsplit.job_folder(out_dir, args.order, args.name)
    there = kcdsplit.existing_files(files, folder)
    if there and not args.replace:
        raise StopRun('Room files for this job are already in %s (%s). Run again with --replace to replace them, or give another --out folder.'
                      % (folder, ', '.join(there)))
    res = kcdsplit.split_job(job_path, args.order, args.name, out_root=out_dir, replace=args.replace)
    rooms = []
    for f in res['files']:
        rooms.append({'path': os.path.join(res['folder'], f['file']), 'name': f['name'], 'rooms': f['rooms'], 'base': f['base'],
                      'walls': f['walls'], 'cabinets': f['cabinets'], 'notes': f['notes'], 'flags': f['flags'], 'md5': f.get('md5')})
    return res, rooms


def planned_rooms(args, job_path):
    """Without a split: the rooms of the job as the splitter would name them, all pointing at the same file."""
    job = kcdsplit.Job(open(job_path, 'rb').read())
    files, job_flags = kcdsplit.plan(job, args.order, args.name)
    base = os.path.splitext(os.path.basename(job_path))[0]
    m = re.match(r'^\s*%s\s+%s\s+(.+)$' % (re.escape(args.order), re.escape(args.name)), base, re.I)
    rooms = []
    for f in files:
        name = f['name']
        if m and len(files) == 1:
            name = m.group(1).strip()          # an engineer's room file: '1089471 WERNER OFFICE.job' -> 'OFFICE'
        rooms.append({'path': job_path, 'name': name, 'rooms': f['rooms'], 'base': kcdsplit.file_part('%s %s %s' % (args.order, args.name, name)),
                      'walls': f['walls'], 'cabinets': f['cabinets'], 'notes': f['notes'], 'flags': f['flags'], 'md5': None})
    return rooms, job_flags


# ----------------------------------------------------------------------------- step 3: one workbook per room
FORM_WORDS = {'IN HOUSE': 'no order form: melamine, cut in house', 'DOORMARK': 'the Doormark A1 tab', 'CF5': 'the CF5 Order tab',
              'CF THERMO': 'the CF Thermo tab', 'ELEMENTS': 'the Elements paper form', 'NONE': 'no faces (the sidebar says none)',
              'ASK': 'which form is not settled: ask'}


def pick_sidebar(sides, room):
    """The sidebar of this room file: the one named like the room, else the one in a room with units, else the first."""
    if not sides:
        return None
    for s in sides:
        if key(s.sidebar_room_name) == key(room['name']):
            return s
    for s in sides:
        if s.unit_count:
            return s
    return sides[0]


def room_workbook(room, args, dd, cat, template, price_path, entries_typed, is_main, ref):
    """Fill one room's workbook. Returns a dict with everything the reports need. Never raises for a refused cell."""
    R = {'room': room['name'], 'job': room['path'], 'xlsm': None, 'report': None, 'entries': [], 'cells': [], 'suggest': [],
         'checks': [], 'notes': [], 'faces': [], 'vjt': [], 'po_open': [], 'pricing': '', 'refused': [], 'verify': [], 'rows': 0,
         'dropped': [], 'engine_flags': []}
    folder = os.path.dirname(room['path']) if room['md5'] else args.out
    xlsm = os.path.join(folder, room['base'] + '.xlsm')
    wrep = os.path.join(folder, room['base'] + ' WORKBOOK REPORT.txt')
    rn = room['name']

    # -- the sidebar and the special-order sheet of this file
    sj, sides, missing = sidebar_mod.parse_job(room['path'])
    side = pick_sidebar([s for s in sides if s.room in room['rooms']] or sides, room)
    price_lines = soitems.read_price_tsv(price_path) if price_path else []
    sheet = {}
    try:
        uj = kcdunits.read_job(room['path'], cat)
        sheet = soitems.build_sheet(uj, cat, price_lines)
    except Exception as e:                              # the special-order sheet is help for the engineer, never a stop
        R['notes'].append('The door, tray and hardware lists could not be made for this room (%s: %s).' % (type(e).__name__, one_line(e)))
    S = None
    for k in room['rooms']:
        if k in sheet and (S is None or (sheet[k]['faces'] or sheet[k]['hardware'])):
            S = sheet[k]
    if side is None:
        R['checks'].append('%s: no ROOM DETAILS sidebar note in this room file, so nothing from the sidebar was written.' % rn)

    entries, src = {}, {}

    def put(cell, value, why):
        entries[cell] = value
        src[cell] = why

    put('B5', int(args.order), 'the order number you gave')
    put('B7', args.name.upper(), 'the last name you gave (the engineers type the last name only, in capitals: WERNER)')
    put('B9', rn.upper(), 'the room part of the file name, in capitals as the engineers type it (WERNER: OFFICE)')
    if args.install:
        put('B1', args.install, 'the install date you gave')
    if args.designer:
        ex = dd.exact('F1', args.designer)
        if ex:
            put('F1', ex, 'the designer you gave (spelled as the workbook list has it)')
        else:
            put('F1', args.designer, 'the designer you gave; NOT in the workbook designer list, so check the spelling')
            R['checks'].append('%s: designer %r is not in the workbook list (Data Entry F1 dropdown); it was written as you typed it.' % (rn, args.designer))
    if side is not None:
        for cell, v in side.forms['workbook'].items():
            val, cert, why = v.get('value'), v.get('certainty'), v.get('source', '')
            if val in (None, ''):
                continue
            if cert == 'certain':
                ex = dd.exact(cell, val)
                if ex is None:
                    R['checks'].append('%s: %s = %r from the sidebar is not an exact entry of the workbook dropdown, so it was not written; pick it in Excel (%s).' % (rn, cell, val, why))
                    R['suggest'].append((cell, val, 'sidebar: ' + why + ' (not in the dropdown list)'))
                else:
                    put(cell, ex, 'sidebar: ' + why)
            else:
                R['suggest'].append((cell, val, '%s, %s' % (cert, why)))
    # the remeasure sheet against the sidebar's molding answer
    if ref.get('molding_none') and side is not None and entries.get('F23') not in (None, 'None'):
        R['checks'].append('%s: F21/F23 were written from the sidebar (%s, %s), but the remeasure sheet says Molding = %s; confirm the base/crown order.'
                           % (rn, entries.get('F21'), entries.get('F23'), ref['molding_none']))
    if is_main and args.sold is not None:
        put('B25', 'YES', 'this is the main room (%s), so it carries the sold-at price' % ('the only room' if is_main == 'only' else '--main'))
        put('B27', args.sold, 'the sold-at price you gave')
    elif args.sold is not None:
        R['suggest'].append(('B27', args.sold, 'sold-at price you gave; not written here because which room is the main closet (B25) was not given (--main "ROOM")'))
    for cell, val in entries_typed.items():
        if '!' in cell:
            continue
        put(cell, val, 'typed by you')

    # -- order tabs
    cells, cell_src = {}, []
    po_rows = []
    if side is not None:
        st = side.structured
        drawers_by_name = side.drawer_fronts_from_names
        box = (st.get('drawer_box', {}).get('type') or '').lower()
        no_drawers = ('no drawer' in box) and drawers_by_name == 0
        bad_parts = {c['what'].replace('part number of ', ''): c for c in side.checks if c['what'].startswith('part number of') and c['agree'] is False}
        for h in side.handles:
            if not h.get('part') or h.get('qty') in (None, 0):
                R['po_open'].append('handle line %r: no part number on the sidebar (%s)' % (h['text'], 'stock handle' if h.get('stock_mark') else 'the engineer types it'))
                continue
            vend_named = (h.get('vendor_basis') or '') == 'named'
            item = 'DOOR' if no_drawers else None
            row = {'B': rn.upper(), 'C': int(h['qty']) if float(h['qty']).is_integer() else h['qty'], 'D': item, 'E': h['part'].replace('-', ''),
                   'K': h['vendor'] if vend_named else None,
                   'why': 'sidebar handle line %r%s' % (h['text'], (' + ' + h['typed_line']) if h.get('typed_line') else '')}
            po_rows.append(row)
            if item is None:
                R['checks'].append('%s: Purchase Order row %d: type DOOR or DRAWER in column D for the %s handles %s (the sidebar does not say which faces they sit on; the file draws %d drawer fronts by unit name%s).'
                                   % (rn, PO_FIRST_ROW + len(po_rows) - 1, row['C'], row['E'], drawers_by_name,
                                      ('; doors drawn by the units: %d, not verified' % (S['face_counts']['doubtful_doors'] + S['face_counts']['doors'])) if S else ''))
            if not vend_named:
                guess = h.get('vendor')
                R['checks'].append('%s: Purchase Order row %d: the vendor for %s is not on the sidebar%s; type it in column K.'
                                   % (rn, PO_FIRST_ROW + len(po_rows) - 1, row['E'], (' (the number looks like %s)' % guess) if guess else ''))
        groups = {}
        for a in side.accessories:
            groups.setdefault((a['name'], a.get('part')), []).append(a)
        for (name, part), grp in groups.items():
            if not part:
                if not re.match(r'JT\b', name):
                    R['po_open'].append('%s x%d: no part number on the sidebar (stock item or library accessory; the engineer decides if it goes on the PO)' % (name, len(grp)))
                continue
            short = name.rstrip('*').strip()
            bad = next((c for k2, c in bad_parts.items() if k2 == short or short.startswith(k2) or k2.startswith(short)), None)
            if bad:
                R['checks'].append('%s: %s: the sidebar says part %s but the unit in the file says %s; not put on the Purchase Order until one of them is corrected.'
                                   % (rn, short, bad['sidebar'], bad['job']))
                R['po_open'].append('%s x%d: sidebar part %s, unit code %s (disagree)' % (short, len(grp), bad['sidebar'], bad['job']))
                continue
            vend_named = (grp[0].get('vendor_basis') or '') == 'named'
            po_rows.append({'B': rn.upper(), 'C': len(grp), 'D': short.upper(), 'E': part, 'K': grp[0]['vendor'] if vend_named else None,
                            'why': 'sidebar line %r (%d line%s = %d unit%s)' % (grp[0]['text'], len(grp), 's' if len(grp) > 1 else '', len(grp), 's' if len(grp) > 1 else '')})
            if not vend_named:
                R['checks'].append('%s: Purchase Order row %d: the vendor for %s is not on the sidebar%s; type it in column K.'
                                   % (rn, PO_FIRST_ROW + len(po_rows) - 1, part, (' (the number looks like %s)' % grp[0]['vendor']) if grp[0].get('vendor') else ''))
        for i, row in enumerate(po_rows):
            r = PO_FIRST_ROW + i
            tab = cells.setdefault('Purchase Order', {})
            for col in 'BCDEK':
                if row.get(col) not in (None, ''):
                    tab['%s%d' % (col, r)] = row[col]
                    cell_src.append(('Purchase Order', '%s%d' % (col, r), row[col], row['why']))
        # Doormark header
        d = st.get('door_drawer_style', {})
        if d.get('kind') == 'thermofoil' and not re.search(r'cf\s*thermo', d.get('style', ''), re.I):
            design = d.get('doormark_design')
            if design and design in dd.dm_designs:
                cells.setdefault('Doormark A1', {})['EM31'] = design
                cell_src.append(('Doormark A1', 'EM31', design, 'sidebar DOOR/DRAWER STYLE %r; the form looks the code (%s) up itself' % (d.get('style'), d.get('doormark_code'))))
                fd = funder_designs().get(d.get('doormark_code'))
                if fd is None and funder_designs():
                    R['notes'].append('%s: Doormark design code %s is in the workbook table but not on Doormark\'s quick reference sheet (1-15-25).' % (rn, d.get('doormark_code')))
            else:
                R['checks'].append('%s: Doormark door design %r is not in the workbook design list (Doormark A1 EM31); pick it in Excel.' % (rn, d.get('style')))
            colour = (d.get('colour') or '').strip()
            cu = colour.upper().replace(' SM', '').strip()
            fund = funder_colours()
            fcode = fund.get(cu) or next((c for n, c in fund.items() if cu and (cu in n or n in cu)), None)
            if cu and cu in dd.dm_colours:
                cells.setdefault('Doormark A1', {})['EM41'] = cu
                cell_src.append(('Doormark A1', 'EM41', cu, 'sidebar Color- line; the form looks the code (%s) up itself' % dd.dm_colours[cu]))
                if fcode and fcode != dd.dm_colours[cu]:
                    R['checks'].append('%s: Doormark colour %s: the workbook table gives code %s, Doormark\'s Funder sheet gives %s; confirm the code on the form.' % (rn, cu, dd.dm_colours[cu], fcode))
            elif colour:
                R['checks'].append('%s: Doormark colour %r is not in the workbook colour list, so Doormark A1 EM41 is blank; %s'
                                   % (rn, colour, ('Doormark\'s Funder sheet gives the code %s: type it on the form (the WERNER engineer typed MYST, a typo).' % fcode) if fcode else 'the engineer types the vendor code.'))
            else:
                R['checks'].append('%s: the sidebar has no Color- line under DOOR/DRAWER STYLE; the Doormark colour is blank.' % rn)
        elif d.get('kind') == 'thermofoil':
            R['notes'].append('%s: the sidebar says CF Thermo doors (%r): the CF Thermo tab; CF Thermo is no longer sold, so the engineer confirms.' % (rn, d.get('style')))
        elif d.get('kind') in ('cf5', 'elements', 'framed'):
            R['notes'].append('%s: door style %r goes on %s; its line items are in the list below, nothing was typed on the tab.'
                              % (rn, d.get('style'), {'cf5': 'the CF5 Order tab', 'elements': 'the Elements paper form', 'framed': 'a form the tool does not know'}[d['kind']]))
    for cell, val in entries_typed.items():
        if '!' in cell:
            tab, _, ref_ = cell.rpartition('!')
            cells.setdefault(tab.strip("'"), {})[ref_] = val
            cell_src.append((tab.strip("'"), ref_, val, 'typed by you'))

    # -- the price paste
    rows = []
    if price_path:
        lines, R['engine_flags'] = kcdbook.read_price_lines(price_path)
        rows, R['dropped'] = kcdbook.paste_rows(lines)
        R['pricing'] = '%d price lines from %s pasted into Data Entry K2..P%d (they add up to %.2f).' % (
            len(rows), price_path, 1 + len(rows), sum(r['K'] for r in rows if isinstance(r['K'], (int, float))))
    else:
        R['pricing'] = "nothing pasted: price this room file in KCD and paste the UNIT PRICE REVIEW into Data Entry K2..P (price, unit, part, size, size), or give --price \"%s=FILE.tsv\"." % rn

    # -- write and check
    rep = kcdbook.fill(template, xlsm, entries, rows, cells=cells, skip_bad=True)
    R['refused'] = rep['refused']
    R['verify'] = kcdbook.verify(template, xlsm, rep['sheet_parts'])
    R['xlsm'] = xlsm
    R['rows'] = rep['rows']
    written_main = {ref_: val for ref_, val in rep['written'].get('Data Entry', [])}
    for cell in sorted(entries, key=lambda c: (kcdbook.split_ref(c)[0], kcdbook.split_ref(c)[1])):
        if cell in written_main:
            R['entries'].append((cell, entries[cell], src[cell]))
    for tab, ref_, val, why in cell_src:
        if (ref_, val) in rep['written'].get(tab, []):
            R['cells'].append((tab, ref_, val, why))
    for s in rep['refused']:
        R['checks'].append('%s: the workbook refused a cell: %s' % (rn, s))
    for s in R['verify']:
        R['checks'].append('%s: workbook check: %s' % (rn, s))

    # -- for the engineer
    if S:
        for f in S['faces']:
            doubt = [x for x in f['flags'] if 'VERIFY' in x or 'not a real door' in x]
            kind = f['kind'] + ('s' if f['qty'] != 1 else '')
            pair = ' (a pair, KCD prints half the face; the elevation size is the one to type)' if f.get('pair') else ''
            style = ', '.join(x for x in (f.get('unit_door_type') or f.get('style_sidebar'), f.get('color_sidebar')) if x)
            R['faces'].append('unit %d (id %d) %s: %d %s %s x %s%s; %s; %s%s' % (
                f['unit_seq'], f['unit_id'], f['unit_name'].strip(), f['qty'], kind, f['width_txt'], f['height_txt'], pair, style or 'style not on the unit',
                FORM_WORDS.get(f['form'], f['form']), ('; NOT CERTAIN: ' + '; '.join(one_line(re.sub(r'\s*\(notes \d+\)', '', x), 140) for x in doubt)) if doubt else ''))
        for J in S['jewelry']:
            h = J.get('host')
            if h:
                R['vjt'].append('%s (unit %d) in drawer unit %d %s (W %s, D %s): insert %s, colour %s, %s; VJT numbers (inferred): shelf width %s, drawer box depth %s (%s), tray %s wide (single) or %s (top of a double), %s deep'
                                % (J['name'].strip(), J['unit_seq'], h['unit_seq'], h['name'].strip(), h['W'], h['D'], J['insert_vjt'], J['color_vjt'], J.get('layout_guess', ''),
                                   h['es_width'], h['drawer_box_depth_rule'], h['drawer_box_rule'], h['vjt_single_width'], h['vjt_dbl_top_width_formula'], h['vjt_depth']))
            else:
                R['vjt'].append('%s (unit %d): %s' % (J['name'].strip(), J['unit_seq'], '; '.join(J['flags']) or 'no drawer unit found under it'))
        for hw in S['hardware']:
            if hw['kind'] in ('po', 'ask') and not any(hw.get('part') and hw['part'] in r.get('E', '') for r in po_rows):
                R['po_open'].append('%s (unit %d)%s: %s' % (hw['name'].strip(), hw['unit_seq'], (' part %s from the unit code' % hw['part']) if hw.get('part') else '', hw['po']))
        for fl in S['flags']:
            if 'not in the library bundle' in fl:
                R['notes'].append('%s: %s' % (rn, fl))
    if side is not None:
        for fl in side.flags:
            if re.match(r'CHECK (door form|part number of)\b', fl):
                continue                        # kcdrun raised its own, more exact CHECK for these above
            fl = re.sub(r'\s*[\r\n]+\s*', ' / ', fl)
            if fl.startswith('CHECK'):
                R['checks'].append('%s: %s' % (rn, fl[len('CHECK'):].strip(' :')))
            elif fl.startswith('NOTE') and 'skill card' not in fl:
                R['notes'].append('%s: %s' % (rn, fl[len('NOTE'):].strip(' :')))
    if not R['faces']:
        R['faces'].append('no door or drawer front is drawn in this room file')
    if not R['vjt']:
        R['vjt'].append('none')
    if not R['po_open']:
        R['po_open'].append('none')

    text = room_report_text(R, template)
    with open(wrep, 'w', encoding='utf-8') as fh:
        fh.write(text + '\n')
    R['report'] = wrep
    R['text'] = text
    return R


def room_report_text(R, template):
    out = ['ROOM: %s' % R['room'],
           '  Room file:  %s' % R['job'],
           '  Workbook:   %s  (made from %s)' % (R['xlsm'], template),
           '  Data Entry answers written:']
    for cell, val, why in R['entries']:
        out.append('    %-4s = %-28s %s' % (cell, val if not isinstance(val, datetime.date) else val.isoformat(), why))
    if not R['entries']:
        out.append('    none')
    out.append('  Order tab cells written:')
    for tab, ref_, val, why in R['cells']:
        out.append('    %s!%-6s = %-20s %s' % (tab, ref_, val, why))
    if not R['cells']:
        out.append('    none')
    out.append('  Pricing: ' + R['pricing'])
    for l, why in R['dropped']:
        out.append('    left out: %s unit %d %s %s %s: %s' % (l['price'], l['unit'], l['part'], l['dim1'], l['dim2'], why))
    if R['suggest']:
        out.append('  Not written, for the engineer to confirm (inferred, check):')
        for cell, val, why in R['suggest']:
            out.append('    %-4s %-28s %s' % (cell, val, why))
    out.append('  For the engineer:')
    out.append('    Faces to size and type on the order tab (qty, KCD face width x height, style, colour):')
    out += ['      ' + s for s in R['faces']]
    out.append('    Jewelry trays (VJT Order tab):')
    out += ['      ' + s for s in R['vjt']]
    out.append('    Purchase order lines not written (not certain):')
    out += ['      ' + s for s in R['po_open']]
    if R['notes']:
        out.append('  Notes:')
        out += ['    ' + s for s in R['notes']]
    check = ('every other part of the workbook is byte for byte the template, the edited sheets parse and the workbook opens'
             if not R['verify'] else '; '.join(R['verify']))
    out.append('  Check of the file: ' + check + '.')
    out.append('  This workbook is a TEST file until the engineer has opened it in Excel.')
    return '\n'.join(out)


# ----------------------------------------------------------------------------- the RUN REPORT
def rem_suggestions(rep):
    """Designer, install date and sold price as the read-out's free-text notes mention them (suggestions only)."""
    notes = (rep or {}).get('rem_notes') or ''
    out, ref = [], {}
    m = re.search(r'designer\s+([A-Z][\w.\'-]*(?:\s+[A-Z][\w.\'-]*){0,2})', notes)
    if m:
        out.append(('F1', m.group(1).upper(), 'the remeasure sheet notes name the designer; give --designer to write it'))
    m = re.search(r'install\s+(\d{1,2})/(\d{1,2})/(\d{4})', notes, re.I)
    if m:
        out.append(('B1', '%s-%02d-%02d' % (m.group(3), int(m.group(1)), int(m.group(2))), 'install date from the remeasure sheet notes; give --install to write it'))
    m = re.search(r'total(?:\s+job)?\s+\$?([\d,]+(?:\.\d\d)?)', notes, re.I)
    if m:
        out.append(('B27', m.group(1), 'sold total from the remeasure sheet notes; give --sold (and --main for a multi-room job) to write it'))
    if re.search(r'\bcostco\b', notes, re.I):
        out.append(('B11', 'YES', 'the remeasure sheet notes say Costco; the template preset is NO'))
    for f in (rep or {}).get('facts', []):
        m = re.match(r'^(.*?)\s+MOLDING\s*=\s*(.*)$', f, re.I)
        if m and re.fullmatch(r'(none|no|n/a|-)', m.group(2).strip(), re.I):
            ref['molding_none'] = m.group(2).strip()
    return out, ref


def write_run_report(args, out_dir, client, test_no, ap, split_res, rooms, books, checks, not_done, suggestions, started):
    rp = os.path.join(out_dir, kcdsplit.file_part('%s %s RUN REPORT.txt' % (args.order, args.name)))
    L = ['RUN REPORT  %s %s  (%s)' % (args.order, args.name, client),
         'Made %s on %s by kcdrun.py. Every file named here is a TEST file until KCD or Excel has opened it.' % (started.strftime('%Y-%m-%d %I:%M %p'), socket.gethostname()),
         '',
         'WHAT WAS RUN',
         '  Job:        %s  (md5 %s)' % (args.job, md5(args.job))]
    if args.rem:
        L.append('  Remeasure:  %s' % args.rem)
        if ap.get('rep') and ap['rep'].get('rem_reader'):
            L.append('              read by: %s' % one_line(ap['rep']['rem_reader'], 160))
    else:
        L.append('  Remeasure:  none given, so only the fillers were checked.')
    L.append('  Order %s, name %s, client %s, test number %d, output folder %s.' % (args.order, args.name, client, test_no, out_dir))
    L.append('  Step 1  ' + (ap['note'] or 'remeasure applied.'))
    if ap.get('written'):
        L.append('          new job: %s  (md5 %s)' % (ap['written'], md5(ap['written'])))
    if ap.get('report'):
        L.append('          report:  %s' % ap['report'])
    if ap.get('fillers'):
        L.append('          fillers: %s.' % ap['fillers'])
    if split_res:
        L.append('  Step 2  split into %d room file%s in %s' % (len(rooms), 's' if len(rooms) != 1 else '', split_res['folder']))
        L.append('          split report: %s' % split_res['report'])
    elif args.no_split or args.workbooks_only:
        L.append('  Step 2  no split (%s).' % ('--workbooks-only' if args.workbooks_only else '--no-split'))
    if args.no_workbooks:
        L.append('  Step 3  no workbooks (--no-workbooks).')
    elif books:
        L.append('  Step 3  %d workbook%s from the template %s' % (len(books), 's' if len(books) != 1 else '', args.template))
    # wall changes
    L += ['', 'WALL CHANGES (step 1)']
    lines, same = trimmed_wall_lines(ap.get('rep'))
    if ap.get('rep') is None:
        L.append('  none: step 1 did not run.')
    else:
        L += ['  ' + s for s in lines] or ['  no wall changed.']
        if same:
            L.append('  %d wall%s measured the same as drawn and %s left alone.' % (same, 's' if same != 1 else '', 'were' if same != 1 else 'was'))
        if ap['rep'].get('facts'):
            L.append('  Room facts on the sheet (not applied to the job):')
            L += ['    ' + f for f in ap['rep']['facts']]
    L += ['', 'FILLERS (step 1)']
    fl, fchecks = fillers_block(ap.get('rep'))
    if fl:
        L += ['  ' + s for s in fl]
    else:
        L.append('  ' + (ap.get('fillers') or 'the filler step did not run') + '.')
    # checks
    L += ['', 'TO CHECK (%d)' % len(checks)]
    if checks:
        for i, c in enumerate(checks, 1):
            L.append('  %2d. %s' % (i, c))
    else:
        L.append('  nothing.')
    if suggestions:
        L += ['', 'NOT WRITTEN, FROM THE REMEASURE SHEET NOTES (check before typing):']
        for cell, val, why in suggestions:
            L.append('  %-4s %-20s %s' % (cell, val, why))
    # rooms
    for i, room in enumerate(rooms):
        L.append('')
        b = next((x for x in books if x['job'] == room['path'] and x['room'] == room['name']), None)
        if b:
            L.append(b['text'])
        else:
            L += ['ROOM: %s' % room['name'], '  Room file:  %s' % room['path'], '  Workbook:   none']
        if room.get('md5'):
            L.append('  Room file check: %d wall(s), %d cabinet(s), %d note(s); md5 %s' % (room['walls'], room['cabinets'], room['notes'], room['md5']))
        for lvl, msg in room.get('flags', []):
            if lvl == NOTE:
                L.append('  Note: ' + msg)
    L += ['', 'NOT DONE AND WHY']
    L += ['  - ' + s for s in not_done] or ['  - nothing was left out.']
    with open(rp, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L) + '\n')
    return rp


# ----------------------------------------------------------------------------- main
def parse_args(argv):
    ap = argparse.ArgumentParser(description='Apply a remeasure to a KCD job, split it into room files and fill a pricing workbook per room.')
    ap.add_argument('job', help="the designer's .job")
    ap.add_argument('--rem', help='the remeasure read-out JSON; without it only the fillers are checked')
    ap.add_argument('--order', required=True, help='the order (job) number, e.g. 1084476')
    ap.add_argument('--name', required=True, help='the customer last name for the file names, e.g. ROBERTS')
    ap.add_argument('--client', help='the client name for the TEST file names; default: the job file name without KCD')
    ap.add_argument('--out', required=True, help='the output folder')
    ap.add_argument('--test', type=int, help='the TEST number; default: the next free one in the output folder')
    ap.add_argument('--no-fillers', action='store_true', help='leave the end-filler step out')
    ap.add_argument('--no-heights', action='store_true', help='do not set the wall heights from the measured ceiling')
    ap.add_argument('--no-split', action='store_true', help='do not split into room files (the workbooks come from the whole job)')
    ap.add_argument('--no-workbooks', action='store_true', help='do not fill the workbooks')
    ap.add_argument('--workbooks-only', action='store_true', help='only the workbook step: no remeasure, no filler check, no split')
    ap.add_argument('--template', default=kcdbook.DEFAULT_TEMPLATE, help='the pricing workbook template (.xltm); default: the bundled one')
    ap.add_argument('--price', action='append', default=[], metavar='ROOM=TSV', help='a kcdprice.py TSV for one room, matched by room name (contains, any case)')
    ap.add_argument('--entry', action='append', default=[], metavar='CELL=VALUE', help='a Data Entry answer (B1=2026-11-04) or a tab cell ("Purchase Order!K19=AMEROCK"); wins over everything')
    ap.add_argument('--designer', help='the designer, as the workbook list spells it')
    ap.add_argument('--install', help='the install date, YYYY-MM-DD')
    ap.add_argument('--sold', type=float, help='the sold-at price (goes into the main room, see --main)')
    ap.add_argument('--main', help='the room that carries the sold-at price (name, contains); not needed for a one-room job')
    ap.add_argument('--replace', action='store_true', help='replace room files already in the output folder')
    return ap.parse_args(argv)


def check_inputs(args):
    if not os.path.isfile(args.job):
        raise StopRun('The job file %s does not exist.' % args.job)
    if not args.job.lower().endswith('.job'):
        raise StopRun('%s is not a .job file.' % args.job)
    with open(args.job, 'rb') as fh:
        head = fh.read(16)
    if head[2:14] != b'Version # 23':
        raise StopRun('%s is not a KCD version 23 job file.' % args.job)
    if args.rem:
        if not os.path.isfile(args.rem):
            raise StopRun('The remeasure file %s does not exist.' % args.rem)
        try:
            rem = kcdwalls.read_rem_json(args.rem)
        except Exception as e:
            raise StopRun('The remeasure file %s could not be read as a read-out (%s).' % (args.rem, one_line(e)))
        if not any(rem.get(k) for k in ('walls', 'walls_review', 'facts', 'angles', 'openings')):
            raise StopRun('The remeasure file %s has no wall lengths and no room facts in it; is it the right file?' % args.rem)
    if not re.fullmatch(r'\d{5,8}', args.order.strip()):
        raise StopRun('The order number must be 5 to 8 digits (you gave %r).' % args.order)
    args.order = args.order.strip()
    args.name = kcdsplit.clean(args.name)
    if not args.name or kcdsplit.file_part(args.name) != args.name:
        raise StopRun('The name %r cannot be used in a file name.' % args.name)
    if not os.path.isfile(args.template):
        raise StopRun('The workbook template %s does not exist.' % args.template)
    args.install = parse_date(args.install) if args.install else None
    if args.sold is not None and args.sold.is_integer():
        args.sold = int(args.sold)
    prices = []
    for p in args.price:
        room, _, path = p.partition('=')
        if not room.strip() or not path.strip():
            raise StopRun('--price needs ROOM=FILE.tsv, for example --price "PRIMARY HIS=his.tsv" (you gave %r).' % p)
        if not os.path.isfile(path.strip()):
            raise StopRun('The price file %s does not exist.' % path.strip())
        prices.append((room.strip(), path.strip()))
    args.prices = prices
    entries = {}
    for s in args.entry:
        cell, sep, val = s.partition('=')
        if not sep or not cell.strip():
            raise StopRun('--entry needs CELL=VALUE, for example --entry B13="Special Order" (you gave %r).' % s)
        cell = cell.strip()
        if '!' not in cell:
            try:
                kcdbook.split_ref(cell.upper())
            except ValueError:
                raise StopRun('%r is not a cell address like B13.' % cell)
            cell = cell.upper()
        entries[cell] = kcdbook.parse_entry_value(val)
    args.entries = entries
    try:
        os.makedirs(args.out, exist_ok=True)
    except OSError as e:
        raise StopRun('The output folder %s could not be made (%s).' % (args.out, e.strerror))
    args.out = os.path.abspath(args.out)


def main(argv=None):
    started = datetime.datetime.now()
    args = parse_args(argv)
    try:
        check_inputs(args)
    except StopRun as e:
        print(str(e))
        return 2
    out_dir = args.out
    client = args.client or default_client(args.job)
    test_no = args.test or next_test_number(out_dir)
    not_done, checks, books, rooms, split_res = [], [], [], [], None

    # step 1
    try:
        ap = step_apply(args, out_dir, client, test_no)
    except StopRun as e:
        print(str(e)); return 2
    except Exception as e:
        print('Step 1 (apply the remeasure) failed: %s. Nothing was written.' % one_line(e))
        traceback.print_exc(file=sys.stderr)
        return 1
    rep = ap.get('rep')
    if rep:
        checks += list(rep.get('checks', []))
        _, fch = fillers_block(rep)
        checks += [c for c in fch if c not in checks]
    suggestions, ref = rem_suggestions(rep)
    given = {'F1': args.designer, 'B1': args.install, 'B27': args.sold}
    suggestions = [s for s in suggestions if not given.get(s[0])]

    # step 2
    job_flags = []
    if args.no_split or args.workbooks_only:
        try:
            rooms, job_flags = planned_rooms(args, ap['job'])
        except kcdsplit.SplitError as e:
            not_done.append('The rooms could not be read (%s).' % e)
    else:
        try:
            split_res, rooms = step_split(args, ap['job'], out_dir)
            job_flags = split_res['job_flags']
        except StopRun as e:
            not_done.append('Step 2 (split) was not run: %s' % e)
            print(str(e))
        except kcdsplit.SplitError as e:
            not_done.append('Step 2 (split) failed: %s' % e)
        except Exception as e:
            not_done.append('Step 2 (split) failed: %s: %s' % (type(e).__name__, one_line(e)))
            traceback.print_exc(file=sys.stderr)
    for lvl, msg in job_flags:
        if lvl == CHECK:
            checks.append(msg)
    for room in rooms:
        for lvl, msg in room.get('flags', []):
            if lvl == CHECK:
                checks.append('%s: %s' % (room['name'], msg))

    # step 3
    if args.no_workbooks:
        not_done.append('No workbook was filled (--no-workbooks).')
    elif not rooms:
        not_done.append('No workbook was filled because there are no room files.')
    else:
        try:
            dd = Dropdowns(args.template)
        except Exception as e:
            dd = None
            not_done.append('The workbooks were not filled: the template\'s dropdown lists could not be read (%s: %s).' % (type(e).__name__, one_line(e)))
        cat = None
        if dd is not None:
            try:
                cat = kcdunits.default_catalog()
            except Exception as e:
                not_done.append('Door and drawer faces were not computed: %s' % one_line(e))
            for room in rooms:
                price = next((p for r, p in args.prices if key(r) and key(r) in key(room['name'])), None)
                is_main = 'only' if len(rooms) == 1 else (bool(args.main and key(args.main) and key(args.main) in key(room['name'])))
                try:
                    books.append(room_workbook(room, args, dd, cat, args.template, price, args.entries, is_main, ref))
                except Exception as e:
                    not_done.append('The workbook for %s was not made: %s: %s' % (room['name'], type(e).__name__, one_line(e)))
                    traceback.print_exc(file=sys.stderr)
            for r, p in args.prices:
                if not any(key(r) in key(room['name']) for room in rooms):
                    not_done.append('The price file for %r (%s) matched no room, so it was not pasted.' % (r, p))
            if args.main and len(rooms) > 1 and not any(key(args.main) in key(room['name']) for room in rooms):
                not_done.append('--main %r matched no room, so the sold-at price was not written anywhere.' % args.main)
            if args.sold is not None and len(rooms) > 1 and not args.main:
                not_done.append('The sold-at price was not written: with more than one room, say which one is the main closet with --main "ROOM".')
    for b in books:
        checks += b['checks']
    if not args.rem and not args.workbooks_only:
        not_done.append('No remeasure was applied (no --rem).')
    if 'did NOT run' in (ap.get('fillers') or '') or 'did not run' in (ap.get('fillers') or ''):
        not_done.append('The end-filler step did not run (%s).' % ap['fillers'])
    not_done.append('Door sizes were not typed on any order form: the size to order is the door-dimensioned elevation\'s, which the tool cannot settle yet; the faces are listed per room.')
    not_done.append('Nothing was typed on the VJT, CF5, CF Thermo and Job Cart Cover Sheet tabs; their values are inferred and listed per room.')
    rp = write_run_report(args, out_dir, client, test_no, ap, split_res, rooms, books, checks, not_done, suggestions, started)
    print(open(rp, encoding='utf-8').read())
    print('RUN REPORT: %s' % rp)
    failed = any('failed' in s or 'was not made' in s or 'was not run' in s for s in not_done)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
