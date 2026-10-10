# OLD SCHOOL JEWELRY TRAY APP

Daily WOODWOP board builder for Jewelry Trays Direct (JTD).

Open the Shopify export and the app gives you:
- the filled-in WOODWOP board files (`.mpr`)
- a printout of each board with the order number on each tray
- the tray bottoms list for CutRite

## Putting it on a computer

**Stand-alone program (use this one):**
1. Copy **`OLD SCHOOL JEWELRY TRAY APP.exe`** to the computer, on the desktop or in a folder of your choice. There's nothing to install.
2. Double-click it. The app opens in its own window. It uses Microsoft Edge (or Chrome) to draw the screen but has no address bar and needs no internet.
3. The first time, in step 1 under **Save folder on this computer**, click **Choose folder…** and pick where each day's folder should go, e.g. `C:\Jewelry Trays\Boards`. You can also type the path. **The L: drive is refused**, including another drive letter or a `\\server\share` path that leads to the same place as L:. Each person can pick their own folder, and each computer remembers its own choice.
4. Each day, click **Save everything to folder**. The app makes a folder like `101026 DAILY TRAYS #4354-4377` in your save folder, with the board files and bottoms list inside. Click **Open folder** to see it, then move that folder to the L: drive when it's needed.
   - Nothing is ever overwritten. Saving the same day again makes `… (2)`, and a single board saved twice becomes `… 1 (2).mpr`.
   - **Save .mpr to folder** on a board saves just that board into the day's folder.
5. Closing the window closes the app. The program stops by itself about 10 minutes later. Opening it again while it's still running just opens a new window.

The first time Windows runs it, it may say "Windows protected your PC" because the program isn't signed by a publisher. Click **More info**, then **Run anyway**. If your company's IT blocks unsigned programs, use the single-file version below.

**Checking a computer:** `desktop\test-on-windows.ps1` tests the program on a real Windows computer without opening a window:
- the page loads
- the L: drive and the network share behind it are refused
- a normal folder works
- saving never overwrites and keeps every byte

It uses a throw-away folder in `%TEMP%`, writes nothing to L: or the real settings, and prints PASS/FAIL. Close the app first, then run: `powershell -ExecutionPolicy Bypass -File desktop\test-on-windows.ps1`.

Two more checks sit next to it:
- `test-window-on-windows.ps1` opens the real app window and the **Choose folder…** picker, presses OK and Cancel, and checks the result. A window flashes on screen for a few seconds.
- `test-l-share-on-windows.ps1` is for a computer with no L: drive. It briefly maps a test L: and N: to the same throw-away folder, so the network-share checks really run, then removes both.

