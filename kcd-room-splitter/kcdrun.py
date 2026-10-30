#!/usr/bin/env python3
"""kcdrun.py - the one command of the production project.

It runs one remeasure end to end: apply the read-out to the designer's KCD job (walls, heights, same-size sections,
interior shelves, end fillers), split the result into one KCD file per room, fill one pricing workbook per room with
everything that is certain, and write one plain-English RUN REPORT for the engineer.

    python3 kcdrun.py JOB.job --rem REM.json --order 1084476 --name ROBERTS --client "Elizabeth Roberts" --out DIR
                      [--test N] [--no-fillers] [--no-heights] [--no-split] [--no-workbooks] [--workbooks-only]
                      [--template PATH] [--price "ROOM NAME=PRICE.tsv" ...] [--entry CELL=VALUE ...]
                      [--designer NAME] [--install YYYY-MM-DD] [--sold 5585] [--main "ROOM NAME"] [--replace]

    python3 kcdrun.py 1084476 [--jobs DIR | --inbox DIR --done DIR] [every other flag]
        Run by order number: DIR (default: the jobs/ folder at the repo root) holds one folder "1084476 <NAME>" with the
        designer's .job and the read-out REM-*.json; the name comes from the folder, the output goes to its out/ folder.

Without --rem the job gets the filler check only (kcdwalls.fillers_only), then the split and the workbooks.
--client defaults to the job's file name without "KCD". --test N defaults to the next free TEST number in DIR; a --test N
whose TEST job or RUN REPORT is already there is refused unless --replace.

Steps and the files they write (DIR = --out):
  1 apply      kcdwalls.apply_rem, filler step on        DIR/<Client> - REM <order> applied - TEST<N>.job  (+ " REPORT.txt")
               without --rem: kcdwalls.fillers_only       DIR/<Client> - fillers checked - TEST<N>.job (+ " REPORT.txt") when a
                                                          filler was added, else only DIR/<Client> - fillers checked.txt
  2 split      kcdsplit.split_job                        DIR/<order> <NAME> <ROOM>.job, one KCD file per room (these are the
                                                          files handed back; the whole-job TEST file is dropped unless --keep-whole)
  3 workbooks  kcdbook.fill from the bundled template    DIR/<order> <NAME> <ROOM>.xlsm  (+ " WORKBOOK REPORT.txt")
  4 report                                               DIR/<order> <NAME> RUN REPORT - TEST<N>.txt

The finished folder DIR holds ONLY the room files (.job) and the workbooks (.xlsm): it is moved as it is into the shop's
production folders (owner's rule, Oct 21 2026). Every report, the whole-job TEST file when kept, and the input files
taken from the in folder go to the reports folder WORK instead (--work; default C:\\grok rem reports\\<order> <NAME> next
to C:\\grok rem completed, or jobs/<order> <NAME>/reports in a cloud session, or "<DIR> reports" beside an --out DIR).
At the end of every run anything else left in DIR is moved to WORK, so the finished folder is clean without hand work.

Rules: nothing uncertain is written as a fact; a doubtful value becomes a CHECK line for the engineer that says what to
look at and what to do. An --entry you type wins over everything and is reported as "typed by you". Every file written
here is a TEST file until KCD has opened it. A bad input stops the run with one plain sentence; a failure in a later step
keeps the earlier outputs and the RUN REPORT says what was not done. The RUN REPORT is written for the owner, who reads
it on a phone: a path-free first screen, the output folder named once, no md5 or jargon in the owner text, and no other
customer's name (precedents belong in kcd-deep-dive-notes.md, not here).

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
                          F21 and F23 stay BLANK (with one CHECK that says what to type) when the remeasure sheet's
                          Molding fact for that room disagrees with the sidebar (NEDDIE, ROBERTS: sidebar base, sheet None)
    B25 main closet     = 'YES' and B27 sold-at price = --sold, only on the main room (--main, or the only room)
    never written: F13 F15 F17 C1 D26 D27 A27 (formulas), B3 B11 B13 B15 B17 B19 B21 B23 F3 F19 F25 (not certain from
    the job; B11 'NO', B17 'V23', F19 'Closet Factory', F25 'NO' are the template's own presets; B19 B21 B23 are
    suggested in the report when the sidebar points to special orders, finishing or specialty work)
  Purchase Order (rows 19, 20, ...; WERNER row 19 = B19 'OFFICE', C19 6, D19 'DOOR', E19 'BP36559CZ', K19 'AMEROCK';
  the template's rows 19-40 have the same plain cells with E:J merged):
    B room name (= B9), C quantity, D item, E part number, K vendor
    written for a handle line with a part number and a quantity on the sidebar (dashes removed, as WERNER typed it),
    and for an accessory RM line with a part number that agrees with the unit's own code; D only when it is certain
    which faces the handles sit on ('DOOR' when the room has no drawers at all); K only when the sidebar names the
    vendor (a vendor guessed from the number's shape is a CHECK, never written; a misspelt vendor word is corrected and
    the report says so)
  Doormark A1 (WERNER: EM31 'SARASOTA SHAKER' typed, AH31 = the SHS lookup; the colour code is a lookup from EM41):
    EM31 door design = the sidebar's TH door style as an exact entry of Data Conversions X3:X36
    EM41 door colour = the sidebar's Color- as an exact entry of X41:X58 (else CHECK with the Funder code)
    never written: door rows R/Y/AR 55, 61, 67 ... (door SIZES are the door-dimensioned elevation's and are not
    settled: WERNER followed (face - 1/8) / 2 for pairs, PRIEM did not), slab fillers CS/CZ/DT 166 and CO167 (4" x
    95 1/4 is nowhere in the job), CA31 (a formula the WERNER engineer typed over)
  VJT Order, CF5 Order, CF Thermo, Final Price Sheet, Job Cart Cover Sheet: nothing is written; every value we can
  compute is inferred and goes in the report as a suggestion.
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import re
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
DEFAULT_JOBS_DIR = os.path.normpath(os.path.join(HERE, '..', 'jobs'))
WIN_INBOX = r'C:\grok rem in'                 # Mike's in folder on his own computer: the KCD file and the scan go there
WIN_DONE = r'C:\grok rem completed'           # where a finished run lands, one folder per order


REPO_ROOT = os.path.normpath(os.path.join(HERE, '..'))


def default_inbox(order=None):
    """The in folder. On Mike's laptop the run project is cloned INTO the in folder (C:\\REM IN GIT, any name works),
    so the project's own folder is the in folder when the scan or read-out of this order sits at its top; else
    C:\\grok rem in when it exists; else none (the jobs/ folder is used, as in a cloud session)."""
    try:
        top = os.listdir(REPO_ROOT)
    except OSError:
        top = []
    if order and any(order in f and f.lower().endswith(('.pdf', '.json')) for f in top):
        return REPO_ROOT
    return WIN_INBOX if os.path.isdir(WIN_INBOX) else None


def default_done(inbox):
    if os.name == 'nt':
        return WIN_DONE
    return os.path.join(os.path.dirname(os.path.abspath(inbox)), 'grok rem completed')


def default_work(out_dir):
    """The reports folder of a run whose finished folder is out_dir: next to the done folder (C:\\grok rem completed\\X
    -> C:\\grok rem reports\\X), jobs/X/out -> jobs/X/reports, any other DIR -> 'DIR reports' beside it."""
    out_dir = os.path.abspath(out_dir)
    parent, base = os.path.split(out_dir)
    if os.path.basename(parent).lower() == 'grok rem completed':
        return os.path.join(os.path.dirname(parent), 'grok rem reports', base)
    if base.lower() == 'out':
        return os.path.join(parent, 'reports')
    return out_dir + ' reports'


FINISHED_KEEPS = ('.job', '.xlsm')            # the only files the finished folder holds (room files and workbooks)


def is_finished_file(name):
    """A room file or a workbook; a TEST job or a 'fillers checked' job is work, not a finished file."""
    return name.lower().endswith(FINISHED_KEEPS) and not TEST_RE.search(name) and 'fillers checked' not in name.lower()


def tidy_finished(out_dir, work_dir, ap, split_res, books):
    """Move everything but the finished room files and workbooks out of out_dir into work_dir, and keep the paths
    the RUN REPORT names in step. Nothing is deleted; a file of the same name in work_dir is replaced."""
    moved = {}
    for f in sorted(os.listdir(out_dir)):
        p = os.path.join(out_dir, f)
        if os.path.isfile(p) and not is_finished_file(f):
            os.makedirs(work_dir, exist_ok=True)
            q = os.path.join(work_dir, f)
            os.replace(p, q)
            moved[p] = q
    for d, k in [(ap, 'written'), (ap, 'report'), (split_res or {}, 'report')] + [(b, 'report') for b in books]:
        if d.get(k) in moved:
            d[k] = moved[d[k]]
    return moved
PO_FIRST_ROW = 19
TEST_RE = re.compile(r' - TEST(\d+)\b', re.I)
CHECK, NOTE = 'CHECK', 'NOTE'
CELL_WORDS = {'B1': 'install date', 'B5': 'order number', 'B7': 'name', 'B9': 'room', 'B11': 'Costco', 'B13': 'jewelry trays',
              'B15': 'hinge type', 'B19': 'other special orders', 'B21': 'finishing', 'B23': 'specialty work', 'B25': 'main closet',
              'B27': 'sold price', 'F1': 'designer', 'F5': 'material', 'F7': 'banding type', 'F9': 'banding colour',
              'F11': 'door/drawer type', 'F13': 'face colour', 'F21': 'molding', 'F23': 'molding location'}


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
    """'ELIZABETH ROBERTS KCD.job' -> 'ELIZABETH ROBERTS'; 'Lynn Neddie - TEST3 saved by KCD try3.job' -> 'Lynn Neddie';
    an engineer's room file '1089471 WERNER OFFICE.job' -> 'WERNER' (give --client for a fuller name)."""
    base = os.path.splitext(os.path.basename(job_path))[0]
    base = re.sub(r'\s*-\s*(TEST|REM)\d*\b.*$', '', base, flags=re.I)
    m = re.match(r'^\d{5,8}\s+(\S+)(?:\s+.*)?$', base)
    if m:
        return m.group(1)
    base = re.sub(r'\bKCD\b', '', base, flags=re.I)
    return re.sub(r'\s+', ' ', base).strip(' -_')


