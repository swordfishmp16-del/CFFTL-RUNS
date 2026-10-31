# Door swing

Written October 31, 2026, so the next session can check this against the paperwork program before anyone codes it.

Door swing means which edge the hinges are on. That is the dotted line KCD draws on the 2D door.

## What the program should do

Read the parts list KCD prints. Do not read swing from the `.job`.

KCD resolves the hinge, including a door that was flipped in the drawing, before it writes the list. In the shop cut list `STDPLIST\_25-06 JUN CUT LIST\Door.prt` (same lines in the LOWES and ODK copies of that file) each door sets `#Hingenote`:

| Note | Hinge edge |
|---|---|
| HL | Left |
| HR | Right |
| HB | Bottom |
| HT | Top |

Take that note off the door line and put it on the paperwork.

A pair is two lines. On the right leaf, `Door.prt` forces a `1` to a `2` before it writes the note, so that leaf comes out `HR` even when the cabinet code was a left hinge.

The list has to be the one KCD just generated for that job. An old list, or the `.job` by itself, will mislabel a door that was flipped.

## Where the digit comes from

The cabinet file stores the hinge as a digit on the door face line. `1` left, `2` right, `3` bottom, `4` top. Same numbers `Door.prt` maps onto `HL` `HR` `HB` `HT`.

`NEW CFFL UNIT LIBRARY\CSE300.cab` (Tall 1 Opening), the unit in the two test jobs:

```text
10101000   left hinge
20202000   right hinge
10102000   the opening beside it, digit changed to 2
20203000   bottom (digit 3)
20204000   top (digit 4)
```

The `1`s and `2`s in that 8-digit code are the hinge digit. A door nobody flipped can also be read by opening the `.cab` the job names. That is only the catalog default.

## What does not work

A single pass of the `.job` cannot tell a flipped door.

Checked on `00000000 claude left door.job` and `00000000 claude right door.job` (Downloads, saved five seconds apart, Oct 28). Both still name `CSE300.cab`. Neither file contains `10101000` or `20202000` as a number. The only content difference is a 144-byte door slot after the material names, plus 6 bytes in one part record. KCD puts a new mask on that slot every save. After removing the mask, the slot is rewritten. It does not come back out as a plain `1` or `2`.

A guess that two flag bits in that slot were the side (left-door file byte 9377 bit 1, byte 9385 bit 3) was checked against about 150 other jobs, including Bunnell, Horn, Saffer, Danter and the Notik rooms. Those bits are not in the other jobs. Do not use them.

Runs of `01 00` and `02 00` show up in almost every job. They are ordinary small integers next to measurements, not the hinge.

## What to check in this program

`experiments/po/soitems.py` builds the special-order door sheet. `kcdcab.py` computes door sizes from the `.cab`. Door lines are still marked VERIFY until the "no door" question is settled (see `kcd-deep-dive-notes.md`).

Before wiring swing into the workbook or the door order:

1. Confirm the parts-list file this program already reads is the KCD cut list, and that the door row actually contains `HL`, `HR`, `HB` or `HT`.
2. If the program only has the `.job` and the `.cab`, it can fill the catalog default and must flag any unit whose door slot was overridden. It must not print a side for that unit.
3. Do not parse the 144-byte slot.
