# OLD SCHOOL JEWELRY TRAY APP - Handoff

Project: Jewelry Trays Direct (JTD). Owner: Mike Policy, Closet Factory FTL. Written Oct 7, 2026 (ET) for the new assistant "OLD SCHOOL JEWELRY TRAY APP".

How to read this:
- **[CHAT]** = said in a conversation (JEWELRY TRAYS DIRECT bot or BIG HOSS), with the date.
- **[FILE]** = read straight from a file. Nobody discussed it in chat.
- **[SKILL]** = from the saved skill `jewelry-trays-woodwop/SKILL.md`, which the JTD bot wrote from the 8/29/2026 work.
- Quotes are exact. Math in the worked examples uses the sheet's own formulas and WOODWOP's own formulas.
- **CONFLICT** = the conversation and the real files disagree. Both versions are given. Do not pick one without asking Mike.

## 1. PURPOSE

- [CHAT 8/29/2026] JTD is "jewelrytraysdirect.com ... a Shopify store selling custom USA-made jewelry trays for drawers and closets, including a wholesale program for cabinet makers, closet companies, designers, and dealers."
- [CHAT 8/29/2026] What Mike asked the JTD bot to do. First: "IF I HAVE A TAB OPEN WITH WOOD WOP RUNNING CAN YOU FILL IN THE SPACES IF I SHOW YOU THE ONES I WANT". Next: "I ALSO NEED A FINALIZED MPR". Then: "PRINT A SCREEN SHOT OF THE FINISHED WOOD WOP SHEET AFTER ALL SIZES ARE ENTERED AND THAT DESCRIPRION ADDED ON TOP OF THE CORRESPONDING TRAY".
- [CHAT 8/29/2026] Mike then said: "ALL THIS LOOKS GOOD CREATE A SKILL WITH ALL OF WHAT WE HAVE DONE".
- [CHAT 9/1/2026] Shopify: "can i link you into our shopify site to run a report only that is how the excel you used earlier is populated"
- [CHAT 10/2/2026, BIG HOSS; transcript not available, see Sources] Mike wanted stick lengths for tray sticks. The result file is quoted in full in section 10.
- The sources never say what the new app itself should do. The workflow below is how the work is done today.

Today's daily flow, as a subagent found it on the shop PC [CHAT 8/29/2026]:
> "Manual. No WOODWOP–Excel link.
> 1. Shopify export CSV into the daily folder
> 2. Copy/update `JEWELRY TRAYS FILE …xlsm` (order + inch W×D)
> 3. Fill `MMDDYY DAILY TRAYS.xlsx` inches on top; mm block auto-converts
> 4. Copy that mm table into a daily MPR cloned from `_2 TALL` / `_3 TALL` / stock templates
> 5. Drop the MPR in `L:\JEWELRY TRAYS BOARDS TO BE CUT` and open it in WOODWOP"
## 2. TRAY TYPES & PARTS

**Tray products.** [FILE `shopify_export_100226.csv`, column "Lineitem Title", count of rows in that export (454 rows, orders 3686–4367)]

| Lineitem Title | Rows |
|---|---|
| Standard Jewelry Tray | 108 |
| Standard Tray With Earrings | 82 |
| Tray Insert | 49 |
| Watch and Bracelet Tray | 34 |
| Sunglasses Tray | 33 |
| Valet Tray | 22 |
| Custom Designed Trays | 18 |
| Flat Liner | 17 |
| Tie and Belt Tray | 16 |
| Earrings Tray | 16 |
| Ring Cushion | 14 |
| Necklace Tray | 13 |
| Watch Pillow Add-On | 12 |
| Plain Tray | 12 |
| Tray Measurement Charge | 8 |

"Lineitem Name" adds color and size class. Real examples: "Standard Jewelry Tray - Champagne / Custom Large", "Standard Jewelry Tray - Blush / Small 22"W x 13 3/8"D", "Standard Jewelry Tray - Silver / Medium 28"W x 13 3/8"D", "Custom Designed Trays - Medium / Navy", "Tray Insert - Watch/Bracelets", "Tray Measurement Charge - Extra Tray Height (3")". Colors seen: Champagne, Black, Blush, Silver, Navy.

**Divider types in the master workbook.** [FILE `JEWELRY TRAYS FILE 100226.xlsm`, sheet "Sheet1"] Rows: EARRING (Earrings Tray), SUNGLASS (Sunglasses Tray), NECKLACES (Necklace Tray), WATCH AND BRACELETS (Watch and Bracelet Tray), TIE AND BELT (Tie and Belt Tray). "MINIMUM" opening WIDTH / DEPTH in inches:

| Type | Min width | Min depth |
|---|---|---|
| Earrings Tray | 2 | 2 |
| Sunglasses Tray | 6.75 | 2.75 |
| Watch and Bracelet Tray | 3.75 | 3.75 |
| Tie and Belt Tray | 4.75 | 4.75 (from sheet "calculo" I/J) |
| Necklace Tray | uses 2.25 spacing (calculo R) | — |