def next_test_number(out_dir, work_dir=None):
    n = 0
    for d in (out_dir, work_dir):
        if not d or not os.path.isdir(d):
            continue
        for f in os.listdir(d):
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
    """One line for an error text (owner text is never cut: this is only for exception messages)."""
    s = re.sub(r'\s+', ' ', str(s)).strip()
    return s if len(s) <= n else s[:n - 3] + '...'


def when(dt):
    """'Oct 20 2026, 2:23 AM' (no leading zero on the hour, on every platform)."""
    h = dt.hour % 12 or 12
    return '%s %d %d, %d:%02d %s' % (dt.strftime('%b'), dt.day, dt.year, h, dt.minute, 'PM' if dt.hour >= 12 else 'AM')


def plural(n, word, words=None):
    return '%d %s' % (n, word if n == 1 else (words or word + 's'))


def join_and(items):
    items = [str(x) for x in items]
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def rel(path, out_dir):
    """A file name relative to the output folder (the folder is named once in the report)."""
    if not path:
        return ''
    r = os.path.relpath(path, out_dir)
    return path if r.startswith('..') else r


def short_room_names(names):
    """'GUEST REACH-IN CLOSET' -> 'GUEST' when the first words of the rooms differ; else the full names (Primary hers/his)."""
    firsts = [n.split()[0].upper() if n.split() else n for n in names]
    if len(set(firsts)) == len(firsts):
        return dict(zip(names, firsts))
    return {n: n for n in names}


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
def step1_names(args, out_dir, client, test_no):
    """(the TEST job path, its REPORT path) for this run."""
    tag = ('REM %s applied' % args.order) if args.rem else 'fillers checked'
    out_job = os.path.join(out_dir, '%s - %s - TEST%d.job' % (client, tag, test_no))
    out_rep = os.path.join(args.work, '%s - %s - TEST%d REPORT.txt' % (client, tag, test_no))
    return out_job, out_rep


def run_report_path(args, out_dir, test_no):
    return os.path.join(args.work, kcdsplit.file_part('%s %s RUN REPORT - TEST%d.txt' % (args.order, args.name, test_no)))


def step_apply(args, out_dir, client, test_no):
    """Returns a dict: rep (kcdwalls report or None), job (the job to split: the written TEST file, or the input when
    nothing was written), report (path), note (what happened, one sentence), fillers (how the filler step went)."""
    out_job, out_rep = step1_names(args, out_dir, client, test_no)
    res = {'rep': None, 'job': args.job, 'report': None, 'note': '', 'fillers': '', 'written': None}
    if args.workbooks_only:
        res['note'] = 'Step 1 was skipped (only the workbooks were asked for): the job was used as it is.'
        return res
    want_fillers = not args.no_fillers
    rep = None
    if args.rem:
        rep = kcdwalls.apply_rem(args.job, args.rem, out_job, fillers=want_fillers, heights_from_rem=not args.no_heights)
        res['fillers'] = ('the filler step ran' if want_fillers else 'the filler step was turned off for this run')
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
            res['fillers'] += (': %s added' % plural(len(added), 'filler')) if added else ': nothing to add'
        title = 'Remeasure %s applied to %s' % (rep.get('rem_job'), os.path.basename(args.job))
    else:
        fn = getattr(kcdwalls, 'fillers_only', None)
        if fn is None or args.no_fillers:
            res['note'] = ('Step 1: no remeasure was given and the filler step was turned off, so the job was used as it is.'
                           if fn is not None else
                           'Step 1: no remeasure was given, and this copy of the tools has no filler check yet, so the job was used as it is.')
            res['fillers'] = 'the filler step did not run'
            return res
        rep = fn(args.job, out_job)
        added = (rep.get('fillers') or {}).get('added') or []
        res['fillers'] = 'the filler check ran (no remeasure given): ' + (('%s added' % plural(len(added), 'filler')) if added else 'nothing to add')
        if rep.get('written') and not (rep.get('fillers') or {}).get('changed', True) and os.path.exists(rep['written']):
            os.remove(rep['written'])                        # a byte-for-byte copy of the input is no TEST file
            rep['written'] = None
        if not rep.get('written'):
            out_rep = os.path.join(args.work, '%s - fillers checked.txt' % client)      # no TEST number when no job was written
        title = 'Fillers checked in %s' % os.path.basename(args.job)
    if args.rem and not rep.get('written'):
        out_rep = os.path.join(args.work, '%s - REM %s checked.txt' % (client, args.order))     # nothing applied, no TEST file
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
    """rep['lines'] without the filler block (fr['lines']) wherever kcdwalls put it (before the corner notes, or at the tail)."""
    lines = list(rep.get('lines', []))
    fr = rep.get('fillers')
    if isinstance(fr, dict) and fr.get('lines'):
        blk = list(fr['lines'])
        n = len(blk)
        for i in range(len(lines) - n, -1, -1):
            if lines[i:i + n] == blk:
                del lines[i:i + n]
                if i > 0 and not str(lines[i - 1]).strip():
                    del lines[i - 1]
                break
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
    """The filler block of the step-1 report, rendered whatever shape it has (list of lines, dict, text)."""
    if not rep or 'fillers' not in rep or rep['fillers'] in (None, '', [], {}):
        return [], []
    fb = rep['fillers']
    lines, checks = [], []
    if isinstance(fb, dict):
        lines = [str(x) for x in fb.get('lines', [])]
        checks = [str(x) for x in fb.get('checks', [])]
        if not lines:
            lines = ['the filler step ran and found nothing to add']
    elif isinstance(fb, (list, tuple)):
        for x in fb:
            s = str(x)
            (checks if s.lstrip().startswith('CHECK') else lines).append(s)
    else:
        lines = str(fb).splitlines()
    return lines, checks


def filler_summary(rep, shorts):
    """(added phrase, holds count): '1 filler added (GUEST wall 6, end)', 3."""
    fr = (rep or {}).get('fillers')
    if not isinstance(fr, dict):
        return None, 0
    added = fr.get('added') or []
    holds = [f for f in fr.get('findings', []) if isinstance(f, dict) and f.get('hold') == 'hold']
    where = []
    for a in added:
        if isinstance(a, dict):
            room = next((f.get('room') for f in fr.get('findings', []) if isinstance(f, dict) and f.get('wall') == a.get('wall') and f.get('end') == a.get('end')), '')
            room = next((s for n, s in shorts.items() if room and (key(room) in key(n) or key(n) in key(room))), room)
            where.append('%swall %s, %s' % ((room + ' ') if room else '', a.get('wall'), a.get('end')))
    phrase = ('%s added (%s)' % (plural(len(added), 'filler'), '; '.join(where))) if added else 'nothing to add'
    return phrase, len(holds)


