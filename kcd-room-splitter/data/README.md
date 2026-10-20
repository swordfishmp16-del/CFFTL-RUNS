# The data folder

These files travel with the tools so that a fresh copy of this repo can run on its own: no test laptop,
no scratch folder. `kcdunits.py` finds them next to itself (`kcdunits.DATA_DIR`), and `kcdbook.py` finds the
template the same way. Nothing here is a customer file; see the rule at the end.

## What each file is

| File | What it is | Where it came from |
|---|---|---|
| `cat_compact.json.gz` | The compact unit catalog: for each of the 1,296 `.cab` unit files in the shop's library, the size slots with their labels and defaults, the `.prt` / `.pcb` names, the unit type, the choose-file questions, the extra variables and the face list, plus `options.dat` and `Sizes.Lst`. It is what labels the 301 size slots of every unit in a `.job`. | Made on Oct 13, 2026 from the shop's KCD23 library (the test laptop's OneDrive folder `me and claude\KCD23`) by `catjson.py` on the laptop. Gzip of `cat_compact.json` (4.2 MB; md5 of the json `fe5056d0c6bf5a77bd329460c917e094`). |
| `rawlib.json.gz` | The full text of every file in that library (`.cab`, `.prt`, `.pcb`, `options.dat`, `Sizes.Lst`, `Code.dat` ...), one JSON object `{relative path: text}`. The door and drawer face geometry (`kcdcab.py`) needs it; the room sheet alone does not. | Bundled by `rawlib.py` on the laptop on Oct 13, 2026 from the same `me and claude\KCD23` folder. Gzip of `rawlib.json` (45 MB; md5 of the json `b987ec33d1902bcd80b53e3ffa20c1c6`). |
| `template.xltm` | The engineers' pricing workbook template (the `mike_p_for_services` family): Data Entry, Final Price Sheet, Purchase Order, the order forms (CF5, VJT, Doormark, CF Stone, CF Thermo, Ladder, BCCD), Data Conversions with the dropdown lists, and the macros. `kcdbook.py` copies it part for part and only writes the answer cells. | Copied on Oct 12, 2026 from the engineers' `mike_p_for_services` workbook template (784 KB, md5 `92f1e4d7b2143b8cd7beec65ba5df152`). Never re-save it with Excel or openpyxl; it is read only. |

How the tools use them:

- `kcdunits.DEFAULT_CATALOG` = `cat_compact.json.gz`, `kcdunits.DEFAULT_RAWLIB` = `rawlib.json.gz`.
  `kcdunits.default_catalog()` loads them once per run; `kcdunits.py`, `kcdcab.py`, `kcdprice.py` and
  `experiments/po/soitems.py` use them when `--lib` / `--raw` are not given. Any json reader in `kcdunits`
  takes a `.json` or a `.json.gz` file.
- `kcdbook.DEFAULT_TEMPLATE` = `template.xltm`; on the command line `-` or `default` in the template place means this file.

## What is NOT here

- **The price list.** KCD prices from the monthly script folders `C:\KCD23-STDPLIST\<date> CFFL PRICING`
  (on the laptop they are copied to `%TEMP%\kcdprice\<LIST>`). They change every month and are not bundled,
  so prices come either from a `kcdprice.py` run on the laptop with the right month's list, or from the
  engineer's KCD UNIT PRICE REVIEW printout. Without a price list the tools still read the job, label the
  sizes, find the doors and fill the workbook answers; the price lines stay empty.
- Any job, remeasure scan, workbook that was filled for a customer, or anything else with a customer's
  name in it.

## The rule

None of these files is a customer file. They are the shop's library, its workbook template and lists made
from them. Customer job files, scans, filled workbooks and read-outs never go in this folder or anywhere
else in the repo; they live on the shop's own drives.

If the shop's library changes (new units, new options), make a new `cat_compact.json` and `rawlib.json` on
a machine that has the library (`catjson.py` and `rawlib.py`, see `kcd-deep-dive-notes.md` section 12),
gzip them and replace the two files here. If the engineers change the workbook template, replace
`template.xltm` and run `kcdbook.py` once on a blank job to confirm its check still passes.
