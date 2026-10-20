"""Read-only dump of the order tabs of the engineering workbook: python3 dump_tabs.py template [TAB ...] shows the
formulas of the bundled data/template.xltm; python3 dump_tabs.py FILLED.xlsm [TAB ...] shows the cached values of a
filled workbook (give its path). Never saves anything."""
import sys, os, openpyxl
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import kcdbook
TABS = ['Final Price Sheet', 'Job Cart Cover Sheet', 'Purchase Order', 'VJT Order', 'CF5 Order',
        'CF Stone', 'CF Thermo', 'Doormark A1', 'Doormark B1', 'Ladder', 'BCCD A1', 'Holes', 'W.W. Template', 'Work Required Grid']
which = sys.argv[1]
if which == 'template':
    wb = openpyxl.load_workbook(kcdbook.DEFAULT_TEMPLATE, data_only=False, keep_vba=False, read_only=True)
else:
    wb = openpyxl.load_workbook(which, data_only=True, keep_vba=False, read_only=True)
tabs = sys.argv[2:] or TABS
for t in tabs:
    if t not in wb.sheetnames:
        print('## MISSING', t); continue
    ws = wb[t]
    print('\n##', t, 'maxrow', ws.max_row, 'maxcol', ws.max_column)
    n = 0
    for row in ws.iter_rows():
        for c in row:
            v = c.value
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            s = str(v).replace('\n', ' | ')
            if len(s) > 160: s = s[:160] + '...'
            print(f'{c.coordinate}\t{s}')
            n += 1
            if n > 900:
                print('... (truncated)'); break
        if n > 900: break
