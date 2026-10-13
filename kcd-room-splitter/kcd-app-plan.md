# KCD pricing and forms app: plan

Written Oct 13, 2026 after the owner answered the phase-2 questions. Read `kcd-deep-dive-notes.md` first
(what a `.job` holds and how KCD prices). This file says what to build, in what order, and what is still needed.

## 1. Owner's answers (Oct 13, 2026)

1. **Workbook master.** A copy of the master lives on the shop PC. The uploaded `mike_p_for_services.xltm` is that copy.
2. **Forms.** The forms are tabs at the bottom of the price workbook (list in section 3). Fill as many as possible. All information comes out of KCD plus the other tabs that help get a form right.
3. **Pricing.** Each room is always priced on its own. The app must price a room the way the engineer does: if the KCD data is pasted in correctly, the price must come out the same as the engineer's. The uploaded TILLIS, NOTIK and BURNS files are examples of the engineered end result.
4. **Price updates.** Sales management does the pricing updates and passes out the updated KCD library. The engineering KCD holds the price lists in a drop-down; jobs are priced on the list in force when they were sold.
5. **Users.** All engineers, after testing. Every engineer's PC has the KCD files (`C:\KCD23` and `C:\KCD23-STDPLIST`).
6. **KCD access.** Claude cannot get into KCD, but the owner can supply any file. He is gathering the files in section 5 now.
7. **Accuracy rule.** Never fill in anything that is not correct. If the app runs into a doubt, it calls it out so the engineer can verify and complete it.

## 2. What the first version does

