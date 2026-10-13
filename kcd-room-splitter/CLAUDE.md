# KCD tools: working notes

Notes for whoever works on this next (a person or Claude). They hold what was learned while building KCD ROOM SPLITTER, so later tools can build on it. Keep them up to date when you learn something new.

## Who it is for and how they work

- Closet Factory Fort Lauderdale. Designers draw in **KCD Software v23**; engineering splits multi-room jobs into one job per room before production.
- Write for non-programmers. Plain words, short steps, no jargon in anything the user sees.
- **Room file name:** `<job number> <LAST NAME> <room name>.job`, for example `1080458 NOTIK PANTRY.job`.
- **Room names come from the sidebar.** The sidebar is a note in the room whose text starts with `ROOM DETAILS <room name>`. After that come lines like `HEIGHT-`, `MATERIAL/COLOR-`, `EDGE BANDING-`, `BACKING-`, `CLOSET RODS-`, `HANDLES/KNOBS` and `DOOR/DRAWER STYLE`. The KCD room list name is often different (shorter, typos, "Room 1").
- **Sidebar rooms.** Some jobs keep the sidebar in its own room: no cabinets, usually one wall, and a name like SIDEBAR, sidebar, sidebr, NOTES, "<room> NOTES", "<room> Specs" or "Room 2". In finished room files that room travels with the room it describes, as a second room in the same file.
- **Job heading.** In finished room files the team often fills in the KCD job heading (5 lines) with the job number, last name, short room name and designer/engineer. The format varies by person, for example `['1078079', 'DIMAURO', '1CARGYM', 'JOYES']` or `['1084414 DUARTE', 'ENTRY', '', 'ANDREA ARANA', 'DIEGO']`. The splitter does not fill it in yet.
- The user wants questionable things **flagged** (CHECK = look at it, NOTE = information), never silently fixed or guessed.
- **Never commit customer job files or customer data.** Code only.

## KCD ROOM SPLITTER (done, in use)