**Tray types in a later draft workbook.** [FILE `_jtd stuff\Tray Calculator.xlsx`, sheet "Types", dated 2/20/2026. A draft. Its "Orders" sheet shows #VALUE! errors.]

| Tray Type Base | Min LR | Min FB | Has Inserts? | Insert Type |
|---|---|---|---|---|
| Standard Tray | 3 | 3 | 0 | None |
| Earring Tray | 2 | 2 | 1 | Earring Pad |
| Valet Tray | 5 | 10 | 0 | None |
| Sunglass Tray | 6.75 | 2.75 | 1 | Sunglass Holder |
| Standard with Earring Tray | 2 | 2 | 1 | Earring Pad |
| Necklace Tray | 2 | 8 | 1 | Necklace Hook |
| Watch and Bracelet Tray | 3.75 | 3.75 | 1 | Watch Pillow |
| Tie and Belt Tray | 4.75 | 4.75 | 0 | None |
| Plain Tray | 0 | 0 | 0 | None |

**Parts of one tray.**
- **Sides.** The WOODWOP templates cut all 4 sides of one tray from one strip: width, depth, width, depth. See section 5. [FILE templates]
- **Bottom.** Daily sheet: PART TYPE "TRAY BOTTOM", MATERIAL "1/4 MELAMINE", GRAIN "N", COMPANY "JEWELRY TRAYS DIRECT". [FILE daily xlsx] The subagent said bottoms are cut in CutRite: "Bottoms: `JEWELRY TRAY BOTTOMS 2026.xlsx`, `JEWELRY TRAY BOTTOMS WHIPS DIVIDERS.xlsx` (CutRite bottoms, not WOODWOP vars)". [CHAT 8/29]
- **Dividers.** Header text from the xlsm: "LEFT TO RIGHT DIVIDER NEED 1 PC/ 1 1/4 HIGH", "FRONT TO BACK DIVIDERS NEED 2 PCS / 1 1/4 HIGH", "LEFT TO RIGHT DIVIDERS NEED 3 PCS ONE 1 1/4 AND TWO 3/4 HIGH", "FRONT TO BACK W/ NOTCH NEED 2 PCS FOR RING HOLDERS", "LEFT TO RIGHT DIVIDERS NEED 2PCS ONE 1 1/4 AND ONE 3/4 HIGH". Divider thickness is 0.4375 in ("Thickness"). The draft calculator says "Thick 7/16"". [FILE]
- **Velvet.** WOODWOP global `v` is "velvet allowance" = 4.76. [CHAT 8/29 + FILE]

**Heights.**
- 2" uses `_2 TALL`, th=49.21. 3" uses `_3 TALL`, th=73.03. [SKILL]
- A 4" template exists: `_4 TALL 36IN TRAYS.mpr`, h=102 "box hight". [FILE]
- Shopify "Height" values in the 10/2 export: 2 (283 rows), 3 (6), 4 (1), 5 (1), blank (163). [FILE]
- 8/21 sheet: "3996 - 5IN TRAY". [FILE/CHAT]
## 3. INPUTS (units, ranges)

**A. Shopify export** [FILE `shopify_export_100226.csv`, 10/2/2026]. It has 8 columns:

```
Order ID | Order Number | Lineitem Name | Lineitem Quantity | Lineitem Title | Width | Height | Depth
```

- Width and Depth are text in inches, written as fractions. Examples: "28 1/4", "22 5/16", "12 1/16", "16 11/16", "21 5/16".
- Height is "2", "3", "4", "5" or blank.
- 163 rows have no width. These are add-ons, inserts, and fixed stock sizes whose size is in the name, e.g. "Small 22"W x 13 3/8"D".
- Real row: order 4354, "Custom Small", Width 21 5/16, Height 2, Depth 14 1/8.
- [CHAT 9/1/2026] Mike asked for a Shopify "report only" link. Later he said: "WE ARE NOT GOING TO BE SIGNING IN WE WILL PICK THIS UP LATER". Shopify is **not connected**.

**B. Master order workbook** [FILE `JEWELRY TRAYS FILE MMDDYY.xlsm`, visible sheet "Jewelry Trays"]
- Row 4 headers: Order Number, Lineitem Name, Lineitem Quantity, Lineitem Title, Tray Width, Tray Height, Tray Depth.
- Data starts at row 6. Inches are stored as decimals, e.g. 25.375 / 2 / 16.375.
- D2 holds `=TODAY()`.

**C. Daily sheet** [FILE `MMDDYY DAILY TRAYS.xlsx`, Sheet1]
- A1 says "FILL IN INFORMATION HERE ".
- Inputs start at row 3:
  - **A** "CUSTOMER # ONLY" (the order number)
  - **C** "WIDTH" in decimal inches (e.g. 21.3125)
  - **D** "X"
  - **E** "DEPTH" in decimal inches
  - **G** "DESCRIPTION". Defaults to A. Can be typed over, e.g. "2391 - 3IN TRAY", "4357 - 2X STOCK 22IN", "2392 - 11X".
  - **L** "QTY"
- Formula rows run 3–53. The mm block has slots 1–51.
- A61 = 0.5625 is a constant input, labeled "for bottom conversion" in A60.

**D. Units.**
- Shopify, the xlsm and the daily sheet are in **inches**.
- WOODWOP files are **metric**. The MPR header has `INCH="0"`, and Mike's variable table shows mm. [FILE + CHAT 8/29]
- [SKILL] "Do NOT type the inch columns (C/E) into WOODWOP."

**E. Fractions vs decimals.**
- Shopify gives fractions as text. The sheets hold decimals.
- How Shopify text becomes decimals in today's xlsm is **NOT DISCUSSED**. Existing files show only the results.
- The draft `Tray Calculator.xlsx` has a parser for this. It is a draft with errors; see section 10.

**F. Size ranges.**
- No min/max size limits were discussed.
- From real sales [FILE `JTD_TRAY_SIZE_LISTS_2026-10-02.txt`]: the common bands run from 12 to 26 deep and from 16 to 38 wide. "Everything else is 9 or fewer."
- The smallest tray-size openings are in section 2.
## 4. MATERIALS & STANDARD SIZES

**Board (tray side stock)** [FILE templates; SKILL]

- `_BSX="2438"`, `_BSY="1219.2"`, `_BSZ="10"` (mm). Variables: `l="2438"` (length), `w="1219.2"` (width), `t="10"` (thickness).
- [SKILL]: "2438×1219.2 mm (96×48 in)".
- The `_4 TALL 36IN TRAYS.mpr` board is `_BSX="2348.4"` × 1219.2.

**Tooling / allowances** (from WOODWOP globals, each with its own comment) [FILE + CHAT 8/29]

| Var | Value | KM comment |
|---|---|---|
| c | 12.7 | 1/2 inch bit |
| th | 49.21 (2") / 73.03 (3") | tray hight |
| v | 4.76 | velvet allowance |
| b | 6.35 | bottom space and groove |
| h | 47.625 (2"/3" templates), 102 (4" template) | box hight |
| s | 337.55 (2"/3"), 487.4 (4") | side |
| f | 555.625 (2"/3"), 914.4 (4") | front and back |

In the 2"/3" tray programs, `b`, `h`, `s` and `f` are declared but not used in the tray contours. The `_4 TALL 36IN` program does use them.

**Trays per board** — **CONFLICT**

- [SKILL / CHAT 8/29] "12 trays per board. First 12 rows → first MPR; rows 13+ → next board". Mike: "IT GOES UPTO TRAY 12" (that was his 3" table).
- [FILE] `_3 TALL DAILY TRAY TEMPLATE.mpr` has tr1–tr12 (12 trays).
- [FILE] `_2 TALL DAILY TRAY TEMPLATE.mpr` has tr1–tr16 (**16 trays**). Mike's real 2" boards from 10/2 (`100226 DAILY TRAYS 1/2.mpr` and the STOCK boards) all have 16.

**Bottoms** [FILE daily xlsx]: "1/4 MELAMINE", GRAIN "N".

**Stock (standard) trays** [FILE 100226 folder + daily xlsx]

- STOCK 21IN, 22IN, 27IN, 28IN, 33IN, 34IN. All are 13.375 in deep.
- Each has its own 16-up 2" MPR: `3 STOCK 21IN` … `8 STOCK 34IN`.
- `9 STOCK 3IN.mpr` has 12 trays of 863.60×339.73 (34 × 13.375 in) at th 73.03.
- Shopify fixed names: "Small 22"W x 13 3/8"D", "Medium 28"W x 13 3/8"D".

**Wholesale fixed sizes** [FILE `L:\JEWELRY TRAYS DIRECT FILES\RICHELIEU - JTD Program Pricing 1.xlsx`; see section 8]. Other stock-size files exist but were **not read**: `_B2B STOCK SIZES\` (e.g. `WHIP'S CARPENTRY JEWELRY TRAY SIZES-SKUS.xlsx`) and `__CF FTL STOCK SIZES\` (24/30/36 ES).

**Stick lengths from sales** [FILE `JTD_TRAY_SIZE_LISTS_2026-10-02.txt`, full text in section 10]

- Rule: "Stick = two depths + two widths + 1.5 inches on each end (3 inches total)."
- Final grouped sticks: 63, 75, 79, 87, 95 and 127 inch.
- Note that 127 in is longer than the 96 in board (my observation).

**Equipment leads (not read)**: `C:\Users\Mike.Policy\Downloads\_jtd buliding machines and racks\` holds stg 10726.pdf, storage racking .png, vorwood 6215 slitter.png and vorwood WL12.jpg (Oct 1–7, 2026).
## 5. RULES & FORMULAS

### 5.1 Inches → mm (daily sheet) [FILE]

There are two mm blocks in `MMDDYY DAILY TRAYS.xlsx`:

| Block | Location | Formula | Label on sheet |
|---|---|---|---|
| Bottoms block | M3 / N3 (rows 3–53) | `=IF(ISBLANK(C3),"",(C3-A61)*25.4)` / `=IF(ISBLANK(E3),"",(E3-A61)*25.4)` | under G1 "JEWELRY TRAY BOTTOMS "; A60 "for bottom conversion", A61 = 0.5625 |
| WOOD WOP block | E60 / G60 (rows 60–110, slot # in B) | `=IF(C3="","",CONVERT(C3,"in","mm"))` / `=IF(E3="","",CONVERT(E3,"in","mm"))` | E57 "MM CONVERSION FOR WOOD WOP" |

The two blocks always differ by 0.5625 in × 25.4 = **14.2875 mm**.

### 5.2 Which block feeds WOODWOP — **CONFLICT (biggest open item)**

- **Conversation FINAL** (Mike, 8/29/2026): "YOU WILL USE M3 TO START FOR THE TRAY WIDTH AND N3 TO START FOR TRAY DEPTH".
  - The skill locked this in: "M3 width mm → trNw ... N3 depth mm → trNd".
  - It says to ignore the E/G block: "(E/G there are ~14.29 mm larger — the 0.5625" bottom offset). File 1 was once filled from it by mistake."
  - This replaced the subagent's first reading on 8/29, which was: M/N = "(inch - 0.5625)*25.4 for bottoms, not WOODWOP".
- **Real files**: Mike's own production MPRs use the **E/G CONVERT** values.
  - `082126 DAILY TRAYS 1.mpr`: tr1 695.33×358.78 = CONVERT(27.375 / 14.125).
  - `100226 DAILY TRAYS 1.mpr` and `2.mpr` (10/2/2026). Example: 4354 → 541.34×358.78.
- So the conversation and the shop's own practice disagree. Ask Mike before you build.

### 5.3 Rounding [SKILL]

"Round to 2 decimals (e.g. 360.36, 484.19)." Real MPRs keep 2 decimals: "541.34", "863.60".

### 5.4 Filling a board [SKILL unless marked]

1. Take rows in Excel order. Row 3 → tr1, row 4 → tr2, and so on.
2. Repeat a row once per tray. Real sheets list one row per tray; the QTY is not expanded.
3. Fill "12 trays per board". The rest go to the next board (`… 2.mpr`). See the 12 vs 16 CONFLICT in section 4.
4. "Replace from tr12 down to tr1 so tr1 doesn't clobber tr10–tr12." This is a text-replace problem: `tr1w` is a prefix of `tr10w`.
5. Template choice:
   - Use `_3 TALL` (th 73.03) when G says "3IN TRAY". Otherwise use `_2 TALL` (th 49.21).
   - "Don't mix 2" and 3" on one board." A 3IN board uses the 3-tall template. Shop rule.
6. Slots with no tray stay `102`, which is the template placeholder.
7. Templates are read-only. Clone them; never edit them.
8. Stock trays go on their own boards using `tw`/`td` (section 10). [FILE 100226]

### 5.5 WOODWOP geometry for one tray [FILE `_3 TALL` template; same in `_2 TALL`]

Each tray is **one strip** that holds the 4 sides. Contour formulas for tray 1:

- Strip length X: `tr1w+tr1d+tr1w+tr1d+40-(v*4)`. Strip height: `th`.
- The strip outline starts at Y=8. A single line runs at Y=18, which is 10 mm up the strip. Its macro is TNO 130, depth ZA=5.
- Five vertical cut lines (TNO 134, ZA "sbc"). Each starts 2 mm below the strip and runs up `th+20`:
  - X = 20
  - X = 20+(tr1w-v)
  - X = 20+(tr1w-v)+(tr1d-v)
  - X = 20+(tr1w-v)+(tr1d-v)+(tr1w-v)
  - X = 20+(tr1w-v)+(tr1d-v)+(tr1w-v)+(tr1d-v)
- So the cut lines are spaced w−v, d−v, w−v, d−v, with 20 mm of strip left at each end.
- The outline is cut by TNO 128 in two passes: ZA=.5, then ZA=sbc.
- Strip pitch is **76 mm** on `_2 TALL` (tray 2 at Y 84/94) and **101 mm** on `_3 TALL` (tray 2 at 84+25 / 94+25).
- Tray 1 is at the bottom (Y≈8) and the last tray is at the top.

Why −v and the 20/40 mm: the only label is `v` = "velvet allowance". The reason was **NOT DISCUSSED**.

### 5.6 Kerf

**NOT DISCUSSED.** No kerf variable exists in any template. The only allowances are `v`, the 20 mm ends, and the stick list's "1.5 inches on each end".

### 5.7 Stick length (10/2/2026) [FILE size-lists txt]

"Sizes grouped within 2 inches. Stick = two depths + two widths + 1.5 inches on each end (3 inches total)."

- Each band uses its middle size. Example: "About 13 by 23 ... 75 inch stick", i.e. 13+13+23+23+3 = 75.
- "similar sticks grouped (within 4 inches). Length is the longest in the group."
### 5.8 Machining order in the 3" program [FILE `082926 DAILY TRAYS 1 3IN.mpr`, 96 macros]

The program runs in this order:
1. All 60 vertical cut lines: TNO 134, F 12, ZA sbc.
2. The 12 Y+10 lines: TNO 130, F 10, ZA 5, RK WRKL.
3. The 12 strip outlines, first pass: TNO 128, F 25, ZA .5, RK WRKR.
4. The 12 strip outlines, second pass: TNO 128, F 25, ZA sbc.

The full parameter blocks are in section 10. What TNO 128/130/134 are, and what "sbc" means, was **NOT DISCUSSED**.

### 5.9 Divider math (inches) [FILE `JEWELRY TRAYS FILE …xlsm`, sheet "calculo"; full formulas in section 10]

Constants:
- P1 = 0.4375 "Thickness" (divider)
- J1 = `=0.4375*2` (0.875) "Thickness x2"
- L1 = 0.8125

Per type:
- **Inside width (M):**
  - Earrings: `F−0.8125`
  - Tie and Belt, Watch and Bracelet: `F−0.875`
- **Inside depth (N):** `H−0.875` for Earrings, Sunglasses, Tie and Belt, Watch and Bracelet.
- **Openings across (AA):** `TRUNC((F−0.875)/(min+0.875),0)+1`.
  - min = 2 (Earrings), 6.75 (Sunglasses), 4.75 (Tie and Belt), 4.75 (Watch and Bracelet).
  - Note: Watch uses 4.75 here, but its minimum is 3.75 in column I.
- **Openings deep (AC):** the same with H.
- **Dividers (K, L):** if the computed spacing is below the minimum, use count−1, else use count.
- **Spacing (O), Watch/Tie:** a ladder by divider count K: `(F−1.75)/(K+1)` for K=2, then `2.1875`, `2.625`, `3.0625`, `3.5` and `3.9375` for K=3…7. Each step is +0.4375.
- **Spacing, Earrings:** `(M−0.4375·K)/(K+1)`.
- **Spacing, Sunglasses:** `(F−0.8125−X·0.4375)/(X+1)`.
- **Necklace:**
  - R = `TRUNC((F−0.875)/(2.25+0.875),0)`
  - S = `F−0.8125`
  - T = `(S−R·0.4375)/(R+1)`
  - Q = `H−0.875`
- **Output** (FINAL sheet → "Jewelry Trays" I/K/L/N): front-to-back count and length; left-to-right count and length. Only for these types: Necklace, Watch and Bracelet, Tie and Belt, Sunglasses, Earrings.

### 5.10 Labels [SKILL / CHAT 8/29]

- "G3 description / order # → label on tray".
- "If needed shorten G labels on the nest (e.g. `2391 - 3IN`) but keep the order #."
- The final look is in section 9.

### 5.11 Shop rules (keep these) [SKILL / CHAT]

- 12 trays per board. Rows 13+ go to the next board. (See the 16-tray CONFLICT in section 4.)
- 2" and 3" never on one board. A 3IN board uses the 3-tall template.
- "Never overwrite an MPR that is open or belongs to another day."
- Templates are read-only.
- Writing files: on 8/29 the bot saved to `L:\JEWELRY TRAYS BOARDS TO BE CUT\` and to the daily folder. Mike then said: "SAVE THIS IN YOUR SKILL I DO NOT WANT YOU WRITING TO FILES ON THE L DRIVE EVER". Then: "AS WE DO MORE WORK I WILL CREATE A FOLDER FOR US TO USE UNTIL THEN WE DO NOTE WRITE ANYWHERE".
  - **FINAL**: write nothing until Mike names a working folder. Both messages came after the 8/29 board and before the 9/1 Shopify request; the exact dates were not recorded.
- Drive letters L: R: S: W: must stay mapped. Never disconnect or remap them.
## 6. WORKED EXAMPLES

Use these as test cases. The inputs and the sheet/MPR values are copied from the files. The strip and cut-line numbers come from applying the template formulas in 5.5 to those values (v = 4.76).

### Example 1 — Order 2362, 8/29/2026 board (M/N route, the conversation's FINAL rule)

Source: [FILE] Mike's 8/29 attached daily sheet, row 3, and the bot-made `082926 DAILY TRAYS 1 3IN.mpr` tray 1.

| Step | Formula | Value |
|---|---|---|
| Input C3 / E3 (in) | — | 14.75 / 19.625 |
| M3 | (14.75 − 0.5625) × 25.4 | 360.3625 |
| N3 | (19.625 − 0.5625) × 25.4 | 484.1875 |
| Round 2 dp → MPR | tr1w / tr1d | **360.36 / 484.19** |
| (E60/G60, not used) | CONVERT | 374.65 / 498.475 |
| Strip length | 360.36+484.19+360.36+484.19+40−(4.76×4) | 1710.06 mm |
| Strip height | th (3-tall template) | 73.03 |
| Cut lines X | 20; +355.60; +479.43; +355.60; +479.43 | 20, 375.60, 855.03, 1210.63, 1690.06 |
| Label | G3 = A3 | 2362 |

Gotcha: 2362 has no "3IN" in G. Only rows 11–14 (2391) say "2391 - 3IN TRAY". Even so, all 12 rows went on a 3-tall board, which breaks the no-mixing rule. See section 11.

### Example 2 — Order 4354, 10/2/2026 (E/G route, Mike's real production MPR)

Source: [FILE] `100226 DAILY TRAYS.xlsx` row 3, `shopify_export_100226.csv`, and `100226 DAILY TRAYS 1.mpr` tray 1.

| Step | Formula | Value |
|---|---|---|
| Shopify Width / Height / Depth | text | "21 5/16" / "2" / "14 1/8" |
| Sheet C3 / E3 (in) | decimal | 21.3125 / 14.125 |
| M3 / N3 (bottoms) | (x − 0.5625) × 25.4 | 527.05 / 344.4875 |
| E60 / G60 | CONVERT(x,"in","mm") | 541.3375 / 358.775 |
| MPR tr1w / tr1d (actual file) | — | **541.34 / 358.78** (= E/G rounded) |
| th | 2-tall | 49.21 |
| Strip length | 541.34+358.78+541.34+358.78+40−19.04 | 1821.20 mm |
| Cut lines X | 20; +536.58; +354.02; +536.58; +354.02 | 20, 556.58, 910.60, 1447.18, 1801.20 |

Rows 3–5 hold 4354 three times. In the MPR, tr1–tr3 are all 541.34×358.78.

### Example 3 — Order 4351 dividers, Watch and Bracelet Tray (10/2/2026)

Source: [FILE] `JEWELRY TRAYS FILE 100226.xlsm`, row 6, values exactly as stored. F = 25.375 W, G = 2 H, H = 16.375 D.

| Cell (calculo) | Formula | Value |
|---|---|---|
| I6 / J6 min | Watch → 3.75 | 3.75 / 3.75 |
| AA6 openings across | TRUNC((25.375−0.875)/(4.75+0.875),0)+1 = TRUNC(4.36)+1 | 5 |
| AC6 openings deep | TRUNC((16.375−0.875)/5.625,0)+1 | 3 |
| AB6 / AD6 | Watch branch unreachable → FALSE | FALSE |
| K6 | IF(AB6<I6, AA6−1, AA6) → FALSE<3.75 is FALSE | 5 |
| L6 | IF(AD6<J6, AC6−1, AC6) | 3 |
| M6 | 25.375 − 0.875 | 24.5 |
| N6 | 16.375 − 0.875 | 15.5 |
| O6 (K=5) | (25.375 − 3.0625)/(5+1) | 3.71875 |
| P6 (AC=3) | (16.375 − 2.1875)/3 | 4.7291667 |
| FINAL / Jewelry Trays I6, K6, L6, N6 | — | 3 Pcs, 15.5, 5 Pcs, 24.5 |

### Extra check — stock board and stick length

- `100226 DAILY TRAYS 8 STOCK 34IN.mpr` [FILE]: tw = 863.60 (34 × 25.4), td = 339.73 (13.375 × 25.4 = 339.725).
  - Strip = 2×863.60 + 2×339.73 + 40 − 19.04 = 2427.62 mm. That is less than the 2438 mm board.
- Stick list [FILE]: "About 13 by 23 ... 75 inch stick" = 13+13+23+23+3.
## 7. OUTPUTS (exact columns/fields/format)

**A. Daily WOODWOP program (.mpr)** [SKILL + FILE]

- Folder: `L:\JEWELRY TRAYS DIRECT FILES\{MMDDYY} DAILY TRAYS #{first}-{last}\`. Cut queue: `L:\JEWELRY TRAYS BOARDS TO BE CUT\`.
  - Under the FINAL rule, the app/bot writes **nowhere** until Mike names a folder (5.11).
- Names:
  - `{MMDDYY} DAILY TRAYS {n}.mpr` (2")
  - `{MMDDYY} DAILY TRAYS {n} 3IN.mpr`
  - Real stock names: `{MMDDYY} DAILY TRAYS {n} STOCK 21IN.mpr`, `… 9 STOCK 3IN.mpr`
- Format: WOODWOP text, header `INCH="0"`. Only the `[001` variable values change. Each is a `name="value"` line followed by a `KM="comment"` line:

```
tr1w="360.36"
KM="2362"
tr1d="484.19"
KM="tray 1 depth"
```

On the 8/29 board the bot put the G description into the width's KM, in place of "tray 1 width". Mike's own files keep "tray N width".

**B. Labeled nest print (PNG)** [SKILL]

- Name: `{MMDDYY} DAILY TRAYS {n}[ 3IN] WOODWOP LABELED.png`.
- Content: the WOODWOP 2D nest with each tray's G text on the tray (see section 9).

**C. Daily sheet "JEWELRY TRAY BOTTOMS" block** [FILE, Print_Area `Sheet1!$G$1:$J$21`]

| Col | Header (row 2) | Content |
|---|---|---|
| G | DESCRIPTION | `=IF(A3="","",A3)` or typed text |
| H | PART TYPE | "TRAY BOTTOM" |
| I | UNIT # | `=IF(A3="","",A3)` (stock rows: "STOCK") |
| J | MATERIAL | "1/4 MELAMINE" |
| L | QTY | 1, 2, 4 … |
| M | WIDTH | (C−0.5625)×25.4 |
| N | DEPTH | (E−0.5625)×25.4 |
| Q | GRAIN | "N" |
| R | COMPANY | "JEWELRY TRAYS DIRECT" |

The sheet also has a WOOD WOP block, E57:G110: slot # (B), order # (C), WIDTH mm (E), "X" (F), DEPTH mm (G).

**D. Divider report** [FILE xlsm "Jewelry Trays", Print_Area `$B$1:$N$146`, print titles rows 1–4]

- Headers: B Order Number, C Lineitem Name, D Lineitem Quantity, E Lineitem Title, F Tray Width, G Tray Height, H Tray Depth, I "FRONT TO BACK / NO NOTCH" (count), J "Pcs", K (length), L "# DIVIDERS LEFT TO RIGHT NOTCH" (count), M "Pcs", N (length).
- The "Report" button runs macro `Report`. It copies the sheet, pastes it as values, and AutoFilters columns 8 and 9 for non-blank.

**E. Stick list** [FILE `JTD_TRAY_SIZE_LISTS_2026-10-02.txt`]: a plain-text file with LIST 1, LIST 2 and LIST 3 (section 10).

**F. Leads not read:** the BIG HOSS fleet report (10/5/2026) says: "the laptop has tray-cutlist/preview PDFs (Oct 2-5), tray-bottoms.xlsx, JTD_TRAY_SIZE_LISTS_2026-10-02.txt and razor CSVs. They came out of the Jewelry Tray Calculator / Claude Code work on the laptop". Those laptop files were not read.

## 8. PRICING/COSTING

**NOT DISCUSSED** in any conversation. What the files show:

- [FILE] The Shopify line item "Tray Measurement Charge - Extra Tray Height (3")". 8 rows on 10/2. No price column in the export.
- [FILE `RICHELIEU - JTD Program Pricing 1.xlsx`, sheet "Jewelry Trays Proposal"] "Last modified: May 27, 2026". "Ship to:  Richelieu Warehouse in Pompano".
  - Columns: CODE, DESCRIPTION, VELVET COLOR, OUTSIDE DIMENSIONS W x D X H, EST. ANNUAL UNIT VOLUME, INV. to keep at JTD (3 mths) (`=G5/12*3`), MOQ, Leadtime (#Days), Unit Cost USD.
  - All rows: BLACK, MOQ 10, leadtime 3.

| CODE | DESCRIPTION | OUTSIDE W x D x H | Est. vol | Unit Cost USD |
|---|---|---|---|---|
| WIN1506211201 | VELVET LINER | 21-13/16" X 12-13/16" | 250 | 18 |
| WIN2306100701 | VELVET JEWELRY TRAY MINI 11X8 | 10-7/8" x 7-7/8" x 2" | 20 | 37 |
| WIN2306151201 | VELVET JEWELRY TRAY 15 5/8X12 5/8 | 15-5/8" x 12-5/8" x 2" | 350 | 48 |
| WIN2306161301 | VELVET PULL-OUT JEWELRY TRAY 14X18 | 16-13/16" x 13-27/32" x 2" | 100 | 50 |
| WIN2306161801 | VELVET PULL-OUT JEWELRY TRAY 18X18 | 16-13/16" x 18-3/16" x 2" | 25 | 55 |
| WIN2306211201 | VELVET JEWELRY TRAY 14X24 | 21-5/8" x 12-5/8" x 2" | 2100 | 55 |
| WIN2306221301 | VELVET PULL-OUT JEWELRY TRAY 14X24 | 22-13/16" x 13-27/32" x 2" | 650 | 65 |
| WIN2306221801 | VELVET PULL-OUT JEWELRY TRAY 18X24 | 22-13/16" x 18-3/16" x 2" | 325 | 70 |
| WIN2306271201 | VELVET JEWELRY TRAY 14X30 | 27-5/8" x 12-5/8" x 2" | 1000 | 58 |
| WIN2306281301 | VELVET PULL-OUT JEWELRY TRAY 14X30 | 28-13/16" x 13-27/32" x 2" | 400 | 74 |
| WIN230628101 | VELVET PULL-OUT JEWELRY TRAY 18X30 | 28-13/16" x 18-3/16" x 2" | 250 | 71 |

Packaging note in that file: "- ALL TRAYS MUST BE SHRINK WRAPPED. - APPLY THE BAR CODE LABEL TO THE SHORT SIDE OF THE JEWEL TRAY, CENTERED LEFT TO RIGHT. - PACK 10 PCS. PER CARTON". There is no material-cost or labor-cost formula anywhere.
## 9. LOOK & FEEL

**What "Old School" means: NOT DISCUSSED.** The phrase does not appear in any conversation or file I read.

What was discussed about how output should look [CHAT 8/29/2026 + SKILL]:

- Mike: "THE LAST PIC IS HOW I WANT THEM LABELED DIRECTLY ON THE WOOD WOP SHEET". The picture shows the WOODWOP 2D nest: a light-blue sheet with red strip outlines and cut lines. The order numbers 2362, 2363 and 2364 are hand-written in big black digits on the bottom three trays.
- [SKILL] "The print is the WOODWOP **2D nest** (light-blue sheet, red tray outlines), with G3 order numbers **on the trays**, same look as handwritten labels. Origin is bottom-left, so **tray 1 (`tr1`, first Excel row) sits at the bottom**. Tray 12 is at the top."
- [SKILL] "If WOODWOP has no usable on-sheet text tool, capture the 2D pane and stamp the G3 labels onto each tray rectangle (white patch, dark bold number on the left of the tray). Do not ship a 3×4 sticker grid as the print."
  - **This replaced** the bot's first 8/29 output, a separate 3×4 grid of labels. Mike's reply to that grid: "I DO NOT SEE THE LABELED PRINTABLE SCREEN SHOT OF THE SHEET".
- [CHAT 8/29] Mike's description of the WOODWOP variable table: "THE BLUE SECTIONS ARE JUST THE TRAY NUMBERS AND THE RED IS THE NUMBERS YOU WOULD FILL OUT FROM A SPREED SHEET IT GOES UPTO TRAY 12". The SKILL restates it: "**Name** (blue) vs **Value** (red). Fill only the red values."
- [FILE] The master xlsm has a logo image and a "Report" button on the "Jewelry Trays" sheet.

Nothing else was discussed about screens, colors, fonts or the app UI.
## 10. CODE

Nothing in this section was written as code in a conversation. **Everything here is [FILE], copied exactly.** Long files are given as their complete repeating pattern, with every distinct line shown.

### 10.1 Daily sheet `MMDDYY DAILY TRAYS.xlsx` (Sheet1) formulas

Pattern for row 3; the same down to row 53 (M48 uses A62, a quirk):

```
A1  FILL IN INFORMATION HERE          G1  JEWELRY TRAY BOTTOMS
A2 CUSTOMER # ONLY | C2 WIDTH | E2 DEPTH | G2 DESCRIPTION | H2 PART TYPE | I2 UNIT #
J2 MATERIAL | L2 QTY | M2 WIDTH | N2 DEPTH | Q2 GRAIN | R2 COMPANY
D3  X
G3  =IF(A3="","",A3)
H3  TRAY BOTTOM
I3  =IF(A3="","",A3)
J3  1/4 MELAMINE
M3  =IF(ISBLANK(C3),"",(C3-A61)*25.4)
N3  =IF(ISBLANK(E3),"",(E3-A61)*25.4)
Q3  N
R3  JEWELRY TRAYS DIRECT
E57 MM CONVERSION FOR WOOD WOP
E59 WIDTH          G59 DEPTH
A60 for bottom conversion
A61 0.5625
B60 1              B61 =B60+1   (... to B110 = 51)
C60 =IF(A3="","",A3)
E60 =IF(C3="","",CONVERT(C3,"in","mm"))
F60 X
G60 =IF(E3="","",CONVERT(E3,"in","mm"))
Print_Area = Sheet1!$G$1:$J$21
```

### 10.2 Master workbook `JEWELRY TRAYS FILE MMDDYY.xlsm`: visible sheet and chain

The calculation chain is **Jewelry Trays ← FINAL ← CALCULATE ← calculo**. The hidden sheets are Sheet1, Sheet, calculo, CALCULATE and FINAL.

```
'Jewelry Trays'  D1 Order Jewelry Trays   D2 =TODAY()   H1 Thickness x2
Row 4: B Order Number | C Lineitem Name | D Lineitem Quantity | E Lineitem Title
       F Tray Width | G Tray Height | H Tray Depth | I FRONT TO BACK\nNO NOTCH
       L # DIVIDERS LEFT TO RIGHT NOTCH
I5 =IF(AND(F5="",G5="",H5=""),"",P5)      J5 =IF(I5="","","Pcs")
K5 =IF(AND(F5="",G5="",H5=""),"",R5)
L5 =IF(AND(F5="",G5="",H5=""),"",S5)      M5 =IF(L5="","","Pcs")
N5 =IF(AND(F5="",G5="",H5=""),"",U5)
P5 =IF(OR(E5="Necklace Tray",E5="Watch and Bracelet Tray",E5="Tie and Belt Tray",E5="Sunglasses Tray",E5="Earrings Tray"),FINAL!I5,"")
R5 / S5 / U5 = same as P5 with FINAL!K5 / FINAL!L5 / FINAL!N5
Defined names: Print_Area='Jewelry Trays'!$B$1:$N$146 ; Print_Titles=$1:$4

FINAL  B..H = 'Jewelry Trays'!B..H ; J and M = "Pcs"
I5 =IF(E5="Necklace Tray",CALCULATE!R5,IF(E5="Earrings Tray",CALCULATE!V5,IF(E5="Tie and Belt Tray",CALCULATE!L5,IF(E5="Watch and Bracelet Tray",CALCULATE!L5,IF(E5="Sunglasses Tray",CALCULATE!X5)))))
K5 =IF(E5="Necklace Tray",CALCULATE!Q5,IF(E5="Earrings Tray",CALCULATE!Q5,IF(E5="Tie and Belt Tray",CALCULATE!N5,IF(E5="Watch and Bracelet Tray",CALCULATE!N5,IF(E5="Sunglasses Tray",CALCULATE!N5)))))
L5 =IF(E5="Necklace Tray","",IF(E5="Earrings Tray",CALCULATE!K5,IF(E5="Tie and Belt Tray",CALCULATE!K5,IF(E5="Watch and Bracelet Tray",CALCULATE!K5,IF(E5="Sunglasses Tray",CALCULATE!Z5)))))
N5 =IF(E5="Necklace Tray","",IF(E5="Earrings Tray",CALCULATE!M5,IF(E5="Tie and Belt Tray",CALCULATE!M5,IF(E5="Watch and Bracelet Tray",CALCULATE!M5,IF(E5="Sunglasses Tray",CALCULATE!Y5)))))

CALCULATE  E..H = FINAL!E..H
I5..Z5 each: =IF(OR(calculo!X5=FALSE,calculo!X5=""),"",calculo!X5)   (X = same column)
```
### 10.3 Sheet "calculo" (row 5 shown; every row is the same)

Constants: J1 `=0.4375*2`, L1 `0.8125`, P1 `0.4375` ("Thickness"). E5..H5 = CALCULATE!E5..H5.

```
I5 =IF(E5="Earrings Tray",2,IF(E5="Sunglasses Tray",6.75,IF(E5="Tie and Belt Tray",4.75,IF(E5="Watch and Bracelet Tray",3.75))))
J5 =IF(E5="Earrings Tray",2,IF(E5="Sunglasses Tray",2.75,IF(E5="Tie and Belt Tray",4.75,IF(E5="Watch and Bracelet Tray",3.75))))
K5 =IF(E5="Earrings Tray",IF(AB5<I5,AA5-1,AA5),IF(E5="Tie and Belt Tray",IF(AB5<I5,AA5-1,AA5),IF(E5="Watch and Bracelet Tray",IF(AB5<I5,AA5-1,AA5))))
L5 =IF(E5="Earrings Tray",IF(AD5<I5,AC5-1,AC5),IF(E5="Tie and Belt Tray",IF(AD5<I5,AC5-1,AC5),IF(E5="Watch and Bracelet Tray",IF(AD5<I5,AC5-1,AC5))))
M5 =IF(E5="Earrings Tray",F5-$L$1,IF(E5="Tie and Belt Tray",F5-$J$1,IF(E5="Watch and Bracelet Tray",F5-$J$1)))
N5 =IF(E5="Earrings Tray",H5-$J$1,IF(E5="Sunglasses Tray",H5-$J$1,IF(E5="Tie and Belt Tray",H5-$J$1,IF(E5="Watch and Bracelet Tray",H5-$J$1))))
Q5 =IF(E5="Necklace Tray",H5-$J$1,IF(E5="Earrings Tray",H5-$J$1))
R5 =IF(E5="Necklace Tray",TRUNC((F5-$J$1)/(2.25+0.875),0))
S5 =IF(E5="Necklace Tray",F5-$L$1)
T5 =IF(E5="Necklace Tray",(S5-(R5*0.4375))/(R5+1))
U5 =IF(E5="Earrings Tray",AC5-1)
V5 =IF(E5="Earrings Tray",L5-1)
W5 =IF(E5="Sunglasses Tray",IF(AB5<=I5,AA5-1,AA5))
X5 =IF(E5="Sunglasses Tray",IF(AD5<=J5,AC5-1,AC5))
Y5 =IF(E5="Sunglasses Tray",F5-$L$1)
Z5 =IF(E5="Sunglasses Tray",W5)
AA5 =IF(E5="Earrings Tray",TRUNC((F5-$J$1)/(2+0.875),0)+1,IF(E5="Sunglasses Tray",TRUNC((F5-$J$1)/(6.75+0.875),0)+1,IF(E5="Tie and Belt Tray",TRUNC((F5-$J$1)/(4.75+0.875),0)+1,IF(E5="Watch and Bracelet Tray",TRUNC((F5-$J$1)/(4.75+0.875),0)+1))))
AC5 =IF(E5="Earrings Tray",TRUNC((H5-$J$1)/(2+0.875),0)+1,IF(E5="Sunglasses Tray",TRUNC((H5-$J$1)/(6.75+0.875),0)+1,IF(E5="Tie and Belt Tray",TRUNC((H5-$J$1)/(4.75+0.875),0)+1,IF(E5="Watch and Bracelet Tray",TRUNC((H5-$J$1)/(4.75+0.875),0)+1))))
AE5 =IF(E5="Earrings Tray",L5)
```
calculo, the long spacing formulas (row 5):

```
O5 =IF(E5="Watch and Bracelet Tray",IF(K5=2,(F5-1.75)/(K5+1),IF(K5=3,(F5-2.1875)/(K5+1),IF(K5=4,(F5-2.625)/(K5+1),IF(K5=5,(F5-3.0625)/(K5+1),IF(K5=6,(F5-3.5)/(K5+1),IF(K5=7,(F5-3.9375)/(K5+1))))))),IF(E5="Earrings Tray",(M5-$P$1*K5)/(K5+1),IF(E5="Sunglasses Tray",(F5-0.8125-(X5*0.4375))/(X5+1),IF(E5="Tie and Belt Tray",IF(K5=2,(F5-1.75)/(K5+1),IF(K5=3,(F5-2.1875)/(K5+1),IF(K5=4,(F5-2.625)/(K5+1),IF(K5=5,(F5-3.0625)/(K5+1),IF(K5=6,(F5-3.5)/(K5+1))))))))))
P5 =IF(E5="Tie and Belt Tray",IF(L5=2,(N5-0.4375)/(L5),IF(L5=3,(N5-0.875)/(L5),IF(L5=4,(N5-1.3125)/(L5),IF(L5=5,(N5-1.7625)/(L5))))),IF(E5="Earrings Tray",(N5-$P$1*V5)/(L5),IF(E5="Sunglasses Tray",(H5-0.8125-(W5*0.4375))/(W5+1),IF(E5="Watch and Bracelet Tray",IF(AC5=2,(H5-1.25)/(AC5),IF(AC5=3,(H5-2.1875)/(AC5),IF(AC5=4,(H5-2.625)/(AC5),IF(AC5=5,(H5-3.0625)/(AC5),IF(AC5=6,(H5-3.5)/(AC5))))))))))
AB5 =IF(E5="Earrings Tray",(M5-$P$1*AA5)/(AA5+1),IF(E5="Sunglasses Tray",(F5-0.8125-(AA5*0.4375))/(AA5+1),IF(E5="Tie and Belt Tray",IF(E5="Tie and Belt Tray",IF(AA5=2,(F5-1.75)/(AA5+1),IF(AA5=3,(F5-2.1875)/(AA5+1),IF(AA5=4,(F5-2.625)/(AA5+1),IF(AA5=5,(F5-3.0625)/(AA5+1),IF(AA5=6,(F5-3.5)/(AA5+1),IF(E5="Watch and Bracelet Tray",IF(AA5=2,(F5-1.75)/(AA5+1),IF(AA5=3,(F5-2.1875)/(AA5+1),IF(AA5=4,(F5-2.625)/(AA5+1),IF(AA5=5,(F5-3.0625)/(AA5+1),IF(AA5=6,(F5-3.5)/(AA5+1),IF(AA5=7,(F5-3.9375)/(AA5+1)))))))))))))))))
AD5 =IF(E5="Earrings Tray",(Q5-$P$1*U6)/(AC5),IF(E5="Sunglasses Tray",(H5-0.8125-(AC5*0.4375))/(AC5+1),IF(E5="Tie and Belt Tray",IF(E5="Tie and Belt Tray",IF(AC5=2,(N5-0.4375)/(AC5),IF(AC5=3,(N5-0.875)/(AC5),IF(AC5=4,(N5-1.3125)/(AC5),IF(AC5=5,(N5-1.7625)/(AC5),IF(E5="Watch and Bracelet Tray",IF(AC5=2,(H5-1.25)/(AC5),IF(AC5=3,(H5-2.1875)/(AC5),IF(AC5=4,(H5-2.625)/(AC5),IF(AC5=5,(H5-3.0625)/(AC5),IF(AC5=6,(H5-3.5)/(AC5)))))))))))))))
```

Note: AD5 references U6, and AD6 references U7. Every row points one row down.
### 10.4 WOODWOP `.mpr`: header and variable table (`_3 TALL DAILY TRAY TEMPLATE.mpr`)

Header excerpt. `WW` is the WOODWOP version that saved the file: 6.0.68 here, 6.0.59 for `_2 TALL`.

```
[H
VERSION="4.0 Alpha"
WW="6.0.68"
MAT="WEEKE"
INCH="0"
_BSX=2438.000000
_BSY=1219.200000
_BSZ=10.000000
_RX=2438.000000
_RY=1219.200000
```

Variable table `[001`. `_2 TALL` is the same except `th="49.21"`, and it runs to tr16.

```
[001
l="2438"
KM="length"
w="1219.2"
KM="width"
t="10"
KM="thickness"
s="337.55"
KM="side"
f="555.625"
KM="front and back"
b="6.35"
KM="bottom space and groove"
h="47.625"
KM="box hight"
c="12.7"
KM="1/2 inch bit"
th="73.03"
KM="tray hight"
v="4.76"
KM="velvet allowance"
tr1w="102"
KM="tray 1 width"
tr1d="102"
KM="tray 1 depth"
... same pair for tr2 ... tr12 (… tr16 in _2 TALL), all "102"
```

Stock board variant (`100226 DAILY TRAYS 8 STOCK 34IN.mpr`, after `v`):

```
tw="863.60"
KM="TRAY WIDTHS"
td="339.73"
KM="TRAY DEPTHS"
tr1w="tw"
KM="tray 1 width"
tr1d="td"
KM="tray 1 depth"
... same for tr2 ... tr16
```

The workpiece block is `<100 \WerkStck\` with `LA="l"`, `BR="w"`, `DI="t"`.

### 10.5 WOODWOP: tray 1 contours, exact (helper lines `.X=`/`KO=` dropped)

Tray N uses the same text with `trNw`/`trNd`. Its start Y moves by the pitch: on `_3 TALL`, tray 2 is `]8` outline `Y=84+25` and `]9` line `Y=94+25`, and each tray after that adds +25 more on top of +76. On `_2 TALL`, tray 2 is `Y=84` and `Y=94`, and so on up to tray 16 at `Y=1148`/`1158`.

```
]1
$E0
KP 
X=0
Y=18
Z=0.0
$E1
KL 
X=tr1w+tr1d+tr1w+tr1d+40-(v*4)
Y=@0
]2
$E0
KP 
X=0
Y=8
Z=0.0
$E1
KL 
X=tr1w+tr1d+tr1w+tr1d+40-(v*4)
Y=@0
$E2
KL 
X=@0
Y=@th
$E3
KL 
X=@-tr1w-tr1d-tr1w-tr1d-40+(v*4)
Y=@0
$E4
KL 
X=@0
Y=@-th
]3
$E0
KP 
X=@20
Y=@-2
Z=0.0
$E1
KL 
X=@0
Y=@th+20
]4
$E0
KP 
X=@20+(tr1w-v)
Y=@0-2
Z=0.0
$E1
KL 
X=@0
Y=@th+20
]5
$E0
KP 
X=@20+(tr1w-v)+(tr1d-v)
Y=@0-2
Z=0.0
$E1
KL 
X=@0
Y=@th+20
]6
$E0
KP 
X=@20+(tr1w-v)+(tr1d-v)+(tr1w-v)
Y=@0-2
Z=0.0
$E1
KL 
X=@0
Y=@th+20
]7
$E0
KP 
X=@20+(tr1w-v)+(tr1d-v)+(tr1w-v)+(tr1d-v)
Y=@-2
Z=0.0
$E1
KL 
X=@0
Y=@th+20
```

Macro for contour 1 (the full block). The other macros are the same except for these fields:

```
<105 \Konturfraesen\
EA="1:0"
MDA="SEN"
STUFEN="0"
BL="0"
WZS="1"
OSZI="0"
OSZVS="0"
ZSTART="0"
ANZZST="0"
RK="WRKL"
EE="1:1"
MDE="SEN_AB"
EM="1"
RI="1"
TNO="130"
SM="0"
S_="STANDARD"
F_="10"
AB="0"
AF="0"
AW="0"
BW="0"
VLS="0"
VLE="0"
ZA="5"
SC="0"
TDM="0"
HP="0"
SP="0"
YVE="0"
WW="1,2,3"
ASG="2"
KG="0"
RP="STANDARD"
RSEL="0"
RWID="0"
KAT="Fräsen"
MNM="Vertical trimming"
ORI="61"
MX="0"
MY="0"
MZ="0"
MXF="1"
MYF="1"
MZF="1"
SYA="0"
SYV="0"
```

```
Contours 3-7 (cut lines):  RK="NoWRK" EE="n:1" TNO="134" F_="12" ZA="sbc"
Contour 1 (line Y+10):     RK="WRKL"  EE="1:1" TNO="130" F_="10" ZA="5"
Contour 2 (outline) x2:    RK="WRKR"  EE="2:4" TNO="128" F_="25" ZA=".5"  then ZA="sbc"
All: KAT="Fräsen" MNM="Vertical trimming"; ORI = run order
```
### 10.6 `_4 TALL 36IN TRAYS.mpr` (variables and contours)

```
[001
l="2348.4"  KM="length"        w="1219.2" KM="width"
t="10"      KM="thickness"     s="487.4"  KM="side"
f="914.4"   KM="front and back"
b="6.35"    KM="bottom space and groove"
h="102"     KM="box hight"     c="12.7"   KM="1/2 inch bit"
]1 KP X=0.0 Y=0.0      ; KL X=@0 Y=@w
]2 KP X=@f Y=@0        ; KL X=@0 Y=@w
]3 KP X=@s+f Y=@0      ; KL X=@0 Y=@w
]4 KP X=@s+f+f Y=@0    ; KL X=@0 Y=@w
]5 KP X=@-15 Y=@b*2+6  ; then repeat: KL X=@f+s+f+30 Y=@0 / KL X=@0 Y=@h+c / KL X=@-f-s-f-30 Y=@0 / KL X=@0 Y=@h+c  ($E1..$E39)
]6 KP X=@-15 Y=@0      ; then repeat: KL X=@f+s+f+40 Y=@0 / KL X=@0 Y=@h+c / KL X=@-f-s-f-40 Y=@0 / KL X=@0 Y=@h+c  ($E1..$E41)
Macros: EA 1-4 TNO 134 F_15 ZA sbc ; EA 5 TNO 130 ZA 5 EE 5:19 ; EA 6 TNO 128 F_20 ZA 1 then ZA sbc (EE 6:21)
```

(The `name`/`KM` pairs are on separate lines in the real file. They are packed two to a line here.)

### 10.7 VBA (`JEWELRY TRAYS FILE …xlsm`, Module1, complete)

```
Attribute VB_Name = "Module1"
Sub Report()
Attribute Report.VB_ProcData.VB_Invoke_Func = " \n14"
'
' Report Macro
'