Input: one engineered room `.job`, the KCD library folders already on the PC, the price list the engineer picks
(same names as KCD's drop-down), and the workbook template.

Output, saved next to the job: a filled copy of the workbook. Data Entry answers, the pasted price lines
(Price, Unit #, Part Name, Depth, Length) and the order tabs that the job needs, with nothing else touched and
the macros intact. Plus a **VERIFY** list: every field left blank or doubtful, with the reason, in the same
GREEN / YELLOW / RED wording the checking reports use.

The app never writes to KCD files, never changes the template, and never guesses.

## 3. The workbook tabs (from `1087543 TILLIS HER CO.xlsm`, 18 tabs)

| Tab | What it is | Where the data comes from |
|---|---|---|
| Data Entry | Job answers (client number, name, room, dates, designer, engineer, materials, banding, molding, yes/no questions, sold-at price) and the paste block for KCD's price lines | Job heading, room defaults (Set Unit Info), sidebar; price lines from the price engine. Sold-at price and dates come from the contract, not KCD |
| Modify Here | Working copy of the price lines (unit, part, width = depth, length, price); feeds everything else | Filled by the workbook from the paste block |
| Final Price Sheet | Job pricing page: subtotal, accessories, processing fee, standard price versus sold-at price | Workbook formulas |
| Job Cart Cover Sheet | CNC cover sheet and beam saw cover sheet: client, install date, core material, banding, faces, board counts, department boxes (beam saw, WoodWOP, rebore, drawer dept, specialty dept), due dates, hinge information | Data Entry; counts come from the nest, not KCD (leave for the engineer) |
| Purchase Order | PO header (date, customer, install date, engineer, ship-to) and item lines (room, qty, item, description, vendor); rows from 119 take the special-order CSV import | Data Entry; hardware and accessories from the job's handles, options and sidebar accessories list |
| VJT Order | Velvet jewelry tray insert form: per room, layout (1 bottom tray only, 2 double, 3 top tray only, 4 dovetail no top), shelf width, drawer depth, insert colour. Rules printed on the tab: tray width = ES width minus 2"; double VJT top tray = ES width minus 3 1/16"; tray depth = drawer box depth minus 1 5/8"; drawer box depths 12, 15, 18, 21 | Unit widths and drawer depths from the job; tray colour from the sidebar DESIGN NOTES |
| CF5 Order | Closet Factory 5-piece / insert door form: engineer types WIDTH and HEIGHT per door "according to KCD"; the tab computes cut size and insert sizes; specs (miter or butt joint), colour, insert; minimums 9 1/2" wide, 7 1/2" high | Door and drawer-front sizes from the job (I41.. heights, W minus reveals); style and colour from Set Unit Info texts 2, 12, 14, 15 |
| CF Stone | Stone countertop selection form | Countertop text (Set Unit Info 13) and sidebar COUNTERTOP TYPE / Area lines; edge and backsplash choices are the engineer's |
| CF Thermo | Thermofoil door form (design, sizes) | Same door sizes; design code from the door style text |
| Doormark A1, Doormark B1 | Doormark order forms (two designs per job possible) | Same door sizes in decimals; design and colour codes from the sidebar |
| Ladder | Ladder order | Engineer |
| BCCD A1 | Another door vendor form (confirm the name with the owner) | Same door sizes |
| Holes | Lookup: panel height in mm and inches to hole count (2420 mm = 95.25" = 76 holes, 32 mm pitch) | Panel heights from the job |
| W.W. Template | WoodWOP sheet template (top shelves drilled cams-up) | Nest, not KCD |
| Data Conversions | Lookup lists (colours, backs) | Fixed |
| Import | Landing sheet for the special-order CSV import macro | Macro |
| Work Required Grid | Due-date grid by work type | Install date |

The app fills Data Entry, the paste block and the order tabs whose fields it can prove. It leaves nest-driven
boxes (board counts, panel counts, WoodWOP) to the engineer and lists them on the VERIFY list as "engineer".

## 4. Build order

1. **Verification set.** For about ten rooms, line up the `.job`, KCD's UNIT PRICE REVIEW, and the filled workbook. Jobs and workbooks are already on the laptop for TILLIS (6 rooms), NOTIK (many rooms), BURNS, BOCUL, CONBOY, MORRIS, BRUNET and BERRIO; about twenty price review PDFs are in Microsoft 365.
2. **Job reader.** Turn `experiments/report_laptop.py` into a module: read a `.job`, load the `.cab` catalog from `C:\KCD23`, return a room sheet (units with sizes, materials, options, rods, doors and drawers, notes, sidebar fields).
3. **Price engine.** An interpreter for the KCD price-list language (`Set`, `DisplaySet`, `Do`, `Load`, `Price`, conditions, `AskQuestion`) that runs the real price list folder against the room sheet and produces the same lines as KCD's UNIT PRICE REVIEW. Prove it line by line on the verification set; any difference is a flag, not a rounding excuse.
4. **Workbook filler.** Write cell values in place into a copy of the template (Excel on the engineers' PCs; XML cell edits as the fallback). Prove the file is byte-identical outside the edited cells and that the macros still run.
5. **Order tabs.** Map every field of the tabs in section 3 to its source; fill only the certain ones. Carry the rules from the checking projects: CF5 butt joint is 1/16 under the door-size elevation in both directions, miter is equal; Elements doors need left/right hinge side; Doormark uses decimals; jewelry tray depth follows the drawer depth (16 to 15, 19 to 18, over 22 to 21).
6. **Window.** Like KCD ROOM SPLITTER: pick the job, pick the price list, run, read the VERIFY list, open the outputs. Build the exe the same way.
7. **Engineer testing**, then roll-out.

## 5. Files still needed from the owner (he is gathering them)

- **A.** From an engineer PC: a zip of the whole `C:\KCD23` folder (unit library, part scripts `.prt`, reports `.Rpr`, doors `.dor`, handles `.Hdl`) and of `C:\KCD23-STDPLIST` (every price list). Also the newest update, `KCD23_Update_CFFL_ENGINEER_26-09-08.exe`.
- **B.** For five to ten rooms whose `.job` files are already here (TILLIS, NOTIK, BURNS): the ENG packet PDF (with the door-size elevations) and KCD's UNIT PRICE REVIEW printout. The filled workbooks are already on the laptop.
- **C.** A few filled workbooks where the order tabs were used: CF5, Doormark, CF Thermo, CF Stone, VJT Order, Purchase Order with items. The TILLIS HER CO workbook has those tabs empty.
- **D.** For each verification room, which price list it was priced on (the drop-down name), when it is not the newest.
- **E.** A sample of KCD's CSV parts export (`R:\import`) if anyone runs it.

## 6. Where the rules live

The checking work in the owner's Claude Projects reaches Claude Code as four synced skills: Pre-Engineering
checklist, 3-Way pre-production checklist, special order door check and shelf order cut list. Their rule packs
(`CORE_RULES_v1.md`, `PRE_ENG_DELTA`, `3WAY_DELTA`) live in the "CF RULES WORKSHOP" project, which Claude Code
cannot open. Suggestion: export the packs into this repo (a `cf-rules/` folder) so every session reads one copy
and the skills can be regenerated from Git. The owner decides.

## 7. Session note

This planning session had its command-line and helper-agent tools blocked by a safety check for the rest of the
conversation. Reading, the laptop tools and GitHub kept working, so the notes were pushed through the GitHub
connection. Start the build in a fresh session.
