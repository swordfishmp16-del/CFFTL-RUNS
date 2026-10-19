#!/usr/bin/env python3
"""sidebar.py - prototype sidebar parser for KCD v23 jobs (Closet Factory Fort Lauderdale).

Reads a .job with kcdunits.read_job (no unit catalog needed), finds every note whose text starts with
ROOM DETAILS (the designer's sidebar), and turns it into one JSON per room:

  room          number, KCD room name, sidebar room name
  fields        the labelled lines, structured (height, material, banding, backing, rods, handles, door style,
                drawer box, crown, base, countertop, design notes, room information)
  options       the Opt-... lines of ROOM OPTIONS and ACCESSORIES (name, qty)
  accessories   the RM<n> ... lines (name, part number, vendor guess, how the vendor was guessed)
  handles       the HANDLES/KNOBS lines (name, part number, vendor guess, qty, stock / special-order marks)
  free_text     everything the parser did not consume, plus the wall notes of the room
  checks        sidebar against the unit records of the same room (rods, accessories, options, materials,
                depths); each check says sidebar value, job value, and whether they agree
  forms         what the sidebar can feed, with a certainty mark on every value:
                  workbook  Data Entry answers (F5 F7 F9 F11 F13 F21 F23 B13 B15 B19 B21)
                  po        purchase-order lines (room, qty, item, description, vendor)
                  doors     door-form header (design, Doormark code, colour, colour code, insert, joint)
                  vjt       jewelry-tray inputs (layout, shelf width, drawer depth, insert styles, colour)
  flags         CHECK = the engineer must look; NOTE = information

Rule: nothing uncertain is written as certain. Every form value carries "certain" (read straight from the
sidebar or the unit records), "inferred" (a rule we believe but have not had confirmed) or "unknown".

Usage: python3 sidebar.py JOB.job [MORE.job ...] [--out DIR]
"""
import sys, os, re, json, collections

sys.path.insert(0, '/home/user/CFFTL-WORKING-/kcd-room-splitter')
import kcdunits

# ------------------------------------------------------------------------------------------------
# reference tables (copied from the shop's own pricing workbook template, sheet Data Conversions)
# ------------------------------------------------------------------------------------------------
DOORMARK_DESIGNS = {  # X3:Y36
    'ABACOA SHAKER': 'SHA', 'BAHAMA SHAKER': 'SHB', 'BAL HARBOR': 'BAL', 'BIMINI': 'BIM', 'BISCAYNE': 'BIS',
    'CAPTIVA': 'CAP', 'DAYTONA': 'DAY', 'DORAL': 'DOR', 'ENGLEWOOD': 'ENG', 'EURO SHAKER': 'EUSH',
    'FREEPORT SHAKER': 'SHF', 'GULFSTREAM': 'GUL', 'HOLLYWOOD': 'HOL', 'ISLAMORADA': 'ISL', 'KEY LARGO': 'KEY',
    'LAS OLAS': 'LAS', 'MARATHON SHAKER': 'SHM', 'MARTINIQUE': 'MAR', 'MONTEGO': 'MON', 'NAPLES SHAKER': 'SHN',
    'NASSAU': 'NAS', 'ORLANDO': 'ORL', 'PALM BEACH': 'PAL', 'POMPANO': 'POM', 'PORT CHARLOTTE': 'POR',
    'SAN MARCO': 'SAN', 'SARASOTA SHAKER': 'SHS', 'SEBRING': 'SEB', 'SOUTH BEACH': 'SOU', 'SUNRISE': 'SUN',
    'VENICE': 'VEN', 'VIZCAYA': 'VIZ', 'WELLINGTON': 'WEL', 'WESTON': 'WES'}
DOORMARK_COLORS = {  # X41:Y58 (X53 HUDSON CHERRY has no code in the template)
    'WHITE': 'FWM', 'ALMOND': 'AM', 'APPLE COCOA': 'CHPE', 'BISQUE': 'OWM', 'BLACK': 'BLMA', 'BLACK GLOSS': 'BLGL',
    'BLANCA ELME': 'BLEL', 'CAMPANIA ELME': 'CAEL', 'ESPRESSO': 'EXPR', 'FOG': 'FOG', 'FOLKSTONE GREY': 'FOST',
    'FUSION MAPLE': 'FM', 'LEWIS': 'LEWI', 'MARSEILLE': 'MARS', 'MONACO': 'MONA', 'MOSCATTO': 'MOEL',
    'TENINO GREY': 'TEGR'}
FACE_TYPES = ['Melamine', 'Melamine W/Applied Mldg', 'Thermo Foil', 'Wood', 'CF5', 'CF Thermo Foil', 'Egger',
              'Combination', 'ODK - Melbourne', 'ODK - Sanford']                       # I7:I16  -> F11
BANDING_TYPES = ['.5mm', '1mm', '2mm', 'Upgraded', 'Woodtape']                          # I37:I41 -> F7
MOLDINGS = ['None', 'Melamine', 'Thermo Foil', 'CF Thermo Foil', 'Wood', 'Combination', 'Mica']   # I47:I53 -> F21
MOLDING_LOCS = ['None', 'Base Only', 'Crown Only', 'Base & Crown', 'Recessed Base']    # I59:I63 -> F23
JEWELRY_ANSWERS = ['Special Order', 'Cut From Stock', 'Combination']                   # I29:I31 -> B13
HINGE_ANSWERS = ['Self Closing', 'Free Swing', 'Combination']                          # I69:I71 -> B15
VJT_INSERTS = ['STANDARD', 'STANDARD W/ EARRINGS', 'EARRINGS', 'VALET', 'SUNGLASS', 'NECKLACE',
               'WATCH & BRACELET', 'TIE & BELT', 'PLAIN TRAY', 'FLAT LINER']           # M30:M39
MATERIALS = [  # B1:B83, the F5 / F9 dropdown
    'White', 'Black', 'Almond', 'Apple Cocoa Grain', 'Bisque', 'Blanca Elme Grain', 'Campania Elme Grain',
    'Espresso Grain', 'Fog Grey', 'Folkstone Grey', 'Fusion Maple Grain', 'Hudson Cherry Grain', 'Lewis Grain',
    'Marsielle Grain', 'Monaco Grain', 'Moscotto Grain', 'Nina Maple Grain', 'Tenino Grey Grain', 'Wild Apple Grain',
    'Wood Prefinish Grain', 'Wood Stained Grain', 'Wood Painted Grain', 'Wood Glazed Grain', 'Wood Custom ST Grain',
    'Wood Custom PT Grain', 'Atlantis', 'Avondale Ash Grain', 'Belair Grain', 'Blackwood Grain', 'Bohemian Blanco Grain',
    'Cemento', 'Celadon', 'Daintree Grain', 'Dering Forest Grain', 'Designer White Grain', 'Espiga Pimienta Grain',
    'Espiga Sal Grain', 'Fairchild Grain', 'Fawn Cypress', 'Fossil Shale', 'Fresno Glacial Grain', 'Friston Ash Grain',
    'Gris Coco', 'High Line Grain', 'Holly Berry', 'Lapis Blue', 'Lino Cancun Grain', 'Low Line Grain', 'Mineral Grey',
    'Monteverdi Grain', 'Mysterious', 'Neo Walnut Grain', 'Nogal Slow Grain', 'Pepper Dust', 'Phantom Ecru Grain',
    'Phantom Charcoal Grain', 'Portico Teak Grain', 'Randolph Forest Grain', 'Roble Azabache Grain',
    'Roble Colorado Grain', 'Roble Joplin Grain', 'Roble Stella Grain', 'Stainless Grain', 'Tessuto Grain',
    'Valley Forge Elm Grain', 'Veranda Teak Grain', 'Wheat Tabby Grain', 'White Cypress Grain', 'White River For Grain',
    'Willow', 'Amalfi Noce Grain GL', 'Black Ultra GL', 'Outer Space GL', 'Red Ultra GL', 'Silver Met Grain GL',
    'Solar White GL', 'Twlight Pearl GL', 'Drift Ash', 'Pure Black', 'Seaside Blue', 'Seashell White', 'Sand Gray',
    'Timber']
