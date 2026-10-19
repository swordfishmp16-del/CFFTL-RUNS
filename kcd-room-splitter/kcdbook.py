"""kcdbook.py - fill the engineering pricing workbook (the `mike_p_for_services` template family) from a price
run, WITHOUT re-saving the workbook.

The template .xltm (or a filled .xlsm) is copied part for part. Only four parts change:
  [Content_Types].xml      the main part becomes a macro-enabled workbook instead of a template
  xl/workbook.xml          calcPr gets fullCalcOnLoad="1" so Excel recomputes every sheet when the file opens
  xl/sharedStrings.xml     the new texts are appended (count/uniqueCount updated)
  the Data Entry sheet     the answer cells (B1 date, B5 client number, B7 name, B9 room, F1 designer, F5 material,
                           ...) and the paste block from row 2: K price, L unit #, M part, N first size, O, P second size
VBA, ActiveX controls, the two external links, comments, drawings, printer settings and every other sheet stay
byte for byte (verify() proves it). Never re-save this workbook with openpyxl: it drops the links and controls.

Paste columns, as the engineers paste KCD's UNIT PRICE REVIEW (checked on the WERNER workbook): a part with two
sizes puts the first in N and the second in P (panels and shelves: depth, length; doors: width, height; backs:
width, height); a part with one size puts it in P; kicks, fillers, leg levelers and mirror backs show one size (the
width) in P although the price scripts know two. Column J (a shifted paste) and Q (an overflow of P) are read by
the Modify Here formulas; R is the engineer's own column. Nothing is written to J, Q or R.
"""
import re
import os
import sys
import json
import zipfile
import datetime
import html
import subprocess
import tempfile
import shutil

TEMPLATE_CT = 'application/vnd.ms-excel.template.macroEnabled.main+xml'
WORKBOOK_CT = 'application/vnd.ms-excel.sheet.macroEnabled.main+xml'
ONE_SIZE = re.compile(r'^(kick|filler|leg leveler|mirror back)\b', re.I)   # parts whose review line shows one size
NEW_ROW_STYLES = {'K': '380', 'L': '169', 'M': '169', 'N': '377', 'O': '377', 'P': '377'}   # as Excel wrote WERNER rows 43+
COL_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


def col_index(col):
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def split_ref(ref):
    m = re.match(r'^([A-Z]+)(\d+)$', ref)
    return m.group(1), int(m.group(2))


def excel_serial(d):
    return (d - datetime.date(1899, 12, 30)).days


def xml_text(s):
    s = str(s)
    esc = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if s != s.strip() or '  ' in s:
        return '<t xml:space="preserve">%s</t>' % esc
    return '<t>%s</t>' % esc


# ----------------------------------------------------------------------------- the package
class Package:
    def __init__(self, path):
        self.path = path
        z = zipfile.ZipFile(path)
        self.order = [i.filename for i in z.infolist()]
        self.compress = {i.filename: i.compress_type for i in z.infolist()}
        self.parts = {n: z.read(n) for n in self.order}
        z.close()

    def text(self, name):
        return self.parts[name].decode('utf-8')

    def set_text(self, name, text):
        self.parts[name] = text.encode('utf-8')

    def sheet_part(self, sheet_name):
        wb = self.text('xl/workbook.xml')
        m = re.search(r'<sheet [^>]*name="%s"[^>]*r:id="([^"]+)"' % re.escape(html.escape(sheet_name, quote=True)), wb)
        if not m:
            raise KeyError('no sheet named %r' % sheet_name)
        rels = self.text('xl/_rels/workbook.xml.rels')
        for rel in re.findall(r'<Relationship [^>]*/>', rels):
            if 'Id="%s"' % m.group(1) in rel:
                target = re.search(r'Target="([^"]+)"', rel).group(1)
                return 'xl/' + target.lstrip('/').replace('xl/', '', 1) if not target.startswith('/xl/') else target.lstrip('/')
        raise KeyError('sheet %r has no relationship' % sheet_name)

    def write(self, out_path):
        with zipfile.ZipFile(out_path, 'w') as z:
            for n in self.order:
                z.writestr(zipfile.ZipInfo(n, date_time=(1980, 1, 1, 0, 0, 0)), self.parts[n], compress_type=self.compress.get(n, zipfile.ZIP_DEFLATED))