**Tested on Windows (10/10/2026, Mike's laptop CFF1FTLLP-9A90EG, Windows with Chrome, no Edge):** all three scripts passed, along with the Go unit tests, against the program built on that laptop from this source.
- The app opened in its own Chrome window.
- The folder picker's OK set the folder, and Cancel changed nothing.
- L:, the share behind it and a second letter on that share were all refused, and nothing was written to the test L:.
- Saving made the day folder and "(2)" copies, never overwrote a file, and kept every byte.

**Single-file version (backup):** `OLD SCHOOL JEWELRY TRAY APP.html` does the same work in a browser tab, but files go to the Downloads folder (as a .zip) instead of a folder you pick.

Your `_2 TALL` and `_3 TALL` templates (copies Mike sent 10/8/2026) are inside both versions, so there's nothing to load. Neither version touches Shopify or the internet, and neither ever writes to the L: drive.

**If you change a template in WOODWOP:** in step 1, click **Load a different one** and pick the new file. That computer uses the new file from then on, and **Go back to the built-in one** undoes it. To change the template for every computer, send the new file so the app can be rebuilt with it.

## Every day

1. Export the orders from Shopify (`shopify_export_MMDDYY.csv`).
2. Open the app and drag the CSV onto step 2. **Or** copy just the lines you want from the export (in Excel or a text editor) and paste them into the box in step 2, press Ctrl+V anywhere on the page, or drag the selected lines onto step 2. The header row is optional. Pasted lines are always used, whatever the order range says, and a line pasted twice only counts once.
3. Set **Orders from # / to #** for today. The app suggests starting right after the last order it made boards for on that computer.
4. **Rush orders:** type the order numbers in **Rush orders** (e.g. `4360, 4372`). They go on the first sheet, even if they're outside the from/to range.
5. Untick anything you are not cutting. Fix any size, height, qty or label.
6. If a board isn't full, go to **Fill empty slots with stock** at the top of step 3. Pick a stock size for the **2" sheets** and one for the **3" sheets**, then click **Fill with stock**. The empty slots fill with that size, labeled e.g. `STOCK 22IN`.
7. In step 3, click **Download everything (.zip)**. You get a folder named like `100226 DAILY TRAYS #4351-4368` that holds:
   - `100226 DAILY TRAYS 1.mpr`, `2.mpr` … (2" boards)
   - `100226 DAILY TRAYS 3 3IN.mpr` … (3" boards)
   - `100226 TRAY BOTTOMS.csv`
8. Click **Print boards with labels** for the shop copy.

## Sharing with the team

- Any team member can run it: copy the `.exe` to their computer, or keep one copy in a shared folder (not on L:) so an update only has to be dropped in once.
- Nothing goes over the internet. The program only listens on its own computer (127.0.0.1), never touches Shopify, and never writes to the L: drive.
- What each computer remembers is kept only on that computer: its save folder, the last order number boards were made for, the stock sizes picked, and any template loaded by hand. The settings are in `%LOCALAPPDATA%\OldSchoolJewelryTrayApp`. Two people building boards on two computers won't see each other's work, so agree on who runs the boards each day.

## Logo

The printouts carry the Jewelry Trays Direct logo from `assets/logo.png`. The current file is a redraw made from the picture Mike sent 10/10/2026 (`assets/logo-redraw.svg`). Replace `assets/logo.png` with the real logo file and run `node build.js` to use the exact one.

## Rules it follows

Mike decided these on 10/8/2026. Rules marked HANDOFF come from `docs/HANDOFF.md`.

| Rule | Detail |
|---|---|
| WOODWOP sizes | Full tray size converted to mm, 2 decimals. Example: 21 5/16 x 14 1/8 gives 541.34 x 358.78. |
| Bottom sizes | Tray size minus 9/16", in mm. Example: 21 5/16 x 14 1/8 gives 527.05 x 344.49. Each bottom is 1/4 MELAMINE, grain N. |
| Trays per board | However many slots the template has. The `_2 TALL` template has 16 and the `_3 TALL` has 12. |
| 2" and 3" | Never on the same board. 3" boards get `3IN` in the file name. |
| What changes in the template | Only the `trNw` / `trNd` values (the red column in WOODWOP). Comments, contours and machining are copied byte for byte. Empty slots stay `102`. |
| Qty | A line with qty 3 takes 3 slots. |
| Tray 1 | At the bottom of the sheet, same as WOODWOP. |
| Labels | Default to the order number. You can type over a label, e.g. `2391 - 3IN`. |
| Standard sizes on orders | Go through like any other tray (e.g. `Small 22"W x 13 3/8"D` from the item name). Label is the order number. (Mike, 10/10/2026) |
| Rush orders | Type one or more order numbers in **Rush orders**. Their trays go into the first slots, starting at tray 1, and the sheet they're on becomes board 1 (a 3" rush sheet comes right after the 2" one) so it gets cut first. A rush order is included even if it's outside the from/to range. Rush trays are marked **RUSH**: a red tag in the list, `4360 RUSH` on the printout, and the board header says **RUSH — CUT FIRST**. Rush bottoms are listed first and described `4360 RUSH`. If a number isn't in the export, or the order has nothing ticked, the app says so under the box. (Mike, 10/10/2026) |
| Fill with stock | At the top of step 3, one stock-size dropdown for **2" sheets** and one for **3" sheets**, each with its own **Fill with stock** button. Every board with empty slots also has the same dropdown. Sizes: STOCK 21IN, 22IN, 27IN, 28IN, 33IN, 34IN, all 13 3/8 deep. Defaults are 22IN for 2" and 34IN for 3", and each computer remembers the last pick for each height. Stock fills only the empty slots and never starts a new board. Two sizes can share the slots: fill some, change the qty on the stock row, then fill again. Stock trays are labeled `STOCK 28IN` on a yellow tag, and the bottoms list gets them with UNIT # `STOCK`. (Mike, 10/10/2026) |
| Too long for one strip | Split into 2 side-by-side slots, the way order 4356 was done on 10/2. The first slot holds the tray width and the next holds the tray depth, with `102` in the depth spot of both. The first strip gives the 2 width sides and the second gives the 2 depth sides. The printout labels them `4356 WIDTHS` and `4356 DEPTHS`. A pair is never split across two boards. If only 1 slot is left, the next single tray fills it. The tray still gets just one bottom. (Mike approved this 10/8/2026.) |

### What it skips (each row stays in the list with the reason)

- **Not trays:** add-ons, inserts, flat liners and measurement charges. They're never cut as trays.
- **Lines with no size** in the size columns or the item name. Type a size and tick the row to cut one.

### What it flags

- A 4" or 5" tray. There's no template for these yet, so they're done by hand.
- A tray too long for the board even when split in two (wider than about 43").
- A blank height. The app uses 2" and flags it.
- An order with an "Extra Tray Height" charge whose trays still say 2".

## Not decided yet

- **4" and 5" trays.** The `_4 TALL 36IN TRAYS.mpr` program works differently, so the app does not handle it.
- **Getting the CSV into CutRite.** The bottoms CSV uses the same columns as the old daily sheet.

## For whoever works on the code

- `src/core.js` holds the tray rules, and `src/app.html` is the screen.
- `templates/` holds Mike's real `_2 TALL` / `_3 TALL` templates, and `templates/templates.json` lists them.
- `desktop/` is the stand-alone Windows program (Go, standard library only). It shows the same page in its own Edge/Chrome window, saves files into the picked folder, and refuses L: (`desktop/folders.go`). The icon and version info are in `desktop/rsrc_windows_amd64.syso`, made from `assets/icon.png` with go-winres.
- `node build.js` combines the code and the templates into `OLD SCHOOL JEWELRY TRAY APP.html` and, if Go is installed, builds `OLD SCHOOL JEWELRY TRAY APP.exe` (Windows 64-bit). Rebuild after every change.
- `cd desktop && go test ./...` checks the L: drive rules, the no-overwrite saving and the day-folder naming.
- `node --test test/core.test.js` checks the rules against the worked examples in `docs/HANDOFF.md` and the real templates. Each filled board must match the template byte for byte outside the tray sizes.