MATERIALS_UP = {m.upper(): m for m in MATERIALS}

# the sidebar's top-level labels, as KCD's macro writes them (matched case-insensitively at the start of a line)
LABELS = ['ROOM DETAILS', 'HEIGHT', 'GARMENT LENGTH', 'MATERIAL/COLOR', 'EDGE BANDING', 'BACKING', 'CLOSET RODS',
          'HANDLES/KNOBS', 'DOOR/DRAWER STYLE', 'DRAWER BOX', 'CROWN', 'BASE', 'COUNTERTOP TYPE', 'COUNTER TOP',
          'COUNTERTOP', 'ROOM OPTIONS and ACCESSORIES', 'ROOM OPTIONS', 'DESIGN NOTES', 'ROOM INFORMATION']
CANON = {'COUNTER TOP': 'COUNTERTOP TYPE', 'COUNTERTOP': 'COUNTERTOP TYPE', 'ROOM OPTIONS': 'ROOM OPTIONS and ACCESSORIES'}
LABEL_RE = re.compile(r'^(' + '|'.join(re.escape(l) for l in sorted(LABELS, key=len, reverse=True)) + r')\s*([-:]|\t|$)(.*)$', re.I)
ROOM_RE = re.compile(r'^ROOM DETAILS\b\s*[-:]?\s*(.*)$', re.I)      # 'ROOM DETAILS HOME OFFICE', 'ROOM DETAILS Primary his'
KNOWN_OPTIONS = {12: 'Set Holes Custom', 5: 'Shelf-Stiffeners 1 side', 13: '3 Hole Adjustable Custom',
                 100: 'LED Routed Full Panel Strips'}       # from notes 2.2; the rest need options.dat

# ------------------------------------------------------------------------------------------------
# small helpers
# ------------------------------------------------------------------------------------------------
def frac(s):
    """'35 1/8' -> 35.125; '28.5' -> 28.5; '84\"' -> 84.0; None when not a number."""
    if s is None:
        return None
    t = s.strip().replace('"', '').replace('in', '').strip()
    m = re.fullmatch(r'(\d+)?\s*(?:(\d+)/(\d+))?', t)
    if not m or not t:
        try:
            return float(t)
        except ValueError:
            return None
    whole = float(m.group(1)) if m.group(1) else 0.0
    if m.group(2):
        whole += float(m.group(2)) / float(m.group(3))
    return whole


def split_qty(s):
    """'Round Polished Chrome Qty-4.00' -> ('Round Polished Chrome', 4.0). Also 'Qty 4.00', '- Qty 4.00'."""
    m = re.search(r'[-\s]*Qty\s*[-\s]*([\d.]+)\s*$', s, re.I)
    if m:
        return s[:m.start()].strip(' -'), float(m.group(1))
    return s.strip(), None


VENDOR_WORDS = [('hafele', 'HAFELE'), ('häfele', 'HAFELE'), ('amerock', 'AMEROCK'), ('rev-a-shelf', 'REV-A-SHELF'),
                ('rev a shelf', 'REV-A-SHELF'), ('blum', 'BLUM'), ('sugatsune', 'SUGATSUNE'), ('wilsonart', 'WILSONART'),
                ('top knobs', 'TOP KNOBS'), ('berenson', 'BERENSON'), ('emtek', 'EMTEK'), ('liberty', 'LIBERTY'),
                ('salice', 'SALICE'), ('grass', 'GRASS'), ('hettich', 'HETTICH')]


def vendor_word(text):
    low = text.lower()
    for w, v in VENDOR_WORDS:
        if w in low:
            return v, w
    # Richelieu is misspelled every time in the samples (Richleui, Richeluio): accept rich...u/i spellings
    m = re.search(r'\brich[a-z]{3,6}\b', low)
    if m and set('eliu') & set(m.group(0)[4:]):
        return 'RICHELIEU', m.group(0)
    return None, None


def find_part(text):
    """Find a vendor part number in free text. Returns (part, vendor, basis, text_without_part).
    basis says how the vendor was decided: 'named' (the vendor's name is in the text) or 'number format'
    (guessed from the shape of the number; the engineer should confirm)."""
    vend, word = vendor_word(text)
    rest = text
    if word:
        rest = re.sub(re.escape(word), '', rest, flags=re.I)
    # Hafele catalogue numbers 547.43.315 / 155.00.092 / 808.71.001
    m = re.search(r'\b(\d{3}\.\d{2}\.\d{3})\b', rest)
    if m:
        return m.group(1), vend or 'HAFELE', 'named' if vend else 'number format (###.##.### is a Hafele number)', (rest[:m.start()] + rest[m.end():]).strip(' -')
    # Richelieu: BP + 7 digits + 3-digit finish (bp8160160-140 = BP8160160140 chrome)
    m = re.search(r'\b(bp\s?\d{7,}[-\s]?\d{2,3})\b', rest, re.I)
    if m:
        part = re.sub(r'[\s-]', '', m.group(1)).upper()
        return part, vend or 'RICHELIEU', 'named' if vend else 'number format (BP+7 digits+finish is a Richelieu number)', (rest[:m.start()] + rest[m.end():]).strip(' -')
    # Amerock: BP + 4..6 digits + finish letters (BP36559-CZ)
    m = re.search(r'\b(bp\s?\d{4,6}(?:-?[a-z0-9]{1,4})?)\b', rest, re.I)
    if m:
        return m.group(1).replace(' ', '').upper(), vend or 'AMEROCK', 'named' if vend else 'number format (BP+5 digits+finish is an Amerock number)', (rest[:m.start()] + rest[m.end():]).strip(' -')
    # a generic catalogue number: letters/digits with dots or dashes and at least 4 digits
    m = re.search(r'\b([A-Z]{0,4}\d[\w.]*[-.]\w*\d\w*)\b', rest)
    if m and sum(c.isdigit() for c in m.group(1)) >= 4:
        return m.group(1), vend, 'named' if vend else None, (rest[:m.start()] + rest[m.end():]).strip(' -')
    return None, vend, 'named' if vend else None, rest.strip(' -')


def classify_door(style):
    s = (style or '').lower()
    if not s:
        return 'unknown'
    if 'no door' in s or 'no faces' in s:
        return 'none'
    if 'element' in s:
        return 'elements'
    if re.search(r'\bth\b|thermo', s):
        return 'thermofoil'
    if re.search(r'cf\s*5|5[- ]piece', s):
        return 'cf5'
    if 'framed' in s:
        return 'framed'
    if 'melamine' in s:
        return 'melamine'
    return 'unknown'


def doormark_design(style):
    """'SARASOTA  Shaker TH' -> ('SARASOTA SHAKER', 'SHS'); None when not in the workbook's table."""
    s = re.sub(r'\s+', ' ', (style or '').upper()).strip()
    s = re.sub(r'\bTH\b', '', s).strip(' -')
    if s in DOORMARK_DESIGNS:
        return s, DOORMARK_DESIGNS[s]
    for name, code in DOORMARK_DESIGNS.items():          # 'ABACOA SHAKER TH' / 'SHAKER ABACOA'
        words = name.split()
        if all(w in s.split() for w in words):
            return name, code
    return s or None, None


