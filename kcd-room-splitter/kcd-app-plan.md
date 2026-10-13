# KCD pricing and forms app: plan

Written Oct 13, 2026 after the owner answered the phase-2 questions. Read `kcd-deep-dive-notes.md` first
(what a `.job` holds and how KCD prices). This file says what to build, in what order, and what is still needed.

## 1. Owner's answers (Oct 13, 2026)

1. **Workbook master.** A copy of the master lives on the shop PC. The uploaded `mike_p_for_services.xltm` is that copy.
2. **Forms.** Fill as many forms as possible. All information comes out of KCD plus the other forms that help get a form right.
3. **Pricing.** The app must price the rooms the way the engineer does. If the KCD data is pasted in correctly, the price must come out the same as the engineer's.
4. **Price updates.** Sales management does the pricing updates and passes out the updated KCD library. The engineering KCD holds the price lists in a drop-down; jobs are priced on the list in force when they were sold.
5. **Users.** All engineers, after testing. Every engineer's PC has the KCD files (`C:\KCD23` and `C:\KCD23-STDPLIST`).
6. **KCD access.** Claude cannot get into KCD, but the owner can supply any file.
7. **Accuracy rule.** Never fill in anything that is not correct. If the app runs into a doubt, it calls it out so the engineer can verify and complete it.

## 2. What the first version does

Input: one engineered room `.job`, the KCD library folders already on the PC, the price list the engineer picks
(same names as KCD's drop-down), and the workbook template.

Output, saved next to the job:

- a filled copy of the workbook: Data Entry answers, the pasted price lines (Price, Unit #, Part Name, Depth, Length), nothing else touched, macros intact;
- the price review lines, computed from the price list, with KCD's own review as the cross-check while we prove it;
- order forms where every field is certain (special order doors, jewelry trays, others once the blank forms are in hand);
- a **VERIFY** list: every field left blank or doubtful, with the reason, in the same GREEN / YELLOW / RED wording the checking reports use.

The app never writes to KCD files, never changes the template, and never guesses.

## 3. Build order

1. **Verification set.** For about ten rooms, line up the `.job`, KCD's UNIT PRICE REVIEW, the filled workbook and the filled forms. Jobs and workbooks are already on the laptop for TILLIS (6 rooms), NOTIK (many rooms), BURNS, BOCUL, CONBOY, MORRIS, BRUNET and BERRIO; about twenty price review PDFs are in Microsoft 365.
2. **Job reader.** Turn `experiments/report_laptop.py` into a module: read a `.job`, load the `.cab` catalog from `C:\KCD23`, return a room sheet (units with sizes, materials, options, rods, doors and drawers, notes, sidebar fields).
3. **Price engine.** An interpreter for the KCD price-list language (`Set`, `DisplaySet`, `Do`, `Load`, `Price`, conditions) that runs the real price list folder against the room sheet and produces the same lines as KCD's UNIT PRICE REVIEW. Prove it line by line on the verification set; any difference is a flag, not a rounding excuse.
4. **Workbook filler.** Write cell values in place into a copy of the template (Excel on the engineers' PCs; XML cell edits as the fallback). Prove the file is byte-identical outside the edited cells and that the macros still run.
5. **Forms.** Inventory each blank form, map every field to its source, fill only the certain ones. Carry the rules from the checking projects: CF5 butt joint is 1/16 under the door-size elevation in both directions, miter is equal; Elements doors need left/right hinge side; Doormark uses decimals; jewelry tray depth follows the drawer depth (16 to 15, 19 to 18, over 22 to 21).
6. **Window.** Like KCD ROOM SPLITTER: pick the job, pick the price list, run, read the VERIFY list, open the outputs. Build the exe the same way.
7. **Engineer testing**, then roll-out.

## 4. Files still needed from the owner

- **A.** From an engineer PC: a zip of the whole `C:\KCD23` folder (unit library, part scripts `.prt`, reports `.Rpr`, doors `.dor`, handles `.Hdl`) and of `C:\KCD23-STDPLIST` (every price list). Also the newest update, `KCD23_Update_CFFL_ENGINEER_26-09-08.exe`.
- **B.** Blank forms: CF5 (5-piece / insert) form, Elements door form, Doormark form, jewelry tray order form, caddy form, stone selection form, CNC cover sheet, purchase order template, WoodWOP sheet, and any other form an engineer fills per job.
- **C.** For five to ten rooms whose `.job` files are already here (TILLIS, NOTIK, BURNS): the full ENG packet PDF (with the door-size elevations), KCD's UNIT PRICE REVIEW printout, the filled workbook and the filled forms.
- **D.** For each of those rooms, which price list it was priced on (the drop-down name), when it is not the newest.
- **E.** A sample of KCD's CSV parts export (`R:\import`) if anyone runs it.

## 5. Where the rules live

The checking work in the owner's Claude Projects reaches Claude Code as four synced skills: Pre-Engineering
checklist, 3-Way pre-production checklist, special order door check and shelf order cut list. Their rule packs
(`CORE_RULES_v1.md`, `PRE_ENG_DELTA`, `3WAY_DELTA`) live in the "CF RULES WORKSHOP" project, which Claude Code
cannot open. Suggestion: export the packs into this repo (a `cf-rules/` folder) so every session reads one copy
and the skills can be regenerated from Git. The owner decides.

## 6. Session note

This planning session had its command-line and helper-agent tools blocked by a safety check for the rest of the
conversation. Reading, the laptop tools and GitHub kept working, so the notes were pushed through the GitHub
connection. Start the build in a fresh session.