- `kcd_room_splitter.py` is the window (tkinter). It also has a CLI mode for testing: `--cli JOBFILE --job N --name NAME [--out DIR] [--replace] [--check-only] [--log FILE]`.
- `kcdsplit.py` does the planning (names, sidebar pairing, flags), builds the room files (`keep_rooms`), checks them (`verify`, `reconcile`) and writes the report.
- `kcdjob.py` is the `.job` reader.
- `kcdcompare.py` compares two jobs section by section.
- Output goes to `C:\KCD ROOM SPLITTER\<job> <NAME>\` plus `<job> <NAME> SPLIT REPORT.txt`. Files are built and checked in a `_working ...` folder, then moved in. Existing files are only replaced after asking.
- Build `KCD ROOM SPLITTER.exe` with `build_exe.bat` (PyInstaller 6.11.1 in a venv, `--onefile --windowed`). It must be built on Windows; the exe is about 10 MB and needs no Python.
- **Distribution:** the exe is in the user's work OneDrive folder `KCD ROOM SPLITTER` (with a .zip copy). It is confirmed working on the user's work computer.

## KCD v23 `.job` format (as far as known)

VB.NET-style binary:
- Strings: `STR` = UInt16 length + bytes (cp1252).
- Int16/Int32 little-endian. Booleans are 0/-1.
- Arrays are often written 0..n (n+1 entries).

`kcdjob.parse(data)` returns sections `(name, start, end, info)` that tile the file exactly. A writer rebuilds a file by joining section bytes. Sections, in order:

| Section | Layout |
|---|---|
| header | STR version (`Version # 23.000`), 12 bytes, UInt16 n + opaque save blob, STR `** Job Heading **`, 5 STR heading lines, 2 STR dates, 2 bytes, 5×Int32 `L` (L[2]=mesh verts+1, L[4]=mesh faces+1), Int16 nwalls, Int16 nunits, STR rtf (job notes file name), Int16 nl + nl×(STR, Int16), STR current library, 82-byte view block, STR `** Rooms **`. |
| view block | Bytes 0..51 are the current room's camera (copied from that room record's first 52 bytes). Int32 at +60 is the note count. |
| rooms | Int16 n, 2 bytes, Int32 current room, then n records: 62 bytes (camera etc.), STR name, 14 bytes, 10 STR (edge/door profile names). |
| handles | (n+1) sets × 9 × (STR, 28 bytes, STR). Set 0 is the default; set k belongs to room k. |
| settings | STR handle group + 9 STR door-style names, Int16 nc + (nc+1)×6 (colour table), Int16 nlo + nlo×(STR library, Int16 k, k×6 shop-standard sizes as Int16 item + Int32 value), Int16 npair + npair×(Int16 unit id, Int16 option code). Option number = code + 1 in the library's `options.dat`. |
| walls | nwalls × (205 bytes + STR texture + 5 bytes). Wall id: Int32 at 125 (Int16 copies at 117/119/121/123). Room: Int32 at 129. Neighbour wall ids: Int32 at 36 and 40. |
| postwall | 16 bytes + STR (KCD user serial). |
| units (cabinets) | nunits × [1806-byte prefix][body][27-byte suffix]. The prefix is 301 six-byte size slots (slot N at byte 6N: Int32 value in 0.1 mm, state byte, 0), labelled by the unit's `.cab` file; see `kcd-deep-dive-notes.md`. Body: 9 STR (cat, cab, lib, prt, pcb, name, edge, shp, profile), 86-byte block, 8 STR materials, 7 STR, 10 bytes, 2 STR (unw, unwname). In the 86-byte block: Int16 at 0 is the wall id (0 = deleted), Int16 at 2 is a flag, Int16 at 10 = number of size items in the `.cab`, Int32 at 12 = width, 16..39 are geometry counts (not prices), 40..63 two centre points, Int16 at 64 = unit type code, Int16 at 66 = unit quantity. The 8 + 7 STR are Set Unit Info texts 1..15 (text 1 = material name and price multiplier). Suffix: Int32 group at +4, unit id Int16 at +12/+14/+16. |
| mesh | 3D cache: Int32 n1 + 4·n1, (L2−1)×12 vertices, index ints, (L4−1)×66-byte faces, ending exactly at `** Notes **`. |
| notes | STR `** Notes **`, Int16 count, records: 30 bytes, STR text, STR font, STR size, 36-byte trailer (Int32 room at trailer+4; 0 = job-wide). Header Int16 at +24 = wall id when nonzero. Empty-text notes are dimensions. |
| roomshapes | Int16 + (n+1) slots × [Int32 cnt; cnt × (Int32 npts + npts×24 + 16 bbox + 16 bytes with Int32 tag first + Int32 m + m×4)]. Only slot 0 seen in practice; tag = room number. |
| materials | Int32 1008 + 1009×72, then Int32 1008 + 1009×(STR + 20). |
| errlog | 4 bytes, Int16 ne, ne+1 STR. |
| gap | Zeros up to `Start-PicTempZipFile`. |
| pictemp | STR `Start-PicTempZipFile` … a ZIP of the print pages (jpg renders, emf elevations, .DAT page info) … STR `End-PicTempZipFile` + 4 bytes. |
| defaults | STR `Start-UnitInfoDefaults`, Int32 14, Int32 nrooms−1, nrooms × 15 STR. Set k−1 belongs to room k. |

- **Membership:** a cabinet belongs to the room of its wall; a note has its own room field.
- **How KCD deletes a room** (matched byte for byte against a file KCD saved): it is a soft delete, so wall and cabinet ids never change.
  - Walls: bytes 16..112 are zeroed except {32–35, 46–49, 82–85}, and the room is set to 0.
  - Cabinets:
    - the prefix is zeroed;
    - cab, lib, prt, pcb, materials, the 7 STR and unw/unwname become empty, and the name is stripped;
    - shp becomes `SQ3.shp` and profile `3" Square`;
    - 86-block offsets 0–3, 16–39 and 66 are zeroed, the 10 bytes are zeroed, and suffix[0:8] is zeroed.
  - Kept rooms are renumbered 1..k in walls, notes and room shapes. Notes of deleted rooms are removed, and settings pairs of deleted cabinets are dropped.
  - Handles become set 0 plus the kept sets; defaults become the kept sets. The view block gets the first kept room's camera and the new note count, and the current room is set to 1.
