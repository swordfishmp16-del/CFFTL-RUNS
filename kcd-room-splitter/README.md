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

| Part of the job | What happens |
|---|---|
| Room list | Only the one room. It is also the room that opens. |
| Walls | Only that room's walls, numbered again from 1. |
| Cabinets and accessories | Only the ones placed on that room's walls, numbered again from 1. Deleted leftovers that KCD keeps in the file are dropped. |
| Notes and dimension labels | Only that room's notes. Their wall numbers are updated. |
| Handle set and unit-info defaults | The kept room's set. |
| Job heading, colours, materials, textures, error log, print pages, 3D view data | Copied unchanged. |

Every file is read back after it is made. If it does not come out with exactly the one room, its walls, its cabinets and its notes, the tool stops and saves nothing for that job.

## Limits

- Only KCD version 23 jobs.
- A few jobs use record layouts the tool does not read yet. The tool stops with an error on those instead of guessing.
- The 3D view data and print pages are copied whole, so each room file is about the size of the original job.

## Files

| File | What it is |
|---|---|
| `kcdjob.py` | Reads a KCD v23 `.job` file into its sections. |
| `kcdsplit.py` | Makes the room files. |
| `kcdcompare.py` | Compares two `.job` files section by section, for checking against a split made in KCD. |
| `Split KCD job.bat` | Drag-and-drop launcher for Windows. |
