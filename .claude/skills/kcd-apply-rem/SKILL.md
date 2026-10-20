---
name: kcd-apply-rem
description: Run one Closet Factory remeasure for the engineers, end to end - read the REM sheet, apply it to the designer's KCD .job (walls, heights, same-size sections, fillers at both ends, interior shelves, drawing cache), split the result into one KCD file per room, fill a pricing workbook per room with everything that is certain, and write a plain-English report. Use when a .job and a remeasure PDF are uploaded with "apply the rem", "run this job" or "do this one".
---

# Apply a remeasure to a KCD job (the engineers' first pass)

You are doing the unskilled part of engineering a sold closet job so the engineer only reviews and decides.
The owner is Mike Policy, not a programmer: write to him in short plain sentences, never jargon.

## Inputs
- the designer's `.job` (KCD v23) and the remeasure scan `REM-<order>-<NAME>.pdf`. Mike drops them into
  `jobs/<order> <NAME>/` (uploaded files go there too; the folder is never committed) and types `run <order>`.
  Page 1 of the scan is usually the Salesforce sale page: order number, client name, designer, install date, sold price.
- optional: a price run of a room (a `kcdprice.py` TSV made on the test laptop). Without one the price block of the
  workbook stays empty and the engineer pastes KCD's UNIT PRICE REVIEW.
Tools: `kcd-room-splitter/` in this repo. Read `kcd-room-splitter/CLAUDE.md` once per session; the detail is in
`kcd-deep-dive-notes.md` sections 14-16. The template and the library bundles are in `kcd-room-splitter/data/`
(nothing is needed from the laptop).

## Rules that never bend
- Never write a number you are not sure of. A doubtful reading, a corner that does not match, a unit the rules cannot
  place: write CHECK and say why, so the engineer decides. A CHECK is better than a wrong inch.
- Owner's unit rules: fillers stay 3/4; the units change, not the fillers; the total of all units equals the wall length;
  the hanging sections of a changed wall share the change so they come out the same size; interior shelves match the
  opening of the cabinet they sit in; drawer units and catalog units keep their width; a run between two walls gets a
  3/4 filler at each end; hamper fronts and flip-ups count as doors.
- The workbook gets only what is certain from the job, the sidebar and the sale page. Door sizes are never typed on an
  order form (the sizing rule is not settled); they go in the report for the engineer.
- The live Jewelry Trays Direct Shopify store is never touched. The test laptop is read-only except our own `%TEMP%`
  folders. Customer files never go into git: only code, notes and the `data/` bundles.
- Every output is a TEST file until KCD has opened it. The applied job is named `<Client> - REM <order> applied - TESTn.job`.

## Steps
0. `run 1084476` means: find `jobs/1084476*/`, take the `.job` and the `REM-*.pdf` in it, do steps 1-2 with the
   read-out JSON written next to the scan, then step 3 with `python3 kcdrun.py 1084476` (it finds the files itself and
   writes into `jobs/1084476 <NAME>/out/`). If the folder holds two `.job` files or no scan, stop and ask which.
1. Render the scan (`pdftoppm -r 150 -png`, and `-r 260` crops for the handwritten numbers) and READ it yourself.
   A printed wall number circled or ticked without a new number beside it is CONFIRMED as drawn. A wall measured in
   pieces (door wall: left part, door opening, right part) is the sum, and the pieces go in a fact line. Write the
   facts H, HD, BB, F, Door, Molding, HOLES per room and every angle written at a corner. Note the order number,
   client name, designer, install date and sold price from the sale page.
2. Write the read-out JSON (`walls/grok/REM-<order>-<NAME>.json` style): `consensus` lines
   `{"label": "<KCD room name> #<n> (printed <old>)", "value": "<new>", "confidence": "high|medium"}`, facts as
   `"<room> H"`, corners as `"<room> corner #a/#b angle"`, plus `reader` and `notes` telling how it was read.
   The room names must be the KCD room names (`python3 kcdwalls.py JOB --list` shows them).
3. Run the whole chain with one command (from `kcd-room-splitter/`):
   `python3 kcdrun.py JOB.job --rem REM.json --order <order> --name <LASTNAME> --client "<First Last>" --out DIR
    [--designer "<name as in the workbook list>"] [--install YYYY-MM-DD] [--sold <price>] [--main "<room>"]`
   It applies the walls and heights, shares the change over the same-size sections, fits the interior shelves, runs the
   filler rule (a 3/4 filler is added where a run between two walls has none; corner zones, angled corners and drawer
   units at a wall end become CHECKs), moves the drawing cache, writes `<Client> - REM <order> applied - TESTn.job`
   and its REPORT, splits that file into `DIR/<order> <NAME>/<order> <NAME> <ROOM>.job` with the splitter's own SPLIT
   REPORT, fills `<order> <NAME> <ROOM>.xlsm` per room from `data/template.xltm` (Data Entry answers from the sale page
   and the sidebar, the Purchase Order lines and the Doormark design and colour that are certain) with a WORKBOOK
   REPORT each, and writes `DIR/<order> <NAME> RUN REPORT.txt` with every CHECK in one place.
   `--price "<ROOM>=PRICE.tsv"` pastes a price run; `--entry CELL=VALUE` or `"TAB!CELL=VALUE"` types a cell you are
   sure of; `--replace` overwrites room files from an earlier run; `--no-rem` is simply leaving `--rem` out (filler
   check, split and workbooks only).
4. Read the RUN REPORT: every wall line, the CHECK list, the room facts. Fix your JSON and rerun with `--replace`
   rather than hand-edit a file.
5. A door opening measured on the sheet (the "#n door opening" fact) is not moved by the chain: run
   `python3 experiments/po/adjust.py TEST1.job TEST2.job UNIT=X,W ...` on the applied file, then
   `python3 kcdrun.py TEST2.job --order ... --name ... --client ... --out DIR --replace` (no `--rem`) to split and
   book the adjusted file. Say so in the report.
6. Deliver the TEST job, the RUN REPORT, the room files and the workbooks with SendUserFile, then list the CHECKs in
   three or four lines. Keep the tool's wording; add the human notes.

## What goes back to the learning project
The KCD-saved copy of every TEST file, the engineer's finished room file and workbook, and every rule the owner states
in words. Those are compared with `kcdcompare.py` and written into the notes; the tools only change there and are then
merged into the `production` branch.
