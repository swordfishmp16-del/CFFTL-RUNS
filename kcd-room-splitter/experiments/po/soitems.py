#!/usr/bin/env python3
"""soitems.py - the SPECIAL ORDER SHEET of a KCD job (prototype, Oct 19 2026).

For every room of a .job it lists
  (a) every door and drawer front: unit, finished size, pair/single, style, colour and which order form it goes on
      (melamine = made in house, no form; thermofoil 'TH' = Doormark; 'CF 5' = CF5 insert form; 'CF Thermo' = CF Thermo form;
      'Elements' = Elements form; anything else = ASK),
  (b) every jewelry tray / velvet insert with the drawer it sits in and what the VJT order form needs,
  (c) every hardware / accessory line for the purchase order (handles, hampers, racks, valets, lights, rods, locks ...).

Sizes come, in this order of preference, from
  1. a price-engine run (kcdprice.py TSV: --price FILE, repeatable; unit column = position among live units),
  2. the engineering workbook paste (--paste FILE.xlsm, Data Entry K..P; unit column = KCD unit id),
  3. the .cab face geometry (kcdcab.UnitFaces) - flagged VERIFY, because the designer's "no door" choice is not in the file.

Nothing is invented: a field the job does not hold is printed as ASK / blank and listed under flags.

Usage:
  python3 soitems.py JOB.job [--lib cat_compact.json --raw rawlib.json] [--price TSV ...] [--paste XLSM]
                     [--room N] [--json OUT.json] [--txt OUT.txt]
"""
import os, re, sys, json, struct, argparse
from fractions import Fraction

sys.path.insert(0, '/home/user/CFFTL-WORKING-/kcd-room-splitter')
import kcdunits, kcdcab

INCH = 254.0


# --------------------------------------------------------------------------- small helpers
def r16(x):
    """Round to the nearest 1/16 (what KCD shows and hands to the price scripts)."""
    return round(x * 16) / 16.0


def frac(x, nd=16):
    """17.3125 -> '17 5/16'. None -> ''."""
    if x is None or x == '':
        return ''
    f = Fraction(x).limit_denominator(nd)
    w, r = divmod(f.numerator, f.denominator)
    if r == 0:
        return str(w)
    if w == 0:
        return '%d/%d' % (r, f.denominator)
    return '%d %d/%d' % (w, r, f.denominator)


def parse_frac(s):
    """'17 5/16' or '17.3125' or '3/4' -> float; '' -> None."""
    s = (s or '').strip().replace('"', '')
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    m = re.match(r'^(-?\d+)?\s*(\d+)/(\d+)$', s)
    if m:
        w = int(m.group(1) or 0)
        v = abs(w) + int(m.group(2)) / int(m.group(3))
        return -v if w < 0 else v
    return None


def dec(x):
    """Vendor forms use decimals: 17.3125."""
    return '' if x is None else ('%.4f' % x).rstrip('0').rstrip('.')


# --------------------------------------------------------------------------- classification rules
# Door / drawer style text -> order form. The text comes from the sidebar's DOOR/DRAWER STYLE line and from
# Set Unit Info text 2 (door type) of each unit. Keyword rules; anything unmatched is ASK.
def classify_style(style):
    s = (style or '').strip()
    l = s.lower()
    if not s:
        return 'ASK', 'no door style text'
    if 'no door' in l or 'no drawer' in l:
        return 'NONE', 'sidebar says no door/drawer faces'
    if 'element' in l:
        return 'ELEMENTS', 'Elements door form (hinge side L/R matters)'
    if 'framed' in l or 'glass' in l or 'mirror' in l:
        return 'ASK', 'framed / glass / mirror door: who makes it is not in the rule table, ask'
    if re.search(r'\bcf ?thermo', l):
        return 'CF THERMO', 'CF Thermo form (workbook tab "CF Thermo")'
    if re.search(r'\bcf ?5\b|5[- ]piece|\bcf ?m\b|\bcf ?b\b|\b[mb] cf ?5\b', l):
        joint = 'MITER' if re.search(r'\bcf ?m\b|\bm cf', l) else ('BUTT' if re.search(r'\bcf ?b\b|\bb cf', l) else '')
        return 'CF5', 'CF5 insert form' + (' joint %s' % joint if joint else ' (joint not called out: engineer\'s choice, default butt)')
    if re.search(r'\bth\b|thermo', l):
        return 'DOORMARK', 'thermofoil -> Doormark Inc. form'
    if 'melamine' in l and 'mldg' not in l and 'applied' not in l:
        return 'IN HOUSE', 'melamine, cut off the nest, no order form'
    return 'ASK', 'style not in the rule table (framed / wood / mirror / egger / applied moulding ...): ask'


