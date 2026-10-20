# KCD deep dive: what a `.job` holds and how KCD prices it

Written Oct 12, 2026 for the "KCD and pricing workbook" project. Plain words, for the owner and for whoever
builds the next tool. Every fact is marked **confirmed** (checked against a file KCD saved or against an
engineering price review), **likely** (fits all data seen but not cross-checked) or **unknown**.

No customer data is in this repo. Checks were run on the test laptop against 149 jobs plus the engineering
workbooks that sit next to them (BOCUL PRIMARY, CONBOY NURSERY, MORRIS GARAGE, BRUNET LIVING, BERRIO ODK,
TILLIS HER CO and others). Scripts used are listed at the end.

## 1. The pipeline we are trying to automate

1. The designer draws in KCD v23 and saves a `.job` with all rooms (heading = customer name, address, phone).
2. Engineering splits it into one job per room (KCD ROOM SPLITTER does this), renames it
   `<job#> <LAST NAME> <room>.job`, fills the heading (`1087543 TILLIS`, `HER CO`, engineer name), adds wall
   notes (`HOLES`, `NO HOLES`, `FIRE SPRINKLER`), custom hole panels, top platforms, and removes
   designer-only units such as `890nc.cab` "No-price Baseboard for show".
3. Engineering runs KCD pricing. KCD prints the **UNIT PRICE REVIEW** (one line per part: Unit #, Name,
   Depth/Width, Height/Length, Cost; then Subtotal, Countertops, Handles/Knobs, Crown/Base molding,
   Job Processing Fee 199, Total).
4. The engineer pastes those lines into the Excel workbook (`mike_p_for_services.xltm` family), fills Data
   Entry, and the workbook builds the Final Price Sheet and the order/PO forms.

Everything the price review needs is in the `.job` plus two library folders that every KCD computer has:
`C:\KCD23\NEW CFFL UNIT LIBRARY` (unit definitions) and `C:\KCD23-STDPLIST\<date> CFFL PRICING` (price list).
Both arrive in the "ENG UPDATE" zips.

## 2. Where the pricing data sits inside a `.job` (confirmed)

Section layout is in `CLAUDE.md`. New details found in this pass:

### 2.1 Unit record = 1806-byte prefix + strings + 86-byte block + Set Unit Info + suffix

**Prefix (1806 bytes) = 301 slots of 6 bytes, one per unit "size item" (confirmed).**
Slot N starts at byte 6×N. Bytes 0..3 = Int32 value in 0.1 mm (divide by 254 for inches; counts and
yes/no flags are stored as plain integers), byte 4 = state byte, byte 5 = 0.
The meaning of slot N comes from the unit's `.cab` file (`#Sizes` table, column 1 = item number).
State byte: 0 = default/computed, 2 = typed by the user (seen on Depth, Right Side = 0, rod heights, door
heights), 1 = integer/yes-no item (matches the 4th column of the `.cab` size line). **Likely** for the
exact meaning of 2.

Slot numbers that are the same in nearly every `.cab` (from a survey of all 1,296 `.cab` files):

| Slot | Meaning | Notes |
|---|---|---|
| I1 | Location: X along the wall from the wall's left end | inches = value/254 |
| I2 | Width W | |
| I3 | Height H | fillers use the room height (SPCH) |
| I4 | Depth D | |
| I5 / I7 | Left side / Right side thickness | 0 = no panel on that side (shared with the neighbour) |
| I6 | Middle divider thickness | 0 = none |
| I8 / I9 / I10 | Top / middle / bottom shelf thickness | |
| I11 | Kick height | 635 = 2.5" |
| I13 | Off floor | wall units |
| I14 | From wall | fillers show 9" or 13" here |
| I15 | Angle | |
| I16 / I17 | Left / right cut back | |
| I19 | Total number of adjustable shelves | |
| I20, I22, I23, I24, I25 | Opening heights top → bottom | derived, stored |
| I21 | Lower middle rail thickness | |
| I31, I33, I32 | Adjustable shelves in top / middle / bottom section | |
| I36 | Number of door openings | 1, 2 or 3 |
| I37 | Number of drawer openings | |
| I41..I46 | Door and drawer front heights top → bottom | first is the top door, then drawers |
| I52..I58 | Gaps and reveals | 32 = 1/8", 111 = 7/16", 16 = 1/16" |
| I61 | Hanger space from wall | hanging units, 24" |
| I70..I74 | Molding front/left/right/back flags | |
| I75 | Molding overlap | |
| I119 | No kick notch (1 = yes) | |
| I121 | Show backs (1 = yes) | |
| I152..I155 | TV / stereo opening settings | entertainment units |
| I192 / I193 | Back / front system-hole location | custom hole panels |
| I251, I252, I253 | 1st, 2nd, 3rd closet rod height | 0 = no rod. Pricing calls these crodht1..3 |
| I254 | Full doors (1 = yes) | |
| I270..I289 | "No holes" ranges | custom hole panels |

A full slot dictionary (every item number with its labels and default formulas across all cabs) is produced
by `report.py` into `catalog_slots.txt` on the laptop. Door, drawer-box and shelf sizes that appear on the
price review are all reproducible from these slots:
shelf and rod length = W − LS − RS (rod minus 1/4"), kick length = W, panel size = D × H,
drawer box height = door/drawer front heights (I42..), drawer front width = W − reveals.

**Body strings (9 STR, confirmed):** `cat` = CabList display name (e.g. `96 Tall 3 Opening`),
`cab` = unit file (`773-96.cab`), `lib` = library folder, `prt` = parts script name (`Z773.prt`),
`pcb` = **pricing script name (`ZC773.pcb`)**, `name` = code template or resolved code (`=#106#=` or
`T-Double-Hg91`), `edge`, `shp`, `profile` = edge profile.
In KCD's own words `cat` is the unit **Name** (`#Name` in the price scripts) and `name` is the unit **Code**
(`#Code`): `=#n#=` is entry n of the library's `Code.dat` (`n, formula, description`, where `[w@1]` in the
formula is the width rounded to 1"), and accessories carry literal codes (`Accessory`, `CLO-SH`,
`310.3020.12.MG(808.71.001)`). The reader keeps the old attribute names; use `Unit.kcd_name` and
`Unit.kcd_code(catalog)`. Found on Oct 13, 2026 when accessory units printed their code instead of their name.

**86-byte block (mostly confirmed):**

| Bytes | Meaning |
|---|---|
| 0..1 | wall id (0 = deleted unit) |
| 2..3 | flag |
| 6..7, 8..9 | small counts (2/1 on door units, 0/0 on fillers) – unknown meaning |
| 10..11 | number of size items in the unit's `.cab` (15 for 234.cab, 44 for CSE304-96.cab) – confirmed |
| 12..15 | Width W (Int32, 0.1 mm) – confirmed |
| 16..39 | six Int32: the unit's slice of the `mesh` section – vertex count, vertex offset, face offset, face count, index offset, index count (counts sum to the mesh totals and the offsets tile; confirmed on a 23-unit job). Not prices |
| 40..63 | two 3D centre points (X+W/2, from-wall + D×k, H/2) in wall coordinates – confirmed |
| 64..65 | **unit type code T** from the `.cab` (230 filler, 300 tall, 320 tall 3-opening, 100 upper w doors, 170 upper L corner, 200 base, 500 backing, 550 custom/finish panel, 641 shelf, 651 single hang, 652 double hang, 670 L-shape, 880 leg leveler, 1000 accessory/obstruction, 20 door, 10 window) – confirmed |
| 66..67 | unit quantity (1 in almost every unit; 2 or 10 seen on LED strips and a filler). KCD prints the unit's price lines quantity times |
| 72..73 | 190 (0.75" material thickness) |

The earlier guess that bytes 16..39 are "price-like values" was wrong; KCD does not store prices in the job.

**Set Unit Info (confirmed):** the 8 + 7 strings after the block are `#ExtraUnitText1..15`:
1 unit material `"Designer White Grain  1 1.00"` (last token = **material price multiplier**; wood is
`"Stained Grain Wood  .5 2.50"`, outdoor `"OD-Gray  0 2.00"`), 2 door/drawer face type, 3 edgebanding,
4 rod type (`Round Polished Chrome`, `Syn Matte Gold`), 5 base type, 6 crown, 7 backing, 8 drawer box type,
9 notch depth, 10 notch height, 11 handle text, 12 contrast material + multiplier, 13 countertop,
14 door/drawer finishing, 15 insert. The room defaults section holds the same 15 strings per room.

**10 bytes + unw/unwname:** `unw` = the saved-unit file the unit was placed from
(`...\96 Filler 12.UNW`). A `.UNW` file holds one unit record in the same layout (prefix, strings, block).

**27-byte suffix:** unit id at +12/+14/+16; Int16 at +4 varies (3, 12, 13…) – unknown, not options.

### 2.2 Options are in the settings section (confirmed on 5 jobs)

`settings` ends with `npair` pairs of (Int16 unit id, Int16 code). **code + 1 = option number in the
library's `options.dat`.** Checked against four engineering price reviews:
code 11 → #12 Opt-Set Holes Custom, code 4 → #5 Opt-Shelf-Stiffeners 1 side, code 12 → #13 Opt-3 Hole
Adjustable Custom, code 99 → #100 Opt-LED Routed Full Panel Strips, codes 205/206 → #206/#207 Outdoor
Vents Left/Right Panel. A unit can carry several pairs. (One job, BOCUL PRIMARY, showed the option on two
more units in the workbook than in the file; the workbook probably came from a later save.)

The rest of `settings`: STR handle group (`Standard Handles`, `Client Supplied`), 9 STR door-style names
(`flat-VG`, `flat-HG-DR`, `Sgp`, `AF016GLD`…), a 501-entry colour table (Int16 index + RGB), then per
library a list of 150 (Int16 item, Int32 value) **shop-standard sizes** (item 1 wall height 96"/107", 2 floor
to top of wall cabinets, 4 depth of wall cabinets, 38 depth of tall cabinets, 3/37/5 heights, 9/10/11 side
thickness 190…). These are the S-variables (SPCH, SPCD, SLS…) the `.cab` defaults refer to.

### 2.3 Other sections that matter

- **header heading:** 5 lines. Designer files: name, address, city, phone, email. Engineered files:
  `<job#> <NAME>`, room, blank, designer, engineer (order varies by engineer).
- **defaults:** 15 Set Unit Info strings per room (room k = set k−1).
- **handles:** per room 9 hardware slots (STR `.Hdl` path, 28 bytes of floats, STR `False`).
- **notes:** the sidebar `ROOM DETAILS …` text (height, material, edge banding, backing, rods qty,
  handles qty, door style, drawer box, crown/base qty, options and accessories, room information), plus
  wall notes (`HOLES`, `NO HOLES`, `FULL BORELINES`, `FIRE SPRINKLER`). Note record: 30-byte header
  (Int16 wall id at +24), STR text, STR font, STR size, 36-byte trailer (Int32 room at +4).
- **unit numbering on the price review = unit ids in file order** (confirmed on 3 jobs).

## 3. The unit library (`C:\KCD23\NEW CFFL UNIT LIBRARY`, confirmed)

Plain text, one `.cab` per unit type (1,292 files + 84 TAG hardware cabs). Layout of a `.cab`:

```
700,  26480.562 ,Version ENTERTAINMENT 3 VERT OP      <- header, display label
254,Inches=254 or Cm=100
0,LtoL
1,Door                                               <- has doors
#Code, =#106#=                                       <- code template (Code.dat)
#Option / 0
#Extra Variable... / 0
#Sizes... Next Lines - Item#    Size    Label        <- THE SLOT TABLE
50
1,0,Location,0
2,0,Width,0
3,95.25,Height {320},0
4,SPCD,Depth,0
...
251,0,1st Closet Rod Height,0
Z773.prt                                             <- parts script
ZC773.pcb                                            <- pricing script
320                                                  <- type code T
#Choose File Questions ... (which .cab variant: 1 opening / 2 openings, left / right corner)
#Extra Variables ... (E-variables, formulas)
#Center Point of Unit
#Pts / #Faces  (3D geometry; face lines flagged "door" / "drawer" tell how faces are drawn)
Load Statements  (sub-components: sh-tall.cld, Top1.cld, Bottom1.cld, Fixedshelf.cld,
                  sd-basesides.cld, bk-stdback.cld, CSEROD.CLD, DV-divider.cld, Pull.cld, MOLDING.MLD)
```

Other library files: `CabList.Dat` (menu: code, display name, `.cab` or `.UNW`), `options.dat` /
`optionsnew.plt` (option number, name, cost), `Sizes.Lst` (shop standards), `Code.dat` (code templates),
`Lock\*.Lok` (tiny per-size lock files, not part scripts), `Custom\*.UNW` (saved units), `*.cld/.mld`
(sub-components), `*.inc` (CNC hole patterns). **The part-list scripts (`Z*.prt`) are not in the ENG UPDATE
zips**; only `FixedShelves.prt` is. Cut lists therefore still need KCD (or a rebuild of the `.prt` logic).

## 4. The pricing library (`C:\KCD23-STDPLIST\_<date> CFFL PRICING`, confirmed from Sept 2024 and June 2025 copies)

About 800 small text scripts (`.pcb`). Language: comma-separated lines; a line starting with `,` is a
comment; `Set`/`DisplaySet` (grid-editable constant with a prompt), `Do,(cond):1 { }`, `Load,(cond):file`,
`Price,(cond):qty, name, cost, dim1, dim2, printorder` (one report line), `Part,…` (parts list),
`AskQuestion`, `Skip`. Conditions use `& | = <> < >`, `(cond):a:b` is if-then-else, `[expr]` forces a number.

Flow for one unit (confirmed): `A-SetUp.Pcb` runs once (defaults, names, print order, loads
`S-Shelf Thicknesses`, `H-Discounts and Fees`, `I-Designer Markup`, `AA-User`), then the unit's own
`Z<unit>.pcb` (the `pcb` string in the unit record) sets `#VertH=[H]`, `#VertD=[D]`,
`#ShelfWidth=[(W-LS-RS)]` and loads shared scripts: `Pricesides.pcb` (left/right panel via `B-Side Cost.Pcb`
grid), `Pricedividers.pcb`, `Pricefixedshelves.pcb`, `Priceadjshelves.pcb` (via `C-Shelf Cost.Pcb` grid),
`Pricerods.pcb`, `Doors.pcb`, `Drawers.Pcb`, `G-Pullout Cost.Pcb`, plus `Price` lines for back and kick.
`Eachunit.pcb` prints `CALL FOR QUOTE` when a unit has no price script.

Built-in variables the scripts read from the unit (confirmed by use): `W H D LS RS MS LMS BMS TR MR BR LMR K
SH SH1..SH6 DH1.. npo opt T ul ur ult urt lcb rcb bkyn nkhyn crodht1 crodht2 crodht3 I<n> E<n> FW LF RF`
and the `#ExtraUnitText1..15` names (`#UnitMaterialName`, `#MaterialCostGroup`, `#EdgeBandingType`,
`#ClosetRodType`, `#BaseType`, `#BackType`…). `opt` loops over the unit's option numbers (the settings
pairs + 1).

Key logic and constants (Sept 2024 copy; the June 2025 copy on the laptop has higher numbers):

- Panels: `B-Side Cost.Pcb` grid by depth (12, 16, 18, 24, 32, 48, 48.125) × height (24, 48.63, 96, 120),
  times `#panelpricemultiplier` (1.10), times material multiplier from Set Unit Info text 1.
  Example 2024: 12" × ≤96" = 147 × 1.10; 16" = 182 × 1.10. The 2025 price review shows 185 and 229.
  `#PanelTouchingWallCost` is added when `ul`/`ur` says the panel touches a wall.
- Shelves: `C-Shelf Cost.Pcb` grid by depth (12, 16, 18, 24, 32, 48) × length (39, 48, 96) times
  `#shelfpricemultiplier` (1.12). 2024: 12" ≤39" = 36 × 1.12; 16" = 39 × 1.12. 2025 review: 46 and 50.
  Fixed shelves print as `Top/Middle/Bottom Euro Shelf`, adjustable as `Adj Shelf`.
- Rods: one line per rod height > 0 (`crodht1..3`), length = W − LS − RS − 0.25, oversize multiplier
  above `#StdClosetRodlength`. Price depends on rod type text (2025: Round Polished Chrome 37, Syn Matte Gold 77).
