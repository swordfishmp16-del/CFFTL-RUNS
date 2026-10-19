"""Read-only dump of the order tabs of the engineering workbook: formulas from the template,
cached values from the filled WERNER workbook. Never saves anything."""
import sys, openpyxl
base = '/tmp/claude-0/-home-user-CFFTL-WORKING-/bef348d8-06f1-5cee-a359-256568af5804/scratchpad/'
TABS = ['Final Price Sheet', 'Job Cart Cover Sheet', 'Purchase Order', 'VJT Order', 'CF5 Order',
        'CF Stone', 'CF Thermo', 'Doormark A1', 'Doormark B1', 'Ladder', 'BCCD A1', 'Holes', 'W.W. Template', 'Work Required Grid']
which = sys.argv[1]
if which == 'template':
    wb = openpyxl.load_workbook(base + 'wb/template.xltm', data_only=False, keep_vba=False, read_only=True)
else:
    wb = openpyxl.load_workbook(base + 'walls/jobs/1089471 WERNER OFFICE.xlsm', data_only=True, keep_vba=False, read_only=True)
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
