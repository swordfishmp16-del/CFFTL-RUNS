# Grok findings: fill the engineering workbook from the finished KCD file

Written October 31, 2026. This file is separate on purpose. It is not a change to the run book and it is not a change to the tools. Point Claude at this file for the final build of the paperwork fill.

The rem run (walls, fillers, a workbook before engineering) is a different job. Do not fill production paperwork from that workbook. The source is the room `.job` the engineer saved when the room was finished.

## What "done" means

Drop in that `.job`. Answer the questions below. Get back the workbook with every cell the engineer would have typed, matching the seventeen finished workbooks already on the laptop. Not close. The same parts, the same sizes, the same prices, the same order-form lines.

Those seventeen are the test. A build that has not been checked against all of them is not finished.

- KCD files: `C:\ENG KCD TESTING\<order> <NAME>\*.job`
- The engineer's workbooks: `C:\ENG KCD TESTING EXCEL\<order> <NAME>\*.xlsm`
- Seventeen pairs. Norwich has six rooms. There is also `1083602 NORWICH WIC fix.job` with no workbook; ignore it.
- Jobs: Raab master, Norwich bed2 bed3 bed4 linen men wic, Mayer master, Orgel billy pantry robin, Amato pantry, Coco laundry, Sharpe mbr, Colmenares wardrobe, Werner office, Khoshnood dining.

The styles in that set are melamine, CF5, thermofoil (Doormark), a mix of those on one job, and one room with no doors (Norwich linen). None of the seventeen used the stone order form.

## What the person types before it starts

Only what is not in the file. Ask, then run. Do not leave a blank and call it done.

1. Date the job was sold. This picks the price list. It is not in the KCD file.
2. Install date. It is on every one of the seventeen workbooks (Data Entry B1) and in none of the jobs.
3. Contract, if that cell is one the shop still fills. It was not a Data Entry cell on these seventeen.

Do not ask for these when the job heading already has them. Do ask when it does not.

| Heading on the finished job | Ask only if that line is blank |
|---|---|
| Job number | Raab's heading is `Raab, Susie` and does not contain `1081681`. The others do. |
| Client last name | Usually there. |
| Room | Usually there. Data Entry B9. |
| Designer | There on Orgel, Sharpe, Colmenares, Werner. Not there on Raab, Norwich, Mayer, Amato, Coco, Khoshnood. Data Entry F1. |
| Who prepared the cut list | Often the last heading line (Scott, Andrew, Alexander, Rubio, Vicente). Data Entry F3. |

Costco was No on all seventeen (Data Entry B11). Default it to No. Do not ask.

Hinge type (Data Entry B15) is not a field that was found in the job. On these workbooks it is Self Closing, blank, or Combination (Khoshnood). Do not default every job to Self Closing. Find where KCD stores it, or the form is not finished.

## Price list: the rule

The lists are folders in

`C:\Users\sword\OneDrive - Closet Factory (Fort Lauderdale)\me and claude\STDPLIST`

(and the same folders under `me and claude\KCD23\STDPLIST`). The pricing folders are named like `_26-05-22 MAY CFFL PRICING`. The date is the start of the name. Counter tops are the matching `CFFL COUNTER TOPS` folders. Each pricing folder on disk has 833 files, so treat each one as a full list.

Use the newest list whose date is on or before the sold date. Never use a list dated after the sold date.

- Sold May 30, 2026, and a May 22 list exists: use `_26-05-22 MAY CFFL PRICING`.
- Sold May 10, 2026: May 22 is after the 10th, so use `_26-05-03 MAY CFFL PRICING`.
- Sold in June, and there is no June list: use May 22. Do not use July.
- Sold April 1, 2026: April 2 is after April 1, so use `_26-03-18 MAR CFFL PRICING`.

The list in the GitHub repo, `kcd-room-splitter/data/pricelist/_24-09-16 SEP CFFL PRICING`, is September 2024. Do not price a 2026 job with it. Say on the report which folder was used.

Same rule for the counter-top list when the room has stone.

## Unit library: the rule

The library the program ships was built October 13, 2026. It is behind KCD.

The shop library to rebuild it from is

`C:\Users\sword\OneDrive - Closet Factory (Fort Lauderdale)\me and claude\KCD23\NEW CFFL UNIT LIBRARY`

Checked: `CSE201nd-slidingshelves.CAB` is in that folder. It is not in the bundle. Werner and Khoshnood both use it, and the program reported those cabinets as unknown and dropped their doors.

Rebuild `cat_compact.json.gz` and `rawlib.json.gz` from that library (`catjson.py` and `rawlib.py`). The check is the seventeen jobs: every `.cab` they name must be in the bundle. KCD23 is the check, not an old copy.