- Filler: `#CostOfFiller = 17 × #MaterialCostGroup` (matches the review: 17).
- Kick: printed at 0 cost; base molding is priced per room by `BaseMolding.pcb`.
- Drawer boxes: by height, type text 8 (2025: 10" Melamine Undermount Match = 210); drawer fronts priced
  like doors (`#PriceDrawerFronts=Yes`), with `Add to DrFrt-<edgeband>` lines at 0.
- Options: `SO-Set option names.pcb` maps option numbers to names and costs; stiffeners 30 each, etc.
- Fees: `H-Discounts and Fees.pcb` → Extra Charge 01 = **Job Processing Fee, flat 199** (`#Sub1FlatCost=199`),
  `#Universalupcharge` 1.00, tax off, installation off, discounts off.
- Report: print order numbers from `A-SetUp` (left side 10, right 15, fixed shelves 20, adj 30, back 40,
  kick 50, doors 100, drawer fronts 110, drawer boxes 150, rods 190, fillers 245).
- Materials list `_<date> CFFL MATERIALS.Plt`: material name + multiplier per group, with a PROMO block.

What this means for the app: the price review can be **recomputed outside KCD** by interpreting these
scripts with the unit values above, or **cross-checked** by pasting KCD's own review. Prices change by
swapping the pricing folder, so the app should read the current `C:\KCD23-STDPLIST` at run time rather than
hard-coding numbers. A full interpreter is a real project; the per-part dimensions are available now.

## 5. Engineering workbook (confirmed on the template and on TILLIS HER CO.xlsm)

- Data Entry answers: B5 client number, B7 client name, B9 room, F1 designer, F3 cutlist prepared by,
  B1 installation date, F5 unit material, F7/F9 banding type/colour, F11 face type, F13 faces material,
  F19 construction type, F21 molding, F23 molding location, F25 notch for baseboard, B11 Costco, B13 jewelry
  tray, B15 hinge type, B17 V9/V23, B19 other special orders, B21 finishing, B23 specialty, B25 main closet,
  B27 sold-at price.
- Paste block from row 2: K price, L unit #, M part name, N depth, O (sometimes the height), P length.
- The workbook has VBA, ActiveX controls and external links: fill it only by writing cell values in place
  (Excel COM or surgical XML edits), never by re-saving with a library such as openpyxl.

## 6. Original versus engineered job (confirmed on TILLIS, BURNS, NOTIK pairs)

Same file format. Engineering changes: heading rewritten; one room per file (sidebar room may travel
along); unit ids renumbered 1..n; designer-only `890nc.cab` baseboards removed; custom hole panels,
garage platforms and obstructions added; wall notes added; material multiplier sometimes changed
(1.05 → 1.00); option pairs kept for the kept units.

## 7. Open points

- **Bottom drawer front of a drawer stack.** The stored slot (I45 on CSE304-96, I44 on CSE264) is the
  `.cab` default formula's result. The review prints something else: on one unit the face-fill remainder with
  three lower gaps (H-K-I53-I55-I41-I52-I42-I43-I44-3*I54 = 12 1/2 versus stored 12 3/8); on a unit with
  `No Kick Notch = 1` it was 2 5/8 more than stored (I45 + K + I52, as if the front covers the kick). The
  face height must come from the price script / `#Faces` geometry, not from the slot.
- **Door presence and door style per unit are not in the unit record at all.** Two CSE300-96 units in one job,
  one with a flatCFMirror door and one without, have byte-identical records apart from width, shelf count and
  the mesh slice. The style text appears only in the room's 9-slot style list and in `settings`. The header's
  opaque blob does not track doors either. Where KCD stores "this opening has a door of style N" is unknown;
  the mesh (drawing cache) does contain the door faces, so a fallback could detect doors from the unit's mesh
  slice. Best next step: have the owner save a tiny job twice, before and after adding one door, and diff.
- **Update Oct 13 (kcdcab.py):** the door and drawer faces, their sizes and whether a door is a pair now come
  from the `.cab` points and face rules (section 11). What is still unknown is the designer's **"no door"
  choice**: drawer towers (CSE304/305), tall shelving towers (CSE300-96, preset `Shelves 96.UNW`) and
  entertainment units (773-96) carry a top-door face in the `.cab`, the engineers' reviews show no door on
  them, and two CSE300-96 units of one job (BURNS HERS 9 with a mirror door, 12 without) differ only in
  width, shelf count, the mesh slice and the Int16 at byte 6 of the 86-byte block (1 on unit 9, 2 on unit
  12). That Int16 is 1 on every single-door unit and 2 on every pair, but also 2 on the door-less towers,
  so it is not the answer by itself. Until the A/B save experiment settles it, every door line the engine
  prints is flagged VERIFY.
- (earlier wording) **Door presence and door style per unit are not in any decoded field.** Non-zero I41..I46 do not mean a
  door; doored units exist whose cab has no door-height slot. Door count comes from the cab (`UIQ,36,...`
  rules, face rules such as `(I51=0)&(I254=0)`); the per-unit style name (for example `flatCFMirror`,
  entry 8 of the job's 9 door styles) was not found in the 86-byte block, the 10 bytes or the suffix.
- **Stale derived slots.** Slots whose cab default is a formula and whose state byte is 0 are results
  KCD computed; they can lag behind values typed later (seen: a typed reveal changed I44 after the review
  was printed). `kcdunits.Unit.is_computed()` marks them.
- L-shape scripts (ZC672 for C272-2opdoor; c271/772 neighbours in 2025/26 lists): back width W - 0.748,
  kick 32 13/16 on a 30 9/16 unit, shared panel printed under the L unit with the neighbour's panel
  omitted, neighbour kick W - 0.75. Needs the live scripts.
- Drawer-box depth looks capped at 24 (D = 36 printed as 24; 16 and 20 print as D). One data point.
- `DrFrt-...` lines appear only when the door type is `Melamine 2nd Material`; plain Melamine faces print
  only `Add to DrFrt`. Inferred from five rooms, not from a script.
- Quantity field: confirmed as a line multiplier on accessories and a filler; untested on multi-part units.
- Bytes 4..9 and 16..39 of the 86-byte block (byte 4 takes 0/30/60/90/120, 6 takes 0..2, 8 takes 0..6;
  neither is the door or drawer count), suffix Int16 at +4, the 28-byte handle floats: unknown.
- `.prt` part scripts are missing from the update zips; ask whether `C:\KCD23` on an engineering PC has them.
- Three jobs still do not parse (BARNARD SANDY note variant; LANGNAS GARAGE and SHOWRM PB "string past EOF").
- Newest library is `KCD23_Update_CFFL_ENGINEER_26-09-08.exe` on the Engineering SharePoint; not obtained.

## 9. Reader check against twelve engineered rooms (Oct 13, 2026)

`kcdunits.py` (the room-sheet reader) was run on twelve room files that also had the engineer's filled
workbook, and every pasted KCD price line (856 lines) was derived from the reader's values by independent
checkers. 800 lines (93.5 %) derive exactly. No line was traced to a wrong value, wrong unit or wrong label.
The misses: 14 lines from the unit quantity field (now read), 2 from door presence/style (not decodable yet),
14 from a job saved after its review was printed, 3 from accessory-library text, 1 engineer edit, 22 from
price-script formulas not known yet (section 7). Rules confirmed, usable as test oracles for the price engine:

- **Unit number** in the review = 1-based position among live units in file order (`Unit.seq`). Units whose
  pcb is `none` (obstructions, outlets, switches, lights, appliances, door openings) print nothing but keep
  their number. The review paste is sorted by unit number, then part name.
- **Rounding**: every printed size is the inch value rounded to the nearest 1/16 (`round(x*16)/16`, see
  `kcdunits.sixteenths`). Per-area prices (backs 9.00/sq ft) are computed on the rounded sizes.
- **Names**: material = Set Unit Info text 1 without the trailing multiplier; door type = text 2; edgeband =
  text 3; rod = text 4; kick = text 5; backing = text 7 with `#unitmaterialName` substituted; drawer box =
  text 8; contrast = text 12. Panels and shelves print as `<Part> - <material>-3/4"-<edgeband>`. Line cost =
  base price x material multiplier (text 1's last number).
- **Panels**: `Left Panel` D x H when LS > 0, `Right Panel` when RS > 0 (RS = 0 typed = shared with the
  neighbour, no line). L-corner cabs (271/272/172/c271/171) use I28/I29 (left/right side depth) as the
  panel depth. L-shapes with Show Backs print a `3rd Panel` H high (width W-RS or D-RS by variant). Custom
  panel units (T = 550) print exactly one panel, D x H; their I5/I7..I10 = 0.748 are not sides.
- **Euro shelves**: Top when TR > 0, Bottom when BR > 0, one Middle per non-zero I9/I21; D x (W-LS-RS).
  Drawer-stack cabs (ZC304/ZC305) print the middle shelf twice (`#addmidshelf=1` in the script).
  L-corner shelves are two pieces (I29 x (W-RS) and I28 x (D-LS) or mirrored).
- **Adjustable shelves**: count = I19 where the cab stores it, else I31; D x (W-LS-RS). Stand-alone shelf
  cabs (Csetsh, garageplatform) use D x W. Option 5 (stiffeners 1 side) adds one 30 line per adj shelf.
- **Rods**: one `Closet Rod <text 4>` per I251..I253 > 0, length W-LS-RS-0.25.
- **Kick**: `Kick <text 5>` when K > 0, length W, price 0 (bases are priced per room on the sheet).
  L-corner base kick = back width + 3.
- **Backs**: only when I121 Show Backs = 1; (W-LS-RS) x (H-TR-BR-K). ZC101 (stacked uppers) uses
  W-LS-RS-0.25 (the rod width left over in `#ShelfWidth`). Drawer stacks and the hamper use the top opening
  height I20 as the back height. L-corner backs: (D-LS-0.75) or (W-LS-0.75) by variant.
- **Doors and drawer fronts**: width (W - I56 - I57) / number of doors; full-height door H-K-I53-I55;
  drawer fronts from I42.. (CSE304), I41.. (CSE263/264), I42..I46 (CSE305); the bottom front is the
  unresolved case in section 7. Drawer boxes: `Drawer Box-<front height>"-<text 8>`, D x (W-LS-RS).
- **Fillers**: `Filler-<material>`, W only, 17 x multiplier. **Options**: one `Opt-<name>` per settings pair,
  name from options.dat (code + 1). **Accessories** (T = 1000): `RM1 <category>`, once per quantity.
- **Sidebar counts are not reliable** (rod and base quantities disagreed with the file in several rooms).
- **Totals**: in a full room the pasted prices sum to the Final Price Sheet subtotal; plus the accessory
  rows (BASE/CROWN quantity x price) they give the Standard Price. Change-order rooms do not reconcile.
- **Test-data lesson**: a change-order room keeps only the remade parts, and a job saved after the review
  (unit numbers or typed reveals changed) cannot be matched. Verification rooms must be full rooms with the
  review printed from the same save.

## 10. Price engine `kcdprice.py` (Oct 13, 2026, first version)

An interpreter for the price-list scripts, written from the language spec that ten readers built from the
Sept 2024 CFFL list (827 files) and then had checked. It runs `A-SetUp.Pcb` once, then per unit
`xxbefore.pcb`, the unit's own script (from the job record's pcb field) and `XXAfter.PCB`, then `Xxend.pcb`
and `XXFinal.PCB`. Values are stored as text and resolved when used; `[ ]` evaluates at once; `{ }` prints a
dimension in sixteenths; `Price` emits a line and option lines come from `options.dat` through
`PriceOptions`. Units whose pcb is `none` print nothing. Everything doubtful goes to `Engine.flags`.

Checked with the **Sept 2024** scripts (the only list in the sandbox) against ten rooms priced in 2026, names
and sizes only (`experiments/compare_keys.py`): about 69 % of the pasted lines come out identical in name,
size and count. The rest, in order of size:
- (superseded by section 11) doors and drawer fronts now come from the `.cab` face geometry;
- 2026 script changes: `Drawer Box-10"-…` name order, `Add to DrFrt` printed with height only, pullout tray
  names, accessory names (`RM1 1 Shelf Strip LED`), kick and filler printed with one dimension;
- accessory libraries (TAG racks, lighting) missing from the sandbox;
- which review column (depth / height / length) a script dimension lands in is not derivable from the 2024
  scripts; the live scripts and one real UNIT PRICE REVIEW printout will settle it.
Run: `python kcdprice.py --lib C:\KCD23 --pricelist "C:\KCD23-STDPLIST\_26-08-03 AUG CFFL PRICING" JOB.job`.

**Layered price lists and the price check (Oct 13, 2026, late).** `kcdprice.Engine` now takes one folder or a
list of folders; a later folder's file replaces an earlier one with the same name (`--pricelist` can be repeated
on the command line), so a monthly update pack can be laid over the last full list. `experiments/compare_keys.py`
pairs every matched line with its engine line and compares the pasted price with the engine's cost (half a
dollar of slack for whole-dollar pastes, one cent when the paste shows cents), printing `PRICES:` per room and a
`TOTAL PRICES:` line. Results of the runs over the monthly folders: see section 12.

## 11. Face geometry `kcdcab.py` (Oct 13, 2026)

The `.cab` file holds more than the size table: after `#Sizes` come `#Extra Variables` (`E,n,formula` extra
values, `U/UI/UIQ,n,formula` rules that rewrite a size), `#Pts` (numbered points whose X, Y, Z are formulas of
W H D LS RS MS TR MR BR K LF RF FW, the `I<n>` sizes, `E<n>` and shop sizes such as `SBDG`), `#Faces` (one
line per drawn face: `[(cond):]type, draw-order, colour, npts, p1..pn, name`) and load statements for
`.cld` includes. Doors and drawer fronts are faces whose 8-digit type starts with 1 or 2 (door), 3
(drawer front) or 0 (open face); digits 4-5 are the face number n that the price scripts see as `Dn`
(`D1W`, `D1H`, `D1T`, `D1DR`, `D1HG`, `Set,#Door=D1`). A face line can be conditional (`(I20>0)&(ms=0):`,
`(I254=0)&(I152<>1)`), which is how `.cab` files turn doors into openings.

