---
name: kcd-apply-rem
description: Run one Closet Factory remeasure for the engineers, end to end - read the REM sheet, apply it to the designer's KCD .job (walls, heights, same-size sections, fillers, interior shelves, drawing cache), write the TEST job and a plain-English report, and fill the room workbooks when a price run exists. Use when a .job and a remeasure PDF are uploaded with "apply the rem", "run this job" or "do this one".
---

# Apply a remeasure to a KCD job (the engineers' first pass)

You are doing the unskilled part of engineering a sold closet job so the engineer only reviews and decides.
The owner is Mike Policy, not a programmer: write to him in short plain sentences, never jargon.

## Inputs
- the designer's `.job` (KCD v23) and the remeasure scan `REM-<order>-<NAME>.pdf` (uploaded, or on the test laptop under
  `%TEMP%\kcdjobs10\<order> <NAME>\`). The Salesforce page is usually page 1 of the scan.
- optional: a price run of the room (a `kcdprice.py` TSV made on the laptop) and the sidebar answers for the workbook.
Tools: `kcd-room-splitter/` in this repo (`kcdwalls.py`, `kcdmesh.py`, `kcdunits.py`, `kcdbook.py`, `experiments/po/*`).
Read `kcd-room-splitter/CLAUDE.md` once per session; the detail is in `kcd-deep-dive-notes.md` sections 14-16.

## Rules that never bend
- Never write a number you are not sure of. A doubtful reading, a corner that does not match, a unit the rules cannot
  place: write CHECK and say why, so the engineer decides. A CHECK is better than a wrong inch.
- Owner's unit rules: fillers stay 3/4; the units change, not the fillers; the total of all units equals the wall length;
  the hanging sections of a changed wall share the change so they come out the same size; interior shelves match the
  opening of the cabinet they sit in; drawer units and catalog units keep their width; a run between two walls gets a
  3/4 filler at each end; hamper fronts and flip-ups count as doors.
- The live Jewelry Trays Direct Shopify store is never touched. The test laptop is read-only except our own `%TEMP%`
  folders. Customer files never go into git: only code and notes.
- The output is a TEST file until KCD has opened it. Name it `<Client> - REM <order> applied - TESTn.job` and say so.

## Steps
1. Render the scan (`pdftoppm -r 150 -png`, and `-r 260` crops for the handwritten numbers) and READ it yourself.
   A printed wall number circled or ticked without a new number beside it is CONFIRMED as drawn. A wall measured in
   pieces (door wall: left part, door opening, right part) is the sum, and the pieces go in a fact line. Write the
   facts H, HD, BB, F, Door, Molding, HOLES per room and every angle written at a corner.
2. Write the read-out JSON (`walls/grok/REM-<order>-<NAME>.json` style): `consensus` lines
   `{"label": "<KCD room name> #<n> (printed <old>)", "value": "<new>", "confidence": "high|medium"}`, facts as
   `"<room> H"`, corners as `"<room> corner #a/#b angle"`, plus `reader` and `notes` telling how it was read.
   The room names must be the KCD room names (`python3 kcdwalls.py JOB --list` shows them).
3. Apply: `python3 kcdwalls.py JOB --rem REM.json --heights-from-rem --out TEST1.job > REPORT.txt`.
   Read the report: every wall line, the CHECK list, the facts. Fix your JSON and rerun rather than hand-edit.
4. Fillers: `python3 experiments/po/fillers.py` (import `missing_fillers`) on TEST1. For a FIX finding at a bare
   wall end run `experiments/po/reserve.py TEST1 WALL OUT` (makes the 3/4 room by the same-size rule) then
   `experiments/po/addfiller.py OUT --source <a filler of the same job> --wall WALL --x end --out TEST1b.job`.
   CHECK findings (corner zones, angled corners, drawer or catalog units at the end) stay for the engineer.
5. A door opening measured on the sheet is moved with `experiments/po/adjust.py` (unit = X, W); say so in the report.
6. Report for the engineer (plain English, one file next to the job): what the sheet said, what changed wall by wall,
   the CHECK list, the room facts, and what was NOT done and why. Keep the tool's wording; add the human notes.
7. Pricing is optional: the engineer prints KCD's UNIT PRICE REVIEW themselves, or the room is priced on the laptop
   (`price_job.py JOB TAG`). Only when a price TSV exists build the workbook:
   `python3 kcdbook.py wb/template.xltm "<order> <NAME> <ROOM>.xlsm" --lines PRICE.tsv --entries ENTRIES.json --report R.txt`
   with the answers taken from the sidebar (`experiments/po/sidebar.py`) and the Salesforce page; `--cell` writes the
   Purchase Order / Doormark / VJT / CF5 lines that are certain (see the kcdbook docstring). Leave blank what is not known.
8. Deliver the TEST job, the report and any workbook with SendUserFile, then list the CHECKs in three or four lines.

## What goes back to the learning project
The KCD-saved copy of every TEST file, the engineer's finished room file and workbook, and every rule the owner states
in words. Those are compared with `kcdcompare.py` and written into the notes; the tools only change there.