# Doormark design and colour codes as the engineering workbook holds them ('Data Conversions' X3:Y36 and X41:Y58 of
# mike_p_for_services template). Read from the workbook, Oct 19 2026. The skill card adds MYBL = Mysterious Blue SM, which the
# workbook table does not have (the WERNER engineer typed 'MYST' by hand).
DOORMARK_DESIGNS = {'ABACOA SHAKER': 'SHA', 'BAHAMA SHAKER': 'SHB', 'BAL HARBOR': 'BAL', 'BIMINI': 'BIM', 'BISCAYNE': 'BIS',
                    'CAPTIVA': 'CAP', 'DAYTONA': 'DAY', 'DORAL': 'DOR', 'ENGLEWOOD': 'ENG', 'EURO SHAKER': 'EUSH',
                    'FREEPORT SHAKER': 'SHF', 'GULFSTREAM': 'GUL', 'HOLLYWOOD': 'HOL', 'ISLAMORADA': 'ISL', 'KEY LARGO': 'KEY',
                    'LAS OLAS': 'LAS', 'MARATHON SHAKER': 'SHM', 'MARTINIQUE': 'MAR', 'MONTEGO': 'MON', 'NAPLES SHAKER': 'SHN',
                    'NASSAU': 'NAS', 'ORLANDO': 'ORL', 'PALM BEACH': 'PAL', 'POMPANO': 'POM', 'PORT CHARLOTTE': 'POR',
                    'SAN MARCO': 'SAN', 'SARASOTA SHAKER': 'SHS', 'SEBRING': 'SEB', 'SOUTH BEACH': 'SOU', 'SUNRISE': 'SUN',
                    'VENICE': 'VEN', 'VIZCAYA': 'VIZ', 'WELLINGTON': 'WEL', 'WESTON': 'WES'}
DOORMARK_COLORS = {'WHITE': 'FWM', 'ALMOND': 'AM', 'APPLE COCOA': 'CHPE', 'BISQUE': 'OWM', 'BLACK': 'BLMA', 'BLACK GLOSS': 'BLGL',
                   'BLANCA ELME': 'BLEL', 'CAMPANIA ELME': 'CAEL', 'ESPRESSO': 'EXPR', 'FOG': 'FOG', 'FOLKSTONE GREY': 'FOST',
                   'FUSION MAPLE': 'FM', 'LEWIS': 'LEWI', 'MARSEILLE': 'MARS', 'MONACO': 'MONA', 'MOSCATTO': 'MOEL',
                   'TENINO GREY': 'TEGR', 'MYSTERIOUS BLUE': 'MYBL (skill card; not in the workbook table)'}

# VJT order form lists ('Data Conversions' L30:L35 and M30:M39). KCD accessory names map onto the insert list by name.
VJT_COLORS = ['Aquamarine', 'Black', 'Blush', 'Champagne', 'Navy Blue', 'Silver']
VJT_INSERTS = ['STANDARD', 'STANDARD W/ EARRINGS', 'EARRINGS', 'VALET', 'SUNGLASS', 'NECKLACE', 'WATCH & BRACELET', 'TIE & BELT',
               'PLAIN TRAY', 'FLAT LINER']
VJT_LAYOUTS = {1: 'BOT TRAY ONLY', 2: 'DBL VJT', 3: 'TOP TRAY ONLY', 4: 'DOVETAIL (NO TOP)'}
VJT_DEPTHS = [12, 15, 18, 21]


def vjt_insert_name(kcd_name):
    n = kcd_name.strip()
    n = re.sub(r'^RM\d+\s+', '', n)
    l = n.lower()
    if l.startswith('jt standard earring'):
        return 'STANDARD W/ EARRINGS'
    if l.startswith('jt standard'):
        return 'STANDARD'
    if l.startswith('jt earring'):
        return 'EARRINGS'
    for ins in VJT_INSERTS:
        if ins.lower().split()[0] in l:
            return ins + ' (by keyword, verify)'
    return 'ASK (%s)' % n


def drawer_box_depth(unit_depth):
    """The pre-eng card's tray rule: 16 -> 15, 19 -> 18, over 22 -> 21 (drawer box depth from the unit depth)."""
    d = r16(unit_depth)
    if abs(d - 16) < 0.01:
        return 15, 'rule 16 -> 15'
    if abs(d - 19) < 0.01:
        return 18, 'rule 19 -> 18'
    if d > 22:
        return 21, 'rule over 22 -> 21'
    return None, 'no rule for a %s deep unit: ask' % frac(d)


# --------------------------------------------------------------------------- what is an accessory / hardware
SITE_CABS = ('outlet.cab', 'switch.cab', 'obstruction.cab', 'utility cover.cab', 'wstv.cab', '010.cab', '020.cab', '025.cab')
STOCK_WORDS = ('led', 'strip light', 'power supply', 'remote', 'receiver', 'sensor', 'driver', 'closet rod', 'shelf stiffener')


def accessory_kind(u):
    """'site' (outlet, window, obstruction: nothing to buy), 'stock' (lights, rods: no vendor row), 'po' (a vendor part number
    is in the unit code), 'ask' (accessory with no part number in the job), or None (a cabinet)."""
    cab = u.cab.lower()
    name = u.kcd_name.lower()
    code = u.kcd_code().strip()
    if cab in SITE_CABS or u.T in (10, 20) or name in ('obstruction', 'electrical outlet', 'window', 'door', 'utility cover'):
        return 'site'
    if u.T == 1000 and (u.pcb or '').strip().lower() in ('', 'none') and not cab.startswith('cfaccessory'):
        return 'site'          # drawing props (shoes, books, clock, TV): no price script, nothing to buy
    if any(w in name for w in ('cutout', 'wiring hole', 'obstruction cut', 'notch')):
        return 'work'
    if any(w in name for w in STOCK_WORDS) or 'light' in cab:
        return 'stock'
    if u.T in (1000, 899) or cab.startswith('cfaccessory') or cab.startswith('kcd') or cab.startswith('tag'):
        if re.search(r'\d{3}\.\d{2}\.\d{3}|\d{3}\.\d{4}', code):
            return 'po'
        return 'ask'
    return None