## Where the form's lines have to come from

The engineer pastes KCD's UNIT PRICE REVIEW into Data Entry, columns K price, L unit, M part, N and P the sizes. That paste is the form. Werner has 50 lines. Norwich WIC has 271. Mayer has 227.

Those lines are not stored as text in the `.job`. KCD works them out from the sizes and the price list. `kcdprice.py` is that same math, and `kcdbook.py` already knows how to write the paste without breaking the workbook. That is the path. Do not re-save the workbook with openpyxl.

Do not fill doors from the cabinet drawing. That path was run on all seventeen. It matched the engineer's door count on one room (Amato, 14) and missed the other sixteen.

| Room | Engineer door and drawer lines | Program, from the drawing |
|---|---|---|
| Norwich linen | 0. Sidebar says no faces. | 4. It ordered doors that are not there. |
| Mayer master | 11 | 31 |
| Orgel pantry | 18 | 8 |
| Orgel robin | 46 | 32 |
| Werner office | 6 | 2 |
| Khoshnood dining | 6 | 0 |
| Coco laundry | 12, and the lines say Gulfstream | Sidebar says Shaker Thin |

The sidebar is not always the door that was ordered. Coco's sidebar says Shaker Thin. The paste says Gulfstream. Khoshnood's door style was sitting under the handles note, so the reader saw a blank style, while the paste says Abacoa Shaker. Colmenares' sidebar was blank and the paste says Abacoa Shaker and Shaker Thin.

The priced line wins. If the sidebar and the priced line disagree, follow the priced line and say so in the report. Do not ask the engineer to retype it.

A door turned off in KCD is still sitting in the drawing. Reading the drawing will order that door. The price scripts are what drop it. That is why the drawing count cannot be the form.

## Order forms

Data Entry feeds the headers. The order tabs get their line items from those same priced lines.

- Thermofoil (`TH`) goes to Doormark. Design code from the door name on the priced line (Sarasota Shaker to SHS, Abacoa to SHA, Gulfstream to GUL). The tables are in `experiments/po/soitems.py`. Mysterious Blue is not in the workbook color table. Werner's color is that name. Add the code the engineer actually types, and check it against Werner. Do not invent one.
- `CF 5` goes to the CF5 tab. Miter or butt comes from the style text (`M CF` or `B CF`). Amato says specialty glass and the reader marked it ASK. The priced lines on Amato are a normal grain insert. Follow the priced line.
- Melamine is cut in house. No order form. Norwich linen is the check: zero door lines, no form.
- A room with two kinds of doors (Raab: CF5 and melamine) is a combination. Face type on Data Entry F11 can be read off the priced lines. One kind, or Combination when there are two. Check that against Raab before trusting it.
- Jewelry trays, handles with a part number, and accessory codes go to the purchase order and the VJT tab. A handle line that says `Enter PN`, or an outlet with no part number, has nothing to type. Those were the only hardware holes on Werner. Do not invent a part number.

## Door swing

Hinge count is in the sidebar. Hinge side is not, not in a way that survives a door the engineer flipped.

A door nobody flipped can be labeled from the cabinet the job names: `1` left, `2` right, `3` bottom, `4` top. The right leaf of a pair is the right hinge even when the code says `1`. See `kcd-room-splitter/DOOR-SWING.md`.

A flipped door is masked in the job. It does not read back out as left or right. Do not guess it. The parts list KCD prints does say HL, HR, HB, or HT, because KCD has already resolved it. Until that mask can be read, a flipped door is the one line that cannot be filled from the `.job` alone. Find it and read it, or this item stays the exception. Do not ship a guess.

## What Claude has to change

1. Rebuild the two library bundles from `KCD23\NEW CFFL UNIT LIBRARY`. Fail the run if a job names a cabinet the bundle does not have. Do not skip that cabinet.
2. Pick the price list with the sold-date rule above. Print the folder name on the report.
3. Price the finished `.job` with that list and write the paste with `kcdbook.py`. This replaces the drawing-based door count.
4. Ask only the questions in the table above, and only when the heading is blank. Always ask sold date and install date.
5. Fill Doormark, CF5, the purchase order, and VJT from the priced lines, not from the sidebar when the two disagree.
6. Do not run the rem or the filler step on a finished file.

## Not done until this passes

For every one of the seventeen pairs: the Data Entry paste matches the engineer's paste on price, unit, part, and both sizes, and every order-form cell the engineer typed matches. A difference is a miss, not a note.

The drawing-based door list already failed that test. Do not use it as the proof.