`kcdcab.py` parses the whole file (`parse_cab_full`), evaluates the formula language (`ExprEval`: arithmetic
with `\` `%` `^`, comparisons, `&` `|`, `(cond):a:b`, `abs int sqrt round`) and builds the faces of a unit
from its stored sizes (`UnitFaces`): width = X extent, height = Z extent of the face's points. Checked
against the engineers' reviews: every door and drawer front the reviews show comes out to the sixteenth
(GARAGE: six door units, HIS, TILLIS HIS, OFFICE drawer fronts, the bottom drawer front that the slot got
wrong by 1/8). Two rules learned from the reviews: a door face wider than about 27" is printed as a pair,
each door exactly half the face width (the pair gap is not subtracted); the Int16 at byte 6 of the unit's
86-byte block is 1 on single-door units and 2 on pairs and is used as the hint, the width only as fallback.
The price engine uses this when the full library text is loaded (`Catalog.from_library_root`, or
`Catalog.load_rawlib_json` for the bundle made by `rawlib.py` on the laptop); otherwise it falls back to
the old slot-based drawer-front model.

Result with the Sept 2024 scripts on twelve rooms: 614 of 856 pasted lines identical (71.7 %), up from 69 %.
What remains, by size: doors the designer removed (section 7, 27 lines); CO rooms whose paste holds only the
changed units; accessory names from libraries not in the sandbox (`CFClosetAccessory.pcb` prints
`RM1 <name>` from a per-file table, the 2026 lists print the unit's category); 2026 script wording (pullout
trays, `Add to DrFrt` dims); the review column question (section 10).

Also learned: KCD trims the result of `Left`/`Right` (the contrast-material mark-up prints as `1.00`, not
` 1.00`); `Set Unit Info` text 12 is `<name>  1 <multiplier>` and text 15 the door insert type.

## 12. Run with the shop's library and the May 2026 list (Oct 13, 2026)

The owner copied the shop's `C:\KCD23` (with `STDPLIST`) to the OneDrive folder `me and claude`. The
Microsoft 365 connector lists the folders but refuses to open `.pcb` and `.cab` files (binary type), so the
files were read on the test laptop, where OneDrive syncs them.

OneDrive on the laptop:
- Synced files start as placeholders (Files On Demand, attribute `O`). Python `open()`/`os.stat` fail with
  `[Errno 22] Invalid argument`, Desktop Commander `read_file` fails, `Copy-Item` says "The cloud operation
  was unsuccessful".
- `attrib +P -U "<folder>\*" /S /D` marks a folder "Always keep on this device" and OneDrive downloads it
  (a few minutes per thousand files). `attrib -P +U` on the image masks (`*.bmp *.jpg ...`) frees them again.
- Globbing the whole tree on OneDrive stalls. Robocopy the text files to a local folder first: unit
  libraries to `%TEMP%\kcdlibod\<folder>` (masks `*.cab *.cld *.mld *.lst *.dat *.unw *.csv *.txt *.prt
  *.plt`), the price list to `%TEMP%\kcdprice\MAY26`.

Price lists in `STDPLIST`: `_26-03-03 MAR`, `_26-04-03 APR` and `_26-05-03 MAY CFFL PRICING` are the same
size (1033 files, 5,753,907 bytes, with a `ZTag FILES\` subfolder). `_26-08-03 AUG CFFL PRICING` is the
current list, but only 203 of its files had synced when this was written; rerun with it when the upload is
complete. Changes since 2024/2025: the 4249-line `CFClosetAccessory.pcb` table is gone; accessories are
priced by `ClosetAccessories.pcb` (a 199-byte stub) with `CF Accessories.csv`, `CF Lighting.csv`,
`New Closet Accessories.csv` and the TAG csv files.

Unit libraries beside `NEW CFFL UNIT LIBRARY` (2271 text files): `CF Accessories` (433), `TAG Hardware
Closet Accessories` (890), `Lighting Accessories` (435), `Closet Accessories` (488), `Room Accessories`
(181), `TAG Closet Accessories - NEW PALETTE 2026` (441). `Catalog.from_library_root` reads them all and
takes `options.dat` and `Sizes.Lst` from the main library.

Result (`runcmp2.py cmp_may26`, 19 rooms, 1067 pasted lines): **765 identical (71.7 %)**, and **769 (72.1 %)**
after the Name/Code fix below (`cmp_may26b`); the Sept 2024 list on 12 of those rooms gave 614 of 856. Rooms: GARAGE 58/83 (every door now to the sixteenth except one
17 9/16 against 17 1/2), GARAGE CO 9/9, TILLIS HIS 88/106, BURNS 98/127, HIS 118/160, OFFICE 45/98,
PANTRY 53/82, HER CO 23/30, WIC CO 33/60.

What still differs, by size:
- door lines the engine prints and the paste lacks (drawer towers `CSE304/305`, shelving towers
  `CSE300-96`, entertainment units `773-96` and `772`, `CSE101stacked`): the designer's "no door" choice
  is still not found in the record (section 7), so every engine door line stays VERIFY;
- accessory units printed `call for quote` because the engine had KCD's Name and Code swapped (section 2.1);
  fixed the same evening (see "How accessories are priced" below): valet and belt racks, jewelry trays, LED
  strips, hampers now print with KCD's wording, part number and cost (`RM1 14in Elite Valet Rack BLK
  808.71.503` 105, `RM1 1 Shelf Strip LED` 130, `RM1 Valet CR` 65, `RM1 18in Tilt Out 1 Lg Bag 547.43.311` 186);
- door style names: KCD prints `flatCFMirror Door-...` (BURNS 9) and `Framed Door-Melamine-...-Mirror-...`
  (HIS 21) where the engine prints a plain `Door-Melamine-...`, and `Framed Door-...-Clear Glass-...` for the
  glass pair HIS 11. In the 2026 list `#Codedoor` (the door style name) and `#IncludeInsert` are KCD built-ins
  that the scripts never set (`A-SetUp` only zeroes `#IncludeInsert`; `AA-User` sets `#DoorDrawerType` from
  text 2 and `#DoorDrawerInsertType` from text 15). Where the unit stores its style is still unknown: the
  mirror-door unit BURNS 9 and the plain-door unit BURNS 12 (same `.cab`, same texts, no options) differ only
  in width, shelf count, mesh and the Int16 at byte 6 of the 86-byte block; the 10-byte block and the suffix
  are identical; the `.cab` face codes are `10101000`/`10102000` for every door, so the style is not in the
  library either. The room's nine door-style names (settings) hold the candidates (`Mirror` or `flatCFMirror`
  in slot 8). Until this is found, every door line stays VERIFY and style/insert words are not printed;
- L-shaped cabs (`C271`, `C272`, `C171`, `CSE101stacked`): the "3rd panel" and back dimensions come out
  swapped against the paste and four adj shelves are missing (their points use the shop size `sctovlp` and
  extra values `e5`/`e6` that live in `.cld` load blocks, both unmapped);
- PANTRY pullout tray wording (`...included 6 1/4"-lino cancun grain16` pasted, `...grain` from the
  engine) and the OFFICE unit 5 drawer-front count;
- kick, filler, leg-leveler and mirror-back column placement (section 10), and the CO rooms whose pastes
  the engineers edited by hand.

**The Int16 at byte 6 of the 86-byte block (`a3`), surveyed on six rooms (Oct 13, 2026).** 0 on units without
door faces (fillers, shelves, accessories, single hang, backing); 1 on single-door units (BURNS 9 and HIS 21
mirror doors, GARAGE 15/17 plain uppers, HIS 6 23" tall 2-opening, PANTRY 772-96 at 25", the L-corner units
271/272/172) and also on every `Hangdbls` double hang (no doors); 2 on wide units whose reviews show pairs
(GARAGE 4/5/8 at 35", upper hutch 760-1 at 37.5", HIS 11 at 34") and on every drawer tower (CSE305/CSE304/
CSE265, 28" to 37.5"), but also on narrow towers whose reviews show no door at all (ELLA 3 and BURNS 12 at
18", HIS 25 773-96 at 20.5") and on HIS 3 (CSE301, 23", review shows one door 22 7/8 x 25 1/8 = the drawer
opening turned into a hamper door, no door on the top opening). So `a3 = 2` is "pair" where a door exists,
but it does not say whether the door exists; the A/B save experiment (section 7) is still the way to settle
"no door" and the door style.

**Pullout trays (`ZC260-Pullout.Pcb`).** `Price,...,RM#Roomnum #showponame #showpofacename #H"-#unitmaterialname,
cost, D, W, order`: the engine prints `Under Mt Pullout Tray w Lino Cancun Grain Melamine Drawer Face included
6 1/4"-Lino Cancun Grain` with dims 16 x 23 3/4; the pasted review has the same words with `16` glued to the
end of the name and only 23 3/4 in the dimension columns. Treat it as a paste quirk until a real printout
shows where the depth lands.

**What the KCD23 root holds (Oct 13, 2026, from the OneDrive copy of the shop PC).** `Start.Dat` is KCD's
start-up data: the nine door-style slots of a job are `1 Top Door, 2 Base Door, 3 Drawer Front, 4..9 Extra Door
4..9` (shop defaults flat-VG, flat-VG, flat-HG, flat-VG, SFP, SGP, SMP, BEVEL, SRP); a job's own list can
differ (`FLAT, FLAT, FLAT, FLAT, Sgp, Smp, Bevel, Mirror|flatCFMirror, Sfp`), so a mirror door is "Extra Door 8"
of the room. Which door number a unit's face uses is still not found in the record. The pricing-list
descriptors live in the root, one `.Pbs` per `STDPLIST` folder (`_26-08-03 AUG CFFL PRICING.Pbs` and the
others are identical: `Pricing Library V8.2 June 11, 2025 release`, `PlistType=Closet`, `REPORTID=W`), with a
`.Plt` materials list and a `.pcs` countertop list per month; `PlistChoice.Dat` names the materials list in
use (`CFFL MATERIALS`), not the price list; `KCD.log` does not log the price list either. The report
definitions are there too: `_ENGINEERING PRICING.Rpr` (Oct 2024), `_ENGINEERING PRICING V9.Rpr`,
`Unit Price Review.Rpr`, `NEW Unit Price Review.Rpr`, plus the stock KCD reports. `_ENGINEERING PRICING.Rpr`
prints the UNIT PRICE REVIEW with one group: `Sort (-Unit)(-name)`, `Print Group (Cost @ 0)(Unit @ 8)
(Name @ 13)(Width @ 90)(Length @ -110)`, header `Unit # | Name | Depth/Width | Height/Length | Cost`. So KCD
prints exactly two dimension columns, dim1 under Depth/Width and dim2 under Height/Length, for every line; the
pastes that show one dimension for kicks (`w, K`), fillers (`w, h`), leg levelers (`w, H`), mirror backs (`w, h`)
and `Add to DrFrt` (`#DrawerFrontHeight, #DrawerFrontWidth`) keep dim1 and drop dim2, which the report itself
does not do; a real printout or export will show whether that is KCD or the engineers' hand. `System\
Maintenance\MaintenanceList.dat` is the KCD program updater, not the price-list updater.

**Monthly price folders are not all full.** Files per `STDPLIST` folder: `_25-09-02 SEP` 1228 (5.3 MB),
`_25-10-02 OCT` 738 (1.4 MB), `_25-12-11 DEC` 347, `_26-01-08 JAN` 349, `_26-02-02 FEB` 713 (5.3 MB),
`_26-03-18 MAR` 1025, `_26-04-02 APR` 1024, `_26-05-03 MAY` 1033, `_26-05-22 MAY` 288 (0.2 MB), `_26-07-07 JUL`
197 (46 KB: `cfcountoptionsroom11`, `GetDrawerBoxCost`, `Z171`, `Z564`, `Zc601-ld` + `ZTag FILES`), `_26-08-03
AUG` 203 (43 KB: 11 scripts + `ZTag FILES`). The owner confirmed the shop PC uses this same KCD23 tree and that
updates land in it. Whether KCD fills a short folder from an earlier list is unknown; the engine now accepts
several folders layered in date order so both readings can be tested against the pasted prices.

**Prices, not just names (Oct 14, 2026).** The first price comparison (`compare_keys.py` PRICES lines) over the
same 19 rooms, 769 matched lines:

| price folders | lines with the same price | note |
|---|---|---|
| `_26-05-03 MAY` alone | 561 of 769 | NOTIK rooms 553 of 561 lines; TILLIS and BURNS rooms mostly off by 1 or 2 |
| MAY + `_26-05-22 MAY` + JUL + AUG packs | 560 of 768 | same prices as MAY alone; the packs change nothing these rooms use (one HIS name changes) |
| SEP 2025 to AUG 2026, all eleven folders layered | 560 of 768 | identical to the line above |
| `_26-03-18 MAR` alone | 489 of 769 | March prices are lower: NOTIK was not priced on March |
| `_25-09-02 SEP` alone | 65 of 162 | the September 2025 folder is itself partial (762 root files), many costs come out 0 |
| `_26-05-03 MAY` alone, after the wall-contact fix below | 568 of 769 | **every NOTIK line now has the pasted price except four cent-level roundings** |

What the differences are:
- the thirteen NOTIK rooms (engineered May to August 2026) match the May 2026 list to the cent except (a)
  **17 dollars** missing from a left or right panel whose unit stands against a wall (`#PanelTouchingWallCost`,
  KCD's built-ins `ul`/`ur`): 2ND LIN unit 2, ARI 7, CABANA 2, ELLA 3 and 4, GUEST 3, MST LIN 2; the engine
  had `ul = ur = 0`. Fixed the same night from the wall record (wall length = Int32 at byte 20 of the 205-byte
  wall record, neighbouring wall ids at 36 and 40; a unit at X = 0, or ending at the wall length, with a wall
  meeting that end, touches it); and (b) a few 2 to 4 cent rounding differences on backs and platform shelves
  (`back-melamine match` 221.92 vs 221.95, 306.54 vs 306.58, 210.94 vs 210.96; `adj shelf ... platform` 71.76
  vs 71.74): KCD rounds somewhere in the area formula where the engine does not; still open.
- the TILLIS rooms and BURNS HERS were priced on a list we do not have a copy of: shelves 46 and 50 where
  every list on hand gives 45 and 49, panels 185 and 229 against 183/227 (March to August 2026), 180/224
  (February 2026) and 179/222 (June 2025 to January 2026); corner-unit shelves 75/71/108/488 against
  74/70/106/486. Tested: June 2025 alone, June 2025 with the September, October, December, January and February
  packs on top, March alone, May alone, May with its packs. The 2026 lists all have `#panelpricemultiplier`,
  `#shelfpricemultiplier` and `#Universalupcharge` at 1.00 and `#PanelTouchingWallCost` 17, and no single
  multiplier turns the engine's numbers into the pasted ones. BURNS was engineered in August 2026 and TILLIS
  rooms are change orders, so the owner's rule (a job is priced on the list in force when it was sold) is the
  likely reason; the owner has to say which list those two jobs were priced on, or hand over that folder.
- the materials list `.Plt` has two blocks: regular (`White Coast Oak Grain  1 1.35`, `Lino Cancun Grain  1
  1.35`, `Black Matte  1 2.50`) and `PROMO` (the same names at `1 1.00`); a unit's text 1 stores the entry the
  designer picked, which is why these jobs price at multiplier 1.00 (promo) or 2.50 (Black Matte).

**How accessories are priced in 2025/2026 lists (confirmed from the May 2026 `Eachunit.pcb`,
`Eachunit2.pcb` and csv files).** A unit whose pcb file is missing from the list runs `Eachunit.pcb`. When the
unit library name matches `Tag *`, `*Access*` or `*Light*` it loads `Eachunit2.pcb`, which picks a csv by
library (`Tag Hardware Closet Accessories.csv`, `Tag Hardware Engage Collection.csv`, ... , `CF Accessories.csv`
for `CF Accessories` and `Closet Accessories`, `CF Lighting.csv` for `CF Lighting` and `Lighting Accessories`),
looks the unit's `#Name` up in column 1 (`ReadCsvValue,<csv>,#Name,#tagcode,#TemptotalunitCost`) and prints
`Price,1, RM#roomnum #Name #tagcodeoutput, cost × #universalupcharge, w, h, d` (the part number is blank when
the csv says `NA` or `Skip`; `d` lands in the print-order field, so the review shows width and height only).
A name not in the csv leaves `#tagcode` at `Does Not Exist` and `Eachunit.pcb` prints `RM<n> <name> -
!*!*!*CALL FOR QUOTE*!*!*!` at print order 261. Example rows: `Valet CR,NA,65`, `JT Valet,NA,175`,
`1 Shelf Strip LED,NA,130`, `12in Elite Valet Rack MG,808.71.001,95`. The `ZTag FILES\Zkcd<code>.pcb` stubs
(200 in the May list) only `load` a cost script (`K-Pant Racks Costs.PCB`, `L-Laundry Costs.PCB`, `P-Elite Hooks
and Holders.pcb`); `ZRoundPoleMNL.pcb` loads `TAG-USES SET UNIT INFO.pcb`, which prints `#Name #Code See Unit
for Toestop pricing` at 0.

**The `_26-08-03 AUG CFFL PRICING` folder is not a full list.** It holds 203 files (42 KB): 11 top-level
scripts (`cfcountoptionsroom11.pcb`, `GetContrastMaterialCostGroup.pcb`, `N-TAG Trackwall System.pcb`,
`Z1118.pcb`, `Z409-dr.PCB`, `Z492.pcb`, `Z599.pcb`, `Z775.pcb`, `ZC304hd.Pcb`, `Zcse-300c.pcb`,
`ZRoundPoleMNL.pcb`) and a `ZTag FILES\` set; no `A-SetUp.Pcb`. `_26-05-22 MAY` (288 files) and `_26-07-07 JUL`
(197 files, 46 KB) look the same. They are update packs laid over a full list, or incomplete copies; the owner
has to say which folder the shop's KCD points at. Full lists on hand: `_26-03-18 MAR` (1025 files),
`_26-04-02 APR` (1024), `_26-05-03 MAY` (1033); older full lists back to `_25-09-02 SEP` are in the same
`STDPLIST` copy. No `.Pbs` file sits in the May folder or the `STDPLIST` root.

## 13. The ten job sets (Oct 14, 2026)

The owner put ten complete job sets in `me and claude` (GODDARD, PRIEM, POLONSKA, SFERRA, BINDLER, MIRANDA,
HUMPHREY, PARINI, ROBERTS, LONG). Copies on the laptop: `%TEMP%\kcdjobs10\<job>` (92 files, all pinned and
downloaded); the pasted workbook lines are in `out\keys10.txt` (1175 lines over 12 rooms), the file survey in
`out\survey10.txt`.

### 13.1 What a set holds

| Prefix | File | What it is |
|---|---|---|
| `[1 DESIGN]` | `<designer's name>.job` | the designer's job as sold (every room; heading often empty) |
| `[2 CO]` | `... Change Order*.pdf` | scan: the change-order contract page (reason, price change, items added/removed, notes) plus the revised KCD printouts |
| `[3 REM]` | `REM-<job>-<NAME>.pdf` | scan of the remeasure (see 13.4) |
| `[4 CSV]` | `<job> <ROOM>.csv` | the cut-list part export of the engineered room (File Name, Part Name, Width, Length, Thickness, Material name, Unit Number, Quantity, allow to rotate, Part Mirrored ... 23 columns, mm) |
| `[4 ENG ROOM]` | `<job> <ROOM>.job` | the engineered room file (one room, heading filled in, engineer's name in line 5) |
| `[4 ENG]` | `ENG <job>.pdf` | scans of the engineering forms (see 13.5) |
| `[4 NEST]` | `<job> <ROOM>.pdf` | Cut Rite Modular nesting patterns (text, one page per board) |
| `[5-6 WORKBOOK+UPR]` | `<job> <ROOM>.xlsm` | the filled workbook with the UNIT PRICE REVIEW paste in K..P |

The REM, CO and ENG pdfs are images (Genius Scan); they were rendered to `out\rem\*.jpg` (`rempng.py`, `rem2jpg.py`)
and read through Desktop Commander `read_file`, which returns images.

### 13.2 Engine against the twelve pasted rooms (May 2026 list + May 22, July and August packs)

After the 1/16" rounding of 13.3 (`runcmp4.py cmp10_r16 ...`, output `out\cmp10_r16.txt`):

| Room | pasted lines | exact name+size | prices same / matched |
|---|---|---|---|
| GODDARD MASTER | 201 | 133 | 133 / 133 |
| PRIEM OFFICE | 47 | 28 | 28 / 28 |
| POLONSKA WIC | 297 | 203 | 199 / 203 (4 backs off by 2 to 5 cents) |
| SFERRA GARAGE | 181 | 125 | 125 / 125 |
| BINDLER PANTRY | 72 | 35 | 35 / 35 |
| MIRANDA OFFICE | 101 | 69 | 67 / 69 (1 back off by 4 cents; unit 29 panel 294 vs 311, see below) |
| HUMPHREY WIC | 72 | 8 | 8 / 8 (paste from another version, see below) |
| PARINI WALLBED | 6 | 1 | 1 / 1 (wall bed: doors not priced yet) |
| ROBERTS RIC | 30 | 18 | 18 / 18 |
| ROBERTS WIC | 48 | 33 | 33 / 33 |
| LONG AUSTIN | 60 | 42 | 42 / 42 (was 40: the two connecting shelves of 13.3) |
| LONG DANI | 60 | 42 | 42 / 42 |
| **total** | **1175** | **737 (62.7%)** | **731 / 737** |

The 19 older rooms (NOTIK, TILLIS, BURNS) with the same engine: 768 of 1067 exact (unchanged), every NOTIK line
prices the same except the GARAGE platform shelf (142.26 against 142.24); TILLIS and BURNS still carry the
2025 prices (section 12). `out\cmp19_r16.txt`.

**Which file the paste comes from.** In eleven rooms the paste's unit numbers are the engineered room file's,
so the engineers paste the UNIT PRICE REVIEW of the engineered file (or of the version just before it). HUMPHREY
is the exception: the paste has 9 units with 34 5/8" openings, the design file and the engineered file both have
8 units with 33 13/16" / 33 7/8" / 39" openings and are identical, so that paste was made from a version that is
not in the set. The design files are not what was pasted: GODDARD's design holds 59 units (accessories and
all), the engineered room 42; POLONSKA 87 (two rooms) against 61; the engineers add fillers, backing, outlets
and panels. For the app: price the engineered room file, and when a workbook paste exists compare and flag.

**MIRANDA unit 29** (`Custom Panel Left-stacked.cab`, a 1 1/2" panel the engineer added at the right end of wall
1, X + W = wall length, wall 3 meets that end): the engine adds the 17 wall-contact charge (311), the paste has
294. The design file has no such unit. Either KCD's `ur` is stricter than "ends at the wall length with a wall
meeting that end" (the filler next to it, unit 30, overlaps it by 3/4") or the file was changed after the paste.
Ask the engineer; keep the rule.