# --------------------------------------------------------------------------- sidebar
def sidebar_blocks(job):
    """Per room: the sidebar text split into the blocks we need (door style, handles, accessories, jewelry colour ...)."""
    out = {}
    for n in job.sidebar_notes():
        lines = [ln.rstrip() for ln in n['text'].splitlines()]
        d = {'raw': lines, 'style': '', 'style_color': '', 'style_finish': '', 'hinge': '', 'handles': [], 'accessories': [],
             'jewelry_color': '', 'rods': '', 'material': '', 'edge': '', 'drawer_box': '', 'base': '', 'crown': '', 'backing': '',
             'room_details': ''}
        sec = ''
        for ln in lines:
            s = ln.strip()
            if not s:
                continue
            u = s.upper()
            if u.startswith('ROOM DETAILS'):
                d['room_details'] = s[12:].strip(); sec = ''; continue
            m = re.match(r'^(HEIGHT|GARMENT LENGTH|MATERIAL/COLOR|EDGE BANDING|BACKING|CLOSET RODS|HANDLES/KNOBS|DOOR/DRAWER STYLE|DRAWER BOX|BASE|CROWN|COUNTERTOP TYPE|ROOM OPTIONS AND ACCESSORIES|DESIGN NOTES|ROOM INFORMATION)\s*-?\s*(.*)$', u)
            if m:
                key = m.group(1)
                val = s[len(key):].lstrip(' -').strip() if s.upper().startswith(key) else m.group(2)
                sec = key
                if key == 'DOOR/DRAWER STYLE':
                    d['style'] = val
                elif key == 'MATERIAL/COLOR':
                    d['material'] = val
                elif key == 'EDGE BANDING':
                    d['edge'] = val
                elif key == 'CLOSET RODS':
                    d['rods'] = val
                elif key == 'DRAWER BOX':
                    d['drawer_box'] = val
                elif key == 'BASE':
                    d['base'] = val
                elif key == 'CROWN':
                    d['crown'] = val
                elif key == 'BACKING':
                    d['backing'] = val
                continue
            if sec == 'DOOR/DRAWER STYLE':
                mc = re.match(r'^Color-\s*(.*)$', s, re.I)
                mf = re.match(r'^Finish-\s*(.*)$', s, re.I)
                if mf:
                    d['style_finish'] = mf.group(1).strip()
                    mc2 = re.search(r'Color-\s*(.*)$', mf.group(1), re.I)
                    if mc2:
                        d['style_color'] = mc2.group(1).strip()
                        d['style_finish'] = mf.group(1)[:mf.group(1).upper().find('COLOR-')].strip()
                elif mc:
                    d['style_color'] = mc.group(1).strip()
                elif 'hinge count' in s.lower():
                    d['hinge'] = s
            elif sec == 'HANDLES/KNOBS':
                d['handles'].append(s)
            elif sec == 'ROOM OPTIONS AND ACCESSORIES':
                d['accessories'].append(s)
            elif sec == 'DESIGN NOTES':
                mj = re.search(r'Jewelry Color-\s*(.*)$', s, re.I)
                if mj:
                    d['jewelry_color'] = mj.group(1).strip()
        out[n['room']] = d
    return out


def handle_lines(lines):
    """Sidebar HANDLES/KNOBS lines -> [{text, part, qty, vendor_hint}]. Part numbers are taken as written; nothing is looked up."""
    out = []
    for s in lines:
        qty = None
        m = re.search(r'Qty-\s*([\d.]+)', s)
        if m:
            qty = float(m.group(1))
        part = ''
        m = re.search(r'(\d{3}\.\d{2,3}\.\d{3}[\w.-]*)', s) or re.search(r'\b([A-Za-z]{1,3}\d{4,}[\w-]*)\b', s)
        if m:
            part = m.group(1).strip()
        if qty is None and not part:
            out.append({'text': s, 'part': '', 'qty': None, 'vendor': '', 'flags': ['note line, not a handle: %r' % s], 'note': True})
            continue
        vendor = ''
        for v in ('amerock', 'hafele', 'häfele', 'richelieu', 'richeluio', 'richleui', 'rev-a-shelf', 'top knobs', 'berenson', 'emtek'):
            if v in s.lower():
                vendor = v.upper().replace('RICHELUIO', 'RICHELIEU').replace('RICHLEUI', 'RICHELIEU')
        if not vendor and re.match(r'^\d{3}\.\d{2}\.\d{3}', part):
            vendor = 'HAFELE? (number pattern 000.00.000, verify)'
        out.append({'text': s, 'part': part, 'qty': qty, 'vendor': vendor, 'flags': []})
    merged = []
    for h in out:
        if merged and not merged[-1]['part'] and h['part'] and h['qty'] is None:
            m0 = merged[-1]
            m0['part'] = h['part']; m0['vendor'] = h['vendor'] or m0['vendor']; m0['text'] += ' / ' + h['text']
            m0['flags'].append('part number taken from the next sidebar line, as written (check the spelling)')
            continue
        merged.append(h)
    for h in merged:
        if h.get('note'):
            continue
        if 'enter pn' in h['text'].lower() and not h['part']:
            h['flags'].append('"Enter PN": the designer never typed the part number')
    return merged


