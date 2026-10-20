#!/usr/bin/env python3
"""doormark_ref.py - turn Doormark's reference sheets into one JSON the door-form fill can use, and compare them with the
pricing workbook's own Doormark tables (Data Conversions X/Y).

Sources (from the owner, Oct 19 2026; the PDFs stay outside the repo):
  codes.txt      pdftotext of 'Doormark Door Ordering Codes 1-15-25.pdf' (QUICK REFERENCE: design type, door design,
                 ordering code, door styles, drawer styles, minimum door width, minimum drawer height)
  funder.txt     pdftotext of 'Doormark Inc - Funder Stock Colors.pdf' (colour name, code, match back, melamine match,
                 laminate; groups Matte / Textured / Woodgrain / Satin; updated 2-03-2025)
  Krono Select   'doormark-kronospan-sell-sheet-2-26.pdf' is an image: 13 finish names typed in below, NO ordering codes
usage: python3 doormark_ref.py codes.txt funder.txt [data_conversions.txt] -o doormark_ref.json
"""
import re, sys, json, argparse

KRONO_SELECT = ['Brushed Aluminum', 'Amber Urban Oak', 'Brandy Castello Oak', 'Cashmere', 'Clay Grey', 'Grey Nordic Wood',
                'Iron Surfside Ash', 'Light Select Walnut', 'Pure Surfside Ash', 'Ristretto Baroque Oak', 'Snow White',
                'Stone Beige', 'White Coastland Oak']
STYLES = {'SLB', 'SRP', 'ARP', 'CRP', 'RR', 'SPR'}      # SPR on the CAPTIVA line is the sheet's own typo for SRP
TYPES = {'SLAB', 'ROUND', 'SQUARE', 'SHAKER', 'APPLIED', 'INFINITE'}

def parse_codes(text):
    out = []
    for ln in text.splitlines():
        t = ln.split()
        if not t or t[0] not in TYPES:
            continue
        typ = t[0]
        # the minimum sizes are the last two tokens like 6.00" / N/A
        sizes = [t.pop(), t.pop()][::-1]
        # the ordering code is the first token after the design name; everything after it is a style, the code itself
        # (designs ordered in their own style: BAL, BIS, FRW, SHA ...) or N/A
        body = t[1:]
        for i in range(1, len(body)):
            cand = body[i]
            if all(x in STYLES or x == cand or x == 'N/A' for x in body[i + 1:]) and body[i + 1:]:
                name, code, styles = ' '.join(body[:i]), cand, body[i + 1:]
                break
        else:
            raise ValueError('cannot split name / code / styles: ' + ln)
        styles = [('SRP' if x == 'SPR' else x) for x in styles]
        # door styles first, then the drawer styles: 'SLB RR', 'SLB <code>', 'SLB' alone, or N/A (no drawers)
        if styles[-1] == 'N/A':
            drawers, doors = [], styles[:-1]
        elif styles[-1] in ('RR', code) and len(styles) >= 2 and styles[-2] == 'SLB':
            drawers, doors = styles[-2:], styles[:-2]
        elif styles[-1] == 'SLB':
            drawers, doors = [styles[-1]], styles[:-1]
        else:
            drawers, doors = [styles[-1]], styles[:-1]
        out.append({'type': typ, 'design': name, 'code': code, 'door_styles': doors, 'drawer_styles': drawers,
                    'min_door_width_in': None if sizes[0] == 'N/A' else float(sizes[0].rstrip('"”')),
                    'min_drawer_height_in': None if sizes[1] == 'N/A' else float(sizes[1].rstrip('"”'))})
    return out

def parse_funder(text):
    out, group = [], None
    for ln in text.splitlines():
        s = ln.strip()
        if s in ('Matte', 'Textured', 'Woodgrain', 'Satin'):
            group = s; continue
        if not group or s.startswith(('Name', '**', '(')) or not s:
            continue
        cols = re.split(r'\s{2,}', s)
        if len(cols) < 3:
            continue
        name, code = cols[0], cols[1]
        rest = cols[2:]
        mback = ''
        if rest and rest[0] in ('Yes', 'YES', 'Mix', 'White'):
            mback = rest.pop(0)
        melamine = rest.pop(0) if rest and not rest[0].startswith(('Formica', 'Wilson', 'Doormark')) else ''
        laminate = rest[0] if rest else ''
        out.append({'group': group, 'name': name, 'code': code, 'match_back': mback or 'no',
                    'melamine_match': melamine.replace(' – ', ' - '), 'laminate': laminate})
    return out

def workbook_tables(text):
    X = dict(re.findall(r"^\s*X(\d+) = '([^']*)'", text, re.M))
    Y = dict(re.findall(r"^\s*Y(\d+) = '([^']*)'", text, re.M))
    designs = {X[str(i)]: Y.get(str(i)) for i in range(3, 37) if str(i) in X}
    colours = {X[str(i)]: Y.get(str(i)) for i in range(41, 59) if str(i) in X}
    return designs, colours

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('codes'); ap.add_argument('funder'); ap.add_argument('dc', nargs='?'); ap.add_argument('-o', required=True)
    a = ap.parse_args()
    designs = parse_codes(open(a.codes, encoding='utf-8').read())
    colours = parse_funder(open(a.funder, encoding='utf-8').read())
    ref = {'source': 'Doormark quick reference 1-15-25; Doormark/Funder cross-reference 2-03-2025; Krono Select sell sheet 2-26',
           'designs': designs, 'colours': colours,
           'krono_select_finishes_no_code': KRONO_SELECT,
           'notes': ['ARP and CRP doors need 2 inches or more over the SRP minimum width, depending on the design',
                     'SLB = slab (matching door edge unless square edges are requested); SRP square / ARP arched / CRP cathedral raised panel; RR = reduced rail raised panel',
                     'all foil colours can be ordered with a white back; match back is a per-square-foot up-charge; glaze colours Black, Dark Walnut, Eggshell, Umber Brown']}
    json.dump(ref, open(a.o, 'w'), indent=1)
    print('designs %d, colours %d, krono select %d -> %s' % (len(designs), len(colours), len(KRONO_SELECT), a.o))
    if a.dc:
        wd, wc = workbook_tables(open(a.dc, encoding='utf-8').read())
        bycode = {d['code']: d for d in designs}
        print('\nworkbook designs (%d) against the quick reference (%d):' % (len(wd), len(designs)))
        for name, code in wd.items():
            d = bycode.get(code)
            print('  %-18s %-5s %s' % (name, code, ('= ' + d['design']) if d else 'NOT on the quick reference'))
        print('  quick-reference designs the workbook lacks: ' + ', '.join('%s %s' % (d['code'], d['design']) for d in designs if d['code'] not in wd.values()))
        ccode = {c['code']: c for c in colours}
        print('\nworkbook colours (%d) against the Funder sheet (%d):' % (len(wc), len(colours)))
        for name, code in wc.items():
            c = ccode.get(code)
            print('  %-16s %-5s %s' % (name, code, ('= %s (melamine %s)' % (c['name'], c['melamine_match'])) if c else 'NOT on the Funder sheet'))
        print('  Funder colours the workbook lacks: ' + ', '.join('%s %s' % (c['code'], c['name']) for c in colours if c['code'] not in wc.values()))

if __name__ == '__main__':
    main()
