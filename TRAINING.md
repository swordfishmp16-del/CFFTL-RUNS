# TRAINING: rules Mike has taught the run sessions

Every run session reads this file before each `run <order>`. The rules here are the owner's own words, made in the
training session. A rule here wins over an older line in the run book until the run book is updated to match.

How this file is kept (for the training session):
- Mike trains in a cloud session on this project. Every rule he states in words goes in here the same day, as a
  dated line under its subject, in plain words, with the job it came from.
- The same change is saved in BOTH projects, so neither falls behind: `CFFTL-RUNS` branch `main` (what the run
  session on Mike's laptop uses) and `CFFTL-WORKING-` branch `production` (the learning project). Commit in one,
  then bring the other to the very same commit (`git fetch` + fast-forward), never two different copies.
- A rule that needs a tool change also goes into the tool, the run book (`.claude/skills/kcd-apply-rem/SKILL.md`)
  or `kcd-room-splitter/CLAUDE.md`, saved in both projects the same way.
- The run session on the laptop never edits this file: it only reads it (and `git pull`s first).

## Where the files are
- 2026-10-21: the finished folder `C:\grok rem completed\<order> <NAME>\` holds ONLY the room KCD files (.job)
  and the workbooks (.xlsm). A bot moves it as it is into the production folders on the server. Every report, the
  inputs and any work file go to `C:\grok rem reports\<order> <NAME>\`. (kcdrun.py does this itself.)
- 2026-10-30: the run project lives IN the in folder: `C:\REM IN GIT` is the clone of `CFFTL-RUNS`. 
- 2026-10-30: Mike never attaches or drops files into a session. He saves the KCD file and the REM scan in the REM IN
  folder `C:\grok rem in` and types only `run <order>`. The session goes and gets them from there itself (or from
  the top of `C:\REM IN GIT`), at once; it never asks for them and never searches anywhere else.
- 2026-10-30: one fresh LOCAL session per job, opened on `C:\REM IN GIT`; Mike types only `run <order>`. Everything
  else (the files, the sale page, the rules) the session finds itself. A cloud session cannot do this.
- 2026-10-30: in a cloud session the only job files are the ones attached to the message; never search for them.

## Reading the REM sheet
- 2026-10-20 (1089711 LAZO): a printed designer name that is crossed out with another name handwritten beside it is
  NOT given to the run as the designer; the handwritten name goes in the report as a suggestion to confirm.
- 2026-10-20 (1089711 LAZO): when the measured door opening does not equal the wall minus the two returns, say so
  in the CHECKs with the numbers; never change a wall to make it add up.
