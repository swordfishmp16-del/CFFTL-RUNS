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

Result (`runcmp2.py cmp_may26`, 19 rooms, 1067 pasted lines): **765 identical (71.7 %)**; the Sept 2024
list on 12 of those rooms gave 614 of 856. Rooms: GARAGE 58/83 (every door now to the sixteenth except one
17 9/16 against 17 1/2), GARAGE CO 9/9, TILLIS HIS 88/106, BURNS 98/127, HIS 118/160, OFFICE 45/98,
PANTRY 53/82, HER CO 23/30, WIC CO 33/60.

What still differs, by size:
- door lines the engine prints and the paste lacks (drawer towers `CSE304/305`, shelving towers
  `CSE300-96`, entertainment units `773-96` and `772`, `CSE101stacked`): the designer's "no door" choice
  is still not found in the record (section 7), so every engine door line stays VERIFY;
- accessory units print `call for quote`: the record's pcb (`CFClosetAccessory.pcb`,
  `Z12inEliteValetRackMG.pcb`, `Zkcd3003144BLK.pcb`) is not in the 2026 list and the library fallback found
  no replacement; being checked;
- L-shaped cabs (`C271`, `C272`, `C171`, `CSE101stacked`): the "3rd panel" and back dimensions come out
  swapped against the paste and four adj shelves are missing (their points use the shop size `sctovlp` and
  extra values `e5`/`e6` that live in `.cld` load blocks, both unmapped);
- PANTRY pullout tray wording (`...included 6 1/4"-lino cancun grain16` pasted, `...grain` from the
  engine) and the OFFICE unit 5 drawer-front count;
- kick, filler, leg-leveler and mirror-back column placement (section 10), and the CO rooms whose pastes
  the engineers edited by hand.

## 8. Scripts (on the test laptop, `%TEMP%\kcdsplit`)

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
- `odstatus.py` counts cloud-only placeholders per OneDrive folder; `survey_kcd23.py` lists the KCD23 tree.
- Library copies used: `%TEMP%\kcdlib` (ENG UPDATE 25-03-06), `%TEMP%\kcdprice` (JUN 25-06-05 pricing),
  `%TEMP%\kcdlibod` (the shop's seven unit libraries from OneDrive, text files only) and
  `%TEMP%\kcdprice\MAY26` (the `_26-05-03 MAY CFFL PRICING` list).