# ----------------------------------------------------------------------------- shared strings
class SharedStrings:
    def __init__(self, pkg):
        self.pkg = pkg
        self.xml = pkg.text('xl/sharedStrings.xml')
        head = re.match(r'(.*?<sst[^>]*>)', self.xml, re.S).group(1)
        self.head = head
        self.items = re.findall(r'<si>.*?</si>', self.xml, re.S)
        self.tail = self.xml[self.xml.rfind('</sst>'):]
        self.plain = {}
        for i, it in enumerate(self.items):
            m = re.fullmatch(r'<si><t(?: xml:space="preserve")?>([^<]*)</t></si>', it, re.S)
            if m:
                self.plain.setdefault(html.unescape(m.group(1)), i)
        self.added = 0
        self.refs_added = 0

    def index(self, text):
        self.refs_added += 1
        if text in self.plain:
            return self.plain[text]
        self.items.append('<si>%s</si>' % xml_text(text))
        self.plain[text] = len(self.items) - 1
        self.added += 1
        return len(self.items) - 1

    def save(self):
        count = int(re.search(r'count="(\d+)"', self.head).group(1)) + self.refs_added
        head = re.sub(r'count="\d+"', 'count="%d"' % count, self.head, count=1)
        head = re.sub(r'uniqueCount="\d+"', 'uniqueCount="%d"' % len(self.items), head, count=1)
        self.pkg.set_text('xl/sharedStrings.xml', head + ''.join(self.items) + self.tail)


# ----------------------------------------------------------------------------- the sheet
class Sheet:
    """The cells of one worksheet part, edited in place; everything outside <sheetData> is kept verbatim."""

    def __init__(self, pkg, part):
        self.pkg, self.part = pkg, part
        self.xml = pkg.text(part)
        m = re.search(r'<sheetData>(.*?)</sheetData>|<sheetData/>', self.xml, re.S)
        if not m:
            raise ValueError('no sheetData in %s' % part)
        self.pre, self.post = self.xml[:m.start()], self.xml[m.end():]
        body = m.group(1) or ''
        self.rows = {}                                   # row number -> {'attrs': str, 'cells': {col: (attrs, body)}}
        for rm in re.finditer(r'<row r="(\d+)"([^>]*?)(?:/>|>(.*?)</row>)', body, re.S):
            r = int(rm.group(1)); cells = {}
            for cm in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', rm.group(3) or '', re.S):
                cells[cm.group(1)] = (cm.group(2) or '', cm.group(3) or '')
            self.rows[r] = {'attrs': rm.group(2) or '', 'cells': cells}
        self.formulas_before = len(re.findall(r'<f[ >/]', body))
        self.written = []

    def style_for(self, col, row):
        """The style of the cell itself, else the nearest cell above in the same column, else the column default."""
        if row in self.rows and col in self.rows[row]['cells']:
            m = re.search(r's="(\d+)"', self.rows[row]['cells'][col][0])
            if m:
                return m.group(1)
        return NEW_ROW_STYLES.get(col)

    def set(self, ref, value, sst):
        col, row = split_ref(ref)
        cur = self.rows.get(row, {}).get('cells', {}).get(col)
        if cur and '<f' in cur[1]:
            raise ValueError('%s holds a formula; refusing to overwrite it' % ref)
        style = self.style_for(col, row)
        attrs = ' s="%s"' % style if style else ''
        if value is None or value == '':
            return
        if isinstance(value, bool):
            xml = '<c r="%s"%s t="b"><v>%d</v></c>' % (ref, attrs, 1 if value else 0)
        elif isinstance(value, datetime.date):
            xml = '<c r="%s"%s><v>%d</v></c>' % (ref, attrs, excel_serial(value))
        elif isinstance(value, (int, float)):
            v = ('%d' % value) if float(value).is_integer() else repr(float(value))
            xml = '<c r="%s"%s><v>%s</v></c>' % (ref, attrs, v)
        else:
            xml = '<c r="%s"%s t="s"><v>%d</v></c>' % (ref, attrs, sst.index(str(value)))
        self.rows.setdefault(row, {'attrs': ' spans="11:16"', 'cells': {}})
        self.rows[row]['cells'][col] = ('__new__', xml)
        self.written.append((ref, value))

    def save(self):
        out = []
        for r in sorted(self.rows):
            cells = self.rows[r]['cells']
            parts = []
            for col in sorted(cells, key=col_index):
                attrs, body = cells[col]
                if attrs == '__new__':
                    parts.append(body)
                elif body:
                    parts.append('<c r="%s%d"%s>%s</c>' % (col, r, attrs, body))
                else:
                    parts.append('<c r="%s%d"%s/>' % (col, r, attrs))
            out.append('<row r="%d"%s>%s</row>' % (r, self.rows[r]['attrs'], ''.join(parts)) if parts else '<row r="%d"%s/>' % (r, self.rows[r]['attrs']))
        body = ''.join(out)
        maxrow = max(self.rows) if self.rows else 1
        pre = re.sub(r'<dimension ref="([A-Z]+)1:([A-Z]+)\d+"/>', lambda m: '<dimension ref="%s1:%s%d"/>' % (m.group(1), m.group(2), maxrow), self.pre, count=1)
        formulas_after = len(re.findall(r'<f[ >/]', body))
        if formulas_after != self.formulas_before:
            raise RuntimeError('formula count changed %d -> %d' % (self.formulas_before, formulas_after))
        self.pkg.set_text(self.part, pre + '<sheetData>' + body + '</sheetData>' + self.post)


