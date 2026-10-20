"""Read-only dump of cell ranges: python3 dump_ranges.py template 'Tab!A1:D9' ...  (the bundled data/template.xltm, formulas)
or python3 dump_ranges.py FILLED.xlsm 'Tab!A1:D9' ... (a filled workbook, cached values). Never saves anything."""
import sys, os, openpyxl
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import kcdbook
src = sys.argv[1]
f = kcdbook.DEFAULT_TEMPLATE if src == 'template' else src
wb = openpyxl.load_workbook(f, data_only=(src != 'template'), keep_vba=False, read_only=True)
for spec in sys.argv[2:]:
    tab, rng = spec.split('!')
    ws = wb[tab]
    print('\n##', tab, rng)
    for row in ws[rng]:
        for c in row:
            if c.value is None or (isinstance(c.value, str) and not c.value.strip()):
                continue
            s = str(c.value).replace('\n', ' | ')
            print(f'{c.coordinate}\t{s[:200]}')