def base_name(mat):
    """colour name without Grain / Finish / (PROMO) / 1 mm, for same-colour comparisons (skill card rule)."""
    s = (mat or '').upper()
    s = re.sub(r'\(?\bPROMO\b\)?|\*PROMO ?COLOR\*', '', s)
    s = re.sub(r'\b(GRAIN|FINISH|FOR)\b', '', s)
    s = re.sub(r'\d*\.?\d+\s*MM', '', s)
    return re.sub(r'[\s-]+', ' ', s).strip()


# ------------------------------------------------------------------------------------------------
# the parser
# ------------------------------------------------------------------------------------------------
class RoomSidebar:
    def __init__(self, job, note, idx):
        self.job = job
        self.note = note
        self.note_index = idx
        self.room = note['room']
        self.kcd_room_name = job.room_name(self.room)
        self.raw_text = note['text']
        self.flags = []
        self.fields = {}            # canonical label -> {'value': first line after the label, 'lines': [continuations]}
        self.order = []
        self.free_text = []
        self.options = []
        self.accessories = []
        self.handles = []
        self.sidebar_room_name = ''
        self._split()
        self._structure()
        self._checks()
        self._forms()

    # ---- step 1: lines into labelled blocks ------------------------------------------------------
    def _split(self):
        lines = self.raw_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        cur = None
        for raw in lines:
            if not raw.strip():
                continue
            s = raw.strip()
            rm = ROOM_RE.match(s)
            if rm and not self.sidebar_room_name and cur is None:
                self.sidebar_room_name = re.sub(r'\s+', ' ', rm.group(1).strip(' -:\t'))
                continue
            m = LABEL_RE.match(s)
            if m and raw[:1] not in '\t ' and m.group(1).upper() != 'ROOM DETAILS':
                label = CANON.get(m.group(1).upper(), m.group(1))
                label = label if label == 'ROOM OPTIONS and ACCESSORIES' else label.upper()
                value = m.group(3).strip()
                if label in self.fields:
                    self.flags.append('CHECK label %s appears twice in the sidebar' % label)
                    label = label + ' (2)'
                self.fields[label] = {'value': value, 'lines': []}
                self.order.append(label)
                cur = label
            else:
                # a column-0 line in capitals with no digits, under a one-line label, is a room-level remark the
                # designer typed ('HOLES FOR ADJUSTABILITY'), not a continuation of that label
                shout = raw[:1] not in '\t ' and s.upper() == s and not re.search(r'\d', s) and '-' not in s
                if cur is None or (shout and cur not in ('HANDLES/KNOBS', 'ROOM OPTIONS and ACCESSORIES', 'DESIGN NOTES', 'ROOM INFORMATION')):
                    self.free_text.append(s)
                else:
                    self.fields[cur]['lines'].append(s)

    # ---- step 2: structure each block ------------------------------------------------------------
    def _structure(self):
        F = self.fields
        S = self.structured = collections.OrderedDict()

        def take(label):
            return F.get(label, {'value': '', 'lines': []})

        # HEIGHT
        h = take('HEIGHT')
        S['height'] = {'text': h['value'], 'inches': frac(h['value']) if re.fullmatch(r'[\d\s/."]+', h['value'] or 'x') else None}
        if h['lines']:
            S['height']['more'] = h['lines']
        # GARMENT LENGTH
        g = take('GARMENT LENGTH')
        gl = {'text': g['value']}
        m = re.search(r'SH\s*([\d/."]+)?', g['value'] or '')
        if m:
            gl['short_hang'] = m.group(1)
        m = re.search(r'LH\s*([\dA-Za-z/."]+)?', g['value'] or '')
        if m:
            gl['long_hang'] = m.group(1)
        S['garment_length'] = gl
        # MATERIAL/COLOR + depths + promo
        mc = take('MATERIAL/COLOR')
        mat = {'name': mc['value'].strip(' -'), 'depths': [], 'promo': False, 'other_lines': []}
        for ln in mc['lines']:
            dm = re.fullmatch(r'([\d\s/.]+)"?\s*deep\.?', ln, re.I)
            if dm:
                mat['depths'].append(frac(dm.group(1)))
            elif 'promo' in ln.lower():
                mat['promo'] = True
                mat['promo_text'] = ln
            else:
                mat['other_lines'].append(ln)
        if 'promo' in mat['name'].lower():
            mat['promo'] = True
        mat['in_workbook_list'] = MATERIALS_UP.get(mat['name'].upper())
        S['material'] = mat
        # EDGE BANDING
        eb = take('EDGE BANDING')
        band = {'text': eb['value'], 'colour': eb['value'], 'thickness': None}
        bm = re.match(r'^(.*?)\s*(\d*\.?\d+)\s*mm\b(.*)$', eb['value'] or '', re.I)
        if bm:
            band['colour'] = bm.group(1).strip(' -')
            band['thickness'] = bm.group(2) + 'mm'
            if bm.group(3).strip():
                band['extra'] = bm.group(3).strip(' -')
        if eb['lines']:
            band['more'] = eb['lines']
        S['edge_banding'] = band
        # BACKING
        bk = take('BACKING')
        S['backing'] = {'text': bk['value'], 'more': bk['lines']} if bk['value'] or bk['lines'] else {'text': None}
        # CLOSET RODS
        cr = take('CLOSET RODS')
        rtype, rqty = split_qty(cr['value'] or '')
        S['closet_rods'] = {'text': cr['value'], 'type': rtype, 'qty': rqty, 'more': cr['lines']}
        # HANDLES/KNOBS
        hk = take('HANDLES/KNOBS')
        hl = ([hk['value']] if hk['value'] else []) + hk['lines']
        notes_h = []
        last = None
        for ln in hl:
            if re.search(r'do not match', ln, re.I):
                notes_h.append(ln)
                continue
            name, qty = split_qty(ln)
            stock = bool(re.search(r'[-\s]Stock\s*$', name, re.I))
            if stock:
                name = re.sub(r'[-\s]*Stock\s*$', '', name, flags=re.I)
            enter_pn = bool(re.search(r'[-\s]*Enter PN\s*$', name, re.I))
            if enter_pn:
                name = re.sub(r'[-\s]*Enter PN\s*$', '', name, flags=re.I)
            part, vend, basis, rest = find_part(name)
            if qty is None and last is not None and (part or vend) and not last.get('part'):
                # a second line that only carries the typed vendor + part number of the line above
                last['part'] = part
                last['vendor'] = vend
                last['vendor_basis'] = basis
                last['typed_line'] = ln
                last['finish_text'] = rest or None
                continue
            entry = {'text': ln, 'name': rest.strip(' -') or name.strip(' -'), 'part': part, 'vendor': vend, 'vendor_basis': basis,
                     'qty': qty, 'stock_mark': stock, 'enter_pn_placeholder': enter_pn,
                     'special_order': bool(re.search(r'special order', name, re.I))}
            self.handles.append(entry)
            last = entry
        S['handles'] = {'items': self.handles, 'kcd_notes': notes_h}
        # DOOR/DRAWER STYLE
        dd = take('DOOR/DRAWER STYLE')
        door = {'style': dd['value'].strip(' -'), 'colour': None, 'finish': None, 'hinge_text': None, 'hinge_count': None, 'other_lines': []}
        for ln in dd['lines']:
            m = re.match(r'^Finish-\s*(.*?)(?:\s+Color-\s*(.*))?$', ln, re.I)
            if m:
                door['finish'] = m.group(1).strip()
                if m.group(2):
                    door['colour'] = m.group(2).strip()
                continue
            m = re.match(r'^Color-\s*(.*)$', ln, re.I)
            if m:
                door['colour'] = m.group(1).strip()
                continue
            m = re.match(r'^(.*?)\s*Hinge Count-\s*([\d.]+)', ln, re.I)
            if m:
                door['hinge_text'] = m.group(1).strip()
                door['hinge_count'] = float(m.group(2))
                continue
            door['other_lines'].append(ln)
        door['kind'] = classify_door(door['style'])
        m = re.search(r'\b(CF\s*M|M\s*CF\s*5|MITER)\b', dd['value'] + ' ' + ' '.join(dd['lines']), re.I)
        door['joint'] = 'Miter' if m else ('Butt Joint' if re.search(r'\b(CF\s*B|B\s*CF\s*5|BUTT)\b', dd['value'] + ' ' + ' '.join(dd['lines']), re.I) else None)
        if door['kind'] == 'thermofoil':
            door['doormark_design'], door['doormark_code'] = doormark_design(door['style'])
            cu = (door['colour'] or '').upper().replace(' SM', '').strip()
            door['doormark_colour_code'] = DOORMARK_COLORS.get(cu)
        S['door_drawer_style'] = door
        # DRAWER BOX
        db = take('DRAWER BOX')
        box = {'type': db['value'].strip(' -'), 'colour': None, 'glides': None, 'other_lines': []}
        for ln in db['lines']:
            m = re.match(r'^Color-\s*(.*)$', ln, re.I)
            if m:
                box['colour'] = m.group(1).strip()
            elif 'glide' in ln.lower():
                box['glides'] = ln
            else:
                box['other_lines'].append(ln)
        S['drawer_box'] = box
        # CROWN / BASE
        for lab, key in (('CROWN', 'crown'), ('BASE', 'base')):
            f = take(lab)
            if not f['value'] and not f['lines']:
                S[key] = {'present': False}
                continue
            t, q = split_qty(f['value'])
            m = re.match(r'^(.*?)-(\d+\s*foot)$', t, re.I)
            ent = {'present': True, 'text': f['value'], 'type': (m.group(1) if m else t).strip(), 'length': m.group(2) if m else None,
                   'qty': q, 'colour': None, 'other_lines': []}
            for ln in f['lines']:
                cm = re.match(r'^Color-\s*(.*)$', ln, re.I)
                if cm:
                    ent['colour'] = cm.group(1).strip()
                else:
                    ent['other_lines'].append(ln)
            S[key] = ent
        # COUNTERTOP
        ct = take('COUNTERTOP TYPE')
        if ct['value'] or ct['lines']:
            top = {'text': ct['value'], 'type': ct['value'], 'colour': None, 'area_sqft': None, 'other_lines': []}
            m = re.match(r'^(.*?)\s*Color-\s*(.*)$', ct['value'], re.I) or re.match(r'^(\w[\w ]*?)-\s*(.*)$', ct['value'])
            if m:
                top['type'], top['colour'] = m.group(1).strip(), m.group(2).strip()
            for ln in ct['lines']:
                am = re.match(r'^Area-\s*([\d\s/.]+)-?\s*sq\.?\s*ft', ln, re.I)
                if am:
                    top['area_sqft'] = frac(am.group(1))
                else:
                    top['other_lines'].append(ln)
            S['countertop'] = top
        else:
            S['countertop'] = {'text': None}
        # ROOM OPTIONS and ACCESSORIES
        ro = take('ROOM OPTIONS and ACCESSORIES')
        items = ([ro['value']] if ro['value'] and ro['value'].lower().strip(' -') not in ('as listed', '') else []) + ro['lines']
        other = []
        for ln in items:
            m = re.match(r'^Opt-\s*(.*?)\s*-?\s*Qty\s*[-\s]*([\d.]+)\s*$', ln, re.I)
            if m:
                self.options.append({'text': ln, 'name': m.group(1).strip(), 'qty': float(m.group(2))})
                continue
            m = re.match(r'^RM\s*(\d+)\s+(.*)$', ln)
            if m:
                part, vend, basis, rest = find_part(m.group(2))
                self.accessories.append({'text': ln, 'rm': int(m.group(1)), 'name': rest.strip(' -') or m.group(2).strip(),
                                         'part': part, 'vendor': vend, 'vendor_basis': basis,
                                         'special_mark': ln.rstrip().endswith('**')})
                continue
            other.append(ln)
        S['room_options'] = {'options': self.options, 'accessories': self.accessories, 'other_lines': other}
        # DESIGN NOTES
        dn = take('DESIGN NOTES')
        des = {'jewelry_colour': None, 'drawer_number': None, 'divider_info': None, 'ctop_template': None, 'specialty': None, 'other_lines': []}
        for ln in ([dn['value']] if dn['value'] else []) + dn['lines']:
            m = re.match(r'^Dr#\s*(\S*)\s*Jewelry Color-\s*(.*)$', ln, re.I)
            if m:
                des['drawer_number'] = m.group(1) or None
                des['jewelry_colour'] = m.group(2).strip() or None
                continue
            for key, lab in (('divider_info', 'Divider Info'), ('ctop_template', 'C top template'), ('specialty', 'Specialty')):
                mm = re.match(r'^%s-\s*(.*)$' % re.escape(lab), ln, re.I)
                if mm:
                    des[key] = mm.group(1).strip() or None
                    break
            else:
                des['other_lines'].append(ln)
        S['design_notes'] = des
        # ROOM INFORMATION
        ri = take('ROOM INFORMATION')
        info = {'base_height': None, 'wall_floor': None, 'floor': None, 'elevator': None, 'preparation': None, 'obstructions': None, 'other_lines': []}
        prev = None
        for ln in ([ri['value']] if ri['value'] else []) + ri['lines']:
            m = re.match(r'^Base Height-\s*(.*)$', ln, re.I)
            if m:
                info['base_height'] = m.group(1).strip() or None
                prev = 'base_height'; continue
            m = re.match(r'^(Drywall|Plaster|Block|Concrete|Wood)\s*/\s*(.*)$', ln, re.I)
            if m:
                info['wall_floor'] = ln; prev = None; continue
            m = re.match(r'^Floor\s*#\s*(\d*)\s*/?\s*(No Elevator|Elevator)?', ln, re.I)
            if m:
                info['floor'] = m.group(1) or None
                info['elevator'] = None if not m.group(2) else (m.group(2).lower() != 'no elevator')
                prev = None; continue
            if 'preparation' in ln.lower():
                info['preparation'] = ln; prev = None; continue
            m = re.match(r'^(No Obstructions|Obstructions?-?\s*(.*))$', ln, re.I)
            if m:
                info['obstructions'] = 'None' if ln.lower().startswith('no ') else (m.group(2).strip() or ln)
                prev = 'obstructions'; continue
            if prev == 'obstructions':
                info['obstructions'] = (info['obstructions'] or '') + ' ' + ln
                continue
            info['other_lines'].append(ln)
        S['room_information'] = info
        # anything labelled that we did not model
        for lab in self.order:
            if lab not in ('HEIGHT', 'GARMENT LENGTH', 'MATERIAL/COLOR', 'EDGE BANDING', 'BACKING', 'CLOSET RODS', 'HANDLES/KNOBS',
                           'DOOR/DRAWER STYLE', 'DRAWER BOX', 'CROWN', 'BASE', 'COUNTERTOP TYPE', 'ROOM OPTIONS and ACCESSORIES',
                           'DESIGN NOTES', 'ROOM INFORMATION'):
                S.setdefault('unmodelled', {})[lab] = F[lab]
                self.flags.append('NOTE sidebar label %r is not modelled yet: %r' % (lab, F[lab]))
        # wall notes of this room (the other notes)
        self.wall_notes = [{'text': n['text'], 'wall': n['wall']} for i, n in enumerate(self.job.notes)
                           if n['room'] == self.room and i != self.note_index and n['text'].strip()
                           and not n['text'].lstrip().upper().startswith('ROOM DETAILS')]

    # ---- step 3: sidebar against the unit records -----------------------------------------------
    def _checks(self):
        S = self.structured
        job = self.job
        units = [u for u in job.units if u.room == self.room]
        self.unit_count = len(units)
        C = self.checks = []

        def chk(what, sidebar, jobval, ok, note=''):
            C.append({'what': what, 'sidebar': sidebar, 'job': jobval, 'agree': ok, 'note': note})

        # rods: slots I251..I253 > 0, times unit quantity
        rods = sum(len(u.rods) * max(1, u.qty) for u in units)
        sq = S['closet_rods']['qty']
        chk('closet rods', sq, rods, sq is not None and abs(sq - rods) < 0.01, 'rods counted from slots I251..I253 of every unit in the room')
        # rod type against Set Unit Info text 4 of the room defaults
        rd = job.room_defaults[self.room - 1] if self.room - 1 < len(job.room_defaults) else []
        rod_default = rd[3].strip() if len(rd) > 3 else ''
        if S['closet_rods']['type'] or rods:
            chk('rod type', S['closet_rods']['type'], rod_default, base_name(S['closet_rods']['type']) == base_name(rod_default) or (not S['closet_rods']['type'] and rods == 0), 'room default text 4')
        # accessories: units of type 1000 (and backing/mirror units named in the list) against the RM lines
        acc_units = collections.Counter()
        for u in units:
            if u.T == 1000 and u.pcb.lower() not in ('none', '') or (u.T == 1000 and u.cab.lower().startswith('cfaccessory')):
                acc_units[u.cat.strip()] += max(1, u.qty)
            elif u.T == 1000 and u.cab.lower().startswith('kcd'):
                acc_units[u.cat.strip()] += max(1, u.qty)
        # a sidebar line may carry a typed tail ('Lock Magnetic w/ extra fob**'): match it to the unit name it starts with
        acc_side = collections.Counter()
        for a in self.accessories:
            nm = a['name'].rstrip('*').strip()
            hit = [u for u in acc_units if nm.lower().startswith(u.lower()) and len(u) >= 4]
            if hit and nm not in acc_units:
                a['unit_name'] = max(hit, key=len)
                a['typed_tail'] = nm[len(a['unit_name']):].strip(' -')
                nm = a['unit_name']
            acc_side[nm] += 1
        for name in sorted(set(acc_units) | set(acc_side)):
            sidev = acc_side.get(name, 0)
            # the sidebar names 'Back-Melamine Match-3/4 Mysterious' and 'Mirror Back' for backing units (type 500), not type 1000
            if sidev and not acc_units.get(name) and re.search(r'\bback', name, re.I):
                nb = sum(max(1, u.qty) for u in units if u.T == 500)
                chk('accessory %s' % name, sidev, nb, sidev == nb, 'backing units (type 500) in the room')
                continue
            jv = acc_units.get(name, 0)
            chk('accessory %s' % name, sidev, jv, sidev == jv, 'accessory units (type 1000) in the room, by their KCD name')
        # accessory part numbers against the unit code (e.g. 300.3146.BLK(547.43.305))
        for a in self.accessories:
            if not a['part']:
                continue
            for u in units:
                if u.cat.strip() == a['name'] and '(' in u.name:
                    code = u.name[u.name.find('(') + 1:u.name.find(')')]
                    chk('part number of %s' % a['name'], a['part'], code, a['part'] == code, 'unit code %s' % u.name.strip())
        # options: pairs per option number against the Opt- lines
        opt_counts = collections.Counter()
        for u in units:
            for o in u.options:
                opt_counts[o] += 1
        for o in self.options:
            matched = None
            for num, nm in KNOWN_OPTIONS.items():
                if nm.lower() in o['name'].lower():
                    matched = num
            if matched is not None:
                jv = opt_counts.get(matched, 0)
                chk('option %s (#%d)' % (o['name'], matched), o['qty'], jv, abs(o['qty'] - jv) < 0.01, 'units carrying option #%d' % matched)
            else:
                chk('option %s' % o['name'], o['qty'], dict(opt_counts), None, 'option numbers in the file: %s; the name needs options.dat to match' % dict(opt_counts))
        # materials: Set Unit Info texts of the units (majority) and the room defaults against the sidebar
        def majority(idx):
            c = collections.Counter(u.set_unit_info[idx].strip() for u in units if len(u.set_unit_info) > idx and u.set_unit_info[idx].strip())
            return c.most_common(1)[0][0] if c else '', dict(c)
        mat_u, mat_all = majority(0)
        mat_u_name = re.sub(r'(\s+[-\d.]+)+\s*$', '', mat_u).strip()
        chk('material', S['material']['name'], mat_u_name, base_name(S['material']['name']) == base_name(mat_u_name), 'unit text 1 (all: %s)' % mat_all)
        face_u, face_all = majority(1)
        chk('door/drawer style', S['door_drawer_style']['style'], face_u, base_name(S['door_drawer_style']['style']).replace(' TH', '') == base_name(face_u).replace(' TH', '') or (S['door_drawer_style']['kind'] == 'none'), 'unit text 2 (all: %s); room default: %r' % (face_all, rd[1] if len(rd) > 1 else ''))
        band_u, _ = majority(2)
        chk('edge banding', S['edge_banding']['text'], band_u, base_name(S['edge_banding']['text']) == base_name(band_u), 'unit text 3')
        base_u, _ = majority(4)
        if S['base'].get('present'):
            chk('base type', S['base']['type'], base_u, base_name(S['base']['type']) == base_name(base_u), 'unit text 5')
        crown_u, _ = majority(5)
        if S['crown'].get('present'):
            chk('crown type', S['crown']['type'], crown_u, base_name(S['crown']['type']) == base_name(crown_u), 'unit text 6')
        box_u, _ = majority(7)
        chk('drawer box', S['drawer_box']['type'], box_u, base_name(S['drawer_box']['type']) == base_name(box_u) or 'no drawer' in S['drawer_box']['type'].lower(), 'unit text 8')
        ctop_u, _ = majority(12)
        if S['countertop'].get('text'):
            chk('countertop', S['countertop']['type'], ctop_u, base_name(S['countertop']['type']) == base_name(ctop_u), 'unit text 13')
        fin_u, _ = majority(13)
        ins_u, _ = majority(14)
        self.unit_texts = {'finishing_text14': fin_u, 'insert_text15': ins_u, 'contrast_text12': majority(11)[0], 'handle_text11': majority(10)[0]}
        # depths: the sidebar's N" deep lines against the cabinet depths in the room
        cab_depths = sorted({round(u.D * 16) / 16 for u in units if u.T not in (230, 1000, 500, 550, 880, 20, 10, 890, 640, 641) and u.pcb.lower() not in ('none', '') and u.D > 2 and u.H > 6})
        if S['material']['depths']:
            chk('depths', S['material']['depths'], cab_depths, set(S['material']['depths']) == set(cab_depths), 'cabinet depths (fillers, panels, accessories, shelves left out)')
        # height: the sidebar HEIGHT against the tallest cabinet
        hmax = max([u.H for u in units if u.T not in (1000, 20, 10, 890)] or [0])
        if S['height']['inches']:
            chk('height', S['height']['inches'], round(hmax * 16) / 16, abs(S['height']['inches'] - hmax) < 1.0, 'tallest unit; the skill card says the sidebar HEIGHT routinely differs from the elevation and is not a finding')
        # handles: sidebar qty against drawer fronts counted from the unit names (doors are the open question)
        drawers = 0
        for u in units:
            m = re.search(r'(\d+)\s*Drawer', u.cat, re.I)
            if m:
                drawers += int(m.group(1)) * max(1, u.qty)
            elif re.search(r'\bDrawer\b', u.cat, re.I) and 'no drawer' not in u.cat.lower():
                drawers += max(1, u.qty)
        self.drawer_fronts_from_names = drawers
        for h in self.handles:
            chk('handle qty %s' % (h['part'] or h['name']), h['qty'], {'drawer fronts (from unit names)': drawers},
                None, 'doors are not counted (the open no-door question); the skill card says the sidebar hardware qty is not the check, count the faces on the drawings')
        # jewelry trays: which drawer unit hosts them
        self.jt_hosts = []
        for u in units:
            if u.T == 1000 and re.match(r'\s*JT\b', u.cat):
                host = None
                for c in units:
                    if c.wall == u.wall and c.T not in (1000, 230, 500, 550, 641, 640, 880, 890) and c.X - 0.01 <= u.X < c.X + c.W + 0.01:
                        host = c
                        break
                self.jt_hosts.append({'tray': u.cat.strip(), 'unit_id': u.id, 'wall': u.wall, 'X': round(u.X, 3),
                                      'host': None if host is None else {'id': host.id, 'name': host.cat.strip(), 'cab': host.cab, 'W': round(host.W, 4), 'D': round(host.D, 4),
                                                                          'LS': round(host.LS, 4), 'RS': round(host.RS, 4), 'ES_width': round(host.W - host.LS - host.RS, 4)}})

    # ---- step 4: what the sidebar can feed -------------------------------------------------------
    def _forms(self):
        S = self.structured
        forms = self.forms = {'workbook': {}, 'po': [], 'doors': {}, 'vjt': []}
        fl = self.flags

        def wb(cell, value, certainty, source):
            forms['workbook'][cell] = {'value': value, 'certainty': certainty, 'source': source}

        # F5 unit material
        mat = S['material']['name']
        if S['material']['in_workbook_list']:
            wb('F5', S['material']['in_workbook_list'], 'certain', 'MATERIAL/COLOR, exact dropdown value')
        else:
            wb('F5', mat, 'inferred', 'MATERIAL/COLOR; NOT in the template dropdown list (B1:B83) as written')
            fl.append('CHECK F5: material %r is not in the workbook dropdown list; the engineer picks the list entry' % mat)
        # F7 / F9 banding
        if S['edge_banding']['thickness'] in BANDING_TYPES:
            wb('F7', S['edge_banding']['thickness'], 'certain', 'EDGE BANDING thickness')
        else:
            wb('F7', None, 'unknown', 'EDGE BANDING has no thickness (%r)' % S['edge_banding']['text'])
            fl.append('CHECK F7: no banding thickness on the EDGE BANDING line (%r)' % S['edge_banding']['text'])
        bc = S['edge_banding']['colour']
        bc_list = MATERIALS_UP.get(bc.upper()) or MATERIALS_UP.get((bc + ' Grain').upper())
        wb('F9', bc_list or bc, 'certain' if bc_list else 'inferred', 'EDGE BANDING colour' + ('' if bc_list else '; not an exact dropdown value'))
        if base_name(bc) != base_name(mat):
            fl.append('NOTE two-tone: edge banding %r is not the unit colour %r (skill card: flag a banding whose base colour differs)' % (bc, mat))
        # F11 face type / F13 faces material
        d = S['door_drawer_style']
        if d['kind'] == 'melamine':
            if '2nd material' in d['style'].lower():
                wb('F11', 'Melamine', 'inferred', 'DOOR/DRAWER STYLE "Melamine 2nd Material"; F13 is then the contrast colour (unit text 12 %r)' % self.unit_texts['contrast_text12'])
                wb('F13', d['colour'] or None, 'unknown', 'contrast face colour: sidebar Color- line %r / unit text 12 %r' % (d['colour'], self.unit_texts['contrast_text12']))
                fl.append('CHECK F13: second-material faces; confirm the face colour')
            else:
                wb('F11', 'Melamine', 'certain', 'DOOR/DRAWER STYLE Melamine')
        elif d['kind'] == 'none':
            wb('F11', 'Melamine', 'inferred', 'no door or drawer faces in the room; DRUBEL was filled Melamine')
        elif d['kind'] == 'thermofoil':
            wb('F11', 'Thermo Foil', 'inferred', 'TH door style; WERNER\'s engineer picked "Thermo Foil" (Doormark). "CF Thermo Foil" is the other list entry: which one depends on who makes the door')
            fl.append('CHECK F11: thermofoil doors: Doormark ("Thermo Foil") or in-house CF Thermo ("CF Thermo Foil")?')
        elif d['kind'] == 'cf5':
            wb('F11', 'CF5', 'inferred', 'DOOR/DRAWER STYLE names CF 5')
        else:
            wb('F11', None, 'unknown', 'DOOR/DRAWER STYLE %r not classified' % d['style'])
            fl.append('CHECK F11: door style %r not recognised' % d['style'])
        # F21 / F23 molding
        base, crown = S['base'], S['crown']
        has_base = bool(base.get('present') and (base.get('qty') or 0) > 0)
        has_crown = bool(crown.get('present') and (crown.get('qty') or 0) > 0)
        loc = {(False, False): 'None', (True, False): 'Base Only', (False, True): 'Crown Only', (True, True): 'Base & Crown'}[(has_base, has_crown)]
        mold_src = (base if has_base else crown).get('type', '') if (has_base or has_crown) else ''
        ml = mold_src.lower()
        if not (has_base or has_crown):
            mold = 'None'
        elif ml.startswith('th'):
            mold = 'Thermo Foil'
        elif 'melamine' in ml:
            mold = 'Melamine'
        elif 'wood' in ml:
            mold = 'Wood'
        elif 'mica' in ml:
            mold = 'Mica'
        else:
            mold = None
        wb('F21', mold, 'certain' if mold in ('None', 'Melamine') else 'inferred', 'BASE %r / CROWN %r' % (base.get('text'), crown.get('text')))
        wb('F23', loc, 'certain', 'BASE qty %s, CROWN qty %s' % (base.get('qty'), crown.get('qty')))
        if mold == 'Thermo Foil':
            fl.append('NOTE F21 Thermo Foil from base type %r (WERNER: TH Square -> Thermo Foil, Base Only)' % mold_src)
        fl.append('NOTE base/crown quantities on the sidebar are not a check (skill card); the remeasure may say no molding (NEDDIE)')
        # B13 jewelry tray
        jt_lines = [a for a in self.accessories if re.match(r'JT\b', a['name'])]
        if jt_lines:
            wb('B13', None, 'unknown', '%d jewelry tray lines (%s); Special Order / Cut From Stock / Combination is not on the sidebar' % (len(jt_lines), ', '.join(a['name'] for a in jt_lines)))
            fl.append('CHECK B13: the room has jewelry trays (%s); answer Special Order / Cut From Stock / Combination' % ', '.join(a['name'] for a in jt_lines))
        else:
            wb('B13', None, 'unknown', 'no jewelry tray line on the sidebar (the template default is blank)')
        # B15 hinge type
        wb('B15', None, 'unknown', 'hinge closing type is not on the sidebar; the Hinge Count line (%r) is overlay/position, not Self Closing / Free Swing' % d['hinge_text'])
        # B19 other special orders
        so = []
        if d['kind'] in ('thermofoil', 'cf5', 'elements', 'framed'):
            so.append('special-order doors (%s)' % d['style'])
        if any(h['special_order'] or h['enter_pn_placeholder'] for h in self.handles):
            so.append('special-order handle')
        wb('B19', 'YES' if so else None, 'inferred' if so else 'unknown', '; '.join(so) if so else 'nothing on the sidebar says special order (what counts is the owner\'s rule)')
        # B21 finishing
        ct = S['countertop']
        if ct.get('text') and re.search(r'wood', ct.get('type') or '', re.I) and re.search(r'stain|paint|glaze', (ct.get('colour') or '') + ' ' + (ct.get('type') or ''), re.I):
            wb('B21', 'YES', 'inferred', 'wood countertop with a stain/paint colour (%r); WERNER was YES' % ct.get('colour'))
        elif re.search(r'wood', (mat or '') + ' ' + (d['style'] or ''), re.I):
            wb('B21', 'YES', 'inferred', 'wood material or wood doors')
        else:
            wb('B21', None, 'unknown', 'nothing on the sidebar needs finishing')
        # purchase order lines: handles and accessories with a part number
        rn = self.kcd_room_name
        for h in self.handles:
            if h['part']:
                forms['po'].append({'room': rn, 'qty': h['qty'], 'item': 'HANDLE (door or drawer: see faces)', 'description': h['part'].replace('-', ''),
                                    'vendor': h['vendor'], 'certainty': 'inferred' if (h['vendor_basis'] or '').startswith('number') else 'certain',
                                    'source': h['text'] + ((' + ' + h['typed_line']) if h.get('typed_line') else ''),
                                    'note': 'qty is the sidebar count; drawer fronts in the file: %d; doors not counted' % self.drawer_fronts_from_names})
            else:
                forms['po'].append({'room': rn, 'qty': h['qty'], 'item': 'HANDLE', 'description': h['name'], 'vendor': None, 'certainty': 'unknown',
                                    'source': h['text'], 'note': 'no part number on the sidebar'})
                fl.append('CHECK PO: handle line %r has no part number' % h['text'])
        acc_groups = collections.OrderedDict()
        for a in self.accessories:
            acc_groups.setdefault((a['name'], a['part']), []).append(a)
        for (name, part), grp in acc_groups.items():
            if part:
                forms['po'].append({'room': rn, 'qty': len(grp), 'item': name, 'description': part, 'vendor': grp[0]['vendor'],
                                    'certainty': 'inferred' if (grp[0]['vendor_basis'] or '').startswith('number') else 'certain',
                                    'source': grp[0]['text'], 'note': 'qty = number of RM lines (one per unit placed)'})
            else:
                forms['po'].append({'room': rn, 'qty': len(grp), 'item': name, 'description': None, 'vendor': None, 'certainty': 'unknown',
                                    'source': grp[0]['text'], 'note': 'no part number: stock item or library accessory; whether it goes on the PO is the engineer\'s call'})
        # door form header
        if d['kind'] not in ('none', 'melamine', 'unknown'):
            forms['doors'] = {'form': {'thermofoil': 'Doormark (or CF Thermo)', 'cf5': 'CF5', 'elements': 'Elements', 'framed': 'Framed (which form?)'}[d['kind']],
                              'design': {'value': d['style'], 'certainty': 'certain', 'source': 'DOOR/DRAWER STYLE'},
                              'design_code': {'value': d.get('doormark_code'), 'certainty': 'certain' if d.get('doormark_code') else 'unknown', 'source': 'workbook table Data Conversions X3:Y36 (%s)' % d.get('doormark_design')},
                              'colour': {'value': d['colour'], 'certainty': 'certain' if d['colour'] else 'unknown', 'source': 'Color- line under DOOR/DRAWER STYLE'},
                              'colour_code': {'value': d.get('doormark_colour_code'), 'certainty': 'certain' if d.get('doormark_colour_code') else 'unknown', 'source': 'workbook table X41:Y58' + ('' if d.get('doormark_colour_code') else '; colour not in the table, engineer types the vendor code')},
                              'finish': {'value': d['finish'], 'certainty': 'certain' if d['finish'] else 'unknown', 'source': 'Finish- line'},
                              'insert': {'value': self.unit_texts['insert_text15'] or None, 'certainty': 'certain' if self.unit_texts['insert_text15'] else 'unknown', 'source': 'unit Set Unit Info text 15 (not on the sidebar)'},
                              'joint': {'value': d['joint'], 'certainty': 'certain' if d['joint'] else 'unknown', 'source': 'CF M / CF B on the sidebar; blank = engineer\'s choice, usually butt (skill card)'},
                              'match_back': {'value': 'X', 'certainty': 'inferred', 'source': 'skill card: ticked for every colour'},
                              'door_sizes': {'value': None, 'certainty': 'unknown', 'source': 'NOT on the sidebar: from the unit records + .cab face rules (kcdcab) and the door-size elevation; Doormark sizes run 1/16 under KCD on WERNER'}}
            if d['kind'] == 'thermofoil' and not d.get('doormark_code'):
                fl.append('CHECK door form: design %r not in the Doormark design table' % d['style'])
            if d['kind'] == 'thermofoil' and not d.get('doormark_colour_code'):
                fl.append('CHECK door form: colour %r has no code in the workbook colour table (WERNER: engineer typed MYST for MYSTERIOUS BLUE)' % d['colour'])
        # jewelry tray inputs
        if self.jt_hosts:
            by_host = collections.OrderedDict()
            for j in self.jt_hosts:
                key = j['host']['id'] if j['host'] else None
                by_host.setdefault(key, []).append(j)
            for hid, trays in by_host.items():
                host = trays[0]['host']
                names = [t['tray'] for t in trays]
                styles = []
                for n in names:
                    s = re.sub(r'^JT\s*', '', n).upper().strip()
                    s = {'STANDARD EARRING': 'STANDARD W/ EARRINGS', 'EARRING': 'EARRINGS'}.get(s, s)
                    styles.append(s if s in VJT_INSERTS else s + ' (not in the form list)')
                dep = host['D'] if host else None
                box_depth = None
                if dep is not None:
                    box_depth = 15 if abs(dep - 16) < 0.01 else 18 if abs(dep - 19) < 0.01 else 21 if dep > 22 else None
                ent = {'host_unit': host, 'trays': names,
                       'layout': {'value': '2 = DBL VJT' if len(trays) == 2 else None, 'certainty': 'inferred' if len(trays) == 2 else 'unknown',
                                  'source': '%d tray lines on one drawer unit' % len(trays) + ('; a wall note may say which drawer' if len(trays) != 2 else '')},
                       'shelf_width': {'value': host['ES_width'] if host else None, 'certainty': 'inferred' if host else 'unknown', 'source': 'host unit W - LS - RS (the ES width); the form takes -2" itself'},
                       'drawer_depth': {'value': box_depth, 'certainty': 'inferred' if box_depth else 'unknown', 'source': 'host depth %s -> drawer box depth by the 16->15, 19->18, >22->21 rule' % dep},
                       'insert_bottom': {'value': styles[-1] if styles else None, 'certainty': 'inferred', 'source': 'tray name(s) %s; which is top and which is bottom comes from the wall note, not the sidebar' % names},
                       'insert_top': {'value': styles[0] if len(styles) > 1 else None, 'certainty': 'inferred' if len(styles) > 1 else 'unknown', 'source': 'second tray name'},
                       'colour': {'value': S['design_notes']['jewelry_colour'], 'certainty': 'certain' if S['design_notes']['jewelry_colour'] else 'unknown', 'source': 'DESIGN NOTES Jewelry Color-'},
                       'drawer_number': {'value': S['design_notes']['drawer_number'], 'certainty': 'certain' if S['design_notes']['drawer_number'] else 'unknown', 'source': 'DESIGN NOTES Dr#'}}
                forms['vjt'].append(ent)
                fl.append('CHECK VJT: trays %s on unit %s; layout, top/bottom order and drawer number need the engineer (wall notes: %s)' %
                          (names, hid, [n['text'] for n in self.wall_notes if re.search(r'jewel|JT|tray', n['text'], re.I)]))
        # general flags from the checks
        for c in self.checks:
            if c['agree'] is False:
                fl.append('CHECK %s: sidebar %r, job %r (%s)' % (c['what'], c['sidebar'], c['job'], c['note']))
        for h in self.handles:
            if h['enter_pn_placeholder']:
                fl.append('NOTE handle line has the "Enter PN" placeholder; the typed part number is %r (%s)' % (h['part'], h.get('typed_line')))
            if h['stock_mark']:
                fl.append('NOTE handle %r carries the "-Stock-" mark; WERNER still put it on the PO (AMEROCK)' % h['part'])
        if S['handles']['kcd_notes']:
            fl.append('NOTE KCD wrote %r on the sidebar' % S['handles']['kcd_notes'])
        for a in self.accessories:
            if a['special_mark']:
                fl.append('NOTE accessory %r is marked ** on the sidebar' % a['text'])
        if S['material']['promo']:
            fl.append('NOTE material is a promo colour (%r); the unit multiplier is %s' % (S['material'].get('promo_text'), [u.material_multiplier for u in self.job.units if u.room == self.room][:1]))
        if self.free_text:
            fl.append('NOTE free text before any label: %r' % self.free_text)

    def to_dict(self):
        return collections.OrderedDict([
            ('file', self.job.name), ('room', self.room), ('kcd_room_name', self.kcd_room_name),
            ('sidebar_room_name', self.sidebar_room_name), ('units_in_room', self.unit_count),
            ('fields', self.structured), ('options', self.options), ('accessories', self.accessories), ('handles', self.handles),
            ('free_text', {'unlabelled': self.free_text, 'wall_notes': self.wall_notes,
                           'room_options_other': self.structured['room_options']['other_lines']}),
            ('raw_fields', self.fields), ('checks', self.checks), ('forms', self.forms), ('flags', self.flags),
            ('raw_text', self.raw_text)])