'
    Range("E11").Select
    Sheets("Jewelry Trays").Select
    Sheets("Jewelry Trays").Copy After:=Sheets(6)
    Cells.Select
    ActiveSheet.Unprotect
    Selection.Copy
    Selection.PasteSpecial Paste:=xlPasteValues, Operation:=xlNone, SkipBlanks _
        :=False, Transpose:=False
    Rows("4:4").Select
    Application.CutCopyMode = False
    Selection.AutoFilter
    ActiveSheet.Range("$A$4:$U$1500").AutoFilter Field:=8, Criteria1:="<>"
    ActiveWindow.SmallScroll Down:=0
    ActiveSheet.Range("$A$4:$U$1500").AutoFilter Field:=9, Criteria1:="<>"
End Sub
```

ThisWorkbook contains only attributes, no code.

### 10.8 xlsm hidden "Sheet1" (minimum-size test table)

```
Row 3 EARRING: D3 30, E3 21, min 2/2      Row 5 SUNGLASS: D5 18.75, E5 13.375, min 6.75/2.75
NECKLACES: 26.75 x 13.375                 Row 6 WATCH AND BRACELETS: D6 22.375, E6 16.75, min 3.75/3.75
J3 =D3-0.8125          K3 =E3-0.875        L3 =(J3-0.4375*H3)/(H3+1)
M3 =(K3-0.4375*T3)/(I3)                    T3 =I3-1
N5 =E5-0.875           P5 =D5- 0.8125      Q5 =(D5-0.8125-(O5*0.4375))/(O5+1)
J6 =D6-0.875           C10 =378/3
```

Hidden "Sheet" is an Earrings-only copy. Row 6: F 30, H 21 → K 11, L 8, M 29.1875, N 20.125, O 2.03125, P 2.1328125, U/V 7, AA 11, AC 8.
### 10.9 Draft `Tray Calculator.xlsx` (2/20/2026), sheet "Orders" (row 3/4)

```
I3 =TRIM(LEFT(C3,FIND(" -",C3&" -")-1))
J..M = VLOOKUP(I3, Types, 2..5)      (Min LR, Min FB, Has Inserts?, Insert Type)
N3 =IF(J3="","",F3-0.875)                                  Inside Width
O3 =IF(K3="","",H3-0.875)                                  Inside Depth
P3 =IF(OR(J3="",J3=0),1,FLOOR((N3 + 0.4375)/(J3 + 0.4375),1))   Max Openings LR
Q3 =IF(OR(K3="",K3=0),1,FLOOR(O3 / (K3 + 0.4375),1))            Max Openings FB
R3 =IF(P3=1,N3,(N3 - (P3-1)*0.4375)/P3)                    Spacing LR
S3 =IF(Q3=1,O3,(O3 - Q3*0.4375)/Q3)                        Spacing FB
T3 =IF(OR(R3<J3,S3<K3,P3<1,Q3<1),"ERROR: Too small for min - check size or config","OK")
U3 =IF(L3=0,0,P3*Q3*E3)                                    Inserts Qty
AG2 =IF(ISNUMBER(F2),F2, VALUE(LEFT(F2,FIND(" ",F2)-1)) + VALUE(MID(F2,FIND(" ",F2)+1,LEN(F2))))
F52 =IF(C52="","",IF(ISNUMBER(C52),C52,LET(clean,TRIM(SUBSTITUTE(SUBSTITUTE(C52,"""",""),"in","")),pos,FIND(  ... (truncated in file view)
```

Parts Description (V4):

```
=IF(T4<>"OK",T4,TEXT(E4*(P4-1),"0")&" Vertical Dividers (run F-B): Length "&TEXT(O4,"# ?/?")&""", Height "&TEXT(G4,"# ?/?")&""", Thick 7/16"""&CHAR(10)&TEXT(E4*(Q4-1),"0")&" Horizontal Dividers (run L-R): Length "&TEXT(N4,"# ?/?")&""", Height "&TEXT(G4,"# ?/?")&""", Thick 7/16"""&IF(U4>0,CHAR(10)&TEXT(U4,"0")&" "&M4&" Inserts: "&TEXT(R4,"# ?/?")&" x "&TEXT(S4,"# ?/?"),"") )
```

Headers: Order ID, Order Number, Lineitem Name, Lineitem Title, Qty, width / height / depth (text like `24 7/8"`), Tray Type Base, Min LR, Min FB, Has Inserts?, Insert Type, Inside Width, Inside Depth, Max Openings LR, Max Openings FB, Spacing LR, Spacing FB, Check, Inserts Qty, Parts Description. The "Manufacturing List" sheet is empty.

### 10.10 Shopify export header (`shopify_export_MMDDYY.csv`)

```
Order ID,Order Number,Lineitem Name,Lineitem Quantity,Lineitem Title,Width,Height,Depth
```
### 10.11 `JTD_TRAY_SIZE_LISTS_2026-10-02.txt` (complete)

```
JTD tray sizes from the order sheet
Friday 10/2/2026
Sizes grouped within 2 inches. Stick = two depths + two widths + 1.5 inches on each end (3 inches total).

LIST 1 — sizes, most sold to least
12 to 14 deep by 22 to 24 wide, 311 trays
16 to 18 deep by 28 to 30 wide, 131 trays
12 to 14 deep by 20 to 22 wide, 56 trays
14 to 16 deep by 20 to 22 wide, 34 trays
12 to 14 deep by 26 to 28 wide, 33 trays
16 to 18 deep by 22 to 24 wide, 27 trays
12 to 14 deep by 28 to 30 wide, 25 trays
14 to 16 deep by 22 to 24 wide, 22 trays
16 to 18 deep by 26 to 28 wide, 17 trays
18 to 20 deep by 22 to 24 wide, 17 trays
12 to 14 deep by 16 to 18 wide, 16 trays
14 to 16 deep by 26 to 28 wide, 12 trays
24 to 26 deep by 36 to 38 wide, 10 trays
Everything else is 9 or fewer. 289 lines had both sizes, 838 trays.

LIST 2 — stick length for each size (middle of the band)
About 13 by 23, from 311 trays: 75 inch stick
About 17 by 29, from 131 trays: 95 inch stick
About 13 by 21, from 56 trays: 71 inch stick
About 15 by 21, from 34 trays: 75 inch stick
About 13 by 27, from 33 trays: 83 inch stick
About 17 by 23, from 27 trays: 83 inch stick
About 13 by 29, from 25 trays: 87 inch stick
About 15 by 23, from 22 trays: 79 inch stick
About 17 by 27, from 17 trays: 91 inch stick
About 19 by 23, from 17 trays: 87 inch stick
About 13 by 17, from 16 trays: 63 inch stick
About 15 by 27, from 12 trays: 87 inch stick
About 25 by 37, from 10 trays: 127 inch stick

LIST 3 — similar sticks grouped (within 4 inches). Length is the longest in the group.
63 inch stick, 16 trays
75 inch stick, 367 trays (the 71s and both 75s)
79 inch stick, 22 trays
87 inch stick, 114 trays (both 83s and the three 87s)
95 inch stick, 148 trays (the 91s and the 95s)
127 inch stick, 10 trays
Total 677 trays.
```
## 11. EDGE CASES & GOTCHAS

1. **M/N vs E/G (14.2875 mm).** The conversation FINAL rule says M/N. Mike's real MPRs (8/21 and 10/2) use E/G. See 5.2. Getting this wrong makes every tray 14.29 mm off on each side.
2. **12 vs 16 per board.** The 2-tall template and the real 2" boards hold 16. The rule says 12. The 3-tall template holds 12.
3. **The 8/29 board mixed heights.** `082926 DAILY TRAYS 1 3IN` holds 8 non-3IN rows (2362–2390) plus 4 rows of "2391 - 3IN TRAY". That breaks "2" and 3" never on one board". The bot was asked to flag it.
4. **Text-replace clobbering.** `tr1w` matches inside `tr10w`, `tr11w` and `tr12w`. Replace tr12 → tr1 (or match exactly).
5. **Placeholder 102 / split rows.** Unfilled slots stay `102`. In `100226 DAILY TRAYS 1.mpr`, tr7–tr10 have depth `102`. Their widths are:
   - tr7w 795.34 and tr8w 501.65: these match 4356's 31.3125 × 19.75 in, split across two slots.
   - tr9w 812.80 and tr10w 482.60: these match 4358's 32 × 19 in, split the same way.
   - The 4357 rows (2X STOCK 22IN / 28IN) were skipped.
   - Record this as observed. Do not copy it.
6. **Same value in w and d.** `100226 DAILY TRAYS 2.mpr` tr11–16 = 558.80×558.80. The open 8/21 3IN file had tr5/tr6 = 428.63×428.63. These may be typing slips; record them, don't copy them.
7. **QTY is not expanded.** The sheet has one row per tray. "2392 - 11X" with QTY 11 sits on a single row. How multi-qty rows reach WOODWOP was **NOT DISCUSSED**.
8. **Heights other than 2"/3".** A 4" template exists only for 36" trays. "3996 - 5IN TRAY" had no matching template in the sources.
9. **Stock rows.** Stock rows (STOCK 21–34IN, 13.375 deep) go to their own `tw`/`td` 16-up boards, not to the daily boards.
10. **Sheet formula quirk.** In 100226, M48 references `A62` instead of `A61`.
11. **calculo quirks.**
    - AD references `U7` (next row).
    - For Watch and Bracelet, AB/AD return FALSE because that branch is nested inside the Tie and Belt branch. K/L then depend on Excel's FALSE<number = FALSE.
    - The AA/AC divisor for Watch is 4.75, not its 3.75 minimum.
    - The O ladder differs between Watch (K up to 7) and Tie (K up to 6).
    - The P ladder for Tie uses 1.7625, not 1.75, at L=5.
    - Watch P uses 1.25 at AC=2.
    - L compares AD with I (the width minimum), not J.
    - Sunglasses counts use W/X with `<=`; the others use K/L with `<`.
12. **Stick-list arithmetic.** LIST 3 says "75 inch stick, 367 trays (the 71s and both 75s)". 311+56+34 = 401; 367 leaves out the 34 trays of 15×21. The "Total 677 trays" equals the LIST 1 total (711) minus 34. LIST 1 also says "289 lines had both sizes, 838 trays". The 13 listed bands add up to 711.
13. **127 in stick** is longer than the 96 in (2438 mm) board.
14. **Fractions.** Shopify sends "21 5/16"-style text. The draft calculator's parser fails on some inputs (#VALUE! errors).
15. **Shop PC.** Never overwrite an MPR that is open or that belongs to another day. Never edit templates. Keep L: R: S: W: mapped.
## 12. OPEN QUESTIONS / NOT DONE YET

1. Which mm block does WOODWOP get: **M/N** (conversation, 8/29) or **E/G** (Mike's real files)? (5.2)
2. 12 or 16 trays per 2" board?
3. Is mixing 2"/3" on one board ever OK, as happened on 8/29?
4. What do the 20 mm ends, the 40 mm and `4×v` represent? Is there a kerf? (NOT DISCUSSED)
5. How should multi-qty rows (e.g. QTY 11) and the 4"/5" trays be handled?
6. Working folder: none named yet, so no writes anywhere.
7. Shopify report link: **not done.** Mike: "WE WILL PICK THIS UP LATER".
8. Pricing logic: none exists beyond the Richelieu table.
9. "Old School" look: NOT DISCUSSED.
10. Draft `Tray Calculator.xlsx` (2/20/2026): unfinished. The Manufacturing List sheet is empty.
11. The 10/2–10/3 stick and sales-grouping chat (BIG HOSS) could not be read. Only the 10/2 result file was found. A "10/3 tray sales grouping" was not found.
12. Laptop outputs (tray-cutlist PDFs, tray-bottoms.xlsx, razor CSVs) were not read.
13. Bottom (CutRite) files, B2B/CF stock-size files and `JEWELRY TRAYS.xlsx` were not read.
14. Divider-calc quirks (section 11 #11): it is not known whether they are intended.

## Sources

- **Conversations:**
  - JEWELRY TRAYS DIRECT bot transcript, 8/29–9/8/2026, read in full from its exported log.
  - The bot's saved skill `jewelry-trays-woodwop/SKILL.md` and its memory notes.
  - BIG HOSS transcript export. It ends about 9/15/2026, so the 10/2–10/3 talks are missing. A 10/5 fleet report mentions the laptop files.
- **Files read on the shop PC (read-only):**
  - `L:\JEWELRY TRAYS DIRECT FILES\100226 DAILY TRAYS #4351-4368\`: `100226 DAILY TRAYS.xlsx`, `JEWELRY TRAYS FILE 100226.xlsm` (incl. VBA), `shopify_export_100226.csv`, `100226 DAILY TRAYS 1/2.mpr`, `3–8 STOCK …IN.mpr`, `9 STOCK 3IN.mpr`
  - `_2 TALL DAILY TRAY TEMPLATE.mpr`, `_3 TALL DAILY TRAY TEMPLATE.mpr`, `_4 TALL 36IN TRAYS.mpr`
  - `RICHELIEU - JTD Program Pricing 1.xlsx`
  - `…\Desktop\_jtd stuff\Tray Calculator.xlsx`, `JTD_TRAY_SIZE_LISTS_2026-10-02.txt`
- **Box copies:**
  - Mike's 8/29 attached daily sheet
  - `082126 DAILY TRAYS.xlsx`
  - the bot-made `082926 DAILY TRAYS 1 3IN.mpr`
  - Mike's 8/29 screenshots
- **Not read:**
  - `shopify_recovery_codes.txt` (a credential, skipped on purpose)
  - laptop files
  - bottoms / stock-size / equipment files