### 13.3 KCD rounds sizes to 1/16" before the scripts see them (fixed)

LONG AUSTIN units 1 and 3 (`Csetbot.cab`, bottom connecting shelf 16 x 20) priced 140.60 instead of 46.55. The
trace (`traceunit.py ENG AUSTIN 1 ...`) showed `#CostOfHorizontal = #ShelfCost1BB`: the double-thick shelf grid
(`C-Shelf Cost Double Thick shelves.pcb`, loaded by `C-Shelf Cost.Pcb:950` when `#shelfTH > #ShelfThickA`).
The shelf's thickness slot holds 195 (19.5 mm = 0.768"), which is more than .75, but KCD priced it as a 3/4"
shelf: KCD hands the scripts sizes rounded to the nearest 1/16" (the fraction it displays everywhere). The engine
now rounds every size builtin and every I-slot size that way (`round16` in `kcdprice.set_unit`) and the face
sizes from `kcdcab` too. That also removed the cent-level back differences of section 12 (backs are priced by
area): NOTIK went from 4 cent-level differences to 1, the new rooms from 36 price differences to 6.

### 13.4 The remeasure (format of the scans)

- Page 1: the Salesforce order printout (order number, client, address, phone, sale date, total job, designer),
  with the appointment window, date and rem tech written on top, the "RE-MEASURE REQUEST" box (scheduled, done
  by, needs re-design yes/no, new signature yes/no), "ONE SPACE", a "completed" stamp and notes ("waiting on
  windows to dry in for drywall 2 weeks", "LED form signature").
- Page 2 (GODDARD): the CF "REMEASURE CHECKLIST" form: rem tech (Drew / Kevin / Keyan / Gary / Brian), width of
  all walls (on plans), ceiling height lowest point, slanted ceiling, soffit (height, depth), baseboard
  (wood/tile/other, size), door type (bifold/bipass/swing in/out, quantity), door width/height incl. trim, bifold
  size, closet header (height), floor type, window, outlet/switches/lights, attic/AC vent, plumbing fixtures,
  other obstructions.
- Then the designer's KCD floor plan and elevations with the measured wall lengths written in circles next to the
  drawn ones (GODDARD: #5 163 9/16 -> 162 5/8, #6 90 3/4 -> 88 7/8, #7 90 3/4 -> 89 1/8, #8 163 9/16 -> 162 1/8;
  HUMPHREY: #1 145 -> 144 3/8, #4 39 -> 38 3/4, #5 35 -> 34 3/16; PRIEM: 166 -> 165 3/4, 57 1/4 -> 57 1/8),
  outlet positions on the elevation, and a short legend: CH (ceiling height), BB (baseboard, e.g. "5 1/2 W" =
  wood), Fl (floor: tile, carpet), DH (door height), crown, header.
- For the app: handwriting; an OCR will not be reliable. Build a remeasure entry screen pre-filled with the KCD
  wall lengths and heights so the tech or engineer only types the measured numbers and the checklist answers.

### 13.5 The engineering forms (ENG pdf of PRIEM)

- The pricing summary sheet: client, designer, standard price 7,175.27, sold at 6,963.00, 97% of standard;
  common accessories (BASE: TH DECORATIVE 2 x 145, CROWN: TH DECORATIVE 2 x 185, CTOP: ARCTIC WHITE 14 9/16 x 88);
  subtotal 5,034.77, accessories 1,941.50, processing fee 199. (These are the workbook's own numbers.)
- The **Doormark Inc. door order form** (thermofoil doors): company code CFJ, customer 7474, PO = job + name +
  room, door design PAL (Palm Beach), color FWM, match back, door lines (style, qty, width, height, hinge side
  L/R: PAL 2 10.8125 x 25.1250), drawer fronts (style slab/RR, qty 4, 33.5000 x 12.5000), mullion doors, slab
  fillers, laminate/foil, molding (REN 2, BAS 2). The sizes on the form are not the KCD door sizes (the paste
  has `Door-Palm Beach TH 10 1/2` and `DrFrt 33 7/8`): the engineers apply the vendor's sizing rules; ask.
- The **purchase order**: room, qty, item, description, vendor (OFFICE 2 DOOR 110.93.461 HAFELE; OFFICE 4 DRAWER
  110.93.461 HAFELE), engineer's name, install date.

### 13.6 Name and size misses, by cause (438 of 1175 lines)

1. **Door style and insert.** The paste names doors `Framed Door-Melamine-Roble Aurora Grain-Clear Glass-...`,
   `Door-B CF 5-Piece Dering Forest Grain w Dering Forest Grain Insert-...`, `Door-Palm Beach TH-White 1 mm`,
   plus `Lift-Up Door Hinge` lines; the engine prints the plain `Door-Melamine-...` or `No Color Selected or
   Invalid Size - call for quote`. The style sits in the unit's Set Unit Info texts: text 2 = door type
   (`#DoorDrawerType`), text 14 = finishing (`#DoorDrawerFinishingType`), text 15 = insert
   (`#DoorDrawerInsertType`, "Clear Glass" on GODDARD unit 14, "None" elsewhere). The engine runs
   `GetDoorStyleCost.pcb` (finishing and insert cost files) but the framed / 5-piece / thermofoil branches are not
   validated yet. Most of POLONSKA's 71 and MIRANDA's 23 key-only lines are these.
2. **Drawer or door on the 774 tall units** (LONG AUSTIN 2, LONG DANI 9, ROBERTS WIC 7): the engine prints four
   doors, the paste two doors plus two `Drawer Box-8 3/4"` and `Add to DrFrt` lines (and the engine's extra middle
   shelf goes with it: `Pricefixedshelves.pcb:172` prints spanner shelves between drawers). `774.cab`
   ("ENTERTAINMENT 4 VERT OP") defines every face as a door (`10101000`, `2020n000`); the drawer choice is not in
   any field we parse: not in the 86-byte block (bytes 68..85 are 0 and 190 on every unit), the 10 bytes, the
   27-byte suffix, the 15 texts or the prefix slots. The unit was placed from the saved unit
   `NEW CFFL UNIT LIBRARY\Shelves 2 Drawer 96.UNW` (the record's `unw` string); a `.UNW` is one unit record in the
   job layout ([Version] 10.090, [Loc Size], [Walls], [Units] with the 1806-byte prefix, strings, 86 bytes, texts,
   [Notes], [Use Shop Stds], [Custom Units]). Needs the save experiment (section 7): the same 774 saved with
   openings 3 and 4 as drawers, as doors, and as open.
3. **Doors the engine prints where the paste has none** (SFERRA 12/29/32, BINDLER 2/11/14/16, ROBERTS RIC 2/4/5,
   ROBERTS WIC 5, PRIEM 4/5/7): the "is there a door" question of section 12. Byte 6 of the block does not settle
   it (ROBERTS WIC 5 has 1 and no door in the paste).
4. **One-dimension lines** (kicks `w, K`, fillers, leg levelers, add-to-drfrt): counted as "same name, other
   dims", 280 lines; not a pricing problem.
5. **Engineer edits after the paste**: left/right panel swapped (POLONSKA 22/23 and 43/44), MIRANDA 2 (drawer
   box in the paste, `Opt-Top Drawer Box to Shelf` + pullout shelf in the file), MIRANDA 3 back material (paste
   designer white, file roble aurora), GODDARD 1 and 8 `Shoe Shelf ... x10` (the engine prints none for
   `shoeshelf-d-match.cab`: unknown i20/i52/i58), PARINI wall-bed doors.
6. Small naming: `14in Elite Tie Rack MNL 807.67.603` (paste) against `... 310.3000.14.mnl(807.67.603)` (engine);
   PRIEM `Opt-3 Hole Adjustable Custom` printed by the engine on 772 units but not in the paste.

### 13.7 Open asks for the owner (added to section 7's list)

- The 774 save experiment above (drawers / doors / open), and one unit saved with and without a door.
- Which rules turn KCD door sizes into Doormark order sizes (10 1/2 -> 10.8125, 33 7/8 -> 33.5 x 12.5).
- Why MIRANDA's end panel (unit 29) was not charged the wall contact.
- The HUMPHREY file the paste was made from (to confirm the "paste = engineered file" rule).

## 14. Walls and the remeasure (Oct 19, 2026)

The owner's question: can the handwritten remeasure, once read by his Grok pipeline, be applied to the
designer's job (wall lengths first, then grow or shrink the sections)? Short answer: the wall part is built
(`kcdwalls.py`), the first test files went to the owner for a KCD round trip, and the section part is a set of
rules with evidence plus one safe automatic step (end fillers).

### 14.1 The Grok read-out

`C:\GROK REM COMPLETED\<job>.json` (pipeline rules in `PASS_RULES.md` and
`Documents\CF_QC\remeasure-multiagent\START_HERE.md`): three Grok readers read crops of the scanned pages; a
value is `consensus` only when all three agree, otherwise `needs_review`. Labels for walls carry KCD's own
wall number and the printed length: `"Linen #7 (printed 25 1/4)" -> "25 1/8"`. Room facts: `H` ceiling height,
`HO`/`HD` header or door height, `BB` baseboard (`5 3/4 x 3/4 W`), `F` floor, `Door`, `Molding`, `HOLES`.
COYNE (1093610): 12 agreed walls over Linen/Guest/Primary, wall #15 in review, 17 facts. WERNER (1089471): the
designer drew one wall (#1 198) and the tech sketched two side walls ("wall A", "wall B") that are not in
the job, and the 205 1/8 is labelled by the room name, not `#1`: that read-out needs an engineer; the tool
flags "a length for the room without a wall number". Ask the pipeline owner to always label a wall value by
its printed `#n` when one is next to it.

### 14.2 The 205-byte wall record (decoded; `kcdwalls.py`, self-test `experiments/walls_selftest.py`)

Checked on all 178 wall records of the ten sets (120 live, 58 dead). Units 0.1 mm (254 = 1"), T = 1143 =
4 1/2" wall thickness.

| Offset | Field |
|---|---|
| 0-15 | preamble: first record of a file carries a list header (38494, 102/119/136, a per-save number, 7646); other records 0 except byte 11 = 1 and a byte-15 flag (unknown, follows the record slot) |
| 16 | float32 direction angle of START->END in degrees x 254 (0, 90, 180, 220, 270, 360 seen) |
| 20 | Int32 L length (copies at 100 and 108) |
| 24 | Int32 -1143: thickness, wall body to the right of START->END (room on the left) |
| 28 | Int32 H wall height (copies at 96 and 104); per wall, not per room |
| 32 | colour bytes R,G,B,0 (e1e1e1 grey, fcfcfc white) |
| 36 / 40 | Int32 ids of the walls meeting the START / the END (0 = open end) |
| 46 / 48 | Int16 3048 (12") and 6096 (24"), constant, meaning unknown; they push the points off 4-byte alignment |
| 50 / 58 | P0 = START and P1 = END of the inner (room-side) face, x,y Int32; P1 = P0 + L x direction (KCD's own files drift 1-16 raw) |
| 66 / 74 | P2 = outer corner at END, P3 = outer corner at START: inner point + T x normal, extended by T x tan(turn/2) along the wall so neighbours' outer faces meet in one point |
| 82 | Int32 4 = number of outline points |
| 117-123 | four Int16 copies of the id; 125 Int32 id; 129 Int32 room (0 = deleted) |
| 133 | three float64 colour (R/255 ...), not always kept in sync; 157-204 six constant doubles |

Topology: `right` of wall k starts where k ends, `left` ends where k starts; 2 closed loops, 20 open chains
and 7 standalone walls in the data; all corners 90 degrees except BINDLER (one reentrant) and ROBERTS WIC
(220-degree wall). Units sit on a wall by id with X from P0 along the direction; X < 0 and X + W > L occur in
designers' files (KCD tolerates both).

Changing a wall's length (anchor = START): set L (3 places), move P1 and P2 by dL x direction, translate all
four points of every wall downstream along `right` until an open end. A closed loop needs the opposite
(antiparallel) wall to change by the same amount, or the room opened (what the GODDARD engineer did with two
63" stubs); `resize_wall` refuses otherwise. Height: bytes 28/96/104 only. All edits are in place (same record
size), so nothing else in the file moves; the 3-D cache and print pages stay stale and KCD rebuilds them (as
with the splitter's files).

### 14.3 `kcdwalls.py`

- `--list JOB`: every live wall with length, angle, height, neighbours and the units on it (X, W, where they end,
  unit id and type code).
- `--rem REM.json --out NEW.job`: match each agreed wall by number, room name and printed length (within
  1/32", else CHECK), apply the measured length, never apply `needs_review`; `--heights-from-rem` sets every
  wall of a room to the measured `H`; `--set 7="25 1/8"`, `--height 1=90.25` for manual edits.
- Which end of a wall moves (`--anchor`, default `auto`, the engineers' way, see 14.7): the room's main wall
  (the 0-degree wall that starts at the origin) keeps its START; walls upstream of it (reached along left_id)
  move their START; the main wall and everything downstream move their END. `--anchor start|end` forces one
  end on every wall. The edited wall gets P1 = P0 + L*d exactly (KCD drops a designer's skew the same way,
  MIRANDA eng wall 3), so the self-test's +1/-1 round trip is byte-exact only on skew-free walls (192 of 240;
  the other 48 come back without their old skew, counted apart).
- The unit step (owner's rule, Oct 19, after tests 1 and 3 in KCD; `--walls-only` turns it off): fillers keep
  their width; the end fillers slide so they still end at the wall (X snapped to the 1/16 grid as KCD stores it);
  the cabinet that reaches the end filler (or stands against the wall end itself) is sized to fill exactly from
  its own X to the filler (slot 2 and the width copy at byte 12 of the 86-byte block), which also removes a
  designer's gap or overlap there (COYNE Linen: the owner took the tall down the extra 1/4 himself in try 3);
  then the units must run from 0 to the new wall length (reported, CHECK when they do not). Shelves drawn in the
  cabinet's opening (types 640/641, running from the inside of its left panel to the inside of its right panel)
  change by the same amount; a show-only item (type 890, the no-price baseboard) that runs the whole wall is set
  to the new wall length. Left alone and flagged: two cabinets ending at the wall end, a drawer unit at the end (engineers keep drawer
  widths), a cabinet with units nested inside it (a shelf spanning its interior), a wall whose units stop short
  of the end (reported, nothing to do), a filler that no cabinet reaches, a start-moving wall's accessories
  (outlets keep their X and move with the start, as KCD does). No stored size slot of the cabs looked at
  (CSE300, Hangdbl, 760-1, 234) depends on W; shelf, kick, door and rod sizes are computed from W by the price
  scripts, and the price run on test 3 shows them following the new widths.
- The two room points of every unit on a moved wall or with a new X/W are rewritten (14.6) and so is the unit's
  entry in the 3-D drawing cache (`kcdmesh.py`, 14.8), so KCD shows the units in place when the file opens.
  Notes are not moved; dimension strings on a changed wall are CHECK, text notes are listed.
- The file keeps its size; a final guard refuses the write if any byte outside the wall records, the touched
  unit fields (slot 1, slot 2, block bytes 12..15 and 40..63) and the moved cache entries changed.
- COYNE test files: TEST (walls only, Oct 19 01:36) went through KCD, see 14.6; TEST2 (walls + heights + two
  fillers resized) was withdrawn: the owner's rule is that fillers stay 3/4 and the units change. TEST3 (14.7)
  went through KCD (14.8); TEST4 (14.8) adds the drawing cache and is the one to round-trip next.

- **Which cabinet takes the change (Oct 19, NEDDIE run).** `unit_step` now works from the wall end that moved: the
  cabinet against that end changes width (a connecting shelf drawn across the end, into a corner, counts and keeps
  its overhang), the fillers at that end stay against it, and every other unit keeps its place in the room (X + dL
  when the start moved, X unchanged when the end moved). When that cabinet cannot change (a drawer unit, two
  candidates, other units inside it) the cabinet against the OTHER end takes the change and the run slides with the
  moved end instead; that is exactly what COYNE test 4 did on Guest wall 11 (start moved, '84 Tall 4 Drawer' at the
  start kept its width, 'Tall 1 Opening' at the end grew) and the owner approved it, so test 4 still rebuilds the
  same except the Guest wall 13 outlet (now kept in place in the room, 6 -> 2 1/4 from the moved start, flagged).
  Obstructions, outlets, switches and openings always keep their place in the room (`is_feature`). Accessories drawn
  in the changed cabinet stay with the panel they sit on (left or right); one centred in the opening (a hamper) is
  flagged for a re-fit. Interior shelves snap to the 1/16 grid. The read-out can also carry corner angles
  ("<room> corner #a/#b angle", degrees) and doorway openings ("<room> opening between #a and #b"): a corner more
  than 1 degree off the drawing is a CHECK (the tool never turns a wall), an opening is recomputed from the open
  wall ends after the edit and compared within 1/8. Lines written against a room name that are not walls or facts
  (obstruction boxes, wire heights) are listed as facts instead of "not used".

- **Sections of a changed wall come out the same size (Oct 19, owner: "if we make units the same sizes it's better, so
  that is a step we can avoid").** When the changed wall carries two or more hanging sections (types 651/652; failing
  that, open talls), they share the change so their interiors come out equal on the 1/16 grid (the odd sixteenths go to
  the sections nearest the moved end, each new width = interior + its two side thicknesses, snapped); every other unit on
  the wall keeps its width and slides with the run; shelves and accessories drawn in a section move with it (racks stay on
  their panel, a centred one is flagged); the designer's gaps are kept and the run still ends where it did against the
  wall end (CHECK if not). It is the default (`spread=True`; `--one-unit` turns it off and the single-cabinet rule above
  applies, which is also the fallback when the wall has fewer than two such sections, when the change is not on the 1/16
  grid, or when a section has units other than shelves inside it). NEDDIE: hers wall 1 (-3/16) 33 1/8, 32 3/8, 32 7/16,
  32 3/8 -> 33 1/16, 32 5/16, 32 3/8, 32 3/8 (interiors 31 9/16, 31 9/16, 31 5/8, 31 5/8); his wall 8 (+7/8) 26 7/8,
  27 5/8, 27 5/8, 27 5/8 -> 27 5/8, 27 5/8, 27 11/16, 27 11/16 (interiors 26 7/8, 26 7/8, 26 15/16, 26 15/16) with the
  96 Tall 5 Drawer sliding 55 1/4 -> 56. The resized units also get their per-face width values redone in the drawing
  cache (14.8), or KCD draws them at the old width until they are opened.

### 14.4 How the engineers absorbed remeasured lengths (ten sets, before and after; `scratchpad walls/rules/absorb.py`)

Rules with evidence (R1-R11 in the study; the short form):
- They apply a remeasure only sometimes: GODDARD yes (walls 163 9/16 -> 162 5/8, 90 3/4 -> 88 7/8 and 89 1/8,
  door wall replaced by two 63" stubs, ceiling 114 -> 115 1/4); PRIEM (166 -> 165 3/4) and HUMPHREY
  (145 -> 144 3/8) were NOT applied, the engineered files keep the design lengths and units.
- Catalog products never change width (drawer towers 29 1/4 with one panel, wall beds, shoe units 31 1/2, 774
  talls, hutches 35, refrigerators 32, L corners); only their X moves.
- Hanging sections and open talls are what gets resized, and when a wall is rebuilt the units of one type in a
  run get EQUAL interiors on the 1/16 grid (GODDARD side walls 3 x 27 3/4 interior; ROBERTS WIC 38 13/16,
  38 13/16, 39 9/16; SFERRA 2 x 34 5/16). Walls the engineer did not rebuild keep the designer's unequal widths.
- Mirrored side walls get the SAME unit set sized to the shorter wall (GODDARD 87" of boxes on 88 7/8 and
  89 1/8, slack 1.6 to 1.9 left at the back corner); how much slack to leave is a human choice.
- Residue goes to the inside corner that the perpendicular wall's connecting shelf covers; the 3/4 filler
  stays flush at the exposed end. Residue under about 1/4 is parked at a corner; larger residue is a human call
  (gap, equal fillers, or resize). POLONSKA split 1 3/4 into two 7/8 fillers.
- Fillers: 3/4 (cab 234) at the exposed end, X = 0 or ending at the wall length; designers' 1" and 1 1/2"
  fillers became 3/4; filler height = adjacent unit height. Two drawing conventions: designer W = 3/4 and D =
  face width; engineer W = face width and D = 3/4.
- Corners: designers draw [side-wall depth] + a connecting shelf of the real span; engineers draw Csetbot +
  Csettop at the nominal W = 20 with X = cabinet edge - 20 plus a 16" Backing, and centre the back-wall run with
  EQUAL corner zones; when the back wall shrinks the corner zones absorb it equally (GODDARD -0.559 each) while
  hanging interiors round UP to 24 3/4 and towers stay nominal.
- Design-only items are stripped (890nc baseboards, LED strip lights, pictures, platforms); accessories become
  1/8-wide markers with quantities parked at the wall end; loose panels become 3/4 Custom Holes Panel units
  and the boxes between them get LS = RS = 0.
- Wall heights are set to the remeasured ceiling in 7 of 10 customers; unit heights are not changed by it.
- Doors and windows are redrawn from the remeasure by hand, or deleted with the wall cut back to the opening.
- Rebuilt files renumber walls in chain order: match walls by chain position and length, never by id.
- Decisions that need a human: whether to apply at all; which unit gives way when the only trimmable part is a
  3/4 filler; product substitutions; opening positions; the interior to pick and the slack on rebuilt side
  walls; gap versus fillers for residue over 1/4; corner-unit depth changes.
Caveats: only GODDARD, LONG and ROBERTS WIC show clean absorption on walls with cabinets (about 8 walls); the
other pairs mix the wall change with re-layouts; remeasure values are only known for GODDARD, PRIEM, HUMPHREY
(and now COYNE, WERNER).

### 14.5 WERNER, one remeasure end to end (designer's job, engineer's final, workbook; study in `scratchpad walls/werner/werner_findings.md`)

- Walls: wall 1 198 -> 205 1/8 (the measured); height 120 -> 138 3/4 on all walls (the read-out's "13 3/4"
  had lost a digit); two side walls added from the tech's sketch: wall 2 (left, 26, angle 270, its END at the
  corner) with an Obstruction 3 3/8 x 96 at 22 5/8..26 from the corner and an outlet 12 3/4 from the corner,
  12 1/4 off the floor; wall 3 (right, 142 7/8 = 10 7/8 + 120 3/8 + 11 5/8 exactly) with the window 120 3/8
  wide at 10 7/8 from the corner, sill 15 1/4, height 80, and an outlet at 8. Site items become library units
  (`010.cab` Window, `Outlet.cab`, `Obstruction.cab`); distances on a side wall are measured from the corner
  (X = dist on the wall that starts at the corner, X = L - dist - W on the one that ends there).
- Not used from the sketch: the two boxed 0s, the circled 2 5/8 (most likely 22 5/8: the door casing the 1 1/2
  filler is set against, 19 5/8 + 3 from the wall), the hatched fraction, BB, F, Molding; the engineer's 26,
  window height 80, outlet positions and the 9" open end have no source in the read-out.
- Units on wall 1: the room was rebuilt (ids reassigned in creation order; only the TV and the two pop-up
  sockets kept their ids and their absolute X). Bases 48 / 33 15/16 / 33 15/16 / 34 5/8 / 48 (198 1/2 drawn on
  198, overlapping) -> 1 1/2 filler + 45 3/8 / 34 3/8 / 34 3/8 / 35 1/8 / 45 3/8 = 196 1/8, flush, one shared
  3/4 panel per joint (8 panels -> 6), 9" left open at the right ("THERE SHOULD BE AN 8" GAP ... " with the
  countertop overhanging 1). The three door cabinets got equal 33 5/8 interiors; the two knee holes took the
  remainder equally ((194 5/8 - 103 7/8) / 2 = 45 3/8). H, D, kicks, materials, cab files unchanged.
  Backings and the sliding shelf were re-fitted to their host (X = host X + LS, W = interior); the four 3/4
  spacer fillers became one unit with qty 4 parked 10" past the wall end. Typed reveals at the shared-panel
  joints (-5/16 / +7/16) give 17 5/16, 17 1/8, 17 5/16 x 25 1/8 doors; the Doormark order has 17 1/4 and
  17 1/16 x 25 1/8 (1/16 under KCD).
- Workbook: the 50 pasted lines carry the engineered unit IDS as unit numbers; every dimension line agrees with
  the engineered slots after 1/16 rounding and every option line sits on its unit. The wood countertop is
  priced on the designer's 35.12 sqft, not recomputed (engineered run is about 34.9).
- For the app: everything in "walls" above is mechanical given the sketch; the unit step is a human layout
  (where the open end goes and why, the casing filler, the target interior) with mechanical consequences the
  app can carry out and check (equal interiors, shared panels, re-fitted backings and pullouts, reveals, qty
  fillers, the price-review unit numbers that change when a room is rebuilt).

### 14.6 What KCD did with test 1 (the owner opened TEST, double-clicked each wall, saved; `jobs/Cathy Coyne - TEST1 saved by KCD.job`)

The owner reported: the file opened, the units were drawn off their walls until he opened and closed each wall
in KCD, and then KCD placed them. The saved file (7,507,246 bytes, 77 more than ours) compared with
`kcdcompare.py` and a per-record diff:

- Every wall length we set survived (12 walls). KCD recomputed the wall points: Linen (walls 7-9) came back
  byte-identical to ours; Guest (10-13) was moved back so the main wall 10 starts at (0,0) again, which is
  exactly what the `auto` anchor now produces (test 3's Guest walls equal KCD's save byte for byte); Primary
  came back with wall 14 detached (left_id/right_id 15/16 -> 0/0, wall 15 right_id -> 0, wall 16 left_id -> 0)
  and moved to (2318,0)-(20638,0) while walls 15-19 moved about 3464 raw in y: that is a drag in KCD, not a
  recomputation, and the reason to ask the owner what he did in that room. Wall 15's f64 colour went to 0 and
  the first record's Int32@8 save counter changed (156 -> 234).
- Units: KCD rewrote the geometry counts (block bytes 16..39) and the two room points (40..63) of the
  cabinets, snapped two accessory X values to the 1/16 grid (4111 -> 4112, 6143 -> 6144), cleared the unwname
  'Closet Shelf Inventory' on two shoe units and put a leading space on some Code strings (' =#36#='). No unit
  width changed. Header 1477 -> 1573 bytes, mesh n1 36 -> 45, pictemp +1 byte, units section -40 bytes.
- The two room points (A at block byte 40, B at 52, three Int32 each) are room coordinates: along the wall
  both sit at X + W/2 from the wall's START on all 30 units; across the wall at a fixed distance (B: D/2 on
  cabinets, From Wall + D/2 on fillers; A: 3/4 D on talls, 7/8 D on uppers, 0.92 D on shelves, D/2 on
  accessories); z is a fixed height. KCD recomputed them for the cabinets but left the fillers and accessories
  where they were (units 10, 11, 15, 17, 29, 98 off by the old translation), so a moved wall needs them
  rewritten by us. `moved_unit_points()` keeps each unit's fraction along its width, its distance from the wall
  and its height, and reproduces KCD's own values exactly on the Guest room of the test-1 save (door, 4-drawer
  tower, shelf, outlet: zero difference; the fillers differ by exactly KCD's stale offset).

### 14.7 Test 3 (Oct 19, `out/Cathy Coyne - REM 1093610 applied - TEST3.job`, md5 0060bbe1...)

Built from the original job with `--rem --heights-from-rem` and the new defaults. What changed:

| Wall | Length | Unit step |
|---|---|---|
| Linen 7 | 25 1/4 -> 25 1/8 (end moved, wall 9 followed) | Tall 1 Opening 24 -> 23 7/8; filler 74 16 slid to X 24 3/8 (its 1/4 overlap with the tall unit is the designer's) |
| Linen 8 / 9 | 32 5/16 -> 32 1/8 (start moved) / 38 -> 34 7/8 | no units |
| Guest 10 | 65 1/16 -> 65 1/4 (end moved, wall 12 followed) | Upper Hutch 37 1/16 -> 37 1/4 (the hutch stands against the wall end; the wall is empty before 28) |
| Guest 11 | 66 3/16 -> 66 1/2 (start moved, wall 13 followed) | Tall 1 Opening 33 3/16 -> 33 1/2; end filler slid to X 65 3/4; units 0 to 66 1/2 |
| Guest 13 | 36 1/2 -> 32 3/4 (start moved) | Electrical Outlet keeps X 6 (CHECK its place) |
| Primary 14 | 72 11/16 -> 72 1/8 (end moved, walls 16, 19 followed) | second Double Hang 35 1/4 -> 34 11/16; end filler slid to X 71 3/8; units 0 to 72 1/8 |
| Primary 16 | 91 1/2 -> 91 1/4 | units stop at 76, nothing to do |
| Primary 18 / 19 | 62 9/16 -> 62 3/8 (start moved) / 33 3/16 -> 33 1/8 | no cabinets |
| Primary 15 | not applied (readers disagree 57 7/8 / 57 3/8) | |
| heights | Linen 90 1/4, Guest 95, Primary 90 1/8 on every wall | |

Checks on the file: section sizes unchanged, only wall records and the unit fields differ (`kcdcompare.py`);
Guest walls equal KCD's own test-1 save; the relative room points of all 30 units are unchanged and the
absolute ones match KCD's recomputation where the walls coincide; 16 units had their room points moved. Price
run (Sep 2024 list, the only full list here): only the four changed units' lines differ, and every dependent
part follows the width (unit 4 shelves 22 1/2 -> 22 3/8, kick 24 -> 23 7/8, doors 11 15/16 -> 11 7/8; unit 10
shelves 32 7/16 -> 32 3/4; unit 12 back 35 9/16 -> 35 3/4 (55.56 -> 55.86), rod 35 5/16 -> 35 1/2; unit 21
shelves 34 1/2 -> 33 15/16, rods 34 1/4 -> 33 11/16). The design plan and the critic that led to the anchor
rule are in `experiments/design/`. Open: the KCD round trip of test 3 (do the units sit on the walls without the
double-click; what KCD does to the two dimension strings on Guest wall 10); which unit the engineer would have
chosen on wall 11 (the tool takes the cabinet next to the end filler, the open tall, not the drawer tower).

### 14.8 What KCD did with test 3, and the drawing cache (`kcdmesh.py`; Oct 19, `jobs/Cathy Coyne - TEST3 saved by KCD try3.job`)

The owner opened test 3, fixed what looked wrong, saved, and sent four pictures: units sitting into their walls
"again but not as much", and fillers overlapping panels. His saved file against ours:

- Linen and Guest walls came back byte for byte; the Primary room was moved as a whole by (2461, 5334) raw with
  every link intact (a drag of the room, harmless). Wall 1's save counter changed again.
- His own edits: the Linen tall (unit 12) 23 7/8 -> 23 5/8, so it ends exactly where the 3/4 filler starts
  (the designer's file had the filler overlapping the tall's side panel by 1/4; the rule is now "the cabinet
  fills exactly to the filler"); the filler's X 6192 -> 6191 (KCD keeps positions on the 1/16 grid: 24 3/8 x
  254 = 6191.25). Nothing else was changed by hand; the Guest hutch and tall and the Primary hang kept our
  widths. The Double Hang's I252 state byte changed because he opened that unit.
- Why the units looked wrong: KCD draws the plan, the elevations and the 3-D view from the cache in the `mesh`
  section and does not rebuild it when a job opens; it regenerates a unit's entry only when that unit or its wall
  is edited. Test 3 moved walls and resized units but left the cache, so the wall-16 units showed 9/16 off
  their wall (wall 16 had moved 9/16), the Primary end filler still sat at its old X overlapping the wall
  (picture: "(-9/16)" on the filler), and the resized Double Hang still read 34 1/2 inside until he opened it.
  The two room points of 14.6 are not what KCD draws from; they are secondary (and KCD moved them by the wall
  delta again when he touched wall 16, so they came back 143 raw off: it adjusts them by delta, not from X/W).
- The cache, decoded (`kcdmesh.py` docstring has the layout): float32 x, y, z vertices in room coordinates,
  1-based per-unit slices from bytes 16..39 of the 86-byte block (vcount, voffset, foffset, fcount, ioffset,
  icount; the vertex and face slices tile the arrays exactly), Int32 indices local to the unit, 66-byte faces
  whose only position-dependent field is the face centre (float32 at 24..35). KCD re-serialises the faces in a
  new order on every save, so faces compare as multisets.
- Proof against KCD's own work. Translating a unit (vertices and face centres + v) reproduces KCD's moves
  exactly: the owner's room drag (every untouched Primary unit, 1692 + 621 + 527 + ... vertices and 3358 + ...
  faces, equal), KCD's re-anchoring of the Guest room in the test-1 save (door +48, tower and shelf +79, equal),
  and the wall-16 units it re-placed (equal). A width change as a stretch about the unit's middle (points past
  the middle + dW, points at the middle + dW/2) against KCD's own regeneration: the Linen tall differs on 17 of
  451 vertices (the handles), the Double Hang on 178 of 621 (the centred hanger symbols move dW/2 in KCD);
  panels, shelves, rods, kicks and door bodies match. KCD leaves fillers and accessories stale when it
  re-anchors a room (test 1: fillers 15/17 and the obstruction; try 3: the utility cover on wall 19), so where
  our positions differ from KCD's for those, ours are the ones on the wall.
- TEST4 (`out/Cathy Coyne - REM 1093610 applied - TEST4.job`, md5 d78b4524...) = test 3 rebuilt from the
  original with the fill-to-filler rule and the cache moved: 14 cache entries translated, 4 stretched, 17 room
  points moved; sections unchanged in size; the price run differs from the original only on the four resized
  units (Linen tall now shelves 22 1/8, kick 23 5/8, doors 11 3/4). Sent to the owner with the request to open
  it without touching any wall. **Owner, Oct 19: "everything looks good on test 4", opened in KCD with no wall or
  unit touched; the units sit on their walls.**
- **The round trip of test 4** (`jobs/Cathy Coyne - TEST4 saved by KCD try4.job`): KCD kept the file as written.
  Linen and Guest walls byte-identical; every unit record unchanged (one Code string lost its leading space);
  all 14,897 cached vertices identical and the face records equal as multisets on 29 of 30 units, the stretched
  Double Hang differing on 52 faces by 1 raw of rounding in the centre (dW/2 = -71.5) and a few hanger centres;
  the per-unit slice fields (block 16..39) identical, the index slices re-serialised, n1 36 -> 45, header blob
  smaller. The Primary room was moved as a whole by (0, 5715) with its room-level notes (KCD re-places that room
  on every save: (2318, ~3464) in test 1, (2461, 5334) in try 3, (0, 5715) here; Linen and Guest never move;
  harmless, links intact). So: wall record + unit slots + room points + cache entry is the complete set of
  things to write for a wall or width change, and the per-face sizes (Int32 at 16/20) and the n1 block can stay.
  COYNE is the first job to go from remeasure sheet to a KCD file nobody had to touch. Still open: what the two
  dimension strings on Guest wall 10 and one on Primary wall 16 show; Primary wall 15 (readers disagreed); a
  second job through the same path (a closed room, a longer change, a start-moving wall with cabinets).
- **The per-face width values (Oct 19, from the NEDDIE TEST1 save, `jobs/Lynn Neddie - TEST1 saved by KCD try1.job`).**
  The owner: "how is it that the his master back wall grew by 7/8 and all the units are still the same size", then "when I
  double click and open then close it changes to the new size". The width was in the file; the drawing was not. KCD had
  rebuilt only the two units he opened (3 and 14). Against ours, their vertices matched (the hanger symbols apart, +-dW/4),
  but the Int32 at byte 20 of every face had moved with the width: in KCD's entries it is k*W + b (k in 1, 2, 5, 1/2, 1/4,
  5/8, 5/4, 3/2, 7/4, 5/2 ...; b in 0, -190, -254) or a constant (D, H, 190, 254, 635, the shelf heights), and KCD sizes
  the drawn panels from it, so a stretch of the vertex list alone shows the old width until the unit is rebuilt.
  `kcdmesh.face_width_value` now rewrites those values (fractions n/8 and n/3 with offsets 0, +-190, +-254, -380/-381;
  a value equal to a fixed size H or D is left alone unless it is a plain multiple of W, after a false "ambiguous" on
  NEDDIE unit 8 where D = 3048 also read as 3/8 W + 190); on units 3 and 14 the result equals KCD's rebuild value for value.
  Also seen in the rebuilt entries: the slice offsets re-packed, A.x/B.x re-rounded, a name string's leading space toggled,
  the hers room shifted by -1 raw, n1 down by 4, the stored face centre is not the mean or the box centre of the corners (a
  per-part centre), the tails (bytes 36..65) of rebuilt faces all zero. The DRUBEL regression file changed only in the face
  width values of its five shelves. TEST2 of NEDDIE (14.10) is the first file written with these values.

### 14.9 DRUBEL (order 1091400, `Bayle DCL - Daughters Room.job`, remeasure `Rem_1091400_drubel.pdf`; Oct 19, waiting for Grok)

- The job: one room "Library Thick", walls 10 (95 7/8, main), 11 (48 3/16, downstream return) and 12 (28 3/16,
  upstream return), heights 144 5/16; walls 1-9 dead. Wall 10 holds three 96 Tall 1 Opening units (RS 1 1/2 on
  the first two, 3/4 on the last), each with five CLO-SH shelves drawn in its opening, 3/4 fillers at both ends
  and a no-price show baseboard (type 890) the length of the wall. No sidebar note; empty job heading.
- The sheet, read by eye: wall 10 "95 7/8" circled with no correction (confirmed); wall 12 "27 7/8" handwritten
  (from 28 3/16); wall 11 carries two handwritten numbers, "12 1/2" and "26 1/4", against the printed 48 3/16
  (a split wall or an obstruction: Grok's read-out and the numbered scan have to settle it, else CHECK); room
  facts "CH 100" (the photo shows a soffit over the cabinets; the file has 144 5/16), "BB 7 1/4 W", "Fl wood";
  wall 10 elevation: "Soffit" drawn with "100" and arrows. So the test here is heights to a soffit, a start-moving
  wall with no units, and an uncertain return wall; not the closed-room case.
- Prepared for it: the unit step now carries the shelves inside the end cabinet and resizes the show baseboard
  (above); a hypothetical `--set 10="95 1/2"` dry run changed the end tall 30 15/16 -> 30 9/16 with its five
  shelves 30 3/16 -> 29 13/16, slid the filler, set the baseboard to 95 1/2, and the cache shapes end exactly at
  the new unit ends. COYNE test 4 rebuilds byte-identical with the new code (md5 d78b4524).
- Owner (Oct 19): "the interior shelves that are numbered individually need to match the unit widths and depth of the
  ones they are in". `shelf_fit()` now runs on every wall: each shelf (type 640/641) inside a cabinet is set to the
  cabinet's opening (X = X + LS, W = W - LS - RS) when off by more than 1/16; a depth that differs is flagged. DRUBEL:
  the middle tall's five shelves were 29 7/16 against a 29 1/2 opening and were fixed; the other ten matched.
- Sent to the owner Oct 19 from my own reading of the sheet (Grok's read-out still pending): TEST1 (wall 12 27 7/8,
  heights 100, wall 11 flagged) and TEST2 (TEST1 + the five shelves), md5 323c7ff5..., plus the pricing workbook
  (section 15).

### 14.10 NEDDIE (order 1090111, `Lynn Neddie.job`, remeasure `REM-1090111-LYNN.pdf`; Oct 19, read by Claude, no Grok)

- The owner's ask: run one job complete with no other AI reading the sheet, to see how close to stand-alone this
  can be. The sheet (12 pages: Salesforce page, hers plan on two pages, photos, his plan, his wall 13 elevation,
  photos) was read by eye from the scan and written as the same read-out JSON Grok produces
  (`scratchpad walls/grok/REM-1090111-NEDDIE.json`): 13 wall lengths, his #9 held for review (nothing written next
  to it), four corner angles per room, the doorway opening per room, H/HD/BB/F/Door/Molding per room, the wall 13
  obstruction box. Remeasure 10-12-26 by Gary; sold 9/11/2026, install 11/4/2026, designer Jessica Philbrook,
  15,155 for the two spaces.
- The job: two rooms, "Primary hers" (walls 1-7) and "Primary his" (walls 8-14), both U-shaped with two angled
  corner walls and two short door-wall stubs, heights 135. Main walls 1 and 8 (0 degrees); anchors hers
  {1 end moves, 2 start, 3 end, 4 start, 5 end, 6 start, 7 end}, his the same pattern. Units: hers wall 1 filler +
  Long/Mid/Double/Double Hang to 131 1/16; wall 2 a corner Top Connecting Shelf at X 0, 84 Tall 1 Drawer at 7 1/2
  with a Shelf, tilt-out and two racks, Connecting Top and Bottom Shelves to 51; wall 3 Connecting shelves at 12,
  96 Tall 6 Drawer at 24 with jewelry trays, lock and mirror backing, a corner Top Connecting Shelf drawn 10 1/2
  past the wall end; walls 4 and 5 a 96 Tall 1 Opening each; his wall 8 filler + Double Hangs, 96 Tall 5 Drawer,
  Double, Mid Hang to 142; wall 11 Long Hang the length of the wall with a belt rack; wall 12 84 Tall 1 Drawer
  the length of the wall with a tilt-out and two racks; wall 13 an obstruction at 15.
- What the sheet says: every wall changed (hers -3/16 to +3 3/8, his +5/16 to +1 7/8, his #14 confirmed), ceilings
  135 3/4, and all eight corners measured 133.6-135.9 degrees where hers is drawn 130/140 and his 135/135.
- The run (`kcdwalls.py "Lynn Neddie.job" --rem REM-1090111-NEDDIE.json --heights-from-rem`,
  `out/Lynn Neddie - REM 1090111 applied - TEST1.job`, md5 30555aa5...): 13 walls and 14 heights set; hers wall 1
  Double Hang 32 3/8 -> 32 3/16; wall 2 (start moved +2 3/4) corner shelf 12 -> 14 3/4 and the six other units
  X + 2 3/4 so they stay put (the Shelf then re-fitted to the tall's opening); wall 3 (end +2 3/8) the corner shelf
  at the end 12 -> 14 3/8 keeping its 10 1/2 overhang; wall 4 (start -1/2) 96 Tall 1 Opening 20 1/2 -> 20; wall 5
  (end +2) 96 Tall 1 Opening 20 5/8 -> 22 5/8; his wall 8 Mid Hang 27 5/8 -> 28 1/2; wall 11 (start +1 7/8) Long
  Hang 30 -> 31 7/8 with the belt rack kept on its left panel; wall 12 flagged (the only cabinet is a drawer unit,
  nothing changed); wall 13 obstruction kept in place (15 -> 15 5/8 from the moved start, flagged). 25 units
  re-pointed, 23 cache entries moved, 8 stretched; sections and mesh counts unchanged. CHECKs (12): his #9 held;
  the four hers corners 3.6-5.6 degrees off the drawing (the engineer redraws them in KCD); the hers doorway works
  out 34 15/16 against 30 1/2 measured (the corners again; his comes out 30 3/16 against 30 1/4); the two corner
  shelves; the belt rack; wall 12; the obstruction. So for hers the file is a starting point and the corners are
  the engineer's; his is complete except wall 12.
- Transfer to the laptop: the original job was already there (Downloads), so only a byte patch went over
  (`applypatch.py`: gzip+base64 JSON of the changed byte runs, 60 KB in 837 lines instead of the 862 KB file); the
  appends glued two lines at the chunk joins (`fix76.py` re-splits at 76 characters) and one 50-line block arrived
  altered and was re-sent (`splice2.py`); md5 of the result checked.
- TEST1 in KCD (owner, Oct 19): the his back wall "grew by 7/8 and all the units are still the same size" until a unit was
  double-clicked: the per-face width values of the drawing cache (14.8, now written). He also set the second rule: units
  of a changed wall should come out the same size (14.3).
- TEST2 (`out/Lynn Neddie - REM 1090111 applied - TEST2.job`, md5 8d60935a...): the same walls and heights; hers wall 1
  and his wall 8 now share the change over their four hanging sections (sizes in 14.3) and the 96 Tall 5 Drawer slides
  55 1/4 -> 56; 32 room points moved, 30 cache entries moved, 11 units stretched with 1504 face width values redone;
  11 CHECKs (as TEST1 less the Double Hang). Sent with the ask to look at both back walls without double-clicking anything.
- Pricing TEST2 on the laptop: the 1237-line patch went over in four chunks; the third lost its last 100 lines and five
  50-line blocks arrived altered (`fixpatch.py FILE START COUNT FIX` on the laptop replaces or inserts lines and prints the
  block md5s; `applypatch.py` checks the source and result md5s, 8d60935a... matched). `price_job.py JOB TAG` prices each
  room: hers 104 lines 11,029.80, his 79 lines 6,923.40, the same money as TEST1 and (hers) as the designer's file; only
  the shared sections' shelf, kick and rod sizes moved (hers interiors 31 9/16, 31 9/16, 31 5/8, 31 5/8; his 26 15/16,
  26 15/16, 26 7/8, 26 7/8). Workbooks v2 in section 15.

## 15. The pricing workbook filler `kcdbook.py` (Oct 19, 2026; first job DRUBEL)

- What it does: copies the `mike_p_for_services` template (`.xltm`, 238 parts) part for part into a `.xlsm` and changes
  four parts only: `[Content_Types].xml` (template -> macro-enabled workbook, the one difference Excel itself makes),
  `xl/workbook.xml` (`fullCalcOnLoad="1"` on `calcPr`, so Excel recomputes every sheet on open), `xl/sharedStrings.xml`
  (new texts appended, count/uniqueCount kept right) and the Data Entry sheet (answer cells and the paste block K..P from
  row 2, existing cell styles kept, rows 3+ styles 379/100/183/377, new rows as Excel wrote WERNER's rows 43+). Never
  re-save the workbook with openpyxl: it drops the two external links, the ActiveX controls and the comments.
- Data Entry answers (dropdown lists live on the Data Conversions sheet; exact text only): B1 install date (serial),
  B3 day type (I20:I23), B5 client number, B7 name, B9 room, B11 Costco, B13 jewelry tray (I29:I31), B15 hinge
  (I69:I71), B17 V9/V23, B19/B21/B23/B25 YES/NO, B27 sold-at price, F1 designer (G1:G69), F3 cutlist by, F5 unit
  material (B1:B83), F7 banding type (I37:I41: .5mm 1mm 2mm Upgraded Woodtape), F9 banding colour (the materials
  list), F11 face type (I7:I16), F13 faces material, F19 construction type, F21 molding (None Melamine Thermo Foil CF
  Thermo Foil Wood Combination Mica), F23 molding location (None, Base Only, Crown Only, Base & Crown, Recessed Base),
  F25 notch. F15/F17/C1/D26/D27/A27 are formulas: never written.
- Paste block (checked against the WERNER workbook): K price, L unit number (KCD's position among live units), M part,
  N first size, P second size; a part with one size goes in P; kicks, fillers, leg levelers and mirror backs show the
  width only in P (the engineer types the height in R). Modify Here's 3,082 formulas read J..Q ('Data Entry'!J2>0
  means the paste landed one column left); R is not read by any formula. Quantity > 1 repeats the line.
- Checks built in: every other part byte-identical to the template; the four edited parts parse; openpyxl opens the
  result; the formula count of the sheet is unchanged. LibreOffice does not recalculate on load (the preview shows the
  template's cached zeros); `recalc.py --force` on a COPY does, and shows the Final Price Sheet computed. The blank
  template itself recalculates with 21 errors (20 #N/A on Data Conversions T/V, one #VALUE! on BCCD A1!AM1): they are
  the template's, not the fill's.
- Parity: rebuilding WERNER from its own Data Entry answers and 50 paste rows reproduces its Data Entry sheet on 274 cells;
  the 14 differences are all in Q and R (the engineer's hand entries: filler and kick heights, a date, two overflow
  sizes) and the template's R2/R3 = 48 that the engineer cleared.
- DRUBEL (`out/1091400 DRUBEL LIBRARY.xlsm`): priced on the laptop with the May 2026 list + May 22, July and August packs
  (`kcdprice.py` there is byte-identical to the repo's); 31 lines pasted, 6 door lines left out (the room says No
  Door/Drawer Faces; the scripts print two doors on every 96 Tall 1 Opening, the open "no door" question of section 7),
  subtotal 4010 + 199 fee = 4209 standard against 4000 sold (Salesforce). Answers filled from the job's room details and
  the Salesforce page; B3, B13, B15, B19, B21, B23, F13 left blank and listed. Kicks price 0 on the 2026 list; the 15
  numbered shelves are 1 1/2" thick (148 each). Waiting for the owner to open it in Excel.
- Transfer note: the laptop received the 278 KB job as gzip+base64 (25 KB) through Desktop Commander `write_file`; one
  50-line block arrived altered and was re-sent (`splice.py` on the laptop compares per-block md5s).

- NEDDIE (Oct 19, two rooms, two workbooks `out/1090111 NEDDIE PRIMARY HERS.xlsm` and `... HIS.xlsm`): priced on the
  laptop per room (`price_neddie.py`, `kcdprice --room`) from the remeasure test file; hers 131 lines 9,973.80 after the
  four door lines of the two 96 Tall 1 Opening units were left out (the scripts print two doors 2 15/16 to 5 3/4 wide on
  them, which cannot be real, and the units have no door-height slot; the open "no door" question), his 87 lines 6,923.40;
  with the 199 fee each that is 17,295 standard against 15,155 sold for the two spaces. `--drop` now matches "unit N part"
  and repeats, so a drop can name units. The remeasure moved sizes but no money in hers (shelf and kick widths), and in
  his 6,940.40 -> 6,923.40 because the unchanged (flagged) 84 Tall 1 Drawer on wall 12 no longer reaches the wall end and
  its right panel drops from 266.70 to 249.70: the price scripts look at whether a panel is at the wall end. B25/B27 left
  blank (the sheet gives one total for both rooms); B13 blank although hers has two jewelry trays.
- NEDDIE v2 (`out/1090111 NEDDIE PRIMARY HERS v2.xlsm`, `... HIS v2.xlsm`, Oct 19): the same answers and drops rebuilt from
  TEST2's prices (the same-size rule, 14.3): hers 131 lines 9,973.80 after the four door lines, his 87 lines 6,923.40; against
  v1 only the shelf, kick and rod sizes of the sections that now share the wall change differ. The reports end with where
  each answer came from, what was left blank and what the remeasure changed, for the engineer.

## 16. Fillers at both ends, the purchase order and the special-order forms (Oct 19, 2026; owner's ask)

Owner: "is it also possible to do more: when units go between 2 walls there needs to be fillers on both sides; also use the
information from the side bar to fill out the PO and any special order items like CF5 doors, Doormark doors, velvet jewelry
trays, as much as we can get done so it's just a review by the engineer vs them doing the work". Five studies ran in
parallel (full reports in the session scratchpad `walls/po/A_sidebar.md` .. `F_critic.md`; the prototypes are kept in
`experiments/po/`). What they found:

### 16.1 The sidebar (`experiments/po/sidebar.py`, prototype parser)

- One KCD note per room, text starting `ROOM DETAILS <name>`: labels at column 0 (`HEIGHT-`, `GARMENT LENGTH-`,
  `MATERIAL/COLOR-`, `EDGE BANDING-`, `BACKING-`, `CLOSET RODS-`, `HANDLES/KNOBS`, `DOOR/DRAWER STYLE-`, `DRAWER BOX-`,
  `CROWN-`, `BASE-`, `COUNTERTOP TYPE-` / `COUNTER TOP-`, `ROOM OPTIONS and ACCESSORIES-as listed`, `DESIGN NOTES`,
  `ROOM INFORMATION`), tab-indented detail lines (`Color-`, `Finish-`, `Area-35 1/8-sqft`, `24" deep`, `Opt-Set Holes
  Custom - Qty 6.00`, `RM1 JT Standard`) and typed extras (`*promo color*`, `Richleui bp8160160-140 chrome`). One `RM` line
  per accessory unit and one `Opt` line per option; those counts and the rod counts matched the unit records in all 8 local
  rooms. Verified on 7 raw sidebars; the 24 sidebars of the ten sets (laptop) carry forms the parser has not seen yet
  (multi-handle lines with face assignments, "TWO PER DRAWER", `Insert-Clear Glass`, `B CF 5-Piece ... w Biscuit insert`,
  `Lift-up Door Hinge`, LED lines). The old `kcdunits.sidebar_fields` keeps only first-line values of the dashed labels.
- WERNER: the designer's and the engineer's sidebar are byte-identical; the designer's cabinets carried `Abacoa Shaker TH`
  while the sidebar said `SARASOTA Shaker TH`, and the engineer ordered Sarasota (Doormark SHS): the sidebar won.
- Checks the parser raises: COYNE Primary/Linen sidebar `White Coast Oak Grain` against every cabinet `Lino Esteiro Grain`
  (KCD prices Lino Esteiro); NEDDIE hamper `547.43.315` against the unit code `547.43.305`; NEDDIE `*promo color*` with
  multiplier 1.10 (the PROMO list is 1.00); sidebar depths 12/16 against 14" and 17" units; handle counts below the drawn
  fronts (NEDDIE hers 6 vs 7, COYNE Primary 2 vs 4, Guest 1 vs 4).
- Certain from the sidebar: F5/F7/F9 when the name is in the template's dropdown (Mysterious, Designer White Grain, Wheat
  Tabby Grain are; White Coast Oak Grain and Lino Esteiro Grain are not), F11 Melamine, F21/F23 from the BASE/CROWN lines,
  the Doormark design code (all 34 names of the workbook's own table resolve), the door colour name, handle part number and
  count, accessory part numbers and counts, jewelry colour and insert styles. Inferred only: the vendor from the number's
  shape (`###.##.###` Hafele, `BP#####-XX` Amerock, `BP#######-###` Richelieu), whether a TH door goes to Doormark or the
  CF Thermo form. Not in the sidebar: door sizes, which units really have doors, hinge side, insert, Doormark colour codes
  beyond the 17 in the workbook, install date / job number / designer / sold price (the Salesforce page).

### 16.2 The forms are tabs of the pricing workbook (all ten ENG packets read on the laptop, 178 pages)

- Every printed form is a tab of `wb/template.xltm`: Final Price Sheet, Purchase Order, Job Cart Cover Sheet (= the CNC
  cover sheet), CF5 Order, VJT Order (velvet jewelry trays), Doormark A1/B1, CF Stone, CF Thermo, Ladder, BCCD A1. Their
  headers (client, room, designer, engineer, install date, PO date, price) are formulas from Data Entry; only the line items
  are typed, and macro buttons PDF and email them (CF5/VJT to Diego, PO to Carrie). Only Elements is an outside paper form.
  So "fill the PO and the forms" = write those typed cells the way `kcdbook.py` writes Data Entry (only `Holes` has a
  Worksheet_Change macro, so XML writes to the order tabs are safe). Data Conversions holds 34 Doormark designs, 18 colour
  names / 17 codes, the CF5 adjustments (butt joint -1/16, cut width -6, insert -5 9/16) and the Work Required Grid offsets
  (21/30/45/65-day types -> 7/14/28/40-day rows; job cart check = install - 2, matched on all 13 cover sheets).
- In the ten packets: price sheet 12, PO 9, CNC cover 13, Closet Poles 7, CF5 on GODDARD / POLONSKA / MIRANDA, VJT on
  GODDARD, Doormark on PRIEM, CF Thinscape on POLONSKA, Marble & Granite on PRIEM, client-supplied hardware on BINDLER; no
  Elements, caddy, CF Thermo, ladder or BCCD form.
- Door sizes on the forms are the DOOR-DIMENSIONED elevation, not the price-engine sizes: PRIEM Doormark 10.8125 x 25.125
  and 33.5 x 12.5 against the engine's 10 1/2 and 33 7/8 (closes the 13.5 question). CF5: the engineer types the elevation
  size and the sheet prints -1/16 for a butt joint (GODDARD 15 5/8 x 91 7/8 -> 15 9/16 x 91 13/16); held on 23 of 26 lines
  (POLONSKA flip-ups typed 1/2 under KCD's size, drawer faces per a "FULL OVERLAY 37 3/8" note). `kcdcab` has not been
  tested against those elevation sizes (section 11 proved it against the price review, where a pair is half the face
  without the 1/8 gap); until it is, no door size can be written on a Doormark / CF5 / Elements form, only CHECKed.
- VJT math (the sheet's formulas): single or bottom tray = euro-shelf width - 2, double top tray = - 3 (its hint text says
  -3 1/16), depth = drawer-box depth (12/15/18/21) - 1 5/8; insert names STANDARD, STANDARD W/ EARRINGS, EARRINGS; colours
  Aquamarine, Black, Blush, Champagne, Navy Blue, Silver. GODDARD: layout 2, shelf width 28 1/2, depth 15 -> 26 1/2 x 13 3/8
  and 25 1/2 x 13 3/8. NEDDIE hers: JT Standard + JT Standard Earring on unit 16 (96 Tall 6 Drawer, W 31 1/2, D 16, shelf
  width 30), champagne, wall note "top drawer is double jewelry drawer".
- PO rules seen: handles split DOOR / DRAWER with part number and vendor, counts = the drawn faces (WERNER `6 DOOR BP36559CZ
  AMEROCK`; PRIEM `2 DOOR` + `4 DRAWER 110.93.461 HAFELE`); chrome stock rods never appear, Square Matte Nickel / Syn Matte
  Gold poles do (by the stick: GODDARD 7 for 14 poles); sidebar part numbers (tie rack, shoe fence, slatwall, murphy
  hardware); sheet goods the engineer computes (1/4" CF5 insert sheets, mica, thinscape, stiffeners); never doors, slides,
  base/crown, cleats, levelers. The vendor is not in the job (`BP...` is both Amerock and Richelieu). CNC price = pricing
  subtotal + 199 on the main room (11 rooms). Pricing-sheet accessories are typed from the sidebar at workbook prices (MELA
  base 30 / crown 95, DES WHT 39 / 123.50, TH DECORATIVE 145 / 185, mica 57/sqft, quartz 88/sqft) with the engineer's
  quantities (POLONSKA base 11 / crown 13 against sidebar 9 / 14).
- **Doormark reference sheets (owner, Oct 20; `experiments/po/doormark_ref.py` -> `doormark_ref.json`).** The quick
  reference (1-15-25) lists 42 door designs with ordering code, door styles, drawer styles and minimum door width / drawer
  height (slab designs 6" / 2"-4.5"; round and square raised-panel 7"-8 1/8" / 5"-6", SRP only, ARP/CRP need 2" more;
  shakers 6" / 4.5", Panama 8", Tortuga 7" / 5"; applied Palm Beach / Vizcaya / Wellington 8" / 5 3/4-5 7/8; the Infinite
  shakers Jupiter / Largo / Vero 7 1/4" / 5"). The Funder cross-reference (2-03-2025) lists 33 foil colours with code,
  match-back availability and the melamine board colour each matches (so the sidebar's MATERIAL/COLOR maps to a foil: 363
  Apple Cocoa -> CHPE Chocolate Pear, 607 Bisque -> OWM, 955 Folkstone -> FOST or LIGR, 751 Midnight Mirage -> MYBL
  Mysterious Blue SM, 128 Fog -> FOGG or CAGR); no match back on 949M, FWM and ONWH (the so-door card's question).
  The Krono Select sell sheet (2-26) names 13 finishes (Brushed Aluminum, Amber Urban Oak, Brandy Castello Oak, Cashmere,
  Clay Grey, Grey Nordic Wood, Iron Surfside Ash, Light Select Walnut, Pure Surfside Ash, Ristretto Baroque Oak, Snow White,
  Stone Beige, White Coastland Oak) with NO ordering codes. Against the workbook's own tables: its 34 designs all resolve,
  but it lacks Capris, Fairway, Shaker Duluth, Holly Hill, Shaker Panama, Shaker Tortuga, Shaker Jupiter / Largo / Vero and
  still carries NASSAU (NAS), which the quick reference no longer lists; of its 18 colour names 11 match the Funder sheet
  and 7 do not (Almond AM, Black BLMA, Black Gloss BLGL, Fog as FOG where Funder says FOGG, Hudson Cherry with no code where
  Funder has HUDS, Lewis LEWI, Tenino Grey TEGR), and 22 Funder colours are missing from it, Mysterious Blue MYBL among
  them: the MYST typed on WERNER's Doormark form is not a code on either sheet. The fill will use the sheets' codes and
  flag a colour or design that is only in the workbook's table.

### 16.3 Fillers at both ends (`experiments/po/fillers.py`, report only)

- Definition used: a wall end is closed when another live wall continues from it (`free_end`), open when the wall simply
  stops; a run is between two walls when it reaches (within 1/8) a closed start AND a closed end. Each closed end is classed
  by the neighbour wall: `wall` (bare within 30"), `zone` (the neighbour's run set back 23-26" with a connecting shelf in
  the corner: the designers' corner convention), `side` (an L-corner unit), `casing` (an opening at the corner), `angled`.
- Data: designer files (14 jobs), 51 closed ends a run touches: wall 20 with a filler / 7 without, zone 9 / 7, side 1 / 0,
  casing 0 / 1, angled 0 / 6. Single wall-to-wall runs always had both fillers (COYNE Linen, Guest, Primary; DRUBEL;
  BINDLER; GODDARD; POLONSKA). The 7 bare ends without: HUMPHREY walls 1 and 4 starts, ROBERTS guest wall 6 end, NEDDIE his
  wall 8 end, COYNE Primary 15 start (a 2 3/8 jog), POLONSKA walls 1 and 4 (L-corner units). Designer against engineer on
  31 ends: the engineers added no end filler (0 of 11), kept 18 of 20, dropped 2 (GODDARD, a copied unit set), changed
  widths ROBERTS 1" -> 3/4, MIRANDA 1 1/2 -> 3/4, POLONSKA 3/4 -> 7/8, WERNER 3/4 -> 1 1/2 at a door casing. So the rule is
  new practice at L back corners and on three reach-ins. FIX candidates: NEDDIE his wall 8 end (Mid Hang 27 5/8 -> 26 7/8,
  filler at 141 1/4 under the old one-unit rule), HUMPHREY walls 1 and 4, ROBERTS guest wall 6 end; zone and angled corners,
  drawer units, catalog units (hutch, L corners, wall bed), stacks and connecting shelves across the end stay CHECK.

### 16.4 Adding a filler record to a job (`experiments/po/addfiller.py`, `reserve.py`; TEST3)

- Unit ids = position in the file (all 7 files, deleted records included); only `nunits` and L[2]/L[3]/L[4] depend on the
  unit count; nothing per room counts units; a filler has no settings pairs. The fillers of a job are identical except
  wall id, slice and room points; suffix +12/+14/+16 = id x3, +4 a copy/paste batch number (0 written). On all 8 designer
  fillers: H = the neighbour cabinet's H, From Wall = neighbour D - 3 (9 by 12" hangs, 13 by 16" talls). A plain filler's
  cache entry is 230 vertices, 26 faces, 103 index ints, a library constant (the same bytes in NEDDIE and COYNE). New: the
  index block is 16 (designer builds) or 20 (the owner's KCD) ints shorter than the slices claim: one early unit's chunk is
  written short and every later unit's data sits 16 ints before its slice offset; the prototype keeps that constant and
  only clones a source proven complete (known chunk or identical twin).
- Recipe: the source filler's bytes with the X / H / From Wall slots, the wall id, a new slice, room points recomputed on the
  target wall, the same room's Set Unit Info, id n+1, appended last; its vertices, index ints and faces cloned, rotated and
  translated onto the wall, appended at the ends of the three arrays; header counts bumped; everything else byte-identical.
  Verified by re-parsing (sections, slices tile, kcdwalls lists it, kcdcompare shows only the growth). Only KCD can prove it
  opens: this is the first time the unit count grows (header blob and n1 block are opaque).
- `reserve.py` makes the room: `unit_step` with a pseudo wall 3/4 shorter at the end, so the hanging sections share the
  3/4 (14.3 rule) and the rest slides, then the room points and the cache like `set_wall_lengths`.
- TEST3 (`out/Lynn Neddie - REM 1090111 applied + his wall 8 end filler - TEST3.job`, md5 82ce2821...): TEST2 plus his
  wall 8: the four hanging sections 27 5/8, 27 5/8, 27 11/16, 27 11/16 -> 27 7/16, 27 7/16, 27 1/2, 27 1/2 (interiors
  26 11/16, 26 11/16, 26 3/4, 26 3/4), the 96 Tall 5 Drawer 56 -> 55 5/8, 897 face width values redone, a cloned filler
  (unit 53, X 142 1/8, H 95 1/4, From Wall 9) appended; 862,295 -> 869,489 bytes; no CHECK. Sent to the owner to open
  without touching anything and save back. His walls 11 and 12 (one unit each filling a 30" wall between two walls) were
  left for his answer.

### 16.5 Open with the owner (the short list)

**Answered by the owner (Oct 20):** the order tabs are filled INSIDE each room's own workbook (one `.xlsm` per room with its
Purchase Order, Doormark, CF5, VJT ... tabs filled); hamper fronts and flip-up fronts COUNT AS DOORS (faces on the forms and
handles on the PO); the sidebar says when a thermofoil door is CF Thermo, and CF Thermo is no longer sold (a few sold jobs
remain to be engineered), everything else thermofoil is Doormark; Mysterious Blue is MYBL (Funder sheet), WERNER's MYST was
a typo. TEST3 (his wall 8 filler) opened in KCD and was saved back unchanged on wall 8: adding a unit record works (the save
shows only KCD's usual re-save changes: header blob, n1 36 -> 45, the index block 16 -> 20 ints short, the hers room
re-placed). The owner also noted the filler was added in one room only (hers wall 1 end is a `zone` corner, held as CHECK)
and asked for "another one" with everything learned today.

- Fillers: the back corner of an L/U where the other wall's run starts 24" out with a connecting shelf, filler or not;
  angled corners; one unit filling a wall between two walls (his 11 Long Hang, his 12 drawer tall): two fillers and the
  unit gives up 1 1/2, even a drawer unit; who gives up the 3/4 when there are no hanging sections (the end unit, the next
  one past a drawer tower); a door casing 3/4 or 1 1/2 (WERNER); designer fillers of 1" / 1 1/2" made 3/4.
- Forms: fill the order tabs inside the same `.xlsm` (yes/no); PO counts from the drawn faces or the sidebar; hamper fronts
  and flip-ups counted as faces and handles; when a TH door goes to Doormark against the CF Thermo form; MYBL or MYST for
  Mysterious Blue and the full Doormark colour list; the part-number -> vendor list and numbers (or "stock") for Valet CR /
  Belt CR / Tie CR / Lock Magnetic / Socket PU / Mirror Back; which rods are stock; the VJT double top tray -3 or -3 1/16;
  the 4" slab-filler height; is B13 `Special Order` for every velvet tray.
- Files: the TEST3 save from KCD; WERNER's ENG packet (its door-size elevation); `options.dat`; a filled Elements and a
  filled CF Thermo form with their jobs; the Doormark quick reference; the A/B save (one unit with and without a door) so
  the file tells which units have doors; MIRANDA's PO.

### 16.6 Wired into the main run; the one-command chain; the production project (Oct 20, 2026)

What changed today, and what was proven:

- **The filler rule runs inside `kcdwalls.py`** (`kcdfill.py`, on by default whenever a file is written; `--no-fillers`
  turns it off; `kcdwalls.py JOB --fillers --out OUT` runs it alone). Per FIX finding: pick a 3/4 source filler (same
  wall, then same room, then anywhere; engineer-style face-wide fillers are not usable), make the room by the same-size
  rule (`reserve.reserve_end`; new `reserve_start` mirrors it for the START of a wall: unit_step on a pseudo wall 3/4
  shorter with anchor 'end', then every X back to the real wall by +3/4, features put back where they were), clone the
  filler (`addfiller.add_filler`), re-run the rule. A failure on one finding is a CHECK; the output is written once.
  Proof: the NEDDIE designer job + its read-out now gives TEST3 (`82ce2821...`) byte for byte, i.e. apply + reserve +
  addfiller in one command; the KCD-saved TEST3 comes back unchanged with no FIX.
- **ROBERTS md5 explained**: the earlier "+ fillers" file (`fca0af81...`) was TEST1 + a hand `adjust.py` step on the
  three wall-14 Door units (the sheet's "door opening 24 3/16 at 68 11/16") + reserve + addfiller. The chain without
  the door step gives `956a19d0...`; adjust.py on that file gives `fca0af81...` byte for byte. The door-opening step
  stays a hand step (run book step 5): mapping the sheet's opening to the casing units is a judgment.
- **START case**: no job of ours has a START FIX (HUMPHREY walls 1 and 4 would, on the laptop). Synthetic cases (the
  start filler of NEDDIE his wall 8 removed or moved, the run slid to X 0) give the exact mirror of the END case:
  sections 27 1/2, 27 1/2, 27 7/16, 27 7/16 (extra sixteenths nearest the START), the tower keeps its width, the new
  filler at X 0..3/4; 191 invariant checks pass. Not yet through KCD.
- **`kcdrun.py`**: apply (+fillers) -> `kcdsplit.split_job` -> per room `sidebar.py` + `soitems.py` + `kcdbook.fill` ->
  RUN REPORT. Cell map used: Data Entry B5 order, B7 last name in capitals, B9 room (the room file's name; engineers
  shorten it: OFFICE, RIC, WIC), F1/B1/B27/B25 only when given, F5/F7/F9/F11/F21/F23 only as exact entries of the
  Data Conversions lists; Purchase Order row 19+ B room, C qty, D item, E part number (dashes removed), K vendor (only
  when the sidebar names it); Doormark A1 EM31 design (exact X3:X36 text), EM41 colour (exact X41:X58 text; MYSTERIOUS
  BLUE is not in the list, so blank + CHECK with the Funder code MYBL). Never written: door rows and sizes, slab
  fillers, CA31, VJT/CF5/CF Thermo/Cover Sheet cells, B15/B19/B21/B23/B13, vendors guessed from a part number's shape.
  WERNER answer key: every cell we write equals the engineer's (18 of 18 with designer/install/sold given); the
  engineer's other typed cells are the price paste (213), Q/R hand sizes (14), door rows, slab fillers, B15/B19/B21/B23,
  K19 AMEROCK (inferred), CA31 MYST (the owner's typo), Final Price Sheet accessory lines (countertop 35 1/8 sqft at 66,
  base thermofoil x3 at 145, the handle under Items That Need Pricing) and Cover Sheet N2 N/A, C11 7.
- **Policy decisions from the checks**: a value two sources disagree on is not written (sidebar BASE line vs the
  sheet's "Molding None" -> F21/F23 blank + CHECK); the sidebar wins over the unit texts for the door style (EM31
  SARASOTA SHAKER on WERNER while the units say Abacoa) but a CHECK names the disagreement; a light strip
  ('Invisible Light', type 1101, 4 wide) is an accessory, not a cabinet, for the filler rule; other customers' names
  never appear in a customer's report; the RUN REPORT carries the TEST number and is never overwritten.
- **`data/`**: the template and the library bundles live in the repo (not customer files) so a fresh checkout runs;
  the price list does not (laptop only), so pricing stays with the engineers unless a price TSV is given.
- **Production**: branch `production` = the tools as proven; `jobs/<order> <NAME>/` holds the dropped files (ignored by
  git); `run <order>` is the run book's step 0 and `kcdrun.py <order>` finds the files itself.
- Pre-existing bugs found by the checks and fixed: `apply_spread` crashed (KeyError) when a hanging section came out
  exactly unchanged (a 1/8 remeasure change did it); `shelf_fit` used a shelf's already-moved X as the old X for the
  cache update when unit_step had shifted it in the same run; `read_rem_json` dropped needs_review items that were not
  wall lengths (COYNE 5, WERNER 9) -> now CHECK lines.

## 8. Scripts (on the test laptop, `%TEMP%\kcdsplit`)

In the repo, `experiments/design/apply-remeasure-plan.md` and `apply-remeasure-critic.md` are the Oct 19 design plan for the
remeasure tool and its adversarial review (the critic found the anchor rule and the stale unit points). `kcdmesh.py` moves a
unit's entry in the 3-D drawing cache (notes 14.8).

- `kcdunits.py` (in this folder) is the reader to use from now on: `python kcdunits.py --lib C:\KCD23 JOB.job`
  prints the room sheet; `Catalog.from_json` takes the compact catalog made by `experiments/catjson.py`.
- `report.py` (copy in `experiments/report_laptop.py`): for the given jobs, decodes every unit with the
  `.cab` slot labels, the settings pairs, room defaults, handles and notes into `out\sizes_<job>.txt`;
  also writes `out\catalog_cabs.tsv` and `out\catalog_slots.txt` from the extracted library.
- `libprobe.py`, `libprobe2.py`: first look at the library and pricing files.
- `bundle.py`: packs the catalog and raw unit records as gzip+base64 text chunks.
- `rawlib.py`: bundles every text file of the unit library (`.cab .cld .mld .lst .dat`) into
  `out\rawlib.b64` (json, gzip, base64) for `Catalog.load_rawlib_json` in the sandbox.
- `engine\` holds copies of `kcdjob.py`, `kcdunits.py`, `kcdprice.py`, `kcdcab.py`, `compare_keys.py`
  (md5-checked with `md5check.py`; `blockmd5.py` finds which 50-line block differs, `fixnl.py` restores a
  lost blank line; `patch_engine.py`, `patch_engine2.py` apply exact-text patches instead of re-uploading);
  `runcmp.py` runs the comparison with the June 2025 list, `runprice.py` prices jobs into `out\eng\`;
  `runcmp2.py OUTNAME [LIBROOT] [PRICEDIR] [NAME...]` and `runprice2.py OUTSUB [LIBROOT] [PRICEDIR] [NAME...]`
  take any library root and price list (defaults: the OneDrive KCD23 copy and the May 2026 list).
- `runcmp3.py OUTNAME LIBROOT "DIR1;DIR2;..." [NAME...]` runs `compare_keys.py` with several price-list folders
  layered in order (the full list first, then the update packs) and reports the price check too.
- Ten-set tools (section 13): `pinjobs.cmd` / `robojobs.cmd` pin and copy the sets to `%TEMP%\kcdjobs10`;
  `survey10.py` -> `out\survey10.txt`; `keys10.py` -> `out\keys10.txt`; `runcmp4.py OUTNAME LIBROOT PRICEDIRS [NAME...]`
  compares the engineered room files with their pastes; `runcmp5.py` does the same with the designer's job
  (`DESIGNSUBSTR=SECTION`); `rempng.py` / `rem2jpg.py` render the scans; `trace1.py` and `traceunit.py KIND SUBSTR
  SEQ [PATTERN...]` trace the engine on one job or one unit; `pcbline.py LIST FILE A B` and `grepprice.py LIST
  REGEX` read the price scripts; `cabfaces.py NAME.cab [all]` prints a library unit; `wallpos.py` shows unit
  positions and wall contact; `dumpraw.py` dumps a unit record; `hexdump.py` any file; `patch_engine6.py` applied
  the 1/16" rounding to the laptop engine copy (md5s equal the repo).
- Laptop venv `%TEMP%\kcdvenv` (openpyxl, pypdf, PyMuPDF); the system Python has PIL and pypdf but no openpyxl.
- `odstatus.py` counts cloud-only placeholders per OneDrive folder; `survey_kcd23.py` lists the KCD23 tree;
  `a3scan.py`, `dumpunit.py`, `dumpunit2.py` dump unit records (the byte-6 survey of section 12);
  `check4.ps1`, `acc_check*.ps1`, `pinroot.cmd`, `pinlists.cmd`, `robopacks.cmd`, `robolists.cmd` pin and copy
  OneDrive folders.
- Price-list copies: `%TEMP%\kcdprice\{SEP25,OCT25,DEC25,JAN26,FEB26,MAR26,APR26,MAY26,MAY22,JUL26,AUG26}`
  (every `STDPLIST` CFFL pricing folder from Sept 2025 on).
- Library copies used: `%TEMP%\kcdlib` (ENG UPDATE 25-03-06), `%TEMP%\kcdprice` (JUN 25-06-05 pricing),
  `%TEMP%\kcdlibod` (the shop's seven unit libraries from OneDrive, text files only) and
  `%TEMP%\kcdprice\MAY26` (the `_26-05-03 MAY CFFL PRICING` list).
