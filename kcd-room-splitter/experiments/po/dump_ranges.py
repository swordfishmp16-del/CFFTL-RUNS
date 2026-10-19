import sys, openpyxl
base = '/tmp/claude-0/-home-user-CFFTL-WORKING-/bef348d8-06f1-5cee-a359-256568af5804/scratchpad/'
src = sys.argv[1]
f = base + ('wb/template.xltm' if src == 'template' else 'walls/jobs/1089471 WERNER OFFICE.xlsm')
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