# ----------------------------------------------------------------------------- price lines
def read_price_lines(path):
    """The TSV kcdprice.py prints: price, unit, qty, part, dim1, dim2, order, script. Stops at the FLAGS block."""
    lines, flags = [], []
    for ln in open(path, encoding='utf-8', errors='replace'):
        ln = ln.rstrip('\n')
        if ln.startswith('price\t') or not ln.strip():
            continue
        if ln.startswith('FLAGS') or ln.startswith('  '):
            flags.append(ln.strip()); continue
        f = ln.split('\t') + [''] * 8
        try:
            lines.append({'price': float(f[0]), 'unit': int(f[1]), 'qty': int(f[2] or 1), 'part': f[3], 'dim1': f[4], 'dim2': f[5], 'order': f[6], 'script': f[7]})
        except ValueError:
            flags.append('unreadable line: ' + ln)
    return lines, flags


def paste_rows(lines, drop=None):
    """Turn engine lines into paste rows (K price, L unit, M part, N, O, P); a dropped line is listed with its reason."""
    rows, dropped = [], []
    for l in lines:
        if drop and drop[0].search(l['part']):
            dropped.append((l, drop[1])); continue
        d1, d2 = l['dim1'].strip(), l['dim2'].strip()
        if d1 and d2 and not ONE_SIZE.search(l['part']):
            n, p = d1, d2
        elif d1 and d2:
            n, p = '', d1
        elif d1 or d2:
            n, p = '', (d1 or d2)
        else:
            n, p = '', ''
        price = l['price']
        price = int(price) if float(price).is_integer() else round(price, 2)
        for _ in range(max(1, l['qty'])):
            rows.append({'K': price, 'L': l['unit'], 'M': l['part'], 'N': n, 'O': '', 'P': p})
    return rows, dropped


# ----------------------------------------------------------------------------- fill and verify
def fill(template, out_path, entries, rows, sheet_name='Data Entry', first_row=2):
    pkg = Package(template)
    ct = pkg.text('[Content_Types].xml')
    if TEMPLATE_CT in ct:
        pkg.set_text('[Content_Types].xml', ct.replace(TEMPLATE_CT, WORKBOOK_CT, 1))
    wb = pkg.text('xl/workbook.xml')
    if 'fullCalcOnLoad' not in wb:
        wb = re.sub(r'<calcPr ', '<calcPr fullCalcOnLoad="1" ', wb, count=1)
        pkg.set_text('xl/workbook.xml', wb)
    sst = SharedStrings(pkg)
    sh = Sheet(pkg, pkg.sheet_part(sheet_name))
    for ref, val in entries.items():
        sh.set(ref, val, sst)
    for i, row in enumerate(rows):
        r = first_row + i
        for col in 'KLMNOP':
            if row.get(col) not in (None, ''):
                sh.set('%s%d' % (col, r), row[col], sst)
    sh.save(); sst.save()
    if os.path.abspath(out_path) == os.path.abspath(template):
        raise ValueError('refusing to overwrite the template')
    pkg.write(out_path)
    return {'cells': sh.written, 'rows': len(rows), 'strings_added': sst.added, 'sheet_part': sh.part}


def verify(template, out_path, sheet_part):
    """Every part byte-identical to the template except the four edited ones; the edited XML well-formed; the
    workbook loadable. Returns a list of findings (empty = clean)."""
    import xml.dom.minidom
    a, b = Package(template), Package(out_path)
    findings = []
    if a.order != b.order:
        findings.append('part order differs')
    allowed = {'[Content_Types].xml', 'xl/workbook.xml', 'xl/sharedStrings.xml', sheet_part}
    for n in a.order:
        if a.parts[n] != b.parts.get(n) and n not in allowed:
            findings.append('part changed: ' + n)
    for n in allowed:
        try:
            xml.dom.minidom.parseString(b.parts[n])
        except Exception as e:
            findings.append('%s not well-formed: %s' % (n, e))
    try:
        import openpyxl
        wbk = openpyxl.load_workbook(out_path, read_only=True, keep_vba=True)
        wbk.close()
    except Exception as e:
        findings.append('openpyxl could not open the result: %s' % e)
    return findings


