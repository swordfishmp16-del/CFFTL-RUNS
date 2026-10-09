# KCD ROOM SPLITTER

Takes one KCD job that has several rooms and makes one `.job` file per room, named with the job number and the room name, for example `1080458 PANTRY.job`. KCD does not need to be installed on the computer that runs it.

> **Status: test version.** Open a few of the room files in KCD and check them before using them for production.

## Using it

1. Python 3 must be installed on the computer.
2. Drag the multi-room `.job` file onto **`Split KCD job.bat`**.
3. Type the job number and press Enter.
4. The room files appear in a new folder next to the original, named like `1080458 rooms`. The original job is not changed.

From a command prompt you can do the same with:

```
python kcdsplit.py "JOB FILE.job" 1080458 "OUTPUT FOLDER"
```

## What each room file keeps

The tool deletes the other rooms the same way KCD does when you delete a room yourself. The rules were matched byte for byte against a job that KCD saved after rooms were deleted in it.

| Part of the job | What happens |
|---|---|
| Room list | Only the one room. It becomes room 1 and is the room that opens. |
| Walls | That room's walls are unchanged. Other rooms' walls stay in the file as deleted (blank) entries, as KCD leaves them, so no wall number changes. |
| Cabinets and accessories | The ones on that room's walls are unchanged. Other rooms' cabinets stay in the file as deleted entries, as KCD leaves them, so no cabinet number changes. |
| Notes and dimension labels | Only that room's notes. |
| Handle set and unit-info defaults | The kept room's set. |
| Saved camera view | The kept room's view. |
| Job heading, colours, materials, textures, error log, print pages | Copied unchanged. |
| 3D view data | Copied unchanged. KCD rebuilds it the next time the room file is saved. |

Every file is read back after it is made. If any room does not come out with exactly its own walls, cabinets and notes, the tool stops and saves nothing for that job. It also stops, without changing anything, if a room file with the same name is already in the output folder.

## Limits

- Only KCD version 23 jobs.
- A few jobs use record layouts the tool does not read yet. The tool stops with an error on those instead of guessing.
- The 3D view data and print pages are copied whole, so each room file is about the size of the original job. If a room's 3D view looks wrong when it opens, save the file once in KCD and KCD rebuilds it.
- A few cabinet figures that KCD works out itself (they look like price totals) are left as they were in the full job. KCD updates them when the room file is saved.

## Files

| File | What it is |
|---|---|
| `kcdjob.py` | Reads a KCD v23 `.job` file into its sections. |
| `kcdsplit.py` | Makes the room files. |
| `kcdcompare.py` | Compares two `.job` files section by section, for checking against a split made in KCD. |
| `Split KCD job.bat` | Drag-and-drop launcher for Windows. |