def parse_job(path):
    job = kcdunits.read_job(path)
    out = []
    for i, n in enumerate(job.notes):
        if n['text'].lstrip().upper().startswith('ROOM DETAILS'):
            out.append(RoomSidebar(job, n, i))
    rooms_with = {r.room for r in out}
    missing = [(k + 1, nm) for k, nm in enumerate(job.rooms) if (k + 1) not in rooms_with and job.units_in_room(k + 1)]
    return job, out, missing


def summary(job, rooms, missing):
    P = ['FILE %s  heading=%s  rooms=%s' % (job.name, job.heading, list(enumerate(job.rooms, 1)))]
    for r in rooms:
        S = r.structured
        P.append('  room %d KCD %r / sidebar %r  units=%d' % (r.room, r.kcd_room_name, r.sidebar_room_name, r.unit_count))
        P.append('    labels: %s' % ', '.join(r.order))
        P.append('    material %r depths %s promo %s | banding %r %s | rods %r x %s | doors %r (%s) colour %r finish %r | box %r | base %s | crown %s | ctop %s' % (
            S['material']['name'], S['material']['depths'], S['material']['promo'], S['edge_banding']['colour'], S['edge_banding']['thickness'],
            S['closet_rods']['type'], S['closet_rods']['qty'], S['door_drawer_style']['style'], S['door_drawer_style']['kind'],
            S['door_drawer_style']['colour'], S['door_drawer_style']['finish'], S['drawer_box']['type'],
            (S['base'].get('type'), S['base'].get('qty')), (S['crown'].get('type'), S['crown'].get('qty')), (S['countertop'].get('type'), S['countertop'].get('colour'), S['countertop'].get('area_sqft'))))
        for h in r.handles:
            P.append('    handle: %s' % json.dumps({k: v for k, v in h.items() if k != 'text'}))
        for o in r.options:
            P.append('    option: %s x %s' % (o['name'], o['qty']))
        for a in r.accessories:
            P.append('    accessory: RM%d %r part=%r vendor=%r (%s)' % (a['rm'], a['name'], a['part'], a['vendor'], a['vendor_basis']))
        P.append('    design notes: %s' % json.dumps(S['design_notes']))
        P.append('    room info: %s' % json.dumps(S['room_information']))
        for c in r.checks:
            P.append('    check %-40s sidebar=%-28r job=%-28r %s' % (c['what'][:40], c['sidebar'], c['job'], 'OK' if c['agree'] else ('DIFF' if c['agree'] is False else '?')))
        P.append('    workbook: ' + '; '.join('%s=%r[%s]' % (k, v['value'], v['certainty'][0]) for k, v in r.forms['workbook'].items()))
        for l in r.forms['po']:
            P.append('    PO: %s' % json.dumps(l))
        if r.forms['doors']:
            P.append('    door form: ' + '; '.join('%s=%r[%s]' % (k, v['value'], v['certainty'][0]) for k, v in r.forms['doors'].items() if isinstance(v, dict)))
        for v in r.forms['vjt']:
            P.append('    VJT: ' + '; '.join('%s=%r[%s]' % (k, x['value'], x['certainty'][0]) for k, x in v.items() if isinstance(x, dict) and 'value' in x) + ' trays=%s host=%s' % (v['trays'], v['host_unit'] and v['host_unit']['name']))
        for f in r.flags:
            P.append('    ' + f)
        for n in r.wall_notes:
            P.append('    wall note (wall %s): %r' % (n['wall'], n['text']))
    for k, nm in missing:
        P.append('  room %d %r has units but NO ROOM DETAILS note' % (k, nm))
    return '\n'.join(P)


def main(argv):
    out_dir = None
    paths = []
    i = 0
    while i < len(argv):
        if argv[i] == '--out':
            out_dir = argv[i + 1]; i += 2
        else:
            paths.append(argv[i]); i += 1
    if not paths:
        print(__doc__); return 2
    out_dir = out_dir or os.getcwd()
    os.makedirs(out_dir, exist_ok=True)
    everything = []
    for p in paths:
        job, rooms, missing = parse_job(p)
        stem = os.path.splitext(os.path.basename(p))[0]
        for r in rooms:
            safe = re.sub(r'[^A-Za-z0-9]+', '_', r.kcd_room_name).strip('_') or 'room'
            fn = os.path.join(out_dir, '%s - room %d %s.json' % (stem, r.room, safe))
            with open(fn, 'w') as f:
                json.dump(r.to_dict(), f, indent=1, default=str)
            everything.append(r.to_dict())
        txt = summary(job, rooms, missing)
        print(txt)
        with open(os.path.join(out_dir, '%s - sidebar summary.txt' % stem), 'w') as f:
            f.write(txt + '\n')
    with open(os.path.join(out_dir, 'all_rooms.json'), 'w') as f:
        json.dump(everything, f, indent=1, default=str)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
