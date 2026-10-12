# KCD ROOM SPLITTER

Takes one KCD job that has several rooms and makes one `.job` file per room. It does the same thing as opening the job in KCD, using Save As for each room and deleting every other room. KCD does not need to be installed on the computer that runs it.

> **Status: test version.** Open a few of the room files in KCD and check them before using them for production.

## Using it

1. Copy **`KCD ROOM SPLITTER.exe`** to the computer (the desktop is a good place). Python is not needed.
2. Open it and click **Choose KCD job...**, or drag a `.job` file onto its icon.
3. Type the **job number** and the **customer last name**. If the job's file name starts with them, they are filled in for you.
4. Check the list of room files and the flags, then click **SPLIT ROOMS**.

The room files are saved in **`C:\KCD ROOM SPLITTER\<job number> <last name>\`**, for example `C:\KCD ROOM SPLITTER\1080458 NOTIK\1080458 NOTIK PANTRY.job`. The program makes the `C:\KCD ROOM SPLITTER` folder itself if it is not there. A split report (`1080458 NOTIK SPLIT REPORT.txt`) is saved with the files. The original job is never changed.

If room files for the job are already in the folder, the program asks before replacing them.

## Room names come from the sidebar

Each file is named `<job number> <last name> <room name>.job`. The room name is the one written in the room's sidebar, the `ROOM DETAILS <name>` note.

- If a room has no sidebar, or its sidebar only says something like "Room 1", the KCD room list name is used and the room is flagged.
- A room that only holds another room's sidebar is not given its own file. These are rooms with no cabinets, often called SIDEBAR, NOTES, Specs or "Room 2". It goes into the file of the room it describes, the same way the team keeps them together today. The program matches them by the name in the sidebar, by the room name (for example "OFFICE NOTES" goes with "OFFICE"), or because there is only one other room.

## Flags

**CHECK** means look at it before using the file. **NOTE** is for information only. The program flags:

- The sidebar name and the KCD room list name are different (spacing, capitals and punctuation are ignored).
- The room has no sidebar, a sidebar with no name, or two sidebars with different names.
- The room is only called "Room N".
- The room has no walls or no cabinets.
- The name has words like OLD, COPY, OPTION/OPT, ALT, TEST, DELETE or VOID in it.
- Two rooms would get the same file name. The second one gets "(2)".
- A sidebar room could not be matched to a room. It is made as its own file.
- Cabinets, walls or notes that do not belong to any room. They cannot go in any room file.
- Characters Windows does not allow in file names (like `/`) were changed to `-`.
- The job folder has other `.job` files the split did not make, for example from an older split.

## Double check

Nothing is saved unless every check below passes. If any check fails, the program stops and saves nothing.

- Every room file is read back and compared with the original job:
  - Its own room(s), walls, cabinets, notes, handle set and unit-info defaults are unchanged.
  - Every other room is deleted the way KCD deletes a room.
  - Everything job-wide is copied unchanged.
- The files are compared with each other. Every wall, cabinet and room note in the job must be in exactly one room file.
- Every file is read back from disk after it is saved.

The deleting rules were matched against a job that KCD itself saved after rooms were deleted. Everything that depends on the room came out identical. What was different is what KCD works out again when it saves:
- the 3D view data
- some cabinet totals
- the scroll position
- the KCD serial

Before release it was run on every KCD v23 job on the test laptop. That was 146 jobs and 290 room files, and all of them passed.

## What happens to each part of the job

| Part of the job | What happens |
|---|---|
| Room list | Only the room (and its sidebar room, if it has one). It becomes room 1 and is the room that opens. |
| Walls | That room's walls are unchanged. Other rooms' walls stay in the file as deleted (blank) entries, as KCD leaves them, so no wall number changes. |
| Cabinets and accessories | That room's cabinets are unchanged. Other rooms' cabinets stay in the file as deleted entries, as KCD leaves them, so no cabinet number changes. |
| Notes, dimension labels and the sidebar | Only that room's. |
| Handle set and unit-info defaults | The kept room's set. |
| Saved camera view | The kept room's view. |
| Job notes file name (.RTF) | Changed to the new file's name, as KCD does with Save As. If the .RTF is next to the original job, it is copied too. |
| Job heading, colours, materials, textures, error log, print pages | Copied unchanged. |
| 3D view data | Copied unchanged. KCD rebuilds it the next time the room file is saved. |

## Limits

- Only KCD version 23 jobs.
- A few jobs use record layouts the program does not read yet. It stops with a message on those instead of guessing; split them in KCD by hand.
- The 3D view data and print pages are copied whole, so each room file is about the size of the original job. If a room's 3D view looks wrong when it opens, save the file once in KCD.
- A few cabinet figures that KCD works out itself (they look like price totals) are left as they were in the full job. KCD updates them when the room file is saved.
- Windows may warn the first time the program is opened on a computer, because it is not signed. Click **More info**, then **Run anyway**.

## Files

| File | What it is |
|---|---|
| `kcd_room_splitter.py` | The program window. It also has a command-line mode for testing: `--cli JOBFILE --job N --name NAME [--out DIR] [--replace] [--check-only] [--log FILE]`. |
| `kcdsplit.py` | Room names, flags, making the room files and the double check. |
| `kcdjob.py` | Reads a KCD v23 `.job` file into its sections. |
| `kcdcompare.py` | Compares two `.job` files section by section, for checking against a split made in KCD. |
| `build_exe.bat` | Builds `KCD ROOM SPLITTER.exe` (needs Python and internet the first time). |
