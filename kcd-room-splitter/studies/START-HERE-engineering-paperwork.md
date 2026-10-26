# START HERE: the "engineering finished KCD paperwork" tool (new work, from Oct 26, 2026)

Owner's ask (Mike Policy, Oct 26): when an engineer is done with a KCD room file, use it to complete the pricing
workbook with every order form filled out, add the 3-way pre-production check, and hand back a solid, checked output
that is ready for production (first target: "ready for a ten-minute review"). Like KCD ROOM SPLITTER later: one app the
engineer runs on the shop PC. Build it first as a Claude skill here, prove it on ten finished jobs, then freeze it.

## Where everything is

- This repo (`CFFTL-WORKING-`, work branch `claude/admiring-albattani-zgoxjl`; `production` and the `CFFTL-RUNS` repo
  are the run-only copies, never develop there). Read `CLAUDE.md` at the root and `kcd-room-splitter/CLAUDE.md` first.
- The knowledge: `kcd-room-splitter/kcd-deep-dive-notes.md`, sections 5 (workbook), 9 (room sheet), 10-13 (pricing,
  the ten job sets, 1/16 rounding), 14 (walls), 15 (kcdbook), 16 (sidebar, forms as workbook tabs, fillers, the
  Oct 20 run chain and the policy decisions from the checks).
- The studies behind section 16 quoted customer paperwork, so they are not in git; their findings are written into
  section 16 (16.1 sidebar, 16.2 the forms as workbook tabs and the WERNER/RUBIN packets, 16.3-16.4 fillers,
  16.5 open questions and the owner's answers, 16.6 the run chain). The engineer packets themselves are on the test
  laptop (below). What is here, in `kcd-room-splitter/studies/`: `data_conversions.txt` (the workbook's dropdown
  lists, exact texts), `template_tabs_1/2.txt` (the template's tabs and typed-cell layout), `doormark/codes.txt`
  and `doormark/funder.txt` (the Doormark ordering codes and the Funder colour cross-reference; parsed form in
  `experiments/po/doormark_ref.json`).
- The tools: `kcdunits.py` (read a job into a room sheet; `default_catalog()`), `kcdcab.py` (doors and drawer fronts
  from the .cab geometry), `kcdprice.py` (the KCD price-list interpreter; needs `--pricelist` folders),
  `kcdbook.py` (fill the workbook without breaking it; `--cell` for order-tab cells), `experiments/po/sidebar.py`,
  `experiments/po/soitems.py` (the special-order sheet), `experiments/po/doormark_ref.json`, `kcdrun.py` (the
  remeasure chain; `room_workbook()` is the per-room workbook step to build on), `experiments/compare_keys.py`
  (price lines against the engineers' pastes).
- Data in the repo: `kcd-room-splitter/data/` (workbook template, library bundles). NOT in the repo: the monthly
  price list (`C:\KCD23-STDPLIST\<date> CFFL PRICING` on the shop machines; copies on the test laptop under
  `%TEMP%\kcdprice\<LIST>`; OneDrive `me and claude\KCD23\STDPLIST`).
- The test material: the ten job sets on the test laptop, `%TEMP%\kcdjobs10\<order> <NAME>\` (designer job,
  engineered room files, KCD price reviews, the filled workbooks, the ENG packet scans with the forms); reach it with
  the Desktop Commander connector (device id from `list_devices`; the laptop is read-only except our `%TEMP%`
  folders; notes section 12-13 and `kcd-room-splitter/CLAUDE.md` say how). Mike can also upload a finished room file
  and its workbook directly. Customer files never go into git.

## What is proven (do not redo)

- Reading a finished room file: sizes, materials, options, sidebar (12 engineered rooms checked).
- Pricing: 731 of 737 lines identical to KCD's review on the ten sets with the May 2026 list and 1/16 rounding.
- Filling the workbook byte-safely; Data Entry answers and the certain order-tab cells (WERNER 18 of 18 equal).
- The forms are tabs of the workbook (E_forms); the cell map used so far is in the kcdrun.py docstring.

## What is open (settle with the engineers before filling those cells)

- Door sizes on the order forms (WERNER: elevation = (face - 1/8) / 2 for pairs; PRIEM did not follow).
- Which drawn doors are sold (the 774 tall units, open shelving with .cab doors).
- VJT tray sizes (inferred: single/bottom = width - 2, double top = width - 3, depth = box depth - 1 5/8),
  the Elements form standard, the vendor list for the PO, the Doormark colour codes in the workbook (MYBL vs the
  list), slab fillers, when a stock handle goes on the PO, B15/B19/B21/B23 answers.
- The 3-way pre-production check: today a Claude skill (`closet-factory-3way`); list its rules, put the arithmetic
  ones in the tool, keep the judgment ones for Claude.

## Rules that never bend

The owner's unit rules and the no-uncertain-value rule are in `.claude/skills/kcd-apply-rem/SKILL.md`. The live
Jewelry Trays Direct Shopify store is read-only. Customer files never in git. Every output is a TEST file until KCD or
Excel has opened it. Write to Mike in short plain sentences.

## Suggested first session

1. Get one finished job set from the laptop (notes 13 says which file the engineers paste from).
2. Run `kcdunits.py`, `kcdprice.py` (current list) and `kcdbook.py` on that room and compare with the engineer's
   workbook, cell by cell (`experiments/po/book_parity_werner.py` style; `compare_keys.py` for the price lines).
3. Build `kcdpaper.py`: finished room file -> priced workbook + the certain order cells + a check report of what the
   engineer still types. Reuse `kcdrun.room_workbook()`.
4. Write the open-questions list for the engineers in plain words and give it to Mike.