# --------------------------------------------------------------------------- price lines (engine TSV or workbook paste)
def read_price_tsv(path):
    lines = []
    for ln in open(path, encoding='utf-8', errors='replace'):
        p = ln.rstrip('\n').split('\t')
        if len(p) < 6 or p[0] == 'price' or not re.match(r'^-?[\d.]+$', p[0]):
            continue
        lines.append({'price': float(p[0]), 'unit': int(p[1]), 'qty': int(float(p[2])), 'part': p[3], 'dim1': p[4], 'dim2': p[5],
                      'src': os.path.basename(path), 'key': 'seq'})
    return lines


def read_paste(path):
    """The workbook's Data Entry paste: K price, L unit (KCD id), M part, N size 1, P size 2."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb['Data Entry']
    out = []
    for row in ws.iter_rows(min_row=2, min_col=11, max_col=16, values_only=True):
        price, unit, part, n, o, p = row
        if unit is None or part is None:
            continue
        out.append({'price': float(price or 0), 'unit': int(unit), 'qty': 1, 'part': str(part), 'dim1': '' if n is None else str(n),
                    'dim2': '' if p is None else str(p), 'src': os.path.basename(path), 'key': 'id'})
    return out


FACE_RE = re.compile(r'^(Framed Door|Lift-Up Door|Door|DrFrt|Add to DrFrt)\b[- ]?(.*)$', re.I)


def faces_from_lines(lines):
    """Door / drawer-front price lines -> faces. Door lines print W then H; 'Add to DrFrt' prints H then W (2026 scripts);
    'DrFrt' (older/2nd material) prints W (and H when there)."""
    faces = []
    for l in lines:
        m = FACE_RE.match(l['part'])
        if not m:
            continue
        kind = m.group(1).lower()
        d1, d2 = parse_frac(l['dim1']), parse_frac(l['dim2'])
        if kind.startswith('add to drfrt'):
            w, h, fk = d2, d1, 'drawer front'
        elif kind.startswith('drfrt'):
            w, h, fk = d1, d2, 'drawer front'
        else:
            w, h, fk = d1, d2, 'door' if kind == 'door' else kind
        faces.append({'unit': l['unit'], 'u': l.get('u'), 'kind': fk, 'w': w, 'h': h, 'qty': l['qty'], 'style_text': m.group(2).strip(' -'),
                      'line': l['part'], 'src': l['src'], 'price': l['price']})
    return faces


# --------------------------------------------------------------------------- the sheet
def build_sheet(job, cat, price_lines, room_filter=None):
    sb = sidebar_blocks(job)
    rooms = {}
    units_by_seq = {u.seq: u for u in job.units}
    units_by_id = {u.id: u for u in job.units}
    for k in range(1, len(job.rooms) + 1):
        if room_filter and k != room_filter:
            continue
        side = sb.get(k, {})
        R = {'room': k, 'kcd_room_name': job.room_name(k), 'sidebar_room': side.get('room_details', ''),
             'door_style': side.get('style', ''), 'door_color': side.get('style_color', ''), 'door_finish': side.get('style_finish', ''),
             'material': side.get('material', ''), 'edge': side.get('edge', ''), 'drawer_box': side.get('drawer_box', ''),
             'base': side.get('base', ''), 'crown': side.get('crown', ''), 'rods_sidebar': side.get('rods', ''),
             'jewelry_color': side.get('jewelry_color', ''), 'handles_sidebar': handle_lines(side.get('handles', [])),
             'accessories_sidebar': side.get('accessories', []), 'hinge_line': side.get('hinge', ''),
             'room_defaults': (job.room_defaults[k - 1] if k - 1 < len(job.room_defaults) else []),
             'handle_slots': [a for a, b in ([(a, b) for a, b, _ in job.handles[k]] if k < len(job.handles) else []) if a],
             'faces': [], 'jewelry': [], 'hardware': [], 'rods': [], 'flags': []}
        form, why = classify_style(R['door_style'])
        R['form'] = form
        R['form_reason'] = why
        if form == 'DOORMARK':
            key = re.sub(r'\s+', ' ', R['door_style'].upper().replace(' TH', '').replace('THERMO', '')).strip()
            key = re.sub(r'\bSHAKER\b.*$', 'SHAKER', key)
            R['doormark_design_code'] = DOORMARK_DESIGNS.get(key, 'ASK (%r not in the workbook design table)' % key)
            ckey = R['door_color'].upper().strip()
            R['doormark_color_code'] = DOORMARK_COLORS.get(ckey, 'ASK (%r not in the workbook colour table)' % ckey)
        units = [u for u in job.units if u.room == k]
        # -- which price lines belong to this room's units
        lines_here = []
        for l in price_lines:
            u = units_by_seq.get(l['unit']) if l['key'] == 'seq' else units_by_id.get(l['unit'])
            if u is not None and u.room == k:
                l = dict(l); l['u'] = u; lines_here.append(l)
        engine_faces = faces_from_lines(lines_here)
        # -- (a) doors and drawer fronts
        for u in units:
            if accessory_kind(u) is not None:
                continue
            sui = u.set_unit_info
            utype = sui[1] if len(sui) > 1 else ''
            ufin = sui[13] if len(sui) > 13 else ''
            uins = sui[14] if len(sui) > 14 else ''
            uform, uwhy = classify_style(utype) if utype else (form, why)
            unit_faces = []
            src = ''
            ef = [f for f in engine_faces if f.get('u') is u]
            has_lines = any(l['u'] is u for l in lines_here)
            if not ef and has_lines:
                continue       # the price review lists this unit without a door or drawer-front line: no faces
            if ef:
                src = ef[0]['src']
                for f in ef:
                    unit_faces.append({'kind': f['kind'], 'w': f['w'], 'h': f['h'], 'qty': f['qty'], 'pair': None, 'line': f['line'],
                                       'style_text': f['style_text'], 'src': src})
            else:
                full = cat.full(u.cab) if cat else None
                if full:
                    try:
                        uf = kcdcab.UnitFaces(full, u, job, cat)
                    except Exception as e:
                        uf = None
                        R['flags'].append('unit %d (id %d, %s): face geometry failed: %s' % (u.seq, u.id, u.cab, e))
                    if uf:
                        src = 'cab geometry (%s)' % u.cab
                        for f in uf.faces:
                            if f['kind'] == 'open':
                                continue
                            if f['kind'] == 'door' and f['pair']:
                                unit_faces.append({'kind': 'door', 'w': r16(f['each_w']), 'h': r16(f['h']), 'qty': 2, 'pair': True,
                                                   'face_w': r16(f['w']), 'line': 'D%d pair' % f['n'], 'style_text': utype, 'src': src})
                            else:
                                unit_faces.append({'kind': 'door' if f['kind'] == 'door' else 'drawer front', 'w': r16(f['w']), 'h': r16(f['h']),
                                                   'qty': 1, 'pair': False, 'line': 'D%d' % f['n'], 'style_text': utype, 'src': src})
                        for fl in uf.flags:
                            if 'unknown names' not in fl:
                                R['flags'].append(fl)
                elif cat and u.T in (100, 200, 300, 320, 615, 670):
                    R['flags'].append('unit %d (id %d): %s not in the library bundle, faces unknown' % (u.seq, u.id, u.cab))
            if ef and cat and cat.full(u.cab):
                try:
                    uf2 = kcdcab.UnitFaces(cat.full(u.cab), u, job, cat)
                    for f2 in uf2.faces:
                        if f2['kind'] == 'open':
                            continue
                        w2 = r16(f2['each_w'] if (f2['kind'] == 'door' and f2['pair']) else f2['w']); h2 = r16(f2['h'])
                        if not any(abs((x['w'] or 0) - w2) < 0.07 and abs((x['h'] or 0) - h2) < 0.07 for x in unit_faces):
                            R['flags'].append('unit %d (id %d, %s): the .cab also draws a %s face D%d %s x %s that the price lines do not have (hamper front? vanity opening?) - verify' % (
                                u.seq, u.id, u.cab, f2['kind'], f2['n'], frac(w2), frac(h2)))
                except Exception:
                    pass
            if not unit_faces:
                continue
            fflags = []
            unw = (u.unw or '').lower()
            if 'shelves' in unw.rsplit('\\', 1)[-1] and 'drawer' not in unw and 'door' not in unw:
                fflags.append('VERIFY: unit placed from the open-shelving preset %r; doors unlikely' % u.unw.rsplit('\\', 1)[-1])
            if 'hamper' in unw:
                fflags.append('VERIFY: unit placed from a hamper preset %r; doors above a tilt-out hamper?' % u.unw.rsplit('\\', 1)[-1])
            if src.startswith('cab geometry'):
                fflags.append('VERIFY: from the .cab geometry; the designer\'s "no door" choice is not in the file (notes 7)')
            if form == 'NONE' and unit_faces:
                fflags.append('VERIFY: sidebar says No Door/Drawer Faces but faces were found')
            if utype and R['door_style'] and classify_style(utype)[0] != form and uform != 'ASK':
                fflags.append('unit door type %r differs from sidebar style %r' % (utype, R['door_style']))
            for f in unit_faces:
                entry = {'unit_seq': u.seq, 'unit_id': u.id, 'unit_name': u.kcd_name, 'cab': u.cab, 'wall': u.wall, 'kind': f['kind'],
                         'qty': f['qty'], 'width': f['w'], 'height': f['h'], 'width_txt': frac(f['w']), 'height_txt': frac(f['h']),
                         'pair': f['pair'], 'unit_door_type': utype, 'unit_finish': ufin, 'unit_insert': uins,
                         'style_sidebar': R['door_style'], 'color_sidebar': R['door_color'], 'form': uform if utype else form,
                         'source': f['src'], 'source_line': f['line'], 'flags': list(fflags)}
                if f.get('pair'):
                    entry['pair_gap_guess_each'] = frac(r16((f['face_w'] - 0.125) / 2.0))
                    entry['flags'].append('pair: KCD prints half the face (%s); true door with the 1/8 pair gap = %s (GUESS, WERNER only)' % (
                        frac(f['w']), entry['pair_gap_guess_each']))
                if f['w'] is not None and f['w'] < 9.5 and f['kind'] == 'door':
                    entry['flags'].append('door narrower than the CF5 minimum 9 1/2: not a real door?')
                if f['h'] is not None and f['kind'] == 'drawer front' and f['h'] < 7.5:
                    entry['flags'].append('drawer front under the CF5 minimum 7 1/2')
                R['faces'].append(entry)
        # -- order form rows: certain faces grouped by form / kind / size
        rows = {}
        for f in R['faces']:
            if any(('VERIFY' in x) or ('not a real door' in x) for x in f['flags']):
                continue
            if f['form'] in ('IN HOUSE', 'NONE'):
                continue
            key = (f['form'], f['kind'], f['width'], f['height'])
            rows[key] = rows.get(key, 0) + f['qty']
        R['form_rows'] = []
        for (fm, kind, w, h), q in sorted(rows.items(), key=lambda x: (x[0][0], x[0][1], -(x[0][2] or 0))):
            row = {'form': fm, 'kind': kind, 'qty': q, 'kcd_width': frac(w), 'kcd_height': frac(h), 'kcd_width_dec': dec(w), 'kcd_height_dec': dec(h)}
            if fm == 'DOORMARK':
                row['doormark_width_werner_rule'] = dec(r16(w - 0.0625)) if w else ''
                row['doormark_height_werner_rule'] = dec(h) if h else ''
                row['note'] = 'WERNER rule (one job): width = KCD pair half-width - 1/16, height = KCD. PRIEM differed. GUESS until the owner confirms.'
            if fm == 'CF5':
                row['note'] = 'type the KCD size in the two left columns; the sheet computes butt/miter, cut and insert sizes'
            R['form_rows'].append(row)
        # -- (b) jewelry trays
        for u in units:
            nm = u.kcd_name
            if not (re.match(r'^(RM\d+\s+)?JT\b', nm, re.I) or 'jewel' in nm.lower() or 'velvet' in nm.lower() or 'jewelry' in u.cab.lower()):
                continue
            host = None
            cands = [h for h in units if h.wall == u.wall and h is not u and accessory_kind(h) is None and h.T not in (230, 500, 641, 640, 645)
                     and h.X - 0.02 <= u.X <= h.X + h.W + 0.02]
            if cands:
                host = min(cands, key=lambda h: h.W)
            J = {'unit_seq': u.seq, 'unit_id': u.id, 'name': nm, 'code': u.kcd_code(cat), 'X': frac(r16(u.X)), 'wall': u.wall,
                 'insert_vjt': vjt_insert_name(nm), 'color_vjt': R['jewelry_color'] or 'ASK (sidebar Jewelry Color- is blank)',
                 'host': None, 'flags': []}
            if R['jewelry_color'] and R['jewelry_color'].title() not in VJT_COLORS:
                J['flags'].append('jewelry colour %r is not in the VJT list %s' % (R['jewelry_color'], VJT_COLORS))
            if host:
                es = r16(host.W - host.LS - host.RS)
                box_d, rule = drawer_box_depth(host.D)
                hf = [f for f in R['faces'] if f['unit_seq'] == host.seq and f['kind'] == 'drawer front']
                J['host'] = {'unit_seq': host.seq, 'unit_id': host.id, 'name': host.kcd_name, 'cab': host.cab, 'W': frac(r16(host.W)),
                             'D': frac(r16(host.D)), 'H': frac(r16(host.H)), 'LS': frac(r16(host.LS)), 'RS': frac(r16(host.RS)),
                             'es_width': frac(es), 'drawer_fronts': ['%s x %s' % (f['width_txt'], f['height_txt']) for f in hf],
                             'drawer_box_depth_rule': box_d, 'drawer_box_rule': rule,
                             'vjt_single_width': frac(es - 2), 'vjt_dbl_top_width_formula': frac(es - 3),
                             'vjt_dbl_top_width_text': frac(es - 3.0625),
                             'vjt_depth': frac(box_d - 1.625) if box_d else 'ASK'}
                if not hf:
                    J['flags'].append('host %d has no drawer-front lines: which drawer holds the tray is unknown' % host.seq)
            else:
                J['flags'].append('no drawer unit found under this tray on wall %d (X %s)' % (u.wall, frac(r16(u.X))))
            R['jewelry'].append(J)
        jt_hosts = {}
        for J in R['jewelry']:
            if J['host']:
                jt_hosts.setdefault(J['host']['unit_seq'], []).append(J)
        for hs, js in jt_hosts.items():
            if len(js) >= 2:
                for J in js:
                    J['layout_guess'] = '2 = DBL VJT (two trays on unit %d; which is top/bottom: see the wall notes)' % hs
            else:
                js[0]['layout_guess'] = 'ASK (one tray: 1 = BOT TRAY ONLY or 3 = TOP TRAY ONLY)'
        # -- (c) hardware and accessories for the PO
        def doubtful(f):
            return any(('VERIFY' in x) or ('not a real door' in x) for x in f['flags'])
        doors = sum(f['qty'] for f in R['faces'] if f['kind'] == 'door' and not doubtful(f))
        drawers = sum(f['qty'] for f in R['faces'] if f['kind'] == 'drawer front' and not doubtful(f))
        R['face_counts'] = {'doors': doors, 'drawer_fronts': drawers,
                            'doubtful_doors': sum(f['qty'] for f in R['faces'] if f['kind'] == 'door' and doubtful(f)),
                            'doubtful_drawer_fronts': sum(f['qty'] for f in R['faces'] if f['kind'] == 'drawer front' and doubtful(f))}
        for h in R['handles_sidebar']:
            if h.get('note'):
                R['flags'].append('sidebar HANDLES/KNOBS note: %r' % h['text'])
                continue
            R['hardware'].append({'kind': 'handle', 'name': h['text'], 'part': h['part'], 'qty_sidebar': h['qty'],
                                  'qty_from_faces': {'DOOR': doors, 'DRAWER': drawers} if (doors or drawers) else 'no faces found',
                                  'vendor': h['vendor'] or 'ASK', 'po': 'yes (PO item DOOR / DRAWER)',
                                  'flags': h['flags'] + ([] if h['part'] else ['no part number on the sidebar line'])})
        for u in units:
            ak = accessory_kind(u)
            if ak is None:
                continue
            code = u.kcd_code(cat).strip()
            pn = ''
            m = re.search(r'\(([\d.]+)\)', code)
            if m:
                pn = m.group(1)
            elif re.match(r'^\d{3}\.\d{2}\.\d{3}', code):
                pn = code
            if re.match(r'^(RM\d+\s+)?JT\b', u.kcd_name, re.I) or 'jewel' in u.kcd_name.lower():
                ak = 'vjt'
            entry = {'kind': ak, 'unit_seq': u.seq, 'unit_id': u.id, 'name': u.kcd_name, 'code': code, 'part': pn, 'qty': u.qty,
                     'wall': u.wall, 'X': frac(r16(u.X)), 'po': {'po': 'yes', 'stock': 'no (stock item)', 'site': 'no (site item)',
                                                                 'ask': 'ASK (no part number in the job)',
                                                                 'work': 'no (shop work, priced as labour)',
                                                                 'vjt': 'no: goes on the VJT order form (section b)'}[ak], 'flags': []}
            if ak == 'site':
                continue
            if pn:
                for s in R['accessories_sidebar']:
                    if u.kcd_name.lower()[:12] in s.lower():
                        m2 = re.search(r'(\d{3}\.\d{2}\.\d{3})', s)
                        if m2 and m2.group(1) != pn:
                            entry['flags'].append('sidebar says %s, the unit code says %s' % (m2.group(1), pn))
            R['hardware'].append(entry)
        for u in units:
            for o in u.options:
                nm = job.option_name(o)
                if any(w in nm.lower() for w in ('led', 'light', 'cleat', 'stiffener', 'lock', 'hinge')):
                    R['hardware'].append({'kind': 'option', 'unit_seq': u.seq, 'unit_id': u.id, 'name': nm, 'code': 'option %d' % o,
                                          'part': '', 'qty': 1, 'po': 'ASK (option: part number not in the job)', 'flags': []})
        # -- rods (stock, information only)
        for u in units:
            for h in u.rods:
                R['rods'].append({'unit_seq': u.seq, 'unit_id': u.id, 'name': u.kcd_name, 'height': frac(r16(h)),
                                  'length': frac(r16(u.W - u.LS - u.RS - 0.25)), 'type': (u.set_unit_info[3] if len(u.set_unit_info) > 3 else '')})
        R['rod_count'] = len(R['rods'])
        m = re.search(r'Qty-\s*([\d.]+)', R['rods_sidebar'] or '')
        if m and int(float(m.group(1))) != R['rod_count']:
            R['flags'].append('rods: sidebar Qty %s, units hold %d rod heights (information: rods are stock)' % (m.group(1), R['rod_count']))
        rooms[k] = R
    return rooms


# --------------------------------------------------------------------------- printing
def print_sheet(job, rooms, out=sys.stdout):
    P = lambda *a: print(*a, file=out)
    P('SPECIAL ORDER SHEET  %s   heading=%s' % (job.name, job.heading))
    for k, R in rooms.items():
        P('')
        P('=' * 110)
        P('ROOM %d  KCD name %r  sidebar %r' % (k, R['kcd_room_name'], R['sidebar_room']))
        P('  material %-30s edge %-28s drawer box %s' % (R['material'], R['edge'], R['drawer_box']))
        P('  DOOR/DRAWER STYLE %r  colour %r  finish %r' % (R['door_style'], R['door_color'], R['door_finish']))
        P('  -> form: %s  (%s)' % (R['form'], R['form_reason']))
        if R['form'] == 'DOORMARK':
            P('     Doormark design code %s   colour code %s' % (R.get('doormark_design_code'), R.get('doormark_color_code')))
        rd = R['room_defaults']
        if rd:
            P('  room defaults: door type %r  finishing %r  insert %r  handles %r' % (rd[1], rd[13], rd[14], rd[10]))
        P('  handle slots: %s' % ', '.join(sorted(set(R['handle_slots']))))
        P('')
        P('  (a) DOORS AND DRAWER FRONTS   certain: doors %d, drawer fronts %d   doubtful (VERIFY): doors %d, drawer fronts %d' % (
            R['face_counts']['doors'], R['face_counts']['drawer_fronts'], R['face_counts']['doubtful_doors'], R['face_counts']['doubtful_drawer_fronts']))
        if not R['faces']:
            P('      none')
        P('      %-4s %-3s %-26s %-12s %3s %9s %9s %-10s %-22s %s' % ('seq', 'id', 'unit', 'kind', 'qty', 'W', 'H', 'form', 'source', 'flags'))
        for f in R['faces']:
            P('      %-4d %-3d %-26s %-12s %3d %9s %9s %-10s %-22s %s' % (f['unit_seq'], f['unit_id'], f['unit_name'][:26], f['kind'], f['qty'],
                                                                     f['width_txt'], f['height_txt'], f['form'], f['source'][:22],
                                                                     '; '.join(f['flags'])))
        if R.get('form_rows'):
            P('')
            P('  ORDER FORM ROWS (certain faces only)')
            for r in R['form_rows']:
                extra = ''
                if r['form'] == 'DOORMARK':
                    extra = '  -> Doormark %s x %s (WERNER rule, GUESS)' % (r['doormark_width_werner_rule'], r['doormark_height_werner_rule'])
                P('      %-10s %-13s qty %-3d KCD %s x %s (%s x %s)%s' % (r['form'], r['kind'], r['qty'], r['kcd_width'], r['kcd_height'],
                                                                      r['kcd_width_dec'], r['kcd_height_dec'], extra))
        P('')
        P('  (b) JEWELRY TRAYS / VELVET INSERTS')
        if not R['jewelry']:
            P('      none')
        for J in R['jewelry']:
            P('      seq %d id %d %-24s insert %-24s colour %-12s layout %s' % (J['unit_seq'], J['unit_id'], J['name'], J['insert_vjt'],
                                                                                 J['color_vjt'], J.get('layout_guess', '')))
            if J['host']:
                h = J['host']
                P('         host unit %d (id %d) %s %s: W %s D %s, ES width %s, drawer fronts %s' % (h['unit_seq'], h['unit_id'], h['name'], h['cab'],
                                                                                                  h['W'], h['D'], h['es_width'], h['drawer_fronts']))
                P('         VJT form: shelf width %s, drawer depth %s (%s), single/bottom tray width %s, double top tray %s (formula -3) or %s (sheet text -3 1/16), tray depth %s' % (
                    h['es_width'], h['drawer_box_depth_rule'], h['drawer_box_rule'], h['vjt_single_width'], h['vjt_dbl_top_width_formula'],
                    h['vjt_dbl_top_width_text'], h['vjt_depth']))
            for fl in J['flags']:
                P('         FLAG ' + fl)
        P('')
        P('  (c) HARDWARE / ACCESSORIES FOR THE PURCHASE ORDER')
        if not R['hardware']:
            P('      none')
        for h in R['hardware']:
            if h['kind'] == 'handle':
                P('      handle   %-50s part %-16s sidebar qty %-5s faces %-32s vendor %-10s %s' % (h['name'][:50], h['part'], h['qty_sidebar'],
                                                                                                   h['qty_from_faces'], h['vendor'], '; '.join(h['flags'])))
            else:
                P('      %-8s seq %-3s %-34s code %-32s part %-14s qty %-2s PO: %s %s' % (h['kind'], h.get('unit_seq', ''), h['name'][:34], h['code'][:32],
                                                                                        h['part'], h['qty'], h['po'], '; '.join(h['flags'])))
        P('      rods: %d in the units (sidebar: %s) - stock, no vendor row' % (R['rod_count'], R['rods_sidebar']))
        if R['accessories_sidebar']:
            P('      sidebar accessory lines: ' + ' | '.join(R['accessories_sidebar']))
        if R['flags']:
            P('')
            P('  FLAGS')
            for fl in R['flags']:
                P('      ' + fl)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('job')
    ap.add_argument('--lib', default='/tmp/claude-0/-home-user-CFFTL-WORKING-/bef348d8-06f1-5cee-a359-256568af5804/scratchpad/lib/cat_compact.json')
    ap.add_argument('--raw', default='/tmp/claude-0/-home-user-CFFTL-WORKING-/bef348d8-06f1-5cee-a359-256568af5804/scratchpad/lib/rawlib.json')
    ap.add_argument('--price', action='append', default=[], help='kcdprice.py TSV (unit = position among live units)')
    ap.add_argument('--paste', help='filled workbook .xlsm: Data Entry paste K..P (unit = KCD id)')
    ap.add_argument('--room', type=int)
    ap.add_argument('--json')
    ap.add_argument('--txt')
    a = ap.parse_args()
    cat = None
    if a.lib and os.path.exists(a.lib):
        cat = kcdunits.Catalog.from_json(a.lib)
        if a.raw and os.path.exists(a.raw):
            cat.load_rawlib_json(a.raw)
    job = kcdunits.read_job(a.job, cat)
    lines = []
    for p in a.price:
        lines += read_price_tsv(p)
    if a.paste:
        lines += read_paste(a.paste)
    rooms = build_sheet(job, cat, lines, a.room)
    if a.json:
        json.dump({'job': job.name, 'heading': job.heading, 'rooms': list(rooms.values())}, open(a.json, 'w'), indent=1, default=str)
    if a.txt:
        with open(a.txt, 'w') as f:
            print_sheet(job, rooms, f)
    print_sheet(job, rooms)


if __name__ == '__main__':
    main()