- **What KCD recalculates when it saves** (so it is safe to leave stale): mesh, header blob and `L` counts, unit block bytes 16..39 (geometry counts), scroll bytes in wall 1, the postwall serial, and pictemp padding.
- **Save As** sets the header rtf to `<new job name>.RTF`.
- **Not readable yet:**
  - BARNARD SANDY (a note variant);
  - LANGNAS GARAGE and SHOWRM PB OVERALL SHOWROOM (a unit variant: "string past EOF").
  The splitter refuses those safely.

## How things were checked (do the same for new tools)

- Never trust a format guess. Compare against a file KCD itself saved after doing the same operation, using `kcdcompare.py`.
- Run every change over all the jobs on the test laptop: 149 v23 jobs, of which 146 read fully.
- `verify()` re-reads every output and checks it against the original. `reconcile()` checks that every wall, cabinet and room note lands in exactly one file. Saved files are read back from disk.
- The window was tested here on a virtual screen (Xvfb plus a tkinter driver script). The exe was tested on the laptop in `--cli` mode.

## Test laptop (via Desktop Commander)

- Device **CFF1FTLLP-9A90EG**, Windows 11. Python 3.12 with tkinter, pip, Git, internet. **KCD is not installed on it.**
- Job files are in Downloads, OneDrive and Outlook attachments. Work scripts are in `%TEMP%\kcdsplit`; the build venv is in `%TEMP%\kcdbuild`.
- Quirks:
  - PowerShell commands lose `$_`, so run small Python scripts instead.
  - `python -c "..."` with inner double quotes breaks under PowerShell. Write a script file and run it.
  - `start_process` waits at most 3 s; read the rest with `read_process_output`. Big outputs are saved to a local tool-results file, which also works as a file-transfer channel.
  - Only one Desktop Commander copy should run on the laptop; other sessions' servers make the relay flaky.
  - `edit_block` turns `\uXXXX` text into real characters, so edit those lines with a Python script.
  - Check uploaded code with md5 after writing (normalize CRLF).
- **Getting files to the user:** the chat cannot take a 10 MB file from the laptop, and the Microsoft 365 upload tool is capped at 1 MB. Copy into `C:\Users\sword\OneDrive - Closet Factory (Fort Lauderdale)\...`, wait for sync, then get the web link with Microsoft 365 `read_resource` on `file:///<driveId>/<path>`.

## Deep dive into pricing data (Oct 12, 2026)

Read `kcd-deep-dive-notes.md` before working on pricing, door orders or the engineering workbook. Short version:

- Every unit size (width, height, depth, panels, shelves, door and drawer heights, rod heights, options) can be read from the `.job`: the 1806-byte prefix is a table of size slots whose labels come from the unit's `.cab` file in `C:\KCD23\NEW CFFL UNIT LIBRARY`.
- Options are the (unit id, code) pairs at the end of `settings`; option number = code + 1.
- KCD prices from text scripts in `C:\KCD23-STDPLIST\<date> CFFL PRICING` (`Z<unit>.pcb` per unit type, shared grids in `B-Side Cost.Pcb` and `C-Shelf Cost.Pcb`, fee 199 in `H-Discounts and Fees.pcb`). Prices change by swapping that folder, so read it at run time.
- Decoded sizes matched the engineering price reviews line by line on six jobs.
- `kcdunits.py` reads a job into a room sheet (units with labelled sizes, materials, options, quantity, notes, sidebar). Checked against twelve engineered rooms: see notes section 9. `experiments/report_laptop.py` is the older laptop-only decoder.

## Ideas not done yet

- Fill in the KCD job heading (job number, last name, room) in each room file.
- Read the three job layouts above.
- Use the sidebar text (material, edge banding, rods, handles) for checks or reports.
- Build the "read the job, fill the workbook and forms" app once the owner answers the phase-2 questions (see the notes file).
