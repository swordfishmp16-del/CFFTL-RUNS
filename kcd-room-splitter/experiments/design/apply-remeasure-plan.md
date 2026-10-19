<!-- Written by a design agent of the Oct 19, 2026 workflow (wf_be3f4a27-f1a), before the KCD round trip of test 1.
Scratchpad paths in it no longer exist. Decisions that changed afterwards: anchor is auto (main-wall rule, see the critic
and notes 14.7), the unit step follows the owner's rule (fillers stay 3/4, the cabinet at the wall end changes), and the
unit room points ARE rewritten (notes 14.6). -->

# apply_remeasure — plan (Oct 19, 2026)

Written to `/tmp/claude-0/-home-user-CFFTL-WORKING-/bef348d8-06f1-5cee-a359-256568af5804/scratchpad/walls/design/plan.md`. Scratch probes used for the new findings: `/tmp/claude-0/-home-user-CFFTL-WORKING-/bef348d8-06f1-5cee-a359-256568af5804/scratchpad/walls/planner/probe_unit_f86.py` and `probe_centre.py`.

Tool that takes the Grok read-out JSON of a handwritten remeasure plus the designer's `.job`, sets the room's wall lengths to the measured values, adjusts the sections (units) on those walls where the adjustment is clear-cut, and writes a new `.job` with a plain-English report. Everything that is not certain is flagged, never filled in (owner's standing rule). KCD is not available here, so every written file is a TEST file until KCD has opened it and saved it back; section 7 is the plan for proving the writes.

Units: raw = 0.1 mm, **254 raw = 1 inch**; 1/16" = 15.875 raw (code uses `IN // 16 = 15` as a tolerance); 1/32" = 7 raw; T = 1143 raw = 4 1/2" wall thickness.

Code: `/home/user/CFFTL-WORKING-/kcd-room-splitter/` (`kcdjob.py`, `kcdunits.py`, `kcdwalls.py`, `kcdsplit.py`, `kcdcompare.py`). Evidence: `.../scratchpad/walls/` (`walls10.txt`, `absorb/absorb_report.txt`, `grok/*.json`, `jobs/*.job`).

---

## 0. What already exists and what this plan adds

`kcdwalls.py` (committed 3c35bc9, working tree clean) already does the wall part: `parse_wall`/`pack_wall` (205-byte record), `resize_wall` (open chains translate downstream, closed loops use an antiparallel absorbing wall), `set_wall_lengths` (in-place patch, same file size, read-back check, "nothing outside the wall records changed" check), `read_rem_json`/`apply_rem` (label grammar `<room> #<n> (printed <len>)`, 1/32" printed check, review items never applied) and a text report. Its COYNE run (`out/Cathy Coyne - REM 1093610 applied - REPORT.txt`) is the baseline.

This plan adds, in order of certainty:
1. Tighter input validation and a three-tier decision (APPLY / READY / CHECK) — section 2.
2. The wall edit as it is, plus the newly found **unit-record room coordinates** that go stale when a wall moves — section 3.4 (needs the round trip before we rely on it).
3. The unit step (slide, filler absorb, proposals for re-splits) with limits taken from the ten design/engineered pairs — section 4.
4. Output: file suffix, report, JSON sidecar, one-click acceptance of READY items — section 5.
5. Validation: eight KCD round-trip experiments, smallest first, and the byte-compare run on what KCD saves back — section 7.

Nothing in `kcd-room-splitter/` was changed by this planning step.

---

## 1. Inputs and the facts they must agree with

**Grok JSON** (`consensus[]` with `label`, `value`, `confidence`; `needs_review[]` with `label`, `possible_values`, `reason`). Two shapes seen:
- COYNE (good): `"Linen #7 (printed 25 1/4)" = "25 1/8"`, `"Linen #9" = "34 7/8"` (no printed value), `"Linen H" = "90 1/4"`, `"Guest HO" = "80 3/4"`, needs_review `"Primary #15 (printed 57 15/16)"` with two values.
- WERNER (poor): `"HOME OFFICE" = "205 1/8"`, `"wall A" = "12 3/4"` **and** `"wall A" = "12 1/4"` (same label twice), `"wall B"` four times, `"H"` only in needs_review with `"13 5/4"` (impossible fraction). No `#n` anywhere.

**The job.** Wall id = Int32@125; the number printed on KCD's floor plan **is this id** (COYNE labels #7..#19 match ids 7..19 and their printed lengths; GODDARD remeasure "#5 163 9/16" matches design wall 5 = 41545 raw). Unit numbers on the price review are positions among live units, but wall numbers are ids: match walls by id. Room of a wall = Int32@129. KCD room-list names often differ from the sidebar name (`ROOM DETAILS <name>`), and both can differ from what the rem tech wrote ("Primary" vs "Master Bedroom WIC").

---

## 2. Input validation (JSON → wall requests)

### 2.1 Label grammar (extend `WALL_LABEL`)

| Label form | Treated as |
|---|---|
| `<room> #<n>` optionally `(printed <len>)` | wall request for wall id n |
| `<room> #<n> <free text>` (e.g. `Primary Wall 14 WIRE, below the line`) | **not** a wall length; listed under "read-out lines not used" |
| `<room> H` / `HO` / `HD` / `BB` / `F` / `Door` / `Molding` / `HOLES` | room fact (reported; H is a READY height proposal, 4.4 B5) |
| anything else (`wall A`, `HOME OFFICE`, `CUSTOMER ORDER #`, `KEVIN`) | not used; listed verbatim |

A bare room label with a length and no `#n` (WERNER `"HOME OFFICE" = "205 1/8"`) is reported as `CHECK HOME OFFICE = 205 1/8 is a length without a wall number; the room's walls are: #1 198. Not applied. Use --set 1="205 1/8" if that is wall 1.` The tool never infers the wall from the room, even when the room has one wall.

### 2.2 Value grammar

Accepted: `W`, `W n/d`, `n/d`, optional `"`/`”`, d in {2, 4, 8, 16, 32}, n < d. Converted exactly with `Fraction`; raw = `round(inches * 254)` (Python round = half to even, which reproduces KCD's stored values: 3/4 → 190 not 191, 7/8 → 222, 29 1/4 → 7430, 36 3/4 → 9334). Rejected (CHECK, not applied): other denominators (`5/4`), decimals with more than 3 places, negative, zero, anything with letters (`26 x 80`, `TILE`, `ND`).

### 2.3 Matching one request to one wall — decision table

For each request (room R, wall n, printed p or none, measured m):

| Check | Result |
|---|---|
| wall n not in the job, or dead (room 0) | CHECK, not applied |
| same wall twice in consensus with different values, or in consensus and needs_review | CHECK, not applied (conflict) |
| p given and \|round(p·254) − L\| > 7 raw (1/32") | CHECK "sheet printed from another file version", not applied |
| room name mismatch (normalised: case, spaces, punctuation; accept exact, prefix, or the sidebar name) | with p matching: NOTE and proceed (wall id + printed length identify the wall); without p: CHECK, not applied |
| m == L (within 1 raw) | "already m, no change" |
| \|m − p\| > 12" or > 15% of p | CHECK "unusually large change", not applied (GODDARD's door wall became two 63" stubs: a redesign, not a length edit) |
| p given, all checks pass | **APPLY** |
| p missing, all other checks pass | **READY**: listed with the exact command/tick box, applied only when the engineer accepts. The printed value is the only second check on the wall number; without it the rule says flag, not guess. COYNE `Linen #9 38 → 34 7/8` is this case. |
| needs_review item | **CHECK**, never applied, printed with both possible values and the job's current length |

Every applied value is echoed in raw and inches: `wall 7 (Linen): 6414 raw (25 1/4) -> 6382 raw (25 1/8), -32 raw (-1/8)`.

### 2.4 Whole-room sanity before any edit

- `check_room()` on every touched room: back-pointers, shared corners, mitre, length copies. A pre-existing inconsistency → CHECK, wall not changed (today's behaviour).
- Closed loops (GODDARD design, ROBERTS RIC design): if the sheet gives new lengths for **both** walls of an opposite pair and they differ, the loop cannot stay closed by lengths alone → CHECK with the exact discrepancy (`88 7/8 vs 89 1/8: differ by 1/4`), nothing applied for that loop; options: apply one pair, or open the room in KCD first. If only one of a pair is given, the antiparallel wall absorbs (today's behaviour) and the report says so; if the remeasure also lists the absorbing wall and agrees within 1/16", apply as one edit.

---

## 3. The wall-length edit

### 3.1 Bytes in the 205-byte record (confirmed on 178 records, 120 live)

Length change dL on wall k, anchor START (P0 fixed), v = round(dL · (cos a, sin a)), a = float32@16 / 254:

| Offset | Field | New value |
|---|---|---|
| 20, 100, 108 | L and its two copies (Int32) | L + dL |
| 58/62 | P1 = END of inner face | P1 + v |
| 66/70 | P2 = outer corner at END | P2 + v |
| 16, 24, 28/96/104, 32–35, 36, 40, 46, 48, 50/54, 74/78, 82, 117–132, 133–204 | angle, thickness, height, colour, ids, constants, P0, P3 | unchanged |

Downstream walls (follow right_id until 0): all four points @50..@81 += v (pure translation). Anchor END mirrors this upstream along left_id and moves k's P0/P3; units on k then need X += dL (4.2). Closed loop: antiparallel wall m gets L += dL, P0/P3 += v, walls between k and m translate. Height: @28, @96, @104 only. `resize_wall()` does all of this and round-trips ±1" on all 120 live walls byte-identically.

### 3.2 Which end moves (anchor) — a decision, not a fact

The sheet says how long the wall is, not which end is wrong. Default `start` (END moves, units keep X). Per-wall choices: `start`, `end` (units X += dL), `split` (slack shared by both corners: units X += dL/2 rounded to 1/16"; what GODDARD's engineer did on the back wall). Experiment E1 tells what KCD does when the length is typed in its wall dialog; the default follows KCD.

### 3.3 Dead walls, bare walls, open ends

- Room-0 walls are never touched. Bare walls change alone (POLONSKA 5 +1 5/8, LONG AUSTIN 4 +1/8, BINDLER 2 −3: the engineers did exactly that); markers on them (outlet/switch, W 1/8") are reported, not moved.
- Open chain end: nothing beyond it is translated; the mitre stays square.

### 3.4 New finding: unit records hold ROOM coordinates that the wall edit leaves stale

`planner/probe_centre.py` over COYNE, WERNER eng, WERNER design (66 units on live walls): the 86-byte unit block holds two 3-D points at bytes 40..51 (A) and 52..63 (B), Int32 raw, in **room** coordinates (not wall coordinates as the notes said: WERNER wall 1 starts at P0 = (5953, 0) and the points carry that offset):
- B along the wall = P0 + (X + W/2)·d on **66/66** (within 0.5 raw); B.z = H/2 on cabinets; B depth from the wall = D/2 on cabinets, I14 (From Wall) + D/2 on fillers (10/10).
- A along the wall = X + W/2 on 54/66; on base cabinets (type 200) it is X + W/2 − 0.05·W (WERNER units 8, 27: −427/−439 raw). A's depth is 0.92·D on bases, 0.75·D on talls/doors, 0.5·D on accessories. **Not derivable with certainty for every type.**
- Int32@12 of the block = W copy on 66/66.

| Edit | A and B | Certainty |
|---|---|---|
| wall chain translated by v | both + v (no formula needed) | high |
| unit slid by dX | both + dX·d | high |
| unit W changed by dW | B + (dW/2)·d exact; A + (dW/2)·d on most types, (dW/2 − 0.05dW)·d on bases | B high, A medium |

Policy: **v1 writes the wall records only** (as today) so that E1/E3 show whether KCD recomputes A/B on load (they look like a draw cache, as the mesh slice at 16..39 is). If KCD does **not** recompute them (E3 diff shows our stale A/B surviving), v2 translates them with the walls and slides them with the units, and for W changes writes B and flags A unless E2 confirms the per-type formula.

### 3.5 What else is left alone, and why

- **mesh**, unit mesh slices (block 16..39), header `L`/save blob, postwall serial, pictemp print pages: KCD recomputes on save (matched byte for byte on the splitter). The report says the 3-D view and print pages in the file are from before the change.
- **notes**: 30-byte header = six Int32 (x0, y0, x1, y1, xc, yc) of the note box, xc = (x0+x1)/2 on every note checked (COYNE, WERNER); Int16@24 = wall id; Int16@28 = kind (4 text, 5 dimension string, 6 leader). Dimension strings carry start/end/mid and the measured length (trailer Int32@16, e.g. 5334 = 21"). Notes on one wall use at least two coordinate spaces (plan vs elevation: WERNER `SOCKET P/U WHITE` at y = −25868). The space flag is not decoded, so **v1 does not move notes**; every note/dimension on a moved wall is CHECK ("may sit off the wall or show the old size"). E1 shows whether KCD moves them itself; if KCD leaves them, leaving them is correct.
- **roomshapes**: empty on the three jobs on hand; if a job has items in an edited room, flag and still write.
- First record's 16-byte preamble, byte 15 flag, Int16@46/@48, six doubles: copied verbatim.

---

## 4. The unit step

### 4.1 The model of a wall's "run"

Units on wall k (block Int16@0 = k) sorted by X (prefix slot 1 = Int32 at byte 6; W = slot 2 at byte 12). Classes by type code (block Int16@64) and cab:
- **structural**: cabinets (100–899 except below), fillers (230; 23x/234.cab), custom/finish panels (550), L-shape corner units (670), doors/windows (20/10 as fixed obstacles);
- **spanners**: connecting shelves (640/641/645 Csettop/Csetbot/Csetsh), backing (500), platforms, skin shelves, slat wall;
- **markers**: accessories/obstructions (1000, 899, LED, outlets, tie racks, jewelry trays, cleats), anything with W ≤ 1/8", anything parked outside [−2", L+2"] (SFERRA's five 3 1/8" fillers at X=30 are a parts count), qty>1 parked units.

Run facts per wall: `clear_start`, `clear_end` = L − (X+W) of the last structural unit, units flush at L (1/16"), overlaps, overhangs, corner zones (depth of the neighbouring wall's corner unit: GODDARD 16"/26 3/4", POLONSKA 36 3/4"/37 1/2").

**Filler convention (trap).** Designers draw fillers edge-on: W = 0.748 (thickness), D = face width (POLONSKA design wall 2: filler X 36.748 W 0.748 D 1.689, next unit at 38.441 = 36.748 + 1.689; D 1.811 at the other end = 188.0 − 186.189). Engineers draw them face-on: W = face (0.874), D = 0.748. Rule: face width = W when D ≈ 0.748; = D when W ≈ 0.748, D > 0.748 and X + D meets the next unit within 1/16"; otherwise CHECK. Edge-on fillers are **never resized automatically**.

### 4.2 Slide (anchor end / split)

X += dL (or dL/2) for every unit on the wall (structural, spanner, marker). Bytes: slot 1 Int32 at prefix byte 6, state byte 10 kept; nothing else.

### 4.3 What the ten design/engineered pairs show

| Case | dL | What the engineer did |
|---|---|---|
| POLONSKA 5, LONG AUSTIN 4, BINDLER 2 | +1 5/8, +1/8, −3 | bare walls: length only |
| PRIEM 8/10, MIRANDA 3, HUMPHREY 1 | −1/4, −1/8, +1/8, −5/8 | run does not reach the moving end, or remeasure not entered at all: no unit change |
| LONG DANI 3 | +1/2 | units unchanged, 1/2" left as a gap at the corner |
| LONG DANI 2 | +1/16 | run slid 1/16 (X += 16 raw), end stays flush |
| POLONSKA 2 | −1/4 | cabinets unchanged; two equal 7/8 fillers replace 3/4 + 3/4 + 0.945 gap |
| POLONSKA 3 | +1/8 | end filler re-anchored flush at the new end (plus a hand re-layout around appliances) |
| GODDARD 5 (back) | −15/16 | cabinets kept/rounded up; whole delta out of the two corner zones equally |
| GODDARD 6, 7 (sides) | −1 7/8, −1 5/8 | rebuilt: three equal interiors 27 3/4, one filler dropped, slack left at corners |
| GODDARD 8 (door wall), POLONSKA 1, SFERRA 1/3 | −1 7/16, −6 1/2, −2 1/2, +2 | redesign by hand |

Up to about 1/4" the engineers use fillers, gaps or a slide and never touch a cabinet width; around 1" they re-centre or re-split with **equal interiors on the 1/16" grid**; beyond that it is a new layout. When they change cabinets they change all sections of a kind together.

### 4.4 Rules, three tiers

**Tier A — applied automatically:**
- A1 bare wall, or run not reaching the moving end (shrink: `clear_end` ≥ |dL| + 1/16"; grow: any): no unit change; report the new clearance. A run ending at a door/window opening counts as not reaching the end only if the opening is not at the moving end.
- A2 face-on filler at the moving end, flush: `W_filler += dL` when |dL| ≤ 1" and the new face is within 3/4" .. 3" (190 .. 762 raw), on the 1/16" grid. Bytes: slot 2 (prefix byte 12), block Int32@12. W-dependent computed slots (`kcdunits.Unit.is_computed`, e.g. 231's stiles = W) are listed as "KCD recomputes when the unit is next edited" and re-evaluated by the tool only once E6 shows what KCD does.
- A3 spanners ending exactly (1/16") where a Tier-A-changed unit ends: W += same dW (GODDARD's Csettop followed the run); spanners ending at the moving wall end with no changed unit under them: CHECK.
- A4 markers: never changed (reported with their new distance to the wall end).

**Tier B — READY: proposed with exact numbers, applied only when ticked:**
- B1 run flush at the moving end, last structural unit a cabinet: propose a re-split of the sections of the same kind with equal interiors (W − LS − RS), each W on the 1/16" grid, remainder to the section nearest the moving end; before/after per unit. Flag inside the proposal when any interior changes by more than 1" or drops below 12", when a section has drawers, a door pair, or is an L-shape corner unit (POLONSKA kept 36 3/4 nominal).
- B2 re-centre (`split` anchor) as an alternative when both corners have zones (GODDARD back wall).
- B3 add a filler at the moving end when the post-change gap would be 3/4" .. 3" (proposal only: adding a unit record is a new write path).
- B4 fillers outside the A2 band (1/2" .. 3/4" or 3" .. 6"): proposed, not applied.
- B5 wall height from `H`: propose `height -> H` for every wall of the room when they share one height; list units taller than H − 1/2" and units whose H equals the old wall height.

**Tier C — CHECK only, never applied:** |dL| > 1" with a flush run; edge-on fillers; both ends flush with no filler at the moving end; pre-existing overlaps/overhangs (WERNER design: Backing/Shelf/Base end at 198 1/4 on a 198 wall: reported, not "fixed"); runs ending at a door/window on the moving end; closed-loop discrepancies; unknown `.cab`; qty > 1 units that are not markers; notes/dimensions on moved walls; any unit `kcdunits` cannot read.

### 4.5 Bytes of a unit edit (A2/B1)

| What | Where | Note |
|---|---|---|
| X | prefix bytes 6..9 (slot 1), state byte 10 kept | |
| W | prefix bytes 12..15 (slot 2), state byte 16 kept (E2 shows whether KCD sets 2 when typed) | |
| W copy | block Int32@12 | always with W |
| A, B points | block 40..63 | v1 left (3.4); v2 per table |
| mesh slice | block 16..39 | left; KCD rebuilds on save |
| computed slots | per `.cab` formula | listed; re-evaluated only after E6 |
| settings pairs, suffix, strings | | unchanged |

### 4.6 When to stop and ask

Stop the unit step for that wall (length still applied) on any Tier C condition, when two Tier A rules compete (filler at the end and a spanner reaching the end with nothing under it), or when W-dependent computed slots cannot be listed (catalog missing). Stop the whole wall on 2.3 failures and 2.4 loop discrepancies. Never write when a post-edit `check_room` has a hard failure or any byte outside the wall/unit records changed.

---

## 5. Output

- **File** `<original name> - REM <rem job> applied - TEST.job` next to the input (never the input; existing output replaced only after asking). Same size as the input; read back after writing.
- **Report** `<same> - REPORT.txt`: one block per wall — `wall 7 (Linen): 25 1/4 -> 25 1/8 (-1/8) [6414 -> 6382]; wall 9 moved with it (-32, 0)`, the run before/after (`corner | Tall Filler 3/4 | Tall 1 Opening 24 | Filler 74 16 3/4 -> 5/8 | end`), per-unit lines (`unit 11 'Filler 74 16': W 3/4 -> 5/8 [190 -> 159] (A2 filler absorbs)`), READY items with the exact tick/command, CHECK items, room facts not applied (BB, F, HO, HD, Door, Molding, HOLES), read-out lines not used, standard tail (3-D view and print pages stale; TEST until KCD saved it). Three levels: **CHECK**, **READY**, **NOTE**.
- **Sidecar** `<same> - CHANGES.json`: every byte range written (offset, length, old/new hex, wall/unit id, rule id), the requests with their decisions, tool version. Input to the byte-compare (7.3).
- **CLI** first (`python kcdwalls.py JOB --rem REM.json --out NEW.job [--anchor start|end|split] [--accept 9,15] [--no-units]`); tkinter window (job, JSON, wall table with decisions, tick boxes for READY, run, open report) after E4, built like KCD ROOM SPLITTER.

---

## 6. Build order

1. `kcdrem.py`: JSON reader with the 2.1–2.3 grammar and decision table; tests on COYNE and WERNER JSONs.
2. Run model (4.1) on `walls10.txt` and the three jobs; eyeball run facts against the absorb report.
3. Tier A rules + unit byte writer + CHANGES.json; self-test: apply and revert on every live wall of the three jobs, byte-identical; re-run `experiments/walls_selftest.py`.
4. `kcdwalldiff.py` (7.3).
5. Experiments E0–E3 with the owner; decide 3.4/3.5 policy; v2 writes if needed.
6. Tier B proposals and `--accept`; E4–E7.
7. Window, exe, notes update, README. Adding a unit record (B3) is a later step with its own KCD ground truth.

---

## 7. Validation plan

### 7.1 Principle
Every write is proven against a file KCD itself saved after the same operation. The first three experiments need **no tool at all** and decide the open questions (which end moves, whether unit points/notes are recomputed, what a typed W does to the state byte and computed slots).

### 7.2 Experiments for the owner, smallest first (copy of a small design job: COYNE Linen or WERNER design; Save As under the given name; files back via OneDrive `me and claude\REM TESTS\`)

| # | Owner does in KCD | We compare | Pass | If it fails we learn |
|---|---|---|---|---|
| E0 | Open, change nothing, Save As `… E0 RESAVE.job` | E0 vs original: only header blob/L, mesh, serial, pictemp padding may differ | save-noise list holds | the noise list is incomplete |
| E1 | Open one wall's properties (open-chain wall with no units, e.g. COYNE Linen #9 = 38), type 39, OK; note which end moved; Save As `… E1 WALL+1.job` | E1 vs E0: wall offsets (expect 20/100/108, P1/P2 or P0/P3), downstream points, every unit's block 40..63 in that room, notes on that wall, roomshapes | wall bytes equal our `resize_wall`; anchor known; unit/note behaviour known | KCD stores something we do not write, or re-derives points |
| E2 | Change one cabinet's Width by exactly 1" and one **filler's** width by 1/8" in their size dialogs; Save As `… E2 UNITS.job` | slot 2 + state byte, block @12, block 40..63, mesh slice, computed slots (filler stiles, openings), settings pairs | every byte a W edit touches is known | unit writer missing fields |
| E3 | Open our TEST file for the E1 edit, look at plan and elevation, Save As `… E3 TOOL.job` | E3 vs E1 identical outside noise; E3 vs TEST shows what KCD "repaired" | identical | KCD rewrote stale A/B or notes → v2 writes them; or KCD refused → stop |
| E4 | Open the COYNE TEST file (full remeasure, walls only), check each room's plan, Save As | E4 vs TEST; `check_room` on E4; unit points | all rooms consistent, accepted | chain translation bug or multi-room side effects |
| E5 | Open the GODDARD design TEST file with wall 6 → 88 7/8 (closed loop, wall 7 absorbs), Save As | as E4 plus the absorbing wall | accepted | KCD treats closed rooms differently |
| E6 | Open a TEST file with a Tier-A filler change (COYNE wall 7: Filler 74 16 3/4 → 5/8), open the filler's size dialog without changing, screenshot UNIT PRICE REVIEW for it, Save As | slot 2/state, @12, computed slots, mesh | filler shows 5/8 and the review line matches | KCD derives W elsewhere or recomputes stiles only on edit |
| E7 | Open a TEST file with a wall height change (B5), Save As | @28/96/104 and anything else | accepted | height has more copies |

Release to engineers only after E3, E4 and E6 pass.

### 7.3 Byte-compare on what KCD saves back (`kcdwalldiff.py`)
Input: original, our TEST, KCD's saved file(s). Per section via `kcdjob.parse`: (1) save-noise classification (header blob/L, mesh, postwall, pictemp = expected; anything else listed); (2) walls: differing offsets decoded by name (L@20, copies, P0..P3, angle, height, flag15, preamble), raw and inches, and whether KCD's value equals ours, the original, or neither; then `check_room()` on KCD's file; (3) units: differing prefix slots (item, label, raw/inches, state old/new), block fields (@0, @12, 16..39, 40..63 decoded against the 3.4 formulas), strings, suffix; (4) notes: header six Int32 and trailer, text, kind, wall id; (5) settings pairs, roomshapes, defaults, handles equal/not; (6) verdict lines in CHECK/NOTE wording plus the decision each experiment was built to make (`anchor`, `A/B points: recomputed / kept / moved`, `notes: moved / kept`). Also re-run `experiments/walls_selftest.py`, the three-job apply-and-revert self-test, and `kcdcompare.py`.

---

## 8. Risks and unknowns
See the risks list in the structured output (same twelve items).