def preview(out_path, sheet='Final Price Sheet', rows=80):
    """What Excel will compute, approximately: LibreOffice converts a COPY to .xlsx (formulas recalculated,
    the two external links unresolved, no VBA) and the sheet's non-empty cells are returned as text lines."""
    tmp = tempfile.mkdtemp(prefix='kcdbook_')
    try:
        src = os.path.join(tmp, 'copy.xlsm'); shutil.copy(out_path, src)
        r = subprocess.run(['soffice', '--headless', '--convert-to', 'xlsx', '--outdir', tmp, src], capture_output=True, text=True, timeout=180)
        conv = os.path.join(tmp, 'copy.xlsx')
        if not os.path.exists(conv):
            return ['(LibreOffice could not convert the workbook: %s)' % (r.stderr or r.stdout).strip()[:300]]
        import openpyxl
        wbk = openpyxl.load_workbook(conv, data_only=True, read_only=True)
        if sheet not in wbk.sheetnames:
            return ['(no sheet %r; sheets: %s)' % (sheet, wbk.sheetnames)]
        ws = wbk[sheet]; out = []
        for row in ws.iter_rows(min_row=1, max_row=rows):
            vals = [(c.coordinate, c.value) for c in row if c.value not in (None, '')]
            if vals:
                out.append('  '.join('%s=%s' % (k, v) for k, v in vals))
        wbk.close()
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def parse_entry_value(text):
    t = text.strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', t):
        y, m, d = map(int, t.split('-')); return datetime.date(y, m, d)
    if re.fullmatch(r'-?\d+', t):
        return int(t)
    if re.fullmatch(r'-?\d+\.\d+', t):
        return float(t)
    return t


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='Fill the engineering pricing workbook from a kcdprice run without re-saving it.')
    ap.add_argument('template'); ap.add_argument('out')
    ap.add_argument('--lines', help='kcdprice.py output (TSV)')
    ap.add_argument('--drop', action='append', default=[], metavar='REGEX=REASON', help='leave out price lines whose part matches REGEX')
    ap.add_argument('--entry', action='append', default=[], metavar='CELL=VALUE', help='Data Entry answer, e.g. B5=1091400, B1=2026-10-24, F5="Designer White Grain"')
    ap.add_argument('--entries', help='JSON file {cell: value}')
    ap.add_argument('--report', help='write the plain-English report here')
    ap.add_argument('--preview', action='store_true', help='show the Final Price Sheet as LibreOffice computes it')
    a = ap.parse_args(argv)
    entries = {}
    if a.entries:
        for k, v in json.load(open(a.entries)).items():
            entries[k] = parse_entry_value(v) if isinstance(v, str) else v
    for s in a.entry:
        k, v = s.split('=', 1); entries[k.strip()] = parse_entry_value(v)
    rows, dropped, flags = [], [], []
    if a.lines:
        lines, flags = read_price_lines(a.lines)
        drop = None
        if a.drop:
            rx, _, why = a.drop[0].partition('=')
            drop = (re.compile(rx, re.I), why or 'dropped')
        rows, dropped = paste_rows(lines, drop)
    rep = fill(a.template, a.out, entries, rows)
    findings = verify(a.template, a.out, rep['sheet_part'])
    out = ['Workbook %s from %s' % (os.path.basename(a.out), os.path.basename(a.template)), '']
    out += ['Data Entry answers written:'] + ['  %s = %s' % (k, v) for k, v in entries.items() if v not in (None, '')]
    out += ['', 'Price lines pasted in K..P from row 2: %d (%d new texts in the string table)' % (rep['rows'], rep['strings_added'])]
    tot = sum(r['K'] for r in rows if isinstance(r['K'], (int, float)))
    out += ['  the pasted prices add up to %.2f' % tot]
    if dropped:
        out += ['', 'Price lines left out (%d):' % len(dropped)] + ['  %s unit %d %s %s %s: %s' % (l['price'], l['unit'], l['part'], l['dim1'], l['dim2'], why) for l, why in dropped]
    if flags:
        out += ['', 'Engine flags:'] + ['  ' + f for f in flags]
    out += ['', 'Check of the file: ' + ('every other part is byte for byte the template, the edited XML parses, the workbook opens' if not findings else '; '.join(findings))]
    if a.preview:
        out += ['', 'Final Price Sheet as LibreOffice computes it (no macros, external links unresolved):'] + ['  ' + s for s in preview(a.out)]
    text = '\n'.join(out)
    print(text)
    if a.report:
        open(a.report, 'w', encoding='utf-8').write(text + '\n')
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