# ----------------------------------------------------------------------------- step 2: split
def step_split(args, job_path, out_dir):
    job = kcdsplit.Job(open(job_path, 'rb').read())
    files, job_flags = kcdsplit.plan(job, args.order, args.name)
    folder = kcdsplit.job_folder(out_dir, args.order, args.name)
    there = kcdsplit.existing_files(files, folder)
    if there and not args.replace:
        raise StopRun('Room files for this job are already in %s (%s). Run again with --replace to replace them, or give another output folder.'
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
FORM_WORDS = {'IN HOUSE': 'cut in house, no order form', 'DOORMARK': 'Doormark form', 'CF5': 'CF5 form',
              'CF THERMO': 'CF Thermo form', 'ELEMENTS': 'Elements form', 'NONE': 'the sidebar says no faces',
              'ASK': 'which form is not settled'}
ORDER_FORMS = ('DOORMARK', 'CF5', 'CF THERMO', 'ELEMENTS')


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


def tidy_style(st):
    """'SARASOTA  Shaker TH' -> 'Sarasota Shaker thermofoil'."""
    st = re.sub(r'\s+', ' ', (st or '')).strip()
    st = ' '.join(w.title() if w.isupper() and len(w) > 2 else w for w in st.split())
    return re.sub(r'\b(TH|Th)\b$', 'thermofoil', st).strip()


def style_words(f):
    """'Sarasota Shaker thermofoil, MYSTERIOUS BLUE' from a face entry (the sidebar's style first: it wins over the unit's);
    '' when the unit and the sidebar name no style."""
    st = tidy_style(f.get('style_sidebar') or f.get('unit_door_type'))
    col = (f.get('color_sidebar') or '').strip()
    return ', '.join(x for x in (st, col) if x)


def face_items(faces):
    """['2 doors 17 15/16 x 80 9/16 (a pair)', '2 drawer fronts 31 3/8 x 7 1/2'] with equal faces counted together."""
    counts = {}
    order = []
    for f in faces:
        k = (f['kind'], f['width_txt'], f['height_txt'], bool(f.get('pair')))
        if k not in counts:
            order.append(k)
        counts[k] = counts.get(k, 0) + (f['qty'] if f.get('pair') else f['qty'])
    out = []
    for k in order:
        kind, w, h, pair = k
        q = counts[k]
        if pair:
            out.append('%s %s x %s (%s)' % (plural(q, kind), w, h, 'a pair' if q == 2 else '%d pairs' % (q // 2)))
        else:
            out.append('%s %s x %s' % (plural(q, kind), w, h))
    return out


def doubtful(f):
    return any(('VERIFY' in x) or ('not a real door' in x) for x in f.get('flags', []))


def face_notes(f):
    """The soitems flags of a face as short owner notes (no VERIFY, no preset names, no guesses)."""
    out = []
    for x in f.get('flags', []):
        s = re.sub(r'^VERIFY:\s*', '', x).strip()
        if s.startswith('sizes read from the drawing') or s.startswith('a pair: KCD gives'):
            continue                                   # said once for the whole block
        if 'the sidebar says no doors' in s:
            continue
        out.append(s)
    return out


def faces_text(S, side, uj):
    """The 'Doors and drawer fronts' block of a room, as plain text lines."""
    faces = S['faces'] if S else []
    out = []
    if not faces:
        return ['Doors and drawer fronts: none drawn in this room file.']
    side_none = side is not None and side.structured['door_drawer_style'].get('kind') == 'none'
    unit_names = []
    for f in faces:
        nm = f['unit_name'].strip()
        if nm not in unit_names:
            unit_names.append(nm)
    kinds = sorted({f['kind'] for f in faces})
    what = ' and '.join(k + 's' for k in kinds).replace('drawer fronts', 'drawer fronts')
    if side_none:
        shelving = all(any('open shelving' in x for x in f['flags']) for f in faces)
        txt = 'Doors and drawer fronts: the sidebar says none. The drawing hints at %s on %s (%s); %s.' % (
            what, plural(len(unit_names), 'open-shelving unit' if shelving else 'unit'), ', '.join(unit_names),
            'most likely there are none' if shelving else 'the sidebar wins unless the elevation shows them')
        styles = sorted({tidy_style(f.get('unit_door_type')) for f in faces if (f.get('unit_door_type') or '').strip()})
        if all(f['form'] in ('IN HOUSE', 'NONE') for f in faces) and all(re.search(r'melamine', x, re.I) for x in styles):
            txt += ' If the designer did sell %s there, they are melamine, cut in house, no order form.' % what
        else:
            txt += ' If the designer did sell them, the units say %s (%s).' % (join_and(styles), ' / '.join(sorted({FORM_WORDS.get(f['form'], f['form']) for f in faces})))
        txt += ' KCD face sizes: %s.' % ', '.join('%s x %s%s' % (f['width_txt'], f['height_txt'], ' (a pair)' if f.get('pair') else '') for f in faces)
        return [txt]
    # the sidebar names a door style (or there is no sidebar): one short line per unit
    by_unit = []
    for f in faces:
        hit = next((b for b in by_unit if b['seq'] == f['unit_seq']), None)
        if hit is None:
            hit = {'seq': f['unit_seq'], 'name': f['unit_name'].strip(), 'wall': f.get('wall'), 'faces': []}
            by_unit.append(hit)
        hit['faces'].append(f)
    names = [b['name'] for b in by_unit]
    out.append('Doors and drawer fronts (%s):' % ('the sidebar says %s' % tidy_style(side.structured['door_drawer_style'].get('style')) if side is not None else 'no sidebar in this room'))
    xs = {u.seq: u.X for u in uj.units} if uj is not None else {}
    for b in by_unit:
        label = b['name']
        if names.count(b['name']) > 1:
            at = ''
            if b['seq'] in xs:
                at = ', at the wall start' if abs(xs[b['seq']]) < 0.03 else ', %s from the wall start' % frac(soitems.r16(xs[b['seq']]))
            label = '%s (wall %s%s)' % (b['name'], b['wall'], at)
        forms = {f['form'] for f in b['faces']}
        form = ' / '.join(FORM_WORDS.get(x, x) for x in sorted(forms))
        parts = [', '.join(face_items(b['faces']))]
        sw = style_words(b['faces'][0])
        if sw:
            parts.append(sw)
        parts.append(form)
        line = '  %s: %s' % (label, ', '.join(parts))
        notes = []
        f0 = b['faces'][0]
        if (f0.get('unit_door_type') or '').strip() and (f0.get('style_sidebar') or '').strip() and key(f0['unit_door_type']) != key(f0['style_sidebar']):
            notes.append('the unit says %s; the sidebar wins' % tidy_style(f0['unit_door_type']))
        for f in b['faces']:
            for n in face_notes(f):
                if n not in notes:
                    notes.append(n)
        if notes:
            line += '. Note: ' + '; '.join(notes)
        out.append(line)
    # the kcdcab single/pair doubts, by unit name
    if S:
        by_seq = {}
        if uj is not None:
            by_seq = {u.seq: u.kcd_name.strip() for u in uj.units}
        for fl in S.get('flags', []):
            m = re.match(r'unit (\S+) door D(\d+): record says (\w+), width ([\d.]+)" suggests (\w+); verify', fl)
            if m:
                out.append('  Note: %s: the file says a %s door, its width (%s) suggests a %s; check which.' % (
                    by_seq.get(int(m.group(1)), 'unit %s' % m.group(1)) if m.group(1).isdigit() else m.group(1), m.group(3), frac(float(m.group(4))), m.group(5)))
                continue
            m = re.match(r'unit (\S+) door D(\d+) is ([\d.]+)" wide, near the pair threshold ([\d.]+)" and the record gives no hint; verify single vs pair', fl)
            if m:
                out.append('  Note: %s: a door %s wide is close to the single/pair limit (%s); check single or pair.' % (
                    by_seq.get(int(m.group(1)), 'unit %s' % m.group(1)) if m.group(1).isdigit() else m.group(1), frac(float(m.group(3))), frac(float(m.group(4)))))
    if any(str(f.get('source', '')).startswith('cab geometry') for f in faces):
        out.append('  These sizes are read from the drawing; a unit drawn without doors still shows its door sizes here, so check the elevation.')
    if any(f['form'] in ORDER_FORMS for f in faces):
        out.append('  The size to order is the size on the door elevation, not the KCD face size; nothing was typed on the order tab.')
    return out


def molding_for_room(ref, room):
    """The remeasure sheet's Molding fact for this room ('None', 'NO', '3 1/4 base' ...), or None."""
    for rname, val in (ref.get('molding') or {}).items():
        if key(rname) == key(room['name']) or key(rname) in key(room['name']) or key(room['name']) in key(rname):
            return val
    return None


def room_workbook(room, args, dd, cat, template, price_path, entries_typed, is_main, ref, out_dir):
    """Fill one room's workbook. Returns a dict with everything the reports need. Never raises for a refused cell."""
    R = {'room': room['name'], 'job': room['path'], 'xlsm': None, 'report': None, 'entries': [], 'cells': [], 'suggest': [],
         'checks': [], 'notes': [], 'faces': [], 'vjt': [], 'po_open': [], 'pricing': '', 'refused': [], 'verify': [], 'rows': 0,
         'dropped': [], 'engine_flags': [], 'price_lines': [], 'molding_blank': False, 'has_faces': False, 'priced': bool(price_path)}
    folder = os.path.dirname(room['path']) if room['md5'] else args.out
    xlsm = os.path.join(folder, room['base'] + '.xlsm')
    wrep = os.path.join(args.work, room['base'] + ' WORKBOOK REPORT.txt')
    rn = room['name']

    # -- the sidebar and the special-order sheet of this file
    sj, sides, missing = sidebar_mod.parse_job(room['path'])
    side = pick_sidebar([s for s in sides if s.room in room['rooms']] or sides, room)
    price_lines = soitems.read_price_tsv(price_path) if price_path else []
    sheet = {}
    uj = None
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
    put('B7', args.name.upper(), 'the last name in capitals, as the engineers type it')
    put('B9', rn.upper(), 'the room name of the room file; engineers often shorten it (OFFICE for HOME OFFICE, RIC for REACH-IN CLOSET)')
    if len(rn.split()) > 1:
        R['notes'].append('%s: the room name has %d words; engineers often type a short form in B9 (RIC for REACH-IN CLOSET, WIC for WALK-IN CLOSET). If you shorten it, rename the room file the same way.' % (rn, len(rn.split())))
    if args.install:
        put('B1', args.install, 'the install date you gave')
    if args.designer:
        ex = dd.exact('F1', args.designer)
        if ex:
            put('F1', ex, 'the designer you gave (spelled as the workbook list has it)')
        else:
            put('F1', args.designer, 'the designer you gave; NOT in the workbook designer list, so check the spelling')
            R['checks'].append("%s: designer %s is not in the workbook's designer list (Data Entry F1); it was written as you typed it. Check the spelling against the list." % (rn, args.designer))
    if side is not None:
        for cell, v in side.forms['workbook'].items():
            val, cert, why = v.get('value'), v.get('certainty'), v.get('source', '')
            if val in (None, ''):
                continue
            if cert == 'certain':
                ex = dd.exact(cell, val)
                if ex is None:
                    R['checks'].append("%s: %s %s: the sidebar says %s, which is not one of the workbook's list entries, so it was left blank; pick the closest list entry in Excel." % (rn, cell, CELL_WORDS.get(cell, ''), val))
                    R['suggest'].append("%s %s: left blank. The sidebar says %s, which is not one of the workbook's list entries; pick the closest list entry." % (cell, CELL_WORDS.get(cell, ''), val))
                else:
                    put(cell, ex, 'sidebar: ' + why)
            else:
                R['suggest'].append('%s %s: left blank. %s' % (cell, CELL_WORDS.get(cell, ''), why if why.endswith('.') else ('The sidebar gives %s (%s).' % (val, why))))
    # the remeasure sheet's Molding fact against the sidebar's base/crown lines: when they disagree, F21/F23 stay blank
    sheet_mold = molding_for_room(ref, room)
    if sheet_mold is not None and side is not None:
        st = side.structured
        sheet_none = bool(re.fullmatch(r'(none|no|n/a|-)', sheet_mold.strip(), re.I))
        side_loc = (side.forms['workbook'].get('F23') or {}).get('value')
        side_none = side_loc in (None, 'None')
        if sheet_none != side_none:
            f21, f23 = entries.get('F21') or (side.forms['workbook'].get('F21') or {}).get('value'), side_loc
            entries.pop('F21', None); entries.pop('F23', None)
            R['suggest'] = [s for s in R['suggest'] if not s.startswith(('F21 ', 'F23 '))]
            R['molding_blank'] = True
            if not side_none:
                said, what = [], []
                for lab, k2 in (('BASE', 'base'), ('CROWN', 'crown')):
                    e = st.get(k2) or {}
                    if e.get('present') and (e.get('qty') or 0) > 0:
                        said.append('%s %s (qty %d)' % (lab, e.get('type') or e.get('text'), int(e['qty'])))
                        what.append(k2)
                R['checks'].append('%s: Molding left blank. The sidebar says %s, the remeasure sheet says Molding %s. If %s sold, set Data Entry F21 = %s and F23 = %s; if not, both None.'
                                   % (rn, ' and '.join(said), sheet_mold, ('%s is' % what[0]) if len(what) == 1 else (' and '.join(what) + ' are'), f21, f23))
            else:
                R['checks'].append('%s: Molding left blank. The sidebar has no BASE or CROWN line, the remeasure sheet says Molding %s. If molding is sold, set Data Entry F21 (its type) and F23 (where it goes); if not, both None.'
                                   % (rn, sheet_mold))
    if is_main and args.sold is not None:
        put('B25', 'YES', 'this is the main room (%s), so it carries the sold-at price' % ('the only room' if is_main == 'only' else 'the one you named'))
        put('B27', args.sold, 'the sold-at price you gave')
    elif args.sold is not None:
        R['suggest'].append('B27 sold price: left blank. %s was given, but with more than one room the run must be told which room is the main closet (B25); it was not written anywhere.' % args.sold)
    for cell, val in entries_typed.items():
        if '!' in cell:
            continue
        put(cell, val, 'typed by you')

    # -- order tabs
    cells, cell_src = {}, []
    po_rows = []
    handle_checks = []
    if side is not None:
        st = side.structured
        drawers_by_name = side.drawer_fronts_from_names
        box = (st.get('drawer_box', {}).get('type') or '').lower()
        no_drawers = ('no drawer' in box) and drawers_by_name == 0
        bad_parts = {c['what'].replace('part number of ', ''): c for c in side.checks if c['what'].startswith('part number of') and c['agree'] is False}
        for h in side.handles:
            qty_txt = ('%d' % h['qty']) if h.get('qty') not in (None, 0) and float(h['qty']).is_integer() else str(h.get('qty') or '?')
            if not h.get('part') or h.get('qty') in (None, 0):
                if h.get('stock_mark'):
                    handle_checks.append('%s: the %s (qty %s) is a stock handle with no part number, so it is not on the Purchase Order. If it should be, type the part number and vendor on Purchase Order row %%d.' % (rn, h['name'], qty_txt))
                else:
                    handle_checks.append('%s: the %s (qty %s) has no part number on the sidebar, so it is not on the Purchase Order. Find the part number and type it with the vendor on Purchase Order row %%d.' % (rn, h['name'], qty_txt))
                continue
            basis = h.get('vendor_basis') or ''
            vend_named = basis.startswith('named')
            spelled = basis.partition(', ')[2] if ', ' in basis else ''
            item = 'DOOR' if no_drawers else None
            row = {'B': rn.upper(), 'C': int(h['qty']) if float(h['qty']).is_integer() else h['qty'], 'D': item, 'E': h['part'].replace('-', ''),
                   'K': h['vendor'] if vend_named else None,
                   'why': 'sidebar handle line %r%s%s' % (h['text'], (' + ' + h['typed_line']) if h.get('typed_line') else '',
                                                           (' (vendor %s)' % spelled) if spelled else '')}
            po_rows.append(row)
            if item is None:
                R['checks'].append('%s: Purchase Order row %d: type DOOR or DRAWER in column D for the %s handles %s; the sidebar does not say which faces they sit on (the file draws %d drawer fronts by unit name%s).'
                                   % (rn, PO_FIRST_ROW + len(po_rows) - 1, row['C'], row['E'], drawers_by_name,
                                      ('; doors drawn by the units: %d, not verified' % (S['face_counts']['doubtful_doors'] + S['face_counts']['doors'])) if S else ''))
            if not vend_named:
                guess = h.get('vendor')
                R['checks'].append('%s: Purchase Order row %d: the vendor of %s is not on the sidebar%s; type the vendor in column K.'
                                   % (rn, PO_FIRST_ROW + len(po_rows) - 1, row['E'], (' (the number has the %s shape)' % guess.title()) if guess else ''))
        groups = {}
        for a in side.accessories:
            groups.setdefault((a['name'], a.get('part')), []).append(a)
        for (name, part), grp in groups.items():
            if not part:
                if not re.match(r'JT\b', name):
                    R['po_open'].append('%s x%d: no part number on the sidebar (a stock item or a library accessory; the engineer decides if it goes on the Purchase Order).' % (name, len(grp)))
                continue
            short = name.rstrip('*').strip()
            bad = next((c for k2, c in bad_parts.items() if k2 == short or short.startswith(k2) or k2.startswith(short)), None)
            if bad:
                R['checks'].append('%s: %s: the sidebar says part %s but the unit in the file says %s; it is not on the Purchase Order until one of them is corrected.'
                                   % (rn, short, bad['sidebar'], bad['job']))
                R['po_open'].append('%s x%d: the sidebar says part %s, the unit says %s (they disagree).' % (short, len(grp), bad['sidebar'], bad['job']))
                continue
            basis = grp[0].get('vendor_basis') or ''
            vend_named = basis.startswith('named')
            spelled = basis.partition(', ')[2] if ', ' in basis else ''
            po_rows.append({'B': rn.upper(), 'C': len(grp), 'D': short.upper(), 'E': part, 'K': grp[0]['vendor'] if vend_named else None,
                            'why': 'sidebar line %r (%s = %s)%s' % (grp[0]['text'], plural(len(grp), 'line'), plural(len(grp), 'unit'), (' (vendor %s)' % spelled) if spelled else '')})
            if not vend_named:
                R['checks'].append('%s: Purchase Order row %d: the vendor of %s is not on the sidebar%s; type the vendor in column K.'
                                   % (rn, PO_FIRST_ROW + len(po_rows) - 1, part, (' (the number has the %s shape)' % grp[0]['vendor'].title()) if grp[0].get('vendor') else ''))
        for s in handle_checks:
            R['checks'].append(s % (PO_FIRST_ROW + len(po_rows)))
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
                    R['notes'].append('%s: the Doormark design code %s is in the workbook table but not on Doormark\'s quick reference sheet (1-15-25).' % (rn, d.get('doormark_code')))
            else:
                R['checks'].append("%s: the Doormark door design %s is not in the workbook's design list (Doormark A1 EM31), so it was left blank; pick it in Excel." % (rn, d.get('style')))
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
                R['checks'].append("%s: the Doormark colour %s is not in the workbook's colour list, so Doormark A1 EM41 is blank; %s"
                                   % (rn, colour, ("Doormark's Funder sheet gives the code %s: type it on the form." % fcode) if fcode else 'type the vendor code on the form.'))
            else:
                R['checks'].append('%s: the sidebar has no Color- line under DOOR/DRAWER STYLE, so the Doormark colour is blank; type it on the form.' % rn)
        elif d.get('kind') == 'thermofoil':
            R['notes'].append('%s: the sidebar says CF Thermo doors (%s): the CF Thermo tab; CF Thermo is no longer sold, so the engineer confirms.' % (rn, d.get('style')))
        elif d.get('kind') in ('cf5', 'elements', 'framed'):
            R['notes'].append('%s: door style %s goes on %s; its faces are listed below, nothing was typed on the tab.'
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
        R['pricing'] = '%s from %s pasted into the price block of Data Entry (columns K to P from row 2); they add up to %.2f.' % (
            plural(len(rows), 'price line'), os.path.basename(price_path), sum(r['K'] for r in rows if isinstance(r['K'], (int, float))))
    else:
        R['pricing'] = 'nothing pasted: price this room file in KCD and paste the UNIT PRICE REVIEW into the price block of Data Entry (columns K to P from row 2), or give the run a price file for this room.'

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
    R['faces'] = faces_text(S, side, uj)
    R['has_faces'] = bool(S and S['faces'])
    if S:
        for J in S['jewelry']:
            h = J.get('host')
            if h:
                R['vjt'].append('%s in the %s (W %s, D %s): insert %s, colour %s, %s. VJT numbers (not typed, check): shelf width %s, drawer box depth %s (%s), tray %s wide (single) or %s (top of a double), %s deep.'
                                % (J['name'].strip(), h['name'].strip(), h['W'], h['D'], J['insert_vjt'], J['color_vjt'],
                                   re.sub(r'\s*\(two trays on unit \d+;', ' (two trays on this unit;', J.get('layout_guess', '')),
                                   h['es_width'], h['drawer_box_depth_rule'], h['drawer_box_rule'], h['vjt_single_width'], h['vjt_dbl_top_width_formula'], h['vjt_depth']))
            else:
                R['vjt'].append('%s: %s' % (J['name'].strip(), '; '.join(J['flags']) or 'no drawer unit found under it'))
        for hw in S['hardware']:
            if hw['kind'] in ('po', 'ask') and not any(hw.get('part') and hw['part'] in r.get('E', '') for r in po_rows):
                R['po_open'].append('%s%s: %s.' % (hw['name'].strip(), (' (part %s from the unit code)' % hw['part']) if hw.get('part') else '',
                                                   hw['po'].replace('ASK (no part number in the job)', 'no part number in the job; the engineer decides')))
        for fl in S['flags']:
            if 'not in the library bundle' in fl:
                m = re.match(r'unit (\d+) \(id \d+\): (.*) not in the library bundle, faces unknown', fl)
                R['notes'].append('%s: %s' % (rn, ('the unit %s is not in the library bundle, so its doors and drawer fronts could not be read' % m.group(2)) if m else fl))
    if side is not None:
        for fl in side.flags:
            if re.match(r'CHECK (door form|part number of|PO)\b', fl):
                continue                        # kcdrun raised its own, more exact CHECK for these above
            fl = re.sub(r'\s*[\r\n]+\s*', ' / ', fl)
            if fl.startswith('CHECK'):
                R['checks'].append('%s: %s' % (rn, fl[len('CHECK'):].strip(' :')))
            elif fl.startswith('NOTE') and 'skill card' not in fl:
                R['notes'].append('%s: %s' % (rn, fl[len('NOTE'):].strip(' :')))
        # suggestions for the other tabs (not written): Final Price Sheet accessory lines, items that need pricing, drawer count
        st = side.structured
        acc = []
        ct = st.get('countertop') or {}
        if ct.get('text'):
            acc.append('countertop %s%s%s' % (ct.get('type') or ct.get('text'), (', colour %s' % ct['colour']) if ct.get('colour') else '',
                                              (', %s sqft' % frac(ct['area_sqft'])) if ct.get('area_sqft') else ''))
        for lab, k2 in (('base', 'base'), ('crown', 'crown')):
            e = st.get(k2) or {}
            if e.get('present') and (e.get('qty') or 0) > 0:
                acc.append('%s %s%s x%d%s' % (lab, e.get('type') or e.get('text'), (', %s' % e['length']) if e.get('length') else '', int(e['qty']),
                                              (', colour %s' % e['colour']) if e.get('colour') else ''))
        if acc:
            R['price_lines'].append('Final Price Sheet accessory lines to type (prices from the shop table): %s.%s' % ('; '.join(acc),
                                    ' The base/crown line only if molding is sold (see the CHECK on the molding).' if R['molding_blank'] else ''))
        need = ['%s x%d' % (h['part'].replace('-', ''), int(h['qty'])) for h in side.handles if h.get('part') and h.get('qty')]
        need += ['%s x%d%s' % (part, len(grp), ' (part number disputed, see the CHECK)' if any(k2 == name.rstrip('*').strip() or name.rstrip('*').strip().startswith(k2) for k2 in bad_parts) else '')
                 for (name, part), grp in groups.items() if part]
        if need:
            R['price_lines'].append('Items That Need Pricing: %s.' % ', '.join(need))
        box = (st.get('drawer_box', {}).get('type') or '')
        if 'no drawer' in box.lower():
            R['price_lines'].append('Job Cart Cover Sheet Drawer Count: N/A (no drawer boxes).')
        elif side.drawer_fronts_from_names:
            R['price_lines'].append('Job Cart Cover Sheet Drawer Count: %d, counted from the unit names; check it against the elevation.' % side.drawer_fronts_from_names)
    if not R['vjt']:
        R['vjt'].append('none')
    if not R['po_open']:
        R['po_open'].append('none')

    text = room_report_text(R, out_dir)
    with open(wrep, 'w', encoding='utf-8') as fh:
        fh.write(text + '\n')
    R['report'] = wrep
    R['text'] = text
    return R


def room_report_text(R, out_dir):
    out = ['ROOM: %s' % R['room'],
           '  Room file:  %s' % rel(R['job'], out_dir),
           '  Workbook:   %s' % rel(R['xlsm'], out_dir),
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
        out.append('  Not written, for the engineer to confirm:')
        for s in R['suggest']:
            out.append('    ' + s)
    out.append('  ' + R['faces'][0])
    out += ['  ' + s for s in R['faces'][1:]]
    out.append('  Jewelry trays (VJT Order tab):')
    out += ['    ' + s for s in R['vjt']]
    out.append('  Not on the Purchase Order (not certain):')
    out += ['    ' + s for s in R['po_open']]
    if R['price_lines']:
        out.append('  Suggested, not typed:')
        out += ['    ' + s for s in R['price_lines']]
    if R['notes']:
        out.append('  Notes:')
        out += ['    ' + s for s in R['notes']]
    check = ('the workbook is the template with only these cells changed, and it opens' if not R['verify'] else '; '.join(R['verify']))
    out.append('  Check of the file: ' + check + '.')
    out.append('  This workbook is a TEST file until the engineer has opened it in Excel.')
    return '\n'.join(out)


# ----------------------------------------------------------------------------- the RUN REPORT
def rem_suggestions(rep):
    """Designer, install date, sold price and Costco as the read-out's free-text notes mention them (suggestions only,
    full sentences for the report), and the sheet's Molding fact per room."""
    notes = (rep or {}).get('rem_notes') or ''
    out, ref = [], {'molding': {}}
    m = re.search(r'designer\s+([A-Z][\w.\'-]*(?:\s+[A-Z][\w.\'-]*){0,2})', notes)
    if m:
        out.append(('F1', m.group(1).upper(), 'F1 designer: %s, read from the sheet notes, not typed: confirm it and type it (or give it to the run as certain).' % m.group(1).upper()))
    m = re.search(r'install\s+(\d{1,2})/(\d{1,2})/(\d{4})', notes, re.I)
    if m:
        d = '%s-%02d-%02d' % (m.group(3), int(m.group(1)), int(m.group(2)))
        out.append(('B1', d, 'B1 install date: %s, read from the sheet notes, not typed: confirm it and type it (or give it to the run as certain).' % d))
    m = re.search(r'total(?:\s+job)?\s+\$?([\d,]+(?:\.\d\d)?)', notes, re.I)
    if m:
        out.append(('B27', m.group(1), 'B27 sold price: %s, read from the sheet notes, not typed: confirm it and type it in the main room (or give it to the run as certain, and say which room is the main closet when there is more than one).' % m.group(1)))
    if re.search(r'\bcostco\b', notes, re.I):
        out.append(('B11', 'YES', "B11 Costco: YES, read from the sheet notes, not typed: the workbook's default answer NO was left; confirm it and type it."))
    for f in (rep or {}).get('facts', []):
        m = re.match(r'^(.*?)\s+MOLDING\s*=\s*(.*)$', f, re.I)
        if m:
            ref['molding'][m.group(1).strip()] = m.group(2).strip()
    return out, ref


def sheet_notes_lines(text):
    """The reader's free-text notes, one fact per line (split on '; ' and '. ' outside parentheses), nothing cut."""
    text = re.sub(r'\s+', ' ', text or '').strip()
    out, cur, depth, i = [], '', 0, 0
    while i < len(text):
        c = text[i]
        if c in '([':
            depth += 1
        elif c in ')]':
            depth = max(0, depth - 1)
        if depth == 0 and c in ';.' and i + 1 < len(text) and text[i + 1] == ' ':
            if cur.strip():
                out.append(cur.strip())
            cur, i = '', i + 2
            continue
        cur += c
        i += 1
    if cur.strip().rstrip('.'):
        out.append(cur.strip().rstrip('.'))
    return out


def walls_changed_phrase(ap, args, shorts):
    """'2 walls changed (MASTER 13 and 14)' from the step-1 report, with the room of each wall."""
    rep = ap.get('rep') or {}
    rooms, ids = {}, []
    for ln in rep.get('lines', []):
        m = re.match(r'^wall (\d+) \((.+?)\): (?!height\b)\S.*? -> ', str(ln))
        if m and int(m.group(1)) not in ids:
            ids.append(int(m.group(1)))
            rn = m.group(2).strip()
            rooms.setdefault(shorts.get(rn, rn), []).append(int(m.group(1)))
    if not ids:
        _, same = trimmed_wall_lines(rep)
        return 'every measured wall was already as drawn' if same else 'no wall length could be matched to a wall of the drawing (see the CHECKS)'
    parts = ['%s%s' % ((rn + ' ') if rn else '', join_and(sorted(v))) for rn, v in rooms.items()]
    return '%s changed (%s)' % (plural(len(ids), 'wall'), '; '.join(parts))


def heights_phrase(ap, rooms_all):
    rep = ap.get('rep') or {}
    hr = []
    for ln in rep.get('lines', []):
        m = re.match(r'^room (.*?): wall heights set to the measured ceiling', str(ln).strip())
        if m:
            hr.append(m.group(1))
    if not hr:
        return ''
    n = len(rooms_all) or len(hr)
    if len(hr) >= n and n == 2:
        return 'ceiling heights set in both rooms'
    if len(hr) >= n:
        return 'ceiling heights set in every room' if n > 1 else 'ceiling height set'
    return 'ceiling heights set in %s' % join_and(hr)


def in_short(args, ap, split_res, rooms, books, checks, not_done, shorts, split_note):
    """The three numbered sentences at the top of the RUN REPORT."""
    L = []
    rep = ap.get('rep')
    # 1. step 1
    if args.workbooks_only:
        s1 = 'The job was used as it is (workbooks only).'
    elif args.rem and rep is not None:
        parts = [walls_changed_phrase(ap, args, shorts)]
        hp = heights_phrase(ap, [r['name'] for r in rooms])
        if hp:
            parts.append(hp)
        s1 = ('Remeasure applied: ' if ap.get('written') or rep.get('changed_walls') else 'Remeasure checked: ') + ', '.join(parts) + '.'
        fp, holds = filler_summary(rep, shorts)
        if fp is None:
            s1 += ' Filler rule not run.' if 'did not run' in (ap.get('fillers') or '') else ''
        else:
            s1 += ' Filler rule run: %s%s.' % (fp, ('; %s left to the engineer' % plural(holds, 'corner')) if holds else '')
    elif args.rem:
        s1 = 'The remeasure could not be applied (see NOT DONE).'
    else:
        fp, holds = filler_summary(rep, shorts)
        s1 = 'No remeasure given. ' + (('Filler rule run: %s%s.' % (fp, ('; %s left to the engineer' % plural(holds, 'corner')) if holds else '')) if fp is not None else 'Filler rule not run.')
    L.append('  1. ' + s1)
    # 2. split
    if split_res:
        L.append('  2. Split into %s, one KCD file per room: %s.' % (plural(len(rooms), 'room file'), ', '.join(r['name'] for r in rooms)))
    elif args.no_split or args.workbooks_only:
        L.append('  2. Not split (not asked for); the workbooks come from the whole file.')
    else:
        L.append('  2. Not split: %s' % (split_note or 'see NOT DONE.'))
    # 3. workbooks
    if books:
        filled, cells = [], set()
        for b in books:
            cells.update(c for c, _, _ in b['entries'])
        for c, word in (('B5', 'order'), ('B7', 'name'), ('B9', 'room'), ('B1', 'install date'), ('F1', 'designer'), ('F5', 'material'),
                        ('F7', 'banding'), ('F9', 'banding'), ('F11', 'door type'), ('F21', 'molding'), ('F23', 'molding'), ('B27', 'sold price')):
            if c in cells and word not in filled:
                filled.append(word)
        tabs = {t for b in books for t, _, _, _ in b['cells']}
        if 'Purchase Order' in tabs:
            filled.append('the handle line of the Purchase Order')
        if 'Doormark A1' in tabs:
            filled.append('the Doormark design' + (' and colour' if any(r == 'EM41' for b in books for _, r, _, _ in b['cells']) else ''))
        still = []
        if all(b['priced'] for b in books):
            filled.append('the price lines' + ((' (from the list %s)' % ', '.join(os.path.basename(os.path.normpath(d)) for d in args.pricelist)) if args.pricelist else ''))
        else:
            still.append('the price lines')
        missing = [w for c, w in (('F1', 'the designer'), ('B1', 'install date'), ('B27', 'sold price')) if c not in cells]
        if missing:
            still.append(join_and(missing) + ' (not given)')
        if any(b['molding_blank'] for b in books):
            still.append('the molding (see the CHECK)')
        if any('F11' not in {c for c, _, _ in b['entries']} for b in books):
            still.append('the door/drawer type' + (' (in one room)' if len(books) > 1 and 'F11' in cells else ''))
        if any(b['has_faces'] for b in books):
            still.append('door sizes')
        L.append('  3. %s. Filled: %s.%s' % ('One workbook per room' if len(books) > 1 else 'One workbook',
                                           ', '.join(filled) or 'nothing', (' The engineer still types: %s.' % ', '.join(still)) if still else ''))
    elif args.no_workbooks:
        L.append('  3. No workbook was filled (not asked for).')
    else:
        L.append('  3. No workbook was filled (see NOT DONE).')
    L.append('  CHECKS: %s.' % (('%d (listed below)' % len(checks)) if checks else 'none'))
    return L


def flatten_rooms(out_dir, split_res, rooms, books, not_done, ap, keep_whole, work_dir):
    """Mike wants one KCD file PER ROOM that has been through the process, one workbook per room, all in one folder:
    move the room files, their workbooks and reports and the splitter's report up into out_dir, drop the splitter's
    folder, and drop the whole-job TEST file (every room is in a room file) unless keep_whole."""
    folder = split_res['folder']
    moved_all = True

    def up(src):
        if not src or not os.path.isfile(src) or os.path.dirname(os.path.abspath(src)) == os.path.abspath(out_dir):
            return src
        dst = os.path.join(out_dir, os.path.basename(src))
        os.replace(src, dst)
        return dst
    for room in rooms:
        if room.get('md5') and room.get('path'):
            old = room['path']
            try:
                room['path'] = up(old)
            except OSError as e:
                moved_all = False
                not_done.append('The room file %s could not be moved into %s (%s); it is in %s.' % (os.path.basename(old), out_dir, e.strerror, folder))
                continue
            for b in books:
                if b.get('job') == old:
                    b['job'] = room['path']
                    if b.get('text'):
                        b['text'] = b['text'].replace(rel(old, out_dir), rel(room['path'], out_dir))
    for b in books:
        for key in ('xlsm',):                       # the workbook reports are already in the reports folder
            src = b.get(key)
            try:
                dst = up(src)
            except OSError as e:
                not_done.append('%s could not be moved into %s (%s); it is in %s.' % (os.path.basename(src), out_dir, e.strerror, folder))
                continue
            if dst != src:
                if key == 'report':
                    try:
                        t = open(dst, encoding='utf-8').read().replace(folder + os.sep, out_dir + os.sep)
                        open(dst, 'w', encoding='utf-8').write(t)
                    except OSError:
                        pass
                if key == 'xlsm' and b.get('text'):
                    b['text'] = b['text'].replace(rel(src, out_dir), rel(dst, out_dir))
                b[key] = dst
    try:
        src = split_res.get('report')               # the splitter's report goes to the reports folder, not the finished one
        if src and os.path.isfile(src):
            os.makedirs(work_dir, exist_ok=True)
            dst = os.path.join(work_dir, os.path.basename(src))
            os.replace(src, dst)
            split_res['report'] = dst
    except OSError:
        pass
    try:
        for f in os.listdir(folder):
            if f.lower().endswith('.rtf'):
                os.remove(os.path.join(folder, f))
        if not os.listdir(folder):
            os.rmdir(folder)
    except OSError:
        pass
    # the whole-job TEST file: every room is now in its own file, so it goes unless asked for
    w = ap.get('written')
    if w and os.path.isfile(w):
        ap['written_md5'] = md5(w)
        if moved_all and not keep_whole and all(r.get('md5') for r in rooms):
            try:
                os.remove(w)
                ap['whole_kept'] = False
            except OSError as e:
                not_done.append('The whole-job TEST file could not be removed (%s); it is still in the folder.' % e.strerror)


def write_run_report(args, out_dir, client, test_no, ap, split_res, rooms, books, checks, not_done, suggestions, started, split_note):
    rp = run_report_path(args, out_dir, test_no)
    L = ['RUN REPORT  %s %s  (%s)   TEST %d, made %s' % (args.order, args.name, client, test_no, when(started)),
         'Every file named here is a TEST file until KCD or Excel has opened it.',
         'IN SHORT']
    try:
        shorts = short_room_names([n.strip() for n in kcdwalls.room_names(open(args.job, 'rb').read()).values() if n.strip()])
    except Exception:
        shorts = short_room_names([r['name'] for r in rooms])
    L += in_short(args, ap, split_res, rooms, books, checks, not_done, shorts, split_note)
    # files
    L += ['', 'FILES',
          '  Finished folder (only the room files and workbooks, ready to move): %s' % out_dir,
          '  Reports folder (every report and the inputs): %s' % args.work]
    if ap.get('written') and ap.get('whole_kept', True):
        L.append('  %s  (the whole job after the changes%s)' % (('reports: ' + os.path.basename(ap['written'])) if os.path.dirname(ap['written']) == args.work else rel(ap['written'], out_dir), '; the room files below are the ones for KCD' if rooms else ''))
    if ap.get('report'):
        L.append('  reports: %s  (what step 1 did, wall by wall)' % os.path.basename(ap['report']))
    for room in rooms:
        if room.get('md5'):
            L.append('  %s  (the KCD file of this room, after the changes)' % rel(room['path'], out_dir))
        b = next((x for x in books if x['job'] == room['path'] and x['room'] == room['name']), None)
        if b:
            L.append('  %s  (its workbook)' % rel(b['xlsm'], out_dir))
            tsv = next((p for r, p in args.prices if key(r) and key(r) in key(room['name'])), None)
            if tsv and os.path.isfile(tsv):
                L.append('  %s  (its price lines, like KCD\'s price review)' % rel(tsv, out_dir))
    if split_res and split_res.get('report'):
        L.append('  reports: %s  (the splitter\'s own check)' % os.path.basename(split_res['report']))
    for b in books:
        if b.get('report'):
            L.append('  reports: %s  (the workbook report of %s)' % (os.path.basename(b['report']), b['room']))
    L.append('  reports: %s  (this report)' % os.path.basename(rp))
    made = 'Made from %s' % os.path.basename(args.job)
    if args.rem:
        made += ' and %s' % os.path.basename(args.rem)
    L.append('  ' + made + '.')
    # wall changes
    L += ['', 'WALL CHANGES (step 1)']
    rep = ap.get('rep')
    if rep is None:
        L.append('  none: step 1 did not run (%s).' % (ap.get('note') or 'no remeasure'))
    else:
        if rep.get('rem_reader'):
            L.append('  Read-out made by: %s' % re.sub(r'\s+', ' ', rep['rem_reader']).strip())
        lines, same = trimmed_wall_lines(rep)
        L += ['  ' + s for s in lines] or ['  no wall changed.']
        if same:
            L.append('  %s measured the same as drawn and %s left alone.' % (plural(same, 'wall'), 'were' if same != 1 else 'was'))
        if rep.get('facts'):
            L.append('  Room facts on the sheet (not applied to the job):')
            L += ['    ' + f for f in rep['facts']]
        if rep.get('rem_notes'):
            L.append('  Sheet notes:')
            L += ['    ' + s for s in sheet_notes_lines(rep['rem_notes'])]
    L += ['', 'FILLERS (step 1)']
    fl, fchecks = fillers_block(rep)
    if fl:
        L += ['  ' + s for s in fl]
    else:
        L.append('  ' + (ap.get('fillers') or 'the filler step did not run') + '.')
    # checks
    L += ['', 'TO CHECK (%d)' % len(checks)]
    if checks:
        for i, c in enumerate(checks, 1):
            L.append('  %2d. %s' % (i, re.sub(r'^CHECK\s+', '', c)))
    else:
        L.append('  nothing.')
    if suggestions:
        L += ['', 'NOT WRITTEN, FROM THE REMEASURE SHEET NOTES (check before typing)']
        for cell, val, sentence in suggestions:
            L.append('  ' + sentence)
    # rooms
    for room in rooms:
        L.append('')
        b = next((x for x in books if x['job'] == room['path'] and x['room'] == room['name']), None)
        if b:
            L.append(b['text'])
        else:
            L += ['ROOM: %s' % room['name'], '  Room file:  %s' % rel(room['path'], out_dir), '  Workbook:   none']
        if room.get('md5'):
            L.append('  Room file check: %s, %s, %s.' % (plural(room['walls'], 'wall'), plural(room['cabinets'], 'cabinet'), plural(room['notes'], 'note')))
        for lvl, msg in room.get('flags', []):
            if lvl == NOTE:
                L.append('  Note: ' + msg)
    L += ['', 'NOT DONE AND WHY']
    L += ['  - ' + s for s in not_done] or ['  - nothing was left out.']
    # the record line (for the lead and the notes, not for the owner)
    rec = ['job %s md5 %s' % (args.job, md5(args.job))]
    if args.rem:
        rec.append('read-out %s' % args.rem)
    if ap.get('written'):
        rec.append('whole-job TEST md5 %s%s' % (ap.get('written_md5') or (md5(ap['written']) if os.path.isfile(ap['written']) else '?'), '' if ap.get('whole_kept', True) else ' (file not kept)'))
    for room in rooms:
        if room.get('md5'):
            rec.append('%s md5 %s' % (os.path.basename(room['path']), room['md5']))
    rec.append('template %s' % args.template)
    rec.append('kcdrun.py %s' % started.strftime('%Y-%m-%d %H:%M'))
    L += ['', 'For the record: ' + '; '.join(rec) + '.']
    with open(rp, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L) + '\n')
    return rp


# ----------------------------------------------------------------------------- main
def parse_args(argv):
    ap = argparse.ArgumentParser(description='Apply a remeasure to a KCD job, split it into room files and fill a pricing workbook per room.')
    ap.add_argument('job', help="the designer's .job, or an order number (then the job and the read-out are taken from the jobs folder)")
    ap.add_argument('--jobs', help='with an order number: the folder that holds "<order> <NAME>" folders (default: jobs/ at the repo root)')
    ap.add_argument('--inbox', help='with an order number: the in folder where the KCD file and the remeasure were dropped (default: C:\\grok rem in when it exists)')
    ap.add_argument('--done', help='with --inbox: where the finished run goes, one folder per order (default: C:\\grok rem completed)')
    ap.add_argument('--work', help='the reports folder: every report, the inputs taken from the in folder and any work file (default: C:\\grok rem reports\\<order> <NAME>, jobs/<order> <NAME>/reports, or "<out> reports"); the finished folder keeps only room files and workbooks')
    ap.add_argument('--rem', help='the remeasure read-out JSON; without it only the fillers are checked')
    ap.add_argument('--order', help='the order (job) number, e.g. 1084476 (not needed when the first argument is the order number)')
    ap.add_argument('--name', help='the customer last name for the file names, e.g. ROBERTS (with an order number: from the folder name)')
    ap.add_argument('--client', help='the client name for the TEST file names; default: the job file name without KCD')
    ap.add_argument('--out', help='the output folder (with an order number: the out/ folder inside the order folder)')
    ap.add_argument('--test', type=int, help='the TEST number; default: the next free one in the output folder')
    ap.add_argument('--no-fillers', action='store_true', help='leave the end-filler step out')
    ap.add_argument('--no-heights', action='store_true', help='do not set the wall heights from the measured ceiling')
    ap.add_argument('--no-split', action='store_true', help='do not split into room files (the workbooks come from the whole job)')
    ap.add_argument('--no-workbooks', action='store_true', help='do not fill the workbooks')
    ap.add_argument('--workbooks-only', action='store_true', help='only the workbook step: no remeasure, no filler check, no split')
    ap.add_argument('--template', default=kcdbook.DEFAULT_TEMPLATE, help='the pricing workbook template (.xltm); default: the bundled one')
    ap.add_argument('--price', action='append', default=[], metavar='ROOM=TSV', help='a kcdprice.py TSV for one room, matched by room name (contains, any case)')
    ap.add_argument('--pricelist', action='append', default=[], metavar='DIR',
                    help="price every room with KCD's price scripts from this folder (repeat for update packs, later ones win), e.g. the current month's C:\\KCD23-STDPLIST folder; data/pricelist holds the Sept 2024 list, for tests only")
    ap.add_argument('--entry', action='append', default=[], metavar='CELL=VALUE', help='a Data Entry answer (B1=2026-11-04) or a tab cell ("Purchase Order!K19=AMEROCK"); wins over everything')
    ap.add_argument('--designer', help='the designer, as the workbook list spells it')
    ap.add_argument('--install', help='the install date, YYYY-MM-DD')
    ap.add_argument('--sold', type=float, help='the sold-at price (goes into the main room, see --main)')
    ap.add_argument('--main', help='the room that carries the sold-at price (name, contains); not needed for a one-room job')
    ap.add_argument('--replace', action='store_true', help='replace room files, a TEST job or a RUN REPORT already in the output folder')
    ap.add_argument('--keep-whole', action='store_true', help='also keep the whole-job TEST file (by default the room files are the KCD files handed back, one per room, with a workbook each, all in one folder)')
    return ap.parse_args(argv)


def resolve_order(args):
    """'python3 kcdrun.py 1084476': find the designer's job and the read-out by the order number and fill in args.
    With an in folder (--inbox, the project's own folder when the files were dropped at its top, or C:\\grok rem in) the two files are taken from there and the run
    lands in the done folder; otherwise jobs/<order> <NAME>/ at the repo root is used."""
    order = args.job.strip()
    inbox = args.inbox or default_inbox(order)
    if inbox:
        return resolve_inbox(args, order, inbox)
    return resolve_folder(args, order, os.path.abspath(args.jobs or DEFAULT_JOBS_DIR))


def resolve_inbox(args, order, inbox):
    inbox = os.path.abspath(inbox)
    if not os.path.isdir(inbox):
        raise StopRun('The in folder %s does not exist; make it and drop the KCD file and the remeasure scan in it.' % inbox)
    files = sorted(os.listdir(inbox))
    subs = [d for d in files if os.path.isdir(os.path.join(inbox, d)) and d.startswith(order) and (len(d) == len(order) or not d[len(order)].isdigit())]
    if subs:                                        # a folder per order inside the in folder works too
        resolve_folder(args, order, inbox)
        args.out = os.path.join(os.path.abspath(args.done or default_done(inbox)), os.path.basename(os.path.dirname(args.job)))
        args.inbox_files = [args.job, args.rem] + [os.path.join(os.path.dirname(args.job), f) for f in os.listdir(os.path.dirname(args.job)) if f.lower().endswith('.pdf')]
        args.found += ' Results go to %s.' % args.out
        return
    pdfs = [f for f in files if f.lower().endswith('.pdf') and order in f]
    jsons = [f for f in files if f.lower().endswith('.json') and order in f]
    jobs = [f for f in files if f.lower().endswith('.job') and not re.search(r'test|applied|fillers checked', f, re.I)]
    rem_name = (jsons or pdfs or [''])[0]
    m = re.match(r'REM[-_ ]*\d+[-_ ]*(.+?)\.(pdf|json)$', rem_name, re.I)
    name = (args.name or (m.group(1).strip(' -_') if m else '')).upper()
    if not jobs:
        raise StopRun("No KCD job file in %s; drop the designer's .job there." % inbox)
    if len(jobs) > 1:
        narrowed = [f for f in jobs if order in f] or ([f for f in jobs if name and name.lower() in f.lower()] if name else [])
        if len(narrowed) == 1:
            jobs = narrowed
        else:
            raise StopRun('More than one KCD job file in %s (%s) and none is clearly order %s; leave only the right one there.' % (inbox, ', '.join(jobs), order))
    if not jsons:
        if pdfs:
            raise StopRun('The in folder %s has the scan %s but no read-out yet: read the scan and write REM-%s-%s.json next to it first.'
                          % (inbox, pdfs[0], order, name or 'NAME'))
        raise StopRun('No remeasure for order %s in %s (no REM-%s-*.pdf and no REM-%s-*.json), so nothing was run.' % (order, inbox, order, order))
    if len(jsons) > 1:
        raise StopRun('More than one read-out for order %s in %s (%s); keep one.' % (order, inbox, ', '.join(jsons)))
    if not name:
        raise StopRun('The customer name is not in the file names (expected REM-%s-NAME.pdf); give it with --name.' % order)
    done_root = os.path.abspath(args.done or default_done(inbox))
    args.job = os.path.join(inbox, jobs[0])
    args.rem = os.path.join(inbox, jsons[0])
    args.order = order
    args.name = name
    args.out = args.out or os.path.join(done_root, '%s %s' % (order, name))
    args.inbox_files = [args.job, args.rem] + [os.path.join(inbox, f) for f in pdfs]
    args.found = 'Order %s: job %s and read-out %s found in %s; results go to %s.' % (order, jobs[0], jsons[0], inbox, args.out)


def resolve_folder(args, order, jobs_dir):
    if not os.path.isdir(jobs_dir):
        raise StopRun('The jobs folder %s does not exist; make it and put the folder "%s <NAME>" with the job and the remeasure in it.' % (jobs_dir, order))
    hits = [d for d in sorted(os.listdir(jobs_dir)) if d.startswith(order) and os.path.isdir(os.path.join(jobs_dir, d))
            and (len(d) == len(order) or not d[len(order)].isdigit())]
    if not hits:
        raise StopRun('No folder for order %s in %s; make the folder "%s <NAME>" there and put the job and the remeasure in it.' % (order, jobs_dir, order))
    if len(hits) > 1:
        raise StopRun('More than one folder for order %s in %s (%s); keep one.' % (order, jobs_dir, ', '.join(hits)))
    folder = os.path.join(jobs_dir, hits[0])
    files = sorted(os.listdir(folder))
    jobs = [f for f in files if f.lower().endswith('.job') and not re.search(r'test|applied|fillers checked', f, re.I)]
    if not jobs:
        raise StopRun("No KCD job file in %s; put the designer's .job there." % folder)
    if len(jobs) > 1:
        raise StopRun("More than one job file in %s (%s); keep the designer's one there, or run that file by name." % (folder, ', '.join(jobs)))
    rems = [f for f in files if re.match(r'REM-.*\.json$', f, re.I)]
    name = hits[0][len(order):].strip(' -_')
    if not rems:
        pdfs = [f for f in files if re.match(r'REM-.*\.pdf$', f, re.I)]
        if pdfs:
            raise StopRun('The folder %s has the scan %s but no read-out yet: read the scan and write REM-%s-%s.json next to it first.'
                          % (folder, pdfs[0], order, (name or 'NAME').upper().replace(' ', '')))
        raise StopRun('No remeasure in the folder %s (no REM-*.pdf and no REM-*.json), so nothing was run. To check the fillers only, run the job file by name without --rem.' % folder)
    if len(rems) > 1:
        raise StopRun('More than one read-out in %s (%s); keep one.' % (folder, ', '.join(rems)))
    if not name:
        m = re.match(r'REM-\d+-(.+)\.json$', rems[0], re.I)
        name = m.group(1) if m else ''
    if not name:
        raise StopRun('The folder %s does not say the customer name; name it "%s <NAME>".' % (folder, order))
    args.job = os.path.join(folder, jobs[0])
    args.rem = os.path.join(folder, rems[0])
    args.order = order
    args.name = args.name or name
    args.out = args.out or os.path.join(folder, 'out')
    args.found = 'Order %s: job %s and read-out %s found in %s.' % (order, jobs[0], rems[0], folder)


def check_inputs(args):
    args.found = ''
    if re.fullmatch(r'\s*\d{5,8}\s*', args.job or ''):
        resolve_order(args)
    else:
        for flag, val in (('--order', args.order), ('--name', args.name), ('--out', args.out)):
            if not val:
                raise StopRun('%s is needed when a job file is given (or give the order number alone, and the job is found in the jobs folder).' % flag)
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
        # anything kcdwalls can turn into a change or a CHECK is enough: lengths, held lengths, facts, angles, openings,
        # the lines it could not place (a room-labelled length becomes "which wall is it?"), the facts held for review, notes
        if not any(rem.get(k) for k in ('walls', 'walls_review', 'facts', 'angles', 'openings', 'skipped', 'facts_review', 'notes')):
            raise StopRun('The remeasure file %s is empty: no wall lengths, facts or notes could be read from it.' % args.rem)
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
    args.work = os.path.abspath(args.work or default_work(args.out))
    if args.work == args.out:
        raise StopRun('The reports folder must not be the finished folder %s: that one holds only the room files and workbooks.' % args.out)
    try:
        os.makedirs(args.work, exist_ok=True)
    except OSError as e:
        raise StopRun('The reports folder %s could not be made (%s).' % (args.work, e.strerror))


def refuse_existing_test(args, out_dir, client, test_no):
    """An explicit --test N whose TEST job or RUN REPORT is already in the folder is refused unless --replace."""
    if not args.test or args.replace:
        return
    out_job, out_rep = step1_names(args, out_dir, client, test_no)
    kept_job = os.path.join(args.work, os.path.basename(out_job))       # a kept whole-job TEST file is moved there
    there = [os.path.basename(p) for p in (out_job, kept_job, out_rep, run_report_path(args, out_dir, test_no)) if os.path.exists(p)]
    if there:
        raise StopRun('TEST %d is already in %s (%s). Use the next number, or run again with --replace to overwrite it.' % (test_no, out_dir, ', '.join(there)))


def main(argv=None):
    started = datetime.datetime.now()
    args = parse_args(argv)
    try:
        check_inputs(args)
        out_dir = args.out
        client = args.client or default_client(args.job)
        test_no = args.test or next_test_number(out_dir, args.work)
        refuse_existing_test(args, out_dir, client, test_no)
    except StopRun as e:
        print(str(e))
        return 2
    if args.found:
        print(args.found)
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
    split_note = ''
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
            split_note = 'the room files of an earlier run are already in the folder and were left as they are (run again with --replace to redo them).'
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

    # step 2b: price every room with the given price-list folders (kcdprice.py prints the TSV kcdbook reads)
    if args.pricelist and rooms:
        for room in rooms:
            if not room.get('md5') or not room.get('path'):
                continue
            tsv = os.path.join(out_dir, room['base'] + ' PRICE LINES.txt')
            cmd = [sys.executable, os.path.join(HERE, 'kcdprice.py'), room['path']]
            for d in args.pricelist:
                cmd += ['--pricelist', d]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            except (OSError, subprocess.TimeoutExpired) as e:
                not_done.append('%s was not priced: the price engine did not run (%s).' % (room['name'], one_line(e)))
                continue
            if res.returncode != 0 or not res.stdout.strip():
                not_done.append('%s was not priced: the price engine stopped (%s).' % (room['name'], one_line(res.stderr.strip().splitlines()[-1] if res.stderr.strip() else 'no output')))
                continue
            with open(tsv, 'w', encoding='utf-8') as fh:
                fh.write(res.stdout)
            args.prices.append((room['name'], tsv))
        lists = ', '.join(os.path.basename(os.path.normpath(d)) for d in args.pricelist)
        checks.append('Prices come from the price list folder(s) %s. If this job was sold on another month\'s list, price it again with that list.' % lists)

    # step 3
    if args.no_workbooks:
        not_done.append('No workbook was filled (not asked for).')
    elif not rooms:
        not_done.append('No workbook was filled because there are no new room files.')
    else:
        try:
            dd = Dropdowns(args.template)
        except Exception as e:
            dd = None
            not_done.append('The workbooks were not filled: the template\'s answer lists could not be read (%s: %s).' % (type(e).__name__, one_line(e)))
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
                    books.append(room_workbook(room, args, dd, cat, args.template, price, args.entries, is_main, ref, out_dir))
                except Exception as e:
                    not_done.append('The workbook for %s was not made: %s: %s' % (room['name'], type(e).__name__, one_line(e)))
                    traceback.print_exc(file=sys.stderr)
            for r, p in args.prices:
                if not any(key(r) in key(room['name']) for room in rooms):
                    not_done.append('The price file for %r (%s) matched no room, so it was not pasted.' % (r, p))
            if args.main and len(rooms) > 1 and not any(key(args.main) in key(room['name']) for room in rooms):
                not_done.append('The main room you named (%r) matched no room, so the sold-at price was not written anywhere.' % args.main)
            if args.sold is not None and len(rooms) > 1 and not args.main:
                not_done.append('The sold-at price was not written: with more than one room, say which one is the main closet.')
    for b in books:
        checks += b['checks']
    if not args.rem and not args.workbooks_only:
        not_done.append('No remeasure was applied (none was given).')
    if 'did not run' in (ap.get('fillers') or ''):
        not_done.append('The end-filler step did not run (%s).' % ap['fillers'])
    if any(b['has_faces'] for b in books):
        not_done.append('Door sizes were not typed on any order form: the size to order is the size on the door elevation, not the KCD face size, and the tool cannot settle that yet; the faces are listed per room.')
    not_done.append('Nothing was typed on the VJT, CF5, CF Thermo, Final Price Sheet and Job Cart Cover Sheet tabs; what the tool can suggest is listed per room.')
    if split_res:
        flatten_rooms(out_dir, split_res, rooms, books, not_done, ap, args.keep_whole, args.work)
    # the finished folder keeps only the room files and the workbooks; everything else goes to the reports folder
    try:
        tidy_finished(out_dir, args.work, ap, split_res, books)
    except OSError as e:
        not_done.append('The finished folder could not be cleaned (%s): move every file but the room .job files and the .xlsm workbooks out of %s by hand.' % (e.strerror, out_dir))
    rp = write_run_report(args, out_dir, client, test_no, ap, split_res, rooms, books, checks, not_done, suggestions, started, split_note)
    print(open(rp, encoding='utf-8').read())
    print('RUN REPORT: %s' % rp)
    failed = any('failed' in s or 'was not made' in s or 'was not run' in s for s in not_done)
    if getattr(args, 'inbox_files', None) and not failed:
        moved = []
        for f in args.inbox_files:
            try:
                shutil.move(f, os.path.join(args.work, os.path.basename(f)))
                moved.append(os.path.basename(f))
            except OSError as e:
                print('Could not move %s into %s (%s); it is still in the in folder.' % (f, args.work, e))
        if moved:
            line = 'Moved from the in folder into the reports folder %s: %s.' % (args.work, ', '.join(moved))
            print(line)
            with open(rp, 'a', encoding='utf-8') as fh:
                fh.write('\n' + line + '\n')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